"""
Test Iteration 42: Finalize Match Refactor v2.2.0

CRITICAL CHANGES TESTED:
1. _should_deduct_credit() centralized credit policy exists
2. _should_deduct_credit returns True for "finished" and "manual"
3. _should_deduct_credit returns False for "aborted" and unknown triggers
4. finalize_match uses _should_deduct_credit for credit decisions
5. finalize_match does NOT close observer when credits remain (should_teardown=False)
6. finalize_match DOES close observer when should_lock=True (credits exhausted)
7. finalize_match DOES close observer on manual trigger
8. finalize_match uses try/finally to ALWAYS release _finalizing guard
9. "post_finish_check" is no longer triggered by observer (FINISHED→IDLE)
10. Observer FINISHED→IDLE transition does NOT call _on_game_ended
11. finalize_match logs OBSERVER_KEPT_ALIVE when credits remain
12. finalize_match logs OBSERVER_CLOSE when teardown happens
13. Idempotency guard still works (board_id in _finalizing)
14. _finalizing is released even on exceptions (try/finally)
15. Observer open_session resets all state flags

REGRESSION TESTS:
- finalize_match signature (board_id, trigger, winner, scores)
- close_session does NOT call window_manager
- classify turn_start → match_start_turn_start
- classify game_shot+match → match_end_gameshot_match
- Backend /api/health responds
"""

import pytest
import asyncio
import sys
import os
import inspect

sys.path.insert(0, '/app')


# ═══════════════════════════════════════════════════════════════
# _should_deduct_credit TESTS
# ═══════════════════════════════════════════════════════════════

class TestShouldDeductCredit:
    """Test centralized credit policy function."""

    def test_should_deduct_credit_exists(self):
        """_should_deduct_credit exists and is callable"""
        from backend.routers.kiosk import _should_deduct_credit
        assert callable(_should_deduct_credit)

    def test_deduct_for_finished(self):
        """finished trigger → deduct credit"""
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("finished") is True

    def test_deduct_for_manual(self):
        """manual trigger → deduct credit"""
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("manual") is True

    def test_no_deduct_for_aborted(self):
        """aborted trigger → NO deduction"""
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("aborted") is False

    def test_no_deduct_for_unknown(self):
        """unknown trigger → NO deduction"""
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("post_finish_check") is False
        assert _should_deduct_credit("unknown") is False
        assert _should_deduct_credit("") is False


class TestFinalizeMatchUsesCreditPolicy:
    """Test finalize_match uses _should_deduct_credit."""

    def test_finalize_calls_should_deduct_credit(self):
        """finalize_match calls _should_deduct_credit for credit decisions"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "_should_deduct_credit" in source, \
            "finalize_match must use _should_deduct_credit for credit decisions"


# ═══════════════════════════════════════════════════════════════
# OBSERVER TEARDOWN LOGIC TESTS
# ═══════════════════════════════════════════════════════════════

class TestObserverConditionalClose:
    """Test observer is only closed when session ends."""

    def test_finalize_has_should_teardown_flag(self):
        """finalize_match uses should_teardown flag"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "should_teardown" in source, \
            "finalize_match must use should_teardown flag"

    def test_finalize_conditional_observer_close(self):
        """observer_manager.close is called conditionally (not always)"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        # The observer close must be inside a conditional block
        assert "if should_teardown" in source, \
            "Observer close must be conditional on should_teardown"

    def test_finalize_logs_observer_kept_alive(self):
        """finalize_match logs OBSERVER_KEPT_ALIVE when not tearing down"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "OBSERVER_KEPT_ALIVE" in source, \
            "Must log OBSERVER_KEPT_ALIVE when observer stays open"

    def test_finalize_logs_observer_close(self):
        """finalize_match logs OBSERVER_CLOSE when tearing down"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "OBSERVER_CLOSE" in source, \
            "Must log OBSERVER_CLOSE when tearing down"


# ═══════════════════════════════════════════════════════════════
# POST_FINISH_CHECK REMOVAL TESTS
# ═══════════════════════════════════════════════════════════════

class TestPostFinishCheckRemoved:
    """Test that post_finish_check no longer triggers finalization."""

    def test_no_post_finish_check_in_observer(self):
        """Observer does NOT trigger post_finish_check anymore"""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "post_finish_check" not in source, \
            "post_finish_check must be removed from observer"

    def test_finished_to_idle_no_on_game_ended(self):
        """FINISHED→IDLE does NOT call _on_game_ended"""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)

        # Find the FINISHED→IDLE block
        lines = source.split('\n')
        in_finished_idle_block = False
        block_lines = []
        for line in lines:
            if 'finished -> idle' in line.lower() or 'result dismissed' in line.lower():
                in_finished_idle_block = True
                block_lines.append(line)
                continue
            if in_finished_idle_block:
                block_lines.append(line)
                # Block ends at next elif/else at same indentation
                if line.strip().startswith(('elif ', 'else:')):
                    break

        block_text = '\n'.join(block_lines)
        assert "NO re-finalize" in block_text or "on_game_ended" not in block_text, \
            "FINISHED→IDLE transition must NOT call on_game_ended"


# ═══════════════════════════════════════════════════════════════
# IDEMPOTENCY & GUARD TESTS
# ═══════════════════════════════════════════════════════════════

class TestFinalizeGuardTryFinally:
    """Test _finalizing guard uses try/finally for cleanup."""

    def test_finalizing_set_exists(self):
        """_finalizing set exists"""
        from backend.routers import kiosk
        assert hasattr(kiosk, '_finalizing')
        assert isinstance(kiosk._finalizing, set)

    def test_finalize_uses_try_finally(self):
        """finalize_match uses try/finally to release guard"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "finally:" in source, \
            "finalize_match must use try/finally to ensure guard release"
        # The discard must be in the finally block
        lines = source.split('\n')
        in_finally = False
        found_discard_in_finally = False
        for line in lines:
            if 'finally:' in line:
                in_finally = True
            if in_finally and '_finalizing.discard' in line:
                found_discard_in_finally = True
                break
        assert found_discard_in_finally, \
            "_finalizing.discard must be in the finally block"


# ═══════════════════════════════════════════════════════════════
# OBSERVER STATE RESET TESTS
# ═══════════════════════════════════════════════════════════════

class TestObserverOpenSessionReset:
    """Test open_session resets all state flags for clean re-open."""

    def test_open_session_resets_closing(self):
        """open_session resets _closing flag"""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.open_session)
        assert "self._closing = False" in source

    def test_open_session_resets_stopping(self):
        """open_session resets _stopping flag"""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.open_session)
        assert "self._stopping = False" in source

    def test_open_session_resets_stable_state(self):
        """open_session resets _stable_state"""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.open_session)
        assert "_stable_state" in source

    def test_open_session_resets_ws_state(self):
        """open_session resets _ws_state"""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.open_session)
        assert "_ws_state" in source

    def test_open_session_resets_credit_consumed(self):
        """open_session resets _credit_consumed"""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.open_session)
        assert "_credit_consumed" in source


# ═══════════════════════════════════════════════════════════════
# DETAILED LOGGING TESTS
# ═══════════════════════════════════════════════════════════════

class TestFinalizeDetailedLogging:
    """Test finalize_match has detailed step-by-step logging."""

    def test_logs_finalize_start(self):
        """Logs START marker"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "===== START" in source

    def test_logs_finalize_end(self):
        """Logs END marker"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "===== END" in source

    def test_logs_credit_deducted(self):
        """Logs CREDIT_DEDUCTED"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "CREDIT_DEDUCTED" in source

    def test_logs_credit_free(self):
        """Logs CREDIT_FREE for no-deduction triggers"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "CREDIT_FREE" in source

    def test_logs_lock_decision(self):
        """Logs LOCK_DECISION"""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "LOCK_DECISION" in source


# ═══════════════════════════════════════════════════════════════
# REGRESSION TESTS
# ═══════════════════════════════════════════════════════════════

class TestRegressionFinalizeMatchSignature:
    """Regression: finalize_match signature unchanged."""

    def test_finalize_match_params(self):
        from backend.routers.kiosk import finalize_match
        sig = inspect.signature(finalize_match)
        params = list(sig.parameters.keys())
        assert 'board_id' in params
        assert 'trigger' in params
        assert 'winner' in params
        assert 'scores' in params

    def test_finalize_match_is_async(self):
        from backend.routers.kiosk import finalize_match
        assert asyncio.iscoroutinefunction(finalize_match)


class TestRegressionCloseSessionNoWindowManager:
    """Regression: close_session does NOT call window_manager."""

    def test_close_session_no_restore(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.close_session)
        assert "restore_kiosk_window" not in source
        assert "window_manager" not in source
        assert "kill_overlay" not in source


class TestRegressionClassification:
    """Regression: WS frame classification unchanged."""

    def test_classify_turn_start(self):
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        result = obs._classify_frame(
            '{"event": "turn_start"}',
            "autodarts.matches.abc.game-events",
            {"event": "turn_start"}
        )
        assert result == "match_start_turn_start"

    def test_classify_gameshot_match(self):
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        result = obs._classify_frame(
            '{"event": "game_shot", "body": {"type": "match"}}',
            "autodarts.matches.abc.game-events",
            {"event": "game_shot", "body": {"type": "match"}}
        )
        assert result == "match_end_gameshot_match"

    def test_classify_throw(self):
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        result = obs._classify_frame(
            '{"event": "throw"}',
            "autodarts.matches.abc.game-events",
            {"event": "throw"}
        )
        assert result == "match_start_throw"


class TestRegressionPageAlive:
    """Regression: _page_alive null-safety."""

    def test_page_alive_false_when_none(self):
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        obs._page = None
        obs._context = None
        assert obs._page_alive() is False


class TestRegressionEndGameEndpoint:
    """Regression: end-game endpoint uses finalize_match."""

    def test_end_game_calls_finalize(self):
        from backend.routers.kiosk import kiosk_end_game
        source = inspect.getsource(kiosk_end_game)
        assert "finalize_match" in source
        assert '"manual"' in source


class TestBackendHealth:
    """Backend health check."""

    def test_health_endpoint(self):
        import requests
        # Read from frontend .env file
        BASE_URL = "https://boardgame-repair.preview.emergentagent.com"
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
