"""
Test v3.3.3 Windows Kiosk Controls (Shell Switch, Task Manager Toggle, Settings)
- Running on Linux preview environment, so all Windows registry operations should return supported=false
- Tests graceful degradation behavior and settings persistence
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


class TestKioskControlsAuth:
    """Test that kiosk endpoints require admin authentication"""
    
    def test_kiosk_status_requires_auth(self):
        """GET /api/admin/kiosk/status should return 401 without token"""
        resp = requests.get(f"{BASE_URL}/api/admin/kiosk/status")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Kiosk status requires auth (401)")
    
    def test_shell_explorer_requires_auth(self):
        """POST /api/admin/kiosk/shell/explorer should return 401 without token"""
        resp = requests.post(f"{BASE_URL}/api/admin/kiosk/shell/explorer")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Shell explorer endpoint requires auth (401)")
    
    def test_shell_kiosk_requires_auth(self):
        """POST /api/admin/kiosk/shell/kiosk should return 401 without token"""
        resp = requests.post(f"{BASE_URL}/api/admin/kiosk/shell/kiosk")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Shell kiosk endpoint requires auth (401)")
    
    def test_taskmanager_enable_requires_auth(self):
        """POST /api/admin/kiosk/taskmanager/enable should return 401 without token"""
        resp = requests.post(f"{BASE_URL}/api/admin/kiosk/taskmanager/enable")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Task manager enable requires auth (401)")
    
    def test_taskmanager_disable_requires_auth(self):
        """POST /api/admin/kiosk/taskmanager/disable should return 401 without token"""
        resp = requests.post(f"{BASE_URL}/api/admin/kiosk/taskmanager/disable")
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Task manager disable requires auth (401)")
    
    def test_kiosk_settings_requires_auth(self):
        """POST /api/admin/kiosk/settings should return 401 without token"""
        resp = requests.post(f"{BASE_URL}/api/admin/kiosk/settings", json={"kiosk_shell_path": "test"})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        print("PASS: Kiosk settings requires auth (401)")


class TestKioskControlsGracefulDegradation:
    """Test kiosk controls graceful degradation on non-Windows (Linux preview)"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert resp.status_code == 200, f"Login failed: {resp.status_code} - {resp.text}"
        self.token = resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_kiosk_status_non_windows(self):
        """GET /api/admin/kiosk/status returns full status with is_windows=false"""
        resp = requests.get(f"{BASE_URL}/api/admin/kiosk/status", headers=self.headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        # Check top-level fields
        assert "is_windows" in data, "Missing is_windows field"
        assert "kiosk_controls_available" in data, "Missing kiosk_controls_available field"
        assert "shell" in data, "Missing shell section"
        assert "task_manager" in data, "Missing task_manager section"
        
        # On Linux, these should be False
        assert data["is_windows"] == False, f"Expected is_windows=false, got {data['is_windows']}"
        assert data["kiosk_controls_available"] == False, f"Expected kiosk_controls_available=false"
        
        # Shell section verification
        shell = data["shell"]
        assert shell.get("supported") == False, "Shell should not be supported on non-Windows"
        assert shell.get("is_windows") == False
        assert "kiosk_shell_configured" in shell
        
        # Task manager section verification
        taskmgr = data["task_manager"]
        assert taskmgr.get("supported") == False, "Task manager should not be supported on non-Windows"
        assert taskmgr.get("is_windows") == False
        
        print(f"PASS: Kiosk status returns correct non-Windows structure")
        print(f"  - is_windows: {data['is_windows']}")
        print(f"  - kiosk_controls_available: {data['kiosk_controls_available']}")
        print(f"  - shell.supported: {shell.get('supported')}")
        print(f"  - task_manager.supported: {taskmgr.get('supported')}")
    
    def test_shell_switch_to_explorer_graceful_degradation(self):
        """POST /api/admin/kiosk/shell/explorer returns supported=false on non-Windows"""
        resp = requests.post(f"{BASE_URL}/api/admin/kiosk/shell/explorer", headers=self.headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("supported") == False, "Should return supported=false on non-Windows"
        assert data.get("reason") == "windows_only", f"Expected reason=windows_only, got {data.get('reason')}"
        
        print("PASS: Shell switch to explorer gracefully degrades on non-Windows")
        print(f"  - supported: {data.get('supported')}")
        print(f"  - reason: {data.get('reason')}")
        print(f"  - message: {data.get('message')}")
    
    def test_shell_switch_to_kiosk_graceful_degradation(self):
        """POST /api/admin/kiosk/shell/kiosk returns supported=false on non-Windows"""
        resp = requests.post(f"{BASE_URL}/api/admin/kiosk/shell/kiosk", headers=self.headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("supported") == False, "Should return supported=false on non-Windows"
        assert data.get("reason") == "windows_only", f"Expected reason=windows_only, got {data.get('reason')}"
        
        print("PASS: Shell switch to kiosk gracefully degrades on non-Windows")
        print(f"  - supported: {data.get('supported')}")
        print(f"  - reason: {data.get('reason')}")
    
    def test_taskmanager_enable_graceful_degradation(self):
        """POST /api/admin/kiosk/taskmanager/enable returns supported=false on non-Windows"""
        resp = requests.post(f"{BASE_URL}/api/admin/kiosk/taskmanager/enable", headers=self.headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("supported") == False, "Should return supported=false on non-Windows"
        assert data.get("reason") == "windows_only", f"Expected reason=windows_only, got {data.get('reason')}"
        
        print("PASS: Task manager enable gracefully degrades on non-Windows")
        print(f"  - supported: {data.get('supported')}")
        print(f"  - reason: {data.get('reason')}")
    
    def test_taskmanager_disable_graceful_degradation(self):
        """POST /api/admin/kiosk/taskmanager/disable returns supported=false on non-Windows"""
        resp = requests.post(f"{BASE_URL}/api/admin/kiosk/taskmanager/disable", headers=self.headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("supported") == False, "Should return supported=false on non-Windows"
        assert data.get("reason") == "windows_only", f"Expected reason=windows_only, got {data.get('reason')}"
        
        print("PASS: Task manager disable gracefully degrades on non-Windows")
        print(f"  - supported: {data.get('supported')}")
        print(f"  - reason: {data.get('reason')}")


class TestKioskSettings:
    """Test kiosk settings persistence"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert resp.status_code == 200, f"Login failed: {resp.status_code}"
        self.token = resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_save_kiosk_shell_path(self):
        """POST /api/admin/kiosk/settings saves kiosk_shell_path"""
        test_path = r"C:\test\kiosk.bat"
        
        resp = requests.post(
            f"{BASE_URL}/api/admin/kiosk/settings",
            headers=self.headers,
            json={"kiosk_shell_path": test_path}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        
        data = resp.json()
        assert data.get("success") == True, "Expected success=true"
        assert data.get("settings", {}).get("kiosk_shell_path") == test_path
        
        print(f"PASS: Kiosk shell path saved successfully")
        print(f"  - path: {test_path}")
    
    def test_verify_saved_kiosk_shell_path(self):
        """GET /api/admin/kiosk/status shows saved kiosk_shell_configured"""
        test_path = r"C:\test\verify_kiosk.bat"
        
        # First save
        save_resp = requests.post(
            f"{BASE_URL}/api/admin/kiosk/settings",
            headers=self.headers,
            json={"kiosk_shell_path": test_path}
        )
        assert save_resp.status_code == 200
        
        # Then verify in status
        status_resp = requests.get(f"{BASE_URL}/api/admin/kiosk/status", headers=self.headers)
        assert status_resp.status_code == 200
        
        data = status_resp.json()
        shell_config = data.get("shell", {}).get("kiosk_shell_configured", "")
        assert shell_config == test_path, f"Expected '{test_path}', got '{shell_config}'"
        
        print(f"PASS: Kiosk shell path persisted and visible in status")
        print(f"  - kiosk_shell_configured: {shell_config}")
    
    def test_save_empty_kiosk_shell_path(self):
        """POST /api/admin/kiosk/settings with empty path resets configuration"""
        # First set a path
        requests.post(
            f"{BASE_URL}/api/admin/kiosk/settings",
            headers=self.headers,
            json={"kiosk_shell_path": r"C:\some\path.bat"}
        )
        
        # Then clear it
        resp = requests.post(
            f"{BASE_URL}/api/admin/kiosk/settings",
            headers=self.headers,
            json={"kiosk_shell_path": ""}
        )
        assert resp.status_code == 200
        
        data = resp.json()
        assert data.get("settings", {}).get("kiosk_shell_path") == ""
        
        print("PASS: Empty kiosk shell path accepted (reset)")


class TestRegressionUnlockSimulateFlow:
    """Regression test: POST /api/boards/BOARD-1/unlock + simulate-game-end still works"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert resp.status_code == 200, f"Login failed: {resp.status_code}"
        self.token = resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_unlock_and_simulate_game_flow(self):
        """Regression: Full unlock → start-game → simulate-game-end flow for 501"""
        # 0. First lock the board to clean state
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        
        # 1. Unlock BOARD-1 with per_game/1 credit
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={"pricing_mode": "per_game", "credits": 1}
        )
        assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.status_code} - {unlock_resp.text}"
        print("  Step 1: BOARD-1 unlocked with per_game/1 credit")
        
        # 2. Start game with 501 (via kiosk endpoint, no auth required)
        start_resp = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/start-game",
            json={"game_type": "501", "players": ["TestPlayer"]}
        )
        assert start_resp.status_code == 200, f"Start game failed: {start_resp.status_code} - {start_resp.text}"
        print("  Step 2: Game started (501)")
        
        # 3. Simulate game start (admin endpoint)
        sim_start_resp = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=self.headers
        )
        assert sim_start_resp.status_code == 200, f"Simulate start failed: {sim_start_resp.status_code}"
        print("  Step 3: Game start simulated")
        
        # 4. Simulate game end (admin endpoint)
        sim_end_resp = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=self.headers
        )
        assert sim_end_resp.status_code == 200, f"Simulate end failed: {sim_end_resp.status_code}"
        
        end_data = sim_end_resp.json()
        should_lock = end_data.get("should_lock", False)
        credits_remaining = end_data.get("credits_remaining", -1)
        
        assert should_lock == True, f"Expected should_lock=True, got {should_lock}"
        assert credits_remaining == 0, f"Expected credits=0, got {credits_remaining}"
        
        print("  Step 4: Game end simulated - LOCKED correctly")
        print(f"    - should_lock: {should_lock}")
        print(f"    - credits_remaining: {credits_remaining}")
        print("PASS: Regression - unlock + simulate-game-end flow works")


class TestRegressionGotchaVariantGuard:
    """Regression test: Gotcha variant guard still blocks game_shot triggers"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        assert resp.status_code == 200, f"Login failed: {resp.status_code}"
        self.token = resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_gotcha_game_shot_trigger_blocked(self):
        """Gotcha with game_shot trigger should NOT lock (credits preserved)"""
        # 0. First lock the board to clean state
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)
        
        # 1. Unlock with 1 credit
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            headers=self.headers,
            json={"pricing_mode": "per_game", "credits": 1}
        )
        assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.status_code} - {unlock_resp.text}"
        
        # 2. Start Gotcha game (via kiosk endpoint)
        start_resp = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/start-game",
            json={"game_type": "Gotcha", "players": ["TestPlayer"]}
        )
        assert start_resp.status_code == 200, f"Start game failed: {start_resp.status_code}"
        
        # 3. Simulate game start
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", headers=self.headers)
        
        # 4. Simulate game end with game_shot trigger (should be BLOCKED)
        sim_end_resp = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end?trigger=match_end_gameshot_match",
            headers=self.headers
        )
        assert sim_end_resp.status_code == 200, f"Simulate end failed: {sim_end_resp.status_code}"
        
        end_data = sim_end_resp.json()
        should_lock = end_data.get("should_lock", True)
        credits_remaining = end_data.get("credits_remaining", 0)
        
        # For Gotcha with game_shot trigger, should NOT lock and credits preserved
        assert should_lock == False, f"Expected should_lock=False for Gotcha+gameshot, got {should_lock}"
        assert credits_remaining == 1, f"Expected credits=1 (preserved), got {credits_remaining}"
        
        print("PASS: Regression - Gotcha variant guard blocks game_shot trigger")
        print(f"  - should_lock: {should_lock}")
        print(f"  - credits_remaining: {credits_remaining}")
        
        # Cleanup: Lock the board
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers)


# Run main if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
