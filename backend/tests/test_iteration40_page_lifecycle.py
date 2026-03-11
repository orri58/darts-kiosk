"""
Test Iteration 40: Observer Page/Context Lifecycle After Match Finish/Reset

FIXES TESTED:
1. _page_alive() null-safe helper: returns False when self._page or self._context is None
2. close_session() idempotent with _closing guard: second call is skipped
3. _closing flag is reset in open_session
4. _cleanup() sets self._page = None, self._context = None, self._playwright = None
5. _read_console_state returns None when page not alive
6. _detect_state_dom returns UNKNOWN when page not alive
7. Observe loop stops cleanly with stop_reason when page becomes None
8. close_session logs CLOSE_SESSION_START and CLOSE_SESSION_DONE
9. _cleanup logs PAGE_SET_NONE and CONTEXT_SET_NONE

Also includes regression tests from iteration 39 for state machine.
"""

import pytest
import asyncio
import sys
import os

sys.path.insert(0, '/app')

from backend.services.autodarts_observer import (
    AutodartsObserver, ObserverState, WSEventState
)


class TestPageAliveNullSafe:
    """Test _page_alive() returns False when page or context is None."""

    def test_page_alive_returns_false_when_page_none(self):
        """_page_alive() returns False when self._page is None"""
        obs = AutodartsObserver("TEST")
        obs._page = None
        obs._context = object()  # non-None context
        
        result = obs._page_alive()
        assert result is False, "_page_alive should return False when self._page is None"

    def test_page_alive_returns_false_when_context_none(self):
        """_page_alive() returns False when self._context is None"""
        obs = AutodartsObserver("TEST")
        obs._page = object()  # non-None page
        obs._context = None
        
        result = obs._page_alive()
        assert result is False, "_page_alive should return False when self._context is None"

    def test_page_alive_returns_false_when_both_none(self):
        """_page_alive() returns False when both page and context are None"""
        obs = AutodartsObserver("TEST")
        obs._page = None
        obs._context = None
        
        result = obs._page_alive()
        assert result is False, "_page_alive should return False when both are None"

    def test_page_alive_method_exists(self):
        """_page_alive method exists on AutodartsObserver"""
        obs = AutodartsObserver("TEST")
        assert hasattr(obs, '_page_alive'), "_page_alive method must exist"
        assert callable(obs._page_alive), "_page_alive must be callable"


class TestCloseSessionIdempotent:
    """Test close_session is idempotent with _closing guard."""

    def test_closing_flag_initial_false(self):
        """_closing flag is initialized to False"""
        obs = AutodartsObserver("TEST")
        assert obs._closing is False, "_closing should be False initially"

    def test_closing_guard_exists_in_close_session(self):
        """close_session checks _closing guard before proceeding"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.close_session)
        
        # Must check self._closing at start
        assert "self._closing" in source, "close_session must reference self._closing"
        assert "if self._closing" in source, "close_session must have if self._closing guard"

    def test_close_session_skips_when_already_closing(self):
        """Second call to close_session is skipped when _closing=True"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.close_session)
        
        # Should have early return or skip logic
        assert "CLOSE_SESSION_SKIPPED" in source or "already closing" in source.lower(), \
            "close_session should log skip when already closing"

    def test_close_session_logs_start_and_done(self):
        """close_session logs CLOSE_SESSION_START and CLOSE_SESSION_DONE"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.close_session)
        
        assert "CLOSE_SESSION_START" in source, "close_session should log CLOSE_SESSION_START"
        assert "CLOSE_SESSION_DONE" in source, "close_session should log CLOSE_SESSION_DONE"


class TestClosingFlagResetInOpenSession:
    """Test _closing flag is reset in open_session."""

    def test_closing_reset_in_open_session(self):
        """_closing flag is reset to False in open_session"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.open_session)
        
        # Must have self._closing = False somewhere in open_session
        assert "self._closing = False" in source, "open_session must reset self._closing = False"


class TestCleanupSetsNone:
    """Test _cleanup() sets page, context, playwright to None."""

    def test_cleanup_sets_page_none(self):
        """_cleanup sets self._page = None"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._cleanup)
        
        assert "self._page = None" in source, "_cleanup must set self._page = None"

    def test_cleanup_sets_context_none(self):
        """_cleanup sets self._context = None"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._cleanup)
        
        assert "self._context = None" in source, "_cleanup must set self._context = None"

    def test_cleanup_sets_playwright_none(self):
        """_cleanup sets self._playwright = None"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._cleanup)
        
        assert "self._playwright = None" in source, "_cleanup must set self._playwright = None"

    def test_cleanup_logs_page_set_none(self):
        """_cleanup logs PAGE_SET_NONE"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._cleanup)
        
        assert "PAGE_SET_NONE" in source, "_cleanup should log PAGE_SET_NONE"

    def test_cleanup_logs_context_set_none(self):
        """_cleanup logs CONTEXT_SET_NONE"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._cleanup)
        
        assert "CONTEXT_SET_NONE" in source, "_cleanup should log CONTEXT_SET_NONE"


class TestReadConsoleStateNullSafe:
    """Test _read_console_state returns None when page not alive."""

    def test_read_console_state_checks_page_alive(self):
        """_read_console_state checks _page_alive() before page operations"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._read_console_state)
        
        # Must check _page_alive or self._page before evaluate
        assert "_page_alive" in source or "self._page" in source, \
            "_read_console_state must check page status"

    def test_read_console_state_returns_none_when_page_not_alive(self):
        """_read_console_state returns None when page is not alive"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._read_console_state)
        
        # Should have early return None when not _page_alive()
        assert "return None" in source, "_read_console_state should return None for null page"
        # Check it's tied to page_alive check
        assert "_page_alive()" in source, "_read_console_state should use _page_alive()"


class TestDetectStateDomNullSafe:
    """Test _detect_state_dom returns UNKNOWN when page not alive."""

    def test_detect_state_dom_checks_page_alive(self):
        """_detect_state_dom checks _page_alive() before page operations"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._detect_state_dom)
        
        assert "_page_alive" in source, "_detect_state_dom must check _page_alive()"

    def test_detect_state_dom_returns_unknown_when_page_not_alive(self):
        """_detect_state_dom returns UNKNOWN when page is not alive"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._detect_state_dom)
        
        # Should return ObserverState.UNKNOWN when not _page_alive()
        assert "UNKNOWN" in source, "_detect_state_dom should return UNKNOWN for null page"


class TestObserveLoopNullSafe:
    """Test observe loop stops cleanly with stop_reason when page becomes None."""

    def test_observe_loop_checks_page_alive(self):
        """Observe loop checks _page_alive() in each iteration"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._observe_loop)
        
        assert "_page_alive()" in source, "observe loop must check _page_alive()"

    def test_observe_loop_has_stop_reason(self):
        """Observe loop uses stop_reason variable"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._observe_loop)
        
        assert "stop_reason" in source, "observe loop must use stop_reason variable"

    def test_observe_loop_logs_stop_reason(self):
        """Observe loop logs OBSERVE_LOOP_STOP_REASON on exit"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._observe_loop)
        
        assert "OBSERVE_LOOP_STOP_REASON" in source, "observe loop must log OBSERVE_LOOP_STOP_REASON"

    def test_observe_loop_page_not_alive_stop_reason(self):
        """Observe loop sets stop_reason='page_not_alive' when page becomes None"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs._observe_loop)
        
        assert "page_not_alive" in source, "observe loop should set stop_reason='page_not_alive'"


class TestChromeArgsFullscreen:
    """Test Chrome launch arguments contain --start-fullscreen."""

    def test_chrome_args_has_start_fullscreen(self):
        """Chrome args contain --start-fullscreen"""
        import inspect
        obs = AutodartsObserver("TEST")
        source = inspect.getsource(obs.open_session)
        
        assert "--start-fullscreen" in source, "Chrome args should contain --start-fullscreen"


# ═══════════════════════════════════════════════════════════════
# REGRESSION TESTS - State Machine (from iteration 39)
# ═══════════════════════════════════════════════════════════════

class TestRegressionClassifyTurnStart:
    """Regression: classify turn_start -> match_start_turn_start"""

    def test_classify_turn_start(self):
        """event=turn_start -> match_start_turn_start"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "turn_start"}'
        payload = {"event": "turn_start"}
        result = obs._classify_frame(raw, "autodarts.matches.abc.game-events", payload)
        assert result == "match_start_turn_start"


class TestRegressionClassifyThrow:
    """Regression: classify throw -> match_start_throw"""

    def test_classify_throw(self):
        """event=throw -> match_start_throw"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "throw"}'
        payload = {"event": "throw"}
        result = obs._classify_frame(raw, "autodarts.matches.abc.game-events", payload)
        assert result == "match_start_throw"


class TestRegressionClassifyGameShotMatch:
    """Regression: classify game_shot+match -> match_end_gameshot_match"""

    def test_classify_gameshot_match(self):
        """game_shot + body.type=match -> match_end_gameshot_match"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "game_shot", "body": {"type": "match"}}'
        payload = {"event": "game_shot", "body": {"type": "match"}}
        result = obs._classify_frame(raw, "autodarts.matches.abc.game-events", payload)
        assert result == "match_end_gameshot_match"


class TestRegressionClassifyFinishedTrue:
    """Regression: classify finished=true -> match_end_state_finished"""

    def test_classify_finished_true(self):
        """finished=true -> match_end_state_finished"""
        obs = AutodartsObserver("TEST")
        raw = '{"finished": true}'
        payload = {"finished": True}
        result = obs._classify_frame(raw, "autodarts.matches.abc.state", payload)
        assert result == "match_end_state_finished"


class TestRegressionClassifyDelete:
    """Regression: classify delete -> match_reset_delete"""

    def test_classify_delete(self):
        """event=delete -> match_reset_delete"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "delete"}'
        payload = {"event": "delete"}
        result = obs._classify_frame(raw, "autodarts.matches.abc.state", payload)
        assert result == "match_reset_delete"


class TestRegressionStateMachineFlow:
    """Regression: state machine start->end->reset flow"""

    def test_start_end_reset_flow(self):
        """State machine: turn_start (START) -> gameshot_match (END) -> delete (RESET)"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        
        # Initial state
        assert obs._ws_state.match_active is False
        assert obs._ws_state.match_finished is False
        
        # START: turn_start
        obs._update_ws_state("match_start_turn_start", "autodarts.matches.abc.game-events", {}, "")
        assert obs._ws_state.match_active is True
        assert obs._ws_state.match_finished is False
        
        # END: gameshot_match
        obs._update_ws_state("match_end_gameshot_match", "autodarts.matches.abc.game-events", {}, "")
        assert obs._ws_state.match_active is False
        assert obs._ws_state.match_finished is True
        
        # RESET: delete
        obs._update_ws_state("match_reset_delete", "autodarts.matches.abc.state", {}, "")
        assert obs._ws_state.match_active is False
        assert obs._ws_state.match_finished is False


class TestRegressionReadWSEventState:
    """Regression: _read_ws_event_state returns FINISHED/IN_GAME/None correctly"""

    def test_read_ws_returns_finished(self):
        """match_finished=True -> FINISHED"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        obs._ws_state.match_finished = True
        result = obs._read_ws_event_state()
        assert result == ObserverState.FINISHED

    def test_read_ws_returns_in_game(self):
        """match_active=True -> IN_GAME"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        obs._ws_state.match_active = True
        result = obs._read_ws_event_state()
        assert result == ObserverState.IN_GAME

    def test_read_ws_returns_none(self):
        """neither -> None"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        result = obs._read_ws_event_state()
        assert result is None


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


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
