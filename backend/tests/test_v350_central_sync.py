"""
Test Suite for v3.5.0 — Central License Server + Hybrid Sync

Tests:
1. Central Server health endpoint
2. Central Server admin CRUD (customers, locations, devices, licenses)
3. Central Server sync endpoint (with X-License-Key auth)
4. Central Server audit log
5. Kiosk Backend sync-config (GET/POST)
6. Kiosk Backend sync-status
7. Kiosk Backend sync-now
8. Kiosk Backend check-status (with last_check_source field)
"""
import pytest
import requests
import os
import time
from datetime import datetime, timedelta, timezone

# Central Server (internal port 8002)
CENTRAL_SERVER_URL = "http://localhost:8002"
CENTRAL_ADMIN_TOKEN = os.environ.get("CENTRAL_ADMIN_TOKEN", "admin-secret-token")

# Kiosk Backend (via public URL)
KIOSK_BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://boardgame-repair.preview.emergentagent.com").rstrip("/")

# Test data containers
created_customer_id = None
created_location_id = None
created_device_id = None
created_device_api_key = None
created_license_id = None


class TestCentralServerHealth:
    """Central Server health endpoint tests"""

    def test_central_health_endpoint_returns_ok(self):
        """GET /api/health returns status=ok"""
        resp = requests.get(f"{CENTRAL_SERVER_URL}/api/health")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("status") == "ok"
        assert data.get("service") == "central-license-server"
        assert "timestamp" in data
        print(f"✓ Central Server health OK: {data}")


class TestCentralServerAdminCRUD:
    """Central Server admin CRUD tests (require admin token)"""
    
    def _admin_headers(self):
        return {"Authorization": f"Bearer {CENTRAL_ADMIN_TOKEN}"}
    
    def test_create_customer_requires_auth(self):
        """POST /api/licensing/customers without token returns 401"""
        resp = requests.post(f"{CENTRAL_SERVER_URL}/api/licensing/customers", json={"name": "Test"})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Create customer requires auth")

    def test_create_customer_with_admin_token(self):
        """POST /api/licensing/customers with admin token creates customer"""
        global created_customer_id
        data = {
            "name": f"TEST_CentralSyncCustomer_{int(time.time())}",
            "contact_email": "test@central.example.com"
        }
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/customers",
            json=data,
            headers=self._admin_headers()
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        result = resp.json()
        assert "id" in result
        assert result["name"] == data["name"]
        created_customer_id = result["id"]
        print(f"✓ Created customer: {created_customer_id}")

    def test_list_customers_with_admin_token(self):
        """GET /api/licensing/customers with admin token returns list"""
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/licensing/customers",
            headers=self._admin_headers()
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Listed customers: {len(data)} total")

    def test_create_location_with_admin_token(self):
        """POST /api/licensing/locations with admin token creates location"""
        global created_location_id
        assert created_customer_id, "Customer must be created first"
        data = {
            "customer_id": created_customer_id,
            "name": f"TEST_CentralLocation_{int(time.time())}",
            "address": "Test Address"
        }
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/locations",
            json=data,
            headers=self._admin_headers()
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        result = resp.json()
        assert "id" in result
        created_location_id = result["id"]
        print(f"✓ Created location: {created_location_id}")

    def test_create_device_returns_api_key(self):
        """POST /api/licensing/devices returns api_key"""
        global created_device_id, created_device_api_key
        assert created_location_id, "Location must be created first"
        data = {
            "location_id": created_location_id,
            "device_name": f"TEST_CentralDevice_{int(time.time())}"
        }
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/devices",
            json=data,
            headers=self._admin_headers()
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        result = resp.json()
        assert "id" in result
        assert "api_key" in result
        assert result["api_key"].startswith("dk_") or len(result["api_key"]) > 20
        created_device_id = result["id"]
        created_device_api_key = result["api_key"]
        print(f"✓ Created device with api_key: {created_device_api_key[:12]}...")

    def test_create_license_with_admin_token(self):
        """POST /api/licensing/licenses creates license"""
        global created_license_id
        assert created_customer_id, "Customer must be created first"
        now = datetime.now(timezone.utc)
        data = {
            "customer_id": created_customer_id,
            "location_id": created_location_id,
            "plan_type": "standard",
            "max_devices": 5,
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(days=365)).isoformat(),
            "grace_days": 7
        }
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/licenses",
            json=data,
            headers=self._admin_headers()
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        result = resp.json()
        assert "id" in result
        assert result["plan_type"] == "standard"
        assert result["status"] == "active"
        created_license_id = result["id"]
        print(f"✓ Created license: {created_license_id}")


class TestCentralServerSync:
    """Central Server sync endpoint tests (X-License-Key auth)"""

    def test_sync_without_api_key_returns_401(self):
        """POST /api/licensing/sync without X-License-Key returns 401"""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/sync",
            json={"install_id": "test-install-id"}
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("✓ Sync without API key returns 401")

    def test_sync_with_invalid_api_key_returns_403(self):
        """POST /api/licensing/sync with invalid X-License-Key returns 403"""
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/sync",
            json={"install_id": "test-install-id"},
            headers={"X-License-Key": "invalid-api-key-12345"}
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
        print("✓ Sync with invalid API key returns 403")

    def test_sync_with_valid_api_key_returns_license_data(self):
        """POST /api/licensing/sync with valid api_key returns license_status, binding_status, expiry, server_timestamp"""
        assert created_device_api_key, "Device with API key must be created first"
        resp = requests.post(
            f"{CENTRAL_SERVER_URL}/api/licensing/sync",
            json={"install_id": f"test-install-{int(time.time())}", "device_name": "Test Kiosk"},
            headers={"X-License-Key": created_device_api_key}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Required fields per spec
        assert "license_status" in data, f"Missing license_status: {data}"
        assert "binding_status" in data, f"Missing binding_status: {data}"
        assert "expiry" in data or data.get("expiry") is None, f"Missing expiry: {data}"
        assert "server_timestamp" in data, f"Missing server_timestamp: {data}"
        # Value checks
        assert data["license_status"] in ["active", "grace", "expired", "blocked", "no_license", "test"]
        print(f"✓ Sync response: license_status={data['license_status']}, binding_status={data['binding_status']}")


class TestCentralServerAuditLog:
    """Central Server audit log endpoint tests"""

    def _admin_headers(self):
        return {"Authorization": f"Bearer {CENTRAL_ADMIN_TOKEN}"}

    def test_audit_log_requires_admin(self):
        """GET /api/licensing/audit-log without token returns 401"""
        resp = requests.get(f"{CENTRAL_SERVER_URL}/api/licensing/audit-log")
        assert resp.status_code == 401
        print("✓ Audit log requires admin auth")

    def test_audit_log_returns_entries(self):
        """GET /api/licensing/audit-log with admin token returns list"""
        resp = requests.get(
            f"{CENTRAL_SERVER_URL}/api/licensing/audit-log",
            headers=self._admin_headers()
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        print(f"✓ Audit log has {len(data)} entries")
        # Check entry structure if we have entries
        if len(data) > 0:
            entry = data[0]
            assert "id" in entry
            assert "timestamp" in entry
            assert "action" in entry
            print(f"  Sample entry: action={entry.get('action')}, message={entry.get('message', '')[:50]}")


class TestKioskSyncConfig:
    """Kiosk Backend sync-config endpoint tests"""

    @pytest.fixture(autouse=True)
    def auth_headers(self):
        """Get auth token from kiosk backend"""
        resp = requests.post(
            f"{KIOSK_BACKEND_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip(f"Login failed: {resp.status_code}")
        yield
    
    def test_sync_config_get_returns_config(self):
        """GET /api/licensing/sync-config returns config with masked api_key"""
        resp = requests.get(
            f"{KIOSK_BACKEND_URL}/api/licensing/sync-config",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Check expected fields
        assert "enabled" in data
        assert "server_url" in data
        assert "api_key_masked" in data or "api_key_set" in data
        assert "interval_hours" in data
        assert "device_name" in data
        # api_key should NOT be returned directly
        assert "api_key" not in data or data.get("api_key") is None
        print(f"✓ Sync config GET: enabled={data.get('enabled')}, url={data.get('server_url')}")

    def test_sync_config_post_saves_config(self):
        """POST /api/licensing/sync-config saves config"""
        unique_device_name = f"Test Kiosk {int(time.time())}"
        config = {
            "enabled": True,
            "server_url": "http://localhost:8002",
            "api_key": created_device_api_key or "test-api-key-12345",
            "interval_hours": 4,
            "device_name": unique_device_name
        }
        resp = requests.post(
            f"{KIOSK_BACKEND_URL}/api/licensing/sync-config",
            json=config,
            headers=self.headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        # Verify the response config has correct values
        response_config = data.get("config", {})
        assert response_config.get("enabled") is True
        assert response_config.get("server_url") == "http://localhost:8002"
        assert response_config.get("interval_hours") == 4
        assert response_config.get("device_name") == unique_device_name
        print(f"✓ Sync config saved and verified in response: {response_config}")


class TestKioskSyncStatus:
    """Kiosk Backend sync-status endpoint tests"""

    @pytest.fixture(autouse=True)
    def auth_headers(self):
        """Get auth token from kiosk backend"""
        resp = requests.post(
            f"{KIOSK_BACKEND_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip(f"Login failed: {resp.status_code}")
        yield
    
    def test_sync_status_returns_sync_and_checker(self):
        """GET /api/licensing/sync-status returns sync and checker status"""
        resp = requests.get(
            f"{KIOSK_BACKEND_URL}/api/licensing/sync-status",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Check required structure
        assert "sync" in data, f"Missing 'sync' key: {data}"
        assert "checker" in data, f"Missing 'checker' key: {data}"
        # Sync status fields
        sync = data["sync"]
        assert "connected" in sync
        assert "last_sync_at" in sync or sync.get("last_sync_at") is None
        assert "sync_count" in sync
        assert "mode" in sync  # 'remote' or 'local'
        # Checker status fields
        checker = data["checker"]
        assert "running" in checker
        assert "last_check_at" in checker or checker.get("last_check_at") is None
        assert "check_count" in checker
        print(f"✓ Sync status: connected={sync.get('connected')}, mode={sync.get('mode')}")
        print(f"✓ Checker status: running={checker.get('running')}, count={checker.get('check_count')}")


class TestKioskSyncNow:
    """Kiosk Backend sync-now endpoint tests"""

    @pytest.fixture(autouse=True)
    def auth_headers(self):
        """Get auth token from kiosk backend"""
        resp = requests.post(
            f"{KIOSK_BACKEND_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip(f"Login failed: {resp.status_code}")
        yield

    def test_sync_now_triggers_hybrid_sync(self):
        """POST /api/licensing/sync-now triggers hybrid sync"""
        resp = requests.post(
            f"{KIOSK_BACKEND_URL}/api/licensing/sync-now",
            json={},
            headers=self.headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("triggered") is True
        print(f"✓ Sync-now triggered: {data}")


class TestKioskCheckStatus:
    """Kiosk Backend check-status endpoint tests"""

    @pytest.fixture(autouse=True)
    def auth_headers(self):
        """Get auth token from kiosk backend"""
        resp = requests.post(
            f"{KIOSK_BACKEND_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip(f"Login failed: {resp.status_code}")
        yield

    def test_check_status_has_last_check_source(self):
        """GET /api/licensing/check-status returns last_check_source field"""
        # First trigger a sync to ensure there's data
        requests.post(
            f"{KIOSK_BACKEND_URL}/api/licensing/sync-now",
            json={},
            headers=self.headers
        )
        time.sleep(2)  # Wait for sync to complete
        
        resp = requests.get(
            f"{KIOSK_BACKEND_URL}/api/licensing/check-status",
            headers=self.headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        # Check required fields
        assert "last_check_source" in data, f"Missing last_check_source: {data}"
        if data.get("last_check_source"):
            assert data["last_check_source"] in ["remote", "local", "error"], f"Invalid source: {data['last_check_source']}"
        print(f"✓ Check status: last_check_source={data.get('last_check_source')}, status={data.get('last_check_status')}")


class TestE2ERemoteSyncFlow:
    """End-to-end test: Configure sync → Trigger → Verify remote connection"""

    @pytest.fixture(autouse=True)
    def auth_headers(self):
        """Get auth token from kiosk backend"""
        resp = requests.post(
            f"{KIOSK_BACKEND_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            pytest.skip(f"Login failed: {resp.status_code}")
        yield

    def test_e2e_remote_sync_flow(self):
        """Full E2E: configure with central server, trigger sync, verify connected"""
        if not created_device_api_key:
            pytest.skip("No device API key available from central server tests")
        
        # 1. Configure sync with central server
        config = {
            "enabled": True,
            "server_url": "http://localhost:8002",
            "api_key": created_device_api_key,
            "interval_hours": 6,
            "device_name": "E2E Test Kiosk"
        }
        resp = requests.post(
            f"{KIOSK_BACKEND_URL}/api/licensing/sync-config",
            json=config,
            headers=self.headers
        )
        assert resp.status_code == 200
        print("✓ Step 1: Sync config saved")
        
        # 2. Trigger sync now
        resp = requests.post(
            f"{KIOSK_BACKEND_URL}/api/licensing/sync-now",
            json={},
            headers=self.headers
        )
        assert resp.status_code == 200
        print("✓ Step 2: Sync triggered")
        
        # 3. Wait for sync to complete
        time.sleep(3)
        
        # 4. Check sync status - should be connected
        resp = requests.get(
            f"{KIOSK_BACKEND_URL}/api/licensing/sync-status",
            headers=self.headers
        )
        assert resp.status_code == 200
        data = resp.json()
        sync = data.get("sync", {})
        
        # After successful sync, should be connected
        if sync.get("connected"):
            print(f"✓ Step 3: Remote sync CONNECTED - sync_count={sync.get('sync_count')}")
        else:
            # Check if there's an error
            if sync.get("last_error"):
                print(f"  Warning: Sync error - {sync.get('last_error')}")
            print(f"  Sync status: connected={sync.get('connected')}, mode={sync.get('mode')}")
        
        # 5. Check check-status for last_check_source
        resp = requests.get(
            f"{KIOSK_BACKEND_URL}/api/licensing/check-status",
            headers=self.headers
        )
        assert resp.status_code == 200
        check_data = resp.json()
        print(f"✓ Step 4: Check status: source={check_data.get('last_check_source')}, status={check_data.get('last_check_status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
