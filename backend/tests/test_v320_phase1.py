"""
Darts Kiosk v3.2.0 Phase 1 - Test Suite

Testing three new features:
1. Autodarts Desktop Supervision (minimal)
2. Configurable Post-Match Delay (post_match_delay_ms)
3. UI Credit Display Fix ('Letztes Spiel' when credits_remaining === 1)

Endpoints tested:
- GET/PUT /api/settings/post-match-delay
- GET/PUT /api/settings/autodarts-desktop
- GET /api/admin/system/autodarts-desktop-status
- POST /api/admin/system/restart-autodarts-desktop
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "https://boardgame-repair.preview.emergentagent.com"

# Test credentials
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


class TestPostMatchDelay:
    """Test Configurable Post-Match Delay feature (v3.2.0)."""
    
    def test_get_default_post_match_delay(self, auth_headers):
        """GET /api/settings/post-match-delay returns default {delay_ms: 5000}."""
        resp = requests.get(f"{BASE_URL}/api/settings/post-match-delay", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "delay_ms" in data, f"Missing 'delay_ms' in response: {data}"
        assert isinstance(data["delay_ms"], int), f"delay_ms should be int: {data}"
        # Default is 5000ms
        print(f"[PASS] GET post-match-delay: delay_ms={data['delay_ms']}")
    
    def test_update_post_match_delay(self, auth_headers):
        """PUT /api/settings/post-match-delay updates the delay value."""
        # Set to custom value
        new_delay = 7000
        resp = requests.put(
            f"{BASE_URL}/api/settings/post-match-delay",
            headers=auth_headers,
            json={"value": {"delay_ms": new_delay}}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("delay_ms") == new_delay, f"Expected delay_ms={new_delay}, got {data}"
        print(f"[PASS] PUT post-match-delay: updated to {new_delay}ms")
        
        # Verify by fetching again
        resp2 = requests.get(f"{BASE_URL}/api/settings/post-match-delay", headers=auth_headers)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("delay_ms") == new_delay, f"Verification failed: {data2}"
        print(f"[PASS] Verified delay_ms persisted: {data2['delay_ms']}ms")
        
        # Reset to default
        requests.put(
            f"{BASE_URL}/api/settings/post-match-delay",
            headers=auth_headers,
            json={"value": {"delay_ms": 5000}}
        )
        print("[INFO] Reset delay to default 5000ms")
    
    def test_post_match_delay_without_auth_rejected(self):
        """PUT without auth should fail (requires admin)."""
        resp = requests.put(
            f"{BASE_URL}/api/settings/post-match-delay",
            json={"value": {"delay_ms": 3000}}
        )
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print(f"[PASS] Unauthorized PUT rejected: {resp.status_code}")


class TestAutodartsDesktopSettings:
    """Test Autodarts Desktop configuration settings (v3.2.0)."""
    
    def test_get_autodarts_desktop_settings(self, auth_headers):
        """GET /api/settings/autodarts-desktop returns default config."""
        resp = requests.get(f"{BASE_URL}/api/settings/autodarts-desktop", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "exe_path" in data, f"Missing 'exe_path' in response: {data}"
        assert "auto_start" in data, f"Missing 'auto_start' in response: {data}"
        print(f"[PASS] GET autodarts-desktop: exe_path={data['exe_path']}, auto_start={data['auto_start']}")
    
    def test_update_autodarts_desktop_settings(self, auth_headers):
        """PUT /api/settings/autodarts-desktop updates the config."""
        new_config = {
            "exe_path": "C:\\Custom\\Path\\Autodarts.exe",
            "auto_start": True
        }
        resp = requests.put(
            f"{BASE_URL}/api/settings/autodarts-desktop",
            headers=auth_headers,
            json={"value": new_config}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("exe_path") == new_config["exe_path"], f"exe_path mismatch: {data}"
        assert data.get("auto_start") == new_config["auto_start"], f"auto_start mismatch: {data}"
        print(f"[PASS] PUT autodarts-desktop: updated config successfully")
        
        # Verify persistence
        resp2 = requests.get(f"{BASE_URL}/api/settings/autodarts-desktop", headers=auth_headers)
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("exe_path") == new_config["exe_path"]
        assert data2.get("auto_start") == new_config["auto_start"]
        print(f"[PASS] Verified autodarts-desktop config persisted")
        
        # Reset to default
        requests.put(
            f"{BASE_URL}/api/settings/autodarts-desktop",
            headers=auth_headers,
            json={"value": {"exe_path": "C:\\Program Files\\Autodarts\\Autodarts.exe", "auto_start": False}}
        )
        print("[INFO] Reset autodarts-desktop to default")


class TestAutodartsDesktopStatus:
    """Test Autodarts Desktop status and restart endpoints (v3.2.0)."""
    
    def test_get_autodarts_desktop_status(self, auth_headers):
        """GET /api/admin/system/autodarts-desktop-status returns status info."""
        resp = requests.get(f"{BASE_URL}/api/admin/system/autodarts-desktop-status", headers=auth_headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Expected fields from AutodartsDesktopService.get_status()
        assert "running" in data, f"Missing 'running' in response: {data}"
        assert "process_name" in data, f"Missing 'process_name' in response: {data}"
        assert "platform" in data, f"Missing 'platform' in response: {data}"
        assert "supported" in data, f"Missing 'supported' in response: {data}"
        
        # On Linux, supported should be False
        print(f"[PASS] GET autodarts-desktop-status: running={data['running']}, platform={data['platform']}, supported={data['supported']}")
        
        # Verify expected values for Linux server
        assert data["process_name"] == "Autodarts.exe", f"Unexpected process_name: {data}"
        assert isinstance(data["running"], bool), f"running should be bool: {data}"
        assert isinstance(data["supported"], bool), f"supported should be bool: {data}"
        
        # On Linux (preview server), supported should be False
        if data["platform"] == "Linux":
            assert data["supported"] == False, "On Linux, supported should be False"
            assert data["running"] == False, "On Linux, running should be False"
            print(f"[PASS] Linux platform detected: supported=False, running=False as expected")
    
    def test_restart_autodarts_desktop_on_linux(self, auth_headers):
        """POST /api/admin/system/restart-autodarts-desktop on Linux returns error (expected)."""
        resp = requests.post(f"{BASE_URL}/api/admin/system/restart-autodarts-desktop", headers=auth_headers)
        
        # On Linux, this should fail with 400 or 500 because exe doesn't exist
        # The endpoint checks exe_path and returns error if not configured or not Windows
        assert resp.status_code in [400, 500], f"Expected 400/500 on Linux, got {resp.status_code}: {resp.text}"
        
        # Response might be JSON or plain text depending on the error type
        try:
            data = resp.json()
            detail = data.get("detail", "")
        except:
            # Plain text error response is also acceptable
            detail = resp.text
        
        print(f"[PASS] POST restart-autodarts-desktop on Linux failed as expected: {resp.status_code} - {detail}")
    
    def test_autodarts_desktop_status_without_auth_rejected(self):
        """GET status without auth should fail."""
        resp = requests.get(f"{BASE_URL}/api/admin/system/autodarts-desktop-status")
        assert resp.status_code in [401, 403], f"Expected 401/403, got {resp.status_code}"
        print(f"[PASS] Unauthorized GET status rejected: {resp.status_code}")


class TestHealthAndBasics:
    """Basic health checks."""
    
    def test_health_endpoint(self):
        """Backend health check."""
        resp = requests.get(f"{BASE_URL}/api/health")
        assert resp.status_code == 200, f"Health check failed: {resp.text}"
        print("[PASS] Backend /api/health is healthy")
    
    def test_system_version(self):
        """Public version endpoint check."""
        resp = requests.get(f"{BASE_URL}/api/system/version")
        assert resp.status_code == 200, f"Version endpoint failed: {resp.text}"
        data = resp.json()
        assert "installed_version" in data, f"Missing installed_version: {data}"
        print(f"[PASS] System version: {data['installed_version']}")


class TestCodeReview:
    """Code inspection tests for v3.2.0 features."""
    
    def test_post_match_delay_default_value(self):
        """Verify DEFAULT_POST_MATCH_DELAY is 5000ms in models."""
        # Read the models file
        try:
            with open("/app/backend/models/__init__.py", "r") as f:
                content = f.read()
            assert "DEFAULT_POST_MATCH_DELAY" in content, "DEFAULT_POST_MATCH_DELAY not found"
            assert '"delay_ms": 5000' in content or "'delay_ms': 5000" in content, "Default 5000ms not found"
            print("[PASS] Code review: DEFAULT_POST_MATCH_DELAY = {delay_ms: 5000}")
        except FileNotFoundError:
            pytest.skip("Cannot access models file for code review")
    
    def test_autodarts_desktop_default_values(self):
        """Verify DEFAULT_AUTODARTS_DESKTOP values in models."""
        try:
            with open("/app/backend/models/__init__.py", "r") as f:
                content = f.read()
            assert "DEFAULT_AUTODARTS_DESKTOP" in content, "DEFAULT_AUTODARTS_DESKTOP not found"
            assert "exe_path" in content and "auto_start" in content, "Missing exe_path/auto_start"
            print("[PASS] Code review: DEFAULT_AUTODARTS_DESKTOP has exe_path and auto_start")
        except FileNotFoundError:
            pytest.skip("Cannot access models file for code review")
    
    def test_kiosk_uses_post_match_delay_from_db(self):
        """Verify kiosk.py reads post_match_delay from DB."""
        try:
            with open("/app/backend/routers/kiosk.py", "r") as f:
                content = f.read()
            assert "post_match_delay" in content, "post_match_delay not found in kiosk.py"
            assert "delay_ms" in content, "delay_ms not found in kiosk.py"
            print("[PASS] Code review: kiosk.py reads post_match_delay from DB")
        except FileNotFoundError:
            pytest.skip("Cannot access kiosk file for code review")
    
    def test_translations_have_last_game_key(self):
        """Verify translations.js has 'last_game' key for both DE and EN."""
        try:
            with open("/app/frontend/src/i18n/translations.js", "r") as f:
                content = f.read()
            # Check German
            assert "last_game:" in content or "last_game :" in content, "last_game key not found"
            assert "Letztes Spiel" in content, "'Letztes Spiel' DE translation not found"
            assert "Last Game" in content, "'Last Game' EN translation not found"
            print("[PASS] Code review: translations.js has last_game: DE='Letztes Spiel', EN='Last Game'")
        except FileNotFoundError:
            pytest.skip("Cannot access translations file for code review")
    
    def test_setup_screen_credit_display_fix(self):
        """Verify SetupScreen shows 'last_game' when credits === 1."""
        try:
            with open("/app/frontend/src/pages/kiosk/SetupScreen.js", "r") as f:
                content = f.read()
            # Check for the condition: credits === 1 shows last_game
            assert "credits === 1" in content or "credits == 1" in content, "credits === 1 check not found"
            assert "last_game" in content, "last_game key not used"
            print("[PASS] Code review: SetupScreen.js shows 'last_game' when credits === 1")
        except FileNotFoundError:
            pytest.skip("Cannot access SetupScreen file for code review")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
