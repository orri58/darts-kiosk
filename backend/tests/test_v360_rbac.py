"""
v3.6.0 RBAC Tests — Testing 4-tier role model (superadmin > installer > owner > staff)
Tests:
1. Role hierarchy - who can create which roles
2. RBAC enforcement - 403 on unauthorized actions
3. Scope filtering - data visibility
4. Dashboard scoping
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

# Central server is on port 8002
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://boardgame-repair.preview.emergentagent.com').rstrip('/')
CENTRAL_API = f"{BASE_URL}/api/central"

# Credentials
SUPERADMIN_CREDS = {"username": "superadmin", "password": "admin"}


@pytest.fixture(scope="module")
def superadmin_token():
    """Get superadmin token"""
    res = requests.post(f"{CENTRAL_API}/auth/login", json=SUPERADMIN_CREDS)
    assert res.status_code == 200, f"Superadmin login failed: {res.text}"
    return res.json()["access_token"]


@pytest.fixture(scope="module")
def test_customer(superadmin_token):
    """Create a test customer for RBAC tests"""
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    # Check if TEST_RBAC_Customer exists
    res = requests.get(f"{CENTRAL_API}/licensing/customers", headers=headers)
    customers = res.json()
    for c in customers:
        if c["name"] == "TEST_RBAC_Customer":
            return c
    # Create
    res = requests.post(f"{CENTRAL_API}/licensing/customers", headers=headers, json={
        "name": "TEST_RBAC_Customer",
        "contact_email": "rbac@test.com"
    })
    assert res.status_code == 200, f"Failed to create test customer: {res.text}"
    return res.json()


@pytest.fixture(scope="module")
def test_location(superadmin_token, test_customer):
    """Create a test location"""
    headers = {"Authorization": f"Bearer {superadmin_token}"}
    res = requests.get(f"{CENTRAL_API}/licensing/locations?customer_id={test_customer['id']}", headers=headers)
    for loc in res.json():
        if loc["name"] == "TEST_RBAC_Location":
            return loc
    res = requests.post(f"{CENTRAL_API}/licensing/locations", headers=headers, json={
        "customer_id": test_customer["id"],
        "name": "TEST_RBAC_Location",
        "address": "Test Address"
    })
    assert res.status_code == 200, f"Failed to create test location: {res.text}"
    return res.json()


class TestCentralServerHealth:
    """Central server connectivity"""

    def test_health_endpoint(self):
        """Test central server health"""
        res = requests.get(f"{CENTRAL_API}/../health".replace("/api/central/../", "/api/"))
        # Also try direct
        res2 = requests.get(f"{BASE_URL}/api/central/health")
        assert res.status_code == 200 or res2.status_code == 200, "Central server not reachable"

    def test_superadmin_login(self):
        """Test superadmin can login"""
        res = requests.post(f"{CENTRAL_API}/auth/login", json=SUPERADMIN_CREDS)
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["user"]["role"] == "superadmin"


class TestRoleCreationHierarchy:
    """Test RBAC: who can create which roles"""

    def test_superadmin_can_get_roles_info(self, superadmin_token):
        """Superadmin can see role hierarchy"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        res = requests.get(f"{CENTRAL_API}/roles", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "hierarchy" in data
        assert data["current_role"] == "superadmin"
        assert "superadmin" in data["can_create"]
        assert "installer" in data["can_create"]
        assert "owner" in data["can_create"]
        assert "staff" in data["can_create"]

    def test_superadmin_can_create_installer(self, superadmin_token, test_customer):
        """Superadmin can create installer user"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        username = f"TEST_installer_{datetime.now().strftime('%H%M%S')}"
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": username,
            "password": "test1234",
            "display_name": "Test Installer",
            "role": "installer",
            "allowed_customer_ids": [test_customer["id"]]
        })
        assert res.status_code == 200, f"Failed: {res.text}"
        data = res.json()
        assert data["role"] == "installer"
        assert test_customer["id"] in data["allowed_customer_ids"]

    def test_superadmin_can_create_owner(self, superadmin_token, test_customer):
        """Superadmin can create owner user"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        username = f"TEST_owner_{datetime.now().strftime('%H%M%S')}"
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": username,
            "password": "test1234",
            "display_name": "Test Owner",
            "role": "owner",
            "allowed_customer_ids": [test_customer["id"]]
        })
        assert res.status_code == 200, f"Failed: {res.text}"
        assert res.json()["role"] == "owner"

    def test_superadmin_can_create_staff(self, superadmin_token, test_customer):
        """Superadmin can create staff user"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        username = f"TEST_staff_{datetime.now().strftime('%H%M%S')}"
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": username,
            "password": "test1234",
            "display_name": "Test Staff",
            "role": "staff",
            "allowed_customer_ids": [test_customer["id"]]
        })
        assert res.status_code == 200, f"Failed: {res.text}"
        assert res.json()["role"] == "staff"


class TestInstallerRBAC:
    """Test installer role constraints"""

    @pytest.fixture
    def installer_user(self, superadmin_token, test_customer):
        """Create installer for testing"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        username = "TEST_rbac_installer"
        # Check if exists
        res = requests.get(f"{CENTRAL_API}/users", headers=headers)
        for u in res.json():
            if u["username"] == username:
                # Login
                login_res = requests.post(f"{CENTRAL_API}/auth/login", json={"username": username, "password": "test1234"})
                if login_res.status_code == 200:
                    return login_res.json()["access_token"]
        # Create
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": username,
            "password": "test1234",
            "role": "installer",
            "allowed_customer_ids": [test_customer["id"]]
        })
        if res.status_code != 200:
            pytest.skip(f"Could not create installer: {res.text}")
        # Login
        login_res = requests.post(f"{CENTRAL_API}/auth/login", json={"username": username, "password": "test1234"})
        assert login_res.status_code == 200
        return login_res.json()["access_token"]

    def test_installer_can_create_owner(self, installer_user, test_customer):
        """Installer can create owner"""
        headers = {"Authorization": f"Bearer {installer_user}"}
        username = f"TEST_inst_owner_{datetime.now().strftime('%H%M%S')}"
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": username,
            "password": "test1234",
            "role": "owner",
            "allowed_customer_ids": [test_customer["id"]]
        })
        assert res.status_code == 200, f"Installer should create owner: {res.text}"

    def test_installer_can_create_staff(self, installer_user, test_customer):
        """Installer can create staff"""
        headers = {"Authorization": f"Bearer {installer_user}"}
        username = f"TEST_inst_staff_{datetime.now().strftime('%H%M%S')}"
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": username,
            "password": "test1234",
            "role": "staff",
            "allowed_customer_ids": [test_customer["id"]]
        })
        assert res.status_code == 200, f"Installer should create staff: {res.text}"

    def test_installer_cannot_create_installer(self, installer_user, test_customer):
        """Installer CANNOT create another installer (403)"""
        headers = {"Authorization": f"Bearer {installer_user}"}
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": f"TEST_bad_inst_{datetime.now().strftime('%H%M%S')}",
            "password": "test1234",
            "role": "installer",
            "allowed_customer_ids": [test_customer["id"]]
        })
        assert res.status_code == 403, f"Installer should NOT create installer: {res.status_code}"

    def test_installer_cannot_create_superadmin(self, installer_user, test_customer):
        """Installer CANNOT create superadmin (403)"""
        headers = {"Authorization": f"Bearer {installer_user}"}
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": f"TEST_bad_sa_{datetime.now().strftime('%H%M%S')}",
            "password": "test1234",
            "role": "superadmin"
        })
        assert res.status_code == 403, f"Installer should NOT create superadmin: {res.status_code}"


class TestOwnerRBAC:
    """Test owner role constraints"""

    @pytest.fixture
    def owner_user(self, superadmin_token, test_customer):
        """Create owner for testing"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        username = "TEST_rbac_owner"
        # Check if exists
        res = requests.get(f"{CENTRAL_API}/users", headers=headers)
        for u in res.json():
            if u["username"] == username:
                login_res = requests.post(f"{CENTRAL_API}/auth/login", json={"username": username, "password": "test1234"})
                if login_res.status_code == 200:
                    return login_res.json()["access_token"]
        # Create
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": username,
            "password": "test1234",
            "role": "owner",
            "allowed_customer_ids": [test_customer["id"]]
        })
        if res.status_code != 200:
            pytest.skip(f"Could not create owner: {res.text}")
        login_res = requests.post(f"{CENTRAL_API}/auth/login", json={"username": username, "password": "test1234"})
        assert login_res.status_code == 200
        return login_res.json()["access_token"]

    def test_owner_can_create_staff(self, owner_user, test_customer):
        """Owner can create staff"""
        headers = {"Authorization": f"Bearer {owner_user}"}
        username = f"TEST_own_staff_{datetime.now().strftime('%H%M%S')}"
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": username,
            "password": "test1234",
            "role": "staff",
            "allowed_customer_ids": [test_customer["id"]]
        })
        assert res.status_code == 200, f"Owner should create staff: {res.text}"

    def test_owner_cannot_create_owner(self, owner_user, test_customer):
        """Owner CANNOT create another owner (403)"""
        headers = {"Authorization": f"Bearer {owner_user}"}
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": f"TEST_bad_own_{datetime.now().strftime('%H%M%S')}",
            "password": "test1234",
            "role": "owner",
            "allowed_customer_ids": [test_customer["id"]]
        })
        assert res.status_code == 403, f"Owner should NOT create owner: {res.status_code}"

    def test_owner_cannot_create_customers(self, owner_user):
        """Owner CANNOT create customers (403)"""
        headers = {"Authorization": f"Bearer {owner_user}"}
        res = requests.post(f"{CENTRAL_API}/licensing/customers", headers=headers, json={
            "name": "TEST_Unauthorized_Customer"
        })
        assert res.status_code == 403, f"Owner should NOT create customer: {res.status_code}"

    def test_owner_cannot_create_licenses(self, owner_user, test_customer):
        """Owner CANNOT create licenses (403)"""
        headers = {"Authorization": f"Bearer {owner_user}"}
        res = requests.post(f"{CENTRAL_API}/licensing/licenses", headers=headers, json={
            "customer_id": test_customer["id"],
            "plan_type": "standard"
        })
        assert res.status_code == 403, f"Owner should NOT create license: {res.status_code}"


class TestStaffRBAC:
    """Test staff role constraints - most restrictive"""

    @pytest.fixture
    def staff_user(self, superadmin_token, test_customer):
        """Create staff for testing"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        username = "TEST_rbac_staff"
        res = requests.get(f"{CENTRAL_API}/users", headers=headers)
        for u in res.json():
            if u["username"] == username:
                login_res = requests.post(f"{CENTRAL_API}/auth/login", json={"username": username, "password": "test1234"})
                if login_res.status_code == 200:
                    return login_res.json()["access_token"]
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": username,
            "password": "test1234",
            "role": "staff",
            "allowed_customer_ids": [test_customer["id"]]
        })
        if res.status_code != 200:
            pytest.skip(f"Could not create staff: {res.text}")
        login_res = requests.post(f"{CENTRAL_API}/auth/login", json={"username": username, "password": "test1234"})
        assert login_res.status_code == 200
        return login_res.json()["access_token"]

    def test_staff_cannot_create_users(self, staff_user, test_customer):
        """Staff CANNOT create users (403)"""
        headers = {"Authorization": f"Bearer {staff_user}"}
        res = requests.post(f"{CENTRAL_API}/users", headers=headers, json={
            "username": f"TEST_staff_bad_{datetime.now().strftime('%H%M%S')}",
            "password": "test1234",
            "role": "staff"
        })
        assert res.status_code == 403, f"Staff should NOT create users: {res.status_code}"

    def test_staff_cannot_create_customers(self, staff_user):
        """Staff CANNOT create customers (403)"""
        headers = {"Authorization": f"Bearer {staff_user}"}
        res = requests.post(f"{CENTRAL_API}/licensing/customers", headers=headers, json={
            "name": "TEST_Staff_Customer"
        })
        assert res.status_code == 403, f"Staff should NOT create customer: {res.status_code}"

    def test_staff_cannot_create_locations(self, staff_user, test_customer):
        """Staff CANNOT create locations (403)"""
        headers = {"Authorization": f"Bearer {staff_user}"}
        res = requests.post(f"{CENTRAL_API}/licensing/locations", headers=headers, json={
            "customer_id": test_customer["id"],
            "name": "TEST_Staff_Location"
        })
        assert res.status_code == 403, f"Staff should NOT create location: {res.status_code}"

    def test_staff_cannot_create_devices(self, staff_user, test_location):
        """Staff CANNOT create devices (403)"""
        headers = {"Authorization": f"Bearer {staff_user}"}
        res = requests.post(f"{CENTRAL_API}/licensing/devices", headers=headers, json={
            "location_id": test_location["id"],
            "device_name": "TEST_Staff_Device"
        })
        assert res.status_code == 403, f"Staff should NOT create device: {res.status_code}"

    def test_staff_cannot_create_licenses(self, staff_user, test_customer):
        """Staff CANNOT create licenses (403)"""
        headers = {"Authorization": f"Bearer {staff_user}"}
        res = requests.post(f"{CENTRAL_API}/licensing/licenses", headers=headers, json={
            "customer_id": test_customer["id"],
            "plan_type": "standard"
        })
        assert res.status_code == 403, f"Staff should NOT create license: {res.status_code}"

    def test_staff_can_view_scoped_customers(self, staff_user):
        """Staff CAN view scope/customers"""
        headers = {"Authorization": f"Bearer {staff_user}"}
        res = requests.get(f"{CENTRAL_API}/scope/customers", headers=headers)
        assert res.status_code == 200, f"Staff should view customers: {res.text}"

    def test_staff_can_view_dashboard(self, staff_user):
        """Staff CAN view dashboard"""
        headers = {"Authorization": f"Bearer {staff_user}"}
        res = requests.get(f"{CENTRAL_API}/dashboard", headers=headers)
        assert res.status_code == 200, f"Staff should view dashboard: {res.text}"


class TestScopeEndpoints:
    """Test scope filtering endpoints"""

    def test_scope_customers_returns_data(self, superadmin_token):
        """GET /api/scope/customers returns scoped data"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        res = requests.get(f"{CENTRAL_API}/scope/customers", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_scope_locations_returns_data(self, superadmin_token, test_customer):
        """GET /api/scope/locations returns scoped data"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        res = requests.get(f"{CENTRAL_API}/scope/locations?customer_id={test_customer['id']}", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)

    def test_scope_devices_returns_data(self, superadmin_token):
        """GET /api/scope/devices returns scoped data"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        res = requests.get(f"{CENTRAL_API}/scope/devices", headers=headers)
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestDashboardScoping:
    """Test dashboard with customer_id filter"""

    def test_dashboard_returns_stats(self, superadmin_token):
        """Dashboard returns stat counts"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        res = requests.get(f"{CENTRAL_API}/dashboard", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "customers" in data
        assert "locations" in data
        assert "devices" in data
        assert "licenses_total" in data

    def test_dashboard_filters_by_customer(self, superadmin_token, test_customer):
        """Dashboard filters by customer_id"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        res = requests.get(f"{CENTRAL_API}/dashboard?customer_id={test_customer['id']}", headers=headers)
        assert res.status_code == 200
        data = res.json()
        # Should be filtered - customers count should be 1 or less
        assert data["customers"] <= 1


class TestAuditLogActorColumn:
    """Test audit log has actor column"""

    def test_audit_log_has_actor(self, superadmin_token):
        """Audit log entries have actor field"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        res = requests.get(f"{CENTRAL_API}/licensing/audit-log?limit=10", headers=headers)
        assert res.status_code == 200
        entries = res.json()
        if entries:
            # At least some entries should have actor
            has_actor = any(e.get("actor") for e in entries)
            assert has_actor, "No audit entries have actor field"


class TestCleanup:
    """Cleanup test users"""

    def test_cleanup_test_users(self, superadmin_token):
        """Deactivate test users"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        res = requests.get(f"{CENTRAL_API}/users", headers=headers)
        if res.status_code == 200:
            for u in res.json():
                if u["username"].startswith("TEST_"):
                    requests.put(f"{CENTRAL_API}/users/{u['id']}", 
                                headers=headers, json={"status": "disabled"})
        assert True  # Cleanup is best-effort
