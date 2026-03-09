"""
Test Credits Overlay Feature - Iteration 15

Tests the credits overlay functionality:
- Overlay visibility based on board status (locked/unlocked)
- Credits decrement via simulate-game-start
- LETZTES SPIEL warning when credits hit 0
- Auto-lock when last game ends
- Overlay config toggle (enabled/disabled)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Login and get admin token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin12345"
    })
    assert response.status_code == 200, f"Admin login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")

@pytest.fixture
def auth_headers(admin_token):
    """Auth headers for admin requests"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestOverlayBasicState:
    """Test overlay endpoint returns correct visibility based on board state"""
    
    def test_overlay_locked_board_not_visible(self, auth_headers):
        """When board is locked, overlay should return visible=false"""
        # First lock the board to ensure clean state
        lock_res = requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=auth_headers)
        assert lock_res.status_code == 200, f"Lock failed: {lock_res.text}"
        
        # Now check overlay
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert response.status_code == 200
        data = response.json()
        assert data.get("visible") == False, f"Expected visible=false when locked, got: {data}"
    
    def test_unlock_board_with_credits(self, auth_headers):
        """Unlock board with 3 credits, verify overlay shows visible=true"""
        # Unlock with 3 credits
        unlock_res = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            json={"credits": 3, "pricing_mode": "per_game"},
            headers=auth_headers
        )
        assert unlock_res.status_code == 200, f"Unlock failed: {unlock_res.text}"
        
        # Check overlay now shows visible=true
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert response.status_code == 200
        data = response.json()
        assert data.get("visible") == True, f"Expected visible=true after unlock, got: {data}"
        assert data.get("credits_remaining") == 3, f"Expected 3 credits, got: {data.get('credits_remaining')}"
        assert data.get("is_last_game") == False, "Should not be last game with 3 credits"


class TestSimulateGameCycle:
    """Test full game simulation cycle with credit decrement"""
    
    def test_setup_fresh_session(self, auth_headers):
        """Lock and unlock board with 3 credits for fresh test state"""
        # Lock first
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=auth_headers)
        
        # Unlock with 3 credits
        unlock_res = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            json={"credits": 3, "pricing_mode": "per_game"},
            headers=auth_headers
        )
        assert unlock_res.status_code == 200, f"Unlock failed: {unlock_res.text}"
        
        # Verify initial state
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("credits_remaining") == 3, f"Expected 3 credits at start, got: {overlay}"
    
    def test_simulate_game_start_decrements_credit(self, auth_headers):
        """Simulate game start should decrement credits from 3 to 2"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=auth_headers)
        assert response.status_code == 200, f"Simulate start failed: {response.text}"
        
        # Verify credit decremented
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("credits_remaining") == 2, f"Expected 2 credits after first game start, got: {overlay}"
        assert overlay.get("is_last_game") == False, "Should not be last game with 2 credits"
    
    def test_simulate_game_end_unlocks_board(self, auth_headers):
        """Simulate game end should keep board unlocked (credits > 0)"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", headers=auth_headers)
        assert response.status_code == 200, f"Simulate end failed: {response.text}"
        
        # Board should still be unlocked
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("visible") == True, "Overlay should remain visible"
        assert overlay.get("credits_remaining") == 2, "Credits should remain at 2"
    
    def test_second_game_cycle(self, auth_headers):
        """Second game start decrements to 1 credit"""
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=auth_headers)
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("credits_remaining") == 1, f"Expected 1 credit after second game start, got: {overlay}"
        
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", headers=auth_headers)
    
    def test_third_game_start_triggers_last_game(self, auth_headers):
        """Third game start should trigger is_last_game=true (credits=0)"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=auth_headers)
        assert response.status_code == 200
        
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("credits_remaining") == 0, f"Expected 0 credits after third game start, got: {overlay}"
        assert overlay.get("is_last_game") == True, f"Should be last game with 0 credits, got: {overlay}"
    
    def test_last_game_end_locks_board(self, auth_headers):
        """When last game ends, board should auto-lock and overlay hide"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", headers=auth_headers)
        assert response.status_code == 200
        
        # Small delay for async processing
        import time
        time.sleep(0.5)
        
        # Board should now be locked
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("visible") == False, f"Overlay should be hidden after last game ends, got: {overlay}"


class TestOverlayConfigToggle:
    """Test overlay enabled/disabled via settings"""
    
    def test_setup_unlocked_board(self, auth_headers):
        """Setup: unlock board for testing"""
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            json={"credits": 3, "pricing_mode": "per_game"},
            headers=auth_headers
        )
        
    def test_overlay_visible_when_enabled(self, auth_headers):
        """With overlay enabled, unlocked board should show overlay"""
        # Ensure overlay is enabled
        requests.put(f"{BASE_URL}/api/settings/overlay", 
            json={"value": {"enabled": True}},
            headers=auth_headers
        )
        
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("visible") == True, f"Overlay should be visible when enabled, got: {overlay}"
    
    def test_disable_overlay_hides_even_when_unlocked(self, auth_headers):
        """Disabling overlay should hide it even if board is unlocked"""
        # Disable overlay
        response = requests.put(f"{BASE_URL}/api/settings/overlay", 
            json={"value": {"enabled": False}},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to disable overlay: {response.text}"
        
        # Overlay should now be hidden with reason=disabled
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("visible") == False, f"Overlay should be hidden when disabled, got: {overlay}"
        assert overlay.get("reason") == "disabled", f"Expected reason='disabled', got: {overlay}"
    
    def test_reenable_overlay(self, auth_headers):
        """Re-enabling overlay should show it again"""
        response = requests.put(f"{BASE_URL}/api/settings/overlay", 
            json={"value": {"enabled": True}},
            headers=auth_headers
        )
        assert response.status_code == 200
        
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("visible") == True, f"Overlay should be visible again after re-enable, got: {overlay}"


class TestOverlayEndpointAuth:
    """Test endpoint auth requirements"""
    
    def test_overlay_get_no_auth_required(self):
        """GET overlay should work without auth (public for display)"""
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert response.status_code == 200
    
    def test_simulate_start_requires_auth(self):
        """Simulate game start requires admin auth"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start")
        assert response.status_code in [401, 403], f"Expected auth error, got: {response.status_code}"
    
    def test_simulate_end_requires_auth(self):
        """Simulate game end requires admin auth"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end")
        assert response.status_code in [401, 403], f"Expected auth error, got: {response.status_code}"
    
    def test_overlay_settings_requires_auth(self):
        """PUT overlay settings requires admin auth"""
        response = requests.put(f"{BASE_URL}/api/settings/overlay", 
            json={"value": {"enabled": True}}
        )
        assert response.status_code in [401, 403], f"Expected auth error, got: {response.status_code}"


class TestOverlayDataFields:
    """Verify overlay endpoint returns all expected fields"""
    
    def test_overlay_response_structure(self, auth_headers):
        """Verify overlay response includes all expected fields"""
        # Ensure board is unlocked
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            json={"credits": 2, "pricing_mode": "per_game"},
            headers=auth_headers
        )
        
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert response.status_code == 200
        data = response.json()
        
        # Check expected fields
        assert "visible" in data, "Missing 'visible' field"
        assert data.get("visible") == True
        assert "credits_remaining" in data, "Missing 'credits_remaining' field"
        assert "is_last_game" in data, "Missing 'is_last_game' field"
        assert "pricing_mode" in data, "Missing 'pricing_mode' field"
        assert "board_name" in data, "Missing 'board_name' field"
        assert "board_status" in data, "Missing 'board_status' field"


class TestCleanup:
    """Cleanup after tests"""
    
    def test_cleanup_enable_overlay(self, auth_headers):
        """Re-enable overlay after tests"""
        requests.put(f"{BASE_URL}/api/settings/overlay", 
            json={"value": {"enabled": True}},
            headers=auth_headers
        )
        
    def test_cleanup_unlock_board(self, auth_headers):
        """Leave board in unlocked state with 3 credits for frontend testing"""
        # First lock it (may fail if already locked, that's ok)
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=auth_headers)
        
        # Now unlock with fresh credits
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            json={"credits": 3, "pricing_mode": "per_game"},
            headers=auth_headers
        )
        assert response.status_code == 200
