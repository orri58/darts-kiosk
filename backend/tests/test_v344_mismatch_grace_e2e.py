"""
E2E Tests for v3.4.4 — Mismatch Grace + Tracking

Tests the following via actual API calls:
1. GET /api/licensing/binding-settings returns binding_grace_hours (auth required)
2. POST /api/licensing/binding-settings updates binding_grace_hours (auth required)
3. GET /api/licensing/devices returns mismatch_detected_at and previous_install_id fields
4. GET /api/kiosk/license-status returns status with binding information
5. POST /api/licensing/devices/{id}/rebind clears mismatch_detected_at
6. Regression: existing license CRUD endpoints work
7. Regression: no_license = fail-open
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://boardgame-repair.preview.emergentagent.com')


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token for admin user."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=10
    )
    if response.status_code != 200:
        pytest.skip("Could not authenticate - skipping authenticated tests")
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for API calls."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestBindingSettingsEndpoint:
    """Test GET/POST /api/licensing/binding-settings"""

    def test_get_binding_settings_requires_auth(self):
        """GET /api/licensing/binding-settings without auth returns 401."""
        response = requests.get(f"{BASE_URL}/api/licensing/binding-settings", timeout=10)
        assert response.status_code == 401

    def test_get_binding_settings_returns_grace_hours(self, auth_headers):
        """GET /api/licensing/binding-settings returns binding_grace_hours."""
        response = requests.get(
            f"{BASE_URL}/api/licensing/binding-settings",
            headers=auth_headers, timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert "binding_grace_hours" in data
        assert isinstance(data["binding_grace_hours"], int)
        assert data["binding_grace_hours"] >= 0

    def test_post_binding_settings_requires_auth(self):
        """POST /api/licensing/binding-settings without auth returns 401."""
        response = requests.post(
            f"{BASE_URL}/api/licensing/binding-settings",
            json={"binding_grace_hours": 48}, timeout=10
        )
        assert response.status_code == 401

    def test_post_binding_settings_updates_grace_hours(self, auth_headers):
        """POST /api/licensing/binding-settings updates binding_grace_hours."""
        # Update to 72
        response = requests.post(
            f"{BASE_URL}/api/licensing/binding-settings",
            headers=auth_headers,
            json={"binding_grace_hours": 72}, timeout=10
        )
        assert response.status_code == 200
        assert response.json()["binding_grace_hours"] == 72

        # Verify persisted
        response = requests.get(
            f"{BASE_URL}/api/licensing/binding-settings",
            headers=auth_headers, timeout=10
        )
        assert response.json()["binding_grace_hours"] == 72

        # Reset to 48
        response = requests.post(
            f"{BASE_URL}/api/licensing/binding-settings",
            headers=auth_headers,
            json={"binding_grace_hours": 48}, timeout=10
        )
        assert response.status_code == 200

    def test_post_binding_settings_validates_input(self, auth_headers):
        """POST /api/licensing/binding-settings validates input."""
        # Missing field
        response = requests.post(
            f"{BASE_URL}/api/licensing/binding-settings",
            headers=auth_headers,
            json={}, timeout=10
        )
        assert response.status_code == 400

        # Negative value
        response = requests.post(
            f"{BASE_URL}/api/licensing/binding-settings",
            headers=auth_headers,
            json={"binding_grace_hours": -1}, timeout=10
        )
        assert response.status_code == 400


class TestDevicesV344Fields:
    """Test v3.4.4 device fields."""

    def test_devices_return_mismatch_fields(self, auth_headers):
        """GET /api/licensing/devices returns mismatch_detected_at and previous_install_id."""
        response = requests.get(
            f"{BASE_URL}/api/licensing/devices",
            headers=auth_headers, timeout=10
        )
        assert response.status_code == 200
        devices = response.json()
        assert len(devices) >= 1

        # Check first device has v3.4.4 fields
        device = devices[0]
        assert "mismatch_detected_at" in device
        assert "previous_install_id" in device
        assert "binding_status" in device
        assert "first_seen_at" in device
        assert "last_seen_at" in device


class TestKioskLicenseStatus:
    """Test GET /api/kiosk/license-status"""

    def test_kiosk_license_status_is_public(self):
        """GET /api/kiosk/license-status is public (no auth required)."""
        response = requests.get(f"{BASE_URL}/api/kiosk/license-status", timeout=10)
        assert response.status_code == 200

    def test_kiosk_license_status_returns_binding_info(self):
        """GET /api/kiosk/license-status returns binding_status and install_id."""
        response = requests.get(f"{BASE_URL}/api/kiosk/license-status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "install_id" in data
        # binding_status may or may not be present depending on license config
        if "binding_status" in data:
            assert data["binding_status"] in ["bound", "unbound", "first_bind", "mismatch_grace", "mismatch_expired", None]


class TestRebindEndpoint:
    """Test POST /api/licensing/devices/{id}/rebind"""

    def test_rebind_requires_auth(self):
        """POST rebind without auth returns 401."""
        response = requests.post(
            f"{BASE_URL}/api/licensing/devices/fake-id/rebind",
            json={"new_install_id": "test"}, timeout=10
        )
        assert response.status_code == 401

    def test_rebind_requires_new_install_id(self, auth_headers):
        """POST rebind without new_install_id returns 400."""
        # Get a device ID first
        devices_response = requests.get(
            f"{BASE_URL}/api/licensing/devices",
            headers=auth_headers, timeout=10
        )
        devices = devices_response.json()
        if not devices:
            pytest.skip("No devices to test rebind")
        device_id = devices[0]["id"]

        response = requests.post(
            f"{BASE_URL}/api/licensing/devices/{device_id}/rebind",
            headers=auth_headers,
            json={}, timeout=10
        )
        assert response.status_code == 400

    def test_rebind_returns_404_for_nonexistent_device(self, auth_headers):
        """POST rebind for nonexistent device returns 404."""
        response = requests.post(
            f"{BASE_URL}/api/licensing/devices/nonexistent-id/rebind",
            headers=auth_headers,
            json={"new_install_id": "test"}, timeout=10
        )
        assert response.status_code == 404

    def test_rebind_clears_mismatch_and_sets_previous(self, auth_headers):
        """POST rebind clears mismatch_detected_at and sets previous_install_id."""
        # Get device identity
        identity_response = requests.get(
            f"{BASE_URL}/api/licensing/device-identity",
            headers=auth_headers, timeout=10
        )
        install_id = identity_response.json().get("install_id")
        if not install_id:
            pytest.skip("No device identity")

        # Get bound device
        devices_response = requests.get(
            f"{BASE_URL}/api/licensing/devices",
            headers=auth_headers, timeout=10
        )
        devices = devices_response.json()
        bound_device = next((d for d in devices if d.get("install_id")), None)
        if not bound_device:
            pytest.skip("No bound device to test")

        # Rebind
        response = requests.post(
            f"{BASE_URL}/api/licensing/devices/{bound_device['id']}/rebind",
            headers=auth_headers,
            json={"new_install_id": install_id}, timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data["binding_status"] == "bound"
        assert data["new_install_id"] == install_id

        # Verify device state
        devices_response = requests.get(
            f"{BASE_URL}/api/licensing/devices",
            headers=auth_headers, timeout=10
        )
        device = next(d for d in devices_response.json() if d["id"] == bound_device["id"])
        assert device["binding_status"] == "bound"
        assert device["mismatch_detected_at"] is None
        # previous_install_id should be set
        assert device["previous_install_id"] is not None


class TestRegressionLicenseCRUD:
    """Regression tests for existing license CRUD endpoints."""

    def test_list_customers(self, auth_headers):
        """GET /api/licensing/customers returns list."""
        response = requests.get(
            f"{BASE_URL}/api/licensing/customers",
            headers=auth_headers, timeout=10
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_locations(self, auth_headers):
        """GET /api/licensing/locations returns list."""
        response = requests.get(
            f"{BASE_URL}/api/licensing/locations",
            headers=auth_headers, timeout=10
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_licenses(self, auth_headers):
        """GET /api/licensing/licenses returns list."""
        response = requests.get(
            f"{BASE_URL}/api/licensing/licenses",
            headers=auth_headers, timeout=10
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_dashboard(self, auth_headers):
        """GET /api/licensing/dashboard returns stats."""
        response = requests.get(
            f"{BASE_URL}/api/licensing/dashboard",
            headers=auth_headers, timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert "customers" in data
        assert "locations" in data
        assert "devices" in data
        assert "licenses_total" in data

    def test_license_status_authed(self, auth_headers):
        """GET /api/licensing/status returns status."""
        response = requests.get(
            f"{BASE_URL}/api/licensing/status",
            headers=auth_headers, timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert "status" in data


class TestSessionAllowedPolicy:
    """Test is_session_allowed logic (no_license = fail-open)."""

    def test_no_license_failopen(self):
        """no_license status allows sessions (fail-open policy)."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "no_license"}) is True

    def test_mismatch_grace_allows(self):
        """mismatch_grace binding allows sessions."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "mismatch_grace"}) is True

    def test_mismatch_expired_blocks(self):
        """mismatch_expired binding blocks sessions."""
        from backend.services.license_service import LicenseValidationService
        svc = LicenseValidationService()
        assert svc.is_session_allowed({"status": "active", "binding_status": "mismatch_expired"}) is False
