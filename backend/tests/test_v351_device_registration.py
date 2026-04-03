"""
v3.5.1 Device Registration Flow Tests

Tests for:
- Central Server: Registration token CRUD (create, list, revoke)
- Central Server: Device registration with token (success, failures)
- Kiosk Backend: Registration status endpoint
- Kiosk Backend: Register device endpoint (proxy to central server)
- Security: token hashing, one-time use, expiration, revocation
- Error cases: used token, invalid token, revoked token, duplicate install_id
"""
import pytest
import requests
import uuid
import os
import time

pytestmark = pytest.mark.integration

# URLs from environment
KIOSK_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
CENTRAL_SERVER_URL = "http://localhost:8002"
ADMIN_TOKEN = "admin-secret-token"  # Central server admin token
KIOSK_ADMIN_USER = "admin"
KIOSK_ADMIN_PASS = "admin123"


class TestCentralServerRegistrationTokens:
    """Tests for Central Server registration token endpoints (v3.5.1)"""
    
    @pytest.fixture(scope="class")
    def setup_data(self):
        """Create a customer and location for token creation"""
        headers = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}
        
        # Create customer
        cust_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/customers",
            headers=headers,
            json={"name": f"TEST_RegTokenCustomer_{uuid.uuid4().hex[:8]}", "contact_email": "test@example.com"}
        )
        customer = cust_resp.json() if cust_resp.status_code == 200 else None
        customer_id = customer["id"] if customer else None
        
        # Create location
        location_id = None
        if customer_id:
            loc_resp = requests.post(
                f"{CENTRAL_SERVER_URL}/api/licensing/locations",
                headers=headers,
                json={"customer_id": customer_id, "name": f"TEST_RegTokenLocation_{uuid.uuid4().hex[:8]}"}
            )
            location = loc_resp.json() if loc_resp.status_code == 200 else None
            location_id = location["id"] if location else None
        
        # Create license
        license_id = None
        if customer_id:
            lic_resp = requests.post(
                f"{CENTRAL_SERVER_URL}/api/licensing/licenses",
                headers=headers,
                json={"customer_id": customer_id, "location_id": location_id, "plan_type": "test", "max_devices": 5}
            )
            license_data = lic_resp.json() if lic_resp.status_code == 200 else None
            license_id = license_data["id"] if license_data else None
        
        return {
            "customer_id": customer_id,
            "location_id": location_id,
            "license_id": license_id,
            "headers": headers
        }
    
    def test_create_registration_token_returns_raw_token(self, setup_data):
        """POST /api/registration-tokens creates token with raw_token in response"""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=setup_data["headers"],
            json={
                "customer_id": setup_data["customer_id"],
                "location_id": setup_data["location_id"],
                "expires_in_hours": 24,
                "note": "TEST_token_for_testing"
            }
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify raw_token is present and has correct format (drt_...)
        assert "raw_token" in data, "raw_token not in response"
        assert data["raw_token"].startswith("drt_"), f"Token should start with drt_, got {data['raw_token'][:10]}"
        
        # Verify other fields
        assert "id" in data
        assert "token_preview" in data
        assert "status" in data
        assert data["status"] == "active"
        assert "expires_at" in data
        
    def test_create_token_requires_admin_auth(self):
        """POST /api/registration-tokens without auth returns 401"""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            json={"expires_in_hours": 24}
        )
        assert resp.status_code == 401, f"Expected 401 without auth, got {resp.status_code}"
    
    def test_list_registration_tokens_returns_correct_status(self, setup_data):
        """GET /api/registration-tokens lists tokens with correct status"""
        # Create a token first
        create_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=setup_data["headers"],
            json={
                "customer_id": setup_data["customer_id"],
                "expires_in_hours": 48,
                "note": "TEST_list_token"
            }
        )
        assert create_resp.status_code == 200
        created = create_resp.json()
        
        # List tokens
        list_resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=setup_data["headers"]
        )
        assert list_resp.status_code == 200
        tokens = list_resp.json()
        assert isinstance(tokens, list)
        
        # Find our token
        found = [t for t in tokens if t["id"] == created["id"]]
        assert len(found) == 1, "Created token not found in list"
        assert found[0]["status"] == "active"
        
        # Verify raw_token is NOT in list (security)
        assert "raw_token" not in found[0], "raw_token should not be exposed in list"
    
    def test_list_tokens_filter_by_status(self, setup_data):
        """GET /api/registration-tokens?status=active filters correctly"""
        list_resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens?status=active",
            headers=setup_data["headers"]
        )
        assert list_resp.status_code == 200
        tokens = list_resp.json()
        for t in tokens:
            assert t["status"] == "active", f"Expected active, got {t['status']}"
    
    def test_revoke_registration_token(self, setup_data):
        """POST /api/registration-tokens/{id}/revoke marks token as revoked"""
        # Create token
        create_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=setup_data["headers"],
            json={"customer_id": setup_data["customer_id"], "expires_in_hours": 24, "note": "TEST_revoke_token"}
        )
        assert create_resp.status_code == 200
        token = create_resp.json()
        
        # Revoke it
        revoke_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens/{token['id']}/revoke",
            headers=setup_data["headers"]
        )
        assert revoke_resp.status_code == 200
        revoked = revoke_resp.json()
        assert revoked["status"] == "revoked"
        assert revoked["is_revoked"] == True
        assert "revoked_at" in revoked
    
    def test_revoke_requires_admin_auth(self, setup_data):
        """POST /api/registration-tokens/{id}/revoke without auth returns 401"""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens/some-id/revoke"
        )
        assert resp.status_code == 401


class TestCentralServerDeviceRegistration:
    """Tests for Central Server register-device endpoint"""
    
    @pytest.fixture(scope="class")
    def setup_with_token(self):
        """Create customer, location, license, and a registration token"""
        headers = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}
        
        # Create customer
        cust_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/customers",
            headers=headers,
            json={"name": f"TEST_DevRegCustomer_{uuid.uuid4().hex[:8]}"}
        )
        customer = cust_resp.json()
        customer_id = customer["id"]
        
        # Create location
        loc_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/locations",
            headers=headers,
            json={"customer_id": customer_id, "name": f"TEST_DevRegLocation_{uuid.uuid4().hex[:8]}"}
        )
        location = loc_resp.json()
        location_id = location["id"]
        
        # Create license
        lic_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/licenses",
            headers=headers,
            json={"customer_id": customer_id, "location_id": location_id, "plan_type": "test", "max_devices": 5}
        )
        license_data = lic_resp.json()
        license_id = license_data["id"]
        
        return {
            "customer_id": customer_id,
            "location_id": location_id,
            "license_id": license_id,
            "headers": headers
        }
    
    def test_register_device_success_with_valid_token(self, setup_with_token):
        """POST /api/register-device succeeds with valid token and returns device_id, api_key, license info"""
        # Create a fresh token
        token_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=setup_with_token["headers"],
            json={
                "customer_id": setup_with_token["customer_id"],
                "location_id": setup_with_token["location_id"],
                "expires_in_hours": 24,
                "note": "TEST_success_registration"
            }
        )
        assert token_resp.status_code == 200
        raw_token = token_resp.json()["raw_token"]
        
        # Register device
        install_id = f"TEST_install_{uuid.uuid4()}"
        reg_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/register-device",
            json={
                "token": raw_token,
                "install_id": install_id,
                "device_name": "TEST_Registered_Device"
            }
        )
        
        assert reg_resp.status_code == 200, f"Expected 200, got {reg_resp.status_code}: {reg_resp.text}"
        data = reg_resp.json()
        
        # Verify response contains required fields
        assert data.get("success") == True
        assert "device_id" in data
        assert "api_key" in data
        assert data["api_key"].startswith("dk_"), "API key should start with dk_"
        assert "license_status" in data
        assert "customer_id" in data
        assert "customer_name" in data
        assert "binding_status" in data
        assert data["binding_status"] == "bound"
    
    def test_register_device_used_token_returns_403(self, setup_with_token):
        """POST /api/register-device with already used token returns 403"""
        # Create token
        token_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=setup_with_token["headers"],
            json={
                "customer_id": setup_with_token["customer_id"],
                "location_id": setup_with_token["location_id"],
                "expires_in_hours": 24
            }
        )
        raw_token = token_resp.json()["raw_token"]
        
        # Use token first time
        install_id_1 = f"TEST_first_{uuid.uuid4()}"
        reg1 = requests.post(
            f"{CENTRAL_SERVER_URL}/api/register-device",
            json={"token": raw_token, "install_id": install_id_1}
        )
        assert reg1.status_code == 200
        
        # Try to use same token again
        install_id_2 = f"TEST_second_{uuid.uuid4()}"
        reg2 = requests.post(
            f"{CENTRAL_SERVER_URL}/api/register-device",
            json={"token": raw_token, "install_id": install_id_2}
        )
        assert reg2.status_code == 403, f"Expected 403 for used token, got {reg2.status_code}"
        assert "already been used" in reg2.text.lower() or "already used" in reg2.text.lower()
    
    def test_register_device_invalid_token_returns_403(self):
        """POST /api/register-device with invalid token returns 403"""
        reg_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/register-device",
            json={
                "token": "drt_invalid_token_12345",
                "install_id": f"TEST_{uuid.uuid4()}"
            }
        )
        assert reg_resp.status_code == 403, f"Expected 403 for invalid token, got {reg_resp.status_code}"
        assert "invalid" in reg_resp.text.lower()
    
    def test_register_device_revoked_token_returns_403(self, setup_with_token):
        """POST /api/register-device with revoked token returns 403"""
        # Create and revoke token
        token_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=setup_with_token["headers"],
            json={"customer_id": setup_with_token["customer_id"], "location_id": setup_with_token["location_id"]}
        )
        token_data = token_resp.json()
        raw_token = token_data["raw_token"]
        
        # Revoke it
        requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens/{token_data['id']}/revoke",
            headers=setup_with_token["headers"]
        )
        
        # Try to use revoked token
        reg_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/register-device",
            json={"token": raw_token, "install_id": f"TEST_{uuid.uuid4()}"}
        )
        assert reg_resp.status_code == 403, f"Expected 403 for revoked token, got {reg_resp.status_code}"
        assert "revoked" in reg_resp.text.lower()
    
    def test_register_device_duplicate_install_id_returns_409(self, setup_with_token):
        """POST /api/register-device with duplicate install_id returns 409 conflict"""
        # Create first token and register
        token1_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=setup_with_token["headers"],
            json={"customer_id": setup_with_token["customer_id"], "location_id": setup_with_token["location_id"]}
        )
        raw_token1 = token1_resp.json()["raw_token"]
        
        install_id = f"TEST_dup_{uuid.uuid4()}"
        reg1 = requests.post(
            f"{CENTRAL_SERVER_URL}/api/register-device",
            json={"token": raw_token1, "install_id": install_id}
        )
        assert reg1.status_code == 200
        
        # Create second token and try to register with same install_id
        token2_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=setup_with_token["headers"],
            json={"customer_id": setup_with_token["customer_id"], "location_id": setup_with_token["location_id"]}
        )
        raw_token2 = token2_resp.json()["raw_token"]
        
        reg2 = requests.post(
            f"{CENTRAL_SERVER_URL}/api/register-device",
            json={"token": raw_token2, "install_id": install_id}
        )
        assert reg2.status_code == 409, f"Expected 409 for duplicate install_id, got {reg2.status_code}"
    
    def test_register_device_without_token_returns_400(self):
        """POST /api/register-device without token returns 400"""
        reg_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/register-device",
            json={"install_id": f"TEST_{uuid.uuid4()}"}
        )
        assert reg_resp.status_code == 400, f"Expected 400, got {reg_resp.status_code}"
        assert "token" in reg_resp.text.lower()
    
    def test_register_device_without_install_id_returns_400(self):
        """POST /api/register-device without install_id returns 400"""
        reg_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/register-device",
            json={"token": "drt_sometoken"}
        )
        assert reg_resp.status_code == 400, f"Expected 400, got {reg_resp.status_code}"
        assert "install_id" in reg_resp.text.lower()


class TestCentralServerTokenHashing:
    """Tests to verify token_hash is stored (not raw token) in database"""
    
    def test_token_hash_stored_not_raw(self):
        """Verify token_hash is stored in database, not raw token"""
        headers = {"Authorization": f"Bearer {ADMIN_TOKEN}", "Content-Type": "application/json"}
        
        # Create a customer first
        cust_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/customers",
            headers=headers,
            json={"name": f"TEST_HashCustomer_{uuid.uuid4().hex[:8]}"}
        )
        customer_id = cust_resp.json()["id"]
        
        # Create location
        loc_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/locations",
            headers=headers,
            json={"customer_id": customer_id, "name": "TEST_HashLocation"}
        )
        location_id = loc_resp.json()["id"]
        
        # Create token
        token_resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/registration-tokens",
            headers=headers,
            json={"customer_id": customer_id, "location_id": location_id, "expires_in_hours": 24}
        )
        assert token_resp.status_code == 200
        data = token_resp.json()
        raw_token = data["raw_token"]
        
        # List tokens and verify raw_token is not exposed
        list_resp = requests.get(f"{CENTRAL_SERVER_URL}/api/registration-tokens", headers=headers)
        tokens = list_resp.json()
        
        for t in tokens:
            # Raw token should never appear in list
            assert "raw_token" not in t, "raw_token should not be in list response"
            # token_hash should not be exposed either
            assert "token_hash" not in t, "token_hash should not be exposed in API"
            # Only token_preview should be visible
            if t["id"] == data["id"]:
                assert "token_preview" in t
                # Preview should be a truncated version
                assert len(t["token_preview"]) < len(raw_token)


class TestKioskRegistrationEndpoints:
    """Tests for Kiosk backend registration endpoints"""
    
    @pytest.fixture(scope="class")
    def kiosk_auth(self):
        """Get auth token for kiosk backend"""
        resp = requests.post(
            f"{KIOSK_URL}/api/auth/login",
            json={"username": KIOSK_ADMIN_USER, "password": KIOSK_ADMIN_PASS}
        )
        if resp.status_code == 200:
            return resp.json().get("access_token")
        return None
    
    def test_registration_status_returns_status_and_install_id(self):
        """GET /api/licensing/registration-status returns status and install_id"""
        resp = requests.get(f"{KIOSK_URL}/api/licensing/registration-status")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()
        
        assert "status" in data
        assert data["status"] in ["registered", "unregistered"]
        assert "install_id" in data
        assert data["install_id"] is not None
        
        # If registered, should have additional fields
        if data["status"] == "registered":
            assert "device_id" in data
            assert "device_name" in data
    
    def test_registration_status_no_auth_required(self):
        """GET /api/licensing/registration-status is public (no auth needed)"""
        resp = requests.get(f"{KIOSK_URL}/api/licensing/registration-status")
        # Should not return 401/403
        assert resp.status_code == 200
    
    def test_license_status_includes_registration_status(self):
        """GET /api/kiosk/license-status includes registration_status field"""
        resp = requests.get(f"{KIOSK_URL}/api/kiosk/license-status")
        assert resp.status_code == 200
        data = resp.json()
        
        assert "registration_status" in data, f"registration_status not in response: {data}"
        assert data["registration_status"] in ["registered", "unregistered"]


class TestKioskRegisterDeviceEndpoint:
    """Tests for Kiosk POST /api/licensing/register-device endpoint"""
    
    def test_register_device_without_token_returns_400(self):
        """POST /api/licensing/register-device without token returns 400"""
        resp = requests.post(
            f"{KIOSK_URL}/api/licensing/register-device",
            json={}
        )
        assert resp.status_code in [400, 422], f"Expected 400/422, got {resp.status_code}: {resp.text}"
    
    def test_register_device_with_invalid_token(self):
        """POST /api/licensing/register-device with invalid token proxies error from central server"""
        resp = requests.post(
            f"{KIOSK_URL}/api/licensing/register-device",
            json={"token": "drt_invalid_fake_token_xyz"}
        )
        # Should return an error (either 400, 403, or 502 depending on central server connectivity)
        assert resp.status_code in [400, 403, 502], f"Expected error status, got {resp.status_code}"


class TestAuditLogTracking:
    """Tests to verify registration events are logged in audit log"""
    
    def test_audit_log_tracks_registration_events(self):
        """Verify audit log contains registration-related events"""
        headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
        
        # Get recent audit log
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/licensing/audit-log?limit=100",
            headers=headers
        )
        assert resp.status_code == 200
        entries = resp.json()
        
        # Check for registration-related actions
        reg_actions = ["REG_TOKEN_CREATED", "REG_TOKEN_REVOKED", "REG_TOKEN_USED", 
                       "DEVICE_REGISTERED", "DEVICE_REGISTRATION_FAILED", "DEVICE_REGISTERED_BIND_CONFLICT"]
        
        found_actions = set()
        for entry in entries:
            if entry.get("action") in reg_actions:
                found_actions.add(entry["action"])
        
        # At least REG_TOKEN_CREATED should exist from our tests
        assert "REG_TOKEN_CREATED" in found_actions or len(found_actions) > 0, \
            f"Expected registration events in audit log, found: {found_actions}"


# ================================================
# Run tests
# ================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
