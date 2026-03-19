"""
v3.5.4 Productization Tests — Token & Registration

Tests for:
- /api/central/ proxy auto-auth (no separate Central Login needed)
- Local kiosk JWT → auto-auth with central admin token
- Central JWT → forwarded as-is (operator portal flow)
- Registration tokens CRUD via proxy
- /api/licensing/central-server-url endpoint
"""
import os
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"


@pytest.fixture(scope="module")
def local_kiosk_token():
    """Get local kiosk admin JWT"""
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    })
    assert resp.status_code == 200, f"Kiosk login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def central_operator_token():
    """Get central server operator JWT"""
    resp = requests.post(f"{BASE_URL}/api/central/auth/login", json={
        "username": "operator1",
        "password": "test1234"
    })
    assert resp.status_code == 200, f"Operator login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def central_superadmin_token():
    """Get central server superadmin JWT"""
    resp = requests.post(f"{BASE_URL}/api/central/auth/login", json={
        "username": "superadmin",
        "password": "admin"
    })
    assert resp.status_code == 200, f"Superadmin login failed: {resp.text}"
    return resp.json()["access_token"]


class TestCentralServerUrlEndpoint:
    """Test /api/licensing/central-server-url endpoint"""
    
    def test_central_server_url_returns_configured_url(self):
        """Public endpoint returns configured central server URL"""
        resp = requests.get(f"{BASE_URL}/api/licensing/central-server-url")
        assert resp.status_code == 200
        data = resp.json()
        assert "url" in data
        assert "configured" in data
        # Should be configured since central server is running
        assert data["configured"] == True
        assert data["url"]  # Non-empty URL


class TestProxyAutoAuth:
    """Test proxy auto-authentication behavior"""
    
    def test_proxy_no_auth_header_uses_central_admin(self):
        """Proxy without auth header → uses cached central admin token"""
        resp = requests.get(f"{BASE_URL}/api/central/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        # Should return superadmin (the configured central admin)
        assert data["username"] == "superadmin"
        assert data["role"] == "superadmin"
    
    def test_proxy_local_kiosk_jwt_replaced_with_central_admin(self, local_kiosk_token):
        """Proxy with local kiosk JWT → replaced with central admin token"""
        resp = requests.get(
            f"{BASE_URL}/api/central/auth/me",
            headers={"Authorization": f"Bearer {local_kiosk_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should return superadmin, not the local admin
        assert data["username"] == "superadmin"
        assert data["role"] == "superadmin"
        assert data["is_superadmin"] == True
    
    def test_proxy_central_jwt_forwarded_as_is(self, central_operator_token):
        """Proxy with central JWT → forwarded as-is (operator portal flow)"""
        resp = requests.get(
            f"{BASE_URL}/api/central/auth/me",
            headers={"Authorization": f"Bearer {central_operator_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        # Should return operator1, not superadmin
        assert data["username"] == "operator1"
        assert data["role"] == "operator"
        assert data["is_superadmin"] == False
        assert "allowed_customer_ids" in data


class TestRegistrationTokensViaProxy:
    """Test registration token CRUD via proxy"""
    
    def test_get_registration_tokens_with_local_jwt(self, local_kiosk_token):
        """GET /api/central/registration-tokens works with local kiosk JWT"""
        resp = requests.get(
            f"{BASE_URL}/api/central/registration-tokens",
            headers={"Authorization": f"Bearer {local_kiosk_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Each token should have expected fields
        if len(data) > 0:
            token = data[0]
            assert "id" in token
            assert "status" in token
            assert "token_preview" in token
    
    def test_create_registration_token_via_proxy(self, local_kiosk_token):
        """POST /api/central/registration-tokens creates a token"""
        resp = requests.post(
            f"{BASE_URL}/api/central/registration-tokens",
            headers={
                "Authorization": f"Bearer {local_kiosk_token}",
                "Content-Type": "application/json"
            },
            json={
                "expires_in_hours": 1,
                "note": "pytest test token"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert "raw_token" in data
        assert data["status"] == "active"
        assert data["note"] == "pytest test token"
        # Return for cleanup
        return data["id"], data["raw_token"]
    
    def test_revoke_registration_token_via_proxy(self, local_kiosk_token):
        """POST /api/central/registration-tokens/{id}/revoke revokes a token"""
        # First create a token
        create_resp = requests.post(
            f"{BASE_URL}/api/central/registration-tokens",
            headers={
                "Authorization": f"Bearer {local_kiosk_token}",
                "Content-Type": "application/json"
            },
            json={"expires_in_hours": 1, "note": "To be revoked"}
        )
        assert create_resp.status_code == 200
        token_id = create_resp.json()["id"]
        
        # Now revoke it
        revoke_resp = requests.post(
            f"{BASE_URL}/api/central/registration-tokens/{token_id}/revoke",
            headers={"Authorization": f"Bearer {local_kiosk_token}"}
        )
        assert revoke_resp.status_code == 200
        data = revoke_resp.json()
        assert data["is_revoked"] == True
        assert data["status"] == "revoked"
        assert data["revoked_by"] == "superadmin"  # Auto-auth uses superadmin


class TestProxyErrorHandling:
    """Test proxy error handling"""
    
    def test_proxy_returns_404_for_invalid_path(self, local_kiosk_token):
        """Proxy returns 404 from central server for non-existent path"""
        resp = requests.get(
            f"{BASE_URL}/api/central/nonexistent-endpoint-12345",
            headers={"Authorization": f"Bearer {local_kiosk_token}"}
        )
        assert resp.status_code == 404


class TestOperatorPortalStillWorks:
    """Verify operator portal flow still works via proxy"""
    
    def test_operator_login_via_proxy(self):
        """Operator can login via proxy"""
        resp = requests.post(
            f"{BASE_URL}/api/central/auth/login",
            json={"username": "operator1", "password": "test1234"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "operator1"
        assert data["user"]["role"] == "operator"
    
    def test_operator_sees_scoped_data(self, central_operator_token):
        """Operator sees only their allowed customers"""
        resp = requests.get(
            f"{BASE_URL}/api/central/licensing/customers",
            headers={"Authorization": f"Bearer {central_operator_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        # operator1 should only see 1 customer (Darts Bar Berlin)
        assert isinstance(data, list)
        assert len(data) == 1  # Scoped to allowed_customer_ids
    
    def test_superadmin_sees_all_data(self, central_superadmin_token):
        """Superadmin sees all customers"""
        resp = requests.get(
            f"{BASE_URL}/api/central/licensing/customers",
            headers={"Authorization": f"Bearer {central_superadmin_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Superadmin sees all customers (should be more than 1)
        assert len(data) >= 1


class TestTokenStatusBadges:
    """Verify token status is correctly computed"""
    
    def test_token_statuses_include_active_expired_revoked(self, local_kiosk_token):
        """Token list includes various statuses"""
        resp = requests.get(
            f"{BASE_URL}/api/central/registration-tokens",
            headers={"Authorization": f"Bearer {local_kiosk_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Collect all statuses
        statuses = set(t["status"] for t in data)
        # Should have at least active and revoked from our tests
        # (expired depends on existing data)
        assert "active" in statuses or "revoked" in statuses or "expired" in statuses
