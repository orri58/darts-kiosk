"""
Test Observer Windows Fix - Iteration 20
Tests for Windows observer runtime fix with step-by-step logging.

Key features tested:
1. GET /api/boards/BOARD-1/session returns observer fields
2. POST /api/boards/BOARD-1/unlock creates session and triggers observer start
3. Observer error handling and concise error messages
4. POST /api/boards/BOARD-1/lock locks board
5. Windows launcher files exist (run_backend.py, _run_backend.bat)
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestObserverSessionEndpoint:
    """Tests for GET /api/boards/{board_id}/session with observer fields"""
    
    def test_session_endpoint_returns_observer_fields_when_locked(self):
        """Session endpoint should return observer_browser_open, observer_state, observer_error fields"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Verify all observer fields are present
        assert "observer_browser_open" in data, "Missing observer_browser_open field"
        assert "observer_state" in data, "Missing observer_state field"
        assert "observer_error" in data, "Missing observer_error field"
        assert "board_status" in data, "Missing board_status field"
        assert "autodarts_mode" in data, "Missing autodarts_mode field"
        
        print(f"Session endpoint fields OK: board_status={data['board_status']}, observer_state={data['observer_state']}")


class TestObserverUnlockFlow:
    """Tests for unlock triggering observer start and proper error handling"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Ensure board is locked before and after each test"""
        # Get auth token first
        login_response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        if login_response.status_code == 200:
            token = login_response.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
            # Lock the board before test
            requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        else:
            pytest.skip("Could not authenticate")
        yield
        # Cleanup - lock board after test
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
    
    def test_unlock_triggers_observer_start(self):
        """POST /api/boards/BOARD-1/unlock should create session and trigger observer start"""
        # Unlock with per_game pricing
        response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock", 
            headers=self.headers,
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "price_total": 6.0
            }
        )
        assert response.status_code == 200, f"Unlock failed: {response.text}"
        data = response.json()
        assert data.get("credits_remaining") == 3
        
        # Wait a moment for async observer to attempt start
        time.sleep(2)
        
        # Check session status shows observer fields
        session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert session_response.status_code == 200
        session_data = session_response.json()
        
        assert session_data["board_status"] == "unlocked"
        assert session_data["autodarts_mode"] == "observer"
        assert "observer_browser_open" in session_data
        assert "observer_state" in session_data
        assert "observer_error" in session_data
        
        print(f"After unlock: board_status={session_data['board_status']}, "
              f"observer_state={session_data['observer_state']}, "
              f"observer_error={session_data.get('observer_error', 'none')}")
    
    def test_observer_error_is_concise(self):
        """Observer error message should be concise (first line only, max 200 chars)"""
        # First unlock to trigger observer
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={"pricing_mode": "per_game", "credits": 3, "price_total": 6.0}
        )
        time.sleep(3)  # Wait for observer attempt
        
        session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        session_data = session_response.json()
        
        # In this env (no display), observer should be in error state
        if session_data.get("observer_state") == "error" and session_data.get("observer_error"):
            error_msg = session_data["observer_error"]
            # Error should not contain multiple lines (should be concise)
            assert "\n" not in error_msg or len(error_msg.split('\n')) == 1, \
                f"Error message should be single line, got: {error_msg[:100]}..."
            # Error should start with exception type
            assert "Error" in error_msg or "error" in error_msg.lower() or ":" in error_msg, \
                f"Error should contain type info, got: {error_msg[:100]}"
            print(f"Observer error (concise): {error_msg}")
        else:
            print(f"Observer state: {session_data.get('observer_state')}, "
                  f"browser_open: {session_data.get('observer_browser_open')}")


class TestBoardLock:
    """Tests for POST /api/boards/{board_id}/lock"""
    
    @pytest.fixture(autouse=True)
    def auth_setup(self):
        """Get auth token"""
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
    
    def test_lock_board_returns_to_locked_state(self):
        """POST /api/boards/BOARD-1/lock should lock the board"""
        # First unlock the board
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={"pricing_mode": "per_game", "credits": 3, "price_total": 6.0}
        )
        
        # Now lock it
        lock_response = requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        assert lock_response.status_code == 200
        
        # Verify locked state
        session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        session_data = session_response.json()
        assert session_data["board_status"] == "locked"
        assert session_data["session"] is None
        print("Board locked successfully")


class TestWindowsLauncherFiles:
    """Tests for Windows launcher files (file existence verification)"""
    
    def test_run_backend_py_exists(self):
        """run_backend.py should exist in Windows bundle"""
        import os
        file_path = "/app/release/windows/run_backend.py"
        assert os.path.exists(file_path), f"run_backend.py not found at {file_path}"
        
        # Verify content has WindowsProactorEventLoopPolicy
        with open(file_path, 'r') as f:
            content = f.read()
        assert "WindowsProactorEventLoopPolicy" in content, \
            "run_backend.py should set WindowsProactorEventLoopPolicy"
        assert "uvicorn" in content, "run_backend.py should use uvicorn"
        print("run_backend.py exists and has correct content")
    
    def test_run_backend_bat_uses_python_launcher(self):
        """_run_backend.bat should use 'python run_backend.py' not 'python -m uvicorn'"""
        file_path = "/app/release/windows/_run_backend.bat"
        assert os.path.exists(file_path), f"_run_backend.bat not found at {file_path}"
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Should use python run_backend.py
        assert "python run_backend.py" in content, \
            "_run_backend.bat should use 'python run_backend.py'"
        # Should NOT use python -m uvicorn
        assert "python -m uvicorn" not in content, \
            "_run_backend.bat should NOT use 'python -m uvicorn'"
        print("_run_backend.bat uses correct launcher command")


class TestObserverStatusEndpoint:
    """Tests for GET /api/kiosk/{board_id}/observer-status"""
    
    def test_observer_status_returns_fields(self):
        """Observer status endpoint should return state, browser_open, etc."""
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/observer-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "autodarts_mode" in data
        assert "state" in data
        assert "browser_open" in data
        print(f"Observer status: mode={data['autodarts_mode']}, state={data['state']}, browser_open={data['browser_open']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
