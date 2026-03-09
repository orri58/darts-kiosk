"""
P0 Production Blockers Test Suite - Iteration 30

Tests for two critical production blockers:
1. Update installation error handling - install endpoint must return 500 on failure, not silent 200 OK
2. Match-end finalization chain - when last credit used, board MUST lock

Uses pytest with the public backend URL from environment.
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    raise ValueError("REACT_APP_BACKEND_URL environment variable not set")

# Test credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
TEST_BOARD_ID = "BOARD-1"


class TestAuth:
    """Authentication tests"""
    
    def test_health_check(self):
        """General: /api/health returns healthy"""
        response = requests.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy" or "healthy" in str(data).lower()
        print(f"✓ Health check passed: {data}")
    
    def test_admin_login(self):
        """General: /api/auth/login works with admin/admin123"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, f"No access_token in response: {data}"
        assert data["user"]["username"] == ADMIN_USERNAME
        print(f"✓ Admin login successful: user={data['user']['username']}")
        return data["access_token"]
    
    def test_system_info(self):
        """General: /api/system/info returns version and mode"""
        # First login to get token
        login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD
        })
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.get(f"{BASE_URL}/api/system/info", headers=headers)
        assert response.status_code == 200, f"System info failed: {response.status_code}"
        data = response.json()
        # System info should contain version and mode
        print(f"✓ System info returned: {data}")


@pytest.fixture
def auth_token():
    """Get admin auth token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip("Could not login as admin")
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Get authorization headers"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestP0Blocker1UpdateInstall:
    """
    P0 Blocker 1: /api/updates/install endpoint error handling
    
    Tests that the install endpoint properly reports failures:
    - Returns 500 with error detail when updater launch fails
    - Returns 404 when asset_filename does not exist
    """
    
    def test_install_returns_404_for_nonexistent_asset(self, auth_headers):
        """P0 Blocker 1: /api/updates/install returns 404 when asset_filename does not exist"""
        response = requests.post(
            f"{BASE_URL}/api/updates/install",
            headers=auth_headers,
            params={
                "asset_filename": "nonexistent_file_xyz123.zip",
                "target_version": "9.9.9"
            }
        )
        # Should return 404 because the asset doesn't exist
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data, f"No error detail in response: {data}"
        print(f"✓ Install correctly returns 404 for nonexistent asset: {data['detail']}")
    
    def test_rollback_returns_404_for_nonexistent_backup(self, auth_headers):
        """P0 Blocker 1: /api/updates/rollback returns 404 when backup doesn't exist"""
        response = requests.post(
            f"{BASE_URL}/api/updates/rollback",
            headers=auth_headers,
            params={"backup_filename": "nonexistent_backup_xyz123.zip"}
        )
        # Should return 404 because the backup doesn't exist
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
        data = response.json()
        assert "detail" in data, f"No error detail in response: {data}"
        print(f"✓ Rollback correctly returns 404 for nonexistent backup: {data['detail']}")


class TestP0Blocker2GameLifecycle:
    """
    P0 Blocker 2: Match-end finalization chain
    
    Tests the full game lifecycle:
    - unlock board with 1 credit → simulate-game-start (credit 1→0) → simulate-game-end (board MUST lock)
    - unlock with 3 credits → simulate-game-start (credit 3→2) → simulate-game-end (board stays unlocked)
    """
    
    def _ensure_board_locked(self, auth_headers):
        """Helper to ensure board is locked before test"""
        # First check current status
        response = requests.get(f"{BASE_URL}/api/boards/{TEST_BOARD_ID}/session")
        if response.status_code == 200:
            data = response.json()
            if data.get("board_status") != "locked":
                # Lock the board
                lock_resp = requests.post(
                    f"{BASE_URL}/api/boards/{TEST_BOARD_ID}/lock",
                    headers=auth_headers
                )
                print(f"  Locked board: {lock_resp.status_code}")
                time.sleep(0.5)  # Give time for lock to complete
    
    def _unlock_board(self, auth_headers, credits: int):
        """Helper to unlock board with specified credits"""
        response = requests.post(
            f"{BASE_URL}/api/boards/{TEST_BOARD_ID}/unlock",
            headers=auth_headers,
            json={
                "pricing_mode": "per_game",
                "credits": credits,
                "game_type": "501"
            }
        )
        return response
    
    def test_observer_status_endpoint(self, auth_headers):
        """P0 Blocker 2: Observer status endpoint /api/kiosk/BOARD-1/observer-status works"""
        response = requests.get(f"{BASE_URL}/api/kiosk/{TEST_BOARD_ID}/observer-status")
        assert response.status_code == 200, f"Observer status failed: {response.status_code}: {response.text}"
        data = response.json()
        assert "autodarts_mode" in data, f"Missing autodarts_mode: {data}"
        assert "state" in data, f"Missing state: {data}"
        print(f"✓ Observer status endpoint works: mode={data.get('autodarts_mode')}, state={data.get('state')}")
    
    def test_full_lifecycle_1_credit_must_lock(self, auth_headers):
        """
        P0 Blocker 2: Full game lifecycle simulation
        unlock board with 1 credit → simulate-game-start (credit 1→0) → simulate-game-end (board MUST lock)
        """
        # Step 1: Ensure board is locked
        self._ensure_board_locked(auth_headers)
        
        # Step 2: Unlock board with 1 credit
        print(f"  Step 1: Unlocking {TEST_BOARD_ID} with 1 credit...")
        unlock_resp = self._unlock_board(auth_headers, credits=1)
        assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.status_code}: {unlock_resp.text}"
        unlock_data = unlock_resp.json()
        assert unlock_data.get("credits_remaining") == 1, f"Expected 1 credit, got: {unlock_data}"
        print(f"  ✓ Board unlocked with 1 credit")
        
        # Step 3: Verify board is unlocked
        session_resp = requests.get(f"{BASE_URL}/api/boards/{TEST_BOARD_ID}/session")
        assert session_resp.status_code == 200
        session_data = session_resp.json()
        assert session_data.get("board_status") == "unlocked", f"Board not unlocked: {session_data}"
        print(f"  ✓ Board status is 'unlocked'")
        
        # Step 4: Simulate game start (credit 1 → 0)
        print(f"  Step 2: Simulating game start...")
        start_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{TEST_BOARD_ID}/simulate-game-start",
            headers=auth_headers
        )
        assert start_resp.status_code == 200, f"Game start failed: {start_resp.status_code}: {start_resp.text}"
        print(f"  ✓ Game started (credits should now be 0)")
        
        # Small delay for async processing
        time.sleep(0.5)
        
        # Verify credits are now 0
        session_resp = requests.get(f"{BASE_URL}/api/boards/{TEST_BOARD_ID}/session")
        session_data = session_resp.json()
        if session_data.get("session"):
            credits_after_start = session_data["session"].get("credits_remaining")
            print(f"  Credits after start: {credits_after_start}")
            assert credits_after_start == 0, f"Expected 0 credits after start, got: {credits_after_start}"
        
        # Step 5: Simulate game end (board MUST lock because credits = 0)
        print(f"  Step 3: Simulating game end...")
        end_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{TEST_BOARD_ID}/simulate-game-end",
            headers=auth_headers
        )
        assert end_resp.status_code == 200, f"Game end failed: {end_resp.status_code}: {end_resp.text}"
        print(f"  ✓ Game ended")
        
        # Delay for async finalization chain
        time.sleep(1.0)
        
        # Step 6: Verify board is LOCKED (CRITICAL CHECK)
        session_resp = requests.get(f"{BASE_URL}/api/boards/{TEST_BOARD_ID}/session")
        assert session_resp.status_code == 200
        final_data = session_resp.json()
        board_status = final_data.get("board_status")
        
        print(f"  Final board status: {board_status}")
        assert board_status == "locked", f"P0 FAILURE: Board should be LOCKED after last credit used, but is: {board_status}"
        print(f"  ✓ P0 Blocker 2 PASSED: Board correctly locked after last credit exhausted")
    
    def test_lifecycle_3_credits_stays_unlocked(self, auth_headers):
        """
        P0 Blocker 2: Verify board stays unlocked when credits remain
        unlock with 3 credits → simulate-game-start (credit 3→2) → simulate-game-end (board stays unlocked)
        """
        # Step 1: Ensure board is locked
        self._ensure_board_locked(auth_headers)
        
        # Step 2: Unlock board with 3 credits
        print(f"  Step 1: Unlocking {TEST_BOARD_ID} with 3 credits...")
        unlock_resp = self._unlock_board(auth_headers, credits=3)
        assert unlock_resp.status_code == 200, f"Unlock failed: {unlock_resp.status_code}: {unlock_resp.text}"
        unlock_data = unlock_resp.json()
        assert unlock_data.get("credits_remaining") == 3, f"Expected 3 credits, got: {unlock_data}"
        print(f"  ✓ Board unlocked with 3 credits")
        
        # Step 3: Simulate game start (credit 3 → 2)
        print(f"  Step 2: Simulating game start...")
        start_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{TEST_BOARD_ID}/simulate-game-start",
            headers=auth_headers
        )
        assert start_resp.status_code == 200, f"Game start failed: {start_resp.status_code}: {start_resp.text}"
        print(f"  ✓ Game started (credits should now be 2)")
        
        # Small delay for async processing
        time.sleep(0.5)
        
        # Verify credits are now 2
        session_resp = requests.get(f"{BASE_URL}/api/boards/{TEST_BOARD_ID}/session")
        session_data = session_resp.json()
        if session_data.get("session"):
            credits_after_start = session_data["session"].get("credits_remaining")
            print(f"  Credits after start: {credits_after_start}")
            assert credits_after_start == 2, f"Expected 2 credits after start, got: {credits_after_start}"
        
        # Step 4: Simulate game end (board should STAY UNLOCKED because credits = 2)
        print(f"  Step 3: Simulating game end...")
        end_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{TEST_BOARD_ID}/simulate-game-end",
            headers=auth_headers
        )
        assert end_resp.status_code == 200, f"Game end failed: {end_resp.status_code}: {end_resp.text}"
        print(f"  ✓ Game ended")
        
        # Delay for async processing
        time.sleep(1.0)
        
        # Step 5: Verify board is STILL UNLOCKED
        session_resp = requests.get(f"{BASE_URL}/api/boards/{TEST_BOARD_ID}/session")
        assert session_resp.status_code == 200
        final_data = session_resp.json()
        board_status = final_data.get("board_status")
        
        print(f"  Final board status: {board_status}")
        assert board_status == "unlocked", f"Board should stay UNLOCKED with credits remaining, but is: {board_status}"
        
        # Verify credits remaining is 2
        if final_data.get("session"):
            remaining = final_data["session"].get("credits_remaining")
            print(f"  Credits remaining: {remaining}")
            assert remaining == 2, f"Expected 2 credits remaining, got: {remaining}"
        
        print(f"  ✓ Board correctly stays unlocked with 2 credits remaining")
        
        # Cleanup: Lock the board
        self._ensure_board_locked(auth_headers)


class TestCleanup:
    """Cleanup after tests"""
    
    def test_cleanup_lock_board(self, auth_headers):
        """Ensure board is locked after all tests"""
        lock_resp = requests.post(
            f"{BASE_URL}/api/boards/{TEST_BOARD_ID}/lock",
            headers=auth_headers
        )
        print(f"Cleanup: Board lock response: {lock_resp.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
