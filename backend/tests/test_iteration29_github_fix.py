"""
Iteration 29 - GitHub Release Asset Download Fix Tests

Tests for the fix where GitHub release asset downloads for private repositories
now use the GitHub API URL (api.github.com/repos/.../releases/assets/{id}) with
Accept: application/octet-stream header instead of browser_download_url.

Tested Features:
1. GET /api/system/version — returns installed_version
2. GET /api/health — returns healthy
3. GET /api/updates/check — returns JSON (no GITHUB_REPO configured message)
4. GET /api/updates/status — returns current_version and update_history
5. POST /api/updates/backups/create — creates app backup (auth required)
6. GET /api/updates/backups — lists backups
7. GET /api/updates/result — returns has_result:false
8. Static frontend: GET / returns HTML
9. SPA routing: GET /admin returns HTML
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://boardgame-repair.preview.emergentagent.com')


class TestHealthAndVersion:
    """Basic health and version endpoint tests"""
    
    def test_health_endpoint(self):
        """Test GET /api/health returns healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"
        assert "mode" in data
        print(f"✓ Health: {data}")
    
    def test_version_endpoint(self):
        """Test GET /api/system/version returns installed_version"""
        response = requests.get(f"{BASE_URL}/api/system/version")
        assert response.status_code == 200
        data = response.json()
        assert "installed_version" in data
        assert data["installed_version"] == "1.7.1"
        print(f"✓ Version: {data}")


class TestStaticFrontend:
    """Static frontend serving tests"""
    
    def test_root_returns_html(self):
        """Test GET / returns HTML (static frontend)"""
        response = requests.get(BASE_URL)
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "<!doctype html>" in response.text.lower()
        print("✓ Root returns HTML")
    
    def test_admin_spa_routing(self):
        """Test GET /admin returns HTML (SPA routing)"""
        response = requests.get(f"{BASE_URL}/admin")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert "<!doctype html>" in response.text.lower()
        print("✓ /admin SPA routing works")


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for admin user"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    token = response.json().get("access_token")
    assert token, "No access_token in response"
    print(f"✓ Auth token obtained")
    return token


class TestUpdateEndpoints:
    """Update system endpoint tests"""
    
    def test_updates_check_no_repo_configured(self, auth_token):
        """Test GET /api/updates/check without GITHUB_REPO returns message"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/updates/check", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Without GITHUB_REPO configured, should return configured: false with message
        assert data.get("configured") == False
        assert "current_version" in data
        assert data["current_version"] == "1.7.1"
        assert "message" in data
        assert "GITHUB_REPO" in data["message"] or "konfiguriert" in data["message"].lower()
        assert "releases" in data
        print(f"✓ Updates check: {data.get('message')}")
    
    def test_updates_status(self, auth_token):
        """Test GET /api/updates/status returns current_version and update_history"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/updates/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "current_version" in data
        assert data["current_version"] == "1.7.1"
        assert "github_repo" in data
        assert "update_history" in data
        assert isinstance(data["update_history"], list)
        print(f"✓ Updates status: version={data['current_version']}, history_count={len(data['update_history'])}")
    
    def test_updates_result(self, auth_token):
        """Test GET /api/updates/result returns has_result:false"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/updates/result", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "has_result" in data
        assert data["has_result"] == False
        print(f"✓ Updates result: {data}")


class TestBackupEndpoints:
    """Backup system endpoint tests"""
    
    def test_list_app_backups(self, auth_token):
        """Test GET /api/updates/backups lists backups"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.get(f"{BASE_URL}/api/updates/backups", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "backups" in data
        assert isinstance(data["backups"], list)
        print(f"✓ App backups listed: {len(data['backups'])} backups")
        
        if data["backups"]:
            backup = data["backups"][0]
            assert "filename" in backup
            assert "size_bytes" in backup
            assert "created_at" in backup
            print(f"  First backup: {backup['filename']} ({backup.get('size_mb', 0)} MB)")
    
    def test_create_app_backup(self, auth_token):
        """Test POST /api/updates/backups/create creates app backup"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = requests.post(f"{BASE_URL}/api/updates/backups/create", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") == True
        assert "filename" in data
        assert "path" in data
        assert "size_bytes" in data
        assert data["filename"].startswith("app_backup_")
        assert data["filename"].endswith(".zip")
        print(f"✓ App backup created: {data['filename']} ({data['size_bytes']} bytes)")
        
        # Verify the backup appears in the list
        list_response = requests.get(f"{BASE_URL}/api/updates/backups", headers=headers)
        assert list_response.status_code == 200
        backups = list_response.json().get("backups", [])
        backup_names = [b["filename"] for b in backups]
        assert data["filename"] in backup_names, "Created backup not found in list"
        print(f"✓ Backup verified in list")


class TestUpdateServiceLogic:
    """Tests for update service URL resolution logic"""
    
    def test_update_service_imports(self):
        """Verify update service module can be imported"""
        from backend.services.update_service import UpdateService, update_service
        assert UpdateService is not None
        assert update_service is not None
        print("✓ UpdateService module imported")
    
    def test_resolve_download_url_method_exists(self):
        """Verify _resolve_download_url method exists"""
        from backend.services.update_service import UpdateService
        service = UpdateService()
        assert hasattr(service, '_resolve_download_url')
        assert callable(service._resolve_download_url)
        print("✓ _resolve_download_url method exists")
    
    def test_find_api_url_for_asset_method_exists(self):
        """Verify _find_api_url_for_asset method exists"""
        from backend.services.update_service import UpdateService
        service = UpdateService()
        assert hasattr(service, '_find_api_url_for_asset')
        assert callable(service._find_api_url_for_asset)
        print("✓ _find_api_url_for_asset method exists")
    
    def test_resolve_download_url_public_repo(self):
        """Test URL resolution for public repo (no token)"""
        from backend.services.update_service import UpdateService
        import os
        
        # Temporarily unset token
        old_token = os.environ.pop('GITHUB_TOKEN', None)
        try:
            service = UpdateService()
            browser_url = "https://github.com/owner/repo/releases/download/v1.0.0/asset.zip"
            
            url, headers = service._resolve_download_url(browser_url, "asset.zip", has_token=False)
            
            # For public repo without token, should return browser URL
            assert url == browser_url
            assert "Accept" in headers
            print(f"✓ Public repo URL resolution: {url}")
        finally:
            if old_token:
                os.environ['GITHUB_TOKEN'] = old_token
    
    def test_resolve_download_url_private_repo_no_cache(self):
        """Test URL resolution for private repo (with token) but no cached releases"""
        from backend.services.update_service import UpdateService
        import os
        
        # Set a fake token
        old_token = os.environ.get('GITHUB_TOKEN')
        os.environ['GITHUB_TOKEN'] = 'test-token-for-testing'
        try:
            service = UpdateService()
            browser_url = "https://github.com/owner/repo/releases/download/v1.0.0/asset.zip"
            
            # With token but no cached releases, should fallback to browser URL with auth
            url, headers = service._resolve_download_url(browser_url, "asset.zip", has_token=True)
            
            # Should include Authorization header when GITHUB_TOKEN is set
            assert "Authorization" in headers
            assert headers["Authorization"] == "Bearer test-token-for-testing"
            print(f"✓ Private repo (no cache) URL resolution: {url[:50]}...")
        finally:
            if old_token:
                os.environ['GITHUB_TOKEN'] = old_token
            else:
                os.environ.pop('GITHUB_TOKEN', None)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
