"""
v3.5.2 Role-Based Access Control Tests — Central License Server

Tests for multi-tenant admin access with roles (superadmin/operator).
- Superadmin has full access to all data
- Operator scoped to allowed_customer_ids only
- Backend enforces scope on all CRUD endpoints
"""
import pytest
import requests
import os
import uuid

pytestmark = pytest.mark.integration

CENTRAL_URL = os.environ.get("CENTRAL_SERVER_URL", "http://localhost:8002")
KIOSK_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://boardgame-repair.preview.emergentagent.com")
LEGACY_TOKEN = "admin-secret-token"


def unique_name(prefix="TEST"):
    """Generate unique name using UUID"""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def superadmin_session():
    """Module-level superadmin session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LEGACY_TOKEN}"
    })
    return session


@pytest.fixture(scope="module")
def test_data(superadmin_session):
    """Create all test data once for the module"""
    # Create Customer A
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/licensing/customers", json={
        "name": unique_name("Customer_A"),
        "contact_email": "testa@test.com"
    })
    assert resp.status_code == 200
    customer_a = resp.json()
    
    # Create Customer B
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/licensing/customers", json={
        "name": unique_name("Customer_B"),
        "contact_email": "testb@test.com"
    })
    assert resp.status_code == 200
    customer_b = resp.json()
    
    # Create Location for Customer A
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/licensing/locations", json={
        "customer_id": customer_a["id"],
        "name": unique_name("Location_A")
    })
    assert resp.status_code == 200
    location_a = resp.json()
    
    # Create Location for Customer B
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/licensing/locations", json={
        "customer_id": customer_b["id"],
        "name": unique_name("Location_B")
    })
    assert resp.status_code == 200
    location_b = resp.json()
    
    # Create Device for Location A
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/licensing/devices", json={
        "location_id": location_a["id"],
        "device_name": unique_name("Device_A")
    })
    assert resp.status_code == 200
    device_a = resp.json()
    
    # Create Device for Location B
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/licensing/devices", json={
        "location_id": location_b["id"],
        "device_name": unique_name("Device_B")
    })
    assert resp.status_code == 200
    device_b = resp.json()
    
    # Create License for Customer A
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/licensing/licenses", json={
        "customer_id": customer_a["id"],
        "plan_type": "standard"
    })
    assert resp.status_code == 200
    license_a = resp.json()
    
    # Create License for Customer B
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/licensing/licenses", json={
        "customer_id": customer_b["id"],
        "plan_type": "premium"
    })
    assert resp.status_code == 200
    license_b = resp.json()
    
    # Create Registration Token for Customer A
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/registration-tokens", json={
        "customer_id": customer_a["id"],
        "expires_in_hours": 24,
        "note": "For Customer A"
    })
    assert resp.status_code == 200
    token_a = resp.json()
    
    # Create Registration Token for Customer B
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/registration-tokens", json={
        "customer_id": customer_b["id"],
        "expires_in_hours": 24,
        "note": "For Customer B"
    })
    assert resp.status_code == 200
    token_b = resp.json()
    
    # Create Operator user with access only to Customer A
    operator_username = unique_name("operator")
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/users", json={
        "username": operator_username,
        "password": "operatorpass",
        "display_name": "Test Operator",
        "role": "operator",
        "allowed_customer_ids": [customer_a["id"]]
    })
    assert resp.status_code == 200
    operator_user = resp.json()
    
    # Login as operator and get token
    resp = superadmin_session.post(f"{CENTRAL_URL}/api/auth/login", json={
        "username": operator_username,
        "password": "operatorpass"
    })
    assert resp.status_code == 200
    operator_token = resp.json()["access_token"]
    
    return {
        "customer_a": customer_a,
        "customer_b": customer_b,
        "location_a": location_a,
        "location_b": location_b,
        "device_a": device_a,
        "device_b": device_b,
        "license_a": license_a,
        "license_b": license_b,
        "token_a": token_a,
        "token_b": token_b,
        "operator_user": operator_user,
        "operator_token": operator_token,
        "operator_username": operator_username
    }


class TestCentralAuthEndpoints:
    """Test auth endpoints for v3.5.2"""
    
    def test_superadmin_login_returns_jwt_and_user(self):
        """POST /api/auth/login with superadmin credentials returns JWT token and user info"""
        session = requests.Session()
        resp = session.post(f"{CENTRAL_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "admin"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        # Verify response structure
        assert "access_token" in data
        assert "user" in data
        assert len(data["access_token"]) > 50  # JWT should be substantial
        
        # Verify user info
        user = data["user"]
        assert user["username"] == "superadmin"
        assert user["role"] == "superadmin"
        assert "id" in user
        assert "display_name" in user
        assert "allowed_customer_ids" in user
        
    def test_login_invalid_credentials_returns_401(self):
        """POST /api/auth/login with invalid credentials returns 401"""
        session = requests.Session()
        resp = session.post(f"{CENTRAL_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "wrongpassword"
        })
        assert resp.status_code == 401
        
    def test_login_missing_fields_returns_400(self):
        """POST /api/auth/login without username/password returns 400"""
        session = requests.Session()
        resp = session.post(f"{CENTRAL_URL}/api/auth/login", json={})
        assert resp.status_code == 400
        
    def test_auth_me_returns_current_user(self):
        """GET /api/auth/me returns current user info"""
        session = requests.Session()
        # First login
        login_resp = session.post(f"{CENTRAL_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "admin"
        })
        token = login_resp.json()["access_token"]
        
        # Get current user
        resp = session.get(f"{CENTRAL_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["username"] == "superadmin"
        assert data["role"] == "superadmin"
        assert data["is_superadmin"] == True
        assert "allowed_customer_ids" in data
        
    def test_legacy_token_works_as_superadmin(self):
        """Legacy admin-secret-token still works as superadmin"""
        session = requests.Session()
        resp = session.get(f"{CENTRAL_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {LEGACY_TOKEN}"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["role"] == "superadmin"
        assert data["is_superadmin"] == True
        

class TestUserManagement:
    """Test user CRUD endpoints - superadmin only"""
    
    def test_create_user_superadmin_only(self, superadmin_session):
        """POST /api/users creates a new user (superadmin only)"""
        test_username = unique_name("user")
        resp = superadmin_session.post(f"{CENTRAL_URL}/api/users", json={
            "username": test_username,
            "password": "testpass123",
            "display_name": "Test User",
            "role": "operator"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["username"] == test_username
        assert data["role"] == "operator"
        assert "id" in data
        
    def test_list_users_superadmin_only(self, superadmin_session):
        """GET /api/users lists all users (superadmin only)"""
        resp = superadmin_session.get(f"{CENTRAL_URL}/api/users")
        assert resp.status_code == 200
        users = resp.json()
        
        assert isinstance(users, list)
        assert len(users) >= 1  # At least superadmin
        
        # Verify user structure
        for u in users:
            assert "id" in u
            assert "username" in u
            assert "role" in u
            

class TestOperatorLogin:
    """Test operator login"""
    
    def test_operator_login_returns_correct_role(self, test_data):
        """POST /api/auth/login with operator credentials returns JWT with role=operator"""
        session = requests.Session()
        resp = session.get(f"{CENTRAL_URL}/api/auth/me", headers={
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        assert resp.status_code == 200
        data = resp.json()
        
        assert data["role"] == "operator"
        assert data["is_superadmin"] == False
        assert test_data["customer_a"]["id"] in data["allowed_customer_ids"]


class TestSuperadminSeesAllData:
    """Test that superadmin sees all data"""
    
    def test_superadmin_sees_all_customers(self, superadmin_session, test_data):
        """GET /api/licensing/customers for superadmin returns ALL customers"""
        resp = superadmin_session.get(f"{CENTRAL_URL}/api/licensing/customers")
        assert resp.status_code == 200
        customers = resp.json()
        
        customer_ids = [c["id"] for c in customers]
        assert test_data["customer_a"]["id"] in customer_ids
        assert test_data["customer_b"]["id"] in customer_ids
        
    def test_superadmin_sees_all_locations(self, superadmin_session, test_data):
        """GET /api/licensing/locations for superadmin returns ALL locations"""
        resp = superadmin_session.get(f"{CENTRAL_URL}/api/licensing/locations")
        assert resp.status_code == 200
        locations = resp.json()
        
        location_ids = [l["id"] for l in locations]
        assert test_data["location_a"]["id"] in location_ids
        assert test_data["location_b"]["id"] in location_ids


class TestOperatorScopedRead:
    """Test that operators can only see data within their allowed scope"""
    
    def test_operator_sees_only_allowed_customers(self, test_data):
        """GET /api/licensing/customers for operator returns ONLY allowed customers"""
        session = requests.Session()
        resp = session.get(f"{CENTRAL_URL}/api/licensing/customers", headers={
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        assert resp.status_code == 200
        customers = resp.json()
        
        customer_ids = [c["id"] for c in customers]
        assert test_data["customer_a"]["id"] in customer_ids
        assert test_data["customer_b"]["id"] not in customer_ids
        
    def test_operator_sees_only_allowed_locations(self, test_data):
        """GET /api/licensing/locations for operator returns ONLY locations of allowed customers"""
        session = requests.Session()
        resp = session.get(f"{CENTRAL_URL}/api/licensing/locations", headers={
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        assert resp.status_code == 200
        locations = resp.json()
        
        location_ids = [l["id"] for l in locations]
        assert test_data["location_a"]["id"] in location_ids
        assert test_data["location_b"]["id"] not in location_ids
        
    def test_operator_devices_scoped_to_allowed_customers(self, test_data):
        """GET /api/licensing/devices for operator returns ONLY devices of allowed customer locations"""
        session = requests.Session()
        resp = session.get(f"{CENTRAL_URL}/api/licensing/devices", headers={
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        assert resp.status_code == 200
        devices = resp.json()
        
        device_ids = [d["id"] for d in devices]
        assert test_data["device_a"]["id"] in device_ids
        assert test_data["device_b"]["id"] not in device_ids
        
    def test_operator_licenses_scoped_to_allowed_customers(self, test_data):
        """GET /api/licensing/licenses for operator returns ONLY licenses of allowed customers"""
        session = requests.Session()
        resp = session.get(f"{CENTRAL_URL}/api/licensing/licenses", headers={
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        assert resp.status_code == 200
        licenses = resp.json()
        
        license_ids = [l["id"] for l in licenses]
        assert test_data["license_a"]["id"] in license_ids
        assert test_data["license_b"]["id"] not in license_ids
        
    def test_operator_registration_tokens_scoped_to_allowed_customers(self, test_data):
        """GET /api/registration-tokens for operator only shows tokens for their customers"""
        session = requests.Session()
        resp = session.get(f"{CENTRAL_URL}/api/registration-tokens", headers={
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        assert resp.status_code == 200
        tokens = resp.json()
        
        token_ids = [t["id"] for t in tokens]
        assert test_data["token_a"]["id"] in token_ids
        assert test_data["token_b"]["id"] not in token_ids
        
    def test_operator_cannot_access_other_customer_location_via_query_param(self, test_data):
        """Operator cannot access other customer's locations via query param (403)"""
        session = requests.Session()
        resp = session.get(
            f"{CENTRAL_URL}/api/licensing/locations?customer_id={test_data['customer_b']['id']}", 
            headers={"Authorization": f"Bearer {test_data['operator_token']}"}
        )
        assert resp.status_code == 403


class TestOperatorWriteRestrictions:
    """Test that operators cannot write to superadmin-only endpoints"""
    
    def test_operator_cannot_create_user(self, test_data):
        """POST /api/users by operator returns 403"""
        session = requests.Session()
        resp = session.post(f"{CENTRAL_URL}/api/users", json={
            "username": unique_name("should_fail"),
            "password": "test123",
            "role": "operator"
        }, headers={"Authorization": f"Bearer {test_data['operator_token']}"})
        
        assert resp.status_code == 403
        
    def test_operator_cannot_create_customer(self, test_data):
        """POST /api/licensing/customers by operator returns 403 (superadmin only)"""
        session = requests.Session()
        resp = session.post(f"{CENTRAL_URL}/api/licensing/customers", json={
            "name": "Should Fail Customer"
        }, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        
        assert resp.status_code == 403
        
    def test_operator_cannot_create_license(self, test_data):
        """POST /api/licensing/licenses by operator returns 403"""
        session = requests.Session()
        resp = session.post(f"{CENTRAL_URL}/api/licensing/licenses", json={
            "customer_id": test_data["customer_a"]["id"],
            "plan_type": "standard"
        }, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        
        assert resp.status_code == 403
        
    def test_operator_cannot_create_device(self, test_data):
        """POST /api/licensing/devices by operator returns 403"""
        session = requests.Session()
        resp = session.post(f"{CENTRAL_URL}/api/licensing/devices", json={
            "location_id": test_data["location_a"]["id"],
            "device_name": "Should Fail Device"
        }, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        
        assert resp.status_code == 403
        
    def test_operator_cannot_create_registration_token(self, test_data):
        """POST /api/registration-tokens by operator returns 403 (superadmin only)"""
        session = requests.Session()
        resp = session.post(f"{CENTRAL_URL}/api/registration-tokens", json={
            "customer_id": test_data["customer_a"]["id"],
            "expires_in_hours": 24
        }, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        
        assert resp.status_code == 403
        
    def test_operator_cannot_revoke_registration_token(self, superadmin_session, test_data):
        """POST /api/registration-tokens/{id}/revoke by operator returns 403"""
        # Create a new token as superadmin (don't use existing one that might get revoked)
        resp = superadmin_session.post(f"{CENTRAL_URL}/api/registration-tokens", json={
            "customer_id": test_data["customer_a"]["id"],
            "expires_in_hours": 1
        })
        assert resp.status_code == 200
        new_token_id = resp.json()["id"]
        
        # Try to revoke as operator
        session = requests.Session()
        resp = session.post(
            f"{CENTRAL_URL}/api/registration-tokens/{new_token_id}/revoke", 
            json={},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {test_data['operator_token']}"
            }
        )
        
        assert resp.status_code == 403


class TestAuditLogScoping:
    """Test audit log access"""
    
    def test_superadmin_sees_all_audit_entries(self, superadmin_session):
        """GET /api/licensing/audit-log for superadmin sees all entries"""
        resp = superadmin_session.get(f"{CENTRAL_URL}/api/licensing/audit-log?limit=20")
        assert resp.status_code == 200
        entries = resp.json()
        
        assert isinstance(entries, list)
        
    def test_operator_audit_log_accessible(self, test_data):
        """GET /api/licensing/audit-log for operator returns filtered entries (no error)"""
        session = requests.Session()
        resp = session.get(f"{CENTRAL_URL}/api/licensing/audit-log?limit=20", headers={
            "Authorization": f"Bearer {test_data['operator_token']}"
        })
        assert resp.status_code == 200
        entries = resp.json()
        
        assert isinstance(entries, list)


class TestKioskBackendRegression:
    """Regression check: Kiosk Backend endpoints still work"""
    
    def test_kiosk_health(self):
        """Kiosk backend health check"""
        session = requests.Session()
        resp = session.get(f"{KIOSK_URL}/api/health")
        assert resp.status_code == 200
        assert "status" in resp.json()
        
    def test_kiosk_registration_status_public(self):
        """GET /api/licensing/registration-status is public (no auth required)"""
        session = requests.Session()
        resp = session.get(f"{KIOSK_URL}/api/licensing/registration-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "install_id" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
