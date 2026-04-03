"""
Test v3.11 Bug Fixes:
1. Bug 2 fix: GET /api/telemetry/device/{device_id} includes license_id and binding_status
2. Bug 3 fix: GET /api/licensing/licenses/{id} returns token_history with used_at fields
3. Bug 1 fix: POST /api/internal/reconfigure-sync returns reconfigured=true
4. E2E: Create license → get token → register device → device appears in license detail
"""
import pytest
import requests
import os
import uuid

pytestmark = pytest.mark.integration

# Central server URL (port 8002)
CENTRAL_URL = "http://localhost:8002"
# Local backend URL
LOCAL_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://boardgame-repair.preview.emergentagent.com")

# Test credentials
SUPERADMIN_USER = "superadmin"
SUPERADMIN_PASS = "admin"


@pytest.fixture(scope="module")
def auth_token():
    """Get auth token from central server."""
    resp = requests.post(f"{CENTRAL_URL}/api/auth/login", json={
        "username": SUPERADMIN_USER,
        "password": SUPERADMIN_PASS
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for central server."""
    return {"Authorization": f"Bearer {auth_token}"}


class TestBug2DeviceDetailIncludesLicenseInfo:
    """Bug 2 fix: Device detail endpoint includes license_id and binding_status."""

    def test_device_detail_endpoint_exists(self, auth_headers):
        """Verify GET /api/telemetry/device/{device_id} endpoint exists."""
        # Get any device first
        devices_resp = requests.get(f"{CENTRAL_URL}/api/licensing/devices", headers=auth_headers)
        assert devices_resp.status_code == 200
        devices = devices_resp.json()
        
        if not devices:
            pytest.skip("No devices available for testing")
        
        device_id = devices[0]["id"]
        resp = requests.get(f"{CENTRAL_URL}/api/telemetry/device/{device_id}", headers=auth_headers)
        assert resp.status_code == 200, f"Device detail failed: {resp.text}"

    def test_device_detail_includes_license_id_field(self, auth_headers):
        """Verify device detail response includes license_id field."""
        devices_resp = requests.get(f"{CENTRAL_URL}/api/licensing/devices", headers=auth_headers)
        devices = devices_resp.json()
        
        if not devices:
            pytest.skip("No devices available for testing")
        
        device_id = devices[0]["id"]
        resp = requests.get(f"{CENTRAL_URL}/api/telemetry/device/{device_id}", headers=auth_headers)
        data = resp.json()
        
        assert "license_id" in data, f"license_id field missing from device detail. Keys: {data.keys()}"

    def test_device_detail_includes_binding_status_field(self, auth_headers):
        """Verify device detail response includes binding_status field."""
        devices_resp = requests.get(f"{CENTRAL_URL}/api/licensing/devices", headers=auth_headers)
        devices = devices_resp.json()
        
        if not devices:
            pytest.skip("No devices available for testing")
        
        device_id = devices[0]["id"]
        resp = requests.get(f"{CENTRAL_URL}/api/telemetry/device/{device_id}", headers=auth_headers)
        data = resp.json()
        
        assert "binding_status" in data, f"binding_status field missing from device detail. Keys: {data.keys()}"

    def test_bound_device_shows_license_id(self, auth_headers):
        """Verify a bound device shows its license_id."""
        # Find a device with license_id set
        devices_resp = requests.get(f"{CENTRAL_URL}/api/licensing/devices", headers=auth_headers)
        devices = devices_resp.json()
        
        bound_device = None
        for d in devices:
            if d.get("license_id"):
                bound_device = d
                break
        
        if not bound_device:
            pytest.skip("No bound devices available for testing")
        
        device_id = bound_device["id"]
        resp = requests.get(f"{CENTRAL_URL}/api/telemetry/device/{device_id}", headers=auth_headers)
        data = resp.json()
        
        assert data["license_id"] is not None, "Bound device should have license_id set"
        assert data["binding_status"] == "bound", f"Expected binding_status='bound', got '{data['binding_status']}'"


class TestBug3LicenseDetailTokenHistory:
    """Bug 3 fix: License detail returns token_history with used_at fields."""

    def test_license_detail_includes_token_history(self, auth_headers):
        """Verify license detail includes token_history array."""
        # Get any license
        licenses_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses", headers=auth_headers)
        assert licenses_resp.status_code == 200
        licenses = licenses_resp.json()
        
        if not licenses:
            pytest.skip("No licenses available for testing")
        
        license_id = licenses[0]["id"]
        resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        
        assert "token_history" in data, f"token_history field missing. Keys: {data.keys()}"
        assert isinstance(data["token_history"], list), "token_history should be a list"

    def test_token_history_entries_have_used_at_field(self, auth_headers):
        """Verify token_history entries include used_at field."""
        # Find a license with token history
        licenses_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses", headers=auth_headers)
        licenses = licenses_resp.json()
        
        for lic in licenses:
            detail_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{lic['id']}", headers=auth_headers)
            detail = detail_resp.json()
            
            if detail.get("token_history") and len(detail["token_history"]) > 0:
                token = detail["token_history"][0]
                assert "used_at" in token, f"used_at field missing from token. Keys: {token.keys()}"
                assert "status" in token, f"status field missing from token. Keys: {token.keys()}"
                return
        
        pytest.skip("No licenses with token history found")

    def test_used_token_has_used_at_set(self, auth_headers):
        """Verify a used token has used_at timestamp set."""
        # Find a license with a used token
        licenses_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses", headers=auth_headers)
        licenses = licenses_resp.json()
        
        for lic in licenses:
            detail_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{lic['id']}", headers=auth_headers)
            detail = detail_resp.json()
            
            for token in detail.get("token_history", []):
                if token.get("status") == "used":
                    assert token["used_at"] is not None, "Used token should have used_at timestamp"
                    print(f"Found used token: used_at={token['used_at']}")
                    return
        
        pytest.skip("No used tokens found in any license")

    def test_license_with_used_token_shows_no_active_token(self, auth_headers):
        """Verify license with all tokens used shows active_token=null."""
        licenses_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses", headers=auth_headers)
        licenses = licenses_resp.json()
        
        for lic in licenses:
            detail_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{lic['id']}", headers=auth_headers)
            detail = detail_resp.json()
            
            # Check if all tokens are used/revoked
            history = detail.get("token_history", [])
            if history and all(t.get("used_at") or t.get("is_revoked") for t in history):
                assert detail.get("active_token") is None, "License with all used tokens should have active_token=null"
                print(f"License {lic['id']} has all tokens used, active_token is correctly null")
                return
        
        pytest.skip("No license with all tokens used found")


class TestBug1ReconfigureSync:
    """Bug 1 fix: POST /api/internal/reconfigure-sync endpoint."""

    def test_reconfigure_sync_endpoint_exists(self):
        """Verify POST /api/internal/reconfigure-sync endpoint exists."""
        resp = requests.post(f"{LOCAL_URL}/api/internal/reconfigure-sync")
        # Should return 200 even without config
        assert resp.status_code == 200, f"Reconfigure endpoint failed: {resp.status_code} - {resp.text}"

    def test_reconfigure_sync_returns_expected_fields(self):
        """Verify reconfigure-sync returns reconfigured field."""
        resp = requests.post(f"{LOCAL_URL}/api/internal/reconfigure-sync")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "reconfigured" in data, f"reconfigured field missing. Keys: {data.keys()}"

    def test_reconfigure_sync_with_config_returns_services(self):
        """Verify reconfigure-sync returns services list when config exists."""
        resp = requests.post(f"{LOCAL_URL}/api/internal/reconfigure-sync")
        assert resp.status_code == 200
        data = resp.json()
        
        if data.get("reconfigured"):
            assert "services" in data, "Should return services list when reconfigured=true"
            services = data["services"]
            # Check expected services
            expected_services = ["telemetry_sync", "config_sync", "action_poller", "offline_queue", "ws_push_client"]
            for svc in expected_services:
                if svc in services:
                    print(f"Service {svc} was reconfigured")
        else:
            # No config - that's OK for this test
            print(f"Reconfigure returned: {data}")


class TestE2ELicenseDeviceFlow:
    """E2E: Create license → get token → register device → verify in license detail."""

    @pytest.fixture
    def test_customer_id(self, auth_headers):
        """Get or create a test customer."""
        resp = requests.get(f"{CENTRAL_URL}/api/licensing/customers", headers=auth_headers)
        customers = resp.json()
        if customers:
            return customers[0]["id"]
        
        # Create one
        resp = requests.post(f"{CENTRAL_URL}/api/licensing/customers", headers=auth_headers, json={
            "name": f"TEST_Customer_{uuid.uuid4().hex[:8]}",
            "contact_email": "test@example.com"
        })
        assert resp.status_code == 200
        return resp.json()["id"]

    @pytest.fixture
    def test_location_id(self, auth_headers, test_customer_id):
        """Get or create a test location."""
        resp = requests.get(f"{CENTRAL_URL}/api/licensing/locations?customer_id={test_customer_id}", headers=auth_headers)
        locations = resp.json()
        if locations:
            return locations[0]["id"]
        
        # Create one
        resp = requests.post(f"{CENTRAL_URL}/api/licensing/locations", headers=auth_headers, json={
            "customer_id": test_customer_id,
            "name": f"TEST_Location_{uuid.uuid4().hex[:8]}"
        })
        assert resp.status_code == 200
        return resp.json()["id"]

    def test_e2e_create_license_get_token_register_device(self, auth_headers, test_customer_id, test_location_id):
        """Full E2E flow: create license, get token, register device, verify."""
        # 1. Create license
        license_resp = requests.post(f"{CENTRAL_URL}/api/licensing/licenses", headers=auth_headers, json={
            "customer_id": test_customer_id,
            "location_id": test_location_id,
            "plan_type": "standard",
            "max_devices": 2,
            "notes": "TEST_E2E_BugFix"
        })
        assert license_resp.status_code == 200, f"Create license failed: {license_resp.text}"
        license_data = license_resp.json()
        license_id = license_data["id"]
        print(f"Created license: {license_id}")

        # 2. Get token
        token_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}/token", headers=auth_headers)
        assert token_resp.status_code == 200, f"Get token failed: {token_resp.text}"
        token_data = token_resp.json()
        raw_token = token_data.get("raw_token")
        assert raw_token, "raw_token not returned"
        print(f"Got token: {raw_token[:20]}...")

        # 3. Register device
        install_id = f"TEST_INSTALL_{uuid.uuid4().hex[:12]}"
        device_name = f"TEST_Device_{uuid.uuid4().hex[:8]}"
        
        reg_resp = requests.post(f"{CENTRAL_URL}/api/register-device", json={
            "token": raw_token,
            "install_id": install_id,
            "device_name": device_name
        })
        assert reg_resp.status_code == 200, f"Register device failed: {reg_resp.text}"
        reg_data = reg_resp.json()
        device_id = reg_data["device_id"]
        print(f"Registered device: {device_id}")

        # Verify registration response includes license_id
        assert reg_data.get("license_id") == license_id, f"Registration should return license_id. Got: {reg_data.get('license_id')}"
        assert reg_data.get("binding_status") == "bound", f"Registration should return binding_status=bound. Got: {reg_data.get('binding_status')}"

        # 4. Verify device appears in license detail
        detail_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}", headers=auth_headers)
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        
        assert detail["device_count"] == 1, f"Expected device_count=1, got {detail['device_count']}"
        assert len(detail["devices"]) == 1, f"Expected 1 device in list, got {len(detail['devices'])}"
        assert detail["devices"][0]["id"] == device_id, "Device ID mismatch"
        print(f"Device appears in license detail with device_count={detail['device_count']}")

        # 5. Verify device detail shows license_id
        dev_detail_resp = requests.get(f"{CENTRAL_URL}/api/telemetry/device/{device_id}", headers=auth_headers)
        assert dev_detail_resp.status_code == 200
        dev_detail = dev_detail_resp.json()
        
        assert dev_detail["license_id"] == license_id, f"Device detail should show license_id. Got: {dev_detail.get('license_id')}"
        assert dev_detail["binding_status"] == "bound", f"Device detail should show binding_status=bound. Got: {dev_detail.get('binding_status')}"
        print(f"Device detail shows license_id={dev_detail['license_id']}, binding_status={dev_detail['binding_status']}")

        # 6. Verify token is now used
        detail_resp2 = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}", headers=auth_headers)
        detail2 = detail_resp2.json()
        
        assert detail2.get("active_token") is None, "After registration, active_token should be null"
        assert len(detail2["token_history"]) > 0, "token_history should have entries"
        
        used_token = next((t for t in detail2["token_history"] if t.get("status") == "used"), None)
        assert used_token is not None, "Should have a used token in history"
        assert used_token["used_at"] is not None, "Used token should have used_at timestamp"
        print(f"Token marked as used: used_at={used_token['used_at']}")

        # Cleanup: archive the license
        requests.delete(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}?action=archive", headers=auth_headers)
        print("Test cleanup: license archived")

    def test_max_devices_enforcement(self, auth_headers, test_customer_id, test_location_id):
        """Verify max_devices limit is enforced."""
        # Create license with max_devices=1
        license_resp = requests.post(f"{CENTRAL_URL}/api/licensing/licenses", headers=auth_headers, json={
            "customer_id": test_customer_id,
            "location_id": test_location_id,
            "plan_type": "basic",
            "max_devices": 1,
            "notes": "TEST_MaxDevices"
        })
        assert license_resp.status_code == 200
        license_id = license_resp.json()["id"]

        # Get token and register first device
        token_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}/token", headers=auth_headers)
        raw_token = token_resp.json()["raw_token"]
        
        reg1_resp = requests.post(f"{CENTRAL_URL}/api/register-device", json={
            "token": raw_token,
            "install_id": f"TEST_INSTALL_1_{uuid.uuid4().hex[:8]}",
            "device_name": "Device 1"
        })
        assert reg1_resp.status_code == 200, "First device should register successfully"

        # Try to register second device - should fail
        token_resp2 = requests.post(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}/regenerate-token", headers=auth_headers, json={})
        raw_token2 = token_resp2.json()["raw_token"]
        
        reg2_resp = requests.post(f"{CENTRAL_URL}/api/register-device", json={
            "token": raw_token2,
            "install_id": f"TEST_INSTALL_2_{uuid.uuid4().hex[:8]}",
            "device_name": "Device 2"
        })
        assert reg2_resp.status_code == 403, f"Second device should be rejected. Got: {reg2_resp.status_code}"
        assert "Gerätelimit" in reg2_resp.json().get("detail", ""), "Error should mention device limit"
        print(f"max_devices enforcement working: {reg2_resp.json()['detail']}")

        # Cleanup
        requests.delete(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}?action=archive", headers=auth_headers)


class TestFrontendTokenStates:
    """Verify frontend TokenSection states are supported by API."""

    def test_license_without_token_history(self, auth_headers):
        """State 1: No token ever created - token_history should be empty."""
        # Create a fresh license without getting a token
        customers_resp = requests.get(f"{CENTRAL_URL}/api/licensing/customers", headers=auth_headers)
        if not customers_resp.json():
            pytest.skip("No customers available")
        customer_id = customers_resp.json()[0]["id"]
        
        license_resp = requests.post(f"{CENTRAL_URL}/api/licensing/licenses", headers=auth_headers, json={
            "customer_id": customer_id,
            "plan_type": "test",
            "max_devices": 1,
            "notes": "TEST_NoToken"
        })
        assert license_resp.status_code == 200
        license_id = license_resp.json()["id"]

        # Check detail - should have empty token_history
        detail_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}", headers=auth_headers)
        detail = detail_resp.json()
        
        assert detail.get("active_token") is None, "New license should have no active_token"
        assert detail.get("token_history") == [], "New license should have empty token_history"
        print("State 1 verified: No token created - token_history is empty")

        # Cleanup
        requests.delete(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}?action=archive", headers=auth_headers)

    def test_license_with_active_token(self, auth_headers):
        """State 3: Active token exists."""
        customers_resp = requests.get(f"{CENTRAL_URL}/api/licensing/customers", headers=auth_headers)
        if not customers_resp.json():
            pytest.skip("No customers available")
        customer_id = customers_resp.json()[0]["id"]
        
        license_resp = requests.post(f"{CENTRAL_URL}/api/licensing/licenses", headers=auth_headers, json={
            "customer_id": customer_id,
            "plan_type": "test",
            "max_devices": 1,
            "notes": "TEST_ActiveToken"
        })
        license_id = license_resp.json()["id"]

        # Create a token
        token_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}/token", headers=auth_headers)
        assert token_resp.status_code == 200

        # Check detail - should have active_token
        detail_resp = requests.get(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}", headers=auth_headers)
        detail = detail_resp.json()
        
        assert detail.get("active_token") is not None, "Should have active_token after creation"
        assert detail["active_token"]["status"] == "active", "Token status should be 'active'"
        assert len(detail.get("token_history", [])) > 0, "token_history should have the token"
        print("State 3 verified: Active token exists")

        # Cleanup
        requests.delete(f"{CENTRAL_URL}/api/licensing/licenses/{license_id}?action=archive", headers=auth_headers)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
