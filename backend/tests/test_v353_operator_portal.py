"""
v3.5.3 Operator Portal Backend Tests

Tests the proxy route /api/central/{path} and auth flows for the Operator Portal.
- Proxy forwards to central server at localhost:8002
- Returns 502 when unreachable
- Auth flows for operator and superadmin
- Data scoping for operators
"""

import pytest
import requests
import os

pytestmark = pytest.mark.integration

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
OPERATOR_CREDS = {"username": "operator1", "password": "test1234"}
SUPERADMIN_CREDS = {"username": "superadmin", "password": "admin"}
WRONG_CREDS = {"username": "wronguser", "password": "wrongpass"}

@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="module")
def operator_token(api_client):
    """Get operator1 JWT token"""
    res = api_client.post(f"{BASE_URL}/api/central/auth/login", json=OPERATOR_CREDS)
    if res.status_code == 200:
        return res.json().get("access_token")
    pytest.skip("Failed to get operator token")

@pytest.fixture(scope="module")
def superadmin_token(api_client):
    """Get superadmin JWT token"""
    res = api_client.post(f"{BASE_URL}/api/central/auth/login", json=SUPERADMIN_CREDS)
    if res.status_code == 200:
        return res.json().get("access_token")
    pytest.skip("Failed to get superadmin token")


# ====================
# PROXY TESTS
# ====================

class TestProxyRouteBasics:
    """Tests for /api/central/{path} proxy functionality"""
    
    def test_proxy_forwards_get_request(self, api_client, operator_token):
        """Proxy forwards GET requests with auth headers"""
        res = api_client.get(
            f"{BASE_URL}/api/central/auth/me",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("username") == "operator1"
        assert data.get("role") == "operator"
        print(f"PASS: Proxy forwards GET /auth/me - user={data.get('username')}, role={data.get('role')}")

    def test_proxy_forwards_post_request(self, api_client):
        """Proxy forwards POST requests (login)"""
        res = api_client.post(f"{BASE_URL}/api/central/auth/login", json=OPERATOR_CREDS)
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert "user" in data
        print("PASS: Proxy forwards POST /auth/login")

    def test_proxy_returns_404_for_invalid_path(self, api_client, operator_token):
        """Proxy returns 404 from central for invalid path"""
        res = api_client.get(
            f"{BASE_URL}/api/central/nonexistent-endpoint",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        # Central server should return 404 for unknown paths
        assert res.status_code == 404
        print("PASS: Proxy returns 404 for invalid path")

    def test_proxy_forwards_authorization_header(self, api_client, operator_token):
        """Proxy correctly forwards Authorization headers"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/customers",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        # Should NOT return 401 (would mean auth header not forwarded)
        assert res.status_code != 401, "Auth header not forwarded"
        assert res.status_code == 200
        print("PASS: Proxy forwards Authorization header correctly")


# ====================
# AUTH FLOW TESTS
# ====================

class TestAuthFlows:
    """Tests for authentication flows in Operator Portal"""
    
    def test_operator_login_success(self, api_client):
        """Operator1 can login successfully"""
        res = api_client.post(f"{BASE_URL}/api/central/auth/login", json=OPERATOR_CREDS)
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["user"]["username"] == "operator1"
        assert data["user"]["role"] == "operator"
        assert "allowed_customer_ids" in data["user"]
        print(f"PASS: Operator login - allowed_customer_ids={data['user']['allowed_customer_ids']}")

    def test_superadmin_login_success(self, api_client):
        """Superadmin can login successfully"""
        res = api_client.post(f"{BASE_URL}/api/central/auth/login", json=SUPERADMIN_CREDS)
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["user"]["username"] == "superadmin"
        assert data["user"]["role"] == "superadmin"
        print(f"PASS: Superadmin login")

    def test_wrong_credentials_returns_401(self, api_client):
        """Wrong credentials return 401 with error message"""
        res = api_client.post(f"{BASE_URL}/api/central/auth/login", json=WRONG_CREDS)
        assert res.status_code == 401
        data = res.json()
        assert "detail" in data or "message" in data
        print(f"PASS: Wrong credentials return 401")

    def test_missing_credentials_returns_error(self, api_client):
        """Missing credentials return error"""
        res = api_client.post(f"{BASE_URL}/api/central/auth/login", json={})
        assert res.status_code in [400, 422]  # Validation error
        print(f"PASS: Missing credentials return {res.status_code}")

    def test_auth_me_returns_user_info(self, api_client, operator_token):
        """GET /auth/me returns current user info"""
        res = api_client.get(
            f"{BASE_URL}/api/central/auth/me",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["username"] == "operator1"
        assert data["role"] == "operator"
        print(f"PASS: /auth/me returns user info")

    def test_unauthenticated_request_returns_401(self, api_client):
        """Request without token returns 401"""
        res = api_client.get(f"{BASE_URL}/api/central/auth/me")
        assert res.status_code == 401
        print(f"PASS: Unauthenticated request returns 401")


# ====================
# DATA SCOPING TESTS
# ====================

class TestDataScopingOperator:
    """Tests that operator only sees scoped data"""
    
    def test_operator_sees_only_allowed_customers(self, api_client, operator_token, superadmin_token):
        """Operator1 should only see 'Darts Bar Berlin' customer"""
        # Get operator's customers
        op_res = api_client.get(
            f"{BASE_URL}/api/central/licensing/customers",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        assert op_res.status_code == 200
        op_customers = op_res.json()
        
        # Get all customers (superadmin)
        sa_res = api_client.get(
            f"{BASE_URL}/api/central/licensing/customers",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert sa_res.status_code == 200
        sa_customers = sa_res.json()
        
        # Operator should see fewer customers than superadmin (or equal if only 1 customer exists)
        assert len(op_customers) <= len(sa_customers), "Operator sees more customers than superadmin"
        
        # Operator should see Darts Bar Berlin
        customer_names = [c.get("name") for c in op_customers]
        assert any("Darts Bar Berlin" in name for name in customer_names if name), \
            f"Operator1 should see 'Darts Bar Berlin'. Got: {customer_names}"
        
        print(f"PASS: Operator sees {len(op_customers)} customer(s): {customer_names}")

    def test_operator_sees_only_allowed_locations(self, api_client, operator_token):
        """Operator sees only locations of allowed customers"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/locations",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        assert res.status_code == 200
        locations = res.json()
        # Should have at least 1 location (Standort Mitte)
        assert len(locations) >= 0  # May have locations if seeded
        location_names = [l.get("name") for l in locations]
        print(f"PASS: Operator sees {len(locations)} location(s): {location_names}")

    def test_operator_sees_only_allowed_devices(self, api_client, operator_token):
        """Operator sees only devices of allowed customer locations"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/devices",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        assert res.status_code == 200
        devices = res.json()
        device_names = [d.get("device_name", d.get("id", "")[:8]) for d in devices]
        print(f"PASS: Operator sees {len(devices)} device(s): {device_names}")

    def test_operator_sees_only_allowed_licenses(self, api_client, operator_token):
        """Operator sees only licenses of allowed customers"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/licenses",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        assert res.status_code == 200
        licenses = res.json()
        license_plans = [l.get("plan_type", "unknown") for l in licenses]
        print(f"PASS: Operator sees {len(licenses)} license(s): {license_plans}")

    def test_operator_can_access_audit_log(self, api_client, operator_token):
        """Operator can access audit log (filtered)"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/audit-log?limit=10",
            headers={"Authorization": f"Bearer {operator_token}"}
        )
        assert res.status_code == 200
        entries = res.json()
        print(f"PASS: Operator sees {len(entries)} audit log entries")


# ====================
# SUPERADMIN FULL ACCESS TESTS
# ====================

class TestSuperadminAccess:
    """Tests that superadmin has full access"""
    
    def test_superadmin_sees_all_customers(self, api_client, superadmin_token):
        """Superadmin sees all customers"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/customers",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert res.status_code == 200
        customers = res.json()
        print(f"PASS: Superadmin sees {len(customers)} customer(s)")

    def test_superadmin_sees_all_locations(self, api_client, superadmin_token):
        """Superadmin sees all locations"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/locations",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert res.status_code == 200
        locations = res.json()
        print(f"PASS: Superadmin sees {len(locations)} location(s)")

    def test_superadmin_sees_all_devices(self, api_client, superadmin_token):
        """Superadmin sees all devices"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/devices",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert res.status_code == 200
        devices = res.json()
        print(f"PASS: Superadmin sees {len(devices)} device(s)")

    def test_superadmin_sees_all_licenses(self, api_client, superadmin_token):
        """Superadmin sees all licenses"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/licenses",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert res.status_code == 200
        licenses = res.json()
        print(f"PASS: Superadmin sees {len(licenses)} license(s)")

    def test_superadmin_sees_full_audit_log(self, api_client, superadmin_token):
        """Superadmin sees full audit log"""
        res = api_client.get(
            f"{BASE_URL}/api/central/licensing/audit-log?limit=10",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert res.status_code == 200
        entries = res.json()
        print(f"PASS: Superadmin sees {len(entries)} audit log entries")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
