"""
Darts Kiosk v3.2.1 - Auto-Start Feature Test Suite

Testing minimal auto-start improvement for Autodarts Desktop:
- On server startup and board unlock: if auto_start=true in settings,
  check if Autodarts.exe is running and start it once (minimized, no focus steal) if missing.
- 60s cooldown to prevent loops
- No standby/wake/reconnect logic, no observer/watchdog/finalize changes

Endpoints tested:
- GET /api/admin/system/autodarts-desktop-status (now includes auto_start_cooldown_s)
- PUT /api/settings/autodarts-desktop (enable auto_start=true)

Code review:
- autodarts_desktop_service.py: ensure_running(), _start_no_focus(), cooldown logic
- server.py: lifespan calls ensure_running with trigger=server_startup
- boards.py: unlock_board calls ensure_running with trigger=board_unlock:{board_id}
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://boardgame-repair.preview.emergentagent.com"

ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token."""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USER,
        "password": ADMIN_PASS
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    token = data.get("access_token")
    assert token, f"No access_token in response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Auth headers for admin requests."""
    return {"Authorization": f"Bearer {admin_token}"}


class TestAutodartsDesktopStatusV321:
    """Test GET /api/admin/system/autodarts-desktop-status includes auto_start_cooldown_s (v3.2.1)."""
    
    def test_status_includes_auto_start_cooldown_s(self, auth_headers):
        """GET status response must include auto_start_cooldown_s field."""
        resp = requests.get(f"{BASE_URL}/api/admin/system/autodarts-desktop-status", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # v3.2.1: auto_start_cooldown_s should now be present
        assert "auto_start_cooldown_s" in data, f"Missing 'auto_start_cooldown_s' in response: {data}"
        assert isinstance(data["auto_start_cooldown_s"], int), f"auto_start_cooldown_s should be int: {data}"
        assert data["auto_start_cooldown_s"] == 60, f"Expected cooldown 60s, got {data['auto_start_cooldown_s']}"
        
        # Also verify existing fields
        assert "running" in data
        assert "process_name" in data
        assert "platform" in data
        assert "supported" in data
        
        print(f"[PASS] GET autodarts-desktop-status includes auto_start_cooldown_s={data['auto_start_cooldown_s']}")


class TestAutodartsDesktopSettingsV321:
    """Test PUT /api/settings/autodarts-desktop can enable auto_start=true."""
    
    def test_enable_auto_start(self, auth_headers):
        """PUT settings with auto_start=true should succeed."""
        # Enable auto_start
        new_config = {
            "exe_path": "C:\\Program Files\\Autodarts\\Autodarts.exe",
            "auto_start": True
        }
        resp = requests.put(
            f"{BASE_URL}/api/settings/autodarts-desktop",
            headers=auth_headers,
            json={"value": new_config}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("auto_start") == True, f"auto_start not True: {data}"
        print("[PASS] PUT autodarts-desktop: auto_start=true enabled successfully")
        
        # Verify persistence
        resp2 = requests.get(f"{BASE_URL}/api/settings/autodarts-desktop", headers=auth_headers)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("auto_start") == True, f"auto_start not persisted: {data2}"
        print("[PASS] Verified auto_start=true persisted")
    
    def test_disable_auto_start(self, auth_headers):
        """PUT settings with auto_start=false should succeed."""
        # Disable auto_start
        new_config = {
            "exe_path": "C:\\Program Files\\Autodarts\\Autodarts.exe",
            "auto_start": False
        }
        resp = requests.put(
            f"{BASE_URL}/api/settings/autodarts-desktop",
            headers=auth_headers,
            json={"value": new_config}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("auto_start") == False, f"auto_start not False: {data}"
        print("[PASS] PUT autodarts-desktop: auto_start=false disabled successfully")


class TestCodeReviewV321:
    """Code inspection tests for v3.2.1 auto-start features."""
    
    def test_ensure_running_has_cooldown_logic(self):
        """Verify ensure_running() has 60s cooldown."""
        with open("/app/backend/services/autodarts_desktop_service.py", "r") as f:
            content = f.read()
        
        # Check cooldown constant
        assert "_AUTO_START_COOLDOWN = 60" in content, "60s cooldown constant not found"
        
        # Check ensure_running method exists
        assert "def ensure_running(" in content, "ensure_running method not found"
        
        # Check cooldown logic
        assert "time.monotonic()" in content, "time.monotonic() not used for cooldown"
        assert "_last_auto_start_ts" in content, "_last_auto_start_ts not found"
        assert "cooldown" in content.lower(), "cooldown logic reference not found"
        
        print("[PASS] Code review: ensure_running() has 60s cooldown logic with time.monotonic()")
    
    def test_ensure_running_uses_sw_showminnoactive(self):
        """Verify _start_no_focus uses SW_SHOWMINNOACTIVE (7) to prevent focus steal."""
        with open("/app/backend/services/autodarts_desktop_service.py", "r") as f:
            content = f.read()
        
        # Check _start_no_focus method
        assert "def _start_no_focus(" in content, "_start_no_focus method not found"
        
        # SW_SHOWMINNOACTIVE = 7
        assert "wShowWindow = 7" in content or "si.wShowWindow = 7" in content, \
            "SW_SHOWMINNOACTIVE (7) not used in _start_no_focus"
        
        # Comment should indicate no focus steal
        assert "SW_SHOWMINNOACTIVE" in content, "SW_SHOWMINNOACTIVE comment not found"
        
        print("[PASS] Code review: _start_no_focus() uses SW_SHOWMINNOACTIVE (7) for no focus steal")
    
    def test_ensure_running_uses_create_no_window(self):
        """Verify _start_no_focus uses CREATE_NO_WINDOW flag."""
        with open("/app/backend/services/autodarts_desktop_service.py", "r") as f:
            content = f.read()
        
        # Check CREATE_NO_WINDOW flag
        assert "CREATE_NO_WINDOW" in content, "CREATE_NO_WINDOW flag not found"
        
        # Should be combined with DETACHED_PROCESS
        assert "DETACHED_PROCESS" in content, "DETACHED_PROCESS not found"
        
        print("[PASS] Code review: _start_no_focus() uses CREATE_NO_WINDOW flag")
    
    def test_server_lifespan_calls_ensure_running_server_startup(self):
        """Verify server.py lifespan calls ensure_running with trigger=server_startup."""
        with open("/app/backend/server.py", "r") as f:
            content = f.read()
        
        # Check auto-start on boot
        assert "ensure_running" in content, "ensure_running not called in server.py"
        assert 'trigger="server_startup"' in content or "trigger='server_startup'" in content, \
            "trigger=server_startup not found"
        
        # Check it's in lifespan context
        assert "v3.2.1" in content or "auto-start" in content.lower(), \
            "v3.2.1 auto-start comment not found"
        
        print("[PASS] Code review: server.py lifespan calls ensure_running with trigger=server_startup")
    
    def test_boards_unlock_calls_ensure_running_board_unlock(self):
        """Verify boards.py unlock_board calls ensure_running with trigger=board_unlock:{board_id}."""
        with open("/app/backend/routers/boards.py", "r") as f:
            content = f.read()
        
        # Check ensure_running call in unlock_board
        assert "ensure_running" in content, "ensure_running not called in boards.py"
        assert "board_unlock" in content, "board_unlock trigger not found"
        
        # Check proper trigger format
        assert 'trigger=f"board_unlock:{board_id}"' in content or \
               "trigger=f'board_unlock:{board_id}'" in content or \
               'trigger=f"board_unlock:' in content, \
            "trigger=board_unlock:{board_id} format not found"
        
        print("[PASS] Code review: boards.py unlock_board calls ensure_running with trigger=board_unlock:{board_id}")
    
    def test_boards_unlock_ensure_running_is_non_blocking(self):
        """Verify unlock_board ensure_running call is wrapped in try/except and non-blocking."""
        with open("/app/backend/routers/boards.py", "r") as f:
            content = f.read()
        
        # Look for the v3.2.1 section with try/except
        assert "v3.2.1" in content, "v3.2.1 version comment not found"
        
        # The ensure_running should be in try/except
        # Check for non-blocking (exception is caught and passed)
        lines = content.split('\n')
        in_try_block = False
        found_ensure_running = False
        found_except = False
        
        for i, line in enumerate(lines):
            if "try:" in line:
                in_try_block = True
            if in_try_block and "ensure_running" in line:
                found_ensure_running = True
            if found_ensure_running and "except" in line:
                found_except = True
                break
        
        assert found_ensure_running, "ensure_running not found in boards.py"
        assert found_except, "try/except wrapping ensure_running not found"
        
        # Check for 'pass' after exception (non-blocking)
        assert "pass  # non-critical" in content or "pass # non-critical" in content, \
            "pass comment for non-critical not found"
        
        print("[PASS] Code review: boards.py ensure_running is wrapped in try/except and non-blocking")
    
    def test_get_status_includes_cooldown_field(self):
        """Verify AutodartsDesktopService.get_status() returns auto_start_cooldown_s."""
        with open("/app/backend/services/autodarts_desktop_service.py", "r") as f:
            content = f.read()
        
        # Check get_status method includes cooldown
        assert "def get_status(" in content, "get_status method not found"
        assert "auto_start_cooldown_s" in content, "auto_start_cooldown_s not in get_status response"
        assert "_AUTO_START_COOLDOWN" in content, "_AUTO_START_COOLDOWN constant not referenced"
        
        print("[PASS] Code review: get_status() returns auto_start_cooldown_s")


class TestV320FeaturesRegression:
    """Ensure v3.2.0 features still work."""
    
    def test_post_match_delay_still_works(self, auth_headers):
        """GET /api/settings/post-match-delay still returns delay_ms."""
        resp = requests.get(f"{BASE_URL}/api/settings/post-match-delay", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "delay_ms" in data, f"Missing 'delay_ms': {data}"
        print(f"[PASS] v3.2.0 regression: post-match-delay returns delay_ms={data['delay_ms']}")
    
    def test_autodarts_desktop_settings_still_works(self, auth_headers):
        """GET /api/settings/autodarts-desktop still returns exe_path, auto_start."""
        resp = requests.get(f"{BASE_URL}/api/settings/autodarts-desktop", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "exe_path" in data, f"Missing 'exe_path': {data}"
        assert "auto_start" in data, f"Missing 'auto_start': {data}"
        print(f"[PASS] v3.2.0 regression: autodarts-desktop settings work")
    
    def test_health_endpoint(self):
        """Backend health check."""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        print("[PASS] Backend /api/health is healthy")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
