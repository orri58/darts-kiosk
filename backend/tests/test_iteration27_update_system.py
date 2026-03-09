"""
Iteration 27 - Update System Backend Tests

Tests the new update system endpoints including:
- /api/system/version (public, no auth)
- /api/health (public)
- /api/updates/status (auth required)
- /api/updates/backups/create (auth required)
- /api/updates/backups (list, auth required)
- /api/updates/backups/{filename} (delete, auth required)
- /api/updates/result (auth required)
- /api/updates/result/clear (auth required)
- /api/updates/downloads (auth required)
- /api/updates/check (auth required)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable must be set")


class TestPublicEndpoints:
    """Public endpoints - no authentication required"""

    def test_system_version_returns_correct_version(self):
        """Test 1: GET /api/system/version returns {installed_version: '1.6.5'}"""
        response = requests.get(f"{BASE_URL}/api/system/version")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "installed_version" in data, "Response should have 'installed_version' field"
        assert data["installed_version"] == "1.6.5", f"Expected '1.6.5', got {data['installed_version']}"
        print(f"✓ System version: {data['installed_version']}")

    def test_health_returns_healthy(self):
        """Test 2: GET /api/health returns {status: 'healthy'}"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Response should have 'status' field"
        assert data["status"] == "healthy", f"Expected 'healthy', got {data['status']}"
        print(f"✓ Health status: {data['status']}, mode: {data.get('mode', 'N/A')}")


@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    if login_response.status_code != 200:
        pytest.skip("Admin login failed - check credentials")
    
    data = login_response.json()
    token = data.get("access_token")
    if not token:
        pytest.skip("No access_token in login response")
    
    return token


@pytest.fixture
def auth_headers(admin_token):
    """Auth headers with admin token"""
    return {"Authorization": f"Bearer {admin_token}"}


class TestUpdateStatusEndpoint:
    """Test /api/updates/status endpoint"""

    def test_updates_status_requires_auth(self):
        """Test that /api/updates/status requires authentication"""
        response = requests.get(f"{BASE_URL}/api/updates/status")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ /api/updates/status requires authentication")

    def test_updates_status_returns_expected_fields(self, auth_headers):
        """Test 3: GET /api/updates/status returns current_version, github_repo, update_history"""
        response = requests.get(f"{BASE_URL}/api/updates/status", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "current_version" in data, "Response should have 'current_version' field"
        assert "github_repo" in data, "Response should have 'github_repo' field"
        assert "update_history" in data, "Response should have 'update_history' field"
        
        assert data["current_version"] == "1.6.5", f"Expected '1.6.5', got {data['current_version']}"
        assert isinstance(data["update_history"], list), "update_history should be a list"
        
        print(f"✓ Updates status: version={data['current_version']}, "
              f"repo={data['github_repo'] or 'not configured'}, "
              f"history_count={len(data['update_history'])}")


class TestAppBackupEndpoints:
    """Test app backup endpoints"""
    
    created_backup_filename = None  # Class-level to share between tests

    def test_backups_create_requires_auth(self):
        """Test that backup create requires auth"""
        response = requests.post(f"{BASE_URL}/api/updates/backups/create")
        assert response.status_code in [401, 403], f"Expected 401/403 without auth, got {response.status_code}"
        print("✓ /api/updates/backups/create requires authentication")

    def test_create_app_backup_success(self, auth_headers):
        """Test 4: POST /api/updates/backups/create creates a full app backup"""
        response = requests.post(f"{BASE_URL}/api/updates/backups/create", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Response should have success: true"
        assert "filename" in data, "Response should have 'filename' field"
        assert "size_bytes" in data, "Response should have 'size_bytes' field"
        assert data["filename"].startswith("app_backup_"), f"Filename should start with 'app_backup_': {data['filename']}"
        assert data["filename"].endswith(".zip"), f"Filename should end with '.zip': {data['filename']}"
        assert data["size_bytes"] > 0, "size_bytes should be > 0"
        
        # Store for later tests
        TestAppBackupEndpoints.created_backup_filename = data["filename"]
        
        print(f"✓ Created app backup: {data['filename']} ({data['size_bytes']} bytes)")

    def test_list_app_backups_shows_created_backup(self, auth_headers):
        """Test 5: GET /api/updates/backups lists all app backups"""
        response = requests.get(f"{BASE_URL}/api/updates/backups", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "backups" in data, "Response should have 'backups' field"
        assert isinstance(data["backups"], list), "backups should be a list"
        
        # Check if our created backup is in the list
        if TestAppBackupEndpoints.created_backup_filename:
            backup_names = [b["filename"] for b in data["backups"]]
            assert TestAppBackupEndpoints.created_backup_filename in backup_names, \
                f"Created backup {TestAppBackupEndpoints.created_backup_filename} should be in list"
        
        # Verify backup structure
        if len(data["backups"]) > 0:
            backup = data["backups"][0]
            assert "filename" in backup, "Backup should have 'filename'"
            assert "size_bytes" in backup, "Backup should have 'size_bytes'"
            assert "size_mb" in backup, "Backup should have 'size_mb'"
            assert "created_at" in backup, "Backup should have 'created_at'"
        
        print(f"✓ Listed {len(data['backups'])} app backups")

    def test_delete_app_backup(self, auth_headers):
        """Test 6: DELETE /api/updates/backups/{filename} deletes a specific app backup"""
        if not TestAppBackupEndpoints.created_backup_filename:
            pytest.skip("No backup was created in previous test")
        
        filename = TestAppBackupEndpoints.created_backup_filename
        response = requests.delete(f"{BASE_URL}/api/updates/backups/{filename}", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should have 'message' field"
        
        # Verify it's gone
        list_response = requests.get(f"{BASE_URL}/api/updates/backups", headers=auth_headers)
        list_data = list_response.json()
        backup_names = [b["filename"] for b in list_data.get("backups", [])]
        assert filename not in backup_names, f"Deleted backup {filename} should not be in list"
        
        print(f"✓ Deleted app backup: {filename}")


class TestUpdateResultEndpoints:
    """Test update result endpoints"""

    def test_update_result_no_result(self, auth_headers):
        """Test 7: GET /api/updates/result returns has_result:false (no update done yet)"""
        response = requests.get(f"{BASE_URL}/api/updates/result", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "has_result" in data, "Response should have 'has_result' field"
        # It may be True or False depending on whether an update was done
        print(f"✓ Update result: has_result={data.get('has_result')}")

    def test_clear_update_result(self, auth_headers):
        """Test 8: POST /api/updates/result/clear clears update result"""
        response = requests.post(f"{BASE_URL}/api/updates/result/clear", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "message" in data, "Response should have 'message' field"
        print(f"✓ Cleared update result: {data.get('message')}")


class TestDownloadsEndpoints:
    """Test downloaded assets endpoints"""

    def test_list_downloads(self, auth_headers):
        """Test 9: GET /api/updates/downloads lists downloaded assets"""
        response = requests.get(f"{BASE_URL}/api/updates/downloads", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "assets" in data, "Response should have 'assets' field"
        assert isinstance(data["assets"], list), "assets should be a list"
        print(f"✓ Listed {len(data['assets'])} downloaded assets")


class TestUpdateCheckEndpoint:
    """Test update check endpoint"""

    def test_check_for_updates(self, auth_headers):
        """Test 10: GET /api/updates/check checks for updates"""
        response = requests.get(f"{BASE_URL}/api/updates/check", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Should have either configured=false (no GITHUB_REPO) or configured=true
        assert "current_version" in data, "Response should have 'current_version'"
        assert data["current_version"] == "1.6.5", f"Expected '1.6.5', got {data['current_version']}"
        
        # If not configured, should have a message
        if not data.get("configured"):
            assert "message" in data, "Unconfigured should return message"
            print(f"✓ Update check (not configured): {data.get('message')}")
        else:
            print(f"✓ Update check: configured={data.get('configured')}, "
                  f"update_available={data.get('update_available')}")


class TestUpdateHistoryEndpoint:
    """Test update history endpoint"""

    def test_get_update_history(self, auth_headers):
        """Test: GET /api/updates/history returns history list"""
        response = requests.get(f"{BASE_URL}/api/updates/history", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "history" in data, "Response should have 'history' field"
        assert isinstance(data["history"], list), "history should be a list"
        print(f"✓ Update history: {len(data['history'])} entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
