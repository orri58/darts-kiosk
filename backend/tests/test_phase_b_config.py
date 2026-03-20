"""
Phase B Testing — Central Config System & Admin Stripdown
Tests for:
1. Central config API endpoints (GET/PUT)
2. Local config sync endpoint
3. Config version incrementing
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://boardgame-repair.preview.emergentagent.com')
CENTRAL_URL = "http://127.0.0.1:8002"


class TestCentralConfigAPI:
    """Tests for central server config endpoints"""
    
    @pytest.fixture
    def superadmin_token(self):
        """Get superadmin JWT token"""
        response = requests.post(f"{CENTRAL_URL}/api/auth/login", json={
            "username": "superadmin",
            "password": "admin"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json()["access_token"]
    
    def test_get_config_effective_unauthenticated(self):
        """GET /api/config/effective should work without auth (for devices)"""
        response = requests.get(f"{CENTRAL_URL}/api/config/effective")
        assert response.status_code == 200
        
        data = response.json()
        assert "config" in data
        assert "version" in data
        assert "layers_applied" in data
        assert isinstance(data["config"], dict)
        assert isinstance(data["version"], int)
        assert "global" in data["layers_applied"]
        print(f"✓ Effective config returned with version {data['version']}")
    
    def test_get_config_profiles_requires_auth(self, superadmin_token):
        """GET /api/config/profiles requires auth"""
        # Without auth
        response = requests.get(f"{CENTRAL_URL}/api/config/profiles")
        assert response.status_code in [401, 403], "Should require auth"
        
        # With auth
        response = requests.get(
            f"{CENTRAL_URL}/api/config/profiles",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1, "Should have at least global profile"
        
        # Check global profile exists
        global_profile = next((p for p in data if p["scope_type"] == "global"), None)
        assert global_profile is not None, "Global profile should exist"
        print(f"✓ Found {len(data)} config profiles including global")
    
    def test_update_global_config_increments_version(self, superadmin_token):
        """PUT /api/config/profile/global/global should increment version"""
        headers = {"Authorization": f"Bearer {superadmin_token}"}
        
        # Get current config
        response = requests.get(f"{CENTRAL_URL}/api/config/effective")
        current_version = response.json()["version"]
        current_config = response.json()["config"]
        
        # Update config with minor change (add test timestamp)
        import time
        updated_config = current_config.copy()
        updated_config["_test_timestamp"] = int(time.time())
        
        response = requests.put(
            f"{CENTRAL_URL}/api/config/profile/global/global",
            headers=headers,
            json={"config_data": updated_config}
        )
        assert response.status_code == 200, f"Update failed: {response.text}"
        
        data = response.json()
        new_version = data["version"]
        assert new_version > current_version, f"Version should increment: {current_version} -> {new_version}"
        print(f"✓ Config version incremented: {current_version} -> {new_version}")
        
        # Verify effective config shows new version
        response = requests.get(f"{CENTRAL_URL}/api/config/effective")
        assert response.json()["version"] == new_version
    
    def test_config_hierarchy_layers(self, superadmin_token):
        """Test that effective config includes proper layers"""
        response = requests.get(f"{CENTRAL_URL}/api/config/effective")
        data = response.json()
        
        # Should have global layer at minimum
        assert "layers_applied" in data
        assert "global" in data["layers_applied"]
        
        # Config should have expected structure
        config = data["config"]
        assert "pricing" in config or "branding" in config or "kiosk" in config, \
            "Config should have at least one expected section"
        print(f"✓ Config layers: {data['layers_applied']}")


class TestLocalConfigSyncEndpoint:
    """Tests for local backend config sync status endpoint"""
    
    def test_config_sync_status_unauthenticated(self):
        """GET /api/licensing/config-sync-status should work without auth"""
        response = requests.get(f"{BASE_URL}/api/licensing/config-sync-status")
        assert response.status_code == 200
        
        data = response.json()
        assert "configured" in data
        assert "config_version" in data
        assert "running" in data
        assert "last_error" in data or data.get("last_error") is None
        print(f"✓ Config sync status: configured={data['configured']}, version={data['config_version']}")
    
    def test_force_config_sync_requires_auth(self):
        """POST /api/licensing/force-config-sync requires admin auth"""
        response = requests.post(f"{BASE_URL}/api/licensing/force-config-sync")
        assert response.status_code in [401, 403], "Should require auth"
        print("✓ Force config sync requires authentication")
    
    def test_effective_config_local(self):
        """GET /api/licensing/effective-config returns local config"""
        response = requests.get(f"{BASE_URL}/api/licensing/effective-config")
        assert response.status_code == 200
        
        data = response.json()
        assert "config" in data
        assert "version" in data
        assert "status" in data
        print(f"✓ Local effective config: version={data['version']}")


class TestCentralHealthEndpoint:
    """Test central server health"""
    
    def test_central_server_health(self):
        """Central server /api/health should return ok"""
        response = requests.get(f"{CENTRAL_URL}/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        print(f"✓ Central server healthy: version={data['version']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
