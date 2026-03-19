"""
Autodarts DOM Selector & Frame Classification Test Suite v3.3.5
================================================================

Tests three layers of the Observer's detection mechanism:
  1. Selector integrity (definitions well-formed)
  2. WS frame classification (unit tests, no network)
  3. DOM selector fallback resolution (mock HTML, validates resolveGroup logic)
  4. Heuristic combination (multi-evidence detection)
  5. Live page probe (optional, skipped on network failure)
  6. Gotcha variant guard

Run:  pytest backend/tests/test_autodarts_dom_selectors.py -v
Live: AUTODARTS_LIVE=1 pytest ... -v
"""
import os
import re
import sys
import json
import logging
import pytest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.autodarts_selectors import (
    SELECTOR_GROUPS,
    IN_GAME_SELECTORS,
    STRONG_MATCH_END_SELECTORS,
    MATCH_END_BUTTON_PATTERNS,
    GENERIC_RESULT_SELECTORS,
    LOGIN_URL_PATTERNS,
    WS_MATCH_START_EVENTS,
    WS_MATCH_END_GAMESHOT_EVENTS,
    WS_MATCH_END_STATE_FIELDS,
    WS_MATCH_END_KEYWORD,
    WS_MATCH_RESET_EVENT,
    WS_CHANNEL_PATTERNS,
    AUTODARTS_BASE_URL,
    build_detect_state_js,
)

logger = logging.getLogger(__name__)
LIVE_TESTS = os.environ.get("AUTODARTS_LIVE", "0") == "1"


# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def browser_context():
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
    context = browser.new_context()
    yield context
    context.close()
    browser.close()
    pw.stop()


@pytest.fixture
def page(browser_context):
    p = browser_context.new_page()
    yield p
    p.close()


def _detect(page, html_body: str) -> dict:
    """Inject mock HTML and run the canonical detection JS."""
    page.set_content(f"<html><body>{html_body}</body></html>")
    js = build_detect_state_js()
    return page.evaluate(js)


# ═══════════════════════════════════════════════════════════════
# PART 1: SELECTOR DEFINITION INTEGRITY
# ═══════════════════════════════════════════════════════════════

class TestSelectorIntegrity:

    def test_selector_groups_structure(self):
        assert isinstance(SELECTOR_GROUPS, dict)
        for group_name, selectors in SELECTOR_GROUPS.items():
            assert isinstance(selectors, list), f"{group_name} is not a list"
            assert len(selectors) >= 1, f"{group_name} is empty"
            for s in selectors:
                assert "css" in s, f"{group_name}: missing 'css' in {s}"
                assert "name" in s, f"{group_name}: missing 'name' in {s}"
                assert "priority" in s, f"{group_name}: missing 'priority' in {s}"
                assert s["priority"] in ("primary", "fallback"), \
                    f"{group_name}/{s['name']}: invalid priority '{s['priority']}'"

    def test_each_group_has_primary(self):
        for group_name, selectors in SELECTOR_GROUPS.items():
            primaries = [s for s in selectors if s["priority"] == "primary"]
            assert len(primaries) >= 1, f"{group_name}: no primary selector"

    def test_primary_is_first(self):
        for group_name, selectors in SELECTOR_GROUPS.items():
            assert selectors[0]["priority"] == "primary", \
                f"{group_name}: first selector should be primary, got '{selectors[0]['priority']}'"

    def test_flat_lists_derived_correctly(self):
        assert len(IN_GAME_SELECTORS) >= 5
        assert len(STRONG_MATCH_END_SELECTORS) >= 3
        assert len(GENERIC_RESULT_SELECTORS) >= 3

    def test_all_selectors_have_required_fields(self):
        for group_name, selectors in [
            ("in_game", IN_GAME_SELECTORS),
            ("strong_match_end", STRONG_MATCH_END_SELECTORS),
            ("generic_result", GENERIC_RESULT_SELECTORS),
        ]:
            for s in selectors:
                assert "name" in s and "css" in s, f"{group_name}: incomplete {s}"
                assert s["css"].strip(), f"{group_name}/{s['name']}: empty CSS"

    def test_button_patterns_compile(self):
        for bp in MATCH_END_BUTTON_PATTERNS:
            try:
                re.compile(bp["pattern"], re.IGNORECASE)
            except re.error as e:
                pytest.fail(f"Invalid regex {bp['name']}: {e}")

    def test_ws_channel_patterns_compile(self):
        for cp in WS_CHANNEL_PATTERNS:
            try:
                re.compile(cp["pattern"])
            except re.error as e:
                pytest.fail(f"Invalid regex {cp['name']}: {e}")

    def test_no_duplicate_selector_names_within_groups(self):
        for group_name, selectors in SELECTOR_GROUPS.items():
            names = [s["name"] for s in selectors]
            dupes = [n for n in names if names.count(n) > 1]
            assert not dupes, f"{group_name}: duplicate names {set(dupes)}"

    def test_build_detect_state_js_generates_valid_js(self):
        js = build_detect_state_js()
        assert "resolveGroup" in js
        assert "evidence" in js
        assert "_groups" in js


# ═══════════════════════════════════════════════════════════════
# PART 2: WS FRAME CLASSIFICATION (UNIT TESTS)
# ═══════════════════════════════════════════════════════════════

class TestWSFrameClassification:

    @pytest.fixture(autouse=True)
    def setup(self):
        from backend.services.autodarts_observer import AutodartsObserver, WSEventState
        self.obs = AutodartsObserver.__new__(AutodartsObserver)
        self.obs.board_id = "TEST-BOARD"
        self.obs._ws_state = WSEventState()
        self.obs._last_finalized_match_id = None

    def test_turn_start(self):
        r = self.obs._classify_frame('{"event":"turn_start"}', "autodarts.matches.123.game-events", {"event": "turn_start"})
        assert r == "match_start_turn_start"

    def test_throw(self):
        r = self.obs._classify_frame('{"event":"throw"}', "autodarts.matches.123.game-events", {"event": "throw"})
        assert r == "match_start_throw"

    def test_game_shot_match(self):
        p = {"event": "game_shot", "body": {"type": "match"}}
        r = self.obs._classify_frame(json.dumps(p), "autodarts.matches.123.game-events", p)
        assert r == "match_end_gameshot_match"

    def test_game_shot_leg(self):
        p = {"event": "game_shot", "body": {"type": "leg"}}
        r = self.obs._classify_frame(json.dumps(p), "autodarts.matches.123.game-events", p)
        assert r == "round_transition_gameshot"

    def test_finished_true(self):
        p = {"finished": True}
        r = self.obs._classify_frame(json.dumps(p), "autodarts.matches.123.state", p)
        assert r == "match_end_state_finished"

    def test_game_finished_true(self):
        p = {"gameFinished": True}
        r = self.obs._classify_frame(json.dumps(p), "autodarts.matches.123.state", p)
        assert r == "match_end_game_finished"

    def test_matchshot_keyword(self):
        raw = '{"data":"matchshot detected"}'
        r = self.obs._classify_frame(raw, "autodarts.matches.abc.game-events", {"data": "matchshot detected"})
        assert r == "match_finished_matchshot"

    def test_delete_event(self):
        p = {"event": "delete"}
        r = self.obs._classify_frame(json.dumps(p), "autodarts.matches.123.state", p)
        assert r == "match_reset_delete"

    def test_irrelevant(self):
        r = self.obs._classify_frame('{"heartbeat":true}', "system.heartbeat", {"heartbeat": True})
        assert r == "irrelevant"

    def test_subscription(self):
        r = self.obs._classify_frame('{"action":"subscribe"}', "autodarts.boards.xyz.state", {"action": "subscribe"})
        assert r == "subscription"


# ═══════════════════════════════════════════════════════════════
# PART 3: DOM FALLBACK RESOLUTION (v3.3.5)
# ═══════════════════════════════════════════════════════════════

class TestFallbackResolution:
    """Test that the resolveGroup pattern correctly selects primary vs fallback."""

    def test_primary_selector_used_when_present(self, page):
        """When primary selector matches, it should be reported as primary."""
        html = '<div class="scoreboard-main">501</div>'  # matches primary of in_game_score
        signals = _detect(page, html)
        grp = signals["_groups"]["in_game_score"]
        assert grp["found"], "in_game_score should be found"
        assert grp["priority"] == "primary", f"Expected primary, got {grp['priority']}"
        assert grp["name"] == "scoreboard"

    def test_fallback_used_when_primary_missing(self, page):
        """When primary is absent but fallback exists, fallback should be used."""
        # No 'scoreboard' class, but has 'player-score' (fallback)
        html = '<div class="player-score-display">301</div>'
        signals = _detect(page, html)
        grp = signals["_groups"]["in_game_score"]
        assert grp["found"], "in_game_score should be found via fallback"
        assert grp["priority"] == "fallback", f"Expected fallback, got {grp['priority']}"
        assert grp["name"] == "player_score"

    def test_second_fallback_used(self, page):
        """When primary and first fallback are absent, second fallback works."""
        # Only 'scoring' class (third in in_game_score group)
        html = '<div class="scoring-panel">Points</div>'
        signals = _detect(page, html)
        grp = signals["_groups"]["in_game_score"]
        assert grp["found"]
        assert grp["priority"] == "fallback"
        assert grp["name"] == "scoring"

    def test_soft_fail_when_all_selectors_missing(self, page):
        """When no selectors match, group reports found=false (no crash)."""
        html = '<div class="unrelated-content">Hello</div>'
        signals = _detect(page, html)
        grp = signals["_groups"]["in_game_score"]
        assert not grp["found"], "Should report not-found"
        assert grp["priority"] is None
        assert grp["name"] is None

    def test_all_groups_soft_fail_on_empty_page(self, page):
        """Empty page: all groups return found=false, no crash."""
        signals = _detect(page, "<div>empty</div>")
        for group_name, info in signals["_groups"].items():
            assert not info["found"], f"{group_name} should not match on empty page"
        assert not signals["inGame"]
        assert not signals["strongMatchEnd"]
        assert not signals["hasGenericResult"]

    def test_finished_ui_primary_hit(self, page):
        """post-match (primary) in finished_ui group."""
        html = '<div class="post-match-screen">Results</div>'
        signals = _detect(page, html)
        grp = signals["_groups"]["finished_ui"]
        assert grp["found"]
        assert grp["priority"] == "primary"
        assert grp["name"] == "post_match"
        assert signals["strongMatchEnd"]

    def test_finished_ui_fallback_hit(self, page):
        """match-summary (fallback) when post-match is absent."""
        html = '<div class="match-summary-panel">Stats</div>'
        signals = _detect(page, html)
        grp = signals["_groups"]["finished_ui"]
        assert grp["found"]
        assert grp["priority"] == "fallback"
        assert grp["name"] == "match_summary"

    def test_result_generic_primary_hit(self, page):
        """match-result (primary) in result_generic group."""
        html = '<div class="match-result-card">Winner: P1</div>'
        signals = _detect(page, html)
        grp = signals["_groups"]["result_generic"]
        assert grp["found"]
        assert grp["priority"] == "primary"

    def test_result_generic_fallback_hit(self, page):
        """winner (fallback) when match-result is absent."""
        html = '<div class="winner-display">Player 1</div>'
        signals = _detect(page, html)
        grp = signals["_groups"]["result_generic"]
        assert grp["found"]
        assert grp["priority"] == "fallback"
        assert grp["name"] == "winner"


# ═══════════════════════════════════════════════════════════════
# PART 4: HEURISTIC COMBINATION
# ═══════════════════════════════════════════════════════════════

class TestHeuristicCombination:
    """Test multi-evidence detection for stronger confidence."""

    def test_in_game_single_evidence(self, page):
        html = '<div class="scoreboard-x">501</div>'
        signals = _detect(page, html)
        assert signals["inGame"]
        assert signals["_evidenceCount"] == 1
        assert "score" in signals["_evidence"]

    def test_in_game_multi_evidence(self, page):
        """Multiple in-game signals → higher confidence."""
        html = '''
        <div class="scoreboard-main">501</div>
        <div class="match-view-active">Game</div>
        <div class="turn-indicator">P1</div>
        '''
        signals = _detect(page, html)
        assert signals["inGame"]
        assert signals["_evidenceCount"] == 3
        assert "score" in signals["_evidence"]
        assert "match" in signals["_evidence"]
        assert "turn" in signals["_evidence"]

    def test_in_game_two_evidence(self, page):
        html = '''
        <div class="player-score-box">180</div>
        <div class="throw-area">Dart 3</div>
        '''
        signals = _detect(page, html)
        assert signals["inGame"]
        assert signals["_evidenceCount"] == 2
        assert "score" in signals["_evidence"]
        assert "turn" in signals["_evidence"]

    def test_finished_ui_plus_button(self, page):
        """Finished UI + rematch button → strong match end."""
        html = '''
        <div class="match-end-overlay">Game Over</div>
        <button>Play Again</button>
        '''
        signals = _detect(page, html)
        assert signals["strongMatchEnd"]
        assert signals["hasPostMatchUI"]
        assert signals["hasRematchBtn"]

    def test_button_only_without_ui(self, page):
        """Button alone triggers strongMatchEnd even without post-match UI."""
        html = '<button class="btn-action">Rematch</button>'
        signals = _detect(page, html)
        assert signals["strongMatchEnd"]
        assert signals["hasRematchBtn"]
        assert not signals["hasPostMatchUI"]


# ═══════════════════════════════════════════════════════════════
# PART 5: CSS SELECTOR SYNTAX VALIDATION
# ═══════════════════════════════════════════════════════════════

class TestCSSSelectorsValid:

    def _test_selector(self, page, css, name):
        page.set_content("<html><body><div>x</div></body></html>")
        try:
            page.evaluate(f'document.querySelectorAll({json.dumps(css)})')
        except Exception as e:
            pytest.fail(
                f"CSS SYNTAX ERROR: name={name} selector={css} "
                f"error={e} ts={datetime.now(timezone.utc).isoformat()}"
            )

    def test_all_group_selectors_valid(self, page):
        for group_name, selectors in SELECTOR_GROUPS.items():
            for s in selectors:
                self._test_selector(page, s["css"], f"{group_name}/{s['name']}")

    def test_all_flat_selectors_valid(self, page):
        for s in IN_GAME_SELECTORS + STRONG_MATCH_END_SELECTORS + GENERIC_RESULT_SELECTORS:
            self._test_selector(page, s["css"], s["name"])


# ═══════════════════════════════════════════════════════════════
# PART 6: EXISTING DOM DETECTION (backward compat)
# ═══════════════════════════════════════════════════════════════

class TestDOMDetectionBackwardCompat:
    """Ensure the canonical JS produces identical results to the old inline JS."""

    def test_idle_empty(self, page):
        signals = _detect(page, "<div>Welcome</div>")
        assert not signals["inGame"]
        assert not signals["strongMatchEnd"]
        assert not signals["hasGenericResult"]

    def test_in_game_scoreboard(self, page):
        signals = _detect(page, '<div class="ad-scoreboard main">501</div>')
        assert signals["inGame"]

    def test_in_game_match_id(self, page):
        signals = _detect(page, '<div id="match">Active</div>')
        assert signals["inGame"]

    def test_finished_german_button(self, page):
        signals = _detect(page, '<button>Nochmal spielen</button>')
        assert signals["strongMatchEnd"]

    def test_finished_share_button(self, page):
        signals = _detect(page, '<button class="share-btn">Ergebnis teilen</button>')
        assert signals["strongMatchEnd"]

    def test_result_winner(self, page):
        signals = _detect(page, '<div class="winner-highlight">P1 wins</div>')
        assert signals["hasGenericResult"]

    def test_no_false_positive(self, page):
        html = '<nav class="main-menu"><a>Profile</a></nav><div class="lobby">Welcome</div>'
        signals = _detect(page, html)
        assert not signals["inGame"]
        assert not signals["strongMatchEnd"]


# ═══════════════════════════════════════════════════════════════
# PART 7: LIVE PAGE PROBE (OPTIONAL)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.skipif(not LIVE_TESTS, reason="AUTODARTS_LIVE=1 not set")
class TestLivePageProbe:

    def test_page_loads(self, page):
        try:
            resp = page.goto(AUTODARTS_BASE_URL, timeout=15000, wait_until="domcontentloaded")
            assert resp and resp.status < 500
        except Exception as e:
            if "net::" in str(e) or "timeout" in str(e).lower():
                pytest.skip(f"Network issue: {e}")
            raise

    def test_login_redirect(self, page):
        try:
            page.goto(AUTODARTS_BASE_URL, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            assert any(p in page.url.lower() for p in LOGIN_URL_PATTERNS)
        except Exception as e:
            if "net::" in str(e) or "timeout" in str(e).lower():
                pytest.skip(f"Network issue: {e}")
            raise

    def test_page_has_basic_dom(self, page):
        try:
            page.goto(AUTODARTS_BASE_URL, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            assert page.query_selector("body") is not None
            assert len(page.content()) > 200
        except Exception as e:
            if "net::" in str(e) or "timeout" in str(e).lower():
                pytest.skip(f"Network issue: {e}")
            raise


# ═══════════════════════════════════════════════════════════════
# PART 8: GOTCHA VARIANT GUARD
# ═══════════════════════════════════════════════════════════════

class TestGotchaVariantGuard:

    @pytest.fixture(autouse=True)
    def setup(self):
        from backend.services.autodarts_observer import AutodartsObserver, WSEventState
        self.obs = AutodartsObserver.__new__(AutodartsObserver)
        self.obs.board_id = "GOTCHA-TEST"
        self.obs._ws_state = WSEventState()
        self.obs._last_finalized_match_id = None

    def test_is_gotcha_positive(self):
        self.obs._ws_state.variant = "Gotcha"
        assert self.obs._is_gotcha()

    def test_is_gotcha_case_insensitive(self):
        self.obs._ws_state.variant = "gotcha 301"
        assert self.obs._is_gotcha()

    def test_is_gotcha_negative_501(self):
        self.obs._ws_state.variant = "501"
        assert not self.obs._is_gotcha()

    def test_is_gotcha_none(self):
        self.obs._ws_state.variant = None
        assert not self.obs._is_gotcha()

    def test_extract_variant_from_payload(self):
        assert self.obs._extract_variant({"variant": "Gotcha"}) == "Gotcha"

    def test_extract_variant_nested(self):
        assert self.obs._extract_variant({"data": {"variant": "Cricket"}}) == "Cricket"

    def test_extract_variant_none(self):
        assert self.obs._extract_variant({"score": 180}) is None
