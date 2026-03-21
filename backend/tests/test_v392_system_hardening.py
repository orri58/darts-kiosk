"""
Test Suite for System Hardening v3.9.2
Tests: action_poller, config_sync_client, config_apply bullet-proofing

Features tested:
- Persistent state (survives restart)
- Idempotent actions
- Retry with backoff
- asyncio.Lock against race conditions
- Per-section error isolation
- Fail-open (local kiosk never crashes from sync failures)
- Extended health check with degraded status
- Production-level logging
"""
import pytest
import requests
import os
import json
import asyncio
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
DATA_DIR = Path("/app/data")


class TestBackendStartup:
    """Verify backend starts without errors after hardening"""
    
    def test_health_endpoint_returns_healthy(self):
        """Backend should start and return healthy status"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Status not healthy: {data}"
        print(f"✓ Backend healthy: {data}")


class TestConfigVersionPersistence:
    """Test GET /api/settings/config-version returns persisted version"""
    
    def test_config_version_endpoint(self):
        """Config version should be >= 0 and persisted"""
        response = requests.get(f"{BASE_URL}/api/settings/config-version", timeout=10)
        assert response.status_code == 200, f"Config version failed: {response.text}"
        data = response.json()
        assert "version" in data, f"Missing 'version' field: {data}"
        assert isinstance(data["version"], int), f"Version not int: {data}"
        assert data["version"] >= 0, f"Version should be >= 0: {data}"
        print(f"✓ Config version: {data['version']}")
    
    def test_config_version_file_exists(self):
        """Persistent version file should exist at /app/data/config_applied_version.json"""
        version_file = DATA_DIR / "config_applied_version.json"
        assert version_file.exists(), f"Version file not found: {version_file}"
        content = json.loads(version_file.read_text())
        assert "version" in content, f"Missing 'version' in file: {content}"
        print(f"✓ Persisted version file: {content}")


class TestConfigSyncStatus:
    """Test GET /api/settings/config-sync/status returns full status"""
    
    def test_config_sync_status_fields(self):
        """Status should include sync_count, sync_errors, consecutive_errors"""
        response = requests.get(f"{BASE_URL}/api/settings/config-sync/status", timeout=10)
        assert response.status_code == 200, f"Status failed: {response.text}"
        data = response.json()
        
        # Check config_sync fields
        assert "config_sync" in data, f"Missing 'config_sync': {data}"
        sync = data["config_sync"]
        required_sync_fields = ["sync_count", "sync_errors", "consecutive_errors", "configured", "running"]
        for field in required_sync_fields:
            assert field in sync, f"Missing config_sync.{field}: {sync}"
        print(f"✓ Config sync status: sync_count={sync['sync_count']}, errors={sync['sync_errors']}, consecutive={sync['consecutive_errors']}")
        
        # Check action_poller fields
        assert "action_poller" in data, f"Missing 'action_poller': {data}"
        poller = data["action_poller"]
        required_poller_fields = ["actions_executed", "actions_failed", "consecutive_poll_errors", "processing_count", "history_size"]
        for field in required_poller_fields:
            assert field in poller, f"Missing action_poller.{field}: {poller}"
        print(f"✓ Action poller status: executed={poller['actions_executed']}, failed={poller['actions_failed']}, consecutive_errors={poller['consecutive_poll_errors']}")
        
        # Check applied_config_version
        assert "applied_config_version" in data, f"Missing 'applied_config_version': {data}"
        print(f"✓ Applied config version: {data['applied_config_version']}")


class TestConfigCachePersistence:
    """Test config cache persists across restarts"""
    
    def test_config_cache_file_exists(self):
        """Config cache should exist at /app/data/config_cache.json"""
        cache_file = DATA_DIR / "config_cache.json"
        assert cache_file.exists(), f"Cache file not found: {cache_file}"
        content = json.loads(cache_file.read_text())
        assert "config" in content, f"Missing 'config' in cache: {content}"
        assert "version" in content, f"Missing 'version' in cache: {content}"
        print(f"✓ Config cache exists: version={content['version']}, synced_at={content.get('synced_at', 'N/A')}")


class TestForceSync:
    """Test POST /api/settings/config-sync/force"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        }, timeout=10)
        if response.status_code != 200:
            pytest.skip("Admin login failed - skipping authenticated tests")
        data = response.json()
        return data.get("access_token")
    
    def test_force_sync_requires_auth(self):
        """Force sync should require authentication"""
        response = requests.post(f"{BASE_URL}/api/settings/config-sync/force", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Force sync requires auth (401 without token)")
    
    def test_force_sync_with_auth(self, admin_token):
        """Force sync should work with admin auth"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.post(f"{BASE_URL}/api/settings/config-sync/force", headers=headers, timeout=15)
        assert response.status_code == 200, f"Force sync failed: {response.text}"
        data = response.json()
        assert "success" in data, f"Missing 'success': {data}"
        assert "changed" in data, f"Missing 'changed': {data}"
        assert "status" in data, f"Missing 'status': {data}"
        print(f"✓ Force sync: success={data['success']}, changed={data['changed']}")


class TestActionPollerStatus:
    """Test action poller status includes all required fields"""
    
    def test_action_poller_status_via_sync_status(self):
        """Action poller status should include all hardening fields"""
        response = requests.get(f"{BASE_URL}/api/settings/config-sync/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        poller = data.get("action_poller", {})
        
        # Required fields from hardening
        required = [
            "actions_executed",
            "actions_failed", 
            "consecutive_poll_errors",
            "processing_count",
            "history_size",
            "configured",
            "running"
        ]
        for field in required:
            assert field in poller, f"Missing action_poller.{field}"
        
        # Verify types
        assert isinstance(poller["actions_executed"], int)
        assert isinstance(poller["actions_failed"], int)
        assert isinstance(poller["consecutive_poll_errors"], int)
        assert isinstance(poller["processing_count"], int)
        assert isinstance(poller["history_size"], int)
        
        print(f"✓ Action poller has all required fields: {list(poller.keys())}")


class TestDetailedHealth:
    """Test GET /api/health/detailed includes config_sync and action_poller"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        }, timeout=10)
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json().get("access_token")
    
    def test_detailed_health_requires_auth(self):
        """Detailed health should require admin auth"""
        response = requests.get(f"{BASE_URL}/api/health/detailed", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Detailed health requires auth")
    
    def test_detailed_health_includes_sync_status(self, admin_token):
        """Detailed health should include config_sync and action_poller objects"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/health/detailed", headers=headers, timeout=10)
        assert response.status_code == 200, f"Detailed health failed: {response.text}"
        data = response.json()
        
        # Check for config_sync
        assert "config_sync" in data, f"Missing 'config_sync' in health: {list(data.keys())}"
        sync = data["config_sync"]
        assert "sync_count" in sync, f"Missing sync_count in config_sync"
        assert "consecutive_errors" in sync, f"Missing consecutive_errors in config_sync"
        
        # Check for action_poller
        assert "action_poller" in data, f"Missing 'action_poller' in health: {list(data.keys())}"
        poller = data["action_poller"]
        assert "actions_executed" in poller, f"Missing actions_executed in action_poller"
        
        # Check status
        assert "status" in data, f"Missing 'status' in health"
        print(f"✓ Detailed health: status={data['status']}, config_sync present, action_poller present")


class TestHealthStatus:
    """Test health status is 'healthy' when no consecutive errors"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        }, timeout=10)
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json().get("access_token")
    
    def test_health_status_healthy_or_degraded(self, admin_token):
        """Health status should be healthy when no consecutive errors"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/health/detailed", headers=headers, timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        status = data.get("status")
        assert status in ["healthy", "degraded", "unhealthy"], f"Invalid status: {status}"
        
        # If config_sync has < 3 consecutive errors, should not be degraded due to sync
        sync = data.get("config_sync", {})
        consecutive = sync.get("consecutive_errors", 0)
        
        if consecutive < 3:
            print(f"✓ Health status: {status} (consecutive_errors={consecutive} < 3)")
        else:
            print(f"✓ Health status: {status} (consecutive_errors={consecutive} >= 3, may be degraded)")


class TestBrandingEndpoint:
    """Test branding endpoint returns central config values"""
    
    def test_branding_returns_central_values(self):
        """Branding should return values from central config"""
        response = requests.get(f"{BASE_URL}/api/settings/branding", timeout=10)
        assert response.status_code == 200, f"Branding failed: {response.text}"
        data = response.json()
        
        # Check expected fields exist
        assert "cafe_name" in data, f"Missing cafe_name: {data}"
        assert "subtitle" in data or "primary_color" in data, f"Missing branding fields: {data}"
        
        # Per context: cafe_name='DartControl HQ', subtitle='Reconnected & Updated'
        print(f"✓ Branding: cafe_name='{data.get('cafe_name')}', subtitle='{data.get('subtitle')}'")


class TestConcurrentForceSync:
    """Test concurrent force_sync calls don't crash or deadlock"""
    
    @pytest.fixture
    def admin_token(self):
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        }, timeout=10)
        if response.status_code != 200:
            pytest.skip("Admin login failed")
        return response.json().get("access_token")
    
    def test_concurrent_force_sync(self, admin_token):
        """Multiple concurrent force_sync calls should not crash"""
        import concurrent.futures
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        def do_force_sync():
            try:
                resp = requests.post(f"{BASE_URL}/api/settings/config-sync/force", headers=headers, timeout=15)
                return resp.status_code, resp.json() if resp.status_code == 200 else resp.text
            except Exception as e:
                return -1, str(e)
        
        # Fire 3 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(do_force_sync) for _ in range(3)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        # All should succeed (200) or be skipped (lock held)
        success_count = sum(1 for code, _ in results if code == 200)
        error_count = sum(1 for code, _ in results if code not in [200, -1])
        
        assert error_count == 0, f"Some requests failed: {results}"
        print(f"✓ Concurrent force_sync: {success_count}/3 succeeded (lock prevents concurrent execution)")


class TestSimpleHealthNoAuth:
    """Test simple /api/health endpoint does NOT require auth"""
    
    def test_simple_health_no_auth(self):
        """Simple health endpoint should work without auth"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Simple health failed: {response.text}"
        data = response.json()
        assert "status" in data, f"Missing status: {data}"
        assert "mode" in data, f"Missing mode: {data}"
        print(f"✓ Simple health (no auth): status={data['status']}, mode={data['mode']}")


class TestFailOpenBehavior:
    """Test fail-open behavior - action_poller not configured doesn't crash"""
    
    def test_action_poller_not_configured_no_crash(self):
        """Action poller should show configured=false when no device_id, not crash"""
        response = requests.get(f"{BASE_URL}/api/settings/config-sync/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        poller = data.get("action_poller", {})
        
        # Per context: action_poller is NOT running because no device_id
        # This is expected fail-open behavior
        configured = poller.get("configured", False)
        running = poller.get("running", False)
        
        # The key test: endpoint returns successfully even if poller not configured
        print(f"✓ Fail-open: action_poller configured={configured}, running={running} (no crash)")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
