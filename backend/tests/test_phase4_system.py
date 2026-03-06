"""
Phase 4 System Management API Tests
Tests for:
- /api/system/info - System information endpoint
- /api/system/logs - Log viewing endpoint
- /api/system/logs/bundle - Log bundle download endpoint
- Regression tests for existing APIs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://boardgame-repair.preview.emergentagent.com').rstrip('/')


class TestAuth:
    """Authentication flow tests"""

    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"

    def test_pin_login_success(self):
        """Test PIN login with staff PIN"""
        response = requests.post(f"{BASE_URL}/api/auth/pin-login", json={
            "pin": "1234"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "wrongpassword"
        })
        assert response.status_code == 401


@pytest.fixture
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json()["access_token"]
    pytest.skip("Authentication failed")


@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestSystemInfo:
    """Tests for GET /api/system/info endpoint"""

    def test_system_info_returns_version(self, auth_headers):
        """Test that system info includes version"""
        response = requests.get(f"{BASE_URL}/api/system/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_system_info_returns_uptime(self, auth_headers):
        """Test that system info includes uptime"""
        response = requests.get(f"{BASE_URL}/api/system/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], int)
        assert data["uptime_seconds"] >= 0

    def test_system_info_returns_disk(self, auth_headers):
        """Test that system info includes disk information"""
        response = requests.get(f"{BASE_URL}/api/system/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "disk" in data
        disk = data["disk"]
        assert "total_gb" in disk
        assert "used_gb" in disk
        assert "free_gb" in disk
        assert "usage_percent" in disk

    def test_system_info_returns_mode(self, auth_headers):
        """Test that system info includes mode"""
        response = requests.get(f"{BASE_URL}/api/system/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert data["mode"] in ["MASTER", "AGENT"]

    def test_system_info_returns_hostname(self, auth_headers):
        """Test that system info includes hostname"""
        response = requests.get(f"{BASE_URL}/api/system/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "hostname" in data
        assert isinstance(data["hostname"], str)

    def test_system_info_requires_auth(self):
        """Test that system info requires authentication"""
        response = requests.get(f"{BASE_URL}/api/system/info")
        assert response.status_code == 401

    def test_system_info_full_structure(self, auth_headers):
        """Test complete structure of system info response"""
        response = requests.get(f"{BASE_URL}/api/system/info", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # All required fields
        required_fields = ["version", "image_tag", "mode", "uptime_seconds", 
                          "start_time", "python_version", "os", "hostname", 
                          "disk", "database", "backups", "data_dir"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


class TestSystemLogs:
    """Tests for GET /api/system/logs endpoint"""

    def test_system_logs_returns_lines(self, auth_headers):
        """Test that logs endpoint returns lines array"""
        response = requests.get(f"{BASE_URL}/api/system/logs", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "lines" in data
        assert isinstance(data["lines"], list)

    def test_system_logs_respects_lines_param(self, auth_headers):
        """Test that lines parameter limits output"""
        response = requests.get(f"{BASE_URL}/api/system/logs?lines=5", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["lines"]) <= 5

    def test_system_logs_requires_auth(self):
        """Test that logs endpoint requires authentication"""
        response = requests.get(f"{BASE_URL}/api/system/logs")
        assert response.status_code == 401


class TestSystemLogsBundle:
    """Tests for GET /api/system/logs/bundle endpoint"""

    def test_logs_bundle_returns_gzip(self, auth_headers):
        """Test that log bundle returns gzip file"""
        response = requests.get(f"{BASE_URL}/api/system/logs/bundle", headers=auth_headers)
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/gzip"
        assert len(response.content) > 0

    def test_logs_bundle_has_disposition_header(self, auth_headers):
        """Test that log bundle has Content-Disposition header"""
        response = requests.get(f"{BASE_URL}/api/system/logs/bundle", headers=auth_headers)
        assert response.status_code == 200
        disposition = response.headers.get("content-disposition", "")
        assert "attachment" in disposition
        assert "darts-logs_" in disposition
        assert ".tar.gz" in disposition

    def test_logs_bundle_requires_auth(self):
        """Test that logs bundle requires authentication"""
        response = requests.get(f"{BASE_URL}/api/system/logs/bundle")
        assert response.status_code == 401


class TestExistingAPIsRegression:
    """Regression tests for existing APIs"""

    def test_health_endpoint(self):
        """Test /api/health endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "mode" in data

    def test_boards_list(self, auth_headers):
        """Test /api/boards endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/boards", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if len(data) > 0:
            assert "board_id" in data[0]
            assert "status" in data[0]

    def test_backups_list(self, auth_headers):
        """Test /api/backups endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/backups", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "backups" in data
        assert "stats" in data

    def test_setup_status(self):
        """Test /api/setup/status endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/setup/status")
        assert response.status_code == 200
        data = response.json()
        assert "is_complete" in data or "setup_complete" in data or "needs_admin_password" in data

    def test_updates_status(self, auth_headers):
        """Test /api/updates/status endpoint still works"""
        response = requests.get(f"{BASE_URL}/api/updates/status", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "current_version" in data
        assert "available_versions" in data


class TestBackupOperations:
    """Test backup operations"""

    def test_backup_create(self, auth_headers):
        """Test creating a new backup"""
        response = requests.post(f"{BASE_URL}/api/backups/create", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "backup" in data
        assert "filename" in data["backup"]

    def test_backup_list_after_create(self, auth_headers):
        """Verify backup appears in list after creation"""
        # First create
        create_resp = requests.post(f"{BASE_URL}/api/backups/create", headers=auth_headers)
        assert create_resp.status_code == 200
        filename = create_resp.json()["backup"]["filename"]
        
        # Then list
        list_resp = requests.get(f"{BASE_URL}/api/backups", headers=auth_headers)
        assert list_resp.status_code == 200
        backups = list_resp.json()["backups"]
        filenames = [b["filename"] for b in backups]
        assert filename in filenames


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
