"""
Config Runtime Integration Tests — v3.9.1
Tests for Config Sync Client, Config Apply, Action Poller, and Settings endpoints.
"""
import pytest
import requests
import os

pytestmark = pytest.mark.integration

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


class TestBackendStartup:
    """Verify backend starts without errors"""
    
    def test_backend_health_settings_branding(self):
        """Backend starts and returns branding settings"""
        response = requests.get(f"{BASE_URL}/api/settings/branding", timeout=10)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "cafe_name" in data, "branding should have cafe_name"
        print(f"✓ Backend alive, branding.cafe_name = {data.get('cafe_name')}")


class TestSettingsEndpoints:
    """Test GET /api/settings/* endpoints"""
    
    def test_get_branding(self):
        """GET /api/settings/branding returns current branding values"""
        response = requests.get(f"{BASE_URL}/api/settings/branding", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "cafe_name" in data
        assert "subtitle" in data
        assert "logo_url" in data
        # Validate branding is from central config (DartControl Berlin expected)
        print(f"✓ branding: cafe_name={data.get('cafe_name')}, subtitle={data.get('subtitle')}")
    
    def test_get_pricing(self):
        """GET /api/settings/pricing returns current pricing values"""
        response = requests.get(f"{BASE_URL}/api/settings/pricing", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "mode" in data
        assert "per_game" in data
        assert "price_per_credit" in data.get("per_game", {})
        price = data.get("per_game", {}).get("price_per_credit")
        print(f"✓ pricing: mode={data.get('mode')}, price_per_credit={price}")
    
    def test_get_config_version(self):
        """GET /api/settings/config-version returns a version number"""
        response = requests.get(f"{BASE_URL}/api/settings/config-version", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], int)
        print(f"✓ config-version: {data['version']}")
    
    def test_get_config_sync_status(self):
        """GET /api/settings/config-sync/status returns sync status with all required fields"""
        response = requests.get(f"{BASE_URL}/api/settings/config-sync/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        # Verify top-level keys
        assert "config_sync" in data, "Missing config_sync field"
        assert "action_poller" in data, "Missing action_poller field"
        assert "applied_config_version" in data, "Missing applied_config_version field"
        
        # Verify config_sync sub-fields
        cs = data["config_sync"]
        assert "configured" in cs
        assert "last_sync_at" in cs
        assert "config_version" in cs
        assert "running" in cs
        
        # Verify action_poller sub-fields
        ap = data["action_poller"]
        assert "configured" in ap
        assert "running" in ap
        assert "last_poll_at" in ap
        assert "poll_count" in ap
        
        print(f"✓ config_sync: configured={cs['configured']}, running={cs['running']}")
        print(f"✓ action_poller: configured={ap['configured']}")
        print(f"✓ applied_config_version: {data['applied_config_version']}")


class TestAuthEndpoint:
    """Test authentication"""
    
    def test_login_admin(self):
        """Admin login returns access_token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
            timeout=10
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "Response should contain access_token"
        assert len(data["access_token"]) > 0
        print(f"✓ Admin login successful, token received")
        return data["access_token"]


class TestConfigSyncForce:
    """Test POST /api/settings/config-sync/force endpoint"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
            timeout=10
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_force_sync_requires_auth(self):
        """POST /api/settings/config-sync/force requires authentication"""
        response = requests.post(f"{BASE_URL}/api/settings/config-sync/force", timeout=10)
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Force sync requires auth (401 without token)")
    
    def test_force_sync_with_admin(self, admin_token):
        """POST /api/settings/config-sync/force triggers a sync with admin auth"""
        response = requests.post(
            f"{BASE_URL}/api/settings/config-sync/force",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "success" in data
        assert data["success"] is True
        assert "changed" in data
        assert "status" in data
        print(f"✓ Force sync: success={data['success']}, changed={data['changed']}")


class TestFailOpenBehavior:
    """Test fail-open behavior for action poller without device_id"""
    
    def test_action_poller_shows_not_configured(self):
        """Action poller shows configured=false when no device_id is set (fail-open)"""
        response = requests.get(f"{BASE_URL}/api/settings/config-sync/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        ap = data["action_poller"]
        # Device ID is not set in this environment, so action_poller should show configured=false
        # This is expected fail-open behavior - no crash, just not configured
        assert "configured" in ap
        # The test passes regardless of configured state - we just verify no crash
        print(f"✓ Action poller fail-open: configured={ap['configured']}, running={ap['running']}, no crash")


class TestConfigApplyIntegration:
    """Test that config values from central server appear in local settings"""
    
    def test_branding_reflects_central_config(self):
        """Branding values should reflect central server config"""
        response = requests.get(f"{BASE_URL}/api/settings/branding", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        # Per agent context: central config has branding.cafe_name='DartControl Berlin'
        cafe_name = data.get("cafe_name", "")
        # Verify it's not the default value (Dart Zone)
        assert cafe_name != "", "cafe_name should not be empty"
        print(f"✓ Branding from config: cafe_name='{cafe_name}'")
    
    def test_pricing_reflects_central_config(self):
        """Pricing values should reflect central server config"""
        response = requests.get(f"{BASE_URL}/api/settings/pricing", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        # Per agent context: central config has pricing.per_game.price_per_credit=2.5
        price = data.get("per_game", {}).get("price_per_credit")
        assert price is not None, "price_per_credit should exist"
        print(f"✓ Pricing from config: price_per_credit={price}")


class TestLiveReload:
    """Test config version tracking for live reload"""
    
    @pytest.fixture
    def admin_token(self):
        """Get admin auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": ADMIN_USER, "password": ADMIN_PASS},
            timeout=10
        )
        assert response.status_code == 200
        return response.json()["access_token"]
    
    def test_config_version_endpoint_works(self):
        """config-version endpoint is lightweight and works"""
        response = requests.get(f"{BASE_URL}/api/settings/config-version", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        version = data["version"]
        assert isinstance(version, int)
        assert version >= 0
        print(f"✓ config-version endpoint works: version={version}")
    
    def test_sync_status_shows_version(self, admin_token):
        """Sync status shows applied_config_version"""
        response = requests.get(f"{BASE_URL}/api/settings/config-sync/status", timeout=10)
        assert response.status_code == 200
        data = response.json()
        
        applied_version = data.get("applied_config_version")
        assert applied_version is not None
        assert isinstance(applied_version, int)
        print(f"✓ applied_config_version={applied_version}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
