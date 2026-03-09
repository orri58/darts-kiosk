"""
Iteration 23 - Session-End Logic Fix Testing

This test suite verifies the unified session-end logic for Darts Kiosk:
1. Last game finished → auto-lock board
2. Last game aborted → auto-lock board  
3. Credits remaining → session stays open

Key test scenarios:
- Single credit: unlock → start → finish → auto-lock
- Single credit: unlock → start → abort → auto-lock
- Multi-credit (3): unlock → game1 finish → game2 abort → game3 finish → auto-lock
- Overlay visibility: visible when active, hidden when locked
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSessionEndLogicFix:
    """Tests for the unified session-end logic with finish and abort scenarios."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for admin operations."""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Ensure board is locked before each test
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        yield
        # Cleanup: lock board after each test
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)

    # =====================================================================
    # Single Credit Tests - Finish Scenario
    # =====================================================================
    
    def test_single_credit_finish_auto_locks(self):
        """
        Scenario: Unlock with 1 credit → start game → finish game → board auto-locks
        This tests the normal game completion with credits exhausted.
        """
        # Step 1: Unlock board with 1 credit
        unlock_resp = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 1,
                "price_total": 3.0
            })
        assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.text}"
        session_data = unlock_resp.json()
        assert session_data["credits_remaining"] == 1
        assert session_data["credits_total"] == 1
        
        # Step 2: Verify board is unlocked
        board_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert board_resp.status_code == 200
        assert board_resp.json()["board"]["status"] == "unlocked"
        
        # Step 3: Simulate game start (credit decremented: 1 → 0)
        start_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", 
            headers=self.headers)
        assert start_resp.status_code == 200, f"Simulate start failed: {start_resp.text}"
        
        # Step 4: Verify credit was decremented
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert session_resp.status_code == 200
        session_info = session_resp.json()
        assert session_info["session"]["credits_remaining"] == 0
        
        # Step 5: Simulate game end (finish) - should auto-lock
        end_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", 
            headers=self.headers)
        assert end_resp.status_code == 200, f"Simulate end failed: {end_resp.text}"
        
        # Step 6: Verify board is now locked and session is None
        board_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert board_resp.status_code == 200
        board_data = board_resp.json()
        assert board_data["board"]["status"] == "locked", "Board should be locked after last game finish"
        assert board_data["active_session"] is None, "Session should be None after credits exhausted"

    # =====================================================================
    # Single Credit Tests - Abort Scenario
    # =====================================================================
    
    def test_single_credit_abort_auto_locks(self):
        """
        Scenario: Unlock with 1 credit → start game → abort game → board auto-locks
        This tests the CRITICAL BUG FIX: aborting a started game when it's the last credit.
        """
        # Step 1: Unlock board with 1 credit
        unlock_resp = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 1,
                "price_total": 3.0
            })
        assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.text}"
        assert unlock_resp.json()["credits_remaining"] == 1
        
        # Step 2: Simulate game start (credit decremented: 1 → 0)
        start_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", 
            headers=self.headers)
        assert start_resp.status_code == 200
        
        # Step 3: Verify credit was decremented
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert session_resp.status_code == 200
        assert session_resp.json()["session"]["credits_remaining"] == 0
        
        # Step 4: Simulate game ABORT (not finish) - should auto-lock because credits=0
        abort_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-abort", 
            headers=self.headers)
        assert abort_resp.status_code == 200, f"Simulate abort failed: {abort_resp.text}"
        assert "Simulated game abort" in abort_resp.json()["message"]
        
        # Step 5: Verify board is now locked after abort
        board_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert board_resp.status_code == 200
        board_data = board_resp.json()
        assert board_data["board"]["status"] == "locked", "Board should be locked after last game abort"
        assert board_data["active_session"] is None, "Session should be None after abort with no credits"

    # =====================================================================
    # Multi-Credit Tests - Mixed Finish/Abort Scenarios
    # =====================================================================
    
    def test_multi_credit_mixed_games_auto_locks_on_last(self):
        """
        Scenario: Unlock with 3 credits → game1 finish → game2 abort → game3 finish → auto-lock
        Credits path: 3 → 2 → 1 → 0
        Tests that finish/abort both work correctly with remaining credits.
        """
        # Step 1: Unlock board with 3 credits
        unlock_resp = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "price_total": 9.0
            })
        assert unlock_resp.status_code == 200
        assert unlock_resp.json()["credits_remaining"] == 3
        
        # ─── Game 1: Start → Finish (credits 3 → 2) ───
        start_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", 
            headers=self.headers)
        assert start_resp.status_code == 200
        
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert session_resp.json()["session"]["credits_remaining"] == 2
        
        end_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", 
            headers=self.headers)
        assert end_resp.status_code == 200
        
        # Board should still be unlocked (2 credits remaining)
        board_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert board_resp.json()["board"]["status"] == "unlocked", "Board should stay unlocked with 2 credits"
        assert board_resp.json()["active_session"]["credits_remaining"] == 2
        
        # ─── Game 2: Start → Abort (credits 2 → 1) ───
        start_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", 
            headers=self.headers)
        assert start_resp.status_code == 200
        
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert session_resp.json()["session"]["credits_remaining"] == 1
        
        abort_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-abort", 
            headers=self.headers)
        assert abort_resp.status_code == 200
        
        # Board should still be unlocked (1 credit remaining)
        board_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert board_resp.json()["board"]["status"] == "unlocked", "Board should stay unlocked with 1 credit"
        assert board_resp.json()["active_session"]["credits_remaining"] == 1
        
        # ─── Game 3: Start → Finish (credits 1 → 0 → auto-lock) ───
        start_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", 
            headers=self.headers)
        assert start_resp.status_code == 200
        
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert session_resp.json()["session"]["credits_remaining"] == 0
        
        end_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", 
            headers=self.headers)
        assert end_resp.status_code == 200
        
        # Board should now be locked (0 credits)
        board_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert board_resp.json()["board"]["status"] == "locked", "Board should be locked after 3rd game"
        assert board_resp.json()["active_session"] is None

    def test_multi_credit_abort_last_game_auto_locks(self):
        """
        Scenario: Unlock with 2 credits → game1 finish → game2 ABORT → auto-lock
        Tests that the last game being aborted (not finished) still triggers lock.
        """
        # Step 1: Unlock board with 2 credits
        unlock_resp = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 2,
                "price_total": 6.0
            })
        assert unlock_resp.status_code == 200
        
        # ─── Game 1: Start → Finish (credits 2 → 1) ───
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", headers=self.headers)
        
        board_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert board_resp.json()["board"]["status"] == "unlocked"
        assert board_resp.json()["active_session"]["credits_remaining"] == 1
        
        # ─── Game 2: Start → ABORT (credits 1 → 0 → auto-lock) ───
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert session_resp.json()["session"]["credits_remaining"] == 0
        
        abort_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-abort", 
            headers=self.headers)
        assert abort_resp.status_code == 200
        
        # Board should be locked after last game abort
        board_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1", headers=self.headers)
        assert board_resp.json()["board"]["status"] == "locked", "Board should lock after last game abort"
        assert board_resp.json()["active_session"] is None

    # =====================================================================
    # Overlay Visibility Tests
    # =====================================================================
    
    def test_overlay_visible_when_unlocked_active(self):
        """Overlay should show visible:true when board is unlocked with active session."""
        # Unlock with 2 credits
        unlock_resp = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 2,
                "price_total": 6.0
            })
        assert unlock_resp.status_code == 200
        
        # Check overlay
        overlay_resp = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert overlay_resp.status_code == 200
        overlay_data = overlay_resp.json()
        assert overlay_data["visible"] is True
        assert overlay_data["credits_remaining"] == 2
        assert overlay_data["board_status"] == "unlocked"
    
    def test_overlay_hidden_when_locked(self):
        """Overlay should show visible:false when board is locked."""
        # Ensure board is locked
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        
        # Check overlay
        overlay_resp = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert overlay_resp.status_code == 200
        overlay_data = overlay_resp.json()
        assert overlay_data["visible"] is False

    def test_overlay_hidden_after_auto_lock(self):
        """Overlay should show visible:false after session auto-locks from credits exhaustion."""
        # Unlock with 1 credit
        unlock_resp = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 1,
                "price_total": 3.0
            })
        assert unlock_resp.status_code == 200
        
        # Start and end game
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", headers=self.headers)
        
        # Check overlay after auto-lock
        overlay_resp = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert overlay_resp.status_code == 200
        assert overlay_resp.json()["visible"] is False

    # =====================================================================
    # Endpoint Existence Tests
    # =====================================================================
    
    def test_simulate_game_abort_endpoint_exists(self):
        """Verify the new simulate-game-abort endpoint exists and works."""
        # First unlock board
        unlock_resp = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 2,
                "price_total": 6.0
            })
        assert unlock_resp.status_code == 200
        
        # Start a game first (so abort makes sense)
        start_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", 
            headers=self.headers)
        assert start_resp.status_code == 200
        
        # Test abort endpoint
        abort_resp = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-abort", 
            headers=self.headers)
        assert abort_resp.status_code == 200
        data = abort_resp.json()
        assert "message" in data
        assert "Simulated game abort" in data["message"]
        assert "BOARD-1" in data["message"]

    # =====================================================================
    # Credits Path Verification
    # =====================================================================
    
    def test_credits_path_3_to_0_across_3_games(self):
        """
        Verify credits decrement correctly: 3 → 2 → 1 → 0
        Testing with mixed finish/abort actions.
        """
        # Unlock with 3 credits
        unlock_resp = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "price_total": 9.0
            })
        assert unlock_resp.status_code == 200
        
        credits_path = []
        
        # Initial
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        credits_path.append(session_resp.json()["session"]["credits_remaining"])  # 3
        
        # Game 1 start
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        credits_path.append(session_resp.json()["session"]["credits_remaining"])  # 2
        
        # Game 1 finish
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", headers=self.headers)
        
        # Game 2 start
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        credits_path.append(session_resp.json()["session"]["credits_remaining"])  # 1
        
        # Game 2 abort
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-abort", headers=self.headers)
        
        # Game 3 start
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        credits_path.append(session_resp.json()["session"]["credits_remaining"])  # 0
        
        # Verify path
        assert credits_path == [3, 2, 1, 0], f"Credits path should be [3, 2, 1, 0], got {credits_path}"


class TestObserverCodeVerification:
    """Tests that verify the observer code has the correct handlers."""
    
    def test_observer_has_abort_handler_in_loop(self):
        """Verify observer.py has handler for in_game → idle (abort) transition."""
        import re
        
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, 'r') as f:
            content = f.read()
        
        # Check for abort handler comment or code
        assert "GAME ABORTED" in content, "Observer should have GAME ABORTED handler"
        assert "in_game -> idle" in content.lower() or "in_game → idle" in content, \
            "Observer should handle in_game → idle transition"
        assert 'reason="aborted"' in content or "reason='aborted'" in content, \
            "Observer should call on_game_ended with reason='aborted'"
    
    def test_observer_uses_unified_on_game_ended(self):
        """Verify observer uses single unified _on_game_ended callback."""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, 'r') as f:
            content = f.read()
        
        # Should have on_game_ended, not separate on_game_finished
        assert "_on_game_ended" in content, "Observer should use _on_game_ended callback"
        # Should NOT have separate _on_game_finished callback
        assert content.count("_on_game_finished") == 0, \
            "Observer should NOT have separate _on_game_finished callback"
    
    def test_kiosk_has_safe_close_observer(self):
        """Verify kiosk.py has _safe_close_observer with error handling."""
        kiosk_path = "/app/backend/routers/kiosk.py"
        with open(kiosk_path, 'r') as f:
            content = f.read()
        
        assert "_safe_close_observer" in content, "kiosk.py should have _safe_close_observer function"
        assert "observer_close_FAILED" in content or "observer_close_OK" in content, \
            "_safe_close_observer should have explicit logging"
    
    def test_on_game_ended_handles_all_scenarios(self):
        """Verify _on_game_ended handles finished, aborted, and post_finish_check."""
        kiosk_path = "/app/backend/routers/kiosk.py"
        with open(kiosk_path, 'r') as f:
            content = f.read()
        
        assert 'reason="finished"' in content or "reason='finished'" in content, \
            "_on_game_ended should handle finished"
        assert 'reason="aborted"' in content or "reason='aborted'" in content, \
            "_on_game_ended should handle aborted"
        assert 'reason="post_finish_check"' in content or "reason='post_finish_check'" in content, \
            "_on_game_ended should handle post_finish_check"
        
        # Check that all reasons are handled in the callback function
        assert "session_end_decision" in content, \
            "_on_game_ended should log session_end_decision"


class TestSessionEndLogging:
    """Tests that verify proper logging during session-end chain."""
    
    def test_logging_keywords_exist_in_kiosk(self):
        """Verify kiosk.py has explicit logging for session-end chain."""
        kiosk_path = "/app/backend/routers/kiosk.py"
        with open(kiosk_path, 'r') as f:
            content = f.read()
        
        # Check for explicit logging keywords
        assert "session_end_decision" in content, "Should log session_end_decision"
        assert "board_lock_triggered" in content, "Should log board_lock_triggered"
        assert "browser_close_triggered" in content, "Should log browser_close_triggered"
    
    def test_logging_keywords_exist_in_observer(self):
        """Verify observer.py has explicit logging for state transitions."""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, 'r') as f:
            content = f.read()
        
        # Check for transition logging
        assert "TRANSITION" in content, "Should log state transitions"
        assert "GAME STARTED" in content, "Should log game start"
        assert "GAME FINISHED" in content, "Should log game finish"
        assert "GAME ABORTED" in content, "Should log game abort"
