"""
Test Iteration 38 - Gotcha Mode Match Teardown & Match-Active Detection

This iteration overhauls the observer based on real Windows board PC WS diagnostics.
Real Autodarts match flow (Gotcha mode) ends via delete/not-found events, not classic 
matchshot/matchWinner. Also match_active was never set to true because the observer 
only recognized explicit 'state: active' messages.

Five fixes applied:
1. match_active detection from throw/turn/score data
2. match teardown via delete/not-found events
3+4. credit deduction + lock follows from correct state tracking
5. --start-fullscreen for observer Chrome (instead of --start-maximized)

Test coverage:
  - _classify_frame: event=delete on autodarts.matches channel -> match_deleted
  - _classify_frame: event=delete on autodarts.boards.*.matches channel -> board_match_deleted
  - _classify_frame: 'match not found' in raw -> match_not_found
  - _classify_frame: matchshot still -> match_finished_matchshot (regression)
  - _classify_frame: gameshot still -> round_transition_gameshot (regression)
  - _classify_frame: state active/running -> match_started (regression)
  - _extract_match_id: extracts UUID from autodarts.matches.{uuid}.state channel
  - _update_ws_state: turn_transition sets match_active=True when not already active
  - _update_ws_state: game_event with throwNumber/turnScore sets match_active=True
  - _update_ws_state: match_deleted + match was active -> match_finished=True
  - _update_ws_state: match_deleted + NO active match -> ignored (match_finished stays False)
  - _update_ws_state: board_match_deleted + active match -> match_finished=True
  - _update_ws_state: match_not_found + active match -> match_finished=True
  - _update_ws_state: match_started resets match_active/finished/winner correctly
  - WSEventState.reset() clears last_match_id too
  - Chrome args contain --start-fullscreen (not --start-maximized or --kiosk)
  - Chrome args contain --disable-session-crashed-bubble
  - Observer still creates fresh page via new_page()
  - Observer still has page close/crash/context close handlers
  - Observer still has browser health check in observe loop
  - Backend /api/health responds
"""
import pytest
import os
import sys
import inspect
import tempfile
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import requests

# Add backend to path
sys.path.insert(0, '/app')

from backend.services.autodarts_observer import (
    AutodartsObserver,
    ObserverState,
    WSEventState,
    CHROME_PROFILE_DIR,
)

# Load BASE_URL from frontend/.env
def _get_base_url():
    env_file = '/app/frontend/.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip().rstrip('/')
    return os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

BASE_URL = _get_base_url()


# ═══════════════════════════════════════════════════════════════
# _classify_frame TESTS - New classifications for Gotcha mode
# ═══════════════════════════════════════════════════════════════

class TestClassifyFrameDeleteEvents:
    """Tests for _classify_frame: delete events on match channels."""

    def test_event_delete_on_matches_channel_returns_match_deleted(self):
        """Verify event=delete on autodarts.matches.{uuid}.* channel -> match_deleted."""
        observer = AutodartsObserver("TEST-BOARD")
        
        # Test with event=delete in payload
        payload = {'event': 'delete'}
        channel = 'autodarts.matches.abc-123-def.state'
        raw = '{"event":"delete","channel":"autodarts.matches.abc-123-def.state"}'
        
        result = observer._classify_frame(raw, channel, payload)
        
        assert result == 'match_deleted', \
            f"event=delete on autodarts.matches channel should return 'match_deleted', got: {result}"
        print(f"PASS: event=delete on autodarts.matches channel -> {result}")

    def test_event_delete_in_nested_data_returns_match_deleted(self):
        """Verify event=delete in payload.data.event also returns match_deleted."""
        observer = AutodartsObserver("TEST-BOARD")
        
        # Test with event=delete in nested data
        payload = {'data': {'event': 'delete'}}
        channel = 'autodarts.matches.xyz-456.state'
        raw = '{"data":{"event":"delete"}}'
        
        result = observer._classify_frame(raw, channel, payload)
        
        assert result == 'match_deleted', \
            f"event=delete in data.event should return 'match_deleted', got: {result}"
        print(f"PASS: event=delete in nested data -> {result}")

    def test_event_delete_on_boards_matches_channel_returns_board_match_deleted(self):
        """Verify event=delete on autodarts.boards.*.matches channel -> board_match_deleted."""
        observer = AutodartsObserver("TEST-BOARD")
        
        # Test with event=delete on boards.*.matches channel
        payload = {'event': 'delete'}
        channel = 'autodarts.boards.BOARD-1.matches'
        raw = '{"event":"delete","channel":"autodarts.boards.BOARD-1.matches"}'
        
        result = observer._classify_frame(raw, channel, payload)
        
        assert result == 'board_match_deleted', \
            f"event=delete on autodarts.boards.*.matches should return 'board_match_deleted', got: {result}"
        print(f"PASS: event=delete on autodarts.boards.*.matches channel -> {result}")


class TestClassifyFrameMatchNotFound:
    """Tests for _classify_frame: 'match not found' error detection."""

    def test_match_not_found_in_raw_returns_match_not_found(self):
        """Verify 'match not found' in raw message -> match_not_found."""
        observer = AutodartsObserver("TEST-BOARD")
        
        raw = '{"error":"match not found","code":404}'
        channel = 'autodarts.matches.unknown-id.state'
        payload = {'error': 'match not found', 'code': 404}
        
        result = observer._classify_frame(raw, channel, payload)
        
        assert result == 'match_not_found', \
            f"'match not found' in raw should return 'match_not_found', got: {result}"
        print(f"PASS: 'match not found' in raw -> {result}")

    def test_match_not_found_case_insensitive(self):
        """Verify 'Match Not Found' (mixed case) also works."""
        observer = AutodartsObserver("TEST-BOARD")
        
        raw = '{"message":"Match Not Found"}'
        channel = 'unknown'
        payload = {'message': 'Match Not Found'}
        
        result = observer._classify_frame(raw, channel, payload)
        
        assert result == 'match_not_found', \
            f"Mixed case 'Match Not Found' should return 'match_not_found', got: {result}"
        print(f"PASS: 'Match Not Found' (mixed case) -> {result}")


class TestClassifyFrameRegressions:
    """Regression tests: matchshot, gameshot, state active/running still work."""

    def test_matchshot_still_returns_match_finished_matchshot(self):
        """Verify matchshot is still classified as match_finished_matchshot."""
        observer = AutodartsObserver("TEST-BOARD")
        
        result = observer._classify_frame(
            '{"type":"matchshot"}',
            'autodarts.matches.123.game-events',
            {'type': 'matchshot'}
        )
        
        assert result == 'match_finished_matchshot', \
            f"matchshot should be match_finished_matchshot, got: {result}"
        print(f"PASS: matchshot -> {result} (regression)")

    def test_gameshot_still_returns_round_transition_gameshot(self):
        """Verify gameshot is still classified as round_transition_gameshot (NOT match_finished)."""
        observer = AutodartsObserver("TEST-BOARD")
        
        result = observer._classify_frame(
            '{"type":"gameshot","score":180}',
            'autodarts.matches.123.game-events',
            {'type': 'gameshot'}
        )
        
        assert result == 'round_transition_gameshot', \
            f"gameshot should be round_transition_gameshot, got: {result}"
        assert 'match_finished' not in result, \
            f"gameshot should NOT be match_finished: {result}"
        print(f"PASS: gameshot -> {result} (regression)")

    def test_state_active_returns_match_started(self):
        """Verify state: active returns match_started."""
        observer = AutodartsObserver("TEST-BOARD")
        
        payload = {'state': 'active'}
        result = observer._classify_frame(
            '{"state":"active"}',
            'autodarts.matches.123.state',
            payload
        )
        
        assert result == 'match_started', \
            f"state: active should return match_started, got: {result}"
        print(f"PASS: state: active -> {result} (regression)")

    def test_state_running_returns_match_started(self):
        """Verify state: running returns match_started."""
        observer = AutodartsObserver("TEST-BOARD")
        
        payload = {'state': 'running'}
        result = observer._classify_frame(
            '{"state":"running"}',
            'autodarts.matches.123.state',
            payload
        )
        
        assert result == 'match_started', \
            f"state: running should return match_started, got: {result}"
        print(f"PASS: state: running -> {result} (regression)")


# ═══════════════════════════════════════════════════════════════
# _extract_match_id TESTS
# ═══════════════════════════════════════════════════════════════

class TestExtractMatchId:
    """Tests for _extract_match_id: UUID extraction from channel names."""

    def test_extracts_uuid_from_matches_state_channel(self):
        """Verify UUID extraction from autodarts.matches.{uuid}.state channel."""
        observer = AutodartsObserver("TEST-BOARD")
        
        channel = 'autodarts.matches.abc12345-6789-0123-4567-890abcdef123.state'
        result = observer._extract_match_id(channel)
        
        assert result == 'abc12345-6789-0123-4567-890abcdef123', \
            f"Should extract UUID from matches channel, got: {result}"
        print(f"PASS: _extract_match_id extracts UUID -> {result}")

    def test_extracts_uuid_from_matches_game_events_channel(self):
        """Verify UUID extraction from autodarts.matches.{uuid}.game-events channel."""
        observer = AutodartsObserver("TEST-BOARD")
        
        channel = 'autodarts.matches.deadbeef-cafe-babe-1234-567890abcdef.game-events'
        result = observer._extract_match_id(channel)
        
        assert result == 'deadbeef-cafe-babe-1234-567890abcdef', \
            f"Should extract UUID from game-events channel, got: {result}"
        print(f"PASS: _extract_match_id extracts UUID from game-events channel -> {result}")

    def test_returns_none_for_non_match_channel(self):
        """Verify returns None for channels without match UUID."""
        observer = AutodartsObserver("TEST-BOARD")
        
        channel = 'autodarts.boards.BOARD-1.state'
        result = observer._extract_match_id(channel)
        
        assert result is None, \
            f"Should return None for non-match channel, got: {result}"
        print(f"PASS: _extract_match_id returns None for non-match channel")


# ═══════════════════════════════════════════════════════════════
# _update_ws_state TESTS - Match-active detection
# ═══════════════════════════════════════════════════════════════

class TestUpdateWsStateMatchActive:
    """Tests for _update_ws_state: match_active detection from turn/throw data."""

    def test_turn_transition_sets_match_active(self):
        """Verify turn_transition sets match_active=True when not already active."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        
        assert observer._ws_state.match_active is False, "Initial match_active should be False"
        
        # Simulate turn_transition interpretation
        observer._update_ws_state(
            'turn_transition',
            'autodarts.matches.123.state',
            {'turn': 1, 'player': 'A'},
            '{"turn":1,"player":"A"}'
        )
        
        assert observer._ws_state.match_active is True, \
            "turn_transition should set match_active=True"
        print("PASS: turn_transition sets match_active=True when not already active")

    def test_game_event_with_throw_number_sets_match_active(self):
        """Verify game_event with throwNumber sets match_active=True."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        
        payload = {'throwNumber': 1, 'score': 20}
        observer._update_ws_state(
            'game_event',
            'autodarts.matches.123.game-events',
            payload,
            '{"throwNumber":1,"score":20}'
        )
        
        assert observer._ws_state.match_active is True, \
            "game_event with throwNumber should set match_active=True"
        print("PASS: game_event with throwNumber sets match_active=True")

    def test_game_event_with_turn_score_sets_match_active(self):
        """Verify game_event with turnScore sets match_active=True."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        
        payload = {'turnScore': 60}
        observer._update_ws_state(
            'game_event',
            'autodarts.matches.123.game-events',
            payload,
            '{"turnScore":60}'
        )
        
        assert observer._ws_state.match_active is True, \
            "game_event with turnScore should set match_active=True"
        print("PASS: game_event with turnScore sets match_active=True")

    def test_game_event_with_game_scores_sets_match_active(self):
        """Verify game_event with gameScores sets match_active=True."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        
        payload = {'gameScores': {'A': 501, 'B': 480}}
        observer._update_ws_state(
            'game_event',
            'autodarts.matches.123.game-events',
            payload,
            '{"gameScores":{"A":501,"B":480}}'
        )
        
        assert observer._ws_state.match_active is True, \
            "game_event with gameScores should set match_active=True"
        print("PASS: game_event with gameScores sets match_active=True")

    def test_game_event_with_nested_throw_data_sets_match_active(self):
        """Verify game_event with throwNumber in data.* sets match_active=True."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        
        payload = {'data': {'throwNumber': 2, 'turnScore': 40}}
        observer._update_ws_state(
            'game_event',
            'autodarts.matches.123.game-events',
            payload,
            '{"data":{"throwNumber":2,"turnScore":40}}'
        )
        
        assert observer._ws_state.match_active is True, \
            "game_event with nested throwNumber should set match_active=True"
        print("PASS: game_event with nested throwNumber/turnScore sets match_active=True")


# ═══════════════════════════════════════════════════════════════
# _update_ws_state TESTS - Match teardown via delete/not-found
# ═══════════════════════════════════════════════════════════════

class TestUpdateWsStateMatchTeardown:
    """Tests for _update_ws_state: match_deleted/not-found triggers match_finished."""

    def test_match_deleted_with_active_match_sets_match_finished(self):
        """Verify match_deleted when match was active -> match_finished=True."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        observer._ws_state.match_active = True
        observer._ws_state.last_match_id = 'test-match-123'
        
        observer._update_ws_state(
            'match_deleted',
            'autodarts.matches.test-match-123.state',
            {'event': 'delete'},
            '{"event":"delete"}'
        )
        
        assert observer._ws_state.match_finished is True, \
            "match_deleted with active match should set match_finished=True"
        assert observer._ws_state.winner_detected is True, \
            "match_deleted with active match should set winner_detected=True"
        print("PASS: match_deleted + match was active -> match_finished=True")

    def test_match_deleted_without_active_match_ignored(self):
        """Verify match_deleted when NO active match -> ignored (match_finished stays False)."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        observer._ws_state.match_active = False
        observer._ws_state.last_match_id = None
        
        observer._update_ws_state(
            'match_deleted',
            'autodarts.matches.unknown.state',
            {'event': 'delete'},
            '{"event":"delete"}'
        )
        
        assert observer._ws_state.match_finished is False, \
            "match_deleted without active match should NOT set match_finished=True"
        print("PASS: match_deleted + NO active match -> ignored (match_finished stays False)")

    def test_board_match_deleted_with_active_match_sets_match_finished(self):
        """Verify board_match_deleted when match was active -> match_finished=True."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        observer._ws_state.match_active = True
        observer._ws_state.last_match_id = 'board-match-456'
        
        observer._update_ws_state(
            'board_match_deleted',
            'autodarts.boards.BOARD-1.matches',
            {'event': 'delete'},
            '{"event":"delete"}'
        )
        
        assert observer._ws_state.match_finished is True, \
            "board_match_deleted with active match should set match_finished=True"
        print("PASS: board_match_deleted + active match -> match_finished=True")

    def test_match_not_found_with_active_match_sets_match_finished(self):
        """Verify match_not_found when match was active -> match_finished=True."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        observer._ws_state.match_active = True
        observer._ws_state.last_match_id = 'not-found-789'
        
        observer._update_ws_state(
            'match_not_found',
            'autodarts.matches.not-found-789.state',
            {'error': 'match not found'},
            '{"error":"match not found"}'
        )
        
        assert observer._ws_state.match_finished is True, \
            "match_not_found with active match should set match_finished=True"
        print("PASS: match_not_found + active match -> match_finished=True")


class TestUpdateWsStateMatchStarted:
    """Tests for _update_ws_state: match_started resets state correctly."""

    def test_match_started_resets_state(self):
        """Verify match_started resets match_active/finished/winner correctly."""
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state = WSEventState()
        
        # Set some prior state
        observer._ws_state.match_finished = True
        observer._ws_state.winner_detected = True
        observer._ws_state.finish_trigger = 'some_trigger'
        
        # Simulate match_started
        observer._update_ws_state(
            'match_started',
            'autodarts.matches.new-match.state',
            {'state': 'active'},
            '{"state":"active"}'
        )
        
        assert observer._ws_state.match_active is True, \
            "match_started should set match_active=True"
        assert observer._ws_state.match_finished is False, \
            "match_started should reset match_finished=False"
        assert observer._ws_state.winner_detected is False, \
            "match_started should reset winner_detected=False"
        assert observer._ws_state.finish_trigger is None, \
            "match_started should clear finish_trigger"
        print("PASS: match_started resets match_active/finished/winner correctly")


# ═══════════════════════════════════════════════════════════════
# WSEventState.reset() TESTS
# ═══════════════════════════════════════════════════════════════

class TestWSEventStateReset:
    """Tests for WSEventState.reset() clearing last_match_id."""

    def test_reset_clears_last_match_id(self):
        """Verify reset() clears last_match_id."""
        ws_state = WSEventState()
        ws_state.match_active = True
        ws_state.match_finished = True
        ws_state.winner_detected = True
        ws_state.last_match_id = 'some-match-uuid'
        ws_state.last_match_state = 'finished'
        ws_state.last_game_event = 'matchshot'
        ws_state.finish_trigger = 'matchshot:channel'
        
        ws_state.reset()
        
        assert ws_state.last_match_id is None, \
            "reset() should clear last_match_id"
        assert ws_state.match_active is False, \
            "reset() should clear match_active"
        assert ws_state.match_finished is False, \
            "reset() should clear match_finished"
        assert ws_state.winner_detected is False, \
            "reset() should clear winner_detected"
        assert ws_state.finish_trigger is None, \
            "reset() should clear finish_trigger"
        print("PASS: WSEventState.reset() clears last_match_id (and other fields)")

    def test_reset_method_has_last_match_id_line(self):
        """Verify reset() method explicitly clears last_match_id in code."""
        source = inspect.getsource(WSEventState.reset)
        
        assert 'last_match_id' in source, \
            "reset() should explicitly clear last_match_id"
        print("PASS: WSEventState.reset() code contains last_match_id clearing")


# ═══════════════════════════════════════════════════════════════
# Chrome args TESTS - --start-fullscreen (not --start-maximized)
# ═══════════════════════════════════════════════════════════════

class TestChromeArgsFullscreen:
    """Tests for Chrome args: --start-fullscreen instead of --start-maximized."""

    def test_chrome_args_contains_start_fullscreen(self):
        """Verify chrome_args contains --start-fullscreen (not --start-maximized)."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        assert '--start-fullscreen' in source, \
            "chrome_args should contain --start-fullscreen"
        print("PASS: Chrome args contain --start-fullscreen")

    def test_chrome_args_not_start_maximized(self):
        """Verify chrome_args does NOT contain --start-maximized."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Check that --start-maximized is NOT in the chrome_args list (could be in comments)
        lines = source.split('\n')
        in_chrome_args = False
        for line in lines:
            stripped = line.strip()
            # Skip pure comment lines
            if stripped.startswith('#'):
                continue
            if 'chrome_args' in line and '=' in line and '[' in line:
                in_chrome_args = True
            if in_chrome_args:
                # Check if --start-maximized appears as an actual arg (not comment)
                if "'--start-maximized'" in line or '"--start-maximized"' in line:
                    if not stripped.startswith('#'):
                        pytest.fail(f"chrome_args should NOT contain --start-maximized: {line}")
                if ']' in line and 'append' not in line:
                    break
        
        # Also check no append('--start-maximized')
        has_maximized_append = (
            ".append('--start-maximized')" in source or 
            '.append("--start-maximized")' in source
        )
        assert not has_maximized_append, "Should NOT append --start-maximized"
        
        print("PASS: Chrome args do NOT contain --start-maximized")

    def test_chrome_args_not_kiosk(self):
        """Verify chrome_args does NOT contain --kiosk."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        # Find the chrome_args definition block (not comments)
        lines = source.split('\n')
        in_chrome_args = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                continue
            if 'chrome_args' in line and '=' in line and '[' in line:
                in_chrome_args = True
            if in_chrome_args:
                if "'--kiosk'" in line or '"--kiosk"' in line:
                    if not stripped.startswith('#'):
                        pytest.fail(f"chrome_args should NOT contain --kiosk: {line}")
                if ']' in line and 'append' not in line:
                    break
        
        # Also check no append('--kiosk')
        has_kiosk_append = ".append('--kiosk')" in source or '.append("--kiosk")' in source
        assert not has_kiosk_append, "Should NOT append --kiosk"
        
        print("PASS: Chrome args do NOT contain --kiosk")

    def test_chrome_args_has_disable_session_crashed_bubble(self):
        """Verify chrome_args includes --disable-session-crashed-bubble."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        assert '--disable-session-crashed-bubble' in source, \
            "chrome_args should include --disable-session-crashed-bubble"
        print("PASS: Chrome args contain --disable-session-crashed-bubble")


# ═══════════════════════════════════════════════════════════════
# Regression TESTS - Fresh page, lifecycle handlers, health check
# ═══════════════════════════════════════════════════════════════

class TestRegressionFreshPage:
    """Regression: Observer still creates fresh page via new_page()."""

    def test_uses_new_page(self):
        """Verify open_session uses context.new_page()."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        assert "new_page()" in source, \
            "Should use new_page() to create a fresh page"
        print("PASS: Observer still creates fresh page via new_page()")


class TestRegressionLifecycleHandlers:
    """Regression: Observer still has page close/crash/context close handlers."""

    def test_page_close_handler(self):
        """Verify page.on('close') handler is registered."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        assert "'close'" in source or '"close"' in source, \
            "Should register page.on('close') handler"
        assert "PAGE CLOSED" in source, "Should log PAGE CLOSED"
        print("PASS: Observer still has page close handler")

    def test_page_crash_handler(self):
        """Verify page.on('crash') handler is registered."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        assert "'crash'" in source or '"crash"' in source, \
            "Should register page.on('crash') handler"
        assert "PAGE CRASHED" in source, "Should log PAGE CRASHED"
        print("PASS: Observer still has page crash handler")

    def test_context_close_handler(self):
        """Verify context.on('close') handler is registered."""
        source = inspect.getsource(AutodartsObserver.open_session)
        
        assert "CONTEXT CLOSED" in source, \
            "Should have context.on('close') handler logging CONTEXT CLOSED"
        print("PASS: Observer still has context close handler")


class TestRegressionObserveLoopHealthCheck:
    """Regression: Observer still has browser health check in observe loop."""

    def test_health_check_in_observe_loop(self):
        """Verify observe loop has browser health check."""
        source = inspect.getsource(AutodartsObserver._observe_loop)
        
        has_health_check = "_page.url" in source or "self._page.url" in source
        assert has_health_check, "Should check page.url for browser health"
        print("PASS: Observer still has browser health check in observe loop")

    def test_browser_dead_logging(self):
        """Verify observe loop logs BROWSER DEAD on failure."""
        source = inspect.getsource(AutodartsObserver._observe_loop)
        
        assert "BROWSER DEAD" in source, \
            "Should log 'BROWSER DEAD' when browser dies"
        print("PASS: Observer logs BROWSER DEAD on health check failure")


# ═══════════════════════════════════════════════════════════════
# Backend Health TESTS
# ═══════════════════════════════════════════════════════════════

class TestBackendHealth:
    """Test backend health endpoint."""

    def test_api_health_responds(self):
        """Verify /api/health returns healthy."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get('status') == 'healthy', f"Unexpected status: {data}"
        print(f"PASS: Backend /api/health responds -> {data}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
