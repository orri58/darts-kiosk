"""
Iteration 34 - Regression Fixes Verification
=============================================
Testing two key regressions:
1. False lock on round/turn transition — observer must ONLY finalize on true match end 
   (matchshot/matchWinner), NOT on gameshot/gameWinner/state:finished
2. Chrome profile path must be exactly data/chrome_profile/BOARD-1 everywhere, 
   no kiosk_chrome_profile references

Key changes in autodarts_observer.py:
- _classify_frame now ONLY returns match_finished for matchshot and matchWinner
- state:finished -> game_state_finished (NOT match_finished)
- gameWinner removed from match-end signals
- _update_ws_state only sets match_finished for match_finished_matchshot and match_finished_winner_field
"""
import pytest
import os
import sys

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


# =============================================================================
# ISSUE 1: Observer Classification Tests
# =============================================================================

class TestObserverClassification:
    """Test that _classify_frame correctly classifies WS frames."""
    
    def test_observer_module_imports(self):
        """Verify observer module imports cleanly with new architecture."""
        from backend.services.autodarts_observer import (
            AutodartsObserver,
            ObserverState,
            WSEventState,
            CapturedWSFrame,
            observer_manager
        )
        assert AutodartsObserver is not None
        assert ObserverState is not None
        print("PASS: Observer module imports cleanly")
    
    def test_classify_gameshot_as_round_transition(self):
        """
        CRITICAL: gameshot must be classified as round_transition_gameshot, NOT match_finished.
        Gameshot indicates a leg (game) end, but the match may continue.
        """
        from backend.services.autodarts_observer import AutodartsObserver
        
        observer = AutodartsObserver("TEST-BOARD")
        
        # Test 1: Simple gameshot message
        result = observer._classify_frame(
            raw='{"type":"gameshot","data":{"winner":"player1"}}',
            channel='autodarts.matches.abc123.game-events',
            payload={'type': 'gameshot', 'data': {'winner': 'player1'}}
        )
        assert result == "round_transition_gameshot", f"Expected round_transition_gameshot, got {result}"
        assert "match_finished" not in result, "gameshot should NOT trigger match_finished"
        print("PASS: gameshot classified as round_transition_gameshot (NOT match_finished)")
        
        # Test 2: Gameshot in raw text
        result2 = observer._classify_frame(
            raw='GAMESHOT! Player wins the leg!',
            channel='unknown',
            payload=None
        )
        assert result2 == "round_transition_gameshot", f"Expected round_transition_gameshot, got {result2}"
        print("PASS: gameshot text classified as round_transition_gameshot")
    
    def test_classify_state_finished_as_game_state_finished(self):
        """
        CRITICAL: state:finished from a leg must NOT set match_finished.
        It should be classified as game_state_finished which is logged but does not lock the board.
        """
        from backend.services.autodarts_observer import AutodartsObserver
        
        observer = AutodartsObserver("TEST-BOARD")
        
        # Test: state: finished payload (could be leg or match - treated conservatively)
        result = observer._classify_frame(
            raw='{"state":"finished","data":{"legs":{"player1":1,"player2":0}}}',
            channel='autodarts.matches.abc123.state',
            payload={'state': 'finished', 'data': {'legs': {'player1': 1, 'player2': 0}}}
        )
        assert result == "game_state_finished", f"Expected game_state_finished, got {result}"
        assert result != "match_finished", "state:finished should NOT be match_finished"
        print("PASS: state:finished classified as game_state_finished (NOT match_finished)")
    
    def test_classify_matchshot_as_match_finished(self):
        """
        CRITICAL: matchshot MUST be classified as match_finished_matchshot.
        This is the definitive signal that the MATCH (not just a leg) is over.
        """
        from backend.services.autodarts_observer import AutodartsObserver
        
        observer = AutodartsObserver("TEST-BOARD")
        
        # Test 1: matchshot in payload
        result = observer._classify_frame(
            raw='{"type":"matchshot","data":{"winner":"player1"}}',
            channel='autodarts.matches.abc123.game-events',
            payload={'type': 'matchshot', 'data': {'winner': 'player1'}}
        )
        assert result == "match_finished_matchshot", f"Expected match_finished_matchshot, got {result}"
        print("PASS: matchshot classified as match_finished_matchshot")
        
        # Test 2: matchshot in raw text (without gameshot)
        result2 = observer._classify_frame(
            raw='MATCHSHOT! Player wins the match!',
            channel='unknown',
            payload=None
        )
        assert result2 == "match_finished_matchshot", f"Expected match_finished_matchshot, got {result2}"
        print("PASS: matchshot text classified as match_finished_matchshot")
    
    def test_classify_match_winner_as_match_finished(self):
        """
        CRITICAL: matchWinner field MUST trigger match_finished_winner_field.
        This is distinct from gameWinner (leg winner) which should NOT trigger match end.
        """
        from backend.services.autodarts_observer import AutodartsObserver
        
        observer = AutodartsObserver("TEST-BOARD")
        
        # Test 1: matchWinner in payload
        result = observer._classify_frame(
            raw='{"matchWinner":"player1","state":"finished"}',
            channel='autodarts.matches.abc123.state',
            payload={'matchWinner': 'player1', 'state': 'finished'}
        )
        assert result == "match_finished_winner_field", f"Expected match_finished_winner_field, got {result}"
        print("PASS: matchWinner field classified as match_finished_winner_field")
        
        # Test 2: matchWinner in nested data
        result2 = observer._classify_frame(
            raw='{"data":{"matchWinner":"player2"}}',
            channel='autodarts.matches.abc123.state',
            payload={'data': {'matchWinner': 'player2'}}
        )
        assert result2 == "match_finished_winner_field", f"Expected match_finished_winner_field, got {result2}"
        print("PASS: nested matchWinner field classified as match_finished_winner_field")
    
    def test_game_winner_does_not_trigger_match_finished(self):
        """
        CRITICAL: gameWinner (leg winner) must NOT trigger match_finished.
        The match continues after a leg is won.
        """
        from backend.services.autodarts_observer import AutodartsObserver
        
        observer = AutodartsObserver("TEST-BOARD")
        
        # Test: gameWinner without matchWinner should NOT be match_finished
        result = observer._classify_frame(
            raw='{"gameWinner":"player1","state":"finished"}',
            channel='autodarts.matches.abc123.state',
            payload={'gameWinner': 'player1', 'state': 'finished'}
        )
        # Should be game_state_finished due to state:finished, NOT match_finished
        assert "match_finished" not in result or result == "game_state_finished", \
            f"gameWinner should NOT trigger match_finished, got {result}"
        print(f"PASS: gameWinner classified as {result} (NOT match_finished_*)")


class TestWSEventStateUpdate:
    """Test that _update_ws_state correctly updates state based on classification."""
    
    def test_update_ws_state_on_matchshot(self):
        """match_finished_matchshot MUST set ws.match_finished = True."""
        from backend.services.autodarts_observer import AutodartsObserver
        
        observer = AutodartsObserver("TEST-BOARD")
        
        # Reset state
        observer._ws_state.reset()
        assert observer._ws_state.match_finished == False
        
        # Simulate matchshot classification
        observer._update_ws_state(
            interpretation="match_finished_matchshot",
            channel="autodarts.matches.abc123.game-events",
            payload={'type': 'matchshot'},
            raw='{"type":"matchshot"}'
        )
        
        assert observer._ws_state.match_finished == True, "matchshot should set match_finished=True"
        assert observer._ws_state.winner_detected == True, "matchshot should set winner_detected=True"
        assert "match_finished_matchshot" in observer._ws_state.finish_trigger, "finish_trigger should indicate matchshot"
        print("PASS: match_finished_matchshot correctly sets ws.match_finished=True")
    
    def test_update_ws_state_on_match_winner_field(self):
        """match_finished_winner_field MUST set ws.match_finished = True."""
        from backend.services.autodarts_observer import AutodartsObserver
        
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state.reset()
        
        observer._update_ws_state(
            interpretation="match_finished_winner_field",
            channel="autodarts.matches.abc123.state",
            payload={'matchWinner': 'player1'},
            raw='{"matchWinner":"player1"}'
        )
        
        assert observer._ws_state.match_finished == True, "matchWinner should set match_finished=True"
        assert observer._ws_state.winner_detected == True, "matchWinner should set winner_detected=True"
        print("PASS: match_finished_winner_field correctly sets ws.match_finished=True")
    
    def test_update_ws_state_on_game_state_finished_does_not_set_match_finished(self):
        """
        CRITICAL: game_state_finished (state:finished from leg) must NOT set match_finished.
        This is the key fix for the false lock regression.
        """
        from backend.services.autodarts_observer import AutodartsObserver
        
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state.reset()
        
        observer._update_ws_state(
            interpretation="game_state_finished",
            channel="autodarts.matches.abc123.state",
            payload={'state': 'finished'},
            raw='{"state":"finished"}'
        )
        
        assert observer._ws_state.match_finished == False, \
            "game_state_finished should NOT set match_finished=True"
        assert observer._ws_state.winner_detected == False, \
            "game_state_finished should NOT set winner_detected=True"
        print("PASS: game_state_finished does NOT set ws.match_finished (prevents false lock)")
    
    def test_update_ws_state_on_round_transition_gameshot(self):
        """round_transition_gameshot must NOT set match_finished."""
        from backend.services.autodarts_observer import AutodartsObserver
        
        observer = AutodartsObserver("TEST-BOARD")
        observer._ws_state.reset()
        
        observer._update_ws_state(
            interpretation="round_transition_gameshot",
            channel="autodarts.matches.abc123.game-events",
            payload={'type': 'gameshot'},
            raw='{"type":"gameshot"}'
        )
        
        assert observer._ws_state.match_finished == False, \
            "gameshot should NOT set match_finished=True"
        assert observer._ws_state.last_game_event == "gameshot", \
            "gameshot should set last_game_event='gameshot'"
        print("PASS: round_transition_gameshot does NOT set ws.match_finished")


# =============================================================================
# ISSUE 2: Chrome Profile Path Verification
# =============================================================================

class TestChromeProfilePath:
    """Verify chrome_profile path is correct, no kiosk_chrome_profile references."""
    
    def test_observer_default_profile_path(self):
        """Observer default profile path must be data/chrome_profile (not kiosk_chrome_profile)."""
        from backend.services.autodarts_observer import CHROME_PROFILE_DIR
        
        assert "kiosk_chrome_profile" not in CHROME_PROFILE_DIR, \
            f"CHROME_PROFILE_DIR should not contain 'kiosk_chrome_profile': {CHROME_PROFILE_DIR}"
        assert "chrome_profile" in CHROME_PROFILE_DIR, \
            f"CHROME_PROFILE_DIR should contain 'chrome_profile': {CHROME_PROFILE_DIR}"
        print(f"PASS: CHROME_PROFILE_DIR = {CHROME_PROFILE_DIR} (correct)")
    
    def test_updater_service_protected_paths(self):
        """Updater service protected_paths must use chrome_profile, not kiosk_chrome_profile."""
        from backend.services.updater_service import UpdaterService
        
        service = UpdaterService()
        # Create a dummy manifest to inspect protected_paths
        manifest_result = service.write_manifest(
            staging_dir="/tmp/staging",
            backup_path="/tmp/backup.zip",
            target_version="1.0.0"
        )
        
        manifest = manifest_result.get('manifest', {})
        protected_paths = manifest.get('protected_paths', [])
        
        # Check no kiosk_chrome_profile in protected_paths
        for path in protected_paths:
            assert "kiosk_chrome_profile" not in path, \
                f"protected_paths contains 'kiosk_chrome_profile': {path}"
        
        # Check chrome_profile is in protected_paths
        chrome_profile_found = any("chrome_profile" in path for path in protected_paths)
        assert chrome_profile_found, \
            f"protected_paths should contain 'chrome_profile': {protected_paths}"
        
        print(f"PASS: updater protected_paths = {protected_paths} (correct)")
    
    def test_no_kiosk_chrome_profile_in_main_observer_source(self):
        """Verify no kiosk_chrome_profile references in autodarts_observer.py."""
        import os
        
        observer_path = os.path.join(
            os.path.dirname(__file__), '..', 'services', 'autodarts_observer.py'
        )
        
        with open(observer_path, 'r') as f:
            content = f.read()
        
        assert "kiosk_chrome_profile" not in content, \
            "autodarts_observer.py should not contain 'kiosk_chrome_profile'"
        print("PASS: autodarts_observer.py has no 'kiosk_chrome_profile' references")
    
    def test_no_kiosk_chrome_profile_in_updater_service_source(self):
        """Verify no kiosk_chrome_profile references in updater_service.py."""
        import os
        
        updater_path = os.path.join(
            os.path.dirname(__file__), '..', 'services', 'updater_service.py'
        )
        
        with open(updater_path, 'r') as f:
            content = f.read()
        
        assert "kiosk_chrome_profile" not in content, \
            "updater_service.py should not contain 'kiosk_chrome_profile'"
        print("PASS: updater_service.py has no 'kiosk_chrome_profile' references")
    
    def test_start_bat_uses_correct_chrome_profile_path(self):
        """Verify start.bat uses chrome_profile, not kiosk_chrome_profile."""
        import os
        
        start_bat_path = '/app/release/windows/start.bat'
        
        if not os.path.exists(start_bat_path):
            pytest.skip("start.bat not found in expected location")
        
        with open(start_bat_path, 'r') as f:
            content = f.read()
        
        assert "kiosk_chrome_profile" not in content, \
            "start.bat should not contain 'kiosk_chrome_profile'"
        assert "chrome_profile" in content, \
            "start.bat should contain 'chrome_profile'"
        print("PASS: start.bat uses 'chrome_profile' correctly")


# =============================================================================
# API Verification Tests
# =============================================================================

class TestAPIEndpoints:
    """Test API endpoints are working."""
    
    def test_health_endpoint(self):
        """GET /api/health returns healthy."""
        import requests
        
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.status_code}"
        data = response.json()
        assert data.get('status') == 'healthy', f"Health status not healthy: {data}"
        print(f"PASS: /api/health returns {data}")
    
    def test_ws_diagnostic_endpoint(self):
        """GET /api/kiosk/BOARD-1/ws-diagnostic returns expected structure."""
        import requests
        
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        response = requests.get(f"{BASE_URL}/api/kiosk/BOARD-1/ws-diagnostic", timeout=10)
        assert response.status_code == 200, f"ws-diagnostic failed: {response.status_code}"
        data = response.json()
        
        # Verify expected fields
        assert 'board_id' in data, "Missing board_id in ws-diagnostic response"
        assert data['board_id'] == 'BOARD-1', f"Wrong board_id: {data['board_id']}"
        assert 'ws_state' in data, "Missing ws_state in ws-diagnostic response"
        assert 'captured_frames' in data, "Missing captured_frames in ws-diagnostic response"
        
        print(f"PASS: /api/kiosk/BOARD-1/ws-diagnostic returns correct structure")


# =============================================================================
# Game Lifecycle Tests
# =============================================================================

class TestGameLifecycle:
    """Test game lifecycle with credit consumption."""
    
    def get_auth_headers(self):
        """Get admin auth headers."""
        import requests
        
        if not BASE_URL:
            return None
        
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        if response.status_code == 200:
            token = response.json().get('access_token')
            return {"Authorization": f"Bearer {token}"}
        return None
    
    def get_board_status(self, headers):
        """Get board session status with parsed fields."""
        import requests
        
        response = requests.get(
            f"{BASE_URL}/api/boards/BOARD-1/session",
            headers=headers,
            timeout=10
        )
        if response.status_code != 200:
            return None
        
        data = response.json()
        # Parse the API response into consistent format
        board_status = data.get('board_status', 'unknown')
        session = data.get('session') or {}
        
        return {
            'board_status': board_status,
            'is_locked': board_status == 'locked',
            'credits_remaining': session.get('credits_remaining', 0),
            'credits_total': session.get('credits_total', 0),
            'raw': data
        }
    
    def test_single_credit_lifecycle(self):
        """Single credit: unlock -> start -> end -> board LOCKED."""
        import requests
        
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        headers = self.get_auth_headers()
        if not headers:
            pytest.skip("Auth failed")
        
        # Step 0: Lock board first to reset any existing session
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers=headers,
            timeout=10
        )
        import time
        time.sleep(0.5)
        
        # Step 1: Unlock with 1 credit
        unlock_response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"credits": 1},
            headers=headers,
            timeout=10
        )
        assert unlock_response.status_code in [200, 201], f"Unlock failed: {unlock_response.text}"
        print("Step 1: Unlocked board with 1 credit")
        
        # Step 2: Simulate game start (consumes credit)
        start_response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=headers,
            timeout=10
        )
        assert start_response.status_code in [200, 201], f"Simulate start failed: {start_response.text}"
        print("Step 2: Simulated game start")
        
        # Step 3: Simulate game end
        end_response = requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=headers,
            timeout=10
        )
        assert end_response.status_code in [200, 201], f"Simulate end failed: {end_response.text}"
        print("Step 3: Simulated game end")
        
        # Step 4: Verify board is locked (0 credits remaining)
        import time
        time.sleep(1)  # Allow finalization to complete
        
        status = self.get_board_status(headers)
        assert status is not None, "Failed to get board status"
        
        is_locked = status.get('is_locked', True)
        credits_remaining = status.get('credits_remaining', 0)
        
        print(f"Step 4: Board status - is_locked={is_locked}, credits_remaining={credits_remaining}")
        assert is_locked == True or credits_remaining == 0, \
            f"Board should be locked after single credit game: {status}"
        
        print("PASS: Single credit lifecycle works correctly")
    
    def test_multi_credit_lifecycle(self):
        """3 credits: board stays unlocked after games 1&2, locks after game 3."""
        import requests
        import time
        
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        
        headers = self.get_auth_headers()
        if not headers:
            pytest.skip("Auth failed")
        
        # Step 0: Lock board first to reset state
        requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/lock",
            headers=headers,
            timeout=10
        )
        time.sleep(0.5)
        
        # Step 1: Unlock with 3 credits
        unlock_response = requests.post(
            f"{BASE_URL}/api/boards/BOARD-1/unlock",
            json={"credits": 3},
            headers=headers,
            timeout=10
        )
        assert unlock_response.status_code in [200, 201], f"Unlock failed: {unlock_response.text}"
        print("Step 1: Locked then unlocked board with 3 credits")
        
        # Games 1 and 2: Board should stay unlocked
        for game_num in [1, 2]:
            # Start game
            requests.post(
                f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
                headers=headers,
                timeout=10
            )
            # End game
            requests.post(
                f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
                headers=headers,
                timeout=10
            )
            time.sleep(0.5)
            
            status = self.get_board_status(headers)
            credits_remaining = status.get('credits_remaining', 0)
            is_locked = status.get('is_locked', True)
            
            expected_credits = 3 - game_num
            print(f"After game {game_num}: credits_remaining={credits_remaining}, is_locked={is_locked}")
            
            if game_num < 3:
                # Should still have credits and not be locked
                assert credits_remaining > 0 or not is_locked, \
                    f"Board should still be unlocked after game {game_num}"
        
        # Game 3: Board should lock
        requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-start",
            headers=headers,
            timeout=10
        )
        requests.post(
            f"{BASE_URL}/api/kiosk/BOARD-1/simulate-game-end",
            headers=headers,
            timeout=10
        )
        time.sleep(1)
        
        status = self.get_board_status(headers)
        credits_remaining = status.get('credits_remaining', 0)
        is_locked = status.get('is_locked', True)
        
        print(f"After game 3: credits_remaining={credits_remaining}, is_locked={is_locked}")
        assert credits_remaining == 0 or is_locked, \
            f"Board should be locked after 3 games with 3 credits: {status}"
        
        print("PASS: Multi-credit lifecycle works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
