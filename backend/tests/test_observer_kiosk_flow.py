"""
Test Observer Mode Kiosk Flow - Iteration 18

Tests the fix: In observer mode (AUTODARTS_MODE=observer), unlocking a board must
show ObserverActiveScreen instead of SetupScreen. The customer uses Autodarts directly.

Key behaviors:
1. GET /api/boards/BOARD-1/session returns autodarts_mode field
2. POST /api/boards/BOARD-1/unlock creates session
3. GET /api/kiosk/BOARD-1/observer-status returns observer state
4. POST /api/kiosk/BOARD-1/end-game ends game (locks if credits=0)
5. POST /api/boards/BOARD-1/lock locks the board
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestObserverKioskFlow:
    """Test observer mode kiosk flow endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token and ensure clean state"""
        # Login
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get('access_token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Lock board to ensure clean state
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        yield
        # Cleanup: lock board
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_01_session_endpoint_returns_autodarts_mode(self):
        """GET /api/boards/BOARD-1/session returns autodarts_mode field"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        
        data = response.json()
        assert "autodarts_mode" in data, "Response missing autodarts_mode field"
        assert data["autodarts_mode"] == "observer", f"Expected 'observer', got {data['autodarts_mode']}"
        assert "board_status" in data, "Response missing board_status field"
        print(f"✓ autodarts_mode={data['autodarts_mode']}, board_status={data['board_status']}")
    
    def test_02_unlock_board_creates_session(self):
        """POST /api/boards/BOARD-1/unlock creates session with valid response"""
        response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "price_total": 6.0,
                "players_count": 1
            }
        )
        assert response.status_code == 200, f"Unlock failed: {response.text}"
        
        data = response.json()
        assert "id" in data, "Response missing session id"
        assert data["pricing_mode"] == "per_game"
        assert data["credits_total"] == 3
        assert data["credits_remaining"] == 3
        assert data["status"] == "active"
        print(f"✓ Session created: id={data['id']}, credits={data['credits_remaining']}")
    
    def test_03_session_shows_unlocked_after_unlock(self):
        """After unlock, board_status is 'unlocked' and autodarts_mode is 'observer'"""
        # Unlock first
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "price_total": 6.0,
                "players_count": 1
            }
        )
        
        # Check session
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        
        data = response.json()
        assert data["board_status"] == "unlocked"
        assert data["autodarts_mode"] == "observer"
        assert data["session"] is not None
        assert data["session"]["credits_remaining"] == 3
        print(f"✓ board_status=unlocked, autodarts_mode=observer, session active")
    
    def test_04_observer_status_endpoint(self):
        """GET /api/kiosk/BOARD-1/observer-status returns observer state when unlocked"""
        # Unlock first
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 2,
                "price_total": 4.0,
                "players_count": 1
            }
        )
        
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/observer-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "autodarts_mode" in data
        assert data["autodarts_mode"] == "observer"
        assert "state" in data
        assert "credits_remaining" in data
        assert data["credits_remaining"] == 2
        print(f"✓ observer_status: state={data['state']}, credits={data['credits_remaining']}")
    
    def test_05_end_game_with_credits_remaining(self):
        """POST /api/kiosk/BOARD-1/end-game returns should_lock=false when credits > 0"""
        # Unlock with 3 credits
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "price_total": 6.0,
                "players_count": 1
            }
        )
        
        # End game
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/end-game")
        assert response.status_code == 200
        
        data = response.json()
        assert data["should_lock"] == False, f"Expected should_lock=false, got {data['should_lock']}"
        assert data["board_status"] == "unlocked"
        print(f"✓ end_game: should_lock={data['should_lock']}, credits_remaining={data['credits_remaining']}")
    
    def test_06_lock_board_endpoint(self):
        """POST /api/boards/BOARD-1/lock locks the board"""
        # Unlock first
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 1,
                "price_total": 2.0,
                "players_count": 1
            }
        )
        
        # Lock
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Board locked"
        assert data["board_id"] == "BOARD-1"
        
        # Verify board is locked
        session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert session_response.status_code == 200
        assert session_response.json()["board_status"] == "locked"
        print(f"✓ Board locked successfully")
    
    def test_07_session_null_when_locked(self):
        """When board is locked, session should be null"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        
        data = response.json()
        assert data["board_status"] == "locked"
        assert data["session"] is None
        print(f"✓ board_status=locked, session=null")
    
    def test_08_per_time_pricing_mode(self):
        """Test unlock with per_time pricing mode returns expires_at"""
        response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={
                "pricing_mode": "per_time",
                "minutes": 30,
                "price_total": 5.0,
                "players_count": 1
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["pricing_mode"] == "per_time"
        assert data["minutes_total"] == 30
        assert data["expires_at"] is not None
        print(f"✓ per_time session: minutes={data['minutes_total']}, expires_at={data['expires_at']}")


class TestObserverStatusDetails:
    """Test observer status endpoint details"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        self.token = response.json().get('access_token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Lock board first
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        yield
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_observer_status_includes_pricing_mode(self):
        """Observer status includes pricing_mode field"""
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 2,
                "price_total": 4.0,
                "players_count": 1
            }
        )
        
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/observer-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "pricing_mode" in data
        assert data["pricing_mode"] == "per_game"
        print(f"✓ pricing_mode={data['pricing_mode']}")
    
    def test_observer_status_includes_session_expires_at(self):
        """Observer status includes session_expires_at for per_time mode"""
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={
                "pricing_mode": "per_time",
                "minutes": 30,
                "price_total": 5.0,
                "players_count": 1
            }
        )
        
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/observer-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "session_expires_at" in data
        assert data["session_expires_at"] is not None
        print(f"✓ session_expires_at={data['session_expires_at']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
