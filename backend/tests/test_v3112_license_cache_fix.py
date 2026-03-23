"""
Test Suite for v3.11.2 License Cache Bug Fix

Tests the fix for: After device registration, license_service continued to cache 
status=no_license, preventing telemetry_sync, config_sync, and action_poller from 
recognizing the device as licensed.

Key fixes verified:
1. device_id persistence after registration
2. immediate license check after reconfigure
3. direct cache update with registration data
4. fail-safe to prevent overwriting valid cache with no_license
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"


class TestLicenseCacheFix:
    """Tests for the license cache bug fix in v3.11.2"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        # Login to get auth token
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USER,
            "password": ADMIN_PASS
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()

    # =========================================================================
    # Test 1: GET /api/kiosk/license-status should return status=active
    # =========================================================================
    def test_kiosk_license_status_returns_active(self):
        """
        GET /api/kiosk/license-status should return status=active (not no_license)
        when device is registered.
        """
        response = self.session.get(f"{BASE_URL}/api/kiosk/license-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Kiosk license status response: {json.dumps(data, indent=2)}")
        
        # Key assertion: status should NOT be no_license
        assert data.get("status") != "no_license", \
            f"BUG: status is 'no_license' but device is registered. Got: {data}"
        
        # Should be active (from registration data or cache)
        assert data.get("status") == "active", \
            f"Expected status='active', got '{data.get('status')}'"
        
        # Should indicate device is registered
        assert data.get("registration_status") == "registered", \
            f"Expected registration_status='registered', got '{data.get('registration_status')}'"
        
        print("✓ Kiosk license status correctly returns 'active' for registered device")

    # =========================================================================
    # Test 2: GET /api/licensing/registration-status should return full data
    # =========================================================================
    def test_registration_status_returns_full_data(self):
        """
        GET /api/licensing/registration-status should return full registration data
        including license_id, plan_type, binding_status.
        """
        response = self.session.get(f"{BASE_URL}/api/licensing/registration-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Registration status response: {json.dumps(data, indent=2)}")
        
        # Should be registered
        assert data.get("status") == "registered", \
            f"Expected status='registered', got '{data.get('status')}'"
        
        # Should have device_id
        assert data.get("device_id"), "Missing device_id in registration status"
        
        # Should have license_id (from registration)
        assert data.get("license_id"), "Missing license_id in registration status"
        
        # Should have plan_type
        assert data.get("plan_type"), "Missing plan_type in registration status"
        
        # Should have binding_status
        assert data.get("binding_status"), "Missing binding_status in registration status"
        
        # Should have license_status
        assert data.get("license_status") == "active", \
            f"Expected license_status='active', got '{data.get('license_status')}'"
        
        print(f"✓ Registration status returns full data: device_id={data.get('device_id')}, "
              f"license_id={data.get('license_id')}, plan_type={data.get('plan_type')}")

    # =========================================================================
    # Test 3: POST /api/internal/reconfigure-sync should work
    # =========================================================================
    def test_reconfigure_sync_returns_success(self):
        """
        POST /api/internal/reconfigure-sync should return reconfigured=true
        with license_check_triggered in services list.
        """
        response = self.session.post(f"{BASE_URL}/api/internal/reconfigure-sync")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Reconfigure sync response: {json.dumps(data, indent=2)}")
        
        # Should indicate reconfigured
        assert data.get("reconfigured") == True, \
            f"Expected reconfigured=True, got {data.get('reconfigured')}"
        
        # Should have services list
        services = data.get("services", [])
        assert isinstance(services, list), "services should be a list"
        
        # Should include license_check_triggered
        assert "license_check_triggered" in services, \
            f"Expected 'license_check_triggered' in services, got {services}"
        
        # device_id can be null if central server is unavailable (expected in preview)
        # but the field should be present
        assert "device_id" in data, "device_id field should be present in response"
        
        print(f"✓ Reconfigure sync successful: services={services}")

    # =========================================================================
    # Test 4: GET /api/licensing/status/cached should return valid cache
    # =========================================================================
    def test_cached_status_not_no_license(self):
        """
        GET /api/licensing/status/cached should return cached status
        (not no_license when device is registered).
        """
        response = self.session.get(f"{BASE_URL}/api/licensing/status/cached")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"Cached status response: {json.dumps(data, indent=2)}")
        
        # Should have status field
        assert "status" in data, "Missing 'status' field in response"
        
        # If we have cached license status, it should not be no_license
        if data.get("status") == "cached":
            license_status = data.get("license_status", {})
            cached_status = license_status.get("status")
            
            assert cached_status != "no_license", \
                f"BUG: cached status is 'no_license' but device is registered. Got: {license_status}"
            
            assert cached_status == "active", \
                f"Expected cached status='active', got '{cached_status}'"
            
            print(f"✓ Cached status is valid: {cached_status}")
        else:
            # No cache is also acceptable if it's a fresh start
            print(f"Note: No cache available (status={data.get('status')})")

    # =========================================================================
    # Test 5: Verify license cache file content
    # =========================================================================
    def test_license_cache_file_content(self):
        """
        The license cache file at /app/data/license_cache.json should contain
        status=active (not no_license).
        """
        cache_file = "/app/data/license_cache.json"
        
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
        except FileNotFoundError:
            pytest.skip(f"Cache file not found at {cache_file}")
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in cache file: {e}")
        
        print(f"License cache file content: {json.dumps(cache_data, indent=2)}")
        
        # Get the license_status from cache
        license_status = cache_data.get("license_status", {})
        status = license_status.get("status")
        
        # Key assertion: status should NOT be no_license
        assert status != "no_license", \
            f"BUG: cache file has status='no_license' but device is registered. Got: {license_status}"
        
        assert status == "active", \
            f"Expected status='active' in cache file, got '{status}'"
        
        # Verify source indicates it came from registration or remote sync
        source = license_status.get("source")
        assert source in ("registration", "registration_data", "remote", "cache_preserved"), \
            f"Expected source to be registration/remote related, got '{source}'"
        
        print(f"✓ Cache file has valid status: {status} (source={source})")

    # =========================================================================
    # Test 6: Verify kiosk license status preserves cache on local no_license
    # =========================================================================
    def test_kiosk_status_preserves_cache_when_registered(self):
        """
        When local DB returns no_license but device IS registered,
        the kiosk endpoint should use cached/registration data instead.
        """
        # First, get the registration status to confirm device is registered
        reg_response = self.session.get(f"{BASE_URL}/api/licensing/registration-status")
        assert reg_response.status_code == 200
        reg_data = reg_response.json()
        
        if reg_data.get("status") != "registered":
            pytest.skip("Device is not registered, cannot test cache preservation")
        
        # Now get kiosk license status
        kiosk_response = self.session.get(f"{BASE_URL}/api/kiosk/license-status")
        assert kiosk_response.status_code == 200
        kiosk_data = kiosk_response.json()
        
        print(f"Kiosk status with registered device: {json.dumps(kiosk_data, indent=2)}")
        
        # The status should NOT be no_license
        assert kiosk_data.get("status") != "no_license", \
            "BUG: Kiosk status returned no_license for registered device"
        
        # Should indicate registration status
        assert kiosk_data.get("registration_status") == "registered", \
            f"Expected registration_status='registered', got '{kiosk_data.get('registration_status')}'"
        
        # Source should indicate it came from cache or registration data
        source = kiosk_data.get("source")
        if source:
            assert source in ("cache", "registration_data", "registration", "remote"), \
                f"Unexpected source: {source}"
            print(f"✓ Kiosk status correctly uses {source} instead of local no_license")
        else:
            print("✓ Kiosk status correctly returns active for registered device")

    # =========================================================================
    # Test 7: Verify cyclic license checker preserves cache
    # =========================================================================
    def test_license_check_status_shows_cache_preserved(self):
        """
        GET /api/licensing/check-status should show the cyclic checker
        is preserving cache when local returns no_license for registered device.
        """
        response = self.session.get(f"{BASE_URL}/api/licensing/check-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        print(f"License check status: {json.dumps(data, indent=2)}")
        
        # Should be running
        assert data.get("running") == True, "Cyclic license checker should be running"
        
        # Should have done at least one check
        assert data.get("check_count", 0) >= 1, "Should have completed at least one check"
        
        # Last check should be OK
        assert data.get("last_check_ok") == True, \
            f"Last check should be OK, got {data.get('last_check_ok')}"
        
        # Last check status should be active (not no_license)
        last_status = data.get("last_check_status")
        assert last_status != "no_license", \
            f"BUG: last_check_status is 'no_license' but device is registered"
        
        assert last_status == "active", \
            f"Expected last_check_status='active', got '{last_status}'"
        
        # Source should indicate cache was preserved or registration data used
        source = data.get("last_check_source")
        print(f"✓ License checker status: {last_status} (source={source})")


class TestReconfigureSyncEndpoint:
    """Tests specifically for the /api/internal/reconfigure-sync endpoint"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        yield
        self.session.close()

    def test_reconfigure_sync_endpoint_exists(self):
        """Verify the reconfigure-sync endpoint exists and is accessible"""
        response = self.session.post(f"{BASE_URL}/api/internal/reconfigure-sync")
        # Should not be 404
        assert response.status_code != 404, "Endpoint /api/internal/reconfigure-sync not found"
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("✓ Reconfigure sync endpoint exists and is accessible")

    def test_reconfigure_sync_triggers_license_check(self):
        """Verify reconfigure-sync triggers an immediate license check"""
        response = self.session.post(f"{BASE_URL}/api/internal/reconfigure-sync")
        assert response.status_code == 200
        
        data = response.json()
        services = data.get("services", [])
        
        assert "license_check_triggered" in services, \
            f"license_check_triggered should be in services list: {services}"
        
        print("✓ Reconfigure sync triggers immediate license check")

    def test_reconfigure_sync_includes_expected_services(self):
        """Verify reconfigure-sync reconfigures all expected services"""
        response = self.session.post(f"{BASE_URL}/api/internal/reconfigure-sync")
        assert response.status_code == 200
        
        data = response.json()
        services = data.get("services", [])
        
        # Expected services that should be reconfigured
        expected_services = [
            "telemetry_sync",
            "config_sync", 
            "action_poller",
            "offline_queue",
            "ws_push_client",
            "license_check_triggered"
        ]
        
        for svc in expected_services:
            assert svc in services, f"Expected '{svc}' in services list: {services}"
        
        print(f"✓ All expected services reconfigured: {services}")


class TestRegistrationDataPersistence:
    """Tests for device_id and registration data persistence"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USER,
            "password": ADMIN_PASS
        })
        if login_resp.status_code == 200:
            token = login_resp.json().get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        yield
        self.session.close()

    def test_registration_data_file_exists(self):
        """Verify device_registration.json file exists with valid data"""
        reg_file = "/app/data/device_registration.json"
        
        try:
            with open(reg_file, 'r') as f:
                reg_data = json.load(f)
        except FileNotFoundError:
            pytest.skip(f"Registration file not found at {reg_file}")
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON in registration file: {e}")
        
        print(f"Registration file content: {json.dumps(reg_data, indent=2)}")
        
        # Should have device_id
        assert reg_data.get("device_id"), "Missing device_id in registration file"
        
        # Should have api_key
        assert reg_data.get("api_key"), "Missing api_key in registration file"
        
        # Should have license_status
        assert reg_data.get("license_status") == "active", \
            f"Expected license_status='active', got '{reg_data.get('license_status')}'"
        
        print(f"✓ Registration file has valid data: device_id={reg_data.get('device_id')}")

    def test_registration_status_matches_file(self):
        """Verify API registration status matches the file data"""
        # Read file
        reg_file = "/app/data/device_registration.json"
        try:
            with open(reg_file, 'r') as f:
                file_data = json.load(f)
        except FileNotFoundError:
            pytest.skip("Registration file not found")
        
        # Get API response
        response = self.session.get(f"{BASE_URL}/api/licensing/registration-status")
        assert response.status_code == 200
        api_data = response.json()
        
        # Compare key fields
        assert api_data.get("device_id") == file_data.get("device_id"), \
            f"device_id mismatch: API={api_data.get('device_id')}, file={file_data.get('device_id')}"
        
        assert api_data.get("license_status") == file_data.get("license_status"), \
            f"license_status mismatch: API={api_data.get('license_status')}, file={file_data.get('license_status')}"
        
        print("✓ API registration status matches file data")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
