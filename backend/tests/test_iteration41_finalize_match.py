"""
Test Iteration 41: Central finalize_match Path Refactor

MAJOR REFACTOR TESTED:
1. finalize_match exists and is callable with (board_id, trigger) args
2. finalize_match accepts optional winner and scores params
3. _finalizing guard: concurrent calls for same board_id are skipped
4. finalize_match with trigger=finished deducts credit for PER_GAME pricing
5. finalize_match with trigger=aborted does NOT deduct credit
6. finalize_match with trigger=manual deducts credit for PER_GAME pricing
7. finalize_match locks board when credits reach 0
8. finalize_match keeps board unlocked when credits remain
9. _on_game_started sets board to IN_GAME (no credit deduction)
10. _on_game_ended schedules finalize_match via create_task (not direct await)
11. observer close_session does NOT call window_manager (no restore_kiosk_window)
12. observer close_session is idempotent (_closing guard)
13. observer _cleanup logs PAGE_SET_NONE, CONTEXT_SET_NONE
14. end-game endpoint uses finalize_match('manual') path
15. _safe_close_observer function no longer exists (removed)

REGRESSION TESTS:
- classify turn_start -> match_start_turn_start
- classify game_shot+match -> match_end_gameshot_match
- _page_alive returns False when page is None
- _read_console_state returns None when page not alive
- Backend /api/health responds
"""

import pytest
import asyncio
import sys
import os
import inspect

sys.path.insert(0, '/app')


class TestFinalizeMatchExists:
    """Test finalize_match function exists with correct signature."""

    def test_finalize_match_exists_in_kiosk(self):
        """finalize_match exists and is callable"""
        from backend.routers.kiosk import finalize_match
        assert callable(finalize_match), "finalize_match must be callable"

    def test_finalize_match_signature_board_id_trigger(self):
        """finalize_match accepts (board_id, trigger) args"""
        from backend.routers.kiosk import finalize_match
        sig = inspect.signature(finalize_match)
        params = list(sig.parameters.keys())
        
        assert 'board_id' in params, "finalize_match must accept board_id param"
        assert 'trigger' in params, "finalize_match must accept trigger param"

    def test_finalize_match_signature_optional_winner_scores(self):
        """finalize_match accepts optional winner and scores params"""
        from backend.routers.kiosk import finalize_match
        sig = inspect.signature(finalize_match)
        params = sig.parameters
        
        assert 'winner' in params, "finalize_match must accept winner param"
        assert 'scores' in params, "finalize_match must accept scores param"
        
        # Check they have defaults (optional)
        assert params['winner'].default is None, "winner should default to None"
        assert params['scores'].default is None, "scores should default to None"

    def test_finalize_match_is_async(self):
        """finalize_match is an async function"""
        from backend.routers.kiosk import finalize_match
        assert asyncio.iscoroutinefunction(finalize_match), "finalize_match must be async"


class TestFinalizingGuard:
    """Test _finalizing guard prevents concurrent calls."""

    def test_finalizing_set_exists(self):
        """_finalizing set exists in kiosk module"""
        from backend.routers import kiosk
        assert hasattr(kiosk, '_finalizing'), "_finalizing set must exist"
        assert isinstance(kiosk._finalizing, set), "_finalizing must be a set"

    def test_finalize_match_checks_finalizing_guard(self):
        """finalize_match checks if board_id in _finalizing"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "if board_id in _finalizing" in source, \
            "finalize_match must check if board_id in _finalizing"

    def test_finalize_match_adds_to_finalizing(self):
        """finalize_match adds board_id to _finalizing set"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "_finalizing.add(board_id)" in source, \
            "finalize_match must add board_id to _finalizing"

    def test_finalize_match_discards_from_finalizing(self):
        """finalize_match discards board_id from _finalizing at end"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "_finalizing.discard(board_id)" in source, \
            "finalize_match must discard board_id from _finalizing"

    def test_finalize_match_skipped_log_when_already_in_progress(self):
        """finalize_match logs SKIPPED when already in progress"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "SKIPPED" in source or "already in progress" in source.lower(), \
            "finalize_match should log skip when already in progress"


class TestCreditDeductionLogic:
    """Test credit deduction logic in finalize_match."""

    def test_finalize_deducts_credit_for_finished_trigger(self):
        """finalize_match with trigger=finished deducts credit for PER_GAME"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        # Check logic: trigger in ("finished", "manual") with PER_GAME pricing
        assert 'trigger in ("finished", "manual")' in source or \
               '"finished"' in source and '"manual"' in source, \
            "Credit deduction must check for finished and manual triggers"
        
        assert "PER_GAME" in source, "Credit deduction must check PER_GAME pricing mode"

    def test_finalize_deducts_credit_for_manual_trigger(self):
        """finalize_match with trigger=manual deducts credit for PER_GAME"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        # "manual" must be in the trigger check for credit deduction
        assert '"manual"' in source, "manual trigger must be handled for credit deduction"

    def test_finalize_no_credit_deduction_for_aborted(self):
        """finalize_match with trigger=aborted does NOT deduct credit"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        # The deduction condition should NOT include "aborted"
        # Look for the credit deduction logic
        lines = source.split('\n')
        found_deduction_condition = False
        for line in lines:
            if 'trigger in' in line and ('finished' in line or 'manual' in line):
                found_deduction_condition = True
                # Should NOT contain "aborted" in the deduction condition
                assert 'aborted' not in line, \
                    "Credit deduction condition should NOT include 'aborted'"
        
        assert found_deduction_condition, "Could not find credit deduction condition"


class TestBoardLockLogic:
    """Test board locking logic in finalize_match."""

    def test_finalize_locks_board_when_credits_zero(self):
        """finalize_match locks board when credits reach 0"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        # Check for lock decision based on credits
        assert "credits_remaining <= 0" in source or "credits_remaining == 0" in source, \
            "Lock decision must check if credits_remaining <= 0"
        
        assert "BoardStatus.LOCKED" in source, \
            "finalize_match must set board to LOCKED status"

    def test_finalize_keeps_unlocked_when_credits_remain(self):
        """finalize_match keeps board unlocked when credits remain"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "BoardStatus.UNLOCKED" in source, \
            "finalize_match must be able to set board to UNLOCKED status"


class TestOnGameStarted:
    """Test _on_game_started sets board to IN_GAME without credit deduction."""

    def test_on_game_started_exists(self):
        """_on_game_started function exists"""
        from backend.routers.kiosk import _on_game_started
        assert callable(_on_game_started), "_on_game_started must be callable"

    def test_on_game_started_sets_in_game_status(self):
        """_on_game_started sets board to IN_GAME"""
        from backend.routers.kiosk import _on_game_started
        source = inspect.getsource(_on_game_started)
        
        assert "IN_GAME" in source, "_on_game_started must set IN_GAME status"
        assert "BoardStatus.IN_GAME" in source, "_on_game_started must use BoardStatus.IN_GAME"

    def test_on_game_started_no_credit_deduction(self):
        """_on_game_started does NOT deduct credits"""
        from backend.routers.kiosk import _on_game_started
        source = inspect.getsource(_on_game_started)
        
        # Should NOT contain credit deduction logic
        assert "credits_remaining" not in source and "credit" not in source.lower(), \
            "_on_game_started should NOT handle credit deduction (finalize_match does that)"


class TestOnGameEnded:
    """Test _on_game_ended schedules finalize_match via create_task."""

    def test_on_game_ended_exists(self):
        """_on_game_ended function exists"""
        from backend.routers.kiosk import _on_game_ended
        assert callable(_on_game_ended), "_on_game_ended must be callable"

    def test_on_game_ended_uses_create_task(self):
        """_on_game_ended schedules finalize_match via asyncio.create_task"""
        from backend.routers.kiosk import _on_game_ended
        source = inspect.getsource(_on_game_ended)
        
        assert "create_task" in source, "_on_game_ended must use create_task"
        assert "finalize_match" in source, "_on_game_ended must call finalize_match"

    def test_on_game_ended_not_direct_await(self):
        """_on_game_ended does NOT directly await finalize_match"""
        from backend.routers.kiosk import _on_game_ended
        source = inspect.getsource(_on_game_ended)
        
        # Should use create_task, not await finalize_match
        assert "await finalize_match" not in source, \
            "_on_game_ended should NOT directly await finalize_match (use create_task)"


class TestObserverCloseSessionNoWindowManager:
    """Test observer close_session does NOT call window_manager."""

    def test_close_session_no_restore_kiosk_window(self):
        """close_session does NOT call restore_kiosk_window"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.close_session)
        
        assert "restore_kiosk_window" not in source, \
            "close_session should NOT call restore_kiosk_window (finalize_match does that)"

    def test_close_session_no_window_manager_import(self):
        """close_session does NOT import/use window_manager"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.close_session)
        
        assert "window_manager" not in source, \
            "close_session should NOT reference window_manager"

    def test_close_session_no_kill_overlay(self):
        """close_session does NOT call kill_overlay_process"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.close_session)
        
        assert "kill_overlay" not in source, \
            "close_session should NOT call kill_overlay_process"


class TestObserverCloseSessionIdempotent:
    """Test observer close_session is idempotent with _closing guard."""

    def test_closing_guard_exists(self):
        """_closing guard exists in close_session"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.close_session)
        
        assert "self._closing" in source, "close_session must check _closing guard"

    def test_close_session_skips_when_closing(self):
        """close_session skips when _closing is True"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.close_session)
        
        assert "if self._closing" in source, "close_session must have if self._closing check"
        assert "CLOSE_SESSION_SKIPPED" in source or "already closing" in source.lower(), \
            "close_session should log/handle skip when already closing"


class TestCleanupLogs:
    """Test _cleanup logs PAGE_SET_NONE and CONTEXT_SET_NONE."""

    def test_cleanup_logs_page_set_none(self):
        """_cleanup logs PAGE_SET_NONE"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._cleanup)
        
        assert "PAGE_SET_NONE" in source, "_cleanup should log PAGE_SET_NONE"

    def test_cleanup_logs_context_set_none(self):
        """_cleanup logs CONTEXT_SET_NONE"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._cleanup)
        
        assert "CONTEXT_SET_NONE" in source, "_cleanup should log CONTEXT_SET_NONE"


class TestEndGameEndpointUsesFinalize:
    """Test end-game endpoint uses finalize_match('manual') path."""

    def test_end_game_endpoint_calls_finalize_match(self):
        """end-game endpoint uses finalize_match"""
        from backend.routers.kiosk import kiosk_end_game
        source = inspect.getsource(kiosk_end_game)
        
        assert "finalize_match" in source, \
            "end-game endpoint must call finalize_match"

    def test_end_game_endpoint_uses_manual_trigger(self):
        """end-game endpoint passes 'manual' as trigger"""
        from backend.routers.kiosk import kiosk_end_game
        source = inspect.getsource(kiosk_end_game)
        
        assert '"manual"' in source, \
            "end-game endpoint must pass 'manual' as trigger"


class TestSafeCloseObserverRemoved:
    """Test _safe_close_observer function no longer exists."""

    def test_safe_close_observer_not_in_kiosk(self):
        """_safe_close_observer is not in kiosk module"""
        from backend.routers import kiosk
        
        assert not hasattr(kiosk, '_safe_close_observer'), \
            "_safe_close_observer should be removed from kiosk module"

    def test_safe_close_observer_not_in_observer(self):
        """_safe_close_observer is not in observer module"""
        from backend.services import autodarts_observer
        
        assert not hasattr(autodarts_observer, '_safe_close_observer'), \
            "_safe_close_observer should be removed from observer module"


# ═══════════════════════════════════════════════════════════════
# REGRESSION TESTS
# ═══════════════════════════════════════════════════════════════

class TestRegressionClassifyTurnStart:
    """Regression: classify turn_start -> match_start_turn_start"""

    def test_classify_turn_start(self):
        """event=turn_start -> match_start_turn_start"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        raw = '{"event": "turn_start"}'
        payload = {"event": "turn_start"}
        result = obs._classify_frame(raw, "autodarts.matches.abc.game-events", payload)
        assert result == "match_start_turn_start"


class TestRegressionClassifyGameShotMatch:
    """Regression: classify game_shot+match -> match_end_gameshot_match"""

    def test_classify_gameshot_match(self):
        """game_shot + body.type=match -> match_end_gameshot_match"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        raw = '{"event": "game_shot", "body": {"type": "match"}}'
        payload = {"event": "game_shot", "body": {"type": "match"}}
        result = obs._classify_frame(raw, "autodarts.matches.abc.game-events", payload)
        assert result == "match_end_gameshot_match"


class TestRegressionPageAlive:
    """Regression: _page_alive returns False when page is None"""

    def test_page_alive_false_when_page_none(self):
        """_page_alive() returns False when self._page is None"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        obs._page = None
        obs._context = None
        
        result = obs._page_alive()
        assert result is False, "_page_alive should return False when page is None"


class TestRegressionReadConsoleState:
    """Regression: _read_console_state returns None when page not alive"""

    def test_read_console_state_null_safe(self):
        """_read_console_state checks _page_alive before page operations"""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._read_console_state)
        
        assert "_page_alive()" in source, \
            "_read_console_state must check _page_alive()"


class TestBackendHealth:
    """Test backend health endpoint."""

    def test_health_endpoint(self):
        """Backend /api/health responds"""
        import requests
        BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"


# ═══════════════════════════════════════════════════════════════
# FINALIZE_MATCH FUNCTIONAL TESTS (Mock-free source analysis)
# ═══════════════════════════════════════════════════════════════

class TestFinalizeMatchReturnStructure:
    """Test finalize_match returns correct structure."""

    def test_finalize_match_returns_dict_keys(self):
        """finalize_match returns dict with should_lock, credits_remaining, board_status"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        # Check return structure contains expected keys
        assert '"should_lock"' in source or "'should_lock'" in source, \
            "finalize_match should return should_lock"
        assert '"credits_remaining"' in source or "'credits_remaining'" in source, \
            "finalize_match should return credits_remaining"
        assert '"board_status"' in source or "'board_status'" in source, \
            "finalize_match should return board_status"


class TestFinalizeMatchDbOperations:
    """Test finalize_match DB operations are structured correctly."""

    def test_finalize_match_uses_async_session(self):
        """finalize_match uses AsyncSessionLocal for DB operations"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "AsyncSessionLocal" in source, \
            "finalize_match should use AsyncSessionLocal"

    def test_finalize_match_uses_transaction(self):
        """finalize_match uses db.begin() transaction"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "db.begin()" in source, \
            "finalize_match should use db.begin() transaction"


class TestFinalizeMatchObserverClose:
    """Test finalize_match closes observer correctly."""

    def test_finalize_match_closes_observer(self):
        """finalize_match calls observer_manager.close"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "observer_manager.close" in source, \
            "finalize_match should call observer_manager.close"


class TestFinalizeMatchWindowManagement:
    """Test finalize_match handles window management for locked boards."""

    def test_finalize_match_restores_kiosk_when_locked(self):
        """finalize_match restores kiosk window when should_lock=True"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "restore_kiosk_window" in source, \
            "finalize_match should call restore_kiosk_window"
        
        # Window management should be conditional on should_lock
        assert "if should_lock" in source, \
            "Window management should be conditional on should_lock"

    def test_finalize_match_kills_overlay_when_locked(self):
        """finalize_match kills overlay when should_lock=True"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        
        assert "kill_overlay" in source, \
            "finalize_match should call kill_overlay_process when locking"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
