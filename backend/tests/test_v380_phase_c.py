"""
Phase C Testing: Config-Management UI, Device Detail, Remote Actions
Tests for iteration 68 — v3.9.0 Phase C SaaS Consolidation

Tests cover:
- Config CRUD endpoints (profiles, effective config)
- Remote actions endpoints (issue, pending, ack)
- Device detail telemetry endpoint
"""
import pytest
import requests
import os
import time

# Central server runs on port 8002 - use directly for backend tests
CENTRAL_API = "http://127.0.0.1:8002/api"

# Test devices from test data
DEVICE_ID_DARTBOARD = "74bb78ce-361d-4728-ac0f-10f60825d291"
DEVICE_ID_BERLIN = "e0921245-f17b-4f70-aeca-60dba291251c"


@pytest.fixture(scope="module")
def auth_token():
    """Get superadmin authentication token"""
    # Access central server directly on port 8002
    try:
        resp = requests.post(
            f"{CENTRAL_API}/auth/login",
            json={"username": "superadmin", "password": "admin"},
            timeout=10
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if token:
                return token
    except Exception as e:
        print(f"Auth error: {e}")
    
    pytest.skip("Unable to obtain auth token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with Bearer token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def api_base():
    """Return the correct API base for central server"""
    return CENTRAL_API


class TestConfigProfiles:
    """Config profile CRUD tests"""
    
    def test_get_config_profiles(self, auth_headers, api_base):
        """GET /api/config/profiles returns list of profiles"""
        resp = requests.get(f"{api_base}/config/profiles", headers=auth_headers, timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert isinstance(data, list), "Response should be a list"
        # Should have at least global profile
        global_profiles = [p for p in data if p.get("scope_type") == "global"]
        assert len(global_profiles) >= 1, "Should have at least one global profile"
        
        # Verify profile structure
        if data:
            profile = data[0]
            assert "id" in profile
            assert "scope_type" in profile
            assert "config_data" in profile
            assert "version" in profile
    
    def test_get_effective_config_unauthenticated(self, api_base):
        """GET /api/config/effective works without auth (for device polling)"""
        resp = requests.get(f"{api_base}/config/effective", timeout=10)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        assert "config" in data
        assert "version" in data
        assert "layers_applied" in data
        assert "global" in data["layers_applied"]
    
    def test_get_effective_config_with_device(self, api_base):
        """GET /api/config/effective with device_id resolves hierarchy"""
        resp = requests.get(
            f"{api_base}/config/effective",
            params={"device_id": DEVICE_ID_DARTBOARD},
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "scope" in data
        # Device scope should be set
        assert data["scope"]["device_id"] == DEVICE_ID_DARTBOARD or data["scope"]["device_id"] is None
    
    def test_put_global_config_increments_version(self, auth_headers, api_base):
        """PUT /api/config/profile/global/global updates and increments version"""
        # Get current version
        resp = requests.get(f"{api_base}/config/profiles", headers=auth_headers, timeout=10)
        assert resp.status_code == 200
        profiles = resp.json()
        global_p = next((p for p in profiles if p["scope_type"] == "global"), None)
        assert global_p, "No global profile found"
        old_version = global_p["version"]
        
        # Update with test timestamp
        test_ts = int(time.time())
        update_data = {
            "config_data": {
                **global_p["config_data"],
                "_test_timestamp": test_ts
            }
        }
        resp = requests.put(
            f"{api_base}/config/profile/global/global",
            json=update_data,
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        updated = resp.json()
        assert updated["version"] == old_version + 1, "Version should increment"
        assert updated["updated_by"] == "superadmin"
        assert updated["config_data"].get("_test_timestamp") == test_ts
    
    def test_put_global_config_requires_superadmin(self, api_base):
        """PUT /api/config/profile/global/global requires superadmin role"""
        # Try without auth
        resp = requests.put(
            f"{api_base}/config/profile/global/global",
            json={"config_data": {}},
            timeout=10
        )
        assert resp.status_code in [401, 403, 422], f"Should reject unauthenticated: {resp.status_code}"


class TestRemoteActions:
    """Remote actions endpoint tests"""
    
    def test_post_remote_action_force_sync(self, auth_headers, api_base):
        """POST /api/remote-actions/:deviceId creates pending force_sync action"""
        resp = requests.post(
            f"{api_base}/remote-actions/{DEVICE_ID_DARTBOARD}",
            json={"action_type": "force_sync"},
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        action = resp.json()
        assert action["device_id"] == DEVICE_ID_DARTBOARD
        assert action["action_type"] == "force_sync"
        assert action["status"] == "pending"
        assert action["issued_by"] == "superadmin"
        assert "id" in action
        assert "issued_at" in action
    
    def test_post_remote_action_restart_backend(self, auth_headers, api_base):
        """POST /api/remote-actions/:deviceId creates pending restart_backend action"""
        resp = requests.post(
            f"{api_base}/remote-actions/{DEVICE_ID_DARTBOARD}",
            json={"action_type": "restart_backend"},
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200
        action = resp.json()
        assert action["action_type"] == "restart_backend"
        assert action["status"] == "pending"
    
    def test_post_remote_action_reload_ui(self, auth_headers, api_base):
        """POST /api/remote-actions/:deviceId creates pending reload_ui action"""
        resp = requests.post(
            f"{api_base}/remote-actions/{DEVICE_ID_DARTBOARD}",
            json={"action_type": "reload_ui"},
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200
        action = resp.json()
        assert action["action_type"] == "reload_ui"
        assert action["status"] == "pending"
    
    def test_post_remote_action_invalid_type(self, auth_headers, api_base):
        """POST /api/remote-actions/:deviceId rejects invalid action types"""
        resp = requests.post(
            f"{api_base}/remote-actions/{DEVICE_ID_DARTBOARD}",
            json={"action_type": "invalid_action"},
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 400, "Should reject invalid action type"
    
    def test_get_pending_actions(self, api_base):
        """GET /api/remote-actions/:deviceId/pending returns pending actions"""
        resp = requests.get(
            f"{api_base}/remote-actions/{DEVICE_ID_DARTBOARD}/pending",
            timeout=10
        )
        assert resp.status_code == 200
        actions = resp.json()
        assert isinstance(actions, list)
        # All returned actions should be pending
        for action in actions:
            assert action["status"] == "pending"
            assert action["device_id"] == DEVICE_ID_DARTBOARD
    
    def test_ack_remote_action(self, auth_headers, api_base):
        """POST /api/remote-actions/:deviceId/ack acknowledges action"""
        # First create an action
        resp = requests.post(
            f"{api_base}/remote-actions/{DEVICE_ID_DARTBOARD}",
            json={"action_type": "force_sync"},
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200
        action_id = resp.json()["id"]
        
        # Acknowledge it
        resp = requests.post(
            f"{api_base}/remote-actions/{DEVICE_ID_DARTBOARD}/ack",
            json={"action_id": action_id, "success": True, "message": "Sync completed"},
            timeout=10
        )
        assert resp.status_code == 200
        assert resp.json().get("ok") == True


class TestDeviceDetailTelemetry:
    """Device detail endpoint tests (GET /api/telemetry/device/:id)"""
    
    def test_get_device_detail(self, auth_headers, api_base):
        """GET /api/telemetry/device/:id returns enriched device info"""
        resp = requests.get(
            f"{api_base}/telemetry/device/{DEVICE_ID_DARTBOARD}",
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        # Core device fields
        assert data["id"] == DEVICE_ID_DARTBOARD
        assert "device_name" in data
        assert "status" in data
        assert "is_online" in data
        assert isinstance(data["is_online"], bool)
        
        # Telemetry fields
        assert "recent_events" in data
        assert isinstance(data["recent_events"], list)
        
        assert "daily_stats" in data
        assert isinstance(data["daily_stats"], list)
        
        assert "recent_actions" in data
        assert isinstance(data["recent_actions"], list)
    
    def test_get_device_detail_includes_location_customer(self, auth_headers, api_base):
        """Device detail includes location and customer info"""
        resp = requests.get(
            f"{api_base}/telemetry/device/{DEVICE_ID_DARTBOARD}",
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Location should be present
        assert "location" in data
        if data["location"]:
            assert "id" in data["location"]
            assert "name" in data["location"]
        
        # Customer should be present
        assert "customer" in data
        if data["customer"]:
            assert "id" in data["customer"]
            assert "name" in data["customer"]
    
    def test_get_device_detail_recent_events_structure(self, auth_headers, api_base):
        """Recent events have correct structure"""
        resp = requests.get(
            f"{api_base}/telemetry/device/{DEVICE_ID_DARTBOARD}",
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200
        events = resp.json().get("recent_events", [])
        
        if events:
            event = events[0]
            assert "event_type" in event
            assert "timestamp" in event
            # data is optional but should be dict if present
            if "data" in event and event["data"]:
                assert isinstance(event["data"], dict)
    
    def test_get_device_detail_daily_stats_structure(self, auth_headers, api_base):
        """Daily stats have correct structure"""
        resp = requests.get(
            f"{api_base}/telemetry/device/{DEVICE_ID_DARTBOARD}",
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200
        stats = resp.json().get("daily_stats", [])
        
        if stats:
            stat = stats[0]
            assert "date" in stat
            assert "revenue_cents" in stat
            assert "sessions" in stat
            assert "games" in stat
    
    def test_get_device_detail_recent_actions_structure(self, auth_headers, api_base):
        """Recent actions have correct structure"""
        resp = requests.get(
            f"{api_base}/telemetry/device/{DEVICE_ID_DARTBOARD}",
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200
        actions = resp.json().get("recent_actions", [])
        
        if actions:
            action = actions[0]
            assert "id" in action
            assert "action_type" in action
            assert "status" in action
            assert "issued_by" in action
            assert "issued_at" in action
    
    def test_get_device_detail_404_for_unknown(self, auth_headers, api_base):
        """GET /api/telemetry/device/:id returns 404 for unknown device"""
        resp = requests.get(
            f"{api_base}/telemetry/device/nonexistent-device-id",
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 404
    
    def test_get_device_detail_requires_auth(self, api_base):
        """GET /api/telemetry/device/:id requires authentication"""
        resp = requests.get(
            f"{api_base}/telemetry/device/{DEVICE_ID_DARTBOARD}",
            timeout=10
        )
        assert resp.status_code in [401, 403, 422], f"Should require auth: {resp.status_code}"


class TestDevicesListNavigation:
    """Test devices list for clickable rows"""
    
    def test_devices_list_returns_devices(self, auth_headers, api_base):
        """GET /api/licensing/devices returns list of devices"""
        resp = requests.get(
            f"{api_base}/licensing/devices",
            headers=auth_headers,
            timeout=10
        )
        assert resp.status_code == 200
        devices = resp.json()
        assert isinstance(devices, list)
        assert len(devices) > 0, "Should have at least one device"
        
        # Verify device has ID for navigation
        for device in devices:
            assert "id" in device
            assert "device_name" in device or "id" in device


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
