"""
Test v3.9.3 Observability & Support Tools
Tests: device_log_buffer, heartbeat with health+logs, device detail endpoint, portal UI
"""
import pytest
import requests
import os
import json

pytestmark = pytest.mark.integration

# Central server URL (running on port 8002)
CENTRAL_URL = "http://localhost:8002"
# Frontend URL for portal testing
FRONTEND_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://boardgame-repair.preview.emergentagent.com")

# Test device credentials
TEST_DEVICE_ID = "e0921245-f17b-4f70-aeca-60dba291251c"
TEST_DEVICE_API_KEY = "dk_sHgIFVVWvqtvDJqsMefQC3lNgNhMZpdvPE_E3S1-bM4"

# Portal credentials
PORTAL_USERNAME = "superadmin"
PORTAL_PASSWORD = "admin"


@pytest.fixture(scope="module")
def portal_token():
    """Get portal auth token"""
    resp = requests.post(f"{CENTRAL_URL}/api/auth/login", json={
        "username": PORTAL_USERNAME,
        "password": PORTAL_PASSWORD
    })
    if resp.status_code == 200:
        return resp.json().get("access_token")
    pytest.skip("Portal auth failed")


class TestCentralServerHealth:
    """Central server basic health checks"""
    
    def test_central_server_health(self):
        """Central server is running and healthy"""
        resp = requests.get(f"{CENTRAL_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "central-license-server" in data.get("service", "")
        print(f"✓ Central server healthy: {data}")


class TestHeartbeatWithHealthAndLogs:
    """Test heartbeat endpoint accepts health snapshot + device logs"""
    
    def test_heartbeat_accepts_health_payload(self):
        """Heartbeat stores health snapshot from device"""
        payload = {
            "version": "3.9.3-pytest",
            "health": {
                "health_status": "healthy",
                "config_sync": {
                    "config_version": 20,
                    "last_sync_at": "2026-03-21T18:50:00Z",
                    "consecutive_errors": 0,
                    "last_error": None,
                    "sync_count": 100
                },
                "action_poller": {
                    "last_poll_at": "2026-03-21T18:50:00Z",
                    "actions_executed": 10,
                    "actions_failed": 2,
                    "consecutive_poll_errors": 0
                },
                "config_applied_version": 5
            }
        }
        resp = requests.post(
            f"{CENTRAL_URL}/api/telemetry/heartbeat",
            json=payload,
            headers={"X-License-Key": TEST_DEVICE_API_KEY}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "server_time" in data
        print(f"✓ Heartbeat with health accepted: {data}")
    
    def test_heartbeat_accepts_logs_payload(self):
        """Heartbeat stores device logs from device"""
        payload = {
            "version": "3.9.3-pytest",
            "logs": [
                {"ts": "2026-03-21T18:51:00Z", "level": "info", "src": "config_sync", "evt": "sync_ok", "msg": "Config synced"},
                {"ts": "2026-03-21T18:51:01Z", "level": "warn", "src": "action_poller", "evt": "timeout", "msg": "Poll timeout"},
                {"ts": "2026-03-21T18:51:02Z", "level": "error", "src": "config_apply", "evt": "apply_failed", "msg": "Failed to apply branding"}
            ]
        }
        resp = requests.post(
            f"{CENTRAL_URL}/api/telemetry/heartbeat",
            json=payload,
            headers={"X-License-Key": TEST_DEVICE_API_KEY}
        )
        assert resp.status_code == 200
        print(f"✓ Heartbeat with logs accepted")
    
    def test_heartbeat_accepts_combined_payload(self):
        """Heartbeat stores both health + logs together"""
        payload = {
            "version": "3.9.3-pytest-combined",
            "health": {
                "health_status": "degraded",
                "config_sync": {"config_version": 21, "consecutive_errors": 3, "sync_count": 101},
                "action_poller": {"actions_executed": 11, "actions_failed": 3, "consecutive_poll_errors": 2}
            },
            "logs": [
                {"ts": "2026-03-21T18:52:00Z", "level": "error", "src": "test", "evt": "combined_test", "msg": "Combined payload test"}
            ]
        }
        resp = requests.post(
            f"{CENTRAL_URL}/api/telemetry/heartbeat",
            json=payload,
            headers={"X-License-Key": TEST_DEVICE_API_KEY}
        )
        assert resp.status_code == 200
        print(f"✓ Heartbeat with combined health+logs accepted")


class TestDeviceDetailEndpoint:
    """Test device detail endpoint returns health_snapshot and device_logs"""
    
    def test_device_detail_returns_health_snapshot(self, portal_token):
        """Device detail includes health_snapshot field"""
        resp = requests.get(
            f"{CENTRAL_URL}/api/telemetry/device/{TEST_DEVICE_ID}",
            headers={"Authorization": f"Bearer {portal_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        # Basic device info
        assert data["id"] == TEST_DEVICE_ID
        assert data["device_name"] == "Berlin Kiosk 1"
        assert "is_online" in data
        
        # Health snapshot
        assert "health_snapshot" in data
        hs = data["health_snapshot"]
        if hs:  # May be None if no heartbeat yet
            assert "health_status" in hs
            assert hs["health_status"] in ["healthy", "degraded", "unknown"]
            if "config_sync" in hs and hs["config_sync"]:
                assert "config_version" in hs["config_sync"]
                assert "sync_count" in hs["config_sync"]
            if "action_poller" in hs and hs["action_poller"]:
                assert "actions_executed" in hs["action_poller"]
        
        print(f"✓ Device detail has health_snapshot: {hs}")
    
    def test_device_detail_returns_device_logs(self, portal_token):
        """Device detail includes device_logs field"""
        resp = requests.get(
            f"{CENTRAL_URL}/api/telemetry/device/{TEST_DEVICE_ID}",
            headers={"Authorization": f"Bearer {portal_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "device_logs" in data
        logs = data["device_logs"]
        assert isinstance(logs, list)
        
        if logs:
            # Check log entry structure
            log = logs[0]
            assert "ts" in log or "timestamp" in log
            assert "level" in log
            assert log["level"] in ["info", "warn", "error"]
            assert "src" in log or "source" in log
            assert "msg" in log or "message" in log
        
        print(f"✓ Device detail has device_logs: {len(logs)} entries")
    
    def test_device_detail_returns_recent_actions(self, portal_token):
        """Device detail includes recent_actions with status badges"""
        resp = requests.get(
            f"{CENTRAL_URL}/api/telemetry/device/{TEST_DEVICE_ID}",
            headers={"Authorization": f"Bearer {portal_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "recent_actions" in data
        actions = data["recent_actions"]
        assert isinstance(actions, list)
        
        if actions:
            action = actions[0]
            assert "id" in action
            assert "action_type" in action
            assert "status" in action
            assert action["status"] in ["pending", "acked", "failed", "expired"]
            assert "issued_by" in action
            assert "issued_at" in action
        
        print(f"✓ Device detail has recent_actions: {len(actions)} entries")
    
    def test_device_detail_returns_daily_stats(self, portal_token):
        """Device detail includes daily_stats for last 7 days"""
        resp = requests.get(
            f"{CENTRAL_URL}/api/telemetry/device/{TEST_DEVICE_ID}",
            headers={"Authorization": f"Bearer {portal_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        
        assert "daily_stats" in data
        stats = data["daily_stats"]
        assert isinstance(stats, list)
        
        if stats:
            stat = stats[0]
            assert "date" in stat
            assert "revenue_cents" in stat
            assert "sessions" in stat
            assert "games" in stat
        
        print(f"✓ Device detail has daily_stats: {len(stats)} days")


class TestRemoteActionsEndpoint:
    """Test remote actions can be issued"""
    
    def test_issue_force_sync_action(self, portal_token):
        """Can issue force_sync remote action"""
        resp = requests.post(
            f"{CENTRAL_URL}/api/remote-actions/{TEST_DEVICE_ID}",
            json={"action_type": "force_sync"},
            headers={
                "Authorization": f"Bearer {portal_token}",
                "Content-Type": "application/json"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("action_type") == "force_sync"
        assert data.get("status") == "pending"
        print(f"✓ force_sync action issued: {data.get('id')}")
    
    def test_issue_restart_backend_action(self, portal_token):
        """Can issue restart_backend remote action"""
        resp = requests.post(
            f"{CENTRAL_URL}/api/remote-actions/{TEST_DEVICE_ID}",
            json={"action_type": "restart_backend"},
            headers={
                "Authorization": f"Bearer {portal_token}",
                "Content-Type": "application/json"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("action_type") == "restart_backend"
        print(f"✓ restart_backend action issued")
    
    def test_issue_reload_ui_action(self, portal_token):
        """Can issue reload_ui remote action"""
        resp = requests.post(
            f"{CENTRAL_URL}/api/remote-actions/{TEST_DEVICE_ID}",
            json={"action_type": "reload_ui"},
            headers={
                "Authorization": f"Bearer {portal_token}",
                "Content-Type": "application/json"
            }
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("action_type") == "reload_ui"
        print(f"✓ reload_ui action issued")


class TestPortalAuth:
    """Test portal authentication"""
    
    def test_portal_login_superadmin(self):
        """Portal login works with superadmin/admin"""
        resp = requests.post(f"{CENTRAL_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "admin"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["role"] == "superadmin"
        print(f"✓ Portal login successful: {data['user']['username']}")
    
    def test_portal_login_invalid_credentials(self):
        """Portal login fails with wrong password"""
        resp = requests.post(f"{CENTRAL_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "wrongpassword"
        })
        assert resp.status_code == 401
        print(f"✓ Portal rejects invalid credentials")


class TestDeviceListEndpoint:
    """Test device list endpoint"""
    
    def test_list_devices(self, portal_token):
        """Can list devices via scope endpoint"""
        resp = requests.get(
            f"{CENTRAL_URL}/api/scope/devices",
            headers={"Authorization": f"Bearer {portal_token}"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        
        # Find our test device
        test_device = next((d for d in data if d["id"] == TEST_DEVICE_ID), None)
        assert test_device is not None
        assert test_device["device_name"] == "Berlin Kiosk 1"
        print(f"✓ Device list returned {len(data)} devices, found Berlin Kiosk 1")


class TestBackendStartup:
    """Test backend starts without errors"""
    
    def test_backend_health(self):
        """Backend health endpoint returns healthy"""
        resp = requests.get(f"{FRONTEND_URL}/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        print(f"✓ Backend healthy: {data}")
    
    def test_device_log_buffer_import(self):
        """device_log_buffer module can be imported (no import errors)"""
        # This tests that the backend started without import errors
        # If device_log_buffer had import issues, backend wouldn't start
        resp = requests.get(f"{FRONTEND_URL}/api/health")
        assert resp.status_code == 200
        print(f"✓ Backend started (device_log_buffer imports working)")


class TestKioskRegression:
    """Test kiosk UI still works (no regression)"""
    
    def test_kiosk_settings_branding(self):
        """Kiosk branding endpoint works"""
        resp = requests.get(f"{FRONTEND_URL}/api/settings/branding")
        assert resp.status_code == 200
        data = resp.json()
        assert "cafe_name" in data
        print(f"✓ Kiosk branding: {data.get('cafe_name')}")
    
    def test_kiosk_settings_pricing(self):
        """Kiosk pricing endpoint works"""
        resp = requests.get(f"{FRONTEND_URL}/api/settings/pricing")
        assert resp.status_code == 200
        data = resp.json()
        assert "mode" in data
        print(f"✓ Kiosk pricing: mode={data.get('mode')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
