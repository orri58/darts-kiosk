"""
Legacy Layer A integration smoke tests.

These remain useful as historical or deployment-specific checks when explicitly
working on the optional adapter ring, but they are not the main validation gate
for the protected local core.

See docs/TESTING.md for the current authoritative local-core subset.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Credentials
LOCAL_ADMIN = {"username": "admin", "password": "admin123"}
CENTRAL_ADMIN = {"username": "superadmin", "password": "admin"}


class TestLocalCoreUnchanged:
    """Tests 1-5: Verify local core functionality is unchanged"""

    def test_01_local_auth_login(self):
        """Test 1: POST /api/auth/login with admin/admin123 returns 200 with token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=LOCAL_ADMIN,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "access_token" in data, f"Expected 'access_token' in response, got: {data.keys()}"
        assert data["access_token"], "Token should not be empty"
        print(f"✓ Local auth login successful, token received")

    def test_02_local_boards_list(self):
        """Test 2: GET /api/boards with token returns board list"""
        # First login to get token
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=LOCAL_ADMIN)
        token = login_resp.json()["access_token"]

        response = requests.get(
            f"{BASE_URL}/api/boards",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Boards list returned {len(data)} boards")

    def test_03_local_board_unlock(self):
        """Test 3: POST /api/boards/BOARD-1/unlock with token returns 200"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=LOCAL_ADMIN)
        token = login_resp.json()["access_token"]

        response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"player_count": 2, "credits": 1, "pricing_mode": "per_game"},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Board BOARD-1 unlocked successfully")

    def test_04_local_board_lock(self):
        """Test 4: POST /api/boards/BOARD-1/lock with token returns 200"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=LOCAL_ADMIN)
        token = login_resp.json()["access_token"]

        response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ Board BOARD-1 locked successfully")

    def test_05_local_settings_branding(self):
        """Test 5: GET /api/settings/branding returns 200"""
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json=LOCAL_ADMIN)
        token = login_resp.json()["access_token"]

        response = requests.get(
            f"{BASE_URL}/api/settings/branding",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Branding returns cafe_name, subtitle, welcome_text directly
        assert "cafe_name" in data or "value" in data, f"Expected branding data, got: {data.keys()}"
        print(f"✓ Branding settings retrieved successfully: {data}")


class TestCentralProxyHealth:
    """Test 6: Central server proxy health check"""

    def test_06_central_health(self):
        """Test 6: GET /api/central/health returns 200 with central server status"""
        response = requests.get(f"{BASE_URL}/api/central/health")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data.get("status") == "ok", f"Expected status='ok', got: {data}"
        print(f"✓ Central server health check passed: {data}")


class TestCentralAuth:
    """Test 7: Central portal authentication"""

    def test_07_central_auth_login(self):
        """Test 7: POST /api/central/auth/login with superadmin/admin returns 200 with token"""
        response = requests.post(
            f"{BASE_URL}/api/central/auth/login",
            json=CENTRAL_ADMIN,
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "access_token" in data, f"Expected 'access_token' in response, got: {data.keys()}"
        assert data["access_token"], "Token should not be empty"
        print(f"✓ Central auth login successful, token received")


class TestCentralDashboard:
    """Test 8: Central dashboard data"""

    @pytest.fixture
    def central_token(self):
        """Get central auth token"""
        response = requests.post(
            f"{BASE_URL}/api/central/auth/login",
            json=CENTRAL_ADMIN,
            headers={"Content-Type": "application/json"},
        )
        return response.json()["access_token"]

    def test_08_central_dashboard(self, central_token):
        """Test 8: GET /api/central/dashboard with central token returns customers/locations/devices counts"""
        response = requests.get(
            f"{BASE_URL}/api/central/dashboard",
            headers={"Authorization": f"Bearer {central_token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        # Verify dashboard has expected fields
        assert "customers" in data, f"Expected 'customers' in dashboard, got: {data.keys()}"
        assert "locations" in data, f"Expected 'locations' in dashboard, got: {data.keys()}"
        assert "devices" in data, f"Expected 'devices' in dashboard, got: {data.keys()}"
        print(f"✓ Dashboard data: customers={data['customers']}, locations={data['locations']}, devices={data['devices']}")


class TestCentralDevices:
    """Test 9: Central devices list with heartbeat data"""

    @pytest.fixture
    def central_token(self):
        """Get central auth token"""
        response = requests.post(
            f"{BASE_URL}/api/central/auth/login",
            json=CENTRAL_ADMIN,
            headers={"Content-Type": "application/json"},
        )
        return response.json()["access_token"]

    def test_09_central_devices_list(self, central_token):
        """Test 9: GET /api/central/licensing/devices with token returns device list"""
        response = requests.get(
            f"{BASE_URL}/api/central/licensing/devices",
            headers={"Authorization": f"Bearer {central_token}"},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"✓ Devices list returned {len(data)} devices")
        
        # Check for Device 1 with heartbeat data
        device_1 = None
        for d in data:
            if d.get("device_name") == "Device 1" or "Device 1" in str(d.get("device_name", "")):
                device_1 = d
                break
        
        if device_1:
            print(f"  Device 1 found: connectivity={device_1.get('connectivity')}, version={device_1.get('reported_version')}")
            # Note: connectivity and version depend on heartbeat timing
        else:
            print(f"  Device 1 not found in list (may need heartbeat)")


class TestLayerASecurity:
    """Tests 10-11: Layer A security - write operations blocked"""

    @pytest.fixture
    def central_token(self):
        """Get central auth token"""
        response = requests.post(
            f"{BASE_URL}/api/central/auth/login",
            json=CENTRAL_ADMIN,
            headers={"Content-Type": "application/json"},
        )
        return response.json()["access_token"]

    def test_10_layer_a_block_create_customer(self, central_token):
        """Test 10: POST /api/central/licensing/customers with token returns 403 (write blocked)"""
        response = requests.post(
            f"{BASE_URL}/api/central/licensing/customers",
            json={"name": "Test Customer", "email": "test@example.com"},
            headers={
                "Authorization": f"Bearer {central_token}",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 403, f"Expected 403 (write blocked), got {response.status_code}: {response.text}"
        print(f"✓ POST /api/central/licensing/customers correctly blocked with 403")

    def test_11_layer_a_block_update_device(self, central_token):
        """Test 11: PUT /api/central/licensing/devices/xyz with token returns 403 (write blocked)"""
        response = requests.put(
            f"{BASE_URL}/api/central/licensing/devices/xyz",
            json={"device_name": "Updated Name"},
            headers={
                "Authorization": f"Bearer {central_token}",
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 403, f"Expected 403 (write blocked), got {response.status_code}: {response.text}"
        print(f"✓ PUT /api/central/licensing/devices/xyz correctly blocked with 403")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
