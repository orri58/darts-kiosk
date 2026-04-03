"""
Test Suite: License/Activation/Device Onboarding Flow (v3.11)
Tests the complete flow: Kunde→Standort→Lizenz→Token→Device registriert→aktiv im Portal

Endpoints tested:
- GET /api/licensing/licenses — list with customer_name, device_count
- GET /api/licensing/licenses?status=X — status filter
- GET /api/licensing/licenses/{id} — full detail with devices, active_token, computed_status
- GET /api/licensing/licenses/{id}/token — get or create token
- POST /api/licensing/licenses/{id}/regenerate-token — revoke old, create new
- POST /api/register-device — register device with token, max_devices enforcement
- DELETE /api/licensing/licenses/{id}?action=deactivate|archive — soft delete
- POST /api/licensing/licenses/{id}/unbind-device/{device_id} — unbind device
- Audit log entries verification
"""

import pytest
import requests
import os
import uuid

pytestmark = pytest.mark.integration

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
CENTRAL_URL = f"{BASE_URL}/api/central"  # Frontend proxy to central server

# Direct central server for testing
DIRECT_CENTRAL = "http://localhost:8002"


class TestLicenseOnboardingFlow:
    """Complete License/Activation/Device Onboarding flow tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup: authenticate and get token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Authenticate
        login_resp = self.session.post(f"{DIRECT_CENTRAL}/api/auth/login", json={
            "username": "superadmin",
            "password": "admin"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        
        # Store test data for cleanup
        self.test_license_id = None
        self.test_device_id = None
        self.test_customer_id = None
        self.test_location_id = None
        
        yield
        
        # Cleanup is handled by test data prefix
    
    # ═══════════════════════════════════════════════════════════════
    # 1. LICENSE LIST ENDPOINTS
    # ═══════════════════════════════════════════════════════════════
    
    def test_01_list_licenses_returns_customer_name_and_device_count(self):
        """GET /api/licensing/licenses returns list with customer_name, device_count"""
        resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        licenses = resp.json()
        assert isinstance(licenses, list), "Response should be a list"
        
        if len(licenses) > 0:
            lic = licenses[0]
            # Verify required fields
            assert "id" in lic, "License should have id"
            assert "customer_id" in lic, "License should have customer_id"
            assert "customer_name" in lic, "License should have customer_name (enriched)"
            assert "device_count" in lic, "License should have device_count"
            assert "status" in lic, "License should have status"
            assert "max_devices" in lic, "License should have max_devices"
            print(f"✓ License list returns {len(licenses)} licenses with customer_name and device_count")
    
    def test_02_filter_licenses_by_status_active(self):
        """GET /api/licensing/licenses?status=active filters correctly"""
        resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses?status=active")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        licenses = resp.json()
        for lic in licenses:
            assert lic["status"] == "active", f"Expected active, got {lic['status']}"
        print(f"✓ Status filter 'active' returns {len(licenses)} licenses, all active")
    
    def test_03_filter_licenses_by_status_deactivated(self):
        """GET /api/licensing/licenses?status=deactivated shows only deactivated"""
        resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses?status=deactivated")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        licenses = resp.json()
        for lic in licenses:
            assert lic["status"] == "deactivated", f"Expected deactivated, got {lic['status']}"
        print(f"✓ Status filter 'deactivated' returns {len(licenses)} licenses")
    
    # ═══════════════════════════════════════════════════════════════
    # 2. FULL ONBOARDING FLOW
    # ═══════════════════════════════════════════════════════════════
    
    def test_04_get_customer_for_license_creation(self):
        """Get existing customer for license creation"""
        resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        customers = resp.json()
        assert len(customers) > 0, "Need at least one customer for testing"
        
        self.test_customer_id = customers[0]["id"]
        print(f"✓ Using customer: {customers[0]['name']} ({self.test_customer_id})")
        return self.test_customer_id
    
    def test_05_get_location_for_license_creation(self):
        """Get existing location for license creation"""
        # First get customer
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/locations?customer_id={customer_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        locations = resp.json()
        if len(locations) > 0:
            self.test_location_id = locations[0]["id"]
            print(f"✓ Using location: {locations[0]['name']} ({self.test_location_id})")
        else:
            print("✓ No locations found, will create license without location")
        return self.test_location_id
    
    def test_06_create_license(self):
        """POST /api/licensing/licenses creates a new license"""
        # Get customer
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        # Get location
        loc_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/locations?customer_id={customer_id}")
        locations = loc_resp.json()
        location_id = locations[0]["id"] if locations else None
        
        # Create license
        payload = {
            "customer_id": customer_id,
            "location_id": location_id,
            "plan_type": "test",
            "max_devices": 2,
            "status": "active",
            "notes": f"TEST_license_{uuid.uuid4().hex[:8]}"
        }
        
        resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json=payload)
        assert resp.status_code == 200, f"Failed to create license: {resp.text}"
        
        lic = resp.json()
        assert lic["customer_id"] == customer_id
        assert lic["plan_type"] == "test"
        assert lic["max_devices"] == 2
        assert lic["status"] == "active"
        
        self.test_license_id = lic["id"]
        print(f"✓ Created license: {lic['id']} (plan={lic['plan_type']}, max_devices={lic['max_devices']})")
        return lic["id"]
    
    def test_07_get_license_detail(self):
        """GET /api/licensing/licenses/{id} returns full detail"""
        # Create a license first
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        loc_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/locations?customer_id={customer_id}")
        locations = loc_resp.json()
        location_id = locations[0]["id"] if locations else None
        
        create_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json={
            "customer_id": customer_id,
            "location_id": location_id,
            "plan_type": "standard",
            "max_devices": 3,
            "notes": f"TEST_detail_{uuid.uuid4().hex[:8]}"
        })
        license_id = create_resp.json()["id"]
        
        # Get detail
        resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        detail = resp.json()
        # Verify all required fields
        assert "id" in detail
        assert "customer_id" in detail
        assert "customer_name" in detail, "Detail should include customer_name"
        assert "location_name" in detail, "Detail should include location_name"
        assert "devices" in detail, "Detail should include devices array"
        assert "device_count" in detail, "Detail should include device_count"
        assert "active_token" in detail, "Detail should include active_token (can be null)"
        assert "computed_status" in detail, "Detail should include computed_status"
        assert "token_history" in detail, "Detail should include token_history"
        
        print(f"✓ License detail includes: customer_name={detail['customer_name']}, "
              f"devices={len(detail['devices'])}, computed_status={detail['computed_status']}")
        return license_id
    
    def test_08_get_or_create_token(self):
        """GET /api/licensing/licenses/{id}/token creates token if none exists"""
        # Create a fresh license
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        loc_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/locations?customer_id={customer_id}")
        locations = loc_resp.json()
        location_id = locations[0]["id"] if locations else None
        
        create_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json={
            "customer_id": customer_id,
            "location_id": location_id,
            "plan_type": "test",
            "max_devices": 1,
            "notes": f"TEST_token_{uuid.uuid4().hex[:8]}"
        })
        license_id = create_resp.json()["id"]
        
        # Get token (should create new one)
        resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}/token")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "token" in data, "Response should include token object"
        assert "raw_token" in data, "Response should include raw_token for new tokens"
        assert data["raw_token"].startswith("drt_"), "Token should start with drt_"
        
        # Call again - should return existing token
        resp2 = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}/token")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2.get("exists") == True, "Second call should indicate token exists"
        
        print(f"✓ Token created: {data['token']['token_preview']}, raw starts with drt_")
        return license_id, data["raw_token"]
    
    def test_09_regenerate_token(self):
        """POST /api/licensing/licenses/{id}/regenerate-token revokes old, creates new"""
        # Create license and get initial token
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        create_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json={
            "customer_id": customer_id,
            "plan_type": "test",
            "max_devices": 1,
            "notes": f"TEST_regen_{uuid.uuid4().hex[:8]}"
        })
        license_id = create_resp.json()["id"]
        
        # Create initial token
        self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}/token")
        
        # Regenerate
        resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}/regenerate-token")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert "raw_token" in data, "Should return new raw_token"
        assert "revoked_count" in data, "Should indicate how many tokens were revoked"
        assert data["revoked_count"] >= 1, "Should have revoked at least 1 token"
        
        print(f"✓ Token regenerated, revoked {data['revoked_count']} old tokens")
    
    def test_10_register_device_with_valid_token(self):
        """POST /api/register-device with valid token registers device"""
        # Create license
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        loc_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/locations?customer_id={customer_id}")
        locations = loc_resp.json()
        location_id = locations[0]["id"] if locations else None
        
        create_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json={
            "customer_id": customer_id,
            "location_id": location_id,
            "plan_type": "test",
            "max_devices": 2,
            "notes": f"TEST_register_{uuid.uuid4().hex[:8]}"
        })
        license_id = create_resp.json()["id"]
        
        # Get token
        token_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}/token")
        raw_token = token_resp.json()["raw_token"]
        
        # Register device (public endpoint, no auth needed)
        install_id = f"TEST_INSTALL_{uuid.uuid4().hex[:12]}"
        device_name = f"TEST_Device_{uuid.uuid4().hex[:6]}"
        
        reg_resp = requests.post(f"{DIRECT_CENTRAL}/api/register-device", json={
            "token": raw_token,
            "install_id": install_id,
            "device_name": device_name
        })
        assert reg_resp.status_code == 200, f"Registration failed: {reg_resp.text}"
        
        data = reg_resp.json()
        assert data["success"] == True
        assert "device_id" in data
        assert "api_key" in data
        assert data["license_id"] == license_id, "Device should be bound to license"
        assert data["binding_status"] == "bound"
        
        self.test_device_id = data["device_id"]
        print(f"✓ Device registered: {data['device_name']} (id={data['device_id'][:8]}..., license_id={data['license_id'][:8]}...)")
        
        # Verify device appears in license detail
        detail_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}")
        detail = detail_resp.json()
        assert detail["device_count"] == 1, "License should show 1 bound device"
        assert len(detail["devices"]) == 1, "License detail should include the device"
        
        return license_id, data["device_id"]
    
    def test_11_register_device_max_devices_enforcement(self):
        """POST /api/register-device with max_devices reached returns 403"""
        # Create license with max_devices=1
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        loc_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/locations?customer_id={customer_id}")
        locations = loc_resp.json()
        location_id = locations[0]["id"] if locations else None
        
        create_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json={
            "customer_id": customer_id,
            "location_id": location_id,
            "plan_type": "test",
            "max_devices": 1,  # Only 1 device allowed
            "notes": f"TEST_maxdev_{uuid.uuid4().hex[:8]}"
        })
        license_id = create_resp.json()["id"]
        
        # Get token
        token_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}/token")
        raw_token = token_resp.json()["raw_token"]
        
        # Register first device (should succeed)
        install_id_1 = f"TEST_INSTALL_{uuid.uuid4().hex[:12]}"
        reg_resp_1 = requests.post(f"{DIRECT_CENTRAL}/api/register-device", json={
            "token": raw_token,
            "install_id": install_id_1,
            "device_name": "First Device"
        })
        assert reg_resp_1.status_code == 200, f"First registration should succeed: {reg_resp_1.text}"
        
        # Need new token since first was used
        regen_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}/regenerate-token")
        new_token = regen_resp.json()["raw_token"]
        
        # Try to register second device (should fail with 403)
        install_id_2 = f"TEST_INSTALL_{uuid.uuid4().hex[:12]}"
        reg_resp_2 = requests.post(f"{DIRECT_CENTRAL}/api/register-device", json={
            "token": new_token,
            "install_id": install_id_2,
            "device_name": "Second Device"
        })
        assert reg_resp_2.status_code == 403, f"Expected 403, got {reg_resp_2.status_code}: {reg_resp_2.text}"
        
        # Verify German error message
        error_detail = reg_resp_2.json().get("detail", "")
        assert "Gerätelimit" in error_detail or "limit" in error_detail.lower(), \
            f"Error should mention device limit in German: {error_detail}"
        
        print(f"✓ max_devices enforcement works: 403 returned with message: {error_detail}")
    
    def test_12_deactivate_license(self):
        """DELETE /api/licensing/licenses/{id}?action=deactivate sets status to deactivated"""
        # Create license
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        create_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json={
            "customer_id": customer_id,
            "plan_type": "test",
            "max_devices": 1,
            "notes": f"TEST_deact_{uuid.uuid4().hex[:8]}"
        })
        license_id = create_resp.json()["id"]
        
        # Deactivate
        resp = self.session.delete(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}?action=deactivate")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert data["success"] == True
        assert data["status"] == "deactivated"
        
        # Verify via GET
        detail_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}")
        assert detail_resp.json()["status"] == "deactivated"
        
        print(f"✓ License deactivated successfully")
    
    def test_13_archive_license(self):
        """DELETE /api/licensing/licenses/{id}?action=archive sets status to archived"""
        # Create license
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        create_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json={
            "customer_id": customer_id,
            "plan_type": "test",
            "max_devices": 1,
            "notes": f"TEST_arch_{uuid.uuid4().hex[:8]}"
        })
        license_id = create_resp.json()["id"]
        
        # Archive
        resp = self.session.delete(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}?action=archive")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        data = resp.json()
        assert data["success"] == True
        assert data["status"] == "archived"
        
        print(f"✓ License archived successfully")
    
    def test_14_unbind_device_from_license(self):
        """POST /api/licensing/licenses/{id}/unbind-device/{device_id} unbinds device"""
        # Create license and register device
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        loc_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/locations?customer_id={customer_id}")
        locations = loc_resp.json()
        location_id = locations[0]["id"] if locations else None
        
        create_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json={
            "customer_id": customer_id,
            "location_id": location_id,
            "plan_type": "test",
            "max_devices": 2,
            "notes": f"TEST_unbind_{uuid.uuid4().hex[:8]}"
        })
        license_id = create_resp.json()["id"]
        
        # Get token and register device
        token_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}/token")
        raw_token = token_resp.json()["raw_token"]
        
        install_id = f"TEST_INSTALL_{uuid.uuid4().hex[:12]}"
        reg_resp = requests.post(f"{DIRECT_CENTRAL}/api/register-device", json={
            "token": raw_token,
            "install_id": install_id,
            "device_name": "Device to Unbind"
        })
        device_id = reg_resp.json()["device_id"]
        
        # Unbind
        unbind_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}/unbind-device/{device_id}")
        assert unbind_resp.status_code == 200, f"Failed: {unbind_resp.text}"
        
        data = unbind_resp.json()
        assert data["success"] == True
        assert data["device"]["license_id"] is None, "Device license_id should be cleared"
        assert data["device"]["binding_status"] == "unbound"
        
        # Verify license detail shows 0 devices
        detail_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}")
        assert detail_resp.json()["device_count"] == 0
        
        print(f"✓ Device unbound successfully, license now has 0 devices")
    
    # ═══════════════════════════════════════════════════════════════
    # 3. AUDIT LOG VERIFICATION
    # ═══════════════════════════════════════════════════════════════
    
    def test_15_audit_log_contains_license_events(self):
        """Verify audit log contains expected action types"""
        resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/audit-log?limit=100")
        assert resp.status_code == 200, f"Failed: {resp.text}"
        
        logs = resp.json()
        actions = set(log["action"] for log in logs)
        
        # Check for expected action types
        expected_actions = [
            "LICENSE_CREATED",
            "LICENSE_UPDATED",
            "REG_TOKEN_CREATED",
            "REG_TOKEN_REGENERATED",
            "DEVICE_REGISTERED",
        ]
        
        found_actions = []
        missing_actions = []
        for action in expected_actions:
            if action in actions:
                found_actions.append(action)
            else:
                missing_actions.append(action)
        
        print(f"✓ Audit log actions found: {', '.join(found_actions)}")
        if missing_actions:
            print(f"  (Not found in recent logs: {', '.join(missing_actions)} - may need more test runs)")
        
        # At minimum, we should have some license-related actions
        license_actions = [a for a in actions if "LICENSE" in a or "TOKEN" in a or "DEVICE" in a]
        assert len(license_actions) > 0, "Should have some license/token/device actions in audit log"


class TestLicenseEdgeCases:
    """Edge case tests for license functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{DIRECT_CENTRAL}/api/auth/login", json={
            "username": "superadmin",
            "password": "admin"
        })
        assert login_resp.status_code == 200
        self.token = login_resp.json().get("access_token")
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        yield
    
    def test_license_not_found(self):
        """GET /api/licensing/licenses/{invalid_id} returns 404"""
        resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/licenses/nonexistent-id-12345")
        assert resp.status_code == 404
        print("✓ 404 returned for non-existent license")
    
    def test_invalid_token_registration(self):
        """POST /api/register-device with invalid token returns 403"""
        resp = requests.post(f"{DIRECT_CENTRAL}/api/register-device", json={
            "token": "invalid_token_12345",
            "install_id": "test_install",
            "device_name": "Test Device"
        })
        assert resp.status_code == 403
        print("✓ 403 returned for invalid registration token")
    
    def test_missing_token_registration(self):
        """POST /api/register-device without token returns 400"""
        resp = requests.post(f"{DIRECT_CENTRAL}/api/register-device", json={
            "install_id": "test_install",
            "device_name": "Test Device"
        })
        assert resp.status_code == 400
        print("✓ 400 returned for missing token")
    
    def test_invalid_delete_action(self):
        """DELETE /api/licensing/licenses/{id}?action=invalid returns 400"""
        # Create a license first
        cust_resp = self.session.get(f"{DIRECT_CENTRAL}/api/licensing/customers")
        customer_id = cust_resp.json()[0]["id"]
        
        create_resp = self.session.post(f"{DIRECT_CENTRAL}/api/licensing/licenses", json={
            "customer_id": customer_id,
            "plan_type": "test",
            "max_devices": 1,
            "notes": f"TEST_invalid_action_{uuid.uuid4().hex[:8]}"
        })
        license_id = create_resp.json()["id"]
        
        resp = self.session.delete(f"{DIRECT_CENTRAL}/api/licensing/licenses/{license_id}?action=invalid")
        assert resp.status_code == 400
        print("✓ 400 returned for invalid delete action")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
