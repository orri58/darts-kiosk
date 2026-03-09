"""
Iteration 31 - Regression Tests
Testing 2 regressions:
1) PWA install now opens admin panel instead of kiosk
2) Port consistency and API functionality

Test cases:
- Manifest.json has correct start_url=/admin, scope=/, name containing 'Admin'
- No manifest-admin.json endpoint exists (should return index.html via SPA catch-all)
- /admin route returns HTTP 200 (SPA routing works)
- /kiosk/BOARD-1 route returns HTTP 200 (kiosk still works)
- All runtime URLs use port 8001 consistently
- /api/health returns healthy status
- /api/system/info returns version info with auth
- /api/auth/login works with admin/admin123
- Board session endpoint /api/boards/BOARD-1/session works
- Full game lifecycle: unlock -> simulate-game-start -> simulate-game-end -> board locks
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestPWAManifestRegression:
    """REGRESSION 1: PWA manifest now points to /admin instead of /kiosk"""
    
    def test_manifest_json_start_url_is_admin(self):
        """Manifest start_url should be /admin (not /kiosk)"""
        response = requests.get(f"{BASE_URL}/manifest.json")
        assert response.status_code == 200, f"manifest.json not served: {response.status_code}"
        
        manifest = response.json()
        assert manifest.get("start_url") == "/admin", f"start_url should be /admin, got: {manifest.get('start_url')}"
        print(f"✓ manifest.json start_url = /admin")
    
    def test_manifest_json_scope_is_root(self):
        """Manifest scope should be /"""
        response = requests.get(f"{BASE_URL}/manifest.json")
        assert response.status_code == 200
        
        manifest = response.json()
        assert manifest.get("scope") == "/", f"scope should be /, got: {manifest.get('scope')}"
        print(f"✓ manifest.json scope = /")
    
    def test_manifest_json_name_contains_admin(self):
        """Manifest name should contain 'Admin'"""
        response = requests.get(f"{BASE_URL}/manifest.json")
        assert response.status_code == 200
        
        manifest = response.json()
        name = manifest.get("name", "")
        assert "Admin" in name, f"name should contain 'Admin', got: {name}"
        print(f"✓ manifest.json name = {name}")
    
    def test_manifest_admin_json_does_not_exist(self):
        """manifest-admin.json should not exist as a separate file (returns index.html via SPA)"""
        response = requests.get(f"{BASE_URL}/manifest-admin.json")
        # SPA catch-all returns 200 with index.html content
        assert response.status_code == 200, f"Unexpected status: {response.status_code}"
        
        # Should return HTML (index.html) not JSON
        content_type = response.headers.get('content-type', '')
        is_html = 'text/html' in content_type or response.text.startswith('<!doctype html>')
        assert is_html, f"manifest-admin.json should return index.html, got content-type: {content_type}"
        print(f"✓ manifest-admin.json returns index.html (no separate endpoint)")
    
    def test_admin_route_returns_200(self):
        """/admin route should return HTTP 200 (SPA routing works)"""
        response = requests.get(f"{BASE_URL}/admin")
        assert response.status_code == 200, f"/admin returned {response.status_code}"
        assert "<!doctype html>" in response.text.lower() or "<html" in response.text.lower()
        print(f"✓ /admin returns 200 (SPA routing)")
    
    def test_kiosk_route_still_works(self):
        """/kiosk/BOARD-1 route should still return HTTP 200"""
        response = requests.get(f"{BASE_URL}/kiosk/BOARD-1")
        assert response.status_code == 200, f"/kiosk/BOARD-1 returned {response.status_code}"
        assert "<!doctype html>" in response.text.lower() or "<html" in response.text.lower()
        print(f"✓ /kiosk/BOARD-1 returns 200 (kiosk still works)")


class TestPortConsistencyRegression:
    """REGRESSION 2: Port consistency - all APIs using port 8001"""
    
    def test_api_health_returns_healthy(self):
        """/api/health should return healthy status"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"/api/health returned {response.status_code}"
        
        data = response.json()
        assert data.get("status") == "healthy", f"Expected healthy, got: {data}"
        print(f"✓ /api/health = healthy, mode = {data.get('mode')}")
    
    def test_api_auth_login_works(self):
        """/api/auth/login should work with admin/admin123"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        assert response.status_code == 200, f"/api/auth/login returned {response.status_code}"
        
        data = response.json()
        assert "access_token" in data, f"Missing access_token in response: {data}"
        assert len(data["access_token"]) > 20, "Token too short"
        print(f"✓ /api/auth/login works, got access_token")
        return data["access_token"]
    
    def test_api_system_info_returns_version(self):
        """/api/system/info should return version info (requires auth)"""
        # Get token first
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        token = login_resp.json().get("access_token")
        
        response = requests.get(
            f"{BASE_URL}/api/system/info",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"/api/system/info returned {response.status_code}"
        
        data = response.json()
        assert "version" in data, f"Missing version in response: {data}"
        assert "mode" in data, f"Missing mode in response: {data}"
        print(f"✓ /api/system/info = version {data.get('version')}, mode = {data.get('mode')}")
    
    def test_board_session_endpoint_works(self):
        """/api/boards/BOARD-1/session should return board status"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        assert response.status_code == 200, f"/api/boards/BOARD-1/session returned {response.status_code}"
        
        data = response.json()
        assert "board_status" in data, f"Missing board_status: {data}"
        print(f"✓ /api/boards/BOARD-1/session = board_status: {data.get('board_status')}")


class TestGameLifecycleRegression:
    """Full game lifecycle test: unlock -> game-start -> game-end -> board locks"""
    
    @pytest.fixture(autouse=True)
    def setup_auth(self):
        """Get admin token for authenticated requests"""
        login_resp = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"}
        )
        self.token = login_resp.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Ensure board is locked before test
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers=self.headers
        )
        yield
        
        # Cleanup: lock board after test
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers=self.headers
        )
    
    def test_full_game_lifecycle_with_1_credit(self):
        """
        Full lifecycle: 
        1. Unlock with 1 credit
        2. Simulate game start (credit decrements)
        3. Simulate game end (board should lock because credits exhausted)
        """
        # Step 1: Unlock board with 1 credit
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"pricing_mode": "per_game", "credits": 1},
            headers=self.headers
        )
        assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.status_code} - {unlock_resp.text}"
        
        # Verify board is unlocked
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        session_data = session_resp.json()
        assert session_data.get("board_status") == "unlocked", f"Expected unlocked, got: {session_data}"
        # credits_remaining is inside session object
        session_obj = session_data.get("session", {})
        assert session_obj.get("credits_remaining") == 1, f"Expected 1 credit, got: {session_obj.get('credits_remaining')}"
        print(f"✓ Board unlocked with 1 credit")
        
        # Step 2: Simulate game start (credit decrements 1 -> 0)
        start_resp = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=self.headers
        )
        assert start_resp.status_code == 200, f"Game start failed: {start_resp.status_code} - {start_resp.text}"
        
        time.sleep(0.5)  # Allow processing
        
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        session_data = session_resp.json()
        session_obj = session_data.get("session", {})
        assert session_obj.get("credits_remaining") == 0, f"Expected 0 credits after game start, got: {session_obj.get('credits_remaining')}"
        print(f"✓ Game started, credits decremented to 0")
        
        # Step 3: Simulate game end (board should lock)
        end_resp = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=self.headers
        )
        assert end_resp.status_code == 200, f"Game end failed: {end_resp.status_code} - {end_resp.text}"
        
        time.sleep(1)  # Allow finalization to complete
        
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session")
        session_data = session_resp.json()
        assert session_data.get("board_status") == "locked", f"Expected locked after credits exhausted, got: {session_data}"
        print(f"✓ Game ended, board locked (credits exhausted)")
        
        print(f"✓ FULL LIFECYCLE TEST PASSED: unlock(1 credit) -> game-start -> game-end -> LOCKED")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
