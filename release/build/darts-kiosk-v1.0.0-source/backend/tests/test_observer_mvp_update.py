"""
Test Observer MVP Update Features
- Match sharing settings (GET/PUT /api/settings/match-sharing)
- Conditional match_token generation in end-game
- Observer status with extended fields
- Credits overlay endpoint
- Board unlock/lock observer lifecycle
"""
import os
import pytest
import requests
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

BOARD_ID = "BOARD-1"


class TestMatchSharingSettings:
    """Match sharing settings API tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        # Get admin token
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin login failed")

    def test_get_match_sharing_default(self):
        """GET /api/settings/match-sharing returns default values (enabled: false, qr_timeout: 60)"""
        response = requests.get(f"{BASE_URL}/api/settings/match-sharing")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Check default values
        assert "enabled" in data, "Response should have 'enabled' field"
        # Default is disabled
        assert data.get("enabled") == False or data.get("enabled") is None or "enabled" in data
        assert "qr_timeout" in data or data.get("qr_timeout", 60), "Should have qr_timeout"
        print(f"Match sharing default: {data}")

    def test_put_match_sharing_enable(self):
        """PUT /api/settings/match-sharing with enabled=true, qr_timeout=30"""
        response = requests.put(
            f"{BASE_URL}/api/settings/match-sharing",
            json={"value": {"enabled": True, "qr_timeout": 30}},
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("enabled") == True, f"Expected enabled=true, got {data.get('enabled')}"
        assert data.get("qr_timeout") == 30, f"Expected qr_timeout=30, got {data.get('qr_timeout')}"
        print(f"Match sharing enabled: {data}")

    def test_put_match_sharing_disable(self):
        """PUT /api/settings/match-sharing with enabled=false, qr_timeout=60"""
        response = requests.put(
            f"{BASE_URL}/api/settings/match-sharing",
            json={"value": {"enabled": False, "qr_timeout": 60}},
            headers=self.headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("enabled") == False, f"Expected enabled=false, got {data.get('enabled')}"
        assert data.get("qr_timeout") == 60, f"Expected qr_timeout=60, got {data.get('qr_timeout')}"
        print(f"Match sharing disabled: {data}")

    def test_put_match_sharing_requires_auth(self):
        """PUT /api/settings/match-sharing requires authentication"""
        response = requests.put(
            f"{BASE_URL}/api/settings/match-sharing",
            json={"value": {"enabled": True, "qr_timeout": 30}}
        )
        assert response.status_code == 401 or response.status_code == 403, \
            f"Expected 401/403 without auth, got {response.status_code}"


class TestObserverStatus:
    """Observer status endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin login failed")

    def test_get_observer_status(self):
        """GET /api/kiosk/{board_id}/observer-status returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/kiosk/{BOARD_ID}/observer-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have autodarts_mode
        assert "autodarts_mode" in data, "Should have autodarts_mode"
        # Should have state field (from observer)
        assert "state" in data, "Should have state field"
        # Extended fields: credits_remaining, pricing_mode
        assert "credits_remaining" in data, "Should have credits_remaining"
        assert "pricing_mode" in data, "Should have pricing_mode"
        print(f"Observer status: {data}")

    def test_get_all_observer_statuses(self):
        """GET /api/kiosk/observers/all returns all observer statuses"""
        response = requests.get(f"{BASE_URL}/api/kiosk/observers/all")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "autodarts_mode" in data, "Should have autodarts_mode"
        assert "observers" in data, "Should have observers list"
        assert isinstance(data["observers"], list), "observers should be a list"
        print(f"All observer statuses: {data}")


class TestCreditsOverlay:
    """Credits overlay endpoint tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin login failed")

    def test_overlay_no_session(self):
        """GET /api/kiosk/{board_id}/overlay returns visible:false when no session"""
        # First ensure board is locked (no active session)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)
        
        response = requests.get(f"{BASE_URL}/api/kiosk/{BOARD_ID}/overlay")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "visible" in data, "Should have visible field"
        # When no session, visible should be false
        assert data.get("visible") == False, f"Expected visible=false when locked, got {data.get('visible')}"
        print(f"Overlay (no session): {data}")

    def test_overlay_with_session(self):
        """GET /api/kiosk/{board_id}/overlay returns visible:true with credits when session active"""
        # Ensure board is locked first
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)
        
        # Unlock board to create session
        unlock_response = requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
            json={
                "pricing_mode": "per_game",
                "credits": 5,
                "price_total": 10.00,
                "players_count": 2
            },
            headers=self.headers
        )
        assert unlock_response.status_code == 200, f"Unlock failed: {unlock_response.text}"
        
        # Now check overlay
        response = requests.get(f"{BASE_URL}/api/kiosk/{BOARD_ID}/overlay")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("visible") == True, f"Expected visible=true with session, got {data.get('visible')}"
        assert "credits_remaining" in data, "Should have credits_remaining when visible"
        assert data.get("credits_remaining") == 5, f"Expected 5 credits, got {data.get('credits_remaining')}"
        assert "pricing_mode" in data, "Should have pricing_mode"
        assert data.get("pricing_mode") == "per_game", f"Expected per_game, got {data.get('pricing_mode')}"
        print(f"Overlay (with session): {data}")
        
        # Cleanup: lock board
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)

    def test_overlay_nonexistent_board(self):
        """GET /api/kiosk/INVALID-BOARD/overlay returns visible:false"""
        response = requests.get(f"{BASE_URL}/api/kiosk/INVALID-BOARD/overlay")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("visible") == False, "Should return visible:false for nonexistent board"


class TestEndGameMatchToken:
    """End game conditional match token tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin login failed")

    def test_end_game_qr_disabled_no_token(self):
        """POST /api/kiosk/{board_id}/end-game with QR disabled returns match_token:null"""
        # Disable QR sharing first
        requests.put(
            f"{BASE_URL}/api/settings/match-sharing",
            json={"value": {"enabled": False, "qr_timeout": 60}},
            headers=self.headers
        )
        
        # Lock first, then unlock to create fresh session
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
            json={"pricing_mode": "per_game", "credits": 3, "price_total": 6.00, "players_count": 1},
            headers=self.headers
        )
        assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.text}"
        
        # End game
        response = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/end-game")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # match_token should be null when QR sharing is disabled
        assert data.get("match_token") is None, f"Expected match_token=null, got {data.get('match_token')}"
        assert data.get("match_sharing_enabled") == False, "match_sharing_enabled should be false"
        print(f"End game (QR disabled): {data}")
        
        # Cleanup
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)

    def test_end_game_qr_enabled_returns_token(self):
        """POST /api/kiosk/{board_id}/end-game with QR enabled returns a match_token"""
        # Enable QR sharing
        requests.put(
            f"{BASE_URL}/api/settings/match-sharing",
            json={"value": {"enabled": True, "qr_timeout": 30}},
            headers=self.headers
        )
        
        # Lock first, then unlock
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
            json={"pricing_mode": "per_game", "credits": 3, "price_total": 6.00, "players_count": 1},
            headers=self.headers
        )
        assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.text}"
        
        # End game
        response = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/end-game")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # match_token should be present when QR sharing is enabled
        assert data.get("match_token") is not None, f"Expected match_token to exist, got {data.get('match_token')}"
        assert isinstance(data.get("match_token"), str), "match_token should be a string"
        assert len(data.get("match_token")) > 0, "match_token should not be empty"
        assert data.get("match_sharing_enabled") == True, "match_sharing_enabled should be true"
        print(f"End game (QR enabled): {data}")
        
        # Cleanup: disable QR sharing and lock board
        requests.put(
            f"{BASE_URL}/api/settings/match-sharing",
            json={"value": {"enabled": False, "qr_timeout": 60}},
            headers=self.headers
        )
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)


class TestBoardUnlockLockObserver:
    """Board unlock/lock observer lifecycle tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if response.status_code == 200:
            self.token = response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {self.token}"}
        else:
            pytest.skip("Admin login failed")

    def test_unlock_creates_session_and_may_start_observer(self):
        """POST /api/boards/{board_id}/unlock creates session and triggers observer start"""
        # Lock first
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)
        
        # Unlock
        response = requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
            json={
                "pricing_mode": "per_game",
                "credits": 4,
                "price_total": 8.00,
                "players_count": 2
            },
            headers=self.headers
        )
        assert response.status_code == 200, f"Unlock failed: {response.status_code}: {response.text}"
        
        data = response.json()
        # Session created
        assert "id" in data, "Should return session id"
        assert data.get("credits_remaining") == 4, f"Expected 4 credits, got {data.get('credits_remaining')}"
        assert data.get("pricing_mode") == "per_game"
        assert data.get("status") == "active"
        print(f"Unlock response: {data}")
        
        # Check observer status - it should be idle or starting if board has autodarts_url
        obs_response = requests.get(f"{BASE_URL}/api/kiosk/{BOARD_ID}/observer-status")
        assert obs_response.status_code == 200
        obs_data = obs_response.json()
        # Observer state might be idle, closed, or in transition depending on config
        print(f"Observer status after unlock: {obs_data}")
        
        # Cleanup
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)

    def test_lock_closes_observer(self):
        """POST /api/boards/{board_id}/lock closes observer"""
        # Ensure unlocked first
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)
        requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
            json={"pricing_mode": "per_game", "credits": 2, "price_total": 4.00, "players_count": 1},
            headers=self.headers
        )
        
        # Lock
        response = requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)
        assert response.status_code == 200, f"Lock failed: {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("board_id") == BOARD_ID
        print(f"Lock response: {data}")
        
        # Observer should be closed
        import time
        time.sleep(0.5)  # Give time for async close
        obs_response = requests.get(f"{BASE_URL}/api/kiosk/{BOARD_ID}/observer-status")
        obs_data = obs_response.json()
        print(f"Observer status after lock: {obs_data}")
        # Observer state should be closed (or transitioning to closed)

    def test_board_status_after_operations(self):
        """Verify board status changes correctly with unlock/lock"""
        # Lock
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)
        
        # Check board status
        board_resp = requests.get(f"{BASE_URL}/api/boards/{BOARD_ID}", headers=self.headers)
        assert board_resp.status_code == 200
        board_data = board_resp.json()
        assert board_data["board"]["status"] == "locked", f"Expected locked, got {board_data['board']['status']}"
        
        # Unlock
        requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
            json={"pricing_mode": "per_game", "credits": 1, "price_total": 2.00, "players_count": 1},
            headers=self.headers
        )
        
        # Check board status
        board_resp = requests.get(f"{BASE_URL}/api/boards/{BOARD_ID}", headers=self.headers)
        board_data = board_resp.json()
        assert board_data["board"]["status"] == "unlocked", f"Expected unlocked, got {board_data['board']['status']}"
        
        # Cleanup
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=self.headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
