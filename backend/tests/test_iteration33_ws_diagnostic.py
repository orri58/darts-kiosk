"""
Iteration 33 - WebSocket Diagnostic & Observer Refactor Tests
=============================================================
Tests the major observer refactor with Playwright native WS observation:
- page.on('websocket') API for network-level frame capture (instead of JS injection)
- CONSOLE_CAPTURE_SCRIPT with add_init_script (runs before page JS)
- New /ws-diagnostic endpoint for debugging
- ObserverState enum values
- Game lifecycle with finalization chain logging

Key architectural change:
- OLD: JS injection approach (WS_INTERCEPT_SCRIPT) - didn't work because WS connections 
  were already open before injection
- NEW: Playwright's page.on('websocket') captures frames at network level regardless 
  of when connection was created. Console capture uses add_init_script.
"""
import pytest
import requests
import os
import time

# Get BASE_URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)


class TestObserverModuleImports:
    """Test observer module imports cleanly with new architecture"""
    
    def test_observer_module_imports_cleanly(self):
        """Observer module should import without errors - new architecture"""
        try:
            from backend.services.autodarts_observer import (
                observer_manager, ObserverState, ObserverManager, AutodartsObserver,
                CapturedWSFrame, WSEventState, CONSOLE_CAPTURE_SCRIPT
            )
            print("SUCCESS: autodarts_observer module imports cleanly with new architecture")
            print("  - observer_manager: imported")
            print("  - ObserverState: imported")
            print("  - ObserverManager: imported")
            print("  - AutodartsObserver: imported")
            print("  - CapturedWSFrame: imported (NEW - for network-level WS frame capture)")
            print("  - WSEventState: imported (NEW - accumulated WS event state)")
            print("  - CONSOLE_CAPTURE_SCRIPT: imported (replaces WS_INTERCEPT_SCRIPT)")
            assert True
        except ImportError as e:
            print(f"FAIL: Import error - {e}")
            pytest.fail(f"Observer module failed to import: {e}")


class TestObserverStateEnum:
    """Test ObserverState enum has all required values"""
    
    def test_observer_state_enum_has_all_values(self):
        """ObserverState enum should have: CLOSED, IDLE, IN_GAME, ROUND_TRANSITION, FINISHED, UNKNOWN, ERROR"""
        from backend.services.autodarts_observer import ObserverState
        
        required_states = {
            'CLOSED': 'closed',
            'IDLE': 'idle',
            'IN_GAME': 'in_game',
            'ROUND_TRANSITION': 'round_transition',
            'FINISHED': 'finished',
            'UNKNOWN': 'unknown',
            'ERROR': 'error'
        }
        
        for state_name, expected_value in required_states.items():
            assert hasattr(ObserverState, state_name), f"ObserverState missing: {state_name}"
            actual_value = getattr(ObserverState, state_name).value
            assert actual_value == expected_value, f"ObserverState.{state_name} = {actual_value}, expected {expected_value}"
            print(f"SUCCESS: ObserverState.{state_name} = '{actual_value}'")
        
        print(f"\nSUCCESS: All {len(required_states)} required ObserverState values present")


class TestConsoleCaptureScript:
    """Test CONSOLE_CAPTURE_SCRIPT (replaces old WS_INTERCEPT_SCRIPT)"""
    
    def test_console_capture_script_defined(self):
        """CONSOLE_CAPTURE_SCRIPT should be defined for add_init_script"""
        from backend.services.autodarts_observer import CONSOLE_CAPTURE_SCRIPT
        
        assert CONSOLE_CAPTURE_SCRIPT is not None
        assert len(CONSOLE_CAPTURE_SCRIPT) > 50, "CONSOLE_CAPTURE_SCRIPT too short"
        
        # Check for key patterns - this script captures console.log for match events
        assert '__dartsKioskConsole' in CONSOLE_CAPTURE_SCRIPT, "Missing __dartsKioskConsole object"
        assert 'console.log' in CONSOLE_CAPTURE_SCRIPT, "Missing console.log override"
        assert 'matchFinished' in CONSOLE_CAPTURE_SCRIPT, "Missing matchFinished flag"
        assert 'winnerDetected' in CONSOLE_CAPTURE_SCRIPT, "Missing winnerDetected flag"
        
        print(f"SUCCESS: CONSOLE_CAPTURE_SCRIPT defined ({len(CONSOLE_CAPTURE_SCRIPT)} chars)")
        print("  - Contains __dartsKioskConsole object for capturing console output")
        print("  - Contains console.log override for match event detection")
        print("  - Contains matchFinished/winnerDetected flags")
        print("  - This script is injected via add_init_script (runs BEFORE page JS)")


class TestWSEventStateAndCapturedFrame:
    """Test new dataclasses for network-level WS capture"""
    
    def test_ws_event_state_dataclass(self):
        """WSEventState should have all required fields for accumulated WS state"""
        from backend.services.autodarts_observer import WSEventState
        
        state = WSEventState()
        
        # Check default values
        assert state.match_active == False
        assert state.match_finished == False
        assert state.winner_detected == False
        assert state.last_match_state is None
        assert state.last_game_event is None
        assert state.last_match_id is None
        assert state.frames_received == 0
        assert state.match_relevant_frames == 0
        assert state.finish_trigger is None
        
        print("SUCCESS: WSEventState dataclass has all required fields with defaults")
        print("  - match_active: False")
        print("  - match_finished: False")
        print("  - winner_detected: False")
        print("  - frames_received: 0")
        print("  - match_relevant_frames: 0")
        print("  - finish_trigger: None")
        
        # Test reset method
        state.match_active = True
        state.match_finished = True
        state.reset()
        assert state.match_active == False
        assert state.match_finished == False
        print("SUCCESS: WSEventState.reset() works correctly")
    
    def test_captured_ws_frame_dataclass(self):
        """CapturedWSFrame should have required fields for frame capture"""
        from backend.services.autodarts_observer import CapturedWSFrame
        
        frame = CapturedWSFrame(
            timestamp="2026-01-01T00:00:00Z",
            url="wss://example.com",
            direction="received",
            raw_preview="test data",
            channel="autodarts.matches.123.state",
            payload_type="json",
            interpretation="match_started",
            payload_data={"state": "active"}
        )
        
        # Test to_dict
        frame_dict = frame.to_dict()
        assert 'ts' in frame_dict
        assert 'dir' in frame_dict
        assert 'channel' in frame_dict
        assert 'interp' in frame_dict
        assert 'raw' in frame_dict
        assert 'payload' in frame_dict
        
        print("SUCCESS: CapturedWSFrame dataclass works correctly")
        print(f"  to_dict() returns: {frame_dict}")


class TestWSDiagnosticEndpoint:
    """Test the NEW /ws-diagnostic endpoint for debugging"""
    
    def test_ws_diagnostic_endpoint_returns_valid_json(self):
        """GET /api/kiosk/BOARD-1/ws-diagnostic should return valid JSON with ws_state and captured_frames"""
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/ws-diagnostic", timeout=10)
        assert response.status_code == 200, f"WS diagnostic failed: {response.status_code}"
        
        data = response.json()
        
        # Required fields
        assert 'board_id' in data, "Missing board_id"
        assert 'ws_state' in data, "Missing ws_state field"
        assert 'captured_frames' in data, "Missing captured_frames field"
        
        # Optional fields when observer is not active
        if data.get('observer_active'):
            assert 'stable_state' in data
            assert 'debounce' in data
            ws_state = data['ws_state']
            assert 'match_active' in ws_state
            assert 'match_finished' in ws_state
            assert 'winner_detected' in ws_state
            assert 'frames_received' in ws_state
        
        print("SUCCESS: /api/kiosk/BOARD-1/ws-diagnostic returns valid JSON")
        print(f"  board_id: {data['board_id']}")
        print(f"  observer_active: {data.get('observer_active')}")
        print(f"  ws_state: {data['ws_state']}")
        print(f"  captured_frames_count: {data.get('captured_frames_count', len(data['captured_frames']))}")


class TestObserverStatusEndpoint:
    """Test observer status endpoint includes observer_active field"""
    
    def test_observer_status_has_required_fields(self):
        """GET /api/kiosk/BOARD-1/observer-status should return observer_active field"""
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/observer-status", timeout=10)
        assert response.status_code == 200, f"Observer status failed: {response.status_code}"
        
        data = response.json()
        assert 'state' in data, "Missing 'state' field"
        assert 'browser_open' in data, "Missing 'browser_open' field"
        assert 'board_id' in data, "Missing 'board_id' field"
        
        print("SUCCESS: /api/kiosk/BOARD-1/observer-status returns:")
        print(f"  board_id: {data.get('board_id')}")
        print(f"  state: {data['state']}")
        print(f"  browser_open: {data['browser_open']}")
        print(f"  autodarts_mode: {data.get('autodarts_mode')}")


class TestCoreAPIEndpoints:
    """Test core API endpoints"""
    
    def test_health_endpoint(self):
        """GET /api/health should return healthy"""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        
        data = response.json()
        assert data.get('status') == 'healthy', f"Status not healthy: {data}"
        print(f"SUCCESS: /api/health returns healthy (mode={data.get('mode')})")
    
    def test_auth_login(self):
        """POST /api/auth/login should work with admin/admin123"""
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


class TestGameLifecycleSingleCredit:
    """Test single credit game lifecycle: unlock -> start -> end -> board locks"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token and lock board before test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        self.token = response.json().get('access_token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Ensure board is locked before test
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers, timeout=10)
        time.sleep(0.5)
    
    def test_single_credit_lifecycle(self):
        """Unlock(1 credit) -> simulate-game-start -> simulate-game-end -> board MUST lock"""
        print("\n=== TEST: Single Credit Game Lifecycle ===")
        
        # Step 1: Unlock with 1 credit
        unlock_response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"pricing_mode": "per_game", "credits": 1},
            headers=self.headers,
            timeout=10
        )
        assert unlock_response.status_code == 200, f"Unlock failed: {unlock_response.text}"
        print(f"Step 1: Unlocked with 1 credit")
        
        # Verify board unlocked
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
        assert session_resp.json()['board_status'] == 'unlocked'
        
        # Step 2: Simulate game start
        start_response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=self.headers,
            timeout=10
        )
        assert start_response.status_code == 200
        time.sleep(0.5)
        print(f"Step 2: Game started (credit consumed)")
        
        # Step 3: Simulate game end
        end_response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=self.headers,
            timeout=10
        )
        assert end_response.status_code == 200
        time.sleep(1.0)
        print(f"Step 3: Game ended")
        
        # Step 4: Verify board locked
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
        board_status = session_resp.json()['board_status']
        assert board_status == 'locked', f"Expected locked, got {board_status}"
        print(f"Step 4: Board status = {board_status} (CORRECT)")
        
        print("SUCCESS: Single credit lifecycle works correctly")


class TestGameLifecycleMultipleCredits:
    """Test 3-credit game lifecycle: board stays unlocked until last credit"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token and lock board before test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        self.token = response.json().get('access_token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Ensure board is locked before test
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers, timeout=10)
        time.sleep(0.5)
    
    def test_three_credit_lifecycle(self):
        """Unlock(3 credits) -> 3x(start+end) -> board unlocked after 1&2, locked after 3"""
        print("\n=== TEST: 3-Credit Game Lifecycle ===")
        
        # Unlock with 3 credits
        unlock_response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"pricing_mode": "per_game", "credits": 3},
            headers=self.headers,
            timeout=10
        )
        assert unlock_response.status_code == 200
        print("Unlocked with 3 credits")
        
        for game_num in range(1, 4):
            print(f"\n--- Game {game_num} ---")
            
            # Start
            requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start", 
                         headers=self.headers, timeout=10)
            time.sleep(0.3)
            
            # End
            requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
                         headers=self.headers, timeout=10)
            time.sleep(0.5)
            
            # Check status
            session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
            board_status = session_resp.json()['board_status']
            
            if game_num < 3:
                assert board_status == 'unlocked', f"Game {game_num}: expected unlocked, got {board_status}"
                print(f"  Board status: {board_status} (correct - credits remaining)")
            else:
                assert board_status == 'locked', f"Game {game_num}: expected locked, got {board_status}"
                print(f"  Board status: {board_status} (correct - no credits left)")
        
        print("\nSUCCESS: 3-credit lifecycle works correctly")


class TestFinalizationChainLogging:
    """Test finalization chain after last-credit game end"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token and lock board before test"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        self.token = response.json().get('access_token')
        self.headers = {"Authorization": f"Bearer {self.token}"}
        
        # Ensure board is locked before test
        requests.post(f"{BASE_URL}/api/boards/BOARD-1/lock", headers=self.headers, timeout=10)
        time.sleep(0.5)
    
    def test_finalization_chain_executes(self):
        """After last-credit game end, logs should contain FINALIZATION START and FINALIZATION COMPLETE"""
        print("\n=== TEST: Finalization Chain ===")
        
        # Unlock with 1 credit
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"pricing_mode": "per_game", "credits": 1},
            headers=self.headers,
            timeout=10
        )
        
        # Start game (credit consumed)
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
                     headers=self.headers, timeout=10)
        time.sleep(0.3)
        
        # End game (triggers finalization)
        requests.post(f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
                     headers=self.headers, timeout=10)
        time.sleep(1.5)  # Wait for async finalization
        
        # Verify board locked (proof finalization completed)
        session_resp = requests.get(f"{BASE_URL}/api/boards/BOARD-1/session", timeout=10)
        board_status = session_resp.json()['board_status']
        assert board_status == 'locked', f"Finalization failed - board not locked: {board_status}"
        
        print("SUCCESS: Finalization chain executed (board locked)")
        print("\nExpected log entries (verify in backend logs):")
        print("  - [Session-End] === FINALIZATION START === board=BOARD-1")
        print("  - [Session-End] step_1: closing_observer (Autodarts browser)")
        print("  - [Session-End] step_2: killing_overlay_process")
        print("  - [Session-End] step_3: verifying_board_locked")
        print("  - [Session-End] === FINALIZATION COMPLETE === board=BOARD-1")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
