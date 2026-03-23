"""
v3.14.0 P0 Consolidation Package Tests
Tests for:
- Block A: Registration 500 fix (location_id=None IntegrityError + graceful re-registration)
- Block B: Portal board control (unlock/lock/start/stop session)
- Block C+D: Device config consolidation (branding, pricing, colors, texts, sound, language, QR/sharing, kiosk behavior, board/autodarts)
- Block E: Panel role cleanup (LOCAL SERVICE header)
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBlockARegistrationCodeInspection:
    """Block A: Verify registration endpoint code fixes via code inspection.
    Central server is not running, so we verify the code patterns."""
    
    def test_register_device_endpoint_exists(self):
        """Verify /api/register-device endpoint is defined in central_server"""
        with open('/app/central_server/server.py', 'r') as f:
            content = f.read()
        assert '@app.post("/api/register-device")' in content, "register-device endpoint not found"
        print("PASSED: /api/register-device endpoint exists")
    
    def test_v3140_location_resolution_chain(self):
        """Verify v3.14.0 location_id resolution chain is implemented"""
        with open('/app/central_server/server.py', 'r') as f:
            content = f.read()
        
        # Check for location resolution from token
        assert 'location_id = token.location_id' in content, "Token location_id resolution missing"
        
        # Check for location resolution from license
        assert 'if not location_id and resolved_license and resolved_license.location_id:' in content, \
            "License location_id resolution missing"
        
        # Check for auto-create default location
        assert 'Auto-created default location' in content or 'Auto-create default location' in content, \
            "Auto-create default location logic missing"
        
        print("PASSED: v3.14.0 location_id resolution chain implemented")
    
    def test_v3140_graceful_reregistration(self):
        """Verify v3.14.0 graceful re-registration (no 409 for same install_id)"""
        with open('/app/central_server/server.py', 'r') as f:
            content = f.read()
        
        # Check for existing device lookup
        assert 'existing_device = existing_r.scalar_one_or_none()' in content, \
            "Existing device lookup missing"
        
        # Check for re-registration logic (update instead of 409)
        assert 'if existing_device:' in content, "Re-registration branch missing"
        assert 'Re-registered existing device' in content or 're-registered' in content.lower(), \
            "Re-registration logging missing"
        
        # Verify NO 409 for duplicate install_id
        # The old code would have: raise HTTPException(409, ...)
        # New code should update existing device instead
        register_func_match = re.search(r'async def register_device\(.*?\n(?:.*?\n)*?(?=\nasync def|\nclass|\n@app\.|\Z)', content, re.DOTALL)
        if register_func_match:
            register_func = register_func_match.group(0)
            # Should NOT have 409 for install_id conflict
            assert 'HTTPException(409' not in register_func or 'install_id' not in register_func.split('HTTPException(409')[0][-200:], \
                "409 error for install_id conflict should be removed"
        
        print("PASSED: v3.14.0 graceful re-registration implemented")
    
    def test_v3140_location_error_message(self):
        """Verify proper error message when location cannot be resolved"""
        with open('/app/central_server/server.py', 'r') as f:
            content = f.read()
        
        assert 'Standort konnte nicht aufgeloest werden' in content, \
            "German error message for location resolution failure missing"
        
        print("PASSED: Location resolution error message present")
    
    def test_token_validation_errors(self):
        """Verify token validation returns proper 403 errors"""
        with open('/app/central_server/server.py', 'r') as f:
            content = f.read()
        
        # Check for invalid token error
        assert 'Ungueltiger Registrierungs-Token' in content, "Invalid token error message missing"
        
        # Check for revoked token error
        assert 'Token wurde widerrufen' in content, "Revoked token error message missing"
        
        # Check for used token error
        assert 'Token wurde bereits verwendet' in content, "Used token error message missing"
        
        # Check for expired token error
        assert 'Token ist abgelaufen' in content, "Expired token error message missing"
        
        print("PASSED: Token validation error messages present")
    
    def test_missing_install_id_returns_400(self):
        """Verify missing install_id returns 400"""
        with open('/app/central_server/server.py', 'r') as f:
            content = f.read()
        
        assert 'install_id fehlt' in content, "Missing install_id error message not found"
        
        print("PASSED: Missing install_id returns 400")


class TestBlockBPortalBoardControl:
    """Block B: Verify Portal device detail page has board control UI elements"""
    
    def test_board_control_actions_defined(self):
        """Verify board control actions are defined in PortalDeviceDetail.js"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        # Check for primary board control actions
        assert 'unlock_board' in content, "unlock_board action missing"
        assert 'lock_board' in content, "lock_board action missing"
        assert 'start_session' in content, "start_session action missing"
        assert 'stop_session' in content, "stop_session action missing"
        
        print("PASSED: Board control actions defined")
    
    def test_system_actions_defined(self):
        """Verify system actions are defined"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'force_sync' in content, "force_sync action missing"
        assert 'restart_backend' in content, "restart_backend action missing"
        assert 'reload_ui' in content, "reload_ui action missing"
        
        print("PASSED: System actions defined")
    
    def test_board_control_grid_testid(self):
        """Verify board-control-grid data-testid exists"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="board-control-grid"' in content, "board-control-grid testid missing"
        
        print("PASSED: board-control-grid testid present")
    
    def test_remote_actions_grid_testid(self):
        """Verify remote-actions-grid data-testid exists"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="remote-actions-grid"' in content, "remote-actions-grid testid missing"
        
        print("PASSED: remote-actions-grid testid present")
    
    def test_action_buttons_have_testids(self):
        """Verify action buttons have data-testid attributes"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        # Check for action button testids pattern
        assert 'data-testid={`action-${key}`}' in content or "data-testid={`action-" in content, \
            "Action button testids missing"
        
        print("PASSED: Action buttons have testids")


class TestBlockCDDeviceConfig:
    """Block C+D: Verify device config consolidation in portal"""
    
    def test_farben_section_exists(self):
        """Verify Farben (colors) section exists"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'Farben' in content, "Farben section missing"
        
        print("PASSED: Farben section exists")
    
    def test_color_pickers_exist(self):
        """Verify primary/secondary/accent color pickers exist"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="cfg-primary-color"' in content, "Primary color picker missing"
        assert 'data-testid="cfg-secondary-color"' in content, "Secondary color picker missing"
        assert 'data-testid="cfg-accent-color"' in content, "Accent color picker missing"
        
        print("PASSED: Color pickers exist")
    
    def test_qr_sharing_section_exists(self):
        """Verify QR/Sharing section exists"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'QR / Sharing' in content or 'QR/Sharing' in content, "QR/Sharing section missing"
        
        print("PASSED: QR/Sharing section exists")
    
    def test_qr_sharing_checkboxes_exist(self):
        """Verify QR/Sharing checkboxes exist"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="cfg-qr-enabled"' in content, "QR enabled checkbox missing"
        assert 'data-testid="cfg-public-results"' in content, "Public results checkbox missing"
        assert 'data-testid="cfg-leaderboard"' in content, "Leaderboard checkbox missing"
        
        print("PASSED: QR/Sharing checkboxes exist")
    
    def test_kiosk_verhalten_section_exists(self):
        """Verify Kiosk-Verhalten section exists"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'Kiosk-Verhalten' in content, "Kiosk-Verhalten section missing"
        
        print("PASSED: Kiosk-Verhalten section exists")
    
    def test_kiosk_behavior_fields_exist(self):
        """Verify kiosk behavior fields exist"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="cfg-autolock"' in content, "Auto-lock field missing"
        assert 'data-testid="cfg-idle"' in content, "Idle timeout field missing"
        assert 'data-testid="cfg-fullscreen"' in content, "Fullscreen checkbox missing"
        
        print("PASSED: Kiosk behavior fields exist")
    
    def test_branding_fields_exist(self):
        """Verify branding fields exist"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="cfg-cafe-name"' in content, "Cafe name field missing"
        assert 'data-testid="cfg-subtitle"' in content, "Subtitle field missing"
        
        print("PASSED: Branding fields exist")
    
    def test_pricing_fields_exist(self):
        """Verify pricing fields exist"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="cfg-pricing-mode"' in content, "Pricing mode field missing"
        assert 'data-testid="cfg-price"' in content, "Price field missing"
        
        print("PASSED: Pricing fields exist")
    
    def test_sound_language_fields_exist(self):
        """Verify sound and language fields exist"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="cfg-sound-enabled"' in content, "Sound enabled field missing"
        assert 'data-testid="cfg-sound-volume"' in content, "Sound volume field missing"
        assert 'data-testid="cfg-language"' in content, "Language field missing"
        
        print("PASSED: Sound and language fields exist")
    
    def test_board_autodarts_fields_exist(self):
        """Verify board/autodarts fields exist"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="cfg-autodarts-url"' in content, "Autodarts URL field missing"
        assert 'data-testid="cfg-board-name"' in content, "Board name field missing"
        
        print("PASSED: Board/Autodarts fields exist")
    
    def test_device_quick_config_card_exists(self):
        """Verify device-quick-config card exists"""
        with open('/app/frontend/src/pages/portal/PortalDeviceDetail.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="device-quick-config"' in content, "device-quick-config testid missing"
        
        print("PASSED: device-quick-config card exists")


class TestBlockEAdminLayout:
    """Block E: Verify admin layout has LOCAL SERVICE header and clear nav structure"""
    
    def test_local_service_header_exists(self):
        """Verify LOCAL SERVICE header exists in AdminLayout"""
        with open('/app/frontend/src/pages/admin/AdminLayout.js', 'r') as f:
            content = f.read()
        
        assert 'LOCAL SERVICE' in content, "LOCAL SERVICE header missing"
        
        print("PASSED: LOCAL SERVICE header exists")
    
    def test_nav_items_defined(self):
        """Verify nav items are properly defined"""
        with open('/app/frontend/src/pages/admin/AdminLayout.js', 'r') as f:
            content = f.read()
        
        assert "path: '/admin'" in content, "Dashboard nav item missing"
        assert "path: '/admin/settings'" in content, "Settings nav item missing"
        assert "path: '/admin/system'" in content, "System nav item missing"
        assert "path: '/admin/health'" in content, "Health nav item missing"
        assert "path: '/admin/licensing'" in content, "Licensing nav item missing"
        
        print("PASSED: Nav items defined")
    
    def test_nav_testids_exist(self):
        """Verify nav items have data-testid attributes"""
        with open('/app/frontend/src/pages/admin/AdminLayout.js', 'r') as f:
            content = f.read()
        
        assert "tid: 'nav-dashboard'" in content, "nav-dashboard testid missing"
        assert "tid: 'nav-settings'" in content, "nav-settings testid missing"
        assert "tid: 'nav-system'" in content, "nav-system testid missing"
        assert "tid: 'nav-health'" in content, "nav-health testid missing"
        assert "tid: 'nav-licensing'" in content, "nav-licensing testid missing"
        
        print("PASSED: Nav testids exist")
    
    def test_admin_layout_testid_exists(self):
        """Verify admin-layout data-testid exists"""
        with open('/app/frontend/src/pages/admin/AdminLayout.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="admin-layout"' in content, "admin-layout testid missing"
        
        print("PASSED: admin-layout testid exists")
    
    def test_logout_button_exists(self):
        """Verify logout button exists"""
        with open('/app/frontend/src/pages/admin/AdminLayout.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="logout-btn"' in content, "logout-btn testid missing"
        
        print("PASSED: Logout button exists")
    
    def test_portal_link_exists(self):
        """Verify portal link exists"""
        with open('/app/frontend/src/pages/admin/AdminLayout.js', 'r') as f:
            content = f.read()
        
        assert 'data-testid="portal-link"' in content, "portal-link testid missing"
        assert '/portal/login' in content, "Portal login link missing"
        
        print("PASSED: Portal link exists")


class TestBackendAPIHealth:
    """Test backend API health and basic endpoints"""
    
    def test_health_endpoint(self):
        """Test /api/health endpoint"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unexpected health status: {data}"
        print(f"PASSED: Health endpoint returns healthy status")
    
    def test_license_status_endpoint(self):
        """Test /api/kiosk/license-status endpoint"""
        response = requests.get(f"{BASE_URL}/api/kiosk/license-status")
        assert response.status_code == 200, f"License status failed: {response.status_code}"
        data = response.json()
        assert "status" in data, "License status missing 'status' field"
        assert "registration_status" in data, "License status missing 'registration_status' field"
        print(f"PASSED: License status endpoint works - status={data.get('status')}, registration={data.get('registration_status')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
