"""
Test: Update Notification Background Check System
Tests for:
- GET /api/updates/notification - returns cached notification from DB
- POST /api/updates/notification/dismiss - dismisses notification for a version
- GET /api/updates/status - current version, github_repo, update_history
- GET /api/updates/check - check for updates (returns configured=false when no GITHUB_REPO)
- Background scheduler starts on server boot (verified via logs)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def admin_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")  # API returns access_token, not token
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


class TestUpdateNotificationEndpoints:
    """Tests for the new update notification endpoints"""

    def test_get_notification_returns_cached_data(self, admin_token):
        """GET /api/updates/notification should return cached notification from DB"""
        response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        # Should have update_available field
        assert "update_available" in data, "Response should contain update_available"
        
        # If update is available, should have version info
        if data.get("update_available"):
            assert "latest_version" in data, "Should have latest_version when update_available"
            assert "current_version" in data, "Should have current_version"
        
        print(f"Notification data: update_available={data.get('update_available')}, "
              f"latest_version={data.get('latest_version')}, "
              f"dismissed_version={data.get('dismissed_version')}")

    def test_dismiss_notification_sets_dismissed_version(self, admin_token):
        """POST /api/updates/notification/dismiss should set dismissed_version"""
        test_version = "0.0.0"  # Reset to show banner
        
        response = requests.post(
            f"{BASE_URL}/api/updates/notification/dismiss?version={test_version}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should contain message"
        print(f"Dismiss response: {data}")
        
        # Verify the dismissed_version was updated by fetching notification
        verify_response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        
        if verify_data.get("update_available"):
            assert verify_data.get("dismissed_version") == test_version, \
                f"Expected dismissed_version={test_version}, got {verify_data.get('dismissed_version')}"
        print(f"Verified dismissed_version: {verify_data.get('dismissed_version')}")

    def test_notification_requires_auth(self):
        """GET /api/updates/notification should require authentication"""
        response = requests.get(f"{BASE_URL}/api/updates/notification")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    def test_dismiss_requires_auth(self):
        """POST /api/updates/notification/dismiss should require authentication"""
        response = requests.post(f"{BASE_URL}/api/updates/notification/dismiss?version=1.0.0")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"


class TestExistingUpdateEndpoints:
    """Verify existing update endpoints still work"""

    def test_get_update_status(self, admin_token):
        """GET /api/updates/status should return current_version, github_repo, update_history"""
        response = requests.get(
            f"{BASE_URL}/api/updates/status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "current_version" in data, "Should have current_version"
        assert "github_repo" in data, "Should have github_repo"
        assert "update_history" in data, "Should have update_history"
        
        print(f"Update status: version={data.get('current_version')}, "
              f"repo={data.get('github_repo')}, "
              f"history_count={len(data.get('update_history', []))}")

    def test_check_for_updates_no_repo(self, admin_token):
        """GET /api/updates/check should return configured=false when no GITHUB_REPO"""
        response = requests.get(
            f"{BASE_URL}/api/updates/check",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "configured" in data, "Should have configured field"
        # Since GITHUB_REPO is not set in .env, should be False
        assert data.get("configured") == False, f"Expected configured=false, got {data.get('configured')}"
        assert "current_version" in data, "Should have current_version"
        
        print(f"Update check: configured={data.get('configured')}, "
              f"version={data.get('current_version')}, "
              f"message={data.get('message')}")


class TestBannerVisibilityLogic:
    """Test the banner visibility logic: update_available=true AND dismissed_version != latest_version"""

    def test_banner_visibility_when_dismissed_matches(self, admin_token):
        """Banner should NOT show when dismissed_version equals latest_version"""
        # Get current notification
        response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        if not data.get("update_available"):
            pytest.skip("No update available to test banner logic")
        
        latest_version = data.get("latest_version")
        
        # Dismiss with the latest version
        dismiss_response = requests.post(
            f"{BASE_URL}/api/updates/notification/dismiss?version={latest_version}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert dismiss_response.status_code == 200
        
        # Check notification again - dismissed_version should match latest_version
        verify_response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        verify_data = verify_response.json()
        
        # Banner should NOT show since dismissed_version == latest_version
        assert verify_data.get("dismissed_version") == latest_version, \
            "dismissed_version should match latest_version"
        print(f"Banner logic test: dismissed_version={verify_data.get('dismissed_version')}, "
              f"latest_version={latest_version}")

    def test_banner_visibility_when_dismissed_differs(self, admin_token):
        """Banner SHOULD show when dismissed_version differs from latest_version"""
        # Get current notification
        response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        if not data.get("update_available"):
            pytest.skip("No update available to test banner logic")
        
        # Reset dismissed_version to 0.0.0 to make banner show
        dismiss_response = requests.post(
            f"{BASE_URL}/api/updates/notification/dismiss?version=0.0.0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert dismiss_response.status_code == 200
        
        # Verify notification - dismissed_version should be 0.0.0
        verify_response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        verify_data = verify_response.json()
        
        assert verify_data.get("dismissed_version") == "0.0.0", \
            f"Expected dismissed_version=0.0.0, got {verify_data.get('dismissed_version')}"
        assert verify_data.get("dismissed_version") != verify_data.get("latest_version"), \
            "dismissed_version should differ from latest_version for banner to show"
        
        print(f"Banner SHOULD show: dismissed_version={verify_data.get('dismissed_version')}, "
              f"latest_version={verify_data.get('latest_version')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
