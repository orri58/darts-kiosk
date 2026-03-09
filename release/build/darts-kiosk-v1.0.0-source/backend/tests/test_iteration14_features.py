"""
Iteration 14 Feature Tests
Tests for:
- GitHub-based update system endpoints (updates check, status)
- Lockscreen QR config endpoints
- System base-url endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def api_session():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def auth_token(api_session):
    """Get admin auth token"""
    response = api_session.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin12345"
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    # API returns access_token not token
    return data.get("access_token") or data.get("token")

@pytest.fixture(scope="module")
def admin_headers(auth_token):
    """Auth headers for admin requests"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    }


class TestUpdatesEndpoints:
    """GitHub-based update system endpoints"""

    def test_updates_check_returns_configured_false_when_no_repo(self, api_session, admin_headers):
        """GET /api/updates/check returns configured=false when GITHUB_REPO not set"""
        response = api_session.get(f"{BASE_URL}/api/updates/check", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        # GITHUB_REPO is not set in .env, so configured should be false
        assert "configured" in data
        assert data["configured"] == False
        assert "current_version" in data
        assert "message" in data
        # Should have a helpful message about configuring
        assert "GITHUB_REPO" in data.get("message", "") or "konfigur" in data.get("message", "").lower()

    def test_updates_status_returns_version_info(self, api_session, admin_headers):
        """GET /api/updates/status returns current_version and github_repo fields"""
        response = api_session.get(f"{BASE_URL}/api/updates/status", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert "current_version" in data
        assert data["current_version"] == "1.0.0"  # Default version from env
        assert "github_repo" in data
        # github_repo should be empty string since not configured
        assert data["github_repo"] == ""

    def test_updates_check_requires_auth(self, api_session):
        """GET /api/updates/check requires admin authentication"""
        response = api_session.get(f"{BASE_URL}/api/updates/check")
        assert response.status_code == 401

    def test_updates_status_requires_auth(self, api_session):
        """GET /api/updates/status requires admin authentication"""
        response = api_session.get(f"{BASE_URL}/api/updates/status")
        assert response.status_code == 401


class TestLockscreenQrEndpoints:
    """Lockscreen QR code configuration endpoints"""

    def test_get_lockscreen_qr_returns_default_config(self, api_session):
        """GET /api/settings/lockscreen-qr returns default config"""
        response = api_session.get(f"{BASE_URL}/api/settings/lockscreen-qr")
        assert response.status_code == 200
        data = response.json()
        
        # Check required fields exist
        assert "enabled" in data
        assert "label" in data
        assert "path" in data
        # Default path should be /public/leaderboard
        assert data["path"] == "/public/leaderboard"

    def test_put_lockscreen_qr_enables_and_persists(self, api_session, admin_headers):
        """PUT /api/settings/lockscreen-qr with enabled=true saves and persists"""
        # Enable the QR code
        payload = {
            "value": {
                "enabled": True,
                "label": "Test Leaderboard",
                "path": "/public/leaderboard"
            }
        }
        response = api_session.put(f"{BASE_URL}/api/settings/lockscreen-qr", json=payload, headers=admin_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert data["enabled"] == True
        assert data["label"] == "Test Leaderboard"
        
        # Verify persistence with GET
        get_response = api_session.get(f"{BASE_URL}/api/settings/lockscreen-qr")
        assert get_response.status_code == 200
        persisted = get_response.json()
        assert persisted["enabled"] == True
        assert persisted["label"] == "Test Leaderboard"

    def test_put_lockscreen_qr_requires_auth(self, api_session):
        """PUT /api/settings/lockscreen-qr without auth returns 401"""
        payload = {"value": {"enabled": False}}
        response = api_session.put(f"{BASE_URL}/api/settings/lockscreen-qr", json=payload)
        assert response.status_code == 401


class TestSystemBaseUrlEndpoint:
    """System base URL endpoint for QR code generation"""

    def test_base_url_returns_valid_url(self, api_session):
        """GET /api/system/base-url returns a valid base_url"""
        response = api_session.get(f"{BASE_URL}/api/system/base-url")
        assert response.status_code == 200
        data = response.json()
        
        assert "base_url" in data
        base_url = data["base_url"]
        
        # URL should be non-empty
        assert base_url and len(base_url) > 0
        # URL should start with http or https
        assert base_url.startswith("http://") or base_url.startswith("https://")

    def test_base_url_not_localhost_in_preview(self, api_session):
        """GET /api/system/base-url must NOT return localhost or 127.0.0.1"""
        response = api_session.get(f"{BASE_URL}/api/system/base-url")
        assert response.status_code == 200
        data = response.json()
        
        base_url = data.get("base_url", "")
        # In the preview environment, should return actual public URL
        assert "localhost" not in base_url, f"base_url should not contain localhost: {base_url}"
        assert "127.0.0.1" not in base_url, f"base_url should not contain 127.0.0.1: {base_url}"


class TestPublicLeaderboardAccess:
    """Public leaderboard page should be accessible without auth"""

    def test_public_leaderboard_api_no_auth(self, api_session):
        """GET /api/stats/leaderboard works without authentication"""
        response = api_session.get(f"{BASE_URL}/api/stats/leaderboard", params={
            "period": "all",
            "sort_by": "games_won",
            "limit": 10
        })
        # Should return 200 (even if empty)
        assert response.status_code == 200
        data = response.json()
        assert "leaderboard" in data


class TestAdminPassword:
    """Verify admin login credentials match requirements"""

    def test_admin_login_with_admin12345(self, api_session):
        """Admin login works with username=admin, password=admin12345"""
        response = api_session.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin12345"
        })
        assert response.status_code == 200
        data = response.json()
        # API returns access_token
        assert "access_token" in data or "token" in data
        assert "user" in data
        assert data["user"]["role"] == "admin"
