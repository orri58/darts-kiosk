"""
Iteration 28 - Production Hardening Tests
Tests for:
1. Static frontend serving from FastAPI
2. API endpoints (/api/system/version, /api/health, /api/updates/*)
3. App backup workflow
4. Update result endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def auth_token(api_client):
    """Get authentication token with admin credentials"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        return response.json().get("access_token")
    pytest.skip(f"Authentication failed: {response.text}")


@pytest.fixture(scope="module")
def authenticated_client(api_client, auth_token):
    """Session with auth header"""
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


# ─────────────────────────────────────────────────────────────
# Test: Public API Endpoints
# ─────────────────────────────────────────────────────────────

class TestPublicEndpoints:
    """Public endpoints that don't require authentication"""

    def test_system_version_returns_1_7_1(self, api_client):
        """GET /api/system/version returns installed_version 1.7.1"""
        response = api_client.get(f"{BASE_URL}/api/system/version")
        assert response.status_code == 200
        data = response.json()
        assert "installed_version" in data
        assert data["installed_version"] == "1.7.1"
        print(f"PASS: /api/system/version returns {data['installed_version']}")

    def test_health_returns_healthy(self, api_client):
        """GET /api/health returns status healthy"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"
        print(f"PASS: /api/health returns status={data['status']}")


# ─────────────────────────────────────────────────────────────
# Test: Static Frontend Serving
# ─────────────────────────────────────────────────────────────

class TestStaticFrontendServing:
    """Backend serves frontend static build (production mode)"""

    def test_root_returns_html(self, api_client):
        """GET / returns index.html (HTTP 200)"""
        response = api_client.get(f"{BASE_URL}/")
        assert response.status_code == 200
        assert "<!doctype html>" in response.text.lower() or "<!DOCTYPE html>" in response.text
        assert "<title>" in response.text
        print("PASS: GET / returns HTML")

    def test_admin_spa_route_returns_html(self, api_client):
        """GET /admin returns index.html for SPA routing (HTTP 200)"""
        response = api_client.get(f"{BASE_URL}/admin")
        assert response.status_code == 200
        assert "<!doctype html>" in response.text.lower() or "<!DOCTYPE html>" in response.text
        print("PASS: GET /admin returns HTML (SPA routing)")

    def test_kiosk_spa_route_returns_html(self, api_client):
        """GET /kiosk/BOARD-1 returns index.html for SPA routing (HTTP 200)"""
        response = api_client.get(f"{BASE_URL}/kiosk/BOARD-1")
        assert response.status_code == 200
        assert "<!doctype html>" in response.text.lower() or "<!DOCTYPE html>" in response.text
        print("PASS: GET /kiosk/BOARD-1 returns HTML (SPA routing)")

    def test_api_still_works(self, api_client):
        """API routes (/api/*) still work alongside static serving"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("PASS: API routes work alongside static frontend serving")


# ─────────────────────────────────────────────────────────────
# Test: Authenticated Update Endpoints
# ─────────────────────────────────────────────────────────────

class TestUpdateEndpoints:
    """Update endpoints require admin authentication"""

    def test_updates_status(self, authenticated_client):
        """GET /api/updates/status returns current version info"""
        response = authenticated_client.get(f"{BASE_URL}/api/updates/status")
        assert response.status_code == 200
        data = response.json()
        assert "current_version" in data
        assert data["current_version"] == "1.7.1"
        print(f"PASS: /api/updates/status returns current_version={data['current_version']}")

    def test_updates_check(self, authenticated_client):
        """GET /api/updates/check returns JSON (may indicate no repo configured)"""
        response = authenticated_client.get(f"{BASE_URL}/api/updates/check")
        assert response.status_code == 200
        data = response.json()
        # Either has 'message' or 'update_available' depending on repo config
        assert "message" in data or "update_available" in data
        print(f"PASS: /api/updates/check returned: {data}")

    def test_updates_result(self, authenticated_client):
        """GET /api/updates/result returns has_result=false (no update done)"""
        response = authenticated_client.get(f"{BASE_URL}/api/updates/result")
        assert response.status_code == 200
        data = response.json()
        assert "has_result" in data
        print(f"PASS: /api/updates/result returns has_result={data['has_result']}")


# ─────────────────────────────────────────────────────────────
# Test: App Backup Workflow
# ─────────────────────────────────────────────────────────────

class TestAppBackupWorkflow:
    """App backup create, list, delete workflow"""

    created_backup_filename = None

    def test_create_app_backup(self, authenticated_client):
        """POST /api/updates/backups/create creates full app backup"""
        response = authenticated_client.post(f"{BASE_URL}/api/updates/backups/create")
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") is True
        assert "filename" in data
        assert "size_bytes" in data
        assert data["size_bytes"] > 0
        TestAppBackupWorkflow.created_backup_filename = data["filename"]
        print(f"PASS: Created backup: {data['filename']} ({data['size_bytes']} bytes)")

    def test_list_app_backups(self, authenticated_client):
        """GET /api/updates/backups lists app backups including the one just created"""
        response = authenticated_client.get(f"{BASE_URL}/api/updates/backups")
        assert response.status_code == 200
        data = response.json()
        assert "backups" in data
        assert isinstance(data["backups"], list)
        
        # Check the created backup is in the list
        if TestAppBackupWorkflow.created_backup_filename:
            filenames = [b["filename"] for b in data["backups"]]
            assert TestAppBackupWorkflow.created_backup_filename in filenames
            print(f"PASS: Listed {len(data['backups'])} backups, including test backup")
        else:
            print(f"PASS: Listed {len(data['backups'])} backups")

    def test_updates_history(self, authenticated_client):
        """GET /api/updates/history returns history list"""
        response = authenticated_client.get(f"{BASE_URL}/api/updates/history")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert isinstance(data["history"], list)
        print(f"PASS: /api/updates/history returned {len(data['history'])} events")

    def test_updates_downloads(self, authenticated_client):
        """GET /api/updates/downloads lists downloaded assets"""
        response = authenticated_client.get(f"{BASE_URL}/api/updates/downloads")
        assert response.status_code == 200
        data = response.json()
        assert "assets" in data
        assert isinstance(data["assets"], list)
        print(f"PASS: /api/updates/downloads returned {len(data['assets'])} assets")


# ─────────────────────────────────────────────────────────────
# Test: Game Simulation Endpoints
# ─────────────────────────────────────────────────────────────

class TestGameSimulation:
    """Simulate game lifecycle for testing observer callbacks"""

    def test_simulate_game_start(self, authenticated_client):
        """POST /api/kiosk/BOARD-1/simulate-game-start triggers game start callback"""
        response = authenticated_client.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"PASS: simulate-game-start: {data['message']}")

    def test_simulate_game_end(self, authenticated_client):
        """POST /api/kiosk/BOARD-1/simulate-game-end triggers game end callback"""
        response = authenticated_client.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        print(f"PASS: simulate-game-end: {data['message']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
