"""
Iteration 24 - Chrome Profile & Extensions Fix Tests

Verifies:
1. ignore_default_args now includes --disable-extensions and --disable-component-extensions-with-background-pages
2. chrome_args does NOT include --disable-default-apps or --disable-sync
3. Profile content logging (cookies_present, extensions_dir)
4. window_manager.py has MAX_RETRIES=3 retry logic
5. setup_profile.bat exists in release package
6. Full credit lifecycle regression (multi-game)
7. API endpoints work correctly
"""
import pytest
import requests
import os
import re
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Admin credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers with Bearer token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestCodeVerification:
    """Verify code changes in autodarts_observer.py and window_manager.py"""
    
    def test_observer_ignore_default_args_has_disable_extensions(self):
        """Verify --disable-extensions is in ignore_default_args"""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, "r") as f:
            content = f.read()
        
        # Look for ignore_args list that includes --disable-extensions
        assert '"--disable-extensions"' in content, \
            "ignore_default_args should include --disable-extensions"
        print("PASS: --disable-extensions found in ignore_default_args")
    
    def test_observer_ignore_default_args_has_component_extensions(self):
        """Verify --disable-component-extensions-with-background-pages is in ignore_default_args"""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, "r") as f:
            content = f.read()
        
        assert '"--disable-component-extensions-with-background-pages"' in content, \
            "ignore_default_args should include --disable-component-extensions-with-background-pages"
        print("PASS: --disable-component-extensions-with-background-pages found in ignore_default_args")
    
    def test_observer_ignore_default_args_has_enable_automation(self):
        """Verify --enable-automation is still in ignore_default_args"""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, "r") as f:
            content = f.read()
        
        assert '"--enable-automation"' in content, \
            "ignore_default_args should include --enable-automation"
        print("PASS: --enable-automation found in ignore_default_args")
    
    def test_observer_chrome_args_no_disable_default_apps(self):
        """Verify --disable-default-apps is NOT in chrome_args"""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, "r") as f:
            content = f.read()
        
        # Find the chrome_args = [...] block
        # This should NOT contain --disable-default-apps
        chrome_args_match = re.search(r"chrome_args\s*=\s*\[([^\]]+)\]", content, re.MULTILINE | re.DOTALL)
        assert chrome_args_match, "chrome_args list not found"
        chrome_args_content = chrome_args_match.group(1)
        
        assert "--disable-default-apps" not in chrome_args_content, \
            "--disable-default-apps should NOT be in chrome_args (blocks extension loading)"
        print("PASS: --disable-default-apps NOT in chrome_args")
    
    def test_observer_chrome_args_no_disable_sync(self):
        """Verify --disable-sync is NOT in chrome_args"""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, "r") as f:
            content = f.read()
        
        chrome_args_match = re.search(r"chrome_args\s*=\s*\[([^\]]+)\]", content, re.MULTILINE | re.DOTALL)
        assert chrome_args_match, "chrome_args list not found"
        chrome_args_content = chrome_args_match.group(1)
        
        assert "--disable-sync" not in chrome_args_content, \
            "--disable-sync should NOT be in chrome_args (breaks profile sync)"
        print("PASS: --disable-sync NOT in chrome_args")
    
    def test_observer_has_profile_content_logging(self):
        """Verify profile content logging for cookies and extensions"""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, "r") as f:
            content = f.read()
        
        # Check for cookies_present and extensions_dir logging
        assert "cookies_present" in content, \
            "Profile logging should include cookies_present"
        assert "extensions_dir" in content, \
            "Profile logging should include extensions_dir"
        print("PASS: Profile content logging includes cookies_present and extensions_dir")
    
    def test_window_manager_has_retry_logic(self):
        """Verify window_manager.py has MAX_RETRIES=3"""
        wm_path = "/app/backend/services/window_manager.py"
        with open(wm_path, "r") as f:
            content = f.read()
        
        assert "MAX_RETRIES" in content, "MAX_RETRIES constant not found"
        assert "MAX_RETRIES = 3" in content, "MAX_RETRIES should be 3"
        print("PASS: window_manager has MAX_RETRIES=3")
    
    def test_window_manager_has_retry_loop(self):
        """Verify window_manager uses retry loop in hide/restore functions"""
        wm_path = "/app/backend/services/window_manager.py"
        with open(wm_path, "r") as f:
            content = f.read()
        
        # Check for retry pattern
        assert "for attempt in range" in content, \
            "window_manager should have retry loop"
        assert "RETRY_DELAY" in content, \
            "window_manager should have RETRY_DELAY"
        print("PASS: window_manager has retry loop pattern")


class TestReleasePackage:
    """Verify release package contents"""
    
    def test_setup_profile_bat_exists_in_source(self):
        """Verify setup_profile.bat exists in source"""
        path = "/app/release/windows/setup_profile.bat"
        assert os.path.exists(path), "setup_profile.bat not found in /app/release/windows/"
        print(f"PASS: setup_profile.bat exists at {path}")
    
    def test_setup_profile_bat_exists_in_release(self):
        """Verify setup_profile.bat exists in release package"""
        path = "/app/release/build/darts-kiosk-v1.0.0-windows/setup_profile.bat"
        assert os.path.exists(path), "setup_profile.bat not found in release package"
        print(f"PASS: setup_profile.bat exists in release package")
    
    def test_setup_profile_bat_has_correct_content(self):
        """Verify setup_profile.bat has proper instructions"""
        path = "/app/release/build/darts-kiosk-v1.0.0-windows/setup_profile.bat"
        with open(path, "r") as f:
            content = f.read()
        
        # Should have instructions for login and extensions
        assert "Google" in content or "anmelden" in content, \
            "setup_profile.bat should mention Google login"
        assert "Extensions" in content or "extension" in content.lower(), \
            "setup_profile.bat should mention extensions"
        assert "play.autodarts.io" in content, \
            "setup_profile.bat should open autodarts URL"
        print("PASS: setup_profile.bat has correct content")


class TestHealthAndAuth:
    """Basic API health and auth tests"""
    
    def test_health_endpoint(self):
        """GET /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print("PASS: Health endpoint returns healthy")
    
    def test_admin_login(self):
        """Admin login works"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        print("PASS: Admin login successful")


class TestCreditLifecycle:
    """Full credit lifecycle with game simulation"""
    
    def test_lock_board_first(self, auth_headers):
        """Ensure board is locked before unlock test"""
        response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers=auth_headers
        )
        # Accept 200 or 404 (board might not exist yet)
        assert response.status_code in [200, 404], f"Lock failed: {response.text}"
        time.sleep(0.5)
        print("PASS: Board lock called (reset state)")
    
    def test_unlock_board_with_credits(self, auth_headers):
        """POST /api/boards/BOARD-1/unlock creates session with credits"""
        response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=auth_headers,
            json={
                "pricing_mode": "per_game",
                "credits": 3,
                "price_total": 9.0,
                "players_count": 2
            }
        )
        assert response.status_code == 200, f"Unlock failed: {response.text}"
        data = response.json()
        assert data.get("credits_remaining") == 3
        assert data.get("pricing_mode") == "per_game"
        print("PASS: Board unlocked with 3 credits")
    
    def test_simulate_game_start_decrements_credit(self, auth_headers):
        """POST /api/kiosk/BOARD-1/simulate-game-start decrements credits"""
        response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Simulate start failed: {response.text}"
        
        # Check credits via overlay
        time.sleep(0.3)
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        data = overlay.json()
        assert data.get("credits_remaining") == 2, f"Expected 2 credits, got {data.get('credits_remaining')}"
        print("PASS: Game 1 started, credits: 3→2")
    
    def test_simulate_game_end_stays_unlocked(self, auth_headers):
        """Game end with credits remaining stays unlocked"""
        response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        time.sleep(0.3)
        session = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        data = session.json()
        assert data.get("board_status") == "unlocked", f"Board should be unlocked, got {data.get('board_status')}"
        print("PASS: Game 1 ended, board stays unlocked (2 credits remain)")
    
    def test_game2_abort_stays_unlocked(self, auth_headers):
        """Game 2: start and abort, still has credits, stays unlocked"""
        # Start game 2
        response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        time.sleep(0.3)
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert overlay.json().get("credits_remaining") == 1, "Expected 1 credit after game 2 start"
        print("PASS: Game 2 started, credits: 2→1")
        
        # Abort game 2
        response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-abort",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        time.sleep(0.3)
        session = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        data = session.json()
        assert data.get("board_status") == "unlocked", f"Board should be unlocked, got {data.get('board_status')}"
        print("PASS: Game 2 aborted, board stays unlocked (1 credit remains)")
    
    def test_game3_finish_auto_locks(self, auth_headers):
        """Game 3: start and finish with 0 credits triggers auto-lock"""
        # Start game 3 (last credit)
        response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        time.sleep(0.3)
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        data = overlay.json()
        assert data.get("credits_remaining") == 0, f"Expected 0 credits, got {data.get('credits_remaining')}"
        assert data.get("is_last_game") == True, "Should be last game"
        print("PASS: Game 3 started, credits: 1→0 (last game)")
        
        # Finish game 3 (should trigger auto-lock)
        response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        time.sleep(0.5)
        session = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        data = session.json()
        assert data.get("board_status") == "locked", f"Board should be locked, got {data.get('board_status')}"
        print("PASS: Game 3 finished, board auto-locked (credits exhausted)")
    
    def test_overlay_hidden_when_locked(self):
        """Overlay returns visible:false when locked"""
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        data = response.json()
        assert data.get("visible") == False, f"Overlay should be hidden, got {data}"
        print("PASS: Overlay hidden when board locked")


class TestAbortAutoLock:
    """Test abort on last credit triggers auto-lock"""
    
    def test_setup_single_credit_session(self, auth_headers):
        """Create session with 1 credit for abort test"""
        # Lock first
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=auth_headers)
        time.sleep(0.3)
        
        # Unlock with 1 credit
        response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=auth_headers,
            json={
                "pricing_mode": "per_game",
                "credits": 1,
                "price_total": 3.0,
                "players_count": 1
            }
        )
        assert response.status_code == 200
        print("PASS: Single credit session created")
    
    def test_abort_last_game_auto_locks(self, auth_headers):
        """Aborting last game triggers auto-lock"""
        # Start the only game
        response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        time.sleep(0.3)
        overlay = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/overlay")
        assert overlay.json().get("credits_remaining") == 0
        print("PASS: Last game started, credits: 1→0")
        
        # ABORT the game (not finish)
        response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-abort",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        time.sleep(0.5)
        session = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        data = session.json()
        assert data.get("board_status") == "locked", \
            f"Board should be locked after abort with 0 credits, got {data.get('board_status')}"
        print("PASS: Abort on last credit triggers auto-lock (KEY BUG FIX)")


class TestLockEndpoint:
    """Test manual lock endpoint"""
    
    def test_lock_works_correctly(self, auth_headers):
        """POST /api/boards/BOARD-1/lock works correctly"""
        # Ensure unlocked first
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=auth_headers,
            json={
                "pricing_mode": "per_game",
                "credits": 2,
                "price_total": 6.0
            }
        )
        time.sleep(0.3)
        
        # Now lock
        response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "locked" in data.get("message", "").lower() or data.get("board_id") == "BOARD-1"
        
        # Verify locked
        session = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert session.json().get("board_status") == "locked"
        print("PASS: Manual lock endpoint works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
