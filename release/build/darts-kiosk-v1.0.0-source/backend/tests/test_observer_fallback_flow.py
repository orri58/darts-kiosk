"""
Observer Mode Kiosk Fallback Flow Tests - Iteration 19
Tests the new two-screen observer mode: HANDOFF (browser open) vs FALLBACK (browser closed)

Key test scenarios:
1. GET /api/boards/BOARD-1/session returns autodarts_mode, observer_browser_open, observer_state
2. POST /api/boards/BOARD-1/unlock creates session with per_game pricing
3. GET /api/boards/BOARD-1/session after unlock returns correct observer status
4. GET /api/kiosk/BOARD-1/overlay returns visible=true with credits
5. POST /api/boards/BOARD-1/lock locks the board
6. POST /api/kiosk/BOARD-1/end-game returns should_lock or credits_remaining
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestObserverFallbackFlow:
    """Test observer mode with fallback screen (no Autodarts URL configured)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token and ensure board is locked before each test"""
        self.api = requests.Session()
        self.api.headers.update({"Content-Type": "application/json"})
        
        # Login
        response = self.api.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        token = response.json().get("access_token")
        assert token, "No access_token in login response"
        self.api.headers.update({"Authorization": f"Bearer {token}"})
        
        # Lock board first to ensure clean state
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/lock")
        
        yield
        
        # Cleanup - lock board after test
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/lock")

    def test_session_endpoint_returns_observer_fields_when_locked(self):
        """GET /api/boards/BOARD-1/session returns autodarts_mode, observer_browser_open, observer_state when locked"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        
        data = response.json()
        assert "board_status" in data, "Missing board_status"
        assert "autodarts_mode" in data, "Missing autodarts_mode"
        assert "observer_browser_open" in data, "Missing observer_browser_open"
        assert "observer_state" in data, "Missing observer_state"
        
        # When locked, board_status should be 'locked'
        assert data["board_status"] == "locked"
        assert data["autodarts_mode"] == "observer"
        assert data["session"] is None, "Session should be null when locked"
        print(f"Session when locked: board_status={data['board_status']}, autodarts_mode={data['autodarts_mode']}, observer_state={data['observer_state']}")

    def test_unlock_creates_session_with_credits(self):
        """POST /api/boards/BOARD-1/unlock creates session with per_game pricing"""
        response = self.api.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 3,
            "price_total": 6.0,
            "players_count": 1
        })
        assert response.status_code == 200, f"Unlock failed: {response.text}"
        
        data = response.json()
        assert data["pricing_mode"] == "per_game"
        assert data["credits_total"] == 3
        assert data["credits_remaining"] == 3
        assert data["price_total"] == 6.0
        assert data["status"] == "active"
        print(f"Session created: id={data['id']}, credits={data['credits_remaining']}, status={data['status']}")

    def test_session_after_unlock_returns_observer_status(self):
        """GET /api/boards/BOARD-1/session after unlock returns board_status=unlocked and observer fields"""
        # First unlock
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 3,
            "price_total": 6.0,
            "players_count": 1
        })
        
        # Get session
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        
        data = response.json()
        assert data["board_status"] == "unlocked", f"Expected unlocked, got {data['board_status']}"
        assert data["autodarts_mode"] == "observer"
        assert "observer_browser_open" in data
        assert "observer_state" in data
        
        # Session should have credits
        assert data["session"] is not None
        assert data["session"]["credits_remaining"] == 3
        print(f"Session after unlock: board_status={data['board_status']}, observer_browser_open={data['observer_browser_open']}, observer_state={data['observer_state']}")

    def test_overlay_returns_visible_true_when_unlocked(self):
        """GET /api/kiosk/BOARD-1/overlay returns visible=true with credits when unlocked"""
        # First unlock
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 3,
            "price_total": 6.0,
            "players_count": 1
        })
        
        # Get overlay
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert response.status_code == 200
        
        data = response.json()
        assert data["visible"] == True
        assert data["credits_remaining"] == 3
        assert data["pricing_mode"] == "per_game"
        print(f"Overlay: visible={data['visible']}, credits={data['credits_remaining']}, observer_state={data.get('observer_state')}")

    def test_lock_board_successfully(self):
        """POST /api/boards/BOARD-1/lock locks the board"""
        # First unlock
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 3,
            "price_total": 6.0,
            "players_count": 1
        })
        
        # Lock
        response = self.api.post(f"{BASE_URL}/api/boards/BOARD-1/lock")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Board locked"
        assert data["board_id"] == "BOARD-1"
        print(f"Lock response: {data}")

    def test_session_after_lock_returns_locked_status(self):
        """GET /api/boards/BOARD-1/session after lock returns board_status=locked"""
        # Unlock then lock
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 3,
            "price_total": 6.0,
            "players_count": 1
        })
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/lock")
        
        # Get session
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        
        data = response.json()
        assert data["board_status"] == "locked"
        assert data["session"] is None
        print(f"Session after lock: board_status={data['board_status']}, session={data['session']}")

    def test_end_game_returns_should_lock_false_when_credits_remain(self):
        """POST /api/kiosk/BOARD-1/end-game returns should_lock=false when credits > 0"""
        # Unlock with 3 credits
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 3,
            "price_total": 6.0,
            "players_count": 1
        })
        
        # End game
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data["should_lock"] == False, f"Expected should_lock=false, got {data['should_lock']}"
        assert data["credits_remaining"] == 3
        assert data["board_status"] == "unlocked"
        print(f"End game: should_lock={data['should_lock']}, credits_remaining={data['credits_remaining']}")

    def test_end_game_returns_should_lock_true_when_no_credits(self):
        """POST /api/kiosk/BOARD-1/end-game returns should_lock=true when credits = 0"""
        # Unlock with 0 credits
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 0,
            "price_total": 0,
            "players_count": 1
        })
        
        # End game
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game", json={})
        assert response.status_code == 200
        
        data = response.json()
        assert data["should_lock"] == True, f"Expected should_lock=true, got {data['should_lock']}"
        assert data["credits_remaining"] == 0
        assert data["board_status"] == "locked"
        print(f"End game with 0 credits: should_lock={data['should_lock']}, board_status={data['board_status']}")

    def test_observer_reset_endpoint(self):
        """POST /api/kiosk/BOARD-1/observer-reset resets the observer"""
        # Unlock first
        self.api.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", json={
            "pricing_mode": "per_game",
            "credits": 3,
            "price_total": 6.0,
            "players_count": 1
        })
        
        # Reset observer
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/observer-reset")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert data["board_id"] == "BOARD-1"
        print(f"Observer reset: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
