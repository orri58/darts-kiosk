"""
Test Suite for v3.9.4 Stability Package
Tests:
1. Device ID auto-resolution from API key at startup
2. Config schema validation before save
3. Config rollback with version history per scope
"""
import pytest
import requests
import os

# Central server URL (running on port 8002)
CENTRAL_URL = "http://localhost:8002"
# Backend URL from environment
BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Test credentials
CENTRAL_CREDS = {"username": "superadmin", "password": "admin"}
LOCAL_CREDS = {"username": "admin", "password": "admin123"}

# Test device
TEST_DEVICE_API_KEY = "dk_sHgIFVVWvqtvDJqsMefQC3lNgNhMZpdvPE_E3S1-bM4"
TEST_DEVICE_ID = "e0921245-f17b-4f70-aeca-60dba291251c"


@pytest.fixture(scope="module")
def central_token():
    """Get auth token from central server."""
    resp = requests.post(f"{CENTRAL_URL}/api/auth/login", json=CENTRAL_CREDS)
    assert resp.status_code == 200, f"Central login failed: {resp.text}"
    data = resp.json()
    return data.get("access_token")


@pytest.fixture(scope="module")
def local_token():
    """Get auth token from local backend."""
    resp = requests.post(f"{BACKEND_URL}/api/auth/login", json=LOCAL_CREDS)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token") or data.get("token")
    return None


class TestCentralServerStartup:
    """Test central server starts without errors and creates config_history table."""

    def test_central_server_health(self):
        """Central server should be running and healthy."""
        resp = requests.get(f"{CENTRAL_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "central-license-server"
        print(f"✓ Central server healthy: {data}")


class TestBackendStartup:
    """Test backend starts without errors."""

    def test_backend_health(self):
        """Backend should be running and healthy."""
        resp = requests.get(f"{BACKEND_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ["healthy", "ok"]
        print(f"✓ Backend healthy: {data}")


class TestDeviceResolve:
    """Test GET /api/device/resolve endpoint for device_id auto-resolution."""

    def test_resolve_with_valid_api_key(self):
        """GET /api/device/resolve with valid API key should return device_id."""
        resp = requests.get(
            f"{CENTRAL_URL}/api/device/resolve",
            headers={"X-License-Key": TEST_DEVICE_API_KEY}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "device_id" in data
        assert data["device_id"] == TEST_DEVICE_ID
        assert "device_name" in data
        assert "location_id" in data
        assert "status" in data
        print(f"✓ Device resolved: device_id={data['device_id']}, name={data['device_name']}")

    def test_resolve_with_invalid_api_key(self):
        """GET /api/device/resolve with invalid API key should return 404."""
        resp = requests.get(
            f"{CENTRAL_URL}/api/device/resolve",
            headers={"X-License-Key": "dk_invalid_key_12345"}
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print("✓ Invalid API key correctly returns 404")

    def test_resolve_without_api_key(self):
        """GET /api/device/resolve without X-License-Key header should return 401."""
        resp = requests.get(f"{CENTRAL_URL}/api/device/resolve")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}: {resp.text}"
        print("✓ Missing API key correctly returns 401")


class TestConfigSchemaValidation:
    """Test config schema validation before save (PUT /api/config/profile)."""

    def test_validation_invalid_pricing_mode(self, central_token):
        """PUT with invalid pricing mode should return 422 with validation_errors."""
        headers = {"Authorization": f"Bearer {central_token}", "Content-Type": "application/json"}
        invalid_config = {
            "config_data": {
                "pricing": {"mode": "invalid_mode"}
            }
        }
        resp = requests.put(
            f"{CENTRAL_URL}/api/config/profile/global/global",
            json=invalid_config,
            headers=headers
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "detail" in data
        assert "validation_errors" in data["detail"]
        errors = data["detail"]["validation_errors"]
        assert any("mode" in e for e in errors)
        print(f"✓ Invalid pricing mode rejected: {errors}")

    def test_validation_negative_price(self, central_token):
        """PUT with negative price should return 422."""
        headers = {"Authorization": f"Bearer {central_token}", "Content-Type": "application/json"}
        invalid_config = {
            "config_data": {
                "pricing": {
                    "mode": "per_game",
                    "per_game": {"price_per_credit": -5.0}
                }
            }
        }
        resp = requests.put(
            f"{CENTRAL_URL}/api/config/profile/global/global",
            json=invalid_config,
            headers=headers
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "validation_errors" in data["detail"]
        errors = data["detail"]["validation_errors"]
        assert any("price_per_credit" in e for e in errors)
        print(f"✓ Negative price rejected: {errors}")

    def test_validation_invalid_hex_color(self, central_token):
        """PUT with invalid hex color should return 422."""
        headers = {"Authorization": f"Bearer {central_token}", "Content-Type": "application/json"}
        invalid_config = {
            "config_data": {
                "branding": {"primary_color": "not-a-color"}
            }
        }
        resp = requests.put(
            f"{CENTRAL_URL}/api/config/profile/global/global",
            json=invalid_config,
            headers=headers
        )
        assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "validation_errors" in data["detail"]
        errors = data["detail"]["validation_errors"]
        assert any("primary_color" in e or "Hex" in e for e in errors)
        print(f"✓ Invalid hex color rejected: {errors}")

    def test_validation_valid_config_succeeds(self, central_token):
        """PUT with valid config should succeed and bump version."""
        headers = {"Authorization": f"Bearer {central_token}", "Content-Type": "application/json"}
        
        # First get current version
        resp = requests.get(
            f"{CENTRAL_URL}/api/config/profiles",
            headers=headers
        )
        assert resp.status_code == 200
        profiles = resp.json()
        global_profile = next((p for p in profiles if p["scope_type"] == "global"), None)
        old_version = global_profile["version"] if global_profile else 0
        
        # Now update with valid config
        valid_config = {
            "config_data": {
                "pricing": {
                    "mode": "per_game",
                    "per_game": {"price_per_credit": 2.50, "default_credits": 3}
                },
                "branding": {
                    "cafe_name": "DartControl HQ",
                    "primary_color": "#f59e0b"
                },
                "kiosk": {
                    "auto_lock_timeout_min": 5,
                    "idle_timeout_min": 15
                }
            }
        }
        resp = requests.put(
            f"{CENTRAL_URL}/api/config/profile/global/global",
            json=valid_config,
            headers=headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["version"] > old_version
        print(f"✓ Valid config saved, version bumped: {old_version} -> {data['version']}")


class TestConfigHistory:
    """Test config history endpoint GET /api/config/history/{scope}/{id}."""

    def test_get_history_global(self, central_token):
        """GET /api/config/history/global/global should return version list."""
        headers = {"Authorization": f"Bearer {central_token}"}
        resp = requests.get(
            f"{CENTRAL_URL}/api/config/history/global/global",
            headers=headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "scope_type" in data
        assert data["scope_type"] == "global"
        assert "active_version" in data
        assert "history" in data
        assert isinstance(data["history"], list)
        print(f"✓ Config history retrieved: active_version={data['active_version']}, history_count={len(data['history'])}")
        
        # Verify history entries have required fields
        if data["history"]:
            entry = data["history"][0]
            assert "id" in entry
            assert "version" in entry
            assert "updated_by" in entry
            assert "saved_at" in entry
            assert "config_data" in entry
            print(f"  First history entry: v{entry['version']} by {entry['updated_by']}")


class TestConfigRollback:
    """Test config rollback endpoint POST /api/config/rollback/{scope}/{id}/{version}."""

    def test_rollback_creates_new_version(self, central_token):
        """POST /api/config/rollback should restore old config and create new version."""
        headers = {"Authorization": f"Bearer {central_token}", "Content-Type": "application/json"}
        
        # First get history to find a version to rollback to
        resp = requests.get(
            f"{CENTRAL_URL}/api/config/history/global/global",
            headers=headers
        )
        assert resp.status_code == 200
        history_data = resp.json()
        
        if not history_data["history"]:
            pytest.skip("No history entries to rollback to")
        
        # Get current version
        current_version = history_data["active_version"]
        
        # Find a version to rollback to (not the current one)
        rollback_version = None
        for entry in history_data["history"]:
            if entry["version"] != current_version:
                rollback_version = entry["version"]
                break
        
        if not rollback_version:
            pytest.skip("No different version to rollback to")
        
        # Perform rollback
        resp = requests.post(
            f"{CENTRAL_URL}/api/config/rollback/global/global/{rollback_version}",
            headers=headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        
        # Verify new version was created (not overwritten)
        # Response format: {"success": true, "new_version": N, "rolled_back_to": M, "config_data": {...}}
        assert data.get("success") == True
        assert "new_version" in data
        assert data["new_version"] > current_version
        print(f"✓ Rollback successful: rolled back to v{rollback_version}, new version is v{data['new_version']}")
        
        # Verify history was updated
        resp = requests.get(
            f"{CENTRAL_URL}/api/config/history/global/global",
            headers=headers
        )
        assert resp.status_code == 200
        new_history = resp.json()
        assert new_history["active_version"] == data["new_version"]
        print(f"  History updated: active_version={new_history['active_version']}")

    def test_rollback_invalid_version_returns_404(self, central_token):
        """POST /api/config/rollback with non-existent version should return 404."""
        headers = {"Authorization": f"Bearer {central_token}", "Content-Type": "application/json"}
        resp = requests.post(
            f"{CENTRAL_URL}/api/config/rollback/global/global/99999",
            headers=headers
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"
        print("✓ Rollback to non-existent version correctly returns 404")


class TestMultipleUpserts:
    """Test that multiple upserts create history chain."""

    def test_multiple_upserts_create_history(self, central_token):
        """Multiple config updates should create history entries."""
        headers = {"Authorization": f"Bearer {central_token}", "Content-Type": "application/json"}
        
        # Get initial history count
        resp = requests.get(
            f"{CENTRAL_URL}/api/config/history/global/global",
            headers=headers
        )
        assert resp.status_code == 200
        initial_count = len(resp.json()["history"])
        
        # Make two updates
        for i in range(2):
            config = {
                "config_data": {
                    "pricing": {
                        "mode": "per_game",
                        "per_game": {"price_per_credit": 2.50 + (i * 0.1), "default_credits": 3}
                    },
                    "branding": {
                        "cafe_name": f"DartControl HQ Test {i}",
                        "primary_color": "#f59e0b"
                    }
                }
            }
            resp = requests.put(
                f"{CENTRAL_URL}/api/config/profile/global/global",
                json=config,
                headers=headers
            )
            assert resp.status_code == 200
        
        # Check history count increased
        resp = requests.get(
            f"{CENTRAL_URL}/api/config/history/global/global",
            headers=headers
        )
        assert resp.status_code == 200
        new_count = len(resp.json()["history"])
        assert new_count >= initial_count + 2
        print(f"✓ Multiple upserts created history: {initial_count} -> {new_count} entries")


class TestForceSyncEndpoint:
    """Test force sync still works."""

    def test_force_sync_works(self, local_token):
        """POST /api/settings/config-sync/force should work."""
        if not local_token:
            pytest.skip("Local auth not available")
        
        headers = {"Authorization": f"Bearer {local_token}", "Content-Type": "application/json"}
        resp = requests.post(
            f"{BACKEND_URL}/api/settings/config-sync/force",
            headers=headers
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "success" in data
        print(f"✓ Force sync works: {data}")


class TestKioskRegression:
    """Test kiosk UI still works (no regression)."""

    def test_kiosk_branding_endpoint(self):
        """GET /api/settings/branding should work."""
        resp = requests.get(f"{BACKEND_URL}/api/settings/branding")
        assert resp.status_code == 200
        data = resp.json()
        assert "cafe_name" in data
        print(f"✓ Kiosk branding works: cafe_name={data.get('cafe_name')}")

    def test_kiosk_pricing_endpoint(self):
        """GET /api/settings/pricing should work."""
        resp = requests.get(f"{BACKEND_URL}/api/settings/pricing")
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data or "per_game" in data
        print(f"✓ Kiosk pricing works: {data}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
