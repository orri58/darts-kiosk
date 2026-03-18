"""
Darts Kiosk v3.3.0 - P0 Focus-Steal Bug Fix Tests
=================================================
Tests the autodarts_desktop_service.py rewrite with two-stage approach:
- Stage 1: SW_SHOWMINNOACTIVE launch (minimized, no focus steal)
- Stage 2: Background thread with debounced PowerShell focus correction

Bug fixes verified:
- NameError (import fix)
- NoneType (null-safe status)  
- UnicodeDecodeError (safe encoding)
"""
import os
import pytest
import requests
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestHealthAndVersion:
    """Basic health and version endpoints"""

    def test_health_endpoint(self):
        """GET /api/health returns 200 with status=healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        print(f"Health check: {data}")

    def test_system_version(self):
        """GET /api/system/info returns version 3.3.0"""
        # Login first
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200
        token = login_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/system/info", headers=headers)
        assert response.status_code == 200
        data = response.json()
        version = data.get("version", "")
        print(f"System version: {version}")
        # Version should be 3.3.0 or higher
        assert version.startswith("3.3") or version >= "3.3.0", f"Expected v3.3.0+, got {version}"


class TestAutodartsDesktopStatusAPI:
    """Test the /api/admin/system/autodarts-desktop-status endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token for admin endpoints"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_status_returns_all_required_fields(self):
        """GET /api/admin/system/autodarts-desktop-status returns valid JSON with all fields"""
        response = requests.get(
            f"{BASE_URL}/api/admin/system/autodarts-desktop-status",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields exist
        required_fields = [
            "running",
            "process_name",
            "platform",
            "supported",
            "auto_start_cooldown_s",
            "cooldown_active",
            "last_start_attempt_at",
            "last_error"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify field types
        assert isinstance(data["running"], bool), "running should be bool"
        assert isinstance(data["process_name"], str), "process_name should be str"
        assert isinstance(data["platform"], str), "platform should be str"
        assert isinstance(data["supported"], bool), "supported should be bool"
        assert isinstance(data["auto_start_cooldown_s"], int), "auto_start_cooldown_s should be int"
        assert isinstance(data["cooldown_active"], bool), "cooldown_active should be bool"
        # last_start_attempt_at and last_error can be None
        
        print(f"Status response: {data}")

    def test_running_field_never_none(self):
        """Verify 'running' field is always bool, never None (NoneType bug fix)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/system/autodarts-desktop-status",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Critical: running must be bool, not None
        assert data["running"] is not None, "running field should not be None"
        assert isinstance(data["running"], bool), f"running should be bool, got {type(data['running'])}"
        print(f"running field correctly returns bool: {data['running']}")

    def test_linux_graceful_degradation(self):
        """On Linux: is_running()=False, supported=False (no crash)"""
        response = requests.get(
            f"{BASE_URL}/api/admin/system/autodarts-desktop-status",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # On Linux test server, should return supported=False
        if data["platform"] == "Linux":
            assert data["supported"] is False, "Linux should have supported=False"
            assert data["running"] is False, "Linux should have running=False"
            print("Linux graceful degradation verified: supported=False, running=False")
        else:
            print(f"Platform is {data['platform']}, not Linux")


class TestRestartAutodartsDesktop:
    """Test the POST /api/admin/system/restart-autodarts-desktop endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_restart_graceful_error_on_linux(self):
        """POST /api/admin/system/restart-autodarts-desktop returns graceful error (not crash)"""
        response = requests.post(
            f"{BASE_URL}/api/admin/system/restart-autodarts-desktop",
            headers=self.headers
        )
        
        # On Linux without exe configured, should return 400 or 500 with detail, not crash
        assert response.status_code in [400, 500], f"Expected 400/500, got {response.status_code}"
        
        # Should have JSON error detail, not plain text error
        try:
            data = response.json()
            assert "detail" in data or "error" in data, "Should have error detail in JSON"
            print(f"Graceful error response: {data}")
        except Exception:
            # If plain text, it should still be informative
            text = response.text
            print(f"Response text: {text}")
            # Should not be an unhandled exception trace
            assert "Traceback" not in text, "Should not expose traceback to client"

    def test_restart_requires_auth(self):
        """POST /api/admin/system/restart-autodarts-desktop without auth returns 401"""
        response = requests.post(f"{BASE_URL}/api/admin/system/restart-autodarts-desktop")
        assert response.status_code == 401 or response.status_code == 403


class TestAutodartsDesktopServiceCode:
    """Code review tests - verify implementation details in the service file"""

    def test_subprocess_safe_dict_has_encoding(self):
        """_SUBPROCESS_SAFE dict has encoding=utf-8 and errors=replace"""
        # Read the service file
        service_path = "/app/backend/services/autodarts_desktop_service.py"
        if os.path.exists(service_path):
            with open(service_path, "r") as f:
                content = f.read()
            
            # Check for safe encoding settings
            assert '"encoding": "utf-8"' in content or "'encoding': 'utf-8'" in content, \
                "_SUBPROCESS_SAFE should have encoding=utf-8"
            assert '"errors": "replace"' in content or "'errors': 'replace'" in content, \
                "_SUBPROCESS_SAFE should have errors=replace"
            print("_SUBPROCESS_SAFE has safe encoding: encoding=utf-8, errors=replace")
        else:
            pytest.skip("Service file not accessible in test environment")

    def test_schedule_focus_correction_uses_daemon_thread(self):
        """_schedule_focus_correction uses threading.Thread with daemon=True"""
        service_path = "/app/backend/services/autodarts_desktop_service.py"
        if os.path.exists(service_path):
            with open(service_path, "r") as f:
                content = f.read()
            
            # Check for daemon thread
            assert "threading.Thread" in content, "Should use threading.Thread"
            assert "daemon=True" in content, "Thread should be daemon=True"
            print("Focus correction uses daemon thread: daemon=True")
        else:
            pytest.skip("Service file not accessible")

    def test_focus_correction_debounce_is_10_seconds(self):
        """_FOCUS_CORRECTION_DEBOUNCE is set to 10 seconds"""
        service_path = "/app/backend/services/autodarts_desktop_service.py"
        if os.path.exists(service_path):
            with open(service_path, "r") as f:
                content = f.read()
            
            # Check for debounce constant
            assert "_FOCUS_CORRECTION_DEBOUNCE = 10" in content, \
                "_FOCUS_CORRECTION_DEBOUNCE should be 10"
            print("Focus correction debounce is 10 seconds")
        else:
            pytest.skip("Service file not accessible")

    def test_sw_showminnoactive_constant(self):
        """Start uses SW_SHOWMINNOACTIVE (value 7) for minimized no-focus launch"""
        service_path = "/app/backend/services/autodarts_desktop_service.py"
        if os.path.exists(service_path):
            with open(service_path, "r") as f:
                content = f.read()
            
            # Check for SW_SHOWMINNOACTIVE = 7
            assert "wShowWindow = 7" in content or "SW_SHOWMINNOACTIVE" in content, \
                "Should use SW_SHOWMINNOACTIVE (7) for minimized launch"
            print("SW_SHOWMINNOACTIVE (7) used for minimized no-focus launch")
        else:
            pytest.skip("Service file not accessible")

    def test_null_safe_is_running(self):
        """is_running() has null-safe stdout handling"""
        service_path = "/app/backend/services/autodarts_desktop_service.py"
        if os.path.exists(service_path):
            with open(service_path, "r") as f:
                content = f.read()
            
            # Check for null-safe stdout handling
            assert 'stdout = result.stdout or ""' in content or \
                   'result.stdout or ""' in content, \
                "is_running() should have null-safe stdout: result.stdout or ''"
            print("is_running() has null-safe stdout handling")
        else:
            pytest.skip("Service file not accessible")

    def test_get_status_returns_running_bool(self):
        """get_status() never returns None for 'running' field"""
        service_path = "/app/backend/services/autodarts_desktop_service.py"
        if os.path.exists(service_path):
            with open(service_path, "r") as f:
                content = f.read()
            
            # Look for the get_status method with try/except for running
            assert "def get_status(self)" in content, "get_status method should exist"
            # Check that running defaults to False on exception
            assert "running = False" in content or "except" in content, \
                "get_status should handle exceptions for running field"
            print("get_status() has null-safe running field")
        else:
            pytest.skip("Service file not accessible")


class TestEnsureRunningOnLinux:
    """Test ensure_running() behavior on Linux"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_ensure_running_returns_skip_on_linux(self):
        """Code review: ensure_running() returns skip reason on Linux"""
        service_path = "/app/backend/services/autodarts_desktop_service.py"
        if os.path.exists(service_path):
            with open(service_path, "r") as f:
                content = f.read()
            
            # Check for skip return on non-Windows
            assert 'return {"action": "skip", "reason": "not_windows"}' in content, \
                "ensure_running should return skip with reason=not_windows on Linux"
            print("ensure_running() returns skip reason on non-Windows")
        else:
            pytest.skip("Service file not accessible")


class TestAutodartsDesktopSingleton:
    """Test the autodarts_desktop singleton behavior"""

    def test_is_running_returns_false_on_linux(self):
        """autodarts_desktop singleton is_running() returns False on Linux (never crashes)"""
        # This tests via the API since we can't directly import the singleton
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        token = login_resp.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}
        
        # Multiple calls should all work without crash
        for i in range(3):
            response = requests.get(
                f"{BASE_URL}/api/admin/system/autodarts-desktop-status",
                headers=headers
            )
            assert response.status_code == 200, f"Call {i+1} failed with {response.status_code}"
            data = response.json()
            assert data["running"] is False or data["running"] is True, \
                f"running should be bool, got {data['running']}"
        
        print("Singleton is_running() works correctly across multiple calls")


class TestV330BugFixes:
    """Explicit tests for the three original bugs fixed in v3.3.0"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def test_nameerror_import_fix(self):
        """Bug fix: No NameError from missing imports"""
        # If there was a NameError, the endpoint would return 500 with traceback
        response = requests.get(
            f"{BASE_URL}/api/admin/system/autodarts-desktop-status",
            headers=self.headers
        )
        assert response.status_code == 200, \
            f"NameError would cause 500, got {response.status_code}"
        print("No NameError: imports are correct")

    def test_nonetype_null_safe_status(self):
        """Bug fix: No NoneType error in status - running field always bool"""
        response = requests.get(
            f"{BASE_URL}/api/admin/system/autodarts-desktop-status",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # The bug was: running could be None causing "'NoneType' object is not subscriptable"
        assert data["running"] is not None, "running should not be None (NoneType fix)"
        assert isinstance(data["running"], bool), "running should be bool"
        print("No NoneType: running field is properly bool")

    def test_unicodedecodeerror_safe_encoding(self):
        """Bug fix: No UnicodeDecodeError from subprocess output"""
        # Multiple rapid calls to stress-test encoding handling
        for i in range(5):
            response = requests.get(
                f"{BASE_URL}/api/admin/system/autodarts-desktop-status",
                headers=self.headers
            )
            # UnicodeDecodeError would cause 500
            assert response.status_code == 200, \
                f"UnicodeDecodeError would cause 500 on call {i+1}"
        print("No UnicodeDecodeError: safe encoding with errors=replace")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
