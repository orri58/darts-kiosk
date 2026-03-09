"""
Iteration 32 - Observer Refactor Tests
======================================
Tests the major observer refactor:
- WebSocket/console event capture as PRIMARY match-end detection
- DOM polling as fallback
- WS_INTERCEPT_SCRIPT injection
- Game lifecycle with finalization chain logging

Also tests:
- /api/health, /api/auth/login
- /api/kiosk/BOARD-1/observer-status returns state and browser_open
- PWA manifest.json has start_url=/admin
- /admin and /kiosk/BOARD-1 routes return 200
"""
import pytest
import requests
import os
import time

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


class TestObserverImportsAndEnum:
    """Test observer module imports and enum values"""
    
    def test_observer_module_imports_cleanly(self):
        """Observer module should import without errors"""
        try:
            from backend.services.autodarts_observer import (
                ObserverState, ObserverManager, AutodartsObserver,
                WS_INTERCEPT_SCRIPT, observer_manager
            )
            print("SUCCESS: autodarts_observer module imports cleanly")
            assert True
        except ImportError as e:
            print(f"FAIL: Import error - {e}")
            pytest.fail(f"Observer module failed to import: {e}")
    
    def test_observer_state_enum_has_required_values(self):
        """ObserverState enum should have all required values"""
        from backend.services.autodarts_observer import ObserverState
        
        required_states = ['CLOSED', 'IDLE', 'IN_GAME', 'ROUND_TRANSITION', 'FINISHED', 'UNKNOWN', 'ERROR']
        
        for state in required_states:
            assert hasattr(ObserverState, state), f"ObserverState missing: {state}"
            print(f"SUCCESS: ObserverState.{state} exists = {getattr(ObserverState, state).value}")
        
        print(f"SUCCESS: All {len(required_states)} required ObserverState values present")
    
    def test_ws_intercept_script_defined(self):
        """WS_INTERCEPT_SCRIPT should be defined and contain WebSocket patching code"""
        from backend.services.autodarts_observer import WS_INTERCEPT_SCRIPT
        
        assert WS_INTERCEPT_SCRIPT is not None
        assert len(WS_INTERCEPT_SCRIPT) > 100, "WS_INTERCEPT_SCRIPT too short"
        
        # Check for key patterns in the script
        assert 'WebSocket' in WS_INTERCEPT_SCRIPT, "Missing WebSocket patching code"
        assert '__dartsKioskCapture' in WS_INTERCEPT_SCRIPT, "Missing capture object"
        assert 'matchFinished' in WS_INTERCEPT_SCRIPT, "Missing matchFinished flag"
        assert 'matchStarted' in WS_INTERCEPT_SCRIPT, "Missing matchStarted flag"
        assert 'winnerDetected' in WS_INTERCEPT_SCRIPT, "Missing winnerDetected flag"
        assert 'console.log' in WS_INTERCEPT_SCRIPT, "Missing console.log interception"
        
        print(f"SUCCESS: WS_INTERCEPT_SCRIPT defined ({len(WS_INTERCEPT_SCRIPT)} chars)")
        print("  - Contains WebSocket patching")
        print("  - Contains capture object __dartsKioskCapture")
        print("  - Contains matchFinished/matchStarted/winnerDetected flags")
        print("  - Contains console.log interception")
    
    def test_observer_manager_initializes(self):
        """ObserverManager should initialize without errors"""
        from backend.services.autodarts_observer import ObserverManager
        
        manager = ObserverManager()
        assert manager is not None
        assert hasattr(manager, 'get')
        assert hasattr(manager, 'get_status')
        assert hasattr(manager, 'get_all_statuses')
        assert hasattr(manager, 'open')
        assert hasattr(manager, 'close')
        assert hasattr(manager, 'close_all')
        
        print("SUCCESS: ObserverManager initializes and has all required methods")


class TestAPIEndpoints:
    """Test core API endpoints"""
    
    def test_health_endpoint(self):
        """GET /api/health should return healthy"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        
        data = response.json()
        assert data.get('status') == 'healthy', f"Status not healthy: {data}"
        print(f"SUCCESS: /api/health returns healthy (mode={data.get('mode')})")
    
    def test_auth_login(self):
        """POST /api/auth/login should work with admin credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        assert response.status_code == 200, f"Login failed: {response.status_code}"
        
        data = response.json()
        assert 'access_token' in data, "No access_token in response"
        assert 'user' in data, "No user in response"
        assert data['user']['username'] == 'admin'
        
        print(f"SUCCESS: /api/auth/login works (username={data['user']['username']})")
        return data['access_token']
    
    def test_observer_status_endpoint(self):
        """GET /api/kiosk/BOARD-1/observer-status should return state and browser_open"""
        response = requests.get(
            f"{BASE_URL}/api/kiosk/BOARD-1/observer-status",
            timeout=10
        )
        assert response.status_code == 200, f"Observer status failed: {response.status_code}"
        
        data = response.json()
        assert 'state' in data, f"Missing 'state' field: {data}"
        assert 'browser_open' in data, f"Missing 'browser_open' field: {data}"
        
        print(f"SUCCESS: /api/kiosk/BOARD-1/observer-status returns:")
        print(f"  state={data['state']}")
        print(f"  browser_open={data['browser_open']}")
        print(f"  autodarts_mode={data.get('autodarts_mode')}")


class TestPWAAndRoutes:
    """Test PWA manifest and routes"""
    
    def test_manifest_start_url(self):
        """GET /manifest.json should have start_url=/admin"""
        response = requests.get(f"{BASE_URL}/manifest.json", timeout=10)
        assert response.status_code == 200, f"Manifest failed: {response.status_code}"
        
        data = response.json()
        assert data.get('start_url') == '/admin', f"start_url is not /admin: {data.get('start_url')}"
        
        print(f"SUCCESS: /manifest.json has start_url=/admin")
        print(f"  name={data.get('name')}")
        print(f"  short_name={data.get('short_name')}")
    
    def test_admin_route_returns_200(self):
        """GET /admin should return 200 (SPA routing)"""
        response = requests.get(f"{BASE_URL}/admin", timeout=10)
        assert response.status_code == 200, f"/admin failed: {response.status_code}"
        print("SUCCESS: /admin returns 200")
    
    def test_kiosk_route_returns_200(self):
        """GET /kiosk/BOARD-1 should return 200"""
        response = requests.get(f"{BASE_URL}/kiosk/BOARD-1", timeout=10)
        assert response.status_code == 200, f"/kiosk/BOARD-1 failed: {response.status_code}"
        print("SUCCESS: /kiosk/BOARD-1 returns 200")


class TestGameLifecycle:
    """Test game lifecycle: unlock -> simulate-game-start -> simulate-game-end -> lock"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        self.token = response.json().get('access_token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Ensure board is locked before test
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers=self.headers,
            timeout=10
        )
        time.sleep(0.5)
    
    def test_single_credit_lifecycle(self):
        """
        Unlock with 1 credit -> simulate-game-start -> simulate-game-end -> board MUST lock
        """
        print("\n=== TEST: Single Credit Game Lifecycle ===")
        
        # Step 1: Unlock with 1 credit
        print("Step 1: Unlocking board with 1 credit...")
        unlock_response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"pricing_mode": "per_game", "credits": 1},
            headers=self.headers,
            timeout=10
        )
        assert unlock_response.status_code == 200, f"Unlock failed: {unlock_response.text}"
        unlock_data = unlock_response.json()
        assert unlock_data['credits_remaining'] == 1
        print(f"  Unlocked: credits_remaining={unlock_data['credits_remaining']}")
        
        # Verify board is unlocked
        session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
        assert session_response.json()['board_status'] == 'unlocked'
        print("  Board status: unlocked")
        
        # Step 2: Simulate game start
        print("Step 2: Simulating game start...")
        start_response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=self.headers,
            timeout=10
        )
        assert start_response.status_code == 200, f"Simulate start failed: {start_response.text}"
        print(f"  Response: {start_response.json()}")
        time.sleep(0.5)
        
        # Verify credit was consumed (should be 0 now)
        session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
        session_data = session_response.json()
        if session_data.get('session'):
            credits_after_start = session_data['session']['credits_remaining']
            print(f"  Credits after start: {credits_after_start}")
            assert credits_after_start == 0, f"Credits should be 0 after start, got {credits_after_start}"
        
        # Step 3: Simulate game end
        print("Step 3: Simulating game end...")
        end_response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=self.headers,
            timeout=10
        )
        assert end_response.status_code == 200, f"Simulate end failed: {end_response.text}"
        print(f"  Response: {end_response.json()}")
        
        # Wait for finalization
        time.sleep(1.0)
        
        # Step 4: Verify board is locked
        print("Step 4: Verifying board is locked...")
        session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
        session_data = session_response.json()
        board_status = session_data['board_status']
        print(f"  Board status: {board_status}")
        
        assert board_status == 'locked', f"Board should be locked after exhausting credits, got: {board_status}"
        print("SUCCESS: Board locked after exhausting 1 credit")
    
    def test_multi_credit_lifecycle(self):
        """
        Unlock with 3 credits -> 3x (start+end) -> board unlocked after game 1 and 2, locked after game 3
        """
        print("\n=== TEST: Multi-Credit Game Lifecycle (3 credits) ===")
        
        # Step 1: Unlock with 3 credits
        print("Step 1: Unlocking board with 3 credits...")
        unlock_response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"pricing_mode": "per_game", "credits": 3},
            headers=self.headers,
            timeout=10
        )
        assert unlock_response.status_code == 200, f"Unlock failed: {unlock_response.text}"
        print(f"  Unlocked with 3 credits")
        
        for game_num in range(1, 4):
            print(f"\n--- Game {game_num} ---")
            
            # Simulate game start
            start_response = requests.post(
                f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
                headers=self.headers,
                timeout=10
            )
            assert start_response.status_code == 200
            time.sleep(0.3)
            
            # Check credits
            session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
            session_data = session_response.json()
            if session_data.get('session'):
                credits_remaining = session_data['session']['credits_remaining']
                expected_credits = 3 - game_num
                print(f"  Credits after start: {credits_remaining} (expected: {expected_credits})")
                assert credits_remaining == expected_credits
            
            # Simulate game end
            end_response = requests.post(
                f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
                headers=self.headers,
                timeout=10
            )
            assert end_response.status_code == 200
            time.sleep(0.5)
            
            # Check board status
            session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
            board_status = session_response.json()['board_status']
            
            if game_num < 3:
                # Games 1 and 2: board should stay unlocked
                print(f"  Board status after game {game_num}: {board_status} (should be unlocked)")
                assert board_status == 'unlocked', f"Board should be unlocked after game {game_num}"
            else:
                # Game 3: board should be locked
                print(f"  Board status after game {game_num}: {board_status} (should be locked)")
                assert board_status == 'locked', f"Board should be locked after final game"
        
        print("\nSUCCESS: 3-credit lifecycle completed correctly")


class TestFinalizationChainLogging:
    """Test that finalization chain logging appears in logs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before tests"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        self.token = response.json().get('access_token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Ensure board is locked before test
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers=self.headers,
            timeout=10
        )
        time.sleep(0.5)
    
    def test_finalization_logging_structure(self):
        """
        After last-credit game end, the finalization chain should execute.
        We verify the chain by checking that the board locks correctly.
        (Note: Full log verification would require log access)
        """
        print("\n=== TEST: Finalization Chain Structure ===")
        
        # Unlock with 1 credit
        unlock_response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"pricing_mode": "per_game", "credits": 1},
            headers=self.headers,
            timeout=10
        )
        assert unlock_response.status_code == 200
        print("Board unlocked with 1 credit")
        
        # Simulate start (credit consumed)
        requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=self.headers,
            timeout=10
        )
        time.sleep(0.3)
        print("Game started (credit consumed)")
        
        # Simulate end (triggers finalization)
        end_response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=self.headers,
            timeout=10
        )
        assert end_response.status_code == 200
        print("Game ended - finalization chain triggered")
        
        # Wait for async finalization
        time.sleep(1.5)
        
        # Verify board is locked (finalization completed)
        session_response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
        board_status = session_response.json()['board_status']
        
        assert board_status == 'locked', f"Finalization failed - board not locked: {board_status}"
        print(f"Finalization complete - board status: {board_status}")
        
        # The finalization chain logs should contain:
        # - FINALIZATION START
        # - step_1: closing_observer
        # - step_2: killing_overlay_process
        # - step_3: verifying_board_locked
        # - FINALIZATION COMPLETE
        print("\nExpected log entries (verify in backend logs):")
        print("  - [Session-End] === FINALIZATION START ===")
        print("  - [Session-End] step_1: closing_observer")
        print("  - [Session-End] step_2: killing_overlay_process")
        print("  - [Session-End] step_3: verifying_board_locked")
        print("  - [Session-End] === FINALIZATION COMPLETE ===")
        
        print("\nSUCCESS: Finalization chain executed (board locked)")


class TestBoardSessionEndpoint:
    """Test board session endpoint"""
    
    def test_board_session_returns_required_fields(self):
        """GET /api/boards/BOARD-1/session should return required fields"""
        response = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
        assert response.status_code == 200
        
        data = response.json()
        assert 'board_status' in data, "Missing board_status"
        assert 'observer_state' in data, "Missing observer_state"
        assert 'observer_browser_open' in data, "Missing observer_browser_open"
        
        print(f"SUCCESS: /api/boards/BOARD-1/session returns:")
        print(f"  board_status={data['board_status']}")
        print(f"  observer_state={data['observer_state']}")
        print(f"  observer_browser_open={data['observer_browser_open']}")
        print(f"  autodarts_mode={data.get('autodarts_mode')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
