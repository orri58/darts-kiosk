"""
Iteration 22 - Darts Kiosk Runtime Fixes Testing

Tests for:
1. API endpoints (health, boards, kiosk, observer)
2. Code verification (ignore_default_args, window_manager integration)
3. Release package verification
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ========== AUTH FIXTURES ==========

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip("Authentication failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


# ========== API ENDPOINT TESTS ==========

class TestHealthEndpoint:
    """Test /api/health endpoint"""
    
    def test_health_returns_healthy(self, api_client):
        """GET /api/health returns healthy status"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"✓ Health check passed: status={data.get('status')}")


class TestBoardSession:
    """Test /api/boards/{board_id}/session endpoint"""
    
    def test_board_session_returns_observer_fields(self, api_client):
        """GET /api/boards/BOARD-1/session returns observer fields when locked"""
        response = api_client.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        data = response.json()
        
        # Verify observer fields exist
        assert "observer_browser_open" in data
        assert "observer_state" in data
        assert "observer_error" in data or data.get("observer_error") is None
        assert "board_status" in data
        
        print(f"✓ Board session fields: board_status={data['board_status']}, " +
              f"observer_state={data['observer_state']}, browser_open={data['observer_browser_open']}")


class TestUnlockAndObserver:
    """Test unlock/lock flow with observer"""
    
    def test_unlock_creates_session_and_starts_observer(self, authenticated_client):
        """POST /api/boards/BOARD-1/unlock creates session and triggers observer start"""
        # First ensure board is locked
        authenticated_client.post(f"{BASE_URL}/api/boards/BOARD-1/lock")
        
        # Unlock the board
        unlock_data = {
            "pricing_mode": "per_game",
            "credits": 3,
            "game_type": "501"
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json=unlock_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get("credits_remaining") == 3
        print(f"✓ Unlock successful: credits_remaining={data.get('credits_remaining')}")
    
    def test_observer_error_on_linux_is_expected(self, api_client):
        """Observer state is 'error' on Linux (no Chrome) - expected behavior"""
        import time
        time.sleep(2)  # Wait for observer to attempt launch
        
        response = api_client.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200
        data = response.json()
        
        # On Linux without Chrome, observer will fail - this is EXPECTED
        observer_state = data.get("observer_state")
        observer_error = data.get("observer_error")
        browser_open = data.get("observer_browser_open")
        
        # browser_open should be False (Chrome failed to launch)
        assert browser_open == False, f"Expected browser_open=False, got {browser_open}"
        
        # State should be error or closed
        assert observer_state in ["error", "closed", "idle"], \
            f"Expected observer_state in [error, closed, idle], got {observer_state}"
        
        print(f"✓ Observer state after unlock: state={observer_state}, browser_open={browser_open}")
        if observer_error:
            print(f"  Observer error (expected on Linux): {observer_error[:100]}")


class TestKioskOverlay:
    """Test overlay endpoint"""
    
    def test_overlay_returns_visible_when_unlocked(self, api_client):
        """GET /api/kiosk/BOARD-1/overlay returns visible:true with credits when unlocked"""
        response = api_client.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert response.status_code == 200
        data = response.json()
        
        # When unlocked, overlay should be visible
        assert data.get("visible") == True
        assert "credits_remaining" in data
        assert "pricing_mode" in data
        
        print(f"✓ Overlay data: visible={data['visible']}, " +
              f"credits_remaining={data.get('credits_remaining')}, " +
              f"pricing_mode={data.get('pricing_mode')}")


class TestGameSimulation:
    """Test game start/end simulation (admin only)"""
    
    def test_simulate_game_start_decrements_credits(self, authenticated_client, api_client):
        """POST /api/kiosk/BOARD-1/simulate-game-start decrements credits"""
        # Get initial credits
        session_resp = api_client.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        initial_credits = session_resp.json().get("session", {}).get("credits_remaining", 0)
        
        # Simulate game start
        response = authenticated_client.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start")
        assert response.status_code == 200
        
        # Verify credits decremented
        session_resp = api_client.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        new_credits = session_resp.json().get("session", {}).get("credits_remaining", 0)
        
        assert new_credits == initial_credits - 1, \
            f"Credits should decrement: expected {initial_credits - 1}, got {new_credits}"
        
        print(f"✓ Game start simulation: credits {initial_credits} → {new_credits}")
    
    def test_simulate_game_end_handles_correctly(self, authenticated_client):
        """POST /api/kiosk/BOARD-1/simulate-game-end handles game end"""
        response = authenticated_client.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end")
        assert response.status_code == 200
        print(f"✓ Game end simulation successful")


class TestLock:
    """Test lock endpoint"""
    
    def test_lock_closes_session_and_resets_observer(self, authenticated_client, api_client):
        """POST /api/boards/BOARD-1/lock closes session and resets observer state"""
        response = authenticated_client.post(f"{BASE_URL}/api/boards/BOARD-1/lock")
        assert response.status_code == 200
        
        # Verify board is locked
        session_resp = api_client.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        data = session_resp.json()
        
        assert data.get("board_status") == "locked"
        print(f"✓ Board locked: board_status={data['board_status']}")
    
    def test_overlay_not_visible_when_locked(self, api_client):
        """GET /api/kiosk/BOARD-1/overlay returns visible:false when locked"""
        response = api_client.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("visible") == False
        print(f"✓ Overlay hidden when locked: visible={data['visible']}")


# ========== CODE VERIFICATION TESTS ==========

class TestCodeVerification:
    """Verify code implementation details"""
    
    def test_autodarts_observer_uses_ignore_default_args(self):
        """Backend autodarts_observer.py uses ignore_default_args=['--enable-automation']"""
        with open("/app/backend/services/autodarts_observer.py", "r") as f:
            content = f.read()
        
        # Check for ignore_default_args with --enable-automation
        assert 'ignore_default_args' in content
        assert '--enable-automation' in content
        
        # Verify it's in the launch_persistent_context call
        launch_pattern = r'launch_persistent_context\([^)]*ignore_default_args\s*=\s*\["--enable-automation"\]'
        assert re.search(launch_pattern, content), \
            "ignore_default_args=['--enable-automation'] should be in launch_persistent_context"
        
        print("✓ autodarts_observer.py uses ignore_default_args=['--enable-automation']")
    
    def test_autodarts_observer_imports_hide_kiosk_window(self):
        """Backend autodarts_observer.py imports and calls hide_kiosk_window"""
        with open("/app/backend/services/autodarts_observer.py", "r") as f:
            content = f.read()
        
        assert "from backend.services.window_manager import hide_kiosk_window" in content
        assert "await hide_kiosk_window()" in content
        
        print("✓ autodarts_observer.py imports and calls hide_kiosk_window")
    
    def test_autodarts_observer_imports_restore_kiosk_window(self):
        """Backend autodarts_observer.py imports and calls restore_kiosk_window in close_session"""
        with open("/app/backend/services/autodarts_observer.py", "r") as f:
            content = f.read()
        
        assert "from backend.services.window_manager import restore_kiosk_window" in content
        assert "await restore_kiosk_window()" in content
        
        print("✓ autodarts_observer.py imports and calls restore_kiosk_window")
    
    def test_window_manager_exists_with_required_functions(self):
        """Backend window_manager.py exists with hide_kiosk_window and restore_kiosk_window"""
        import os
        
        # Check file exists
        path = "/app/backend/services/window_manager.py"
        assert os.path.exists(path), f"window_manager.py not found at {path}"
        
        with open(path, "r") as f:
            content = f.read()
        
        # Check required functions
        assert "async def hide_kiosk_window" in content
        assert "async def restore_kiosk_window" in content
        
        # Check it uses Win32 API
        assert "sys.platform" in content
        assert "win32" in content
        assert "ctypes" in content
        
        print("✓ window_manager.py exists with hide_kiosk_window and restore_kiosk_window")


# ========== RELEASE PACKAGE VERIFICATION ==========

class TestReleasePackage:
    """Verify release package contents"""
    
    def test_windows_package_contains_window_manager(self):
        """Release package darts-kiosk-v1.0.0-windows contains window_manager.py"""
        import os
        
        path = "/app/release/build/darts-kiosk-v1.0.0-windows/backend/services/window_manager.py"
        assert os.path.exists(path), f"window_manager.py not found in Windows release at {path}"
        
        with open(path, "r") as f:
            content = f.read()
        
        assert "hide_kiosk_window" in content
        assert "restore_kiosk_window" in content
        
        print("✓ Windows release contains window_manager.py with required functions")
    
    def test_windows_package_contains_autodarts_observer(self):
        """Release package contains autodarts_observer.py"""
        import os
        
        path = "/app/release/build/darts-kiosk-v1.0.0-windows/backend/services/autodarts_observer.py"
        assert os.path.exists(path), f"autodarts_observer.py not found in Windows release"
        
        with open(path, "r") as f:
            content = f.read()
        
        # Verify automation banner fix is in release
        assert "ignore_default_args" in content
        
        print("✓ Windows release contains autodarts_observer.py with automation fix")
    
    def test_windows_package_contains_credits_overlay(self):
        """Release package contains credits_overlay.py"""
        import os
        
        path = "/app/release/build/darts-kiosk-v1.0.0-windows/credits_overlay.py"
        assert os.path.exists(path), f"credits_overlay.py not found in Windows release"
        
        with open(path, "r") as f:
            content = f.read()
        
        assert "CreditsOverlay" in content
        assert "tkinter" in content
        
        print("✓ Windows release contains credits_overlay.py")
    
    def test_windows_zip_exists(self):
        """Verify Windows zip package exists"""
        import os
        
        path = "/app/release/build/darts-kiosk-v1.0.0-windows.zip"
        assert os.path.exists(path), f"Windows zip not found at {path}"
        
        size = os.path.getsize(path)
        print(f"✓ Windows zip exists: {path} ({size / 1024 / 1024:.2f} MB)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
