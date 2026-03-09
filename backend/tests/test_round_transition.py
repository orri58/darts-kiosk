"""
Test for the Three-Tier state detection and ROUND_TRANSITION handling.

Validates that:
1. Normal turn/round changes (ROUND_TRANSITION) do NOT trigger session end
2. Only strong match-end markers (FINISHED) trigger session end after debounce
3. ROUND_TRANSITION resets the exit debounce counter
4. Abort (sustained IDLE) still works correctly
5. Mixed sequences (turn changes interspersed with real end) work correctly
6. Credit consumption happens only on first IN_GAME detection
"""
import asyncio
import pytest
import logging
from unittest.mock import AsyncMock
from backend.services.autodarts_observer import (
    AutodartsObserver, ObserverState,
    DEBOUNCE_EXIT_POLLS,
)

logger = logging.getLogger(__name__)


class SimulatedObserver(AutodartsObserver):
    """Observer with injectable DOM detection results for testing."""

    def __init__(self, board_id):
        super().__init__(board_id)
        self._simulated_states = []
        self._sim_index = 0

    def set_sequence(self, states):
        self._simulated_states = states
        self._sim_index = 0

    async def _detect_state(self):
        if self._sim_index < len(self._simulated_states):
            state = self._simulated_states[self._sim_index]
            self._sim_index += 1
            return state
        return ObserverState.IDLE


def _make_observer(board_id="TEST", stable=ObserverState.IN_GAME):
    """Create a SimulatedObserver pre-set to a stable state."""
    obs = SimulatedObserver(board_id)
    obs._stable_state = stable
    obs._credit_consumed = True
    obs.status.browser_open = True
    obs._on_game_ended = AsyncMock()
    obs._on_game_started = AsyncMock()
    return obs


async def _run_loop_iterations(obs, count):
    """
    Manually execute the observe loop logic for N iterations.
    Replicates the exact logic from _observe_loop without async sleep.
    """
    for _ in range(count):
        if obs._sim_index >= len(obs._simulated_states):
            break

        raw = await obs._detect_state()
        stable = obs._stable_state

        if stable == ObserverState.IN_GAME:
            if raw == ObserverState.IN_GAME:
                if obs._exit_polls > 0:
                    obs._exit_polls = 0
                    obs._exit_saw_finished = False
                continue

            if raw == ObserverState.ROUND_TRANSITION:
                if obs._exit_polls > 0:
                    obs._exit_polls = 0
                    obs._exit_saw_finished = False
                continue

            # IDLE or FINISHED: real exit candidate
            obs._exit_polls += 1
            if raw == ObserverState.FINISHED:
                obs._exit_saw_finished = True

            if obs._exit_polls >= DEBOUNCE_EXIT_POLLS:
                reason = "finished" if obs._exit_saw_finished else "aborted"
                confirmed = ObserverState.FINISHED if obs._exit_saw_finished else raw
                obs._stable_state = confirmed
                obs._exit_polls = 0
                obs._exit_saw_finished = False
                if obs._on_game_ended:
                    await obs._on_game_ended(obs.board_id, reason)
                obs._credit_consumed = False

        else:
            effective_raw = raw
            if raw == ObserverState.ROUND_TRANSITION:
                effective_raw = ObserverState.IDLE

            if effective_raw == stable:
                continue

            if effective_raw == ObserverState.IN_GAME:
                obs._stable_state = ObserverState.IN_GAME
                obs._credit_consumed = True
                obs._exit_polls = 0
                obs._exit_saw_finished = False
                obs.status.games_observed += 1
                if obs._on_game_started:
                    await obs._on_game_started(obs.board_id)

            elif stable == ObserverState.FINISHED and effective_raw == ObserverState.IDLE:
                obs._stable_state = ObserverState.IDLE
                if obs._on_game_ended:
                    await obs._on_game_ended(obs.board_id, "post_finish_check")
            else:
                obs._stable_state = effective_raw


# ===================================================================
# TEST 1: Round transition does NOT end session
# ===================================================================

@pytest.mark.asyncio
async def test_round_transition_does_not_end_session():
    """
    Scenario: Player finishes a 3-dart turn. Autodarts shows a brief
    result screen (generic result markers) before the next turn starts.
    Expected: ROUND_TRANSITION detected, session continues, no lock.
    """
    obs = _make_observer()
    obs.set_sequence([
        ObserverState.IN_GAME,           # Normal play
        ObserverState.ROUND_TRANSITION,  # Turn result screen
        ObserverState.ROUND_TRANSITION,  # Still showing result
        ObserverState.IN_GAME,           # Next turn starts
        ObserverState.IN_GAME,           # Normal play
    ])

    await _run_loop_iterations(obs, 5)

    obs._on_game_ended.assert_not_called()
    assert obs._stable_state == ObserverState.IN_GAME
    assert obs._exit_polls == 0
    print("PASS: Round transition does NOT end session")


# ===================================================================
# TEST 2: Round transition resets debounce counter
# ===================================================================

@pytest.mark.asyncio
async def test_round_transition_resets_exit_debounce():
    """
    Scenario: During a turn change, one IDLE poll sneaks in, then a
    ROUND_TRANSITION appears. The ROUND_TRANSITION must reset the
    exit counter, preventing premature lock.
    """
    obs = _make_observer()
    obs.set_sequence([
        ObserverState.IN_GAME,           # Normal play
        ObserverState.IDLE,              # Brief IDLE flicker (exit_polls=1)
        ObserverState.ROUND_TRANSITION,  # Turn result → resets counter!
        ObserverState.IDLE,              # Another IDLE (exit_polls=1 again, not 2)
        ObserverState.IN_GAME,           # Recovered
    ])

    await _run_loop_iterations(obs, 5)

    obs._on_game_ended.assert_not_called()
    assert obs._stable_state == ObserverState.IN_GAME
    print("PASS: ROUND_TRANSITION resets exit debounce counter")


# ===================================================================
# TEST 3: Real match finish (strong markers) triggers session end
# ===================================================================

@pytest.mark.asyncio
async def test_real_match_finish_triggers_end():
    """
    Scenario: Match truly ends. Strong markers (Rematch/Share buttons)
    are detected as FINISHED for DEBOUNCE_EXIT_POLLS consecutive polls.
    Expected: Session ends with reason="finished".
    """
    obs = _make_observer()
    sequence = [ObserverState.IN_GAME]
    sequence += [ObserverState.FINISHED] * (DEBOUNCE_EXIT_POLLS + 1)
    obs.set_sequence(sequence)

    await _run_loop_iterations(obs, len(sequence))

    obs._on_game_ended.assert_called_once_with(obs.board_id, "finished")
    assert obs._stable_state == ObserverState.FINISHED
    print("PASS: Real match finish triggers session end")


# ===================================================================
# TEST 4: Abort (sustained IDLE) triggers session end
# ===================================================================

@pytest.mark.asyncio
async def test_abort_sustained_idle_triggers_end():
    """
    Scenario: Player aborts mid-game, returning to lobby.
    Sustained IDLE without any game markers.
    Expected: Session ends with reason="aborted".
    """
    obs = _make_observer()
    sequence = [ObserverState.IN_GAME]
    sequence += [ObserverState.IDLE] * (DEBOUNCE_EXIT_POLLS + 1)
    obs.set_sequence(sequence)

    await _run_loop_iterations(obs, len(sequence))

    obs._on_game_ended.assert_called_once_with(obs.board_id, "aborted")
    assert obs._stable_state == ObserverState.IDLE
    print("PASS: Abort (sustained IDLE) triggers session end")


# ===================================================================
# TEST 5: Multiple round transitions during a full match
# ===================================================================

@pytest.mark.asyncio
async def test_multiple_round_transitions_no_exit():
    """
    Scenario: Full match with 3 turns/rounds, each showing a
    ROUND_TRANSITION screen. None should trigger a session end.
    """
    obs = _make_observer()
    obs.set_sequence([
        ObserverState.IN_GAME,           # Turn 1 play
        ObserverState.IN_GAME,
        ObserverState.ROUND_TRANSITION,  # Turn 1 result
        ObserverState.IN_GAME,           # Turn 2 play
        ObserverState.IN_GAME,
        ObserverState.ROUND_TRANSITION,  # Turn 2 result
        ObserverState.ROUND_TRANSITION,  # Still showing
        ObserverState.IN_GAME,           # Turn 3 play
        ObserverState.IN_GAME,
        ObserverState.ROUND_TRANSITION,  # Turn 3 result
        ObserverState.IN_GAME,           # Continue
    ])

    await _run_loop_iterations(obs, 11)

    obs._on_game_ended.assert_not_called()
    assert obs._stable_state == ObserverState.IN_GAME
    print("PASS: Multiple round transitions do not exit")


# ===================================================================
# TEST 6: Round transition → then real match end
# ===================================================================

@pytest.mark.asyncio
async def test_round_transition_then_real_match_end():
    """
    Scenario: Normal turn change (ROUND_TRANSITION), then the match
    actually ends (FINISHED with strong markers).
    Expected: Only the real match end triggers session end.
    """
    obs = _make_observer()
    sequence = [
        ObserverState.IN_GAME,
        ObserverState.ROUND_TRANSITION,  # Turn change
        ObserverState.IN_GAME,           # Next turn
        ObserverState.IN_GAME,
    ]
    # Now the match really ends
    sequence += [ObserverState.FINISHED] * (DEBOUNCE_EXIT_POLLS + 1)
    obs.set_sequence(sequence)

    await _run_loop_iterations(obs, len(sequence))

    obs._on_game_ended.assert_called_once_with(obs.board_id, "finished")
    assert obs._stable_state == ObserverState.FINISHED
    print("PASS: Round transition then real match end works correctly")


# ===================================================================
# TEST 7: ROUND_TRANSITION interleaved with IDLE does not reach debounce
# ===================================================================

@pytest.mark.asyncio
async def test_round_transition_interleaved_with_idle():
    """
    Scenario: IDLE (exit_polls=1), ROUND_TRANSITION (resets to 0),
    IDLE (exit_polls=1 again), ROUND_TRANSITION (resets to 0).
    Never reaches DEBOUNCE_EXIT_POLLS.
    """
    obs = _make_observer()
    obs.set_sequence([
        ObserverState.IDLE,              # exit_polls=1
        ObserverState.ROUND_TRANSITION,  # reset to 0
        ObserverState.IDLE,              # exit_polls=1
        ObserverState.ROUND_TRANSITION,  # reset to 0
        ObserverState.IDLE,              # exit_polls=1
        ObserverState.ROUND_TRANSITION,  # reset to 0
        ObserverState.IN_GAME,           # back to game
    ])

    await _run_loop_iterations(obs, 7)

    obs._on_game_ended.assert_not_called()
    assert obs._stable_state == ObserverState.IN_GAME
    print("PASS: ROUND_TRANSITION interleaved with IDLE prevents false exit")


# ===================================================================
# TEST 8: ROUND_TRANSITION outside IN_GAME is treated as IDLE
# ===================================================================

@pytest.mark.asyncio
async def test_round_transition_outside_in_game_is_idle():
    """
    Scenario: Stable state is IDLE. A ROUND_TRANSITION is detected.
    Should be treated as IDLE (no state change).
    """
    obs = _make_observer(stable=ObserverState.IDLE)
    obs.set_sequence([
        ObserverState.ROUND_TRANSITION,  # Should be treated as IDLE
        ObserverState.ROUND_TRANSITION,  # Still IDLE
    ])

    await _run_loop_iterations(obs, 2)

    obs._on_game_ended.assert_not_called()
    obs._on_game_started.assert_not_called()
    assert obs._stable_state == ObserverState.IDLE
    print("PASS: ROUND_TRANSITION outside IN_GAME treated as IDLE")


# ===================================================================
# TEST 9: Game start (idle -> in_game) still immediate
# ===================================================================

@pytest.mark.asyncio
async def test_game_start_still_immediate():
    """
    Verify that entering IN_GAME from IDLE is still immediate
    (no debounce, credit consumed).
    """
    obs = _make_observer(stable=ObserverState.IDLE)
    obs._credit_consumed = False
    obs.set_sequence([
        ObserverState.IN_GAME,  # Should trigger immediately
    ])

    await _run_loop_iterations(obs, 1)

    obs._on_game_started.assert_called_once_with(obs.board_id)
    assert obs._stable_state == ObserverState.IN_GAME
    assert obs._credit_consumed is True
    assert obs.status.games_observed == 1
    print("PASS: Game start is still immediate")


# ===================================================================
# TEST 10: FINISHED → IDLE triggers post_finish_check
# ===================================================================

@pytest.mark.asyncio
async def test_finished_to_idle_post_finish_check():
    """
    After match ends (FINISHED), returning to IDLE should trigger
    post_finish_check callback.
    """
    obs = _make_observer(stable=ObserverState.FINISHED)
    obs.set_sequence([
        ObserverState.IDLE,  # Result screen dismissed
    ])

    await _run_loop_iterations(obs, 1)

    obs._on_game_ended.assert_called_once_with(obs.board_id, "post_finish_check")
    assert obs._stable_state == ObserverState.IDLE
    print("PASS: FINISHED → IDLE triggers post_finish_check")


# ===================================================================
# Run all tests directly
# ===================================================================

if __name__ == "__main__":
    tests = [
        test_round_transition_does_not_end_session,
        test_round_transition_resets_exit_debounce,
        test_real_match_finish_triggers_end,
        test_abort_sustained_idle_triggers_end,
        test_multiple_round_transitions_no_exit,
        test_round_transition_then_real_match_end,
        test_round_transition_interleaved_with_idle,
        test_round_transition_outside_in_game_is_idle,
        test_game_start_still_immediate,
        test_finished_to_idle_post_finish_check,
    ]
    for test in tests:
        asyncio.run(test())
    print(f"\n=== ALL {len(tests)} ROUND TRANSITION TESTS PASSED ===")
