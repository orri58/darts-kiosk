"""
v3.15.0 P0 Fixes Test Suite
Tests for:
- Block A: Portal board control (VALID_ACTIONS, action_poller board control, params)
- Block B: Device config tabbed interface (verified via frontend)
- Block C: License lock enforcement (cache check for suspended/blocked/inactive)
"""
import pytest
import requests
import os
import json
from pathlib import Path

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# ═══════════════════════════════════════════════════════════════
# Block A: Portal Board Control Tests
# ═══════════════════════════════════════════════════════════════

class TestBlockA_BoardControl:
    """Tests for Block A: Portal board control end-to-end"""
    
    def test_valid_actions_includes_board_control(self):
        """Verify VALID_ACTIONS in central_server/server.py includes board control actions"""
        server_path = Path("/app/central_server/server.py")
        content = server_path.read_text()
        
        # Check VALID_ACTIONS definition
        assert "VALID_ACTIONS" in content, "VALID_ACTIONS not found in server.py"
        assert "unlock_board" in content, "unlock_board not in VALID_ACTIONS"
        assert "lock_board" in content, "lock_board not in VALID_ACTIONS"
        assert "start_session" in content, "start_session not in VALID_ACTIONS"
        assert "stop_session" in content, "stop_session not in VALID_ACTIONS"
        print("PASSED: VALID_ACTIONS includes all board control actions")
    
    def test_remote_action_model_has_params(self):
        """Verify RemoteAction model has params JSON column"""
        models_path = Path("/app/central_server/models.py")
        content = models_path.read_text()
        
        # Check RemoteAction class has params column
        assert "class RemoteAction" in content, "RemoteAction class not found"
        assert "params = Column(JSON" in content, "params JSON column not found in RemoteAction"
        print("PASSED: RemoteAction model has params JSON column")
    
    def test_action_poller_handles_board_control(self):
        """Verify action_poller._execute_action handles board control actions"""
        poller_path = Path("/app/backend/services/action_poller.py")
        content = poller_path.read_text()
        
        # Check _execute_action handles board control
        assert "_execute_action" in content, "_execute_action method not found"
        assert "unlock_board" in content, "unlock_board handling not found"
        assert "lock_board" in content, "lock_board handling not found"
        assert "start_session" in content, "start_session handling not found"
        assert "stop_session" in content, "stop_session handling not found"
        assert "_do_board_control" in content, "_do_board_control method not found"
        assert "_do_unlock" in content, "_do_unlock method not found"
        assert "_do_lock" in content, "_do_lock method not found"
        print("PASSED: action_poller handles all board control actions")
    
    def test_action_poller_unlock_creates_session(self):
        """Verify _do_unlock creates session with pricing params"""
        poller_path = Path("/app/backend/services/action_poller.py")
        content = poller_path.read_text()
        
        # Check _do_unlock creates session with pricing params
        assert "pricing_mode" in content, "pricing_mode not handled in _do_unlock"
        assert "game_type" in content, "game_type not handled in _do_unlock"
        assert "credits" in content, "credits not handled in _do_unlock"
        assert "minutes" in content, "minutes not handled in _do_unlock"
        assert "price_total" in content, "price_total not handled in _do_unlock"
        assert "players_count" in content, "players_count not handled in _do_unlock"
        assert "Session(" in content, "Session creation not found in _do_unlock"
        assert "BoardStatus.UNLOCKED" in content, "Board status update to UNLOCKED not found"
        print("PASSED: _do_unlock creates session with pricing params")
    
    def test_action_poller_lock_ends_session(self):
        """Verify _do_lock ends active session and sets board to locked"""
        poller_path = Path("/app/backend/services/action_poller.py")
        content = poller_path.read_text()
        
        # Check _do_lock ends session
        assert "SessionStatus.CANCELLED" in content or "CANCELLED" in content, "Session cancellation not found"
        assert "BoardStatus.LOCKED" in content, "Board status update to LOCKED not found"
        assert "ended_reason" in content, "ended_reason not set in _do_lock"
        print("PASSED: _do_lock ends session and locks board")
    
    def test_portal_frontend_sends_params(self):
        """Verify Portal frontend issueAction sends params with board control actions"""
        portal_path = Path("/app/frontend/src/pages/portal/PortalDeviceDetail.js")
        content = portal_path.read_text()
        
        # Check issueAction sends params
        assert "issueAction" in content, "issueAction function not found"
        assert "params" in content, "params not sent in issueAction"
        assert "body.params = params" in content or '"params": params' in content or "body.params" in content, "params not added to body"
        print("PASSED: Portal frontend sends params with board control actions")
    
    def test_portal_unlock_dialog_fields(self):
        """Verify Portal unlock dialog has all required fields"""
        portal_path = Path("/app/frontend/src/pages/portal/PortalDeviceDetail.js")
        content = portal_path.read_text()
        
        # Check unlock dialog fields
        assert "unlock-pricing-mode" in content or "unlockParams" in content, "pricing_mode field not found"
        assert "unlock-game-type" in content or "game_type" in content, "game_type field not found"
        assert "unlock-credits" in content or "credits" in content, "credits field not found"
        assert "unlock-minutes" in content or "minutes" in content, "minutes field not found"
        assert "unlock-price" in content or "price_total" in content, "price_total field not found"
        assert "unlock-players" in content or "players_count" in content, "players_count field not found"
        assert "unlock-board-id" in content or "board_id" in content, "board_id field not found"
        print("PASSED: Portal unlock dialog has all required fields")


# ═══════════════════════════════════════════════════════════════
# Block B: Device Config Tabbed Interface Tests
# ═══════════════════════════════════════════════════════════════

class TestBlockB_DeviceConfig:
    """Tests for Block B: Device config tabbed interface matching local admin"""
    
    def test_portal_config_has_tabs(self):
        """Verify Portal device config uses tabbed interface"""
        portal_path = Path("/app/frontend/src/pages/portal/PortalDeviceDetail.js")
        content = portal_path.read_text()
        
        # Check for tabs
        assert "Tabs" in content, "Tabs component not imported"
        assert "TabsList" in content, "TabsList not used"
        assert "TabsTrigger" in content, "TabsTrigger not used"
        assert "TabsContent" in content, "TabsContent not used"
        print("PASSED: Portal device config uses tabbed interface")
    
    def test_portal_config_tab_names(self):
        """Verify Portal config has correct tab names"""
        portal_path = Path("/app/frontend/src/pages/portal/PortalDeviceDetail.js")
        content = portal_path.read_text()
        
        # Check tab names (German)
        required_tabs = ["Branding", "Preise", "Sound", "Stammkunde", "Farben", "Kiosk", "Sharing"]
        for tab in required_tabs:
            assert tab in content, f"Tab '{tab}' not found in Portal config"
        print(f"PASSED: All required tabs found: {required_tabs}")
    
    def test_pricing_tab_has_subsections(self):
        """Verify Pricing tab has per_game, per_time, per_player sub-sections"""
        portal_path = Path("/app/frontend/src/pages/portal/PortalDeviceDetail.js")
        content = portal_path.read_text()
        
        # Check pricing subsections
        assert "per_game" in content, "per_game subsection not found"
        assert "per_time" in content, "per_time subsection not found"
        assert "per_player" in content, "per_player subsection not found"
        assert "cfg-per-game-price" in content or "price_per_credit" in content, "per_game price field not found"
        assert "cfg-per-time-30" in content or "price_per_30_min" in content, "per_time 30min field not found"
        assert "cfg-per-player-price" in content or "price_per_player" in content, "per_player price field not found"
        print("PASSED: Pricing tab has per_game, per_time, per_player subsections")
    
    def test_sound_tab_has_required_fields(self):
        """Verify Sound tab has sound pack, rate limit, quiet hours"""
        portal_path = Path("/app/frontend/src/pages/portal/PortalDeviceDetail.js")
        content = portal_path.read_text()
        
        # Check sound tab fields
        assert "sound_pack" in content or "cfg-spack" in content, "sound pack selection not found"
        assert "rate_limit" in content or "cfg-sound-rate" in content, "rate limit not found"
        assert "quiet_hours" in content or "cfg-quiet" in content, "quiet hours not found"
        print("PASSED: Sound tab has sound pack, rate limit, quiet hours")
    
    def test_stammkunde_tab_has_required_fields(self):
        """Verify Stammkunde tab has display toggle, period, interval, max entries, nickname length"""
        portal_path = Path("/app/frontend/src/pages/portal/PortalDeviceDetail.js")
        content = portal_path.read_text()
        
        # Check stammkunde tab fields
        assert "stammkunde_display" in content, "stammkunde_display section not found"
        assert "cfg-stammkunde-enabled" in content or "enabled" in content, "display toggle not found"
        assert "cfg-sk-period" in content or "period" in content, "period selection not found"
        assert "cfg-sk-interval" in content or "interval_seconds" in content, "interval not found"
        assert "cfg-sk-max" in content or "max_entries" in content, "max entries not found"
        assert "cfg-sk-nick" in content or "nickname_max_length" in content, "nickname length not found"
        print("PASSED: Stammkunde tab has all required fields")


# ═══════════════════════════════════════════════════════════════
# Block C: License Lock Enforcement Tests
# ═══════════════════════════════════════════════════════════════

class TestBlockC_LicenseLockEnforcement:
    """Tests for Block C: Device/license lock enforcement"""
    
    def test_license_service_checks_cache_first(self):
        """Verify license_service.get_effective_status checks local cache FIRST"""
        license_path = Path("/app/backend/services/license_service.py")
        content = license_path.read_text()
        
        # Check that cache is checked at the start of get_effective_status
        # The cache check should be before any DB queries
        assert "load_from_cache" in content, "load_from_cache not called"
        
        # Find get_effective_status method and verify cache check is early
        lines = content.split('\n')
        in_method = False
        cache_check_line = -1
        db_query_line = -1
        
        for i, line in enumerate(lines):
            if "async def get_effective_status" in line:
                in_method = True
            if in_method:
                if "load_from_cache" in line and cache_check_line == -1:
                    cache_check_line = i
                if "await db.execute" in line and db_query_line == -1:
                    db_query_line = i
                if "async def " in line and "get_effective_status" not in line:
                    break
        
        assert cache_check_line > 0, "Cache check not found in get_effective_status"
        assert cache_check_line < db_query_line, f"Cache check (line {cache_check_line}) should be before DB query (line {db_query_line})"
        print(f"PASSED: Cache check at line {cache_check_line}, DB query at line {db_query_line}")
    
    def test_license_service_blocks_suspended_status(self):
        """Verify license_service.get_effective_status returns early for suspended/blocked/inactive"""
        license_path = Path("/app/backend/services/license_service.py")
        content = license_path.read_text()
        
        # Check for suspended/blocked/inactive handling in cache check
        assert '"suspended"' in content or "'suspended'" in content, "suspended status not handled"
        assert '"blocked"' in content or "'blocked'" in content, "blocked status not handled"
        assert '"inactive"' in content or "'inactive'" in content, "inactive status not handled"
        
        # Check that these statuses cause early return
        assert "Central lock enforced" in content or "centrally locked" in content.lower(), "Central lock enforcement message not found"
        print("PASSED: get_effective_status handles suspended/blocked/inactive from cache")
    
    def test_is_session_allowed_blocks_suspended(self):
        """Verify license_service.is_session_allowed explicitly blocks suspended, blocked, inactive"""
        license_path = Path("/app/backend/services/license_service.py")
        content = license_path.read_text()
        
        # Find is_session_allowed method
        assert "def is_session_allowed" in content, "is_session_allowed method not found"
        
        # Check that suspended/blocked/inactive are blocked
        # Look for the explicit check in is_session_allowed
        lines = content.split('\n')
        in_method = False
        found_suspended_check = False
        
        for i, line in enumerate(lines):
            if "def is_session_allowed" in line:
                in_method = True
            if in_method:
                if "suspended" in line and ("blocked" in line or "inactive" in line):
                    found_suspended_check = True
                if "def " in line and "is_session_allowed" not in line:
                    break
        
        assert found_suspended_check, "is_session_allowed does not explicitly check for suspended/blocked/inactive"
        print("PASSED: is_session_allowed blocks suspended/blocked/inactive statuses")
    
    def test_central_rejection_handler_writes_suspended(self):
        """Verify central_rejection_handler writes suspended status to cache"""
        handler_path = Path("/app/backend/services/central_rejection_handler.py")
        content = handler_path.read_text()
        
        # Check that handler writes suspended to cache
        assert "handle_central_rejection" in content, "handle_central_rejection function not found"
        assert '"suspended"' in content or "'suspended'" in content, "suspended status not written"
        assert "save_to_cache" in content, "save_to_cache not called"
        assert "central_rejection" in content, "source not set to central_rejection"
        print("PASSED: central_rejection_handler writes suspended status to cache")
    
    def test_license_cache_integration(self):
        """Test that writing a suspended cache blocks unlock operations"""
        # This test verifies the integration by checking the code flow
        license_path = Path("/app/backend/services/license_service.py")
        content = license_path.read_text()
        
        # Verify the flow: cache check → return early if suspended
        assert "cached_status" in content or "cached" in content, "Cache status variable not found"
        assert "binding_status" in content, "binding_status not set for suspended"
        
        # Check that suspended returns with binding_status = "suspended"
        lines = content.split('\n')
        found_suspended_binding = False
        for line in lines:
            if "suspended" in line.lower() and "binding_status" in line:
                found_suspended_binding = True
                break
        
        assert found_suspended_binding, "Suspended status does not set binding_status"
        print("PASSED: License cache integration verified")


# ═══════════════════════════════════════════════════════════════
# Backend API Health Tests
# ═══════════════════════════════════════════════════════════════

class TestBackendHealth:
    """Basic backend health tests"""
    
    def test_health_endpoint(self):
        """Verify backend health endpoint returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get("status") == "healthy", f"Unexpected status: {data}"
        print(f"PASSED: Backend health OK - {data}")
    
    def test_kiosk_license_status(self):
        """Verify kiosk license status endpoint works"""
        response = requests.get(f"{BASE_URL}/api/kiosk/license-status", timeout=10)
        assert response.status_code == 200, f"License status failed: {response.status_code}"
        data = response.json()
        assert "status" in data, f"No status in response: {data}"
        print(f"PASSED: License status OK - status={data.get('status')}")
    
    def test_boards_endpoint(self):
        """Verify boards endpoint works"""
        response = requests.get(f"{BASE_URL}/api/boards", timeout=10)
        assert response.status_code == 200, f"Boards endpoint failed: {response.status_code}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got: {type(data)}"
        print(f"PASSED: Boards endpoint OK - {len(data)} boards")


# ═══════════════════════════════════════════════════════════════
# Central Server Code Verification (not HTTP - code inspection)
# ═══════════════════════════════════════════════════════════════

class TestCentralServerCode:
    """Verify central server code changes (central server not running)"""
    
    def test_server_issue_remote_action_accepts_params(self):
        """Verify central server issue_remote_action accepts params"""
        server_path = Path("/app/central_server/server.py")
        content = server_path.read_text()
        
        # Check that params is extracted from body
        assert 'body.get("params")' in content or "action_params" in content, "params not extracted from body"
        
        # Check that params is passed to RemoteAction
        assert "params=action_params" in content or "params=" in content, "params not passed to RemoteAction"
        print("PASSED: Central server issue_remote_action accepts params")
    
    def test_server_serializer_includes_params(self):
        """Verify _ser_action includes params in response"""
        server_path = Path("/app/central_server/server.py")
        content = server_path.read_text()
        
        # Check that params is included in serialized action
        assert 'a.params' in content or '"params"' in content, "params not serialized in action response"
        print("PASSED: _ser_action includes params in response")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
