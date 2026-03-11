"""
Test Iteration 43: Integration Tests for Finalize Match v2.3.0

Covers all 15 features from the test requirements:
1. _should_deduct_credit('match_end_gameshot_match') returns True
2. _should_deduct_credit('match_end_state_finished') returns True
3. _should_deduct_credit('aborted') returns False
4. Full 3-game loop: unlock(3) → game1(3→2, no teardown) → game2(2→1, no teardown) → game3(1→0, teardown+lock)
5. Abort does NOT deduct credit
6. _finalized blocks duplicate finish signals (second simulate-game-end returns credits=-1)
7. Manual stop bypasses _finalized guard and locks board
8. simulate-game-end returns should_teardown field
9. _on_game_ended has NO asyncio.create_task (source inspection)
10. close_session has self-call detection (is_self_call in source)
11. _cleanup logs PAGE_CLOSE_DONE, CONTEXT_CLOSE_DONE, PLAYWRIGHT_STOP_DONE
12. Observer _finalized is reset in open_session
13. Observe loop has READY_FOR_NEXT_GAME log
14. post_finish_check is NOT in observe loop
15. Backend /api/health responds 200
"""

import pytest
import requests
import inspect
import sys
import os

sys.path.insert(0, '/app')

BASE_URL = "https://boardgame-repair.preview.emergentagent.com"
BOARD_ID = "BOARD-1"


@pytest.fixture(scope="module")
def admin_token():
    """Get admin authentication token."""
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "username": "admin",
        "password": "admin123"
    }, timeout=10)
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    """Get headers with admin authentication."""
    return {"Authorization": f"Bearer {admin_token}"}


def reset_board(admin_headers):
    """Helper to lock the board (reset state)."""
    requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/lock", headers=admin_headers, timeout=10)


class TestFeature1_ShouldDeductCreditMatchEndGameshot:
    """Feature 1: _should_deduct_credit('match_end_gameshot_match') returns True"""

    def test_match_end_gameshot_match_deducts(self):
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("match_end_gameshot_match") is True


class TestFeature2_ShouldDeductCreditMatchEndStateFinished:
    """Feature 2: _should_deduct_credit('match_end_state_finished') returns True"""

    def test_match_end_state_finished_deducts(self):
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("match_end_state_finished") is True


class TestFeature3_AbortedDoesNotDeduct:
    """Feature 3: _should_deduct_credit('aborted') returns False"""

    def test_aborted_free(self):
        from backend.routers.kiosk import _should_deduct_credit
        assert _should_deduct_credit("aborted") is False


class TestFeature4_Full3GameLoop:
    """Feature 4: Full 3-game loop: unlock(3) → game1(3→2) → game2(2→1) → game3(1→0, teardown+lock)"""

    def test_3_game_loop_with_credits(self, admin_headers):
        # Step 0: Lock board to reset state
        reset_board(admin_headers)

        # Step 1: Unlock board with 3 credits
        r = requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                          headers=admin_headers,
                          json={"pricing_mode": "per_game", "credits": 3},
                          timeout=10)
        assert r.status_code == 200, f"Unlock failed: {r.text}"

        # Verify board unlocked and 3 credits
        r = requests.get(f"{BASE_URL}/api/boards/{BOARD_ID}", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["active_session"]["credits_remaining"] == 3
        assert data["board"]["status"] == "unlocked"

        # Step 2: Game 1 - start and end (3→2, no teardown)
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["credits_remaining"] == 2, f"Expected credits=2, got {data['credits_remaining']}"
        assert data["should_teardown"] is False, "Game 1 should NOT teardown (credits=2)"

        # Step 3: Game 2 - start and end (2→1, no teardown)
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["credits_remaining"] == 1, f"Expected credits=1, got {data['credits_remaining']}"
        assert data["should_teardown"] is False, "Game 2 should NOT teardown (credits=1)"

        # Step 4: Game 3 - start and end (1→0, teardown+lock)
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["credits_remaining"] == 0, f"Expected credits=0, got {data['credits_remaining']}"
        assert data["should_teardown"] is True, "Game 3 should TEARDOWN (credits=0)"
        assert data["should_lock"] is True, "Game 3 should LOCK board"

        # Verify board is locked
        r = requests.get(f"{BASE_URL}/api/boards/{BOARD_ID}", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["board"]["status"] == "locked"


class TestFeature5_AbortDoesNotDeductCredit:
    """Feature 5: Abort does NOT deduct credit"""

    def test_abort_no_deduction(self, admin_headers):
        # Reset and unlock with 3 credits
        reset_board(admin_headers)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                      headers=admin_headers,
                      json={"pricing_mode": "per_game", "credits": 3},
                      timeout=10)

        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)

        # Abort the game
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-abort", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()

        # Credits should remain at 3 (no deduction for abort)
        assert data["credits_remaining"] == 3, f"Abort should NOT deduct credit, got {data['credits_remaining']}"


class TestFeature6_FinalizedBlocksDuplicateFinish:
    """Feature 6: _finalized blocks duplicate finish signals (second simulate-game-end returns credits=-1)"""

    def test_finalized_blocks_duplicate(self, admin_headers):
        # Reset and unlock with 3 credits
        reset_board(admin_headers)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                      headers=admin_headers,
                      json={"pricing_mode": "per_game", "credits": 3},
                      timeout=10)

        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)

        # First finish - should deduct (3→2)
        r1 = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end", headers=admin_headers, timeout=10)
        assert r1.status_code == 200
        data1 = r1.json()
        assert data1["credits_remaining"] == 2

        # Second finish WITHOUT simulate-game-start - should be blocked by _finalized
        r2 = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end", headers=admin_headers, timeout=10)
        assert r2.status_code == 200
        data2 = r2.json()
        # _finalized guard returns credits=-1 when blocked
        assert data2["credits_remaining"] == -1, f"Second finish should be blocked, got credits={data2['credits_remaining']}"


class TestFeature7_ManualBypassesFinalizedGuard:
    """Feature 7: Manual stop bypasses _finalized guard and locks board"""

    def test_manual_bypasses_finalized(self, admin_headers):
        # Reset and unlock with 3 credits
        reset_board(admin_headers)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                      headers=admin_headers,
                      json={"pricing_mode": "per_game", "credits": 3},
                      timeout=10)

        # Start a game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)

        # First finish
        r1 = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end", headers=admin_headers, timeout=10)
        assert r1.status_code == 200

        # Manual end-game should bypass _finalized guard
        r2 = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/end-game", headers=admin_headers, timeout=10)
        assert r2.status_code == 200
        data2 = r2.json()

        # Manual SHOULD work even after finalize (bypasses _finalized)
        # and should lock the board
        assert data2.get("should_lock") is True, "Manual should LOCK the board"

    def test_manual_bypasses_finalized_source(self):
        """Verify 'manual' trigger bypasses in source code."""
        from backend.routers.kiosk import finalize_match
        source = inspect.getsource(finalize_match)
        assert 'trigger != "manual"' in source, "Manual trigger must bypass _finalized guard in source"


class TestFeature8_SimulateGameEndReturnsShouldTeardown:
    """Feature 8: simulate-game-end returns should_teardown field"""

    def test_simulate_game_end_returns_should_teardown(self, admin_headers):
        # Reset and unlock with 1 credit
        reset_board(admin_headers)
        requests.post(f"{BASE_URL}/api/boards/{BOARD_ID}/unlock",
                      headers=admin_headers,
                      json={"pricing_mode": "per_game", "credits": 1},
                      timeout=10)

        # Start and end game
        requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-start", headers=admin_headers, timeout=10)
        r = requests.post(f"{BASE_URL}/api/kiosk/{BOARD_ID}/simulate-game-end", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        data = r.json()

        assert "should_teardown" in data, f"Response should contain should_teardown field: {data}"
        assert data["should_teardown"] is True, "With 1 credit, should_teardown should be True"


class TestFeature9_OnGameEndedNoCreateTask:
    """Feature 9: _on_game_ended has NO asyncio.create_task (source inspection)"""

    def test_no_create_task_in_on_game_ended(self):
        from backend.routers.kiosk import _on_game_ended
        source = inspect.getsource(_on_game_ended)
        assert "asyncio.create_task" not in source, \
            "_on_game_ended must NOT use asyncio.create_task (synchronous finalize)"

    def test_awaits_finalize_match(self):
        from backend.routers.kiosk import _on_game_ended
        source = inspect.getsource(_on_game_ended)
        assert "await finalize_match" in source, \
            "_on_game_ended must directly await finalize_match"


class TestFeature10_CloseSessionSelfCallDetection:
    """Feature 10: close_session has self-call detection (is_self_call in source)"""

    def test_has_current_task_check(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.close_session)
        assert "current_task" in source, "close_session must check asyncio.current_task()"
        assert "is_self_call" in source, "close_session must have is_self_call variable"

    def test_skips_cancel_on_self_call(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.close_session)
        assert "self-call detected" in source, "close_session must log self-call detection"


class TestFeature11_CleanupStepByStepLogging:
    """Feature 11: _cleanup logs PAGE_CLOSE_DONE, CONTEXT_CLOSE_DONE, PLAYWRIGHT_STOP_DONE"""

    def test_page_close_done(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._cleanup)
        assert "PAGE_CLOSE_DONE" in source

    def test_context_close_done(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._cleanup)
        assert "CONTEXT_CLOSE_DONE" in source

    def test_playwright_stop_done(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._cleanup)
        assert "PLAYWRIGHT_STOP_DONE" in source


class TestFeature12_ObserverFinalizedResetInOpenSession:
    """Feature 12: Observer _finalized is reset in open_session"""

    def test_observer_finalized_reset_in_open_session(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver.open_session)
        assert "_finalized = False" in source, "open_session must reset _finalized flag"


class TestFeature13_ObserveLoopReadyForNextGame:
    """Feature 13: Observe loop has READY_FOR_NEXT_GAME log"""

    def test_ready_for_next_game_log(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "READY_FOR_NEXT_GAME" in source, "Observe loop must log READY_FOR_NEXT_GAME"


class TestFeature14_PostFinishCheckNotInObserveLoop:
    """Feature 14: post_finish_check is NOT in observe loop"""

    def test_no_post_finish_check(self):
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "post_finish_check" not in source, "post_finish_check should NOT be in observe loop"


class TestFeature15_BackendHealthResponds200:
    """Feature 15: Backend /api/health responds 200"""

    def test_health_endpoint(self):
        r = requests.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"


class TestAdditionalRegressionChecks:
    """Additional regression tests from v2.3.0 requirements."""

    def test_finalized_dict_exists_in_kiosk(self):
        """_finalized dict exists at module level in kiosk.py"""
        from backend.routers import kiosk
        assert hasattr(kiosk, '_finalized')
        assert isinstance(kiosk._finalized, dict)

    def test_should_deduct_credit_handles_all_match_end_triggers(self):
        """All match_end_* triggers should deduct credit.
        Note: match_finished_matchshot is a WS classification type, not a trigger.
        Only match_end_* prefixed triggers are passed to _should_deduct_credit.
        """
        from backend.routers.kiosk import _should_deduct_credit
        # These are the actual triggers that would be passed to _should_deduct_credit
        triggers = [
            "match_end_gameshot_match",
            "match_end_state_finished",
            "match_end_game_finished",
        ]
        for trigger in triggers:
            result = _should_deduct_credit(trigger)
            assert result is True, f"Trigger {trigger} should deduct credit, got {result}"
        
        # Non match_end_* triggers should return False
        assert _should_deduct_credit("match_finished_matchshot") is False, \
            "match_finished_matchshot is not a match_end_* trigger"

    def test_finished_idle_does_not_retrigger_finalization(self):
        """FINISHED→IDLE transition does NOT call on_game_ended."""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        lines = source.split('\n')
        in_block = False
        block_lines = []
        for line in lines:
            if 'result dismissed' in line.lower():
                in_block = True
            if in_block:
                block_lines.append(line)
                if line.strip().startswith(('elif ', 'else:')):
                    break
        block_text = '\n'.join(block_lines)
        assert "on_game_ended" not in block_text, "FINISHED→IDLE should NOT call on_game_ended"

    def test_observe_loop_breaks_after_finalize_teardown(self):
        """After finalize sets _stopping=True, observe loop should break."""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "_stopping=True after finalize" in source

    def test_stop_reason_is_finalize_teardown(self):
        """Stop reason should be 'finalize_teardown' when finalize caused the stop."""
        from backend.services.autodarts_observer import AutodartsObserver
        source = inspect.getsource(AutodartsObserver._observe_loop)
        assert "finalize_teardown" in source


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
