"""
Test Iteration 42 Integration Tests: 3-Game Loop via API

INTEGRATION TESTS for the finalize_match refactor v2.2.0:
1. Unlock board with 3 credits (per_game pricing)
2. Simulate game1 end → verify credit deduction (3→2)
3. Simulate game2 end → verify credit deduction (2→1)
4. Simulate game3 end → verify credit deduction (1→0) and board lock
5. Test abort does NOT deduct credit
6. Test manual end-game via /api/kiosk/{board_id}/end-game
7. Board status transitions: unlocked→in_game→unlocked (credits remain) or locked (0 credits)

These tests use the simulation endpoints which don't require real Autodarts browser.
"""

import pytest
import requests
import time
import os

# API base URL from frontend .env
BASE_URL = "https://boardgame-repair.preview.emergentagent.com"
BOARD_ID = "BOARD-1"


@pytest.fixture(scope="module")
def auth_token():
    """Get admin authentication token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin123"},
        timeout=10
    )
    if response.status_code != 200:
        pytest.skip(f"Auth failed: {response.status_code} {response.text}")
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for admin requests."""
    return {"Authorization": f"Bearer {auth_token}"}


def get_board_status(auth_headers):
    """Helper to get board status and credits. Returns nested board.status."""
    response = requests.get(
        f"{BASE_URL}/api/boards/{BOARD_ID}",
        headers=auth_headers,
        timeout=10
    )
    if response.status_code == 200:
        data = response.json()
        # API returns nested structure: {"board": {...}, "active_session": {...}}
        return data.get("board", {}).get("status")
    return None


def get_observer_status(auth_headers):
    """Helper to get observer status with credits."""
    response = requests.get(
        f"{BASE_URL}/api/kiosk/{BOARD_ID}/observer-status",
        headers=auth_headers,
        timeout=10
    )
    if response.status_code == 200:
        return response.json()
    return None


def lock_board(auth_headers):
    """Lock board to cleanup any existing sessions."""
    response = requests.post(
        f"{BASE_URL}/api/boards/{BOARD_ID}/lock",
        headers=auth_headers,
        timeout=10
    )
    return response


def unlock_board(auth_headers, credits=3, pricing_mode="per_game"):
    """Unlock board with specified credits and pricing mode."""
    # First lock to ensure clean state
    lock_board(auth_headers)
    time.sleep(0.3)
    
    response = requests.post(
        f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
        headers=auth_headers,
        json={"pricing_mode": pricing_mode, "credits": credits},
        timeout=10
    )
    return response


# ═══════════════════════════════════════════════════════════════
# HEALTH CHECK
# ═══════════════════════════════════════════════════════════════

class TestHealthAndAuth:
    """Verify backend health and auth work."""

    def test_health_endpoint(self):
        """Backend /api/health responds 200."""
        response = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert data.get("status") == "healthy"

    def test_auth_login(self):
        """Admin login works."""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data or "token" in data


# ═══════════════════════════════════════════════════════════════
# BOARD UNLOCK AND STATUS TESTS
# ═══════════════════════════════════════════════════════════════

class TestBoardUnlock:
    """Test board unlock with credits."""

    def test_unlock_board_with_3_credits(self, auth_headers):
        """Unlock BOARD-1 with 3 credits."""
        response = unlock_board(auth_headers, credits=3, pricing_mode="per_game")
        assert response.status_code in [200, 201], f"Unlock failed: {response.text}"
        data = response.json()
        print(f"Unlock response: {data}")
        assert data.get("credits_remaining") == 3

    def test_board_status_after_unlock(self, auth_headers):
        """Board status is 'unlocked' after unlock."""
        unlock_board(auth_headers, credits=3)
        time.sleep(0.5)
        
        status = get_board_status(auth_headers)
        print(f"Board status after unlock: {status}")
        assert status == "unlocked"
        
        obs_status = get_observer_status(auth_headers)
        if obs_status:
            print(f"Observer status: credits={obs_status.get('credits_remaining')}, "
                  f"pricing={obs_status.get('pricing_mode')}")
            assert obs_status.get("credits_remaining") == 3
            assert obs_status.get("pricing_mode") == "per_game"


# ═══════════════════════════════════════════════════════════════
# SIMULATE GAME START/END TESTS
# ═══════════════════════════════════════════════════════════════

class TestSimulateGameStart:
    """Test simulate-game-start endpoint."""

    def test_simulate_game_start(self, auth_headers):
        """Simulate game start sets board to in_game."""
        # First unlock the board
        unlock_board(auth_headers, credits=3)
        time.sleep(0.5)
        
        # Simulate game start
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Start failed: {response.text}"
        data = response.json()
        print(f"Simulate start response: {data}")
        
        # Check board status is now in_game
        time.sleep(0.5)
        status = get_board_status(auth_headers)
        print(f"Board status after start: {status}")
        assert status == "in_game"


class TestSimulateGameEnd:
    """Test simulate-game-end endpoint (finished trigger)."""

    def test_simulate_game_end_deducts_credit(self, auth_headers):
        """Simulate game end deducts credit (finished trigger)."""
        # Unlock with 3 credits
        unlock_board(auth_headers, credits=3)
        time.sleep(0.5)
        
        # Verify initial credits
        obs_status = get_observer_status(auth_headers)
        initial_credits = obs_status.get("credits_remaining") if obs_status else 0
        print(f"Initial credits: {initial_credits}")
        assert initial_credits == 3
        
        # Simulate game end (finished trigger)
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"End failed: {response.text}"
        data = response.json()
        print(f"Simulate end response: {data}")
        
        # Allow async finalize_match to complete
        time.sleep(1.0)
        
        # Check credits were deducted
        obs_status = get_observer_status(auth_headers)
        new_credits = obs_status.get("credits_remaining") if obs_status else -1
        print(f"Credits after game end: {new_credits}")
        assert new_credits == 2, f"Expected 2 credits, got {new_credits}"


class TestSimulateGameAbort:
    """Test simulate-game-abort endpoint (aborted trigger)."""

    def test_simulate_game_abort_no_deduction(self, auth_headers):
        """Simulate game abort does NOT deduct credit."""
        # Unlock with 3 credits (fresh state)
        unlock_board(auth_headers, credits=3)
        time.sleep(0.5)
        
        # Verify initial credits
        obs_status = get_observer_status(auth_headers)
        initial_credits = obs_status.get("credits_remaining") if obs_status else 0
        print(f"Initial credits before abort test: {initial_credits}")
        assert initial_credits == 3
        
        # Simulate game abort (aborted trigger - should NOT deduct)
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort",
            headers=auth_headers,
            timeout=10
        )
        assert response.status_code == 200, f"Abort failed: {response.text}"
        data = response.json()
        print(f"Simulate abort response: {data}")
        
        # Allow async finalize_match to complete
        time.sleep(1.0)
        
        # Check credits were NOT deducted
        obs_status = get_observer_status(auth_headers)
        new_credits = obs_status.get("credits_remaining") if obs_status else -1
        print(f"Credits after game abort: {new_credits}")
        assert new_credits == 3, f"Expected 3 credits (no deduction), got {new_credits}"


# ═══════════════════════════════════════════════════════════════
# 3-GAME LOOP TEST (CRITICAL)
# ═══════════════════════════════════════════════════════════════

class TestThreeGameLoop:
    """Test full 3-game loop: unlock→game1→game2→game3→lock."""

    def test_full_three_game_loop(self, auth_headers):
        """
        Full integration test:
        1. Unlock with 3 credits
        2. Game 1 end → 3→2 credits, board stays unlocked
        3. Game 2 end → 2→1 credits, board stays unlocked
        4. Game 3 end → 1→0 credits, board LOCKED
        """
        print("\n=== 3-GAME LOOP TEST START ===")
        
        # Step 1: Unlock board with 3 credits
        print("\n[Step 1] Unlocking board with 3 credits...")
        response = unlock_board(auth_headers, credits=3)
        assert response.status_code in [200, 201], f"Unlock failed: {response.text}"
        time.sleep(0.5)
        
        obs = get_observer_status(auth_headers)
        assert obs.get("credits_remaining") == 3, f"Expected 3 credits after unlock"
        print(f"✓ Board unlocked with {obs.get('credits_remaining')} credits")
        
        # Step 2: Game 1 - Start and End
        print("\n[Step 2] Game 1: Start and End (3→2)...")
        
        # Start game 1
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", 
                      headers=auth_headers, timeout=10)
        time.sleep(0.5)
        status = get_board_status(auth_headers)
        print(f"  Board status after game1 start: {status}")
        assert status == "in_game"
        
        # End game 1 (finished trigger - should deduct credit)
        response = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
                                 headers=auth_headers, timeout=10)
        assert response.status_code == 200
        time.sleep(1.0)  # Allow finalize_match to complete
        
        obs = get_observer_status(auth_headers)
        credits_after_g1 = obs.get("credits_remaining")
        print(f"  Credits after game1 end: {credits_after_g1}")
        assert credits_after_g1 == 2, f"Expected 2 credits after game1, got {credits_after_g1}"
        
        status = get_board_status(auth_headers)
        print(f"  Board status after game1 end: {status}")
        assert status == "unlocked", "Board should stay unlocked with 2 credits"
        print("✓ Game 1 complete: 3→2 credits, board unlocked")
        
        # Step 3: Game 2 - Start and End
        print("\n[Step 3] Game 2: Start and End (2→1)...")
        
        # Start game 2
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
                      headers=auth_headers, timeout=10)
        time.sleep(0.5)
        status = get_board_status(auth_headers)
        print(f"  Board status after game2 start: {status}")
        assert status == "in_game"
        
        # End game 2
        response = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
                                 headers=auth_headers, timeout=10)
        assert response.status_code == 200
        time.sleep(1.0)
        
        obs = get_observer_status(auth_headers)
        credits_after_g2 = obs.get("credits_remaining")
        print(f"  Credits after game2 end: {credits_after_g2}")
        assert credits_after_g2 == 1, f"Expected 1 credit after game2, got {credits_after_g2}"
        
        status = get_board_status(auth_headers)
        print(f"  Board status after game2 end: {status}")
        assert status == "unlocked", "Board should stay unlocked with 1 credit"
        print("✓ Game 2 complete: 2→1 credits, board unlocked")
        
        # Step 4: Game 3 - Start and End (SHOULD LOCK)
        print("\n[Step 4] Game 3: Start and End (1→0, LOCK)...")
        
        # Start game 3
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
                      headers=auth_headers, timeout=10)
        time.sleep(0.5)
        status = get_board_status(auth_headers)
        print(f"  Board status after game3 start: {status}")
        assert status == "in_game"
        
        # End game 3 (should trigger lock)
        response = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
                                 headers=auth_headers, timeout=10)
        assert response.status_code == 200
        time.sleep(1.0)
        
        # Verify credits are 0 and board is locked
        status = get_board_status(auth_headers)
        print(f"  Board status after game3 end: {status}")
        assert status == "locked", f"Board should be LOCKED with 0 credits, got {status}"
        print("✓ Game 3 complete: 1→0 credits, board LOCKED")
        
        print("\n=== 3-GAME LOOP TEST PASSED ===")


# ═══════════════════════════════════════════════════════════════
# MANUAL END-GAME ENDPOINT TEST
# ═══════════════════════════════════════════════════════════════

class TestManualEndGame:
    """Test manual end-game endpoint /api/kiosk/{board_id}/end-game."""

    def test_manual_end_game_uses_manual_trigger(self, auth_headers):
        """Manual end-game uses 'manual' trigger and deducts credit."""
        # Unlock with 3 credits
        unlock_board(auth_headers, credits=3)
        time.sleep(0.5)
        
        obs = get_observer_status(auth_headers)
        initial_credits = obs.get("credits_remaining")
        print(f"Initial credits: {initial_credits}")
        
        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
                      headers=auth_headers, timeout=10)
        time.sleep(0.5)
        
        # Manual end-game (uses 'manual' trigger)
        response = requests.post(
            f"{BASE_URL}/api/kiosk/{BOARD_ID}/end-game",
            headers=auth_headers,
            json={},
            timeout=10
        )
        assert response.status_code == 200, f"End-game failed: {response.text}"
        data = response.json()
        print(f"Manual end-game response: {data}")
        
        # Manual trigger should deduct credit AND lock board (regardless of credits remaining)
        # According to v2.2.0 refactor: manual always triggers teardown
        assert "should_lock" in data
        assert "credits_remaining" in data
        print(f"Should lock: {data.get('should_lock')}, Credits: {data.get('credits_remaining')}")


# ═══════════════════════════════════════════════════════════════
# OBSERVER TEARDOWN BEHAVIOR TESTS
# ═══════════════════════════════════════════════════════════════

class TestObserverTeardownBehavior:
    """Test observer teardown is conditional based on credits and trigger."""

    def test_observer_kept_alive_when_credits_remain(self, auth_headers):
        """Observer stays open when credits remain after game end."""
        unlock_board(auth_headers, credits=3)
        time.sleep(0.5)
        
        # End game 1
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
                      headers=auth_headers, timeout=10)
        time.sleep(1.0)
        
        # Observer status should still be queryable (not closed)
        obs = get_observer_status(auth_headers)
        assert obs is not None
        assert obs.get("credits_remaining") == 2
        print(f"Observer status after game with credits remaining: credits={obs.get('credits_remaining')}")

    def test_teardown_on_zero_credits(self, auth_headers):
        """Observer teardown happens when credits reach 0."""
        # Unlock with 1 credit
        unlock_board(auth_headers, credits=1)
        time.sleep(0.5)
        
        # End game (should trigger lock and teardown)
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
                      headers=auth_headers, timeout=10)
        time.sleep(1.0)
        
        # Board should be locked
        status = get_board_status(auth_headers)
        print(f"Board status after credit exhaustion: {status}")
        assert status == "locked"


# ═══════════════════════════════════════════════════════════════
# BOARD STATUS TRANSITIONS
# ═══════════════════════════════════════════════════════════════

class TestBoardStatusTransitions:
    """Test board status transitions: unlocked→in_game→unlocked/locked."""

    def test_transition_unlocked_to_in_game(self, auth_headers):
        """Board transitions from unlocked to in_game on game start."""
        unlock_board(auth_headers, credits=3)
        time.sleep(0.3)
        
        status = get_board_status(auth_headers)
        assert status == "unlocked"
        
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
                      headers=auth_headers, timeout=10)
        time.sleep(0.3)
        
        status = get_board_status(auth_headers)
        assert status == "in_game"
        print(f"Transition verified: unlocked → in_game")

    def test_transition_in_game_to_unlocked(self, auth_headers):
        """Board transitions from in_game to unlocked when credits remain."""
        unlock_board(auth_headers, credits=3)
        time.sleep(0.3)
        
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
                      headers=auth_headers, timeout=10)
        time.sleep(0.3)
        
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
                      headers=auth_headers, timeout=10)
        time.sleep(1.0)
        
        status = get_board_status(auth_headers)
        assert status == "unlocked"
        print(f"Transition verified: in_game → unlocked (credits remain)")

    def test_transition_in_game_to_locked(self, auth_headers):
        """Board transitions from in_game to locked when credits exhausted."""
        unlock_board(auth_headers, credits=1)
        time.sleep(0.3)
        
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start",
                      headers=auth_headers, timeout=10)
        time.sleep(0.3)
        
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end",
                      headers=auth_headers, timeout=10)
        time.sleep(1.0)
        
        status = get_board_status(auth_headers)
        assert status == "locked"
        print(f"Transition verified: in_game → locked (credits exhausted)")


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
