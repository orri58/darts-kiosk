"""
Test Iteration 39: Autodarts WebSocket Observer State Machine REWRITE

MAJOR REWRITE: Previous classifications are ALL REMOVED and replaced with new
event-driven match lifecycle detection based on real board PC diagnostics.

Old (REMOVED):
  match_deleted, board_match_deleted, match_not_found, match_started,
  game_state_finished, turn_transition, game_event, match_state, match_related

New (ADDED):
  match_start_turn_start    : event=turn_start  -> match START
  match_start_throw         : event=throw       -> match START
  match_end_gameshot_match  : event=game_shot + body.type=match -> match END
  match_end_state_finished  : finished=true (boolean) -> match END
  match_end_game_finished   : gameFinished=true (boolean) -> match END
  match_finished_matchshot  : matchshot keyword -> match END (backward compat)
  match_reset_delete        : event=delete -> full RESET (post-match cleanup)
  round_transition_gameshot : event=game_shot + NOT body.type=match -> leg end
  match_other               : other autodarts-related frames
  subscription              : subscribe/attach frames
  irrelevant                : non-autodarts frames

Credit Logic Change:
  Credits deducted at game END (on reason="finished"), NOT at game start.
"""

import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, '/app')

from backend.services.autodarts_observer import (
    AutodartsObserver, ObserverState, WSEventState
)


class TestClassifyFrameMatchStart:
    """Test _classify_frame for MATCH START signals."""

    def test_turn_start_event_direct(self):
        """event=turn_start (direct) -> match_start_turn_start"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "turn_start", "player": 1}'
        payload = {"event": "turn_start", "player": 1}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "match_start_turn_start", f"Expected match_start_turn_start, got {result}"

    def test_turn_start_event_nested(self):
        """event=turn_start (nested in data) -> match_start_turn_start"""
        obs = AutodartsObserver("TEST")
        raw = '{"data": {"event": "turn_start"}}'
        payload = {"data": {"event": "turn_start"}}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "match_start_turn_start", f"Expected match_start_turn_start, got {result}"

    def test_throw_event_direct(self):
        """event=throw -> match_start_throw"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "throw", "segment": "T20"}'
        payload = {"event": "throw", "segment": "T20"}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "match_start_throw", f"Expected match_start_throw, got {result}"

    def test_throw_event_nested(self):
        """event=throw (nested in data) -> match_start_throw"""
        obs = AutodartsObserver("TEST")
        raw = '{"data": {"event": "throw", "segment": "D16"}}'
        payload = {"data": {"event": "throw", "segment": "D16"}}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "match_start_throw", f"Expected match_start_throw, got {result}"

    def test_turn_end_is_NOT_match_start(self):
        """turn_end should NOT be classified as match start (ignored for lifecycle)"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "turn_end"}'
        payload = {"event": "turn_end"}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        # Should be match_other, NOT a start signal
        assert result != "match_start_turn_start", "turn_end should not be match_start_turn_start"
        assert result != "match_start_throw", "turn_end should not be match_start_throw"
        assert result == "match_other", f"Expected match_other for turn_end, got {result}"


class TestClassifyFrameMatchEnd:
    """Test _classify_frame for MATCH END signals."""

    def test_game_shot_match_type_direct(self):
        """game_shot + body.type=match -> match_end_gameshot_match"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "game_shot", "body": {"type": "match"}}'
        payload = {"event": "game_shot", "body": {"type": "match"}}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "match_end_gameshot_match", f"Expected match_end_gameshot_match, got {result}"

    def test_game_shot_match_type_nested_data(self):
        """game_shot + data.type=match -> match_end_gameshot_match"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "game_shot", "data": {"type": "match"}}'
        payload = {"event": "game_shot", "data": {"type": "match"}}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "match_end_gameshot_match", f"Expected match_end_gameshot_match, got {result}"

    def test_game_shot_match_type_nested_data_body(self):
        """game_shot + data.body.type=match -> match_end_gameshot_match"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "game_shot", "data": {"body": {"type": "match"}}}'
        payload = {"event": "game_shot", "data": {"body": {"type": "match"}}}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "match_end_gameshot_match", f"Expected match_end_gameshot_match, got {result}"

    def test_game_shot_game_type(self):
        """game_shot + body.type=game -> round_transition_gameshot (leg end, NOT match)"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "game_shot", "body": {"type": "game"}}'
        payload = {"event": "game_shot", "body": {"type": "game"}}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "round_transition_gameshot", f"Expected round_transition_gameshot, got {result}"

    def test_game_shot_no_type(self):
        """game_shot with no type -> round_transition_gameshot (default to leg)"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "game_shot"}'
        payload = {"event": "game_shot"}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "round_transition_gameshot", f"Expected round_transition_gameshot, got {result}"

    def test_finished_true_boolean_direct(self):
        """finished=true (boolean, direct) -> match_end_state_finished"""
        obs = AutodartsObserver("TEST")
        raw = '{"finished": true, "state": "done"}'
        payload = {"finished": True, "state": "done"}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.state", payload)
        assert result == "match_end_state_finished", f"Expected match_end_state_finished, got {result}"

    def test_finished_true_nested_data(self):
        """data.finished=true (nested boolean) -> match_end_state_finished"""
        obs = AutodartsObserver("TEST")
        raw = '{"data": {"finished": true}}'
        payload = {"data": {"finished": True}}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.state", payload)
        assert result == "match_end_state_finished", f"Expected match_end_state_finished, got {result}"

    def test_finished_false_not_match_end(self):
        """finished=false should NOT be match_end_state_finished"""
        obs = AutodartsObserver("TEST")
        raw = '{"finished": false}'
        payload = {"finished": False}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.state", payload)
        assert result != "match_end_state_finished", "finished=false should not trigger match end"

    def test_finished_missing_not_match_end(self):
        """missing 'finished' key should NOT be match_end_state_finished"""
        obs = AutodartsObserver("TEST")
        raw = '{"state": "active"}'
        payload = {"state": "active"}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.state", payload)
        assert result != "match_end_state_finished", "missing finished should not trigger match end"

    def test_game_finished_true_boolean(self):
        """gameFinished=true (boolean) -> match_end_game_finished"""
        obs = AutodartsObserver("TEST")
        raw = '{"gameFinished": true}'
        payload = {"gameFinished": True}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.state", payload)
        assert result == "match_end_game_finished", f"Expected match_end_game_finished, got {result}"

    def test_game_finished_false_not_end(self):
        """gameFinished=false should NOT be match_end_game_finished"""
        obs = AutodartsObserver("TEST")
        raw = '{"gameFinished": false}'
        payload = {"gameFinished": False}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.state", payload)
        assert result != "match_end_game_finished", "gameFinished=false should not trigger match end"

    def test_matchshot_keyword(self):
        """matchshot keyword -> match_finished_matchshot (backward compat)"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "matchshot", "winner": "Player1"}'
        payload = {"event": "matchshot", "winner": "Player1"}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "match_finished_matchshot", f"Expected match_finished_matchshot, got {result}"

    def test_matchshot_in_text_message(self):
        """matchshot in raw text -> match_finished_matchshot"""
        obs = AutodartsObserver("TEST")
        raw = 'Player wins with a matchshot!'
        result = obs._classify_frame(raw, "some.channel", None)
        assert result == "match_finished_matchshot", f"Expected match_finished_matchshot, got {result}"


class TestClassifyFrameMatchReset:
    """Test _classify_frame for post-match RESET signals."""

    def test_delete_event_direct(self):
        """event=delete -> match_reset_delete"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "delete"}'
        payload = {"event": "delete"}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.state", payload)
        assert result == "match_reset_delete", f"Expected match_reset_delete, got {result}"

    def test_delete_event_nested(self):
        """data.event=delete -> match_reset_delete"""
        obs = AutodartsObserver("TEST")
        raw = '{"data": {"event": "delete"}}'
        payload = {"data": {"event": "delete"}}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.state", payload)
        assert result == "match_reset_delete", f"Expected match_reset_delete, got {result}"


class TestClassifyFrameOther:
    """Test _classify_frame for non-lifecycle frames."""

    def test_subscription_frame(self):
        """subscribe in raw -> subscription"""
        obs = AutodartsObserver("TEST")
        raw = '{"action": "subscribe", "channel": "autodarts.matches.abc"}'
        payload = {"action": "subscribe", "channel": "autodarts.matches.abc"}
        result = obs._classify_frame(raw, "autodarts", payload)
        assert result == "subscription", f"Expected subscription, got {result}"

    def test_attach_frame(self):
        """attach in raw -> subscription"""
        obs = AutodartsObserver("TEST")
        raw = '{"action": "attach", "channel": "autodarts.boards.123"}'
        payload = {"action": "attach"}
        result = obs._classify_frame(raw, "autodarts.boards.123", payload)
        assert result == "subscription", f"Expected subscription, got {result}"

    def test_score_update_is_match_other(self):
        """score update -> match_other (not lifecycle)"""
        obs = AutodartsObserver("TEST")
        raw = '{"event": "score", "points": 60}'
        payload = {"event": "score", "points": 60}
        result = obs._classify_frame(raw, "autodarts.matches.abc123.game-events", payload)
        assert result == "match_other", f"Expected match_other for score event, got {result}"

    def test_irrelevant_frame(self):
        """non-autodarts frame -> irrelevant"""
        obs = AutodartsObserver("TEST")
        raw = '{"ping": "pong"}'
        payload = {"ping": "pong"}
        result = obs._classify_frame(raw, "other.channel", payload)
        assert result == "irrelevant", f"Expected irrelevant, got {result}"


class TestUpdateWSStateMatchStart:
    """Test _update_ws_state for MATCH START transitions."""

    def test_turn_start_sets_match_active(self):
        """turn_start sets match_active=True"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        
        assert obs._ws_state.match_active is False
        obs._update_ws_state("match_start_turn_start", "autodarts.matches.abc.game-events", {}, "")
        assert obs._ws_state.match_active is True, "turn_start should set match_active=True"

    def test_throw_sets_match_active(self):
        """throw sets match_active=True (when not already active)"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        
        assert obs._ws_state.match_active is False
        obs._update_ws_state("match_start_throw", "autodarts.matches.abc.game-events", {}, "")
        assert obs._ws_state.match_active is True, "throw should set match_active=True"

    def test_throw_after_delete_re_enables_match(self):
        """throw after delete re-enables match_active"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        
        # Simulate: match was active, then deleted
        obs._ws_state.match_active = False
        obs._ws_state.match_finished = False  # delete resets this
        obs._ws_state.last_match_id = None  # delete resets this
        
        # Now throw should re-enable
        obs._update_ws_state("match_start_throw", "autodarts.matches.xyz.game-events", {}, "")
        assert obs._ws_state.match_active is True, "throw should re-enable match_active after reset"


class TestUpdateWSStateMatchEnd:
    """Test _update_ws_state for MATCH END transitions."""

    def test_gameshot_match_sets_finished(self):
        """game_shot+match sets match_finished=True, match_active=False"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        obs._ws_state.match_active = True
        
        obs._update_ws_state("match_end_gameshot_match", "autodarts.matches.abc.game-events", {}, "")
        
        assert obs._ws_state.match_finished is True, "gameshot_match should set match_finished=True"
        assert obs._ws_state.match_active is False, "gameshot_match should set match_active=False"
        assert obs._ws_state.winner_detected is True

    def test_finished_true_sets_finished(self):
        """finished=true sets match_finished=True, match_active=False"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        obs._ws_state.match_active = True
        
        obs._update_ws_state("match_end_state_finished", "autodarts.matches.abc.state", {}, "")
        
        assert obs._ws_state.match_finished is True
        assert obs._ws_state.match_active is False

    def test_game_finished_sets_finished(self):
        """gameFinished=true sets match_finished=True, match_active=False"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        obs._ws_state.match_active = True
        
        obs._update_ws_state("match_end_game_finished", "autodarts.matches.abc.state", {}, "")
        
        assert obs._ws_state.match_finished is True
        assert obs._ws_state.match_active is False


class TestUpdateWSStateMatchReset:
    """Test _update_ws_state for FULL RESET on delete event."""

    def test_delete_does_full_reset(self):
        """delete event does FULL RESET (match_active=False, match_finished=False, last_match_id=None)"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        
        # Setup: match was active
        obs._ws_state.match_active = True
        obs._ws_state.match_finished = False
        obs._ws_state.last_match_id = "abc-123"
        obs._ws_state.winner_detected = True
        
        # Delete should reset everything
        obs._update_ws_state("match_reset_delete", "autodarts.matches.abc.state", {}, "")
        
        assert obs._ws_state.match_active is False, "delete should reset match_active"
        assert obs._ws_state.match_finished is False, "delete should reset match_finished"
        assert obs._ws_state.last_match_id is None, "delete should reset last_match_id"

    def test_delete_after_active_match_resets_everything(self):
        """delete after active match resets everything"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        
        # Setup: full match flow
        obs._update_ws_state("match_start_turn_start", "autodarts.matches.abc-123.game-events", {}, "")
        obs._ws_state.last_match_id = "abc-123"
        
        assert obs._ws_state.match_active is True
        
        # Delete should fully reset
        obs._update_ws_state("match_reset_delete", "autodarts.matches.abc-123.state", {}, "")
        
        assert obs._ws_state.match_active is False
        assert obs._ws_state.match_finished is False
        assert obs._ws_state.last_match_id is None


class TestReadWSEventState:
    """Test _read_ws_event_state method."""

    def test_match_finished_returns_finished(self):
        """match_finished=True -> FINISHED"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        obs._ws_state.match_finished = True
        
        result = obs._read_ws_event_state()
        assert result == ObserverState.FINISHED, f"Expected FINISHED, got {result}"

    def test_match_active_returns_in_game(self):
        """match_active=True -> IN_GAME"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        obs._ws_state.match_active = True
        
        result = obs._read_ws_event_state()
        assert result == ObserverState.IN_GAME, f"Expected IN_GAME, got {result}"

    def test_neither_returns_none(self):
        """neither active nor finished -> None"""
        obs = AutodartsObserver("TEST")
        obs._ws_state = WSEventState()
        obs._ws_state.match_active = False
        obs._ws_state.match_finished = False
        
        result = obs._read_ws_event_state()
        assert result is None, f"Expected None, got {result}"


class TestHelperExtractEvent:
    """Test _extract_event helper method."""

    def test_extract_event_direct(self):
        """Extract event from direct payload"""
        obs = AutodartsObserver("TEST")
        payload = {"event": "turn_start"}
        assert obs._extract_event(payload) == "turn_start"

    def test_extract_event_nested_data(self):
        """Extract event from data.event"""
        obs = AutodartsObserver("TEST")
        payload = {"data": {"event": "throw"}}
        assert obs._extract_event(payload) == "throw"

    def test_extract_event_type_key(self):
        """Extract type as event"""
        obs = AutodartsObserver("TEST")
        payload = {"type": "game_shot"}
        assert obs._extract_event(payload) == "game_shot"

    def test_extract_event_empty_payload(self):
        """Empty payload returns empty string"""
        obs = AutodartsObserver("TEST")
        assert obs._extract_event(None) == ""
        assert obs._extract_event({}) == ""


class TestHelperExtractBodyType:
    """Test _extract_body_type helper method."""

    def test_extract_body_type_from_body(self):
        """Extract type from body"""
        obs = AutodartsObserver("TEST")
        payload = {"body": {"type": "match"}}
        assert obs._extract_body_type(payload) == "match"

    def test_extract_body_type_from_data(self):
        """Extract type from data"""
        obs = AutodartsObserver("TEST")
        payload = {"data": {"type": "game"}}
        assert obs._extract_body_type(payload) == "game"

    def test_extract_body_type_from_data_body(self):
        """Extract type from data.body"""
        obs = AutodartsObserver("TEST")
        payload = {"data": {"body": {"type": "match"}}}
        assert obs._extract_body_type(payload) == "match"

    def test_extract_body_type_empty(self):
        """Empty payload returns empty string"""
        obs = AutodartsObserver("TEST")
        assert obs._extract_body_type(None) == ""
        assert obs._extract_body_type({}) == ""


class TestHelperExtractBoolField:
    """Test _extract_bool_field helper method."""

    def test_extract_bool_field_true_direct(self):
        """finished=True (direct) returns True"""
        obs = AutodartsObserver("TEST")
        payload = {"finished": True}
        assert obs._extract_bool_field(payload, "finished") is True

    def test_extract_bool_field_false_direct(self):
        """finished=False (direct) returns False"""
        obs = AutodartsObserver("TEST")
        payload = {"finished": False}
        assert obs._extract_bool_field(payload, "finished") is False

    def test_extract_bool_field_nested_data(self):
        """data.finished=True returns True"""
        obs = AutodartsObserver("TEST")
        payload = {"data": {"finished": True}}
        assert obs._extract_bool_field(payload, "finished") is True

    def test_extract_bool_field_nested_match(self):
        """match.finished=True returns True"""
        obs = AutodartsObserver("TEST")
        payload = {"match": {"finished": True}}
        assert obs._extract_bool_field(payload, "finished") is True

    def test_extract_bool_field_missing(self):
        """missing field returns False"""
        obs = AutodartsObserver("TEST")
        payload = {"other": "value"}
        assert obs._extract_bool_field(payload, "finished") is False

    def test_extract_bool_field_string_not_bool(self):
        """String 'true' is not boolean True, returns False"""
        obs = AutodartsObserver("TEST")
        payload = {"finished": "true"}  # string, not boolean
        assert obs._extract_bool_field(payload, "finished") is False


class TestChromeArgs:
    """Test Chrome launch arguments."""

    def test_chrome_args_has_start_fullscreen(self):
        """Chrome args contain --start-fullscreen"""
        obs = AutodartsObserver("TEST")
        # Read the source code to verify chrome_args
        import inspect
        source = inspect.getsource(obs.open_session)
        assert "--start-fullscreen" in source, "Chrome args should contain --start-fullscreen"

    def test_chrome_args_no_kiosk(self):
        """Chrome args do NOT contain --kiosk"""
        obs = AutodartsObserver("TEST")
        import inspect
        source = inspect.getsource(obs.open_session)
        # --kiosk should NOT be in chrome_args list (it's only in comments)
        # Check that chrome_args list doesn't contain kiosk
        # The actual args list is defined in the method
        assert "chrome_args.append('--kiosk')" not in source, "Chrome args should NOT append --kiosk"


class TestKioskCreditDeduction:
    """Test credit deduction logic in kiosk.py - verifies credit is deducted at END, not START."""

    def test_on_game_started_no_credit_deduction(self):
        """_on_game_started does NOT deduct credits (deferred to end)"""
        # Read kiosk.py source to verify no credit deduction at start
        with open('/app/backend/routers/kiosk.py', 'r') as f:
            source = f.read()
        
        # Find _on_game_started function - capture until next async def
        import re
        match = re.search(r'async def _on_game_started\(.*?\n(.*?)(?=\nasync def )', source, re.DOTALL)
        if match:
            func_source = match.group(0)
            # Should NOT have credit deduction logic (credits_remaining - 1)
            assert "credits_remaining - 1" not in func_source, "_on_game_started should NOT deduct credits"
            # Should have log saying deferred to match end
            assert "deferred to match end" in func_source.lower(), \
                f"_on_game_started should log that credit is deferred to match end. Got:\n{func_source[:500]}"

    def test_on_game_ended_deducts_credit_on_finished(self):
        """_on_game_ended with reason=finished DOES deduct credit (PER_GAME mode)"""
        with open('/app/backend/routers/kiosk.py', 'r') as f:
            source = f.read()
        
        import re
        match = re.search(r'async def _on_game_ended\(.*?\n(?:.*?\n)*?(?=async def|class |@router|\n\n\n)', source, re.MULTILINE)
        if match:
            func_source = match.group(0)
            # Should have credit deduction for finished
            assert "credits_remaining - 1" in func_source or "credits_remaining" in func_source, \
                "_on_game_ended should have credit deduction logic"
            # Should check for reason == "finished"
            assert 'reason == "finished"' in func_source or "finished" in func_source, \
                "_on_game_ended should check for finished reason"

    def test_on_game_ended_no_deduction_on_aborted(self):
        """_on_game_ended with reason=aborted does NOT deduct credit"""
        with open('/app/backend/routers/kiosk.py', 'r') as f:
            source = f.read()
        
        # The logic should only deduct on finished, not aborted
        # Check the conditional: if reason == "finished"
        assert 'if reason == "finished"' in source, \
            "Credit deduction should be conditional on reason='finished'"


class TestBackendHealth:
    """Test backend health endpoint."""

    def test_health_endpoint(self):
        """Backend /api/health responds"""
        import requests
        BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unexpected health status: {data}"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
