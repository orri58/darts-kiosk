"""
Autodarts DOM Selector Tests
Validates that the CSS selectors used by the observer service
match the expected DOM structure on the Autodarts website.

These tests can be run without Playwright — they test the selector
patterns against synthetic HTML fragments that mirror the real DOM.
Run with: pytest backend/tests/test_autodarts_selectors.py -v
"""
import re
import pytest

# ===== Selector patterns from autodarts_observer.py =====
# These are the exact JS selectors used in _detect_state()

IN_GAME_SELECTORS = [
    '[class*="match"]',
    '[class*="scoreboard"]',
    '[data-testid*="match"]',
    '#match',
]

IN_GAME_SECONDARY = [
    '[class*="dart-input"]',
    '[class*="throw"]',
    '[class*="scoring"]',
    '[class*="game-view"]',
]

FINISHED_SELECTORS = [
    '[class*="winner"]',
    '[class*="result"]',
    '[class*="game-over"]',
    '[class*="match-end"]',
    '[class*="finished"]',
]

FINISHED_SECONDARY = [
    '[class*="post-match"]',
    '[class*="match-stats"]',
    '[class*="game-result"]',
]


# ===== Helper: simulate CSS attribute selector matching =====

def matches_attr_contains(selector: str, html_attrs: dict) -> bool:
    """Check if a CSS selector like [class*="match"] matches given HTML attributes."""
    # [class*="value"]
    m = re.match(r'\[(\w+)\*="([^"]+)"\]', selector)
    if m:
        attr, value = m.groups()
        attr_val = html_attrs.get(attr, "")
        return value in attr_val

    # [attr="value"]
    m = re.match(r'\[(\w+)="([^"]+)"\]', selector)
    if m:
        attr, value = m.groups()
        return html_attrs.get(attr, "") == value

    # #id
    if selector.startswith('#'):
        return html_attrs.get('id', '') == selector[1:]

    return False


# ===== Synthetic DOM fragments =====
# These represent the expected DOM state on Autodarts

IDLE_PAGE_ATTRS = [
    {"class": "lobby-container", "id": "lobby"},
    {"class": "board-selector"},
    {"class": "game-setup-panel"},
]

IN_GAME_PAGE_ATTRS = [
    {"class": "match-container active-match", "id": "match"},
    {"class": "scoreboard-panel"},
    {"class": "dart-input-area"},
    {"class": "throw-display current-throw"},
    {"data-testid": "match-view"},
]

FINISHED_PAGE_ATTRS = [
    {"class": "match-end-screen"},
    {"class": "winner-display"},
    {"class": "game-result-summary"},
    {"class": "post-match-stats"},
    {"class": "match-stats-table"},
]


# ===== Tests =====

class TestInGameDetection:
    """Test that in-game selectors correctly match active game DOM."""

    def test_primary_selectors_match_game_dom(self):
        """At least one primary selector should match the in-game DOM."""
        matched = []
        for selector in IN_GAME_SELECTORS:
            for attrs in IN_GAME_PAGE_ATTRS:
                if matches_attr_contains(selector, attrs):
                    matched.append((selector, attrs))
        assert len(matched) > 0, (
            f"No primary in-game selector matched. "
            f"Selectors: {IN_GAME_SELECTORS}"
        )

    def test_secondary_selectors_match_game_dom(self):
        """At least one secondary selector should match the in-game DOM."""
        matched = []
        for selector in IN_GAME_SECONDARY:
            for attrs in IN_GAME_PAGE_ATTRS:
                if matches_attr_contains(selector, attrs):
                    matched.append((selector, attrs))
        assert len(matched) > 0, (
            f"No secondary in-game selector matched. "
            f"Selectors: {IN_GAME_SECONDARY}"
        )

    def test_in_game_selectors_do_not_match_idle(self):
        """In-game selectors should NOT match the idle/lobby DOM."""
        false_positives = []
        for selector in IN_GAME_SELECTORS:
            for attrs in IDLE_PAGE_ATTRS:
                if matches_attr_contains(selector, attrs):
                    false_positives.append((selector, attrs))
        assert len(false_positives) == 0, (
            f"In-game selectors incorrectly matched idle DOM: {false_positives}"
        )


class TestFinishedDetection:
    """Test that finished selectors correctly match post-game DOM."""

    def test_primary_selectors_match_finished_dom(self):
        """At least one primary finished selector should match."""
        matched = []
        for selector in FINISHED_SELECTORS:
            for attrs in FINISHED_PAGE_ATTRS:
                if matches_attr_contains(selector, attrs):
                    matched.append((selector, attrs))
        assert len(matched) > 0, (
            f"No primary finished selector matched. "
            f"Selectors: {FINISHED_SELECTORS}"
        )

    def test_secondary_selectors_match_finished_dom(self):
        """At least one secondary finished selector should match."""
        matched = []
        for selector in FINISHED_SECONDARY:
            for attrs in FINISHED_PAGE_ATTRS:
                if matches_attr_contains(selector, attrs):
                    matched.append((selector, attrs))
        assert len(matched) > 0, (
            f"No secondary finished selector matched. "
            f"Selectors: {FINISHED_SECONDARY}"
        )

    def test_finished_selectors_do_not_match_idle(self):
        """Finished selectors should NOT match idle DOM."""
        false_positives = []
        for selector in FINISHED_SELECTORS:
            for attrs in IDLE_PAGE_ATTRS:
                if matches_attr_contains(selector, attrs):
                    false_positives.append((selector, attrs))
        assert len(false_positives) == 0, (
            f"Finished selectors incorrectly matched idle DOM: {false_positives}"
        )


class TestStateTransitions:
    """Test that state detection logic follows expected transitions."""

    def _detect_state(self, page_attrs):
        """Simulate the _detect_state logic from autodarts_observer.py."""
        in_game = False
        for selector in IN_GAME_SELECTORS + IN_GAME_SECONDARY:
            for attrs in page_attrs:
                if matches_attr_contains(selector, attrs):
                    in_game = True
                    break
            if in_game:
                break

        finished = False
        for selector in FINISHED_SELECTORS + FINISHED_SECONDARY:
            for attrs in page_attrs:
                if matches_attr_contains(selector, attrs):
                    finished = True
                    break
            if finished:
                break

        # finished takes priority (same as observer)
        if finished:
            return "finished"
        if in_game:
            return "in_game"
        return "idle"

    def test_idle_page_detected_as_idle(self):
        assert self._detect_state(IDLE_PAGE_ATTRS) == "idle"

    def test_in_game_page_detected_as_in_game(self):
        assert self._detect_state(IN_GAME_PAGE_ATTRS) == "in_game"

    def test_finished_page_detected_as_finished(self):
        assert self._detect_state(FINISHED_PAGE_ATTRS) == "finished"

    def test_empty_page_detected_as_idle(self):
        assert self._detect_state([{"class": "app-root"}]) == "idle"


class TestSelectorCoverage:
    """Ensure all selector groups have minimum coverage."""

    def test_in_game_has_minimum_selectors(self):
        """In-game detection should have at least 3 selectors."""
        total = len(IN_GAME_SELECTORS) + len(IN_GAME_SECONDARY)
        assert total >= 3, f"Only {total} in-game selectors defined"

    def test_finished_has_minimum_selectors(self):
        """Finished detection should have at least 3 selectors."""
        total = len(FINISHED_SELECTORS) + len(FINISHED_SECONDARY)
        assert total >= 3, f"Only {total} finished selectors defined"

    def test_no_duplicate_selectors(self):
        """No selector should appear in both in-game and finished groups."""
        in_game_set = set(IN_GAME_SELECTORS + IN_GAME_SECONDARY)
        finished_set = set(FINISHED_SELECTORS + FINISHED_SECONDARY)
        overlap = in_game_set & finished_set
        assert len(overlap) == 0, f"Overlapping selectors: {overlap}"
