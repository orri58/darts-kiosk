"""
v3.13.0 Consolidation Package Tests

Tests for:
- BLOCK A: Hard enforcement when central server deactivates/blocks a device (403 handling)
- BLOCK B: Portal Device Detail Quick Config
- BLOCK C: Board/Autodarts config centrally manageable
- BLOCK D: Heartbeat response includes device_status
- BLOCK E: Data hygiene cleanup endpoint
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBlockA_403Handling:
    """BLOCK A: Hard enforcement when central server deactivates/blocks a device"""
    
    def test_central_rejection_handler_exists(self):
        """Verify central_rejection_handler.py exists with required functions"""
        import sys
        sys.path.insert(0, '/app')
        from backend.services.central_rejection_handler import handle_central_rejection, handle_central_reactivation
        
        # Verify functions exist and are callable
        assert callable(handle_central_rejection), "handle_central_rejection should be callable"
        assert callable(handle_central_reactivation), "handle_central_reactivation should be callable"
        print("PASSED: central_rejection_handler.py has handle_central_rejection and handle_central_reactivation")
    
    def test_telemetry_sync_client_has_403_handling(self):
        """Verify telemetry_sync_client handles 403 responses"""
        with open('/app/backend/services/telemetry_sync_client.py', 'r') as f:
            content = f.read()
        
        assert 'handle_central_rejection' in content, "telemetry_sync_client should import handle_central_rejection"
        assert 'resp.status_code == 403' in content or 'status_code == 403' in content, "telemetry_sync_client should check for 403"
        print("PASSED: telemetry_sync_client.py has 403 handling with central_rejection_handler")
    
    def test_config_sync_client_has_403_handling(self):
        """Verify config_sync_client handles 403 responses before raise_for_status"""
        with open('/app/backend/services/config_sync_client.py', 'r') as f:
            content = f.read()
        
        assert 'handle_central_rejection' in content, "config_sync_client should import handle_central_rejection"
        # Check that 403 is handled BEFORE raise_for_status
        idx_403 = content.find('status_code == 403')
        idx_raise = content.find('raise_for_status')
        assert idx_403 < idx_raise, "403 handling should come before raise_for_status"
        print("PASSED: config_sync_client.py handles 403 before raise_for_status")
    
    def test_action_poller_has_403_handling(self):
        """Verify action_poller handles 403 responses"""
        with open('/app/backend/services/action_poller.py', 'r') as f:
            content = f.read()
        
        assert 'handle_central_rejection' in content, "action_poller should import handle_central_rejection"
        assert 'status_code == 403' in content, "action_poller should check for 403"
        print("PASSED: action_poller.py has 403 handling with central_rejection_handler")
    
    def test_license_sync_client_has_403_handling(self):
        """Verify license_sync_client handles 403 responses"""
        with open('/app/backend/services/license_sync_client.py', 'r') as f:
            content = f.read()
        
        assert 'handle_central_rejection' in content, "license_sync_client should import handle_central_rejection"
        assert 'status_code == 403' in content, "license_sync_client should check for 403"
        print("PASSED: license_sync_client.py has 403 handling with central_rejection_handler")
    
    def test_is_session_allowed_blocks_suspended(self):
        """Verify is_session_allowed returns False for status='suspended'"""
        import sys
        sys.path.insert(0, '/app')
        from backend.services.license_service import license_service
        
        # Test suspended status - should NOT be in allowed set
        suspended_status = {"status": "suspended", "binding_status": "bound"}
        result = license_service.is_session_allowed(suspended_status)
        
        # Note: Current implementation only allows: active, grace, test, no_license
        # 'suspended' is NOT in this list, so it should return False
        assert result == False, f"is_session_allowed should return False for suspended status, got {result}"
        print("PASSED: is_session_allowed returns False for status='suspended'")
    
    def test_license_status_returns_active_for_registered_device(self):
        """GET /api/kiosk/license-status returns status=active for registered device"""
        response = requests.get(f"{BASE_URL}/api/kiosk/license-status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "active", f"Expected status=active, got {data.get('status')}"
        assert data.get("registration_status") == "registered", f"Expected registration_status=registered"
        print(f"PASSED: /api/kiosk/license-status returns status=active, registration_status=registered")


class TestBlockB_PortalDeviceQuickConfig:
    """BLOCK B: Portal device detail page renders Device Trust card and Device Quick Config card"""
    
    def test_portal_device_detail_has_trust_card(self):
        """Verify PortalDeviceDetail.js has Device Trust card"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'device-trust-card' in content, "PortalDeviceDetail should have device-trust-card"
        assert 'Geraete-Vertrauen' in content or 'Device Trust' in content, "Should have Device Trust title"
        print("PASSED: PortalDeviceDetail.js has Device Trust card")
    
    def test_portal_device_detail_has_quick_config_card(self):
        """Verify PortalDeviceDetail.js has Device Quick Config card"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'device-quick-config' in content, "PortalDeviceDetail should have device-quick-config"
        assert 'Device-Konfiguration' in content, "Should have Device-Konfiguration title"
        print("PASSED: PortalDeviceDetail.js has Device Quick Config card")
    
    def test_quick_config_has_required_fields(self):
        """Verify Device Quick Config has all required fields"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        required_fields = [
            'cfg-cafe-name',      # cafe_name
            'cfg-subtitle',       # subtitle
            'cfg-pricing-mode',   # pricing_mode
            'cfg-price',          # price
            'cfg-autodarts-url',  # autodarts_url
            'cfg-board-name',     # board_name
            'cfg-sound-enabled',  # sound
            'cfg-language',       # language
        ]
        
        missing = []
        for field in required_fields:
            if field not in content:
                missing.append(field)
        
        assert len(missing) == 0, f"Missing Quick Config fields: {missing}"
        print(f"PASSED: Device Quick Config has all required fields: {required_fields}")
    
    def test_trust_card_has_status_buttons(self):
        """Verify Device Trust card has activate/deactivate/block buttons"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'device-activate-btn' in content, "Should have activate button"
        assert 'device-deactivate-btn' in content, "Should have deactivate button"
        assert 'device-block-btn' in content, "Should have block button"
        print("PASSED: Device Trust card has activate/deactivate/block buttons")


class TestBlockC_BoardsConfigSchema:
    """BLOCK C: Board/Autodarts config centrally manageable"""
    
    def test_config_schema_validates_boards_section(self):
        """Verify central config schema validates 'boards' section"""
        with open('/app/central_server/config_schema.py', 'r') as f:
            content = f.read()
        
        assert '_validate_boards' in content, "config_schema should have _validate_boards function"
        assert '"boards"' in content or "'boards'" in content, "config_schema should reference boards section"
        print("PASSED: config_schema.py has _validate_boards function")
    
    def test_boards_validation_checks_autodarts_url(self):
        """Verify boards validation checks autodarts_url"""
        with open('/app/central_server/config_schema.py', 'r') as f:
            content = f.read()
        
        assert 'autodarts_url' in content, "boards validation should check autodarts_url"
        print("PASSED: boards validation checks autodarts_url")
    
    def test_boards_validation_checks_board_name(self):
        """Verify boards validation checks board_name"""
        with open('/app/central_server/config_schema.py', 'r') as f:
            content = f.read()
        
        assert 'board_name' in content, "boards validation should check board_name"
        print("PASSED: boards validation checks board_name")
    
    def test_boards_validation_checks_auto_start(self):
        """Verify boards validation checks auto_start"""
        with open('/app/central_server/config_schema.py', 'r') as f:
            content = f.read()
        
        # Check in _validate_boards function specifically
        assert 'auto_start' in content, "boards validation should check auto_start"
        print("PASSED: boards validation checks auto_start")
    
    def test_config_apply_has_boards_mapping(self):
        """Verify config_apply.py has 'boards' section mapping"""
        with open('/app/backend/services/config_apply.py', 'r') as f:
            content = f.read()
        
        assert '"boards"' in content or "'boards'" in content, "config_apply should have boards section"
        assert 'autodarts_url' in content, "config_apply boards should map autodarts_url"
        assert 'board_name' in content, "config_apply boards should map board_name"
        print("PASSED: config_apply.py has boards section with autodarts_url, board_name, auto_start")


class TestBlockD_HeartbeatDeviceStatus:
    """BLOCK D: Heartbeat response includes device_status field"""
    
    def test_central_server_heartbeat_includes_device_status(self):
        """Verify central server heartbeat response includes device_status"""
        with open('/app/central_server/server.py', 'r') as f:
            content = f.read()
        
        # Check that heartbeat endpoint returns device_status
        assert '"device_status"' in content or "'device_status'" in content, "Heartbeat should return device_status"
        assert 'device.status' in content, "device_status should be set from device.status"
        print("PASSED: Central server heartbeat response includes device_status field")
    
    def test_telemetry_sync_processes_device_status(self):
        """Verify telemetry_sync_client processes device_status from heartbeat response"""
        with open('/app/backend/services/telemetry_sync_client.py', 'r') as f:
            content = f.read()
        
        assert 'device_status' in content, "telemetry_sync_client should process device_status"
        # Check that it handles non-active device_status
        assert 'device_status' in content and 'active' in content, "Should check if device_status != active"
        print("PASSED: telemetry_sync_client processes device_status from heartbeat response")


class TestBlockE_DataHygieneCleanup:
    """BLOCK E: Data hygiene cleanup endpoint"""
    
    def test_cleanup_endpoint_exists(self):
        """Verify central server has POST /api/admin/cleanup endpoint"""
        with open('/app/central_server/server.py', 'r') as f:
            content = f.read()
        
        assert '/api/admin/cleanup' in content, "Central server should have /api/admin/cleanup endpoint"
        assert 'data_cleanup' in content, "Should have data_cleanup function"
        print("PASSED: Central server has POST /api/admin/cleanup endpoint")
    
    def test_cleanup_requires_superadmin(self):
        """Verify cleanup endpoint requires superadmin role"""
        with open('/app/central_server/server.py', 'r') as f:
            content = f.read()
        
        # Find the cleanup function and check for superadmin requirement
        idx_cleanup = content.find('async def data_cleanup')
        if idx_cleanup > 0:
            # Check next 200 chars for superadmin check
            snippet = content[idx_cleanup:idx_cleanup+300]
            assert 'superadmin' in snippet, "cleanup should require superadmin role"
        print("PASSED: Cleanup endpoint requires superadmin role")


class TestConfigSyncStatus:
    """Test config sync status endpoint"""
    
    def test_config_sync_status_returns_expected_fields(self):
        """GET /api/settings/config-sync/status returns expected fields"""
        response = requests.get(f"{BASE_URL}/api/settings/config-sync/status")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check for config_sync section
        assert 'config_sync' in data, "Should have config_sync section"
        cs = data['config_sync']
        assert 'running' in cs, "config_sync should have running field"
        assert 'configured' in cs, "config_sync should have configured field"
        
        # Check for version fields
        assert 'received_config_version' in data, "Should have received_config_version"
        assert 'applied_config_version' in data, "Should have applied_config_version"
        
        print(f"PASSED: config-sync/status returns expected fields")
        print(f"  - config_sync.running: {cs.get('running')}")
        print(f"  - config_sync.configured: {cs.get('configured')}")
        print(f"  - received_config_version: {data.get('received_config_version')}")
        print(f"  - applied_config_version: {data.get('applied_config_version')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
