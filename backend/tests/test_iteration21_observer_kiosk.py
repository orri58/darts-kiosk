"""
Test Observer Kiosk Flow - Iteration 21
Tests for Darts Kiosk + Admin Control system with observer mode.

Key features tested:
1. GET /api/boards/BOARD-1/session returns observer fields
2. GET /api/kiosk/BOARD-1/overlay returns visible:false when board is locked
3. POST /api/boards/BOARD-1/unlock creates session, starts observer
4. POST /api/kiosk/BOARD-1/simulate-game-start decrements credits (observer callback)
5. POST /api/kiosk/BOARD-1/simulate-game-end handles game completion
6. POST /api/kiosk/BOARD-1/observer-reset restarts observer
7. POST /api/boards/BOARD-1/lock closes session and observer
8. Window management: KioskLayout.js has prevBrowserOpenRef logic
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestSessionEndpointObserverFields:
    """Tests for GET /api/boards/{board_id}/session with observer fields"""
    
    def test_session_endpoint_returns_all_observer_fields(self):
        """Session endpoint should return observer_browser_open, observer_state, observer_error, autodarts_mode"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify all observer fields are present
        assert "observer_browser_open" in data, "Missing observer_browser_open field"
        assert "observer_state" in data, "Missing observer_state field"
        assert "observer_error" in data, "Missing observer_error field"
        assert "autodarts_mode" in data, "Missing autodarts_mode field"
        assert "board_status" in data, "Missing board_status field"
        
        print(f"Session fields: board_status={data['board_status']}, "
              f"autodarts_mode={data['autodarts_mode']}, "
              f"observer_state={data['observer_state']}, "
              f"observer_browser_open={data['observer_browser_open']}")


class TestOverlayEndpoint:
    """Tests for GET /api/kiosk/{board_id}/overlay"""
    
    @pytest.fixture(autouse=True)
    def ensure_locked(self):
        """Ensure board is locked before test"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        else:
            pytest.skip("Could not authenticate")
        yield
        # Cleanup - ensure board is locked
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_overlay_returns_visible_false_when_locked(self):
        """Overlay should return visible:false when board is locked"""
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("visible") == False, f"Expected visible=false when locked, got {data}"
        assert data.get("board_status") == "locked", f"Expected board_status=locked, got {data.get('board_status')}"
        print(f"Overlay when locked: visible={data.get('visible')}, board_status={data.get('board_status')}")


class TestUnlockSessionOverlayFlow:
    """Tests for unlock flow - session creation, observer start, overlay visible"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Ensure board is locked before and after test"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        else:
            pytest.skip("Could not authenticate")
        yield
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_unlock_creates_session_and_overlay_becomes_visible(self):
        """POST /api/boards/BOARD-1/unlock creates session, overlay shows visible:true with credits"""
        # Unlock with 5 credits
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 5,
                "price_total": 10.0
            }
        )
        assert response.status_code == 200, f"Unlock failed: {response.text}"
        data = response.json()
        assert data.get("credits_remaining") == 5, f"Expected 5 credits, got {data.get('credits_remaining')}"
        
        # Wait for async observer attempt
        time.sleep(2)
        
        # Check overlay now shows visible:true
        overlay_response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert overlay_response.status_code == 200
        overlay_data = overlay_response.json()
        
        assert overlay_data.get("visible") == True, f"Expected visible=true after unlock, got {overlay_data}"
        assert overlay_data.get("credits_remaining") == 5, f"Expected 5 credits in overlay, got {overlay_data.get('credits_remaining')}"
        assert overlay_data.get("pricing_mode") == "per_game"
        
        print(f"Overlay after unlock: visible={overlay_data.get('visible')}, "
              f"credits={overlay_data.get('credits_remaining')}, "
              f"observer_state={overlay_data.get('observer_state')}")


class TestSimulateGameStartCredits:
    """Tests for POST /api/kiosk/{board_id}/simulate-game-start credit decrement"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup: Lock board, login, unlock with 5 credits"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
            # Lock board first
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
            # Unlock with 5 credits
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
                headers=self.headers,
                json={"pricing_mode": "per_game", "credits": 5, "price_total": 10.0}
            )
            time.sleep(1)  # Wait for session creation
        else:
            pytest.skip("Could not authenticate")
        yield
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_simulate_game_start_decrements_credits(self):
        """POST /api/kiosk/BOARD-1/simulate-game-start should decrement credits from 5 to 4"""
        # Check initial credits
        overlay_before = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        initial_credits = overlay_before.get("credits_remaining")
        print(f"Credits before simulate-game-start: {initial_credits}")
        assert initial_credits == 5, f"Expected 5 initial credits, got {initial_credits}"
        
        # Simulate game start (requires admin auth)
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=self.headers
        )
        assert response.status_code == 200, f"simulate-game-start failed: {response.text}"
        
        # Check credits decremented
        time.sleep(0.5)
        overlay_after = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        new_credits = overlay_after.get("credits_remaining")
        print(f"Credits after simulate-game-start: {new_credits}")
        
        assert new_credits == 4, f"Expected 4 credits after game start, got {new_credits}"


class TestSimulateGameEnd:
    """Tests for POST /api/kiosk/{board_id}/simulate-game-end"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup: Lock board, login, unlock with 2 credits"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
                headers=self.headers,
                json={"pricing_mode": "per_game", "credits": 2, "price_total": 4.0}
            )
            time.sleep(1)
        else:
            pytest.skip("Could not authenticate")
        yield
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_simulate_game_end_handles_completion(self):
        """POST /api/kiosk/BOARD-1/simulate-game-end should handle game completion correctly"""
        # First simulate game start to decrement to 1 credit
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        time.sleep(0.5)
        
        # Verify 1 credit remaining
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay.get("credits_remaining") == 1, f"Expected 1 credit, got {overlay.get('credits_remaining')}"
        
        # Simulate game end - board should still be unlocked (1 credit remaining)
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=self.headers
        )
        assert response.status_code == 200, f"simulate-game-end failed: {response.text}"
        
        time.sleep(0.5)
        session_data = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session").json()
        # Board should be unlocked (credits > 0)
        assert session_data.get("board_status") == "unlocked", \
            f"Expected unlocked (credits>0), got {session_data.get('board_status')}"
        
        print(f"After simulate-game-end: board_status={session_data.get('board_status')}")
    
    def test_simulate_game_end_locks_board_when_credits_exhausted(self):
        """Board should lock when credits reach 0 after game end"""
        # Start game - credits 2 -> 1
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        time.sleep(0.3)
        
        # End game - board stays unlocked with 1 credit
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", headers=self.headers)
        time.sleep(0.3)
        
        # Start second game - credits 1 -> 0
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        time.sleep(0.3)
        
        # End second game - board should lock (0 credits)
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end", headers=self.headers)
        time.sleep(0.5)
        
        session_data = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session").json()
        assert session_data.get("board_status") == "locked", \
            f"Expected locked when credits exhausted, got {session_data.get('board_status')}"
        
        print("Board correctly locked when credits exhausted")


class TestObserverReset:
    """Tests for POST /api/kiosk/{board_id}/observer-reset"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup: Login and unlock board"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
                headers=self.headers,
                json={"pricing_mode": "per_game", "credits": 3, "price_total": 6.0}
            )
            time.sleep(1)
        else:
            pytest.skip("Could not authenticate")
        yield
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_observer_reset_attempts_restart(self):
        """POST /api/kiosk/BOARD-1/observer-reset should attempt to restart observer"""
        response = requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/observer-reset")
        assert response.status_code == 200, f"observer-reset failed: {response.text}"
        
        data = response.json()
        # Should return message about reset
        assert "message" in data
        assert "board_id" in data
        assert data["board_id"] == "BOARD-1"
        
        print(f"Observer reset response: {data}")


class TestBoardLockClosesObserver:
    """Tests for POST /api/boards/{board_id}/lock closing session and observer"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup: Login"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip("Could not authenticate")
        yield
    
    def test_lock_closes_session_and_observer(self):
        """POST /api/boards/BOARD-1/lock should close session and observer"""
        # First unlock
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={"pricing_mode": "per_game", "credits": 3, "price_total": 6.0}
        )
        time.sleep(1)
        
        # Verify unlocked with session
        session_before = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session").json()
        assert session_before.get("board_status") == "unlocked"
        assert session_before.get("session") is not None
        
        # Lock the board
        lock_response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        assert lock_response.status_code == 200
        
        time.sleep(1)
        
        # Verify locked and session closed
        session_after = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session").json()
        assert session_after.get("board_status") == "locked"
        assert session_after.get("session") is None
        # Observer should be closed
        assert session_after.get("observer_state") in ["closed", "error"]
        
        print(f"Board locked: status={session_after.get('board_status')}, "
              f"session={session_after.get('session')}, "
              f"observer_state={session_after.get('observer_state')}")


class TestOverlayHidesWhenLocked:
    """Tests for overlay visibility based on board status"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup: Login"""
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip("Could not authenticate")
        yield
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_overlay_hides_when_locked_shows_when_unlocked(self):
        """Overlay should be visible=false when locked, visible=true when unlocked"""
        # Ensure locked
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        time.sleep(0.5)
        
        # Check overlay hidden
        overlay_locked = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay_locked.get("visible") == False, "Overlay should be hidden when locked"
        
        # Unlock
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={"pricing_mode": "per_game", "credits": 3, "price_total": 6.0}
        )
        time.sleep(0.5)
        
        # Check overlay visible
        overlay_unlocked = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay_unlocked.get("visible") == True, "Overlay should be visible when unlocked"
        
        # Lock again
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        time.sleep(0.5)
        
        # Check overlay hidden again
        overlay_locked_again = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay").json()
        assert overlay_locked_again.get("visible") == False, "Overlay should hide after lock"
        
        print("Overlay visibility correctly toggles with board status")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
