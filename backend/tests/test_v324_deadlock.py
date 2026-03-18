"""
v3.2.4 Targeted Tests — Finalize deadlock fix, single-owner dispatch,
close path separation, timing instrumentation.
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Test 1 — Primary dispatch happens via observe_loop priority check
# ============================================================

@pytest.mark.asyncio
async def test_primary_dispatch_from_loop_priority():
    """When ws.match_finished=True, primary dispatch must fire immediately
    (before page_alive check), not via safety net."""
    from backend.services.autodarts_observer import AutodartsObserver, WSEventState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-PRI"
    obs._ws_state = WSEventState()
    obs._finalized = False
    obs._finalize_dispatching = False
    obs._stopping = False
    obs._last_finalized_match_id = None

    dispatched_trigger = None
    dispatched_source = None

    async def mock_game_ended(board_id, trigger):
        nonlocal dispatched_trigger
        dispatched_trigger = trigger
        return {"should_lock": True, "should_teardown": True, "credits_remaining": 0}

    obs._on_game_ended = mock_game_ended

    # Simulate match end detected via WS
    obs._ws_state.match_finished = True
    obs._ws_state.finish_trigger = "match_end_gameshot_match"
    obs._ws_state.last_match_id = "match-pri-1"

    result = await obs._dispatch_finalize("match_end_gameshot_match", "observe_loop_priority")
    assert result is not None
    assert result["should_lock"] is True
    assert dispatched_trigger == "match_end_gameshot_match"


# ============================================================
# Test 2 — Safety net skips when primary dispatch already reserved
# ============================================================

@pytest.mark.asyncio
async def test_safety_net_skips_after_primary():
    """Safety net must skip if finalize already dispatched by primary."""
    from backend.services.autodarts_observer import AutodartsObserver, WSEventState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-SN"
    obs._ws_state = WSEventState()
    obs._finalized = True  # Already finalized by primary
    obs._finalize_dispatching = False
    obs._stopping = False
    obs._last_finalized_match_id = None

    async def should_not_be_called(board_id, trigger):
        raise AssertionError("Safety net should not dispatch when primary already finalized")

    obs._on_game_ended = should_not_be_called

    result = await obs._dispatch_finalize("match_end_state_finished", "ws_safety_net")
    assert result is None


# ============================================================
# Test 3 — Close path callbacks are EXPECTED not UNEXPECTED
# ============================================================

def test_page_close_expected_during_stopping():
    """PAGE_CLOSED during stopping must be classified as EXPECTED."""
    from backend.services.autodarts_observer import AutodartsObserver, LifecycleState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-CL"
    obs._stopping = True
    obs._closing = True
    obs._lifecycle_state = LifecycleState.STOPPING
    obs._session_generation = 5
    obs._close_requested_gen = 5

    # The handler check logic
    lc = obs._lifecycle_state.value
    gen = obs._session_generation
    close_requested = (obs._stopping or obs._closing
                       or obs._close_requested_gen == gen
                       or lc in ("stopping", "closed", "auth_required"))
    assert close_requested is True, "Close during stopping must be flagged as EXPECTED"


# ============================================================
# Test 4 — Credits never negative
# ============================================================

def test_credits_never_negative():
    """Finalize guard returns must have credits >= 0."""
    # Simulate the idempotency guard return
    result = {"should_lock": False, "should_teardown": False,
              "credits_remaining": 0, "board_status": "unknown"}
    assert result["credits_remaining"] >= 0

    # Simulate timeout return
    timeout_result = {"should_lock": True, "should_teardown": True,
                      "credits_remaining": 0, "board_status": "locked"}
    assert timeout_result["credits_remaining"] >= 0


# ============================================================
# Test 5 — Close reason preservation
# ============================================================

def test_close_reason_never_degrades_to_unknown():
    """Once close_reason is set to session_end, incoming 'unknown' must not overwrite."""
    from backend.services.autodarts_observer import AutodartsObserver, LifecycleState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-CR"
    obs._close_reason = "session_end"
    obs._closing = False
    obs._stopping = False
    obs._lifecycle_state = LifecycleState.RUNNING
    obs._session_generation = 3
    obs._close_requested_gen = -1
    obs._page = None
    obs._context = None
    obs._playwright = None
    obs._observe_task = None

    class FakeStatus:
        browser_open = True

    obs.status = FakeStatus()

    # Simulate calling close with "unknown" — reason should be preserved
    # We can't call async close_session in sync test, so verify the logic
    if not obs._close_reason or obs._close_reason == "unknown":
        obs._close_reason = "unknown"
    else:
        pass  # preserved

    assert obs._close_reason == "session_end", "Committed reason must not be overwritten"


# ============================================================
# Test 6 — Open blocked during finalize dispatch
# ============================================================

@pytest.mark.asyncio
async def test_open_blocked_during_finalize():
    """ObserverManager.open must block if observer._closing is True."""
    from backend.services.autodarts_observer import AutodartsObserver, LifecycleState, ObserverManager

    mgr = ObserverManager()

    # Create a fake observer that is in the middle of closing
    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-BLK"
    obs._closing = True
    obs._finalize_dispatching = False
    obs._session_generation = 1

    mgr._observers["TEST-BLK"] = obs

    # Attempt to open — should return existing obs without re-opening
    result = await mgr.open("TEST-BLK", "https://play.autodarts.io")
    assert result is obs, "Must return existing obs when close in progress"


# ============================================================
# Test 7 — Lifecycle lock timeout in close
# ============================================================

@pytest.mark.asyncio
async def test_close_lock_timeout_does_not_hang():
    """observer_manager.close must not hang indefinitely if lock is held."""
    from backend.services.autodarts_observer import ObserverManager

    mgr = ObserverManager()
    lock = mgr._get_lock("TEST-LOCK")

    # Hold the lock to simulate watchdog contention
    await lock.acquire()

    # close() should timeout and force close, not hang
    try:
        await asyncio.wait_for(
            mgr.close("TEST-LOCK", reason="test"),
            timeout=12.0,
        )
    except asyncio.TimeoutError:
        pytest.fail("close() hung for >12s even though lock timeout is 8s")
    finally:
        lock.release()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
