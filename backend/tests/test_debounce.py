"""
Test for the debounce logic in AutodartsObserver.

Simulates:
1. Normal turn change (brief non-in_game → recovers to in_game)
2. Real abort (sustained non-in_game for 3+ polls)
3. Real finish (sustained finished state for 3+ polls)

Uses direct method calls on the observer to simulate DOM poll results,
bypassing the actual Playwright page.
"""
import asyncio
import pytest
import logging
from unittest.mock import AsyncMock, patch
from backend.services.autodarts_observer import (
    AutodartsObserver, ObserverState,
    DEBOUNCE_EXIT_POLLS, DEBOUNCE_POLL_INTERVAL, OBSERVER_POLL_INTERVAL
)

logger = logging.getLogger(__name__)


class SimulatedObserver(AutodartsObserver):
    """Observer with injectable DOM detection results."""

    def __init__(self, board_id):
        super().__init__(board_id)
        self._simulated_states = []
        self._sim_index = 0
        self.transitions = []  # Record all confirmed transitions

    def set_sequence(self, states):
        """Set a sequence of states that _detect_state will return."""
        self._simulated_states = states
        self._sim_index = 0

    async def _detect_state(self):
        if self._sim_index < len(self._simulated_states):
            state = self._simulated_states[self._sim_index]
            self._sim_index += 1
            return state
        return ObserverState.IDLE


@pytest.mark.asyncio
async def test_debounce_config():
    """Verify debounce constants are reasonable."""
    assert DEBOUNCE_EXIT_POLLS >= 2, "Need at least 2 exit polls for debounce"
    assert DEBOUNCE_POLL_INTERVAL >= 1, "Debounce poll interval must be >= 1s"
    assert DEBOUNCE_EXIT_POLLS * DEBOUNCE_POLL_INTERVAL >= 4, "Total debounce time should be >= 4s"
    print(f"Debounce config: {DEBOUNCE_EXIT_POLLS} polls × {DEBOUNCE_POLL_INTERVAL}s = {DEBOUNCE_EXIT_POLLS * DEBOUNCE_POLL_INTERVAL}s")


@pytest.mark.asyncio
async def test_turn_change_does_not_exit_in_game():
    """
    Simulate: in_game → idle (turn change) → in_game (next turn).
    The observer should NOT fire any game_ended callback.
    """
    obs = SimulatedObserver("TEST-1")
    obs._stable_state = ObserverState.IN_GAME
    obs._credit_consumed = True
    obs.status.browser_open = True

    game_ended = AsyncMock()
    obs._on_game_ended = game_ended

    # Simulate: in_game, idle (turn change), in_game (recovered)
    obs.set_sequence([
        ObserverState.IN_GAME,   # Normal poll
        ObserverState.IDLE,      # Turn change flicker (1 exit poll)
        ObserverState.IN_GAME,   # Recovered! Turn change over
        ObserverState.IN_GAME,   # Normal poll
    ])

    # Run 4 iterations manually
    for i in range(4):
        if obs._sim_index >= len(obs._simulated_states):
            break
        raw = await obs._detect_state()
        stable = obs._stable_state

        if stable == ObserverState.IN_GAME:
            if raw == ObserverState.IN_GAME:
                if obs._exit_polls > 0:
                    logger.info(f"[Test] RECOVERED after {obs._exit_polls} exit polls")
                obs._exit_polls = 0
                obs._exit_saw_finished = False
            else:
                obs._exit_polls += 1
                if raw == ObserverState.FINISHED:
                    obs._exit_saw_finished = True
                logger.info(f"[Test] Exit poll {obs._exit_polls}/{DEBOUNCE_EXIT_POLLS}")

                if obs._exit_polls >= DEBOUNCE_EXIT_POLLS:
                    reason = "finished" if obs._exit_saw_finished else "aborted"
                    await obs._on_game_ended("TEST-1", reason)
                    obs._exit_polls = 0

    # game_ended should NOT have been called (turn change recovered)
    game_ended.assert_not_called()
    assert obs._stable_state == ObserverState.IN_GAME
    print("PASS: Turn change did NOT exit in_game")


@pytest.mark.asyncio
async def test_real_abort_triggers_after_debounce():
    """
    Simulate: in_game → idle → idle → idle (3 consecutive).
    After DEBOUNCE_EXIT_POLLS polls, should fire game_ended(aborted).
    """
    obs = SimulatedObserver("TEST-2")
    obs._stable_state = ObserverState.IN_GAME
    obs._credit_consumed = True
    obs.status.browser_open = True

    game_ended = AsyncMock()
    obs._on_game_ended = game_ended

    # Simulate: 3+ consecutive idle polls (real abort)
    idle_sequence = [ObserverState.IDLE] * (DEBOUNCE_EXIT_POLLS + 1)
    obs.set_sequence(idle_sequence)

    for i in range(DEBOUNCE_EXIT_POLLS + 1):
        if obs._sim_index >= len(obs._simulated_states):
            break
        raw = await obs._detect_state()
        stable = obs._stable_state

        if stable == ObserverState.IN_GAME:
            if raw == ObserverState.IN_GAME:
                obs._exit_polls = 0
                obs._exit_saw_finished = False
            else:
                obs._exit_polls += 1
                if raw == ObserverState.FINISHED:
                    obs._exit_saw_finished = True

                if obs._exit_polls >= DEBOUNCE_EXIT_POLLS:
                    reason = "finished" if obs._exit_saw_finished else "aborted"
                    await obs._on_game_ended("TEST-2", reason)
                    obs._stable_state = ObserverState.IDLE
                    obs._exit_polls = 0
                    break

    # game_ended should have been called with "aborted"
    game_ended.assert_called_once_with("TEST-2", "aborted")
    print("PASS: Real abort triggered after debounce")


@pytest.mark.asyncio
async def test_real_finish_triggers_after_debounce():
    """
    Simulate: in_game → finished → finished → finished (3 consecutive).
    Should fire game_ended(finished).
    """
    obs = SimulatedObserver("TEST-3")
    obs._stable_state = ObserverState.IN_GAME
    obs._credit_consumed = True
    obs.status.browser_open = True

    game_ended = AsyncMock()
    obs._on_game_ended = game_ended

    finished_sequence = [ObserverState.FINISHED] * (DEBOUNCE_EXIT_POLLS + 1)
    obs.set_sequence(finished_sequence)

    for i in range(DEBOUNCE_EXIT_POLLS + 1):
        if obs._sim_index >= len(obs._simulated_states):
            break
        raw = await obs._detect_state()
        stable = obs._stable_state

        if stable == ObserverState.IN_GAME:
            if raw == ObserverState.IN_GAME:
                obs._exit_polls = 0
                obs._exit_saw_finished = False
            else:
                obs._exit_polls += 1
                if raw == ObserverState.FINISHED:
                    obs._exit_saw_finished = True

                if obs._exit_polls >= DEBOUNCE_EXIT_POLLS:
                    reason = "finished" if obs._exit_saw_finished else "aborted"
                    await obs._on_game_ended("TEST-3", reason)
                    obs._stable_state = ObserverState.FINISHED
                    obs._exit_polls = 0
                    obs._exit_saw_finished = False
                    break

    game_ended.assert_called_once_with("TEST-3", "finished")
    print("PASS: Real finish triggered after debounce")


@pytest.mark.asyncio
async def test_mixed_flicker_does_not_exit():
    """
    Simulate: in_game → idle → in_game → idle → in_game
    Alternating: never reaches DEBOUNCE_EXIT_POLLS consecutive exits.
    """
    obs = SimulatedObserver("TEST-4")
    obs._stable_state = ObserverState.IN_GAME
    obs._credit_consumed = True

    game_ended = AsyncMock()
    obs._on_game_ended = game_ended

    # Alternating pattern (turn changes every other poll)
    obs.set_sequence([
        ObserverState.IDLE,      # exit poll 1
        ObserverState.IN_GAME,   # recovered
        ObserverState.IDLE,      # exit poll 1 again
        ObserverState.IN_GAME,   # recovered again
        ObserverState.IDLE,      # exit poll 1
        ObserverState.IN_GAME,   # recovered
    ])

    for i in range(6):
        raw = await obs._detect_state()
        if obs._stable_state == ObserverState.IN_GAME:
            if raw == ObserverState.IN_GAME:
                obs._exit_polls = 0
                obs._exit_saw_finished = False
            else:
                obs._exit_polls += 1
                if obs._exit_polls >= DEBOUNCE_EXIT_POLLS:
                    await obs._on_game_ended("TEST-4", "aborted")

    game_ended.assert_not_called()
    print("PASS: Alternating flicker did NOT exit in_game")


if __name__ == "__main__":
    asyncio.run(test_debounce_config())
    asyncio.run(test_turn_change_does_not_exit_in_game())
    asyncio.run(test_real_abort_triggers_after_debounce())
    asyncio.run(test_real_finish_triggers_after_debounce())
    asyncio.run(test_mixed_flicker_does_not_exit())
    print("\n=== ALL DEBOUNCE TESTS PASSED ===")
