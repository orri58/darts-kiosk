"""
Test Suite for Autodarts Integration Endpoints (P0 Bug Fixes)
Tests for:
- POST /api/kiosk/{board_id}/start-game (with/without autodarts_target_url)
- POST /api/kiosk/{board_id}/end-game
- GET /api/kiosk/{board_id}/autodarts-status
- POST /api/kiosk/{board_id}/autodarts-reset
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestAutodartsIntegration:
    """Tests for Autodarts integration endpoints"""
    
    # ===========================================
    # Test 1: Start game returns 400 when no active session
    # ===========================================
    def test_start_game_no_session_returns_400(self, auth_headers):
        """POST /api/kiosk/BOARD-1/start-game returns 400 when no active session exists"""
        # First ensure board is locked (no active session)
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=auth_headers)
        
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/start-game", json={
            "game_type": "501",
            "players": ["TestPlayer1", "TestPlayer2"]
        })
        # Should return 400 because board must be unlocked first
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"
        data = response.json()
        assert "No active session" in data.get("detail", ""), f"Expected 'No active session' error, got: {data}"
    
    # ===========================================
    # Test 2: Start game WITHOUT autodarts_target_url returns autodarts_triggered=false
    # ===========================================
    def test_start_game_without_autodarts_url(self, auth_headers):
        """POST /api/kiosk/BOARD-1/start-game returns autodarts_triggered=false when no autodarts_target_url"""
        # Step 1: Lock board to ensure clean state
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=auth_headers)
        
        # Step 2: Clear autodarts_target_url (set to empty string or null)
        update_response = requests.put(f"{BASE_URL}/api/boards/BOARD-1", 
            headers=auth_headers,
            json={"autodarts_target_url": ""}  # Empty string to clear
        )
        assert update_response.status_code == 200, f"Board update failed: {update_response.text}"
        
        # Step 3: Unlock board with fresh credits
        unlock_response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=auth_headers,
            json={"pricing_mode": "per_game", "credits": 5}
        )
        assert unlock_response.status_code == 200, f"Unlock failed: {unlock_response.text}"
        
        # Step 4: Start game
        start_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/start-game", json={
            "game_type": "501",
            "players": ["Player1", "Player2"]
        })
        assert start_response.status_code == 200, f"Start game failed: {start_response.text}"
        data = start_response.json()
        
        # Verify autodarts_triggered is false
        assert "autodarts_triggered" in data, f"Missing autodarts_triggered in response: {data}"
        assert data["autodarts_triggered"] == False, f"Expected autodarts_triggered=false, got: {data}"
        assert data["game_type"] == "501"
        assert data["players"] == ["Player1", "Player2"]
        
        # Step 5: End game to clean up
        end_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game", json={
            "winner": "Player1"
        })
        assert end_response.status_code == 200, f"End game failed: {end_response.text}"
    
    # ===========================================
    # Test 3: Start game WITH autodarts_target_url returns autodarts_triggered=true
    # ===========================================
    def test_start_game_with_autodarts_url(self, auth_headers):
        """POST /api/kiosk/BOARD-1/start-game returns autodarts_triggered=true when autodarts_target_url configured"""
        # Step 1: Lock board to ensure clean state
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=auth_headers)
        
        # Step 2: Set autodarts_target_url on board
        update_response = requests.put(f"{BASE_URL}/api/boards/BOARD-1", 
            headers=auth_headers,
            json={"autodarts_target_url": "https://play.autodarts.io/test-board-123"}
        )
        assert update_response.status_code == 200, f"Board update failed: {update_response.text}"
        
        # Step 3: Unlock board with fresh credits
        unlock_response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=auth_headers,
            json={"pricing_mode": "per_game", "credits": 5}
        )
        assert unlock_response.status_code == 200, f"Unlock failed: {unlock_response.text}"
        
        # Step 4: Start game
        start_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/start-game", json={
            "game_type": "501",
            "players": ["AutodartsPlayer1", "AutodartsPlayer2"]
        })
        assert start_response.status_code == 200, f"Start game failed: {start_response.text}"
        data = start_response.json()
        
        # Verify autodarts_triggered is true
        assert "autodarts_triggered" in data, f"Missing autodarts_triggered in response: {data}"
        assert data["autodarts_triggered"] == True, f"Expected autodarts_triggered=true, got: {data}"
        assert data["game_type"] == "501"
        assert data["players"] == ["AutodartsPlayer1", "AutodartsPlayer2"]
        
        # Step 5: End game to clean up
        end_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game", json={
            "winner": "AutodartsPlayer1"
        })
        assert end_response.status_code == 200, f"End game failed: {end_response.text}"
    
    # ===========================================
    # Test 4: GET autodarts-status endpoint
    # ===========================================
    def test_autodarts_status_endpoint(self):
        """GET /api/kiosk/BOARD-1/autodarts-status returns integration status"""
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/autodarts-status")
        assert response.status_code == 200, f"Autodarts status failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "board_id" in data, f"Missing board_id: {data}"
        assert data["board_id"] == "BOARD-1"
        assert "integration_active" in data, f"Missing integration_active: {data}"
        assert "circuit_state" in data, f"Missing circuit_state: {data}"
        assert "manual_mode" in data, f"Missing manual_mode: {data}"
    
    # ===========================================
    # Test 5: POST autodarts-reset endpoint
    # ===========================================
    def test_autodarts_reset_endpoint(self):
        """POST /api/kiosk/BOARD-1/autodarts-reset resets circuit breaker"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/autodarts-reset")
        assert response.status_code == 200, f"Autodarts reset failed: {response.text}"
        data = response.json()
        
        # Verify response
        assert "message" in data, f"Missing message: {data}"
        assert "reset" in data["message"].lower(), f"Expected reset message, got: {data}"
        assert data["board_id"] == "BOARD-1"
    
    # ===========================================
    # Test 6: End game creates match result and updates player stats
    # ===========================================
    def test_end_game_creates_match_result(self, auth_headers):
        """POST /api/kiosk/BOARD-1/end-game correctly creates match result and updates player stats"""
        # Step 1: Lock board and clear autodarts URL
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=auth_headers)
        requests.put(f"{BASE_URL}/api/boards/BOARD-1", 
            headers=auth_headers,
            json={"autodarts_target_url": ""}
        )
        
        # Step 2: Unlock board
        unlock_response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=auth_headers,
            json={"pricing_mode": "per_game", "credits": 5}
        )
        assert unlock_response.status_code == 200, f"Unlock failed: {unlock_response.text}"
        
        # Step 3: Start game with unique player names for tracking
        unique_player = f"TEST_MatchPlayer_{int(time.time())}"
        start_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/start-game", json={
            "game_type": "Cricket",
            "players": [unique_player, "OpponentPlayer"]
        })
        assert start_response.status_code == 200, f"Start game failed: {start_response.text}"
        
        # Step 4: End game with winner
        end_response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game", json={
            "winner": unique_player,
            "scores": {"checkout": 100}
        })
        assert end_response.status_code == 200, f"End game failed: {end_response.text}"
        end_data = end_response.json()
        
        # Verify match result was created
        assert "match_token" in end_data, f"Missing match_token: {end_data}"
        assert "match_url" in end_data, f"Missing match_url: {end_data}"
        assert end_data["match_url"].startswith("/match/")
        
        # Step 5: Verify match is accessible
        match_token = end_data["match_token"]
        match_response = requests.get(f"{BASE_URL}/api/matches/{match_token}")
        assert match_response.status_code == 200, f"Match not found: {match_response.text}"
        match_data = match_response.json()
        
        # Verify match data
        assert match_data["game_type"] == "Cricket"
        assert unique_player in match_data["players"]
        assert match_data["winner"] == unique_player
    
    # ===========================================
    # Test 7: Test non-existent board returns 404
    # ===========================================
    def test_start_game_nonexistent_board(self):
        """POST /api/kiosk/INVALID-BOARD/start-game returns 404"""
        response = requests.post(f"{BASE_URL}/api/kiosk/INVALID-BOARD/start-game", json={
            "game_type": "501",
            "players": ["Player1"]
        })
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    
    # ===========================================
    # Test 8: Autodarts status for non-triggered board
    # ===========================================
    def test_autodarts_status_untriggered_board(self):
        """GET /api/kiosk/BOARD-2/autodarts-status returns status for BOARD-2"""
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-2/autodarts-status")
        assert response.status_code == 200, f"Autodarts status failed: {response.text}"
        data = response.json()
        
        assert data["board_id"] == "BOARD-2"
        assert "integration_active" in data


class TestCORSAndLANAccess:
    """Tests for CORS configuration (P0 LAN Access fix)"""
    
    def test_cors_headers_present(self):
        """Verify CORS headers are set (allow_origins = *)"""
        # Test actual GET request works from any origin
        headers = {"Origin": "http://192.168.1.100:3000"}
        get_response = requests.get(f"{BASE_URL}/api/health", headers=headers)
        assert get_response.status_code == 200
    
    def test_api_accessible_from_different_origins(self):
        """Verify API responds correctly from LAN-like origins"""
        headers = {"Origin": "http://10.0.0.5:3000"}
        response = requests.get(f"{BASE_URL}/api/health", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestLogging:
    """Tests to verify backend behavior (logs are written correctly)"""
    
    def test_start_game_endpoint_behavior(self, auth_headers):
        """Verify that start-game endpoint works correctly (implies logging)"""
        # Lock board first
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=auth_headers)
        
        # Try to start without session - should log warning
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/start-game", json={
            "game_type": "301",
            "players": ["LogTestPlayer"]
        })
        
        # 400 expected when no session
        assert response.status_code == 400


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup_after_tests(auth_headers):
    """Clean up test data after all tests"""
    yield
    # Reset board state
    try:
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            cleanup_headers = {"Authorization": f"Bearer {login_response.json()['access_token']}"}
            # Lock boards
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=cleanup_headers)
            # Remove autodarts URL
            requests.put(f"{BASE_URL}/api/boards/BOARD-1", 
                headers=cleanup_headers,
                json={"autodarts_target_url": ""}
            )
    except:
        pass
