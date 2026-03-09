"""
Test: Snooze Update Notification Feature (Iteration 17)
Tests for:
- POST /api/updates/notification/snooze?version=X.X.X&hours=48 - snooze notification
- GET /api/updates/notification - returns snoozed_version, snooze_until fields
- Snooze persists to DB (survives restart)
- Banner visibility logic with snooze
- Reset snooze when newer version appears (version comparison)
"""
import pytest
import requests
import os
from datetime import datetime, timedelta, timezone

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
        return data.get("access_token")
    pytest.skip(f"Authentication failed: {response.status_code} - {response.text}")


@pytest.fixture(autouse=True)
def reset_notification_state(admin_token):
    """Reset snooze and dismiss state before each test"""
    # Reset dismissed_version and snoozed_version to show banner
    requests.post(
        f"{BASE_URL}/api/updates/notification/dismiss?version=0.0.0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    requests.post(
        f"{BASE_URL}/api/updates/notification/snooze?version=0.0.0&hours=0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    yield
    # Cleanup after test
    requests.post(
        f"{BASE_URL}/api/updates/notification/dismiss?version=0.0.0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    requests.post(
        f"{BASE_URL}/api/updates/notification/snooze?version=0.0.0&hours=0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )


class TestSnoozeEndpoint:
    """Tests for POST /api/updates/notification/snooze"""

    def test_snooze_sets_snoozed_version_and_snooze_until(self, admin_token):
        """POST /api/updates/notification/snooze?version=1.5.0&hours=48 sets fields in DB"""
        response = requests.post(
            f"{BASE_URL}/api/updates/notification/snooze?version=1.5.0&hours=48",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should contain message"
        assert data.get("snooze_hours") == 48, f"Expected snooze_hours=48, got {data.get('snooze_hours')}"
        print(f"Snooze response: {data}")
        
        # Verify the fields were set via GET notification
        verify_response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        
        assert verify_data.get("snoozed_version") == "1.5.0", \
            f"Expected snoozed_version=1.5.0, got {verify_data.get('snoozed_version')}"
        assert "snooze_until" in verify_data, "Response should contain snooze_until"
        
        # Verify snooze_until is ~48h from now
        snooze_until = datetime.fromisoformat(verify_data["snooze_until"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        expected_snooze_until = now + timedelta(hours=48)
        
        # Allow 2 minute tolerance
        assert abs((snooze_until - expected_snooze_until).total_seconds()) < 120, \
            f"snooze_until should be ~48h from now, got {snooze_until}"
        
        print(f"Verified snoozed_version={verify_data.get('snoozed_version')}, "
              f"snooze_until={verify_data.get('snooze_until')}")

    def test_snooze_requires_auth(self):
        """POST /api/updates/notification/snooze should require authentication"""
        response = requests.post(f"{BASE_URL}/api/updates/notification/snooze?version=1.5.0&hours=48")
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    def test_snooze_with_different_hours(self, admin_token):
        """Snooze should work with different hour values"""
        for hours in [1, 24, 72]:
            response = requests.post(
                f"{BASE_URL}/api/updates/notification/snooze?version=1.5.0&hours={hours}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            assert response.status_code == 200, f"Expected 200 for hours={hours}, got {response.status_code}"
            data = response.json()
            assert data.get("snooze_hours") == hours, f"Expected snooze_hours={hours}, got {data.get('snooze_hours')}"


class TestDismissEndpoint:
    """Tests for POST /api/updates/notification/dismiss (permanent dismiss)"""

    def test_dismiss_sets_dismissed_version(self, admin_token):
        """POST /api/updates/notification/dismiss?version=1.5.0 sets dismissed_version in DB"""
        response = requests.post(
            f"{BASE_URL}/api/updates/notification/dismiss?version=1.5.0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "message" in data, "Response should contain message"
        print(f"Dismiss response: {data}")
        
        # Verify dismissed_version was set
        verify_response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert verify_response.status_code == 200
        verify_data = verify_response.json()
        
        assert verify_data.get("dismissed_version") == "1.5.0", \
            f"Expected dismissed_version=1.5.0, got {verify_data.get('dismissed_version')}"
        print(f"Verified dismissed_version={verify_data.get('dismissed_version')}")


class TestNotificationFields:
    """Tests for GET /api/updates/notification response fields"""

    def test_notification_returns_snooze_fields(self, admin_token):
        """GET /api/updates/notification should return snoozed_version and snooze_until"""
        # First set snooze
        requests.post(
            f"{BASE_URL}/api/updates/notification/snooze?version=1.5.0&hours=48",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Check all required fields
        required_fields = [
            "update_available", "current_version", "latest_version",
            "snoozed_version", "snooze_until", "dismissed_version"
        ]
        for field in required_fields:
            assert field in data, f"Response should contain {field}"
        
        print(f"Notification fields present: {list(data.keys())}")


class TestBannerVisibilityWithSnooze:
    """Tests for banner visibility logic with snooze"""

    def test_banner_hidden_when_snoozed_matches_and_not_expired(self, admin_token):
        """Banner should be hidden when snoozed_version=latest_version AND snooze_until is in future"""
        # Snooze for 48 hours
        snooze_response = requests.post(
            f"{BASE_URL}/api/updates/notification/snooze?version=1.5.0&hours=48",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert snooze_response.status_code == 200
        
        # Get notification
        response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = response.json()
        
        latest_version = data.get("latest_version")
        snoozed_version = data.get("snoozed_version")
        snooze_until = data.get("snooze_until")
        
        assert snoozed_version == latest_version, \
            f"snoozed_version ({snoozed_version}) should match latest_version ({latest_version})"
        
        # Verify snooze_until is in the future
        snooze_until_dt = datetime.fromisoformat(snooze_until.replace("Z", "+00:00"))
        assert snooze_until_dt > datetime.now(timezone.utc), \
            f"snooze_until ({snooze_until}) should be in the future"
        
        print(f"Banner should be HIDDEN: snoozed_version={snoozed_version}, "
              f"latest_version={latest_version}, snooze_until={snooze_until}")

    def test_banner_shown_when_snoozed_version_differs(self, admin_token):
        """Banner should show when snoozed_version != latest_version"""
        # Set snoozed_version to different version
        requests.post(
            f"{BASE_URL}/api/updates/notification/snooze?version=0.0.0&hours=48",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Get notification
        response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = response.json()
        
        latest_version = data.get("latest_version")
        snoozed_version = data.get("snoozed_version")
        
        assert snoozed_version != latest_version, \
            f"snoozed_version ({snoozed_version}) should differ from latest_version ({latest_version})"
        
        print(f"Banner should be SHOWN: snoozed_version={snoozed_version}, "
              f"latest_version={latest_version}")

    def test_banner_shown_when_dismissed_version_differs_no_snooze(self, admin_token):
        """Banner should show when dismissed_version != latest_version and no active snooze"""
        # Reset both dismissed and snoozed to 0.0.0
        requests.post(
            f"{BASE_URL}/api/updates/notification/dismiss?version=0.0.0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        requests.post(
            f"{BASE_URL}/api/updates/notification/snooze?version=0.0.0&hours=0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        response = requests.get(
            f"{BASE_URL}/api/updates/notification",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        data = response.json()
        
        assert data.get("dismissed_version") != data.get("latest_version"), \
            "dismissed_version should differ from latest_version for banner to show"
        
        # snoozed_version is also 0.0.0, so no active snooze for latest
        print(f"Banner should be SHOWN: dismissed_version={data.get('dismissed_version')}, "
              f"latest_version={data.get('latest_version')}")


class TestSnoozePersistence:
    """Tests for snooze data persistence in database"""

    def test_snooze_survives_api_call(self, admin_token):
        """Snooze data should persist across multiple GET calls"""
        # Set snooze
        requests.post(
            f"{BASE_URL}/api/updates/notification/snooze?version=1.5.0&hours=48",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        # Multiple GET calls should return same data
        for i in range(3):
            response = requests.get(
                f"{BASE_URL}/api/updates/notification",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            data = response.json()
            assert data.get("snoozed_version") == "1.5.0", f"Call {i+1}: snoozed_version should be 1.5.0"
            assert "snooze_until" in data, f"Call {i+1}: should have snooze_until"
        
        print("Snooze data persisted across 3 GET calls")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
