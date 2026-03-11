"""
Test Iteration 44: Delete Event = Aborted Match End

Tests the fix for: delete event (Spiel-Abbruch im Autodarts Interface) must be treated
as an aborted match-end. Previously, delete was only interpreted as reset, which caused:
- Observer staying open
- Kiosk UI hanging
- Session not finalized

Three match-end types:
1. Normal finish (finished, credit-=1)
2. Manual finish (finished, credit-=1) 
3. Abort via delete (aborted, NO credit deduction, but FULL teardown)

CRITICAL CHANGES:
1. _classify_frame returns 'match_reset_delete' for delete events
2. _update_ws_state: delete during match_active=True sets finish_trigger='match_abort_delete', match_active=False
3. _update_ws_state: delete when match_active=False does full ws.reset()
4. _should_deduct_credit('aborted') returns False
5. _should_deduct_credit('match_abort_delete') returns False
6. simulate-game-abort: credits unchanged, should_lock=False, should_teardown=True
7. After abort: board status stays 'unlocked', session still active
"""

import pytest
import requests
import sys

sys.path.insert(0, '/app')

BASE_URL = "https://boardgame-repair.preview.emergentagent.com"
BOARD_ID = "BOARD-1"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token."""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    }, timeout=10)
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Get headers with admin authentication."""
    return {"Authorization": f"Bearer {admin_token}"}


def reset_board(admin_headers):
    """Helper to lock the board (reset state)."""
    requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=admin_headers, timeout=10)


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: _classify_frame for delete events
# ═══════════════════════════════════════════════════════════════════════════════

class TestClassifyFrameDelete:
    """Test that _classify_frame returns 'match_reset_delete' for delete events."""

    def test_classify_delete_event_returns_match_reset_delete(self):
        """delete event should be classified as match_reset_delete."""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        
        result = obs._classify_frame(
            '{"event": "delete"}',
            "autodarts.matches.abc.game-events",
            {"event": "delete"}
        )
        assert result == "match_reset_delete", f"Expected 'match_reset_delete', got '{result}'"

    def test_classify_delete_event_different_formats(self):
        """delete event in various payload formats."""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        
        # Format 1: Simple event payload
        result1 = obs._classify_frame(
            '{"event": "delete"}',
            "unknown",
            {"event": "delete"}
        )
        assert result1 == "match_reset_delete"
        
        # Format 2: Nested data payload
        result2 = obs._classify_frame(
            '{"data": {"event": "delete"}}',
            "autodarts.matches.xyz",
            {"data": {"event": "delete"}}
        )
        # _extract_event checks data.event too
        assert result2 == "match_reset_delete"


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: _update_ws_state for delete events
# ═══════════════════════════════════════════════════════════════════════════════

class TestUpdateWsStateDelete:
    """Test _update_ws_state behavior for delete events during different states."""

    def test_delete_during_active_match_sets_abort_trigger(self):
        """Delete during match_active=True should set finish_trigger='match_abort_delete', match_active=False."""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        
        # Set up: match is active
        obs._ws_state.match_active = True
        obs._ws_state.match_finished = False
        obs._ws_state.last_match_id = "test-match-123"
        
        # Call _update_ws_state with match_reset_delete
        obs._update_ws_state("match_reset_delete", "autodarts.matches.test-match-123", None, "")
        
        # Verify state changes
        assert obs._ws_state.match_active is False, "match_active should be False after abort"
        assert obs._ws_state.finish_trigger == "match_abort_delete", \
            f"finish_trigger should be 'match_abort_delete', got '{obs._ws_state.finish_trigger}'"
        assert obs._ws_state.match_finished is False, \
            "match_finished should stay False (abort, not finish)"

    def test_delete_after_match_finished_does_full_reset(self):
        """Delete when match_active=False (post-match) should do full ws.reset()."""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        
        # Set up: match just finished (post-match state)
        obs._ws_state.match_active = False
        obs._ws_state.match_finished = True
        obs._ws_state.winner_detected = True
        obs._ws_state.finish_trigger = "match_end_gameshot_match"
        obs._ws_state.last_match_id = "test-match-456"
        
        # Call _update_ws_state with match_reset_delete (post-match cleanup)
        obs._update_ws_state("match_reset_delete", "autodarts.matches.test-match-456", None, "")
        
        # Verify full reset (ws.reset() clears all fields)
        assert obs._ws_state.match_active is False
        assert obs._ws_state.match_finished is False, "match_finished should be reset"
        assert obs._ws_state.winner_detected is False, "winner_detected should be reset"
        assert obs._ws_state.finish_trigger is None, "finish_trigger should be None after reset"

    def test_delete_when_idle_does_full_reset(self):
        """Delete when match_active=False and match_finished=False should do full reset."""
        from backend.services.autodarts_observer import AutodartsObserver
        obs = AutodartsObserver("TEST")
        
        # Set up: idle state (no active match)
        obs._ws_state.match_active = False
        obs._ws_state.match_finished = False
        obs._ws_state.last_match_id = "old-match"
        
        # Call _update_ws_state with match_reset_delete
        obs._update_ws_state("match_reset_delete", "autodarts.matches.old-match", None, "")
        
        # Verify reset
        assert obs._ws_state.match_active is False
        assert obs._ws_state.match_finished is False
        assert obs._ws_state.finish_trigger is None


# ═══════════════════════════════════════════════════════════════════════════════
# UNIT TESTS: _should_deduct_credit policy
# ═══════════════════════════════════════════════════════════════════════════════

class TestShouldDeductCreditAbortTriggers:
    """Test credit deduction policy for abort-related triggers."""

    def test_aborted_returns_false(self):
        """_should_deduct_credit('aborted') returns False."""
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("aborted") is False

    def test_match_abort_delete_returns_false(self):
        """_should_deduct_credit('match_abort_delete') returns False."""
        from backend.routers.kiosk import _should_deduct_credit
        result = _should_deduct_credit("match_abort_delete")
        assert result is False, f"match_abort_delete should NOT deduct credit, got {result}"

    def test_finished_returns_true(self):
        """_should_deduct_credit('finished') returns True."""
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("finished") is True

    def test_match_end_gameshot_match_returns_true(self):
        """_should_deduct_credit('match_end_gameshot_match') returns True."""
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("match_end_gameshot_match") is True

    def test_manual_returns_true(self):
        """_should_deduct_credit('manual') returns True."""
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("manual") is True


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: simulate-game-abort endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestSimulateGameAbort:
    """Test simulate-game-abort endpoint behavior."""

    def test_abort_credits_unchanged(self, admin_headers):
        """simulate-game-abort: credits should remain unchanged."""
        # Reset and unlock with 3 credits
        reset_board(admin_headers)
        r = requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                          headers=admin_headers,
                          json={"pricing_mode": "per_game", "credits": 3},
                          timeout=10)
        assert r.status_code == 200
        
        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        
        # Abort the game
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        
        # Credits should remain at 3
        assert data["credits_remaining"] == 3, \
            f"Abort should NOT deduct credit, expected 3, got {data['credits_remaining']}"

    def test_abort_should_lock_false(self, admin_headers):
        """simulate-game-abort: should_lock should be False."""
        # Reset and unlock with 3 credits
        reset_board(admin_headers)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                      headers=admin_headers,
                      json={"pricing_mode": "per_game", "credits": 3},
                      timeout=10)
        
        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        
        # Abort the game
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        
        assert data["should_lock"] is False, \
            f"Abort should NOT lock board, got should_lock={data['should_lock']}"

    def test_abort_should_teardown_true(self, admin_headers):
        """simulate-game-abort: should_teardown should be True."""
        # Reset and unlock with 3 credits
        reset_board(admin_headers)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                      headers=admin_headers,
                      json={"pricing_mode": "per_game", "credits": 3},
                      timeout=10)
        
        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        
        # Abort the game
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        
        assert data["should_teardown"] is True, \
            f"Abort should trigger TEARDOWN, got should_teardown={data['should_teardown']}"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Board status after abort
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoardStatusAfterAbort:
    """Test board status remains unlocked after abort."""

    def test_board_status_stays_unlocked(self, admin_headers):
        """After abort: board status stays 'unlocked'."""
        # Reset and unlock with 3 credits
        reset_board(admin_headers)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                      headers=admin_headers,
                      json={"pricing_mode": "per_game", "credits": 3},
                      timeout=10)
        
        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        
        # Abort the game
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["board_status"] == "unlocked", \
            f"After abort, board should be unlocked, got {data['board_status']}"
        
        # Double-check via GET /api/boards/{id}
        r = requests.get(f"{BASE_URL}/api/boards/{BOARD_ID}", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        board_data = r.json()
        assert board_data["board"]["status"] == "unlocked", \
            f"Board status should be unlocked, got {board_data['board']['status']}"

    def test_session_still_active_after_abort(self, admin_headers):
        """After abort: session still active (credits available)."""
        # Reset and unlock with 3 credits
        reset_board(admin_headers)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                      headers=admin_headers,
                      json={"pricing_mode": "per_game", "credits": 3},
                      timeout=10)
        
        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        
        # Abort the game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort", headers=admin_headers, timeout=10)
        
        # Check session still active
        r = requests.get(f"{BASE_URL}/api/boards/{BOARD_ID}", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        
        assert data["active_session"] is not None, "Session should still be active after abort"
        assert data["active_session"]["credits_remaining"] == 3, \
            f"Credits should remain at 3, got {data['active_session']['credits_remaining']}"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Full 3-scenario test
# ═══════════════════════════════════════════════════════════════════════════════

class TestFull3ScenarioLoop:
    """Test: unlock(3) → finish(3→2) → abort(2→2, teardown=True) → finish(2→1)"""

    def test_3_scenario_loop(self, admin_headers):
        """Full cycle: unlock(3) → finish(3→2) → abort(2→2, teardown=True) → finish(2→1)."""
        # Step 0: Lock board to reset state
        reset_board(admin_headers)
        
        # Step 1: Unlock board with 3 credits
        r = requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                          headers=admin_headers,
                          json={"pricing_mode": "per_game", "credits": 3},
                          timeout=10)
        assert r.status_code == 200
        
        # Verify 3 credits
        r = requests.get(f"{BASE_URL}/api/boards/{BOARD_ID}", headers=admin_headers, timeout=10)
        assert r.json()["active_session"]["credits_remaining"] == 3
        
        # ─── GAME 1: Normal finish (3→2) ───
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["credits_remaining"] == 2, f"After game 1, credits should be 2, got {data['credits_remaining']}"
        assert data["should_teardown"] is False, "Game 1 should NOT teardown (credits=2)"
        assert data["board_status"] == "unlocked"
        
        # ─── GAME 2: Abort (2→2, teardown=True) ───
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["credits_remaining"] == 2, f"After abort, credits should still be 2, got {data['credits_remaining']}"
        assert data["should_teardown"] is True, "Abort SHOULD trigger teardown"
        assert data["should_lock"] is False, "Abort should NOT lock board"
        assert data["board_status"] == "unlocked"
        
        # ─── GAME 3: Normal finish (2→1) ───
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["credits_remaining"] == 1, f"After game 3, credits should be 1, got {data['credits_remaining']}"
        assert data["should_teardown"] is False, "Game 3 should NOT teardown (credits=1)"
        assert data["board_status"] == "unlocked"


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Manual end-game
# ═══════════════════════════════════════════════════════════════════════════════

class TestManualEndGame:
    """Test manual end-game behavior."""

    def test_manual_end_deducts_credit_and_locks(self, admin_headers):
        """Manual end-game: credits decremented, should_lock=True, should_teardown=True."""
        # Reset and unlock with 2 credits
        reset_board(admin_headers)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                      headers=admin_headers,
                      json={"pricing_mode": "per_game", "credits": 2},
                      timeout=10)
        
        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        
        # Manual end-game
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/end-game", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        
        # Manual should: deduct credit, lock board, trigger teardown
        assert data["credits_remaining"] == 1, \
            f"Manual should deduct credit, expected 1, got {data['credits_remaining']}"
        assert data["should_lock"] is True, "Manual should LOCK board"
        assert data["should_teardown"] is True, "Manual should trigger teardown"


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthCheck:
    """Backend health check."""

    def test_health_endpoint(self):
        """Backend /api/health responds 200."""
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
