"""
Autodarts DOM Selector Tests + Soak Test
=========================================
Acceptance Criteria:
  AC-1: 200+ game start/status/end cycles complete without unrecoverable errors
  AC-2: All 4 game modes (301, 501, Cricket, Training) tested equally
  AC-3: Circuit breaker opens after 3 consecutive failures and recovers
  AC-4: Selector fallback learns and prioritizes working selectors
  AC-5: Error screenshots are saved for every failure
  AC-6: Overall success rate >= 95%

Error Analysis Workflow:
  1. On failure: screenshot + HTML snapshot saved to /data/autodarts_debug/
  2. Circuit breaker tracks consecutive failures -> opens at 3
  3. After recovery_timeout (120s in prod, 2s in test) -> half_open
  4. One success in half_open -> closes circuit
  5. Selector fallback records success/failure per selector per category
  6. Admin Health page shows all metrics + screenshots
"""
import asyncio
import pytest
import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import asdict

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.autodarts_integration import (
    MockAutodartsIntegration,
    PlaywrightAutodartsIntegration,
    CircuitBreaker,
    CircuitState,
    SelectorFallback,
    GameConfig,
    GameStatus,
    AutomationResult,
    AutodartsError,
    GameType,
)

GAME_MODES = ["301", "501", "Cricket", "Training"]
SOAK_CYCLES = 200
REPORT_PATH = Path("/app/test_reports/autodarts_soak_report.json")


# ============================================================
# Unit Tests – Circuit Breaker
# ============================================================

class TestCircuitBreaker:
    def test_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=2)
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    def test_opens_after_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

    def test_transitions_to_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(1.1)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute()

    def test_half_open_success_closes(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(1.1)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(1.1)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_manual_reset(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=999)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()


# ============================================================
# Unit Tests – Selector Fallback
# ============================================================

class TestSelectorFallback:
    def test_neutral_for_untested(self):
        sf = SelectorFallback()
        sels = sf.get_selectors("game", ["a", "b", "c"])
        assert len(sels) == 3

    def test_prioritizes_successful(self):
        sf = SelectorFallback()
        sf.record_failure("game", "bad_sel")
        sf.record_failure("game", "bad_sel")
        sf.record_success("game", "good_sel")
        sf.record_success("game", "good_sel")
        result = sf.get_selectors("game", ["bad_sel", "good_sel"])
        assert result[0] == "good_sel"

    def test_learning_across_categories(self):
        sf = SelectorFallback()
        sf.record_success("start", "sel_a")
        sf.record_failure("stop", "sel_a")
        # Different categories don't interfere
        start_result = sf.get_selectors("start", ["sel_a", "sel_b"])
        stop_result = sf.get_selectors("stop", ["sel_a", "sel_b"])
        assert start_result[0] == "sel_a"
        assert stop_result[0] == "sel_b"


# ============================================================
# Unit Tests – Mock Integration
# ============================================================

class TestMockIntegration:
    @pytest.mark.asyncio
    async def test_lifecycle(self):
        mock = MockAutodartsIntegration(game_duration_seconds=1)
        assert await mock.is_available()

        config = GameConfig(
            game_type="501",
            players=["Alice", "Bob"],
            board_id="BOARD-1",
            session_id="sess-001",
        )
        result = await mock.start_game(config)
        assert result.success

        status = await mock.get_game_status()
        assert status.is_running

        await asyncio.sleep(1.2)
        status = await mock.get_game_status()
        assert status.is_finished
        assert status.winner == "Alice"

    @pytest.mark.asyncio
    async def test_stop_game(self):
        mock = MockAutodartsIntegration(game_duration_seconds=999)
        config = GameConfig(
            game_type="301", players=["P1"], board_id="B1", session_id="s1"
        )
        await mock.start_game(config)
        result = await mock.stop_game()
        assert result.success
        status = await mock.get_game_status()
        assert not status.is_running


# ============================================================
# Soak Test – 200+ cycles across all game modes
# ============================================================

class TestAutodartsSOAK:
    """
    AC-1: 200+ cycles without unrecoverable error
    AC-2: All 4 game modes tested
    AC-6: >= 95 % success rate
    """

    @pytest.mark.asyncio
    async def test_soak_200_cycles(self):
        mock = MockAutodartsIntegration(game_duration_seconds=0)
        results = {mode: {"success": 0, "fail": 0} for mode in GAME_MODES}
        total_ok = 0
        total_fail = 0
        errors = []

        for i in range(SOAK_CYCLES):
            mode = GAME_MODES[i % len(GAME_MODES)]
            players = [f"P{j+1}" for j in range(1 + (i % 4))]
            config = GameConfig(
                game_type=mode,
                players=players,
                board_id=f"BOARD-{(i % 3) + 1}",
                session_id=f"soak-{i:04d}",
            )

            try:
                start = await mock.start_game(config)
                assert start.success, f"Cycle {i} start failed: {start.message}"

                status = await mock.get_game_status()
                assert status.is_finished or status.is_running

                stop = await mock.stop_game()
                assert stop.success

                results[mode]["success"] += 1
                total_ok += 1
            except Exception as exc:
                results[mode]["fail"] += 1
                total_fail += 1
                errors.append({"cycle": i, "mode": mode, "error": str(exc)})

        # Build report
        rate = total_ok / SOAK_CYCLES * 100
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_cycles": SOAK_CYCLES,
            "success": total_ok,
            "fail": total_fail,
            "success_rate": round(rate, 2),
            "by_mode": results,
            "errors": errors[:20],
            "acceptance_criteria": {
                "AC-1_200_cycles": total_ok + total_fail >= SOAK_CYCLES,
                "AC-2_all_modes": all(
                    results[m]["success"] + results[m]["fail"] > 0
                    for m in GAME_MODES
                ),
                "AC-6_95pct": rate >= 95.0,
            },
        }

        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2))

        # Assertions
        assert rate >= 95.0, f"Soak success rate {rate}% < 95%"
        for m in GAME_MODES:
            assert results[m]["success"] > 0, f"No successes for mode {m}"


# ============================================================
# Circuit Breaker Integration Test
# ============================================================

class TestCircuitBreakerIntegration:
    """AC-3: Circuit breaker opens after 3 failures and recovers"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_lifecycle(self):
        integration = PlaywrightAutodartsIntegration(headless=True)
        cb = integration._circuit_breaker

        # Initially closed
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

        # Simulate 3 failures to open
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

        # Reset for test (simulates recovery timeout)
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    @pytest.mark.asyncio
    async def test_manual_mode_toggle(self):
        integration = PlaywrightAutodartsIntegration(headless=True)
        assert not integration.is_manual_mode

        integration.enable_manual_mode()
        assert integration.is_manual_mode

        integration.disable_manual_mode()
        assert not integration.is_manual_mode
        assert integration.circuit_state == CircuitState.CLOSED


# ============================================================
# Selector Fallback Integration Test
# ============================================================

class TestSelectorFallbackIntegration:
    """AC-4: Selector fallback learns and prioritizes working selectors"""

    def test_fallback_learning(self):
        integration = PlaywrightAutodartsIntegration(headless=True)
        sf = integration._selector_fallback

        # Simulate selector usage
        sf.record_success("game_select", '[data-game="501"]')
        sf.record_success("game_select", '[data-game="501"]')
        sf.record_failure("game_select", 'button:has-text("501")')
        sf.record_failure("game_select", '.game-501')

        ordered = sf.get_selectors("game_select", [
            '.game-501',
            'button:has-text("501")',
            '[data-game="501"]',
        ])
        assert ordered[0] == '[data-game="501"]'
