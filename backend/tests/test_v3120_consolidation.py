"""
v3.12.0 Consolidation Package Tests

Tests for:
- BLOCK 3 P0: Config Sync Status endpoint with new fields
- BLOCK 3 P0: Config sync client running status
- BLOCK 3 P0: Reconfigure-sync endpoint with license_check_triggered
- BLOCK 3 P0: Kiosk license-status returns active for registered device
- BLOCK 1: Registration status with device_id, license_id, plan_type, binding_status
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBlock3P0ConfigSync:
    """BLOCK 3 P0: Config Sync/Apply/Runtime fix tests"""
    
    def test_config_sync_status_returns_new_fields(self):
        """GET /api/settings/config-sync/status returns all required fields"""
        response = requests.get(f"{BASE_URL}/api/settings/config-sync/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify all new fields exist
        assert "received_config_version" in data, "Missing received_config_version field"
        assert "applied_config_version" in data, "Missing applied_config_version field"
        assert "last_applied_central_version" in data, "Missing last_applied_central_version field"
        assert "versions_in_sync" in data, "Missing versions_in_sync field"
        assert "source" in data, "Missing source field"
        
        # Verify config_sync nested object
        assert "config_sync" in data, "Missing config_sync object"
        cs = data["config_sync"]
        assert "configured" in cs, "Missing config_sync.configured"
        assert "running" in cs, "Missing config_sync.running"
        
        print(f"Config sync status: received_v={data['received_config_version']}, "
              f"applied_v={data['applied_config_version']}, "
              f"central_v={data['last_applied_central_version']}, "
              f"in_sync={data['versions_in_sync']}, source={data['source']}")
    
    def test_config_sync_client_is_running(self):
        """Config sync client should be running (running=true in status)"""
        response = requests.get(f"{BASE_URL}/api/settings/config-sync/status")
        assert response.status_code == 200
        
        data = response.json()
        cs = data.get("config_sync", {})
        
        # Config sync should be configured and running
        assert cs.get("configured") == True, "Config sync should be configured"
        assert cs.get("running") == True, "Config sync should be running"
        
        print(f"Config sync running: {cs.get('running')}, configured: {cs.get('configured')}")
    
    def test_reconfigure_sync_returns_license_check_triggered(self):
        """POST /api/internal/reconfigure-sync returns license_check_triggered in services"""
        response = requests.post(f"{BASE_URL}/api/internal/reconfigure-sync")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("reconfigured") == True, "Expected reconfigured=True"
        
        services = data.get("services", [])
        assert "license_check_triggered" in services, \
            f"Expected 'license_check_triggered' in services list, got: {services}"
        
        # Also verify config_sync is in the list (the P0 fix)
        assert "config_sync" in services, \
            f"Expected 'config_sync' in services list, got: {services}"
        
        print(f"Reconfigure services: {services}")
    
    def test_kiosk_license_status_returns_active_for_registered_device(self):
        """GET /api/kiosk/license-status returns status=active for registered device"""
        response = requests.get(f"{BASE_URL}/api/kiosk/license-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # For a registered device, status should NOT be no_license
        status = data.get("status")
        assert status != "no_license", \
            f"Expected status != 'no_license' for registered device, got: {status}"
        
        # Should be active (from registration data or cache)
        assert status == "active", f"Expected status='active', got: {status}"
        
        # Should indicate registered
        reg_status = data.get("registration_status")
        assert reg_status == "registered", f"Expected registration_status='registered', got: {reg_status}"
        
        print(f"Kiosk license status: {status}, registration: {reg_status}, source: {data.get('source')}")


class TestBlock1DeviceTrustBinding:
    """BLOCK 1: Device Trust/Binding hardening tests"""
    
    def test_registration_status_returns_all_fields(self):
        """GET /api/licensing/registration-status returns device_id, license_id, plan_type, binding_status"""
        response = requests.get(f"{BASE_URL}/api/licensing/registration-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        
        # Verify registration status
        assert data.get("status") == "registered", f"Expected status='registered', got: {data.get('status')}"
        
        # Verify all required fields exist
        assert "device_id" in data, "Missing device_id field"
        assert "license_id" in data, "Missing license_id field"
        assert "plan_type" in data, "Missing plan_type field"
        assert "binding_status" in data, "Missing binding_status field"
        assert "install_id" in data, "Missing install_id field"
        
        # Verify values are not empty
        assert data.get("device_id"), "device_id should not be empty"
        assert data.get("license_id"), "license_id should not be empty"
        assert data.get("plan_type"), "plan_type should not be empty"
        assert data.get("binding_status"), "binding_status should not be empty"
        
        print(f"Registration status: device_id={data.get('device_id')[:12]}..., "
              f"license_id={data.get('license_id')[:12]}..., "
              f"plan_type={data.get('plan_type')}, binding_status={data.get('binding_status')}")
    
    def test_registration_status_device_id_matches_file(self):
        """Verify device_id from API matches the persisted file"""
        response = requests.get(f"{BASE_URL}/api/licensing/registration-status")
        assert response.status_code == 200
        
        data = response.json()
        api_device_id = data.get("device_id")
        
        # Expected device_id from the registration file
        expected_device_id = "336b19fb-5b78-4bf9-8cbf-fb39da5f15f9"
        
        assert api_device_id == expected_device_id, \
            f"device_id mismatch: API={api_device_id}, expected={expected_device_id}"
        
        print(f"Device ID verified: {api_device_id}")


class TestBlock3ConfigSyncDetails:
    """Additional config sync detail tests"""
    
    def test_config_version_endpoint(self):
        """GET /api/settings/config-version returns version"""
        response = requests.get(f"{BASE_URL}/api/settings/config-version")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "version" in data, "Missing version field"
        print(f"Config version: {data.get('version')}")
    
    def test_licensing_config_sync_status(self):
        """GET /api/licensing/config-sync-status returns sync client status"""
        response = requests.get(f"{BASE_URL}/api/licensing/config-sync-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "configured" in data, "Missing configured field"
        assert "running" in data, "Missing running field"
        
        print(f"Licensing config sync: configured={data.get('configured')}, running={data.get('running')}")


class TestHealthEndpoints:
    """Health and system endpoints"""
    
    def test_health_detailed(self):
        """GET /api/health/detailed returns system health"""
        # Need auth for this endpoint
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json().get("access_token")
        
        response = requests.get(
            f"{BASE_URL}/api/health/detailed",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "status" in data, "Missing status field"
        assert "uptime_seconds" in data, "Missing uptime_seconds field"
        
        print(f"Health status: {data.get('status')}, uptime: {data.get('uptime_seconds')}s")


class TestAuthEndpoints:
    """Authentication tests"""
    
    def test_admin_login(self):
        """Admin login with admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Missing access_token"
        assert data.get("user", {}).get("role") == "admin", "Expected admin role"
        
        print(f"Admin login successful, role: {data.get('user', {}).get('role')}")
    
    def test_staff_login(self):
        """Staff login with wirt/wirt123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "wirt",
            "password": "wirt123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "access_token" in data, "Missing access_token"
        assert data.get("user", {}).get("role") == "staff", "Expected staff role"
        
        print(f"Staff login successful, role: {data.get('user', {}).get('role')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
