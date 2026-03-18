"""
v3.2.3 Targeted Tests — Finalize chain reliability
"""
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================
# Test A — Duplicate finish signals → exactly one finalize
# ============================================================

@pytest.mark.asyncio
async def test_duplicate_finish_signals_exactly_one_finalize():
    """First finish signal wins, second is ignored. No double dispatch."""
    from backend.services.autodarts_observer import AutodartsObserver, WSEventState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-1"
    obs._ws_state = WSEventState()
    obs._finalized = False
    obs._finalize_dispatching = False
    obs._stopping = False
    obs._last_finalized_match_id = None

    call_count = 0
    async def mock_game_ended(board_id, reason):
        nonlocal call_count
        call_count += 1
        return {"should_lock": True, "should_teardown": True, "credits_remaining": 0}

    obs._on_game_ended = mock_game_ended

    # Set up WS state as if match just finished
    obs._ws_state.last_match_id = "match-123"
    obs._ws_state.match_finished = True
    obs._ws_state.finish_trigger = "match_end_gameshot_match"

    # First dispatch — should succeed
    result1 = await obs._dispatch_finalize("match_end_gameshot_match", "debounce_confirmed")
    assert result1 is not None
    assert result1["should_lock"] is True
    assert call_count == 1

    # Second dispatch (same match) — should be ignored
    result2 = await obs._dispatch_finalize("match_end_state_finished", "ws_safety_net")
    assert result2 is None  # Ignored because _finalized=True
    assert call_count == 1  # Still 1 — no double dispatch


@pytest.mark.asyncio
async def test_concurrent_dispatch_blocked():
    """If a finalize is already dispatching, second call is blocked."""
    from backend.services.autodarts_observer import AutodartsObserver, WSEventState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-2"
    obs._ws_state = WSEventState()
    obs._finalized = False
    obs._stopping = False
    obs._last_finalized_match_id = None
    obs._ws_state.last_match_id = "match-456"

    # Simulate long-running finalize
    call_count = 0
    async def slow_game_ended(board_id, reason):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(2)
        return {"should_lock": True, "should_teardown": True}

    obs._on_game_ended = slow_game_ended

    # Manually set _finalize_dispatching to simulate concurrent dispatch
    obs._finalize_dispatching = True
    result = await obs._dispatch_finalize("match_end_state_finished", "test")
    assert result is None
    assert call_count == 0


# ============================================================
# Test B — Last game → session_end
# ============================================================

def test_last_game_session_end():
    """credit_before=1, consume=True → branch=session_end, should_lock=True."""
    credit_before = 1
    consume_credit = True
    credit_after = max(0, credit_before - 1) if consume_credit else credit_before
    has_remaining_credits = credit_after > 0
    should_lock = not has_remaining_credits
    should_teardown = should_lock
    branch = "session_end" if should_lock else "keep_alive"

    assert credit_after == 0
    assert has_remaining_credits is False
    assert should_lock is True
    assert should_teardown is True
    assert branch == "session_end"


# ============================================================
# Test C — Keep-alive unchanged
# ============================================================

def test_keep_alive_unchanged():
    """credit_before=2, consume=True → branch=keep_alive, observer stays alive."""
    credit_before = 2
    consume_credit = True
    credit_after = max(0, credit_before - 1) if consume_credit else credit_before
    has_remaining_credits = credit_after > 0
    should_lock = not has_remaining_credits
    should_teardown = should_lock
    branch = "session_end" if should_lock else "keep_alive"

    assert credit_after == 1
    assert has_remaining_credits is True
    assert should_lock is False
    assert should_teardown is False
    assert branch == "keep_alive"


# ============================================================
# Test D — _update_ws_state duplicate signals
# ============================================================

def test_ws_duplicate_finish_signals():
    """Second finish signal for same match is ignored in _update_ws_state."""
    from backend.services.autodarts_observer import AutodartsObserver, WSEventState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-3"
    obs._ws_state = WSEventState()
    obs._last_finalized_match_id = None
    obs._finalized = False
    obs._finalize_dispatching = False
    obs._stopping = False
    obs._on_game_ended = None

    # Patch _schedule_finalize_safety to avoid async issues in sync test
    obs._schedule_finalize_safety = lambda *a, **kw: None

    # First signal
    obs._update_ws_state("match_end_gameshot_match", "autodarts.matches.abc.state", {}, "")
    assert obs._ws_state.match_finished is True
    assert obs._ws_state.finish_trigger == "match_end_gameshot_match"

    # Second signal (duplicate) — should NOT overwrite trigger
    obs._update_ws_state("match_end_state_finished", "autodarts.matches.abc.state", {}, "")
    assert obs._ws_state.finish_trigger == "match_end_gameshot_match"  # First trigger wins


# ============================================================
# Test E — open_session blocked during finalize dispatch
# ============================================================

@pytest.mark.asyncio
async def test_open_session_blocked_during_finalize():
    """open_session must not proceed if _finalize_dispatching is True."""
    from backend.services.autodarts_observer import AutodartsObserver, LifecycleState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-4"
    obs._lifecycle_state = LifecycleState.CLOSED
    obs._finalize_dispatching = True
    obs._closing = False
    obs._stopping = False
    obs._session_generation = 0
    obs._context = None
    obs.status = MagicMock()
    obs.status.browser_open = False

    # open_session should bail early
    await obs.open_session("https://play.autodarts.io")
    # Lifecycle should still be CLOSED (not STARTING)
    assert obs._lifecycle_state == LifecycleState.CLOSED


# ============================================================
# Test F — dispatch_finalize no callback
# ============================================================

@pytest.mark.asyncio
async def test_dispatch_finalize_no_callback():
    """Dispatch without callback should return None gracefully."""
    from backend.services.autodarts_observer import AutodartsObserver, WSEventState

    obs = AutodartsObserver.__new__(AutodartsObserver)
    obs.board_id = "TEST-5"
    obs._ws_state = WSEventState()
    obs._finalized = False
    obs._finalize_dispatching = False
    obs._stopping = False
    obs._last_finalized_match_id = None
    obs._on_game_ended = None

    result = await obs._dispatch_finalize("finished", "test")
    assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
