"""
v3.2.5 Targeted Tests — Immediate finalize dispatch, null-safe page, start/close race
"""
import pytest
import asyncio
from unittest.mock import MagicMock


# ============================================================
# Test 1 — Immediate finalize dispatch from WS handler
# ============================================================

@pytest.mark.asyncio
async def test_immediate_finalize_dispatch():
    """_schedule_immediate_finalize must dispatch finalize within 100ms."""
    from backend.services.autodarts_observer import AutodartsObserver, WSEventState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "IMM-1"
    obs._ws_state = WSEventState()
    obs._finalized = False
    obs._finalize_dispatching = False
    obs._stopping = False
    obs._last_finalized_match_id = None

    dispatched = []
    async def mock_game_ended(board_id, trigger):
        dispatched.append(trigger)
        return {"should_lock": True, "should_teardown": True, "credits_remaining": 0}

    obs._on_game_ended = mock_game_ended

    # Schedule immediate dispatch
    obs._schedule_immediate_finalize("match_end_gameshot_match", "match-imm-1")
    # Wait for the 50ms yield + processing
    await asyncio.sleep(0.2)
    assert len(dispatched) == 1, f"Expected exactly 1 dispatch, got {len(dispatched)}"
    assert dispatched[0] == "match_end_gameshot_match"


# ============================================================
# Test 2 — Safety net skips after immediate dispatch
# ============================================================

@pytest.mark.asyncio
async def test_safety_net_skips_after_immediate():
    """Safety net must not fire if immediate dispatch already ran."""
    from backend.services.autodarts_observer import AutodartsObserver, WSEventState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "SN-1"
    obs._ws_state = WSEventState()
    obs._finalized = True  # Already finalized by immediate dispatch
    obs._finalize_dispatching = False
    obs._stopping = False
    obs._last_finalized_match_id = None
    obs._on_game_ended = None

    result = await obs._dispatch_finalize("match_end_state_finished", "ws_safety_net")
    assert result is None, "Safety net must skip when already finalized"


# ============================================================
# Test 3 — open_session hard stop during close
# ============================================================

@pytest.mark.asyncio
async def test_open_session_aborts_during_close():
    """open_session must abort immediately if _closing is True."""
    from backend.services.autodarts_observer import AutodartsObserver, LifecycleState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "STOP-1"
    obs._lifecycle_state = LifecycleState.STOPPING
    obs._closing = True
    obs._stopping = True
    obs._finalize_dispatching = False
    obs._session_generation = 5
    obs._context = None
    obs.status = MagicMock()
    obs.status.browser_open = False

    # This should return immediately without touching any browser objects
    await obs.open_session("https://play.autodarts.io")
    assert obs._lifecycle_state == LifecycleState.STOPPING, "Lifecycle must not change"


@pytest.mark.asyncio
async def test_open_session_aborts_during_finalize():
    """open_session must abort if _finalize_dispatching is True."""
    from backend.services.autodarts_observer import AutodartsObserver, LifecycleState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "STOP-2"
    obs._lifecycle_state = LifecycleState.RUNNING
    obs._closing = False
    obs._stopping = False
    obs._finalize_dispatching = True
    obs._session_generation = 3
    obs._context = None
    obs.status = MagicMock()
    obs.status.browser_open = True

    await obs.open_session("https://play.autodarts.io")
    # Should not have started anything new
    assert obs._lifecycle_state == LifecycleState.RUNNING


# ============================================================
# Test 4 — Null-safe page access
# ============================================================

def test_page_alive_none_safe():
    """_page_alive must return False when page is None."""
    from backend.services.autodarts_observer import AutodartsObserver

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs._page = None
    obs._context = None
    assert obs._page_alive() is False


# ============================================================
# Test 5 — Watchdog blocks during finalize
# ============================================================

def test_watchdog_blocks_during_finalize():
    """Watchdog must not attempt recovery when finalize is dispatching."""
    from backend.services.autodarts_observer import AutodartsObserver, LifecycleState
    from backend.services.watchdog_service import _should_attempt_recovery

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "WD-1"
    obs._lifecycle_state = LifecycleState.RUNNING
    obs._closing = False
    obs._stopping = False
    obs._finalize_dispatching = True
    obs._close_reason = ""
    obs._last_launch_time = None
    obs._context = MagicMock()  # Needed for is_open property
    obs.status = MagicMock()
    obs.status.browser_open = True
    obs._page = MagicMock()

    from backend.services.autodarts_observer import observer_manager
    observer_manager._observers["WD-1"] = obs
    observer_manager._desired_state["WD-1"] = "running"

    should, reason = _should_attempt_recovery("WD-1")
    assert should is False
    assert "close_or_finalize" in reason

    # Cleanup
    del observer_manager._observers["WD-1"]
    del observer_manager._desired_state["WD-1"]


# ============================================================
# Test 6 — Double immediate dispatch is idempotent
# ============================================================

@pytest.mark.asyncio
async def test_double_immediate_dispatch_idempotent():
    """Two immediate dispatches for same match → only one callback."""
    from backend.services.autodarts_observer import AutodartsObserver, WSEventState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "DUP-1"
    obs._ws_state = WSEventState()
    obs._finalized = False
    obs._finalize_dispatching = False
    obs._stopping = False
    obs._last_finalized_match_id = None

    count = 0
    async def mock_cb(board_id, trigger):
        nonlocal count
        count += 1
        return {"should_lock": True, "should_teardown": True}

    obs._on_game_ended = mock_cb

    # Two immediate dispatches (simulating gameshot + state_finished)
    obs._schedule_immediate_finalize("match_end_gameshot_match", "m-1")
    obs._schedule_immediate_finalize("match_end_state_finished", "m-1")
    await asyncio.sleep(0.3)
    assert count == 1, f"Expected exactly 1 dispatch, got {count}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
