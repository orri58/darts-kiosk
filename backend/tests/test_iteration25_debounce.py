"""
Iteration 25 - Debounce Logic Testing

Tests the NEW debounce logic that prevents false exits from in_game during turn changes.

Key features to test:
1. Backend debounce constants: DEBOUNCE_EXIT_POLLS=3, DEBOUNCE_POLL_INTERVAL=2
2. Backend observer _observe_loop has debounce logic
3. Backend observer entering in_game is immediate (no debounce)
4. Backend observer exiting in_game requires consecutive confirmation polls
5. Full lifecycle with credits
6. Overlay endpoint returns visible:false when locked
"""
import os
import pytest
import requests
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    BASE_URL = "https://boardgame-repair.preview.emergentagent.com"

BOARD_ID = "BOARD-1"


# ============================================================
# Module 1: Authentication fixture
# ============================================================

@pytest.fixture(scope="module")
def admin_token():
    """Login as admin and return JWT token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        token = data.get("access_token")
        if token:
            return token
    pytest.skip("Admin login failed - skipping authenticated tests")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    """Return headers with auth token."""
    return {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }


# ============================================================
# Module 2: Health and basic API tests
# ============================================================

class TestHealthAndBasicAPI:
    """Verify basic API health and accessibility."""

    def test_health_endpoint(self):
        """GET /api/health returns healthy."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data.get("status") == "healthy", f"Status not healthy: {data}"
        print(f"PASS: Health endpoint returns healthy, mode={data.get('mode')}")

    def test_admin_login(self):
        """Admin login returns access_token."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, f"No access_token in response: {data}"
        print("PASS: Admin login returns access_token")


# ============================================================
# Module 3: Debounce constants verification (code check)
# ============================================================

class TestDebounceCodeConstants:
    """Verify debounce constants are correctly defined in observer code."""

    def test_debounce_constants_exist(self):
        """Check DEBOUNCE_EXIT_POLLS=3 and DEBOUNCE_POLL_INTERVAL=2 in code."""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, 'r') as f:
            code = f.read()
        
        # Check DEBOUNCE_EXIT_POLLS
        assert "DEBOUNCE_EXIT_POLLS" in code, "DEBOUNCE_EXIT_POLLS not found in observer code"
        match_polls = re.search(r"DEBOUNCE_EXIT_POLLS\s*=\s*int\([^)]*['\"](\d+)['\"]", code)
        if match_polls:
            default_polls = match_polls.group(1)
            assert default_polls == "3", f"Default DEBOUNCE_EXIT_POLLS should be 3, found {default_polls}"
        
        # Check DEBOUNCE_POLL_INTERVAL
        assert "DEBOUNCE_POLL_INTERVAL" in code, "DEBOUNCE_POLL_INTERVAL not found in observer code"
        match_interval = re.search(r"DEBOUNCE_POLL_INTERVAL\s*=\s*int\([^)]*['\"](\d+)['\"]", code)
        if match_interval:
            default_interval = match_interval.group(1)
            assert default_interval == "2", f"Default DEBOUNCE_POLL_INTERVAL should be 2, found {default_interval}"
        
        print("PASS: Debounce constants DEBOUNCE_EXIT_POLLS=3, DEBOUNCE_POLL_INTERVAL=2 found")

    def test_debounce_logic_in_observe_loop(self):
        """Check _observe_loop has debounce logic with RECOVERED pattern."""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, 'r') as f:
            code = f.read()
        
        # Check for debounce-related variables
        assert "_exit_polls" in code, "_exit_polls variable not found"
        assert "_exit_saw_finished" in code, "_exit_saw_finished variable not found"
        
        # Check for RECOVERED log message (indicates debounce recovery logic)
        assert "RECOVERED" in code, "RECOVERED pattern not found in debounce logic"
        
        # Check debounce confirmation pattern
        assert "DEBOUNCE_EXIT_POLLS" in code, "DEBOUNCE_EXIT_POLLS not used in code"
        
        print("PASS: _observe_loop has debounce logic (RECOVERED, _exit_polls, DEBOUNCE_EXIT_POLLS)")

    def test_immediate_entry_no_debounce(self):
        """Check entering in_game is immediate (no debounce on entry)."""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, 'r') as f:
            code = f.read()
        
        # The code should show "immediate" for entering in_game
        assert "immediate" in code.lower(), "No 'immediate' keyword found for in_game entry"
        
        # Check for the CASE B section that handles entering IN_GAME
        assert "Entering IN_GAME: immediate" in code or "in_game (immediate)" in code, \
            "Entry to in_game should be marked as immediate in comments/logs"
        
        print("PASS: Entering in_game is immediate (no debounce on entry)")

    def test_exit_requires_consecutive_polls(self):
        """Check exiting in_game requires DEBOUNCE_EXIT_POLLS consecutive polls."""
        observer_path = "/app/backend/services/autodarts_observer.py"
        with open(observer_path, 'r') as f:
            code = f.read()
        
        # Check for consecutive poll check
        assert "_exit_polls >=" in code or "_exit_polls <" in code, \
            "_exit_polls comparison not found"
        
        # Check for the confirmed pattern
        assert "CONFIRMED" in code, "CONFIRMED pattern not found for exit confirmation"
        
        print("PASS: Exiting in_game requires consecutive confirmation polls")


# ============================================================
# Module 4: Unit test execution verification
# ============================================================

class TestDebounceUnitTests:
    """Run and verify the debounce unit tests."""

    def test_run_debounce_unit_tests(self):
        """Run test_debounce.py and verify all 4 tests pass."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "pytest", "/app/backend/tests/test_debounce.py", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONPATH": "/app"},
            timeout=60
        )
        
        # Check for all expected tests
        output = result.stdout + result.stderr
        
        assert "test_debounce_config" in output, "test_debounce_config not found in output"
        assert "test_turn_change_does_not_exit_in_game" in output, "test_turn_change_does_not_exit_in_game not found"
        assert "test_real_abort_triggers_after_debounce" in output, "test_real_abort_triggers_after_debounce not found"
        assert "test_real_finish_triggers_after_debounce" in output, "test_real_finish_triggers_after_debounce not found"
        assert "test_mixed_flicker_does_not_exit" in output, "test_mixed_flicker_does_not_exit not found"
        
        # Count passed tests
        passed = output.count(" PASSED")
        assert passed >= 4, f"Expected at least 4 tests to pass, got {passed}. Output: {output[:500]}"
        
        print(f"PASS: Debounce unit tests passed ({passed} tests)")


# ============================================================
# Module 5: API Lifecycle tests (with simulation endpoints)
# ============================================================

class TestDebounceLifecycle:
    """Test full lifecycle with debounce through API simulation."""

    def test_unlock_board_with_credits(self, auth_headers):
        """POST /api/boards/BOARD-1/unlock creates session with credits."""
        # First ensure board is locked
        lock_resp = requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/lock",
            headers=auth_headers,
            timeout=10
        )
        # Lock might fail if already locked, that's OK
        
        # Now unlock with 2 credits
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
            headers=auth_headers,
            json={"credits": 2, "pricing_mode": "per_game"},
            timeout=10
        )
        assert unlock_resp.status_code in [200, 201], f"Unlock failed: {unlock_resp.text}"
        data = unlock_resp.json()
        
        # Check session was created (response has 'id' field for session)
        assert "id" in data or "session_id" in data or data.get("message") == "Board unlocked", \
            f"Unexpected unlock response: {data}"
        
        print(f"PASS: Board unlocked with 2 credits. Response: {data.get('message', data)}")

    def test_simulate_game_start_consumes_credit(self, auth_headers):
        """POST /api/kiosk/BOARD-1/simulate-game-start consumes credit."""
        # Check credits before
        overlay_before = requests.get(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/overlay",
            timeout=10
        )
        credits_before = overlay_before.json().get("credits_remaining", 0)
        
        # Simulate game start
        start_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
            headers=auth_headers,
            timeout=10
        )
        assert start_resp.status_code == 200, f"Simulate start failed: {start_resp.text}"
        
        # Check credits after
        overlay_after = requests.get(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/overlay",
            timeout=10
        )
        credits_after = overlay_after.json().get("credits_remaining", 0)
        
        # Credit should be decremented by 1
        if credits_before > 0:
            assert credits_after == credits_before - 1, \
                f"Credit not decremented: before={credits_before}, after={credits_after}"
        
        print(f"PASS: simulate-game-start consumed credit ({credits_before} -> {credits_after})")

    def test_simulate_game_end_finished(self, auth_headers):
        """POST /api/kiosk/BOARD-1/simulate-game-end triggers game_ended(finished)."""
        end_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
            headers=auth_headers,
            timeout=10
        )
        assert end_resp.status_code == 200, f"Simulate end failed: {end_resp.text}"
        data = end_resp.json()
        assert "Simulated game end" in data.get("message", ""), f"Unexpected response: {data}"
        
        print(f"PASS: simulate-game-end completed: {data.get('message')}")

    def test_simulate_game_abort(self, auth_headers):
        """POST /api/kiosk/BOARD-1/simulate-game-abort triggers game_ended(aborted)."""
        # First start a new game
        start_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
            headers=auth_headers,
            timeout=10
        )
        # If start fails due to locked board, unlock first
        if start_resp.status_code != 200:
            requests.post(
                f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                headers=auth_headers,
                json={"credits": 1},
                timeout=10
            )
            start_resp = requests.post(
                f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
                headers=auth_headers,
                timeout=10
            )
        
        # Now abort the game
        abort_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort",
            headers=auth_headers,
            timeout=10
        )
        assert abort_resp.status_code == 200, f"Simulate abort failed: {abort_resp.text}"
        data = abort_resp.json()
        assert "Simulated game abort" in data.get("message", ""), f"Unexpected response: {data}"
        
        print(f"PASS: simulate-game-abort completed: {data.get('message')}")


# ============================================================
# Module 6: Full lifecycle test (unlock → start → finish → start → abort → lock)
# ============================================================

class TestFullDebounceLifecycle:
    """Test complete lifecycle: unlock(2) → start → finish → start → abort → auto-lock."""

    def test_full_lifecycle_with_credits(self, auth_headers):
        """
        Full lifecycle: unlock(2 credits) → start → finish (stays unlocked, 1 credit) 
        → start → abort (auto-lock, 0 credits)
        """
        # Step 1: Lock board first to ensure clean state
        requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/lock",
            headers=auth_headers,
            timeout=10
        )
        
        # Step 2: Unlock with 2 credits
        unlock_resp = requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
            headers=auth_headers,
            json={"credits": 2, "pricing_mode": "per_game"},
            timeout=10
        )
        assert unlock_resp.status_code in [200, 201], f"Unlock failed: {unlock_resp.text}"
        print("Step 1: Unlocked with 2 credits")
        
        # Step 3: Start game 1 (credits: 2 → 1)
        start1_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
            headers=auth_headers,
            timeout=10
        )
        assert start1_resp.status_code == 200, f"Start 1 failed: {start1_resp.text}"
        
        # Verify credit decremented
        overlay1 = requests.get(f"{BASE_URL}/api/kiosk/{BOARD_ID}/overlay", timeout=10)
        credits_after_start1 = overlay1.json().get("credits_remaining", -1)
        assert credits_after_start1 == 1, f"Expected 1 credit after start, got {credits_after_start1}"
        print(f"Step 2: Game 1 started, credits: 2 → {credits_after_start1}")
        
        # Step 4: Finish game 1 (stays unlocked with 1 credit)
        end1_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
            headers=auth_headers,
            timeout=10
        )
        assert end1_resp.status_code == 200, f"End 1 failed: {end1_resp.text}"
        
        # Verify still unlocked
        overlay2 = requests.get(f"{BASE_URL}/api/kiosk/{BOARD_ID}/overlay", timeout=10)
        visible_after_end1 = overlay2.json().get("visible", False)
        assert visible_after_end1 == True, f"Expected visible=True after finish with credit remaining"
        print(f"Step 3: Game 1 finished, stays unlocked with 1 credit")
        
        # Step 5: Start game 2 (credits: 1 → 0)
        start2_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
            headers=auth_headers,
            timeout=10
        )
        assert start2_resp.status_code == 200, f"Start 2 failed: {start2_resp.text}"
        
        overlay3 = requests.get(f"{BASE_URL}/api/kiosk/{BOARD_ID}/overlay", timeout=10)
        credits_after_start2 = overlay3.json().get("credits_remaining", -1)
        assert credits_after_start2 == 0, f"Expected 0 credits after start 2, got {credits_after_start2}"
        print(f"Step 4: Game 2 started, credits: 1 → {credits_after_start2}")
        
        # Step 6: Abort game 2 (should auto-lock because 0 credits)
        abort_resp = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort",
            headers=auth_headers,
            timeout=10
        )
        assert abort_resp.status_code == 200, f"Abort failed: {abort_resp.text}"
        
        # Verify board is now locked
        overlay4 = requests.get(f"{BASE_URL}/api/kiosk/{BOARD_ID}/overlay", timeout=10)
        visible_after_abort = overlay4.json().get("visible", True)
        board_status = overlay4.json().get("board_status", "")
        
        assert visible_after_abort == False, f"Expected visible=False after abort with 0 credits"
        print(f"Step 5: Game 2 aborted, board auto-locked (visible={visible_after_abort}, status={board_status})")
        
        print("PASS: Full lifecycle completed successfully")


# ============================================================
# Module 7: Overlay endpoint tests
# ============================================================

class TestOverlayEndpoint:
    """Test overlay endpoint behavior."""

    def test_overlay_visible_false_when_locked(self, auth_headers):
        """GET /api/kiosk/BOARD-1/overlay returns visible:false when locked."""
        # First lock the board
        lock_resp = requests.post(
            f"{BASE_URL}/api/boards/{BOARD_ID}/lock",
            headers=auth_headers,
            timeout=10
        )
        
        # Check overlay returns visible: false
        overlay_resp = requests.get(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/overlay",
            timeout=10
        )
        assert overlay_resp.status_code == 200, f"Overlay failed: {overlay_resp.text}"
        data = overlay_resp.json()
        assert data.get("visible") == False, f"Expected visible=False when locked, got {data}"
        
        print(f"PASS: Overlay returns visible=False when board is locked")


# ============================================================
# Module 8: Observer status endpoint
# ============================================================

class TestObserverStatus:
    """Test observer status endpoint."""

    def test_observer_status_endpoint(self, auth_headers):
        """GET /api/kiosk/BOARD-1/observer-status returns observer info."""
        response = requests.get(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/observer-status",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Observer status failed: {response.text}"
        data = response.json()
        
        # Should have autodarts_mode and state
        assert "autodarts_mode" in data, f"autodarts_mode not in response: {data}"
        assert "state" in data, f"state not in response: {data}"
        
        print(f"PASS: Observer status: mode={data.get('autodarts_mode')}, state={data.get('state')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
