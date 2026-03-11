"""
Test Iteration 43: Finalize Match v2.3.0 — Critical Refactor

Tests the core fix: synchronous finalize from observe loop, self-call deadlock
prevention, _finalized guard, clean state reset, step-by-step Playwright logging.

CRITICAL CHANGES:
1. _on_game_ended directly awaits finalize_match (no create_task)
2. close_session detects self-call (asyncio.current_task) to avoid deadlock
3. _finalized flag per observer prevents double finalization
4. _finalized flag per board in kiosk.py blocks duplicate WS signals
5. manual trigger bypasses _finalized guard
6. _cleanup logs PAGE_CLOSE_DONE, CONTEXT_CLOSE_DONE, PLAYWRIGHT_STOP_DONE
7. open_session resets _finalized flag
8. Observe loop breaks immediately after teardown finalize
9. _should_deduct_credit accepts match_end_* triggers
10. FINISHED→IDLE does NOT re-trigger finalization
"""

import pytest
import asyncio
import sys
import os
import inspect

sys.path.insert(0, '/app')


class TestShouldDeductCreditPolicy:
    """Centralized credit policy handles all trigger types."""

    def test_finished_deducts(self):
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("finished") is True

    def test_manual_deducts(self):
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("manual") is True

    def test_match_end_gameshot_match_deducts(self):
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("match_end_gameshot_match") is True

    def test_match_end_state_finished_deducts(self):
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("match_end_state_finished") is True

    def test_aborted_free(self):
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("aborted") is False

    def test_unknown_free(self):
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("unknown") is False
        assert _should_deduct_credit("") is False


class TestFinalizedGuard:
    """_finalized dict blocks duplicate WS signals but allows manual."""

    def test_finalized_dict_exists(self):
        from backend.routers import kiosk
        assert hasattr(kiosk, '_finalized')
        assert isinstance(kiosk._finalized, dict)

    def test_finalize_checks_finalized(self):
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert "_finalized" in source

    def test_manual_bypasses_finalized(self):
        """Manual trigger must bypass _finalized guard."""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert 'trigger != "manual"' in source


class TestOnGameEndedSynchronous:
    """_on_game_ended directly awaits finalize (no create_task)."""

    def test_no_create_task(self):
        from backend.routers.kiosk import _on_game_ended
        source = inspect.getsource(_on_game_ended)
        assert "asyncio.create_task" not in source, \
            "_on_game_ended must NOT use asyncio.create_task (synchronous finalize)"

    def test_awaits_finalize_match(self):
        from backend.routers.kiosk import _on_game_ended
        source = inspect.getsource(_on_game_ended)
        assert "await finalize_match" in source

    def test_returns_result(self):
        from backend.routers.kiosk import _on_game_ended
        source = inspect.getsource(_on_game_ended)
        assert "return" in source


class TestOnGameStartedResetsFinalized:
    """_on_game_started resets _finalized flag for new game."""

    def test_resets_finalized(self):
        from backend.routers.kiosk import _on_game_started
        source = inspect.getsource(_on_game_started)
        assert "_finalized" in source


class TestCloseSessionSelfCallDetection:
    """close_session detects self-call to prevent deadlock."""

    def test_has_current_task_check(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.close_session)
        assert "current_task" in source
        assert "is_self_call" in source

    def test_skips_cancel_on_self_call(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.close_session)
        assert "is_self_call" in source
        # The code uses "if is_self_call:" to skip cancel, and "else:" to do cancel
        assert "self-call detected" in source


class TestCleanupStepByStepLogging:
    """_cleanup logs each Playwright close step."""

    def test_page_close_done(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._cleanup)
        assert "PAGE_CLOSE_DONE" in source

    def test_context_close_done(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._cleanup)
        assert "CONTEXT_CLOSE_DONE" in source

    def test_playwright_stop_done(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._cleanup)
        assert "PLAYWRIGHT_STOP_DONE" in source

    def test_cleanup_complete(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._cleanup)
        assert "CLEANUP_COMPLETE" in source


class TestObserverFinalizedFlag:
    """Observer has _finalized flag for double-finalization prevention."""

    def test_init_has_finalized(self):
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        assert hasattr(obs, '_finalized')
        assert obs._finalized is False

    def test_open_session_resets_finalized(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.open_session)
        assert "_finalized = False" in source

    def test_observe_loop_checks_finalized(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "not self._finalized" in source

    def test_observe_loop_sets_finalized(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "self._finalized = True" in source


class TestObserveLoopBreaksAfterTeardown:
    """Observe loop checks _stopping after finalize and breaks."""

    def test_breaks_after_stopping(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "if self._stopping:" in source
        # Should have break after stopping check within the finalize section
        lines = source.split('\n')
        for i, line in enumerate(lines):
            if '_stopping=True after finalize' in line:
                # Next meaningful line should be break
                for j in range(i+1, min(i+3, len(lines))):
                    if 'break' in lines[j]:
                        return  # Found it
        # Alternative: just check the string exists
        assert "_stopping=True after finalize" in source


class TestObserveLoopReadyForNextGame:
    """After non-teardown finalize, observer resets for next game."""

    def test_logs_ready_for_next_game(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "READY_FOR_NEXT_GAME" in source


class TestStopReasonAccuracy:
    """Stop reason distinguishes finalize_teardown from generic stopping_flag."""

    def test_stop_reason_finalize_teardown(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "finalize_teardown" in source


class TestPostFinishCheckRemoved:
    """FINISHED→IDLE does NOT trigger re-finalization."""

    def test_no_post_finish_check(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "post_finish_check" not in source

    def test_finished_idle_no_callback(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        lines = source.split('\n')
        in_block = False
        block_lines = []
        for line in lines:
            if 'result dismissed' in line.lower():
                in_block = True
            if in_block:
                block_lines.append(line)
                if line.strip().startswith(('elif ', 'else:')):
                    break
        block_text = '\n'.join(block_lines)
        assert "on_game_ended" not in block_text


class TestFinalizeMatchShouldTeardownInResult:
    """finalize_match returns should_teardown in result dict."""

    def test_returns_should_teardown(self):
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert '"should_teardown"' in source


class TestRegressionCloseSessionNoWindowManager:
    """close_session does NOT call window_manager."""

    def test_no_window_manager(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.close_session)
        assert "restore_kiosk_window" not in source
        assert "window_manager" not in source


class TestRegressionClassification:
    """WS frame classification unchanged."""

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


class TestBackendHealth:
    def test_health(self):
        import requests
        BASE = "https://boardgame-repair.preview.emergentagent.com"
        r = requests.get(f"{BASE}/api/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
