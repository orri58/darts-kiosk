"""
Autodarts DOM Selector & Frame Classification Test Suite v3.3.4
================================================================

Tests three layers of the Observer's detection mechanism:
  1. WS frame classification (unit tests, no network)
  2. DOM selector logic (mock HTML injection, validates JS detection)
  3. Live page probe (optional, skipped on network failure)

Run: pytest backend/tests/test_autodarts_dom_selectors.py -v
Run with live tests: AUTODARTS_LIVE=1 pytest ... -v
"""
import os
import re
import sys
import json
import time
import logging
import pytest
from datetime import datetime, timezone

# Ensure imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.tests.autodarts_selectors import (
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
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# FIXTURES
# ═══════════════════════════════════════════════════════════════

LIVE_TESTS = os.environ.get("AUTODARTS_LIVE", "0") == "1"


@pytest.fixture(scope="module")
def browser_context():
    """Launch a headless Chromium browser for DOM tests."""
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
    """Fresh page for each test."""
    p = browser_context.new_page()
    yield p
    p.close()


# ═══════════════════════════════════════════════════════════════
# PART 1: SELECTOR DEFINITION INTEGRITY
# ═══════════════════════════════════════════════════════════════

class TestSelectorIntegrity:
    """Validate that selector definitions are well-formed and non-empty."""

    def test_in_game_selectors_not_empty(self):
        assert len(IN_GAME_SELECTORS) >= 5, \
            f"Expected at least 5 in-game selectors, got {len(IN_GAME_SELECTORS)}"

    def test_strong_match_end_selectors_not_empty(self):
        assert len(STRONG_MATCH_END_SELECTORS) >= 3

    def test_generic_result_selectors_not_empty(self):
        assert len(GENERIC_RESULT_SELECTORS) >= 3

    def test_button_patterns_not_empty(self):
        assert len(MATCH_END_BUTTON_PATTERNS) >= 2

    def test_all_selectors_have_required_fields(self):
        """Each selector dict must have name, css, desc."""
        for group_name, selectors in [
            ("in_game", IN_GAME_SELECTORS),
            ("strong_match_end", STRONG_MATCH_END_SELECTORS),
            ("generic_result", GENERIC_RESULT_SELECTORS),
        ]:
            for s in selectors:
                assert "name" in s, f"{group_name}: missing 'name' in {s}"
                assert "css" in s, f"{group_name}: missing 'css' in {s}"
                assert "desc" in s, f"{group_name}: missing 'desc' in {s}"
                assert s["css"].strip(), f"{group_name}/{s['name']}: empty CSS selector"

    def test_button_patterns_compile(self):
        """All button regex patterns must be valid."""
        for bp in MATCH_END_BUTTON_PATTERNS:
            try:
                re.compile(bp["pattern"], re.IGNORECASE)
            except re.error as e:
                pytest.fail(f"Invalid regex in {bp['name']}: {bp['pattern']} — {e}")

    def test_ws_channel_patterns_compile(self):
        """All WS channel regex patterns must be valid."""
        for cp in WS_CHANNEL_PATTERNS:
            try:
                re.compile(cp["pattern"])
            except re.error as e:
                pytest.fail(f"Invalid regex in {cp['name']}: {cp['pattern']} — {e}")

    def test_no_duplicate_selector_names(self):
        """No duplicate names within a group."""
        for group_name, selectors in [
            ("in_game", IN_GAME_SELECTORS),
            ("strong_match_end", STRONG_MATCH_END_SELECTORS),
            ("generic_result", GENERIC_RESULT_SELECTORS),
        ]:
            names = [s["name"] for s in selectors]
            dupes = [n for n in names if names.count(n) > 1]
            assert not dupes, f"{group_name}: duplicate names: {set(dupes)}"


# ═══════════════════════════════════════════════════════════════
# PART 2: WS FRAME CLASSIFICATION (UNIT TESTS — NO NETWORK)
# ═══════════════════════════════════════════════════════════════

class TestWSFrameClassification:
    """Test that the observer's _classify_frame logic matches our selector defs."""

    @pytest.fixture(autouse=True)
    def setup_observer_stub(self):
        """Create a minimal observer stub to test _classify_frame."""
        from backend.services.autodarts_observer import AutodartsObserver
        self.obs = AutodartsObserver.__new__(AutodartsObserver)
        self.obs.board_id = "TEST-BOARD"
        from backend.services.autodarts_observer import WSEventState
        self.obs._ws_state = WSEventState()
        self.obs._last_finalized_match_id = None

    def test_turn_start_is_match_start(self):
        raw = json.dumps({"event": "turn_start", "channel": "autodarts.matches.123.game-events"})
        payload = {"event": "turn_start"}
        result = self.obs._classify_frame(raw, "autodarts.matches.123.game-events", payload)
        assert result == "match_start_turn_start", f"Expected match_start_turn_start, got {result}"

    def test_throw_is_match_start(self):
        raw = json.dumps({"event": "throw"})
        payload = {"event": "throw"}
        result = self.obs._classify_frame(raw, "autodarts.matches.123.game-events", payload)
        assert result == "match_start_throw", f"Expected match_start_throw, got {result}"

    def test_game_shot_match_is_match_end(self):
        payload = {"event": "game_shot", "body": {"type": "match"}}
        raw = json.dumps(payload)
        result = self.obs._classify_frame(raw, "autodarts.matches.123.game-events", payload)
        assert result == "match_end_gameshot_match", f"Expected match_end_gameshot_match, got {result}"

    def test_game_shot_leg_is_round_transition(self):
        payload = {"event": "game_shot", "body": {"type": "leg"}}
        raw = json.dumps(payload)
        result = self.obs._classify_frame(raw, "autodarts.matches.123.game-events", payload)
        assert result == "round_transition_gameshot", f"Expected round_transition_gameshot, got {result}"

    def test_finished_true_is_match_end(self):
        payload = {"finished": True, "state": "finished"}
        raw = json.dumps(payload)
        result = self.obs._classify_frame(raw, "autodarts.matches.123.state", payload)
        assert result == "match_end_state_finished", f"Expected match_end_state_finished, got {result}"

    def test_game_finished_true_is_match_end(self):
        payload = {"gameFinished": True}
        raw = json.dumps(payload)
        result = self.obs._classify_frame(raw, "autodarts.matches.123.state", payload)
        assert result == "match_end_game_finished", f"Expected match_end_game_finished, got {result}"

    def test_matchshot_keyword(self):
        raw = '{"channel":"autodarts.matches.abc.game-events","data":"matchshot detected"}'
        result = self.obs._classify_frame(raw, "autodarts.matches.abc.game-events", {"data": "matchshot detected"})
        assert result == "match_finished_matchshot", f"Expected match_finished_matchshot, got {result}"

    def test_delete_event_is_reset(self):
        payload = {"event": "delete"}
        raw = json.dumps(payload)
        result = self.obs._classify_frame(raw, "autodarts.matches.123.state", payload)
        assert result == "match_reset_delete", f"Expected match_reset_delete, got {result}"

    def test_irrelevant_frame(self):
        raw = '{"heartbeat": true}'
        result = self.obs._classify_frame(raw, "system.heartbeat", {"heartbeat": True})
        assert result == "irrelevant", f"Expected irrelevant, got {result}"

    def test_autodarts_subscription(self):
        raw = '{"action":"subscribe","channel":"autodarts.boards.xyz.state"}'
        result = self.obs._classify_frame(raw, "autodarts.boards.xyz.state", {"action": "subscribe"})
        assert result == "subscription", f"Expected subscription, got {result}"


# ═══════════════════════════════════════════════════════════════
# PART 3: DOM DETECTION LOGIC (MOCK HTML — NO NETWORK)
# ═══════════════════════════════════════════════════════════════

# The exact JS from _detect_state_dom, extracted for testability
DETECT_STATE_JS = """() => {
    var inGame = !!(
        document.querySelector('[class*="scoreboard"]') ||
        document.querySelector('[class*="dart-input"]') ||
        document.querySelector('[class*="throw"]') ||
        document.querySelector('[class*="scoring"]') ||
        document.querySelector('[class*="game-view"]') ||
        document.querySelector('[class*="match-view"]') ||
        document.querySelector('[class*="player-score"]') ||
        document.querySelector('[class*="turn"]') ||
        document.querySelector('[class*="match"][class*="running"]') ||
        document.querySelector('[data-testid*="match"]') ||
        document.querySelector('#match')
    );

    var allButtons = Array.from(document.querySelectorAll('button, a[role="button"], [class*="btn"]'));
    var buttonTexts = allButtons.map(function(b) { return (b.textContent || '').trim().toLowerCase(); });

    var hasRematchBtn = buttonTexts.some(function(t) {
        return /rematch|nochmal spielen|play again|erneut spielen/i.test(t);
    });
    var hasShareBtn = buttonTexts.some(function(t) {
        return /share|teilen|share result|ergebnis teilen/i.test(t);
    });
    var hasNewGameBtn = buttonTexts.some(function(t) {
        return /new game|neues spiel|new match|neues match/i.test(t);
    });
    var hasPostMatchUI = !!(
        document.querySelector('[class*="post-match"]') ||
        document.querySelector('[class*="match-summary"]') ||
        document.querySelector('[class*="match-end"]') ||
        document.querySelector('[class*="game-over"]')
    );
    var strongMatchEnd = hasRematchBtn || hasShareBtn || hasNewGameBtn || hasPostMatchUI;

    var hasGenericResult = !!(
        document.querySelector('[class*="result"]') ||
        document.querySelector('[class*="winner"]') ||
        document.querySelector('[class*="finished"]') ||
        document.querySelector('[class*="match-result"]') ||
        document.querySelector('[class*="leg-result"]')
    );

    return {
        inGame: inGame,
        strongMatchEnd: strongMatchEnd,
        hasGenericResult: hasGenericResult,
        hasRematchBtn: hasRematchBtn,
        hasShareBtn: hasShareBtn,
        hasNewGameBtn: hasNewGameBtn,
        hasPostMatchUI: hasPostMatchUI
    };
}"""


class TestDOMDetectionLogic:
    """Inject mock HTML and run the exact observer detection JS."""

    def _inject_and_detect(self, page, html_body: str) -> dict:
        """Load mock HTML and run detection JS."""
        full_html = f"<html><body>{html_body}</body></html>"
        page.set_content(full_html)
        return page.evaluate(DETECT_STATE_JS)

    def _log_result(self, test_name, signals, expected_state):
        """Log selector test result for debugging."""
        logger.info(
            f"[SELECTOR_TEST] {test_name} | "
            f"expected={expected_state} | "
            f"inGame={signals.get('inGame')} | "
            f"strongMatchEnd={signals.get('strongMatchEnd')} | "
            f"hasGenericResult={signals.get('hasGenericResult')} | "
            f"ts={datetime.now(timezone.utc).isoformat()}"
        )

    def test_idle_empty_page(self, page):
        """Empty page → nothing detected (IDLE state)."""
        signals = self._inject_and_detect(page, "<div>Welcome to Autodarts</div>")
        self._log_result("idle_empty", signals, "idle")
        assert not signals["inGame"], "Empty page should NOT detect inGame"
        assert not signals["strongMatchEnd"], "Empty page should NOT detect strongMatchEnd"
        assert not signals["hasGenericResult"], "Empty page should NOT detect genericResult"

    def test_in_game_scoreboard(self, page):
        """Scoreboard class → inGame detected."""
        html = '<div class="ad-scoreboard main">Player 1: 501</div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("in_game_scoreboard", signals, "in_game")
        assert signals["inGame"], "Scoreboard class should trigger inGame"

    def test_in_game_player_score(self, page):
        """player-score class → inGame detected."""
        html = '<div class="player-score-container"><span class="player-score">301</span></div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("in_game_player_score", signals, "in_game")
        assert signals["inGame"], "player-score should trigger inGame"

    def test_in_game_match_running(self, page):
        """match + running combo class → inGame detected."""
        html = '<div class="match-container running active">Match in progress</div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("in_game_match_running", signals, "in_game")
        assert signals["inGame"], "match+running combo should trigger inGame"

    def test_in_game_data_testid(self, page):
        """data-testid=match-view → inGame detected."""
        html = '<div data-testid="match-view-501">Game</div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("in_game_testid", signals, "in_game")
        assert signals["inGame"], "data-testid*=match should trigger inGame"

    def test_in_game_turn_indicator(self, page):
        """turn class → inGame detected."""
        html = '<div class="current-turn active">Player 1\'s turn</div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("in_game_turn", signals, "in_game")
        assert signals["inGame"], "turn class should trigger inGame"

    def test_in_game_match_id(self, page):
        """#match element → inGame detected."""
        html = '<div id="match">Active match</div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("in_game_match_id", signals, "in_game")
        assert signals["inGame"], "#match should trigger inGame"

    def test_finished_rematch_button(self, page):
        """Rematch button → strongMatchEnd detected."""
        html = '''
        <div class="post-game">
            <button class="btn-primary">Rematch</button>
            <button class="btn-secondary">Share Result</button>
        </div>
        '''
        signals = self._inject_and_detect(page, html)
        self._log_result("finished_rematch", signals, "finished")
        assert signals["strongMatchEnd"], "Rematch button should trigger strongMatchEnd"
        assert signals["hasRematchBtn"], "hasRematchBtn should be True"

    def test_finished_nochmal_spielen(self, page):
        """German 'Nochmal spielen' button → strongMatchEnd."""
        html = '<button>Nochmal spielen</button>'
        signals = self._inject_and_detect(page, html)
        self._log_result("finished_nochmal", signals, "finished")
        assert signals["strongMatchEnd"], "'Nochmal spielen' should trigger strongMatchEnd"

    def test_finished_share_button(self, page):
        """Share button → strongMatchEnd."""
        html = '<button class="share-btn">Ergebnis teilen</button>'
        signals = self._inject_and_detect(page, html)
        self._log_result("finished_share", signals, "finished")
        assert signals["strongMatchEnd"], "Share button should trigger strongMatchEnd"
        assert signals["hasShareBtn"], "hasShareBtn should be True"

    def test_finished_new_game_button(self, page):
        """New Game button → strongMatchEnd."""
        html = '<a role="button" class="btn">New Game</a>'
        signals = self._inject_and_detect(page, html)
        self._log_result("finished_new_game", signals, "finished")
        assert signals["strongMatchEnd"], "New Game button should trigger strongMatchEnd"

    def test_finished_post_match_ui(self, page):
        """post-match class → strongMatchEnd."""
        html = '<div class="post-match-results"><h2>Match Over</h2></div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("finished_post_match", signals, "finished")
        assert signals["strongMatchEnd"], "post-match class should trigger strongMatchEnd"
        assert signals["hasPostMatchUI"], "hasPostMatchUI should be True"

    def test_finished_match_summary(self, page):
        """match-summary class → strongMatchEnd."""
        html = '<div class="match-summary-card">Winner: Player 1</div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("finished_summary", signals, "finished")
        assert signals["strongMatchEnd"], "match-summary should trigger strongMatchEnd"

    def test_generic_result_winner(self, page):
        """winner class → hasGenericResult."""
        html = '<div class="winner-highlight">Player 1 wins!</div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("result_winner", signals, "result")
        assert signals["hasGenericResult"], "winner class should trigger hasGenericResult"

    def test_generic_result_finished(self, page):
        """finished class → hasGenericResult."""
        html = '<div class="game-finished-overlay">Game finished</div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("result_finished", signals, "result")
        assert signals["hasGenericResult"], "finished class should trigger hasGenericResult"

    def test_generic_result_leg_result(self, page):
        """leg-result class → hasGenericResult."""
        html = '<div class="leg-result-panel">Leg 1 of 3</div>'
        signals = self._inject_and_detect(page, html)
        self._log_result("result_leg", signals, "result")
        assert signals["hasGenericResult"], "leg-result should trigger hasGenericResult"

    def test_no_false_positive_on_unrelated(self, page):
        """Unrelated UI must NOT trigger any detection."""
        html = '''
        <nav class="main-menu"><a href="/profile">Profile</a></nav>
        <div class="lobby-container"><h1>Welcome</h1></div>
        <button>Play Now</button>
        '''
        signals = self._inject_and_detect(page, html)
        self._log_result("no_false_positive", signals, "idle")
        assert not signals["inGame"], "Lobby should NOT trigger inGame"
        assert not signals["strongMatchEnd"], "Lobby should NOT trigger strongMatchEnd"


# ═══════════════════════════════════════════════════════════════
# PART 4: INDIVIDUAL CSS SELECTOR VALIDATION
# ═══════════════════════════════════════════════════════════════

class TestCSSSelectorsValid:
    """Verify each CSS selector is syntactically valid via querySelectorAll."""

    def _test_selector_valid(self, page, selector_css: str, name: str):
        """Run querySelectorAll with the selector — no JS error = valid syntax."""
        page.set_content("<html><body><div>test</div></body></html>")
        try:
            page.evaluate(f'document.querySelectorAll({json.dumps(selector_css)})')
        except Exception as e:
            pytest.fail(
                f"CSS selector SYNTAX ERROR: "
                f"selector_name={name} selector_string={selector_css} "
                f"error={e} url=mock timestamp={datetime.now(timezone.utc).isoformat()}"
            )

    def test_all_in_game_selectors_valid(self, page):
        for s in IN_GAME_SELECTORS:
            self._test_selector_valid(page, s["css"], s["name"])

    def test_all_strong_match_end_selectors_valid(self, page):
        for s in STRONG_MATCH_END_SELECTORS:
            self._test_selector_valid(page, s["css"], s["name"])

    def test_all_generic_result_selectors_valid(self, page):
        for s in GENERIC_RESULT_SELECTORS:
            self._test_selector_valid(page, s["css"], s["name"])


# ═══════════════════════════════════════════════════════════════
# PART 5: LIVE PAGE PROBE (OPTIONAL — SET AUTODARTS_LIVE=1)
# ═══════════════════════════════════════════════════════════════

@pytest.mark.skipif(not LIVE_TESTS, reason="AUTODARTS_LIVE=1 not set")
class TestLivePageProbe:
    """Probe play.autodarts.io — verify page loads and login redirect works."""

    def test_page_loads(self, page):
        """Autodarts page should load without error."""
        try:
            response = page.goto(AUTODARTS_BASE_URL, timeout=15000, wait_until="domcontentloaded")
            assert response is not None, "No response from play.autodarts.io"
            status = response.status
            assert status < 500, f"Server error: HTTP {status}"
            logger.info(
                f"[LIVE_PROBE] page_loaded url={page.url} status={status} "
                f"ts={datetime.now(timezone.utc).isoformat()}"
            )
        except Exception as e:
            if "net::" in str(e) or "timeout" in str(e).lower():
                pytest.skip(f"Network/environment issue (not a selector bug): {e}")
            raise

    def test_login_redirect(self, page):
        """Without auth, Autodarts should redirect to login page."""
        try:
            page.goto(AUTODARTS_BASE_URL, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            url = page.url.lower()
            detected_login = any(p in url for p in LOGIN_URL_PATTERNS)
            logger.info(
                f"[LIVE_PROBE] login_check url={page.url} "
                f"detected_login={detected_login} "
                f"ts={datetime.now(timezone.utc).isoformat()}"
            )
            assert detected_login, (
                f"Expected redirect to login page. "
                f"actual_url={page.url} expected_patterns={LOGIN_URL_PATTERNS}"
            )
        except Exception as e:
            if "net::" in str(e) or "timeout" in str(e).lower():
                pytest.skip(f"Network/environment issue: {e}")
            raise

    def test_page_has_basic_dom(self, page):
        """The page should have a body and basic structure."""
        try:
            page.goto(AUTODARTS_BASE_URL, timeout=15000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            body = page.query_selector("body")
            assert body is not None, "No <body> element found"
            html = page.content()
            assert len(html) > 200, f"Page too small ({len(html)} chars) — may not have loaded"
        except Exception as e:
            if "net::" in str(e) or "timeout" in str(e).lower():
                pytest.skip(f"Network/environment issue: {e}")
            raise


# ═══════════════════════════════════════════════════════════════
# PART 6: GOTCHA VARIANT GUARD
# ═══════════════════════════════════════════════════════════════

class TestGotchaVariantGuard:
    """Verify the Gotcha guard blocks gameshot triggers correctly."""

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

    def test_is_gotcha_negative(self):
        self.obs._ws_state.variant = "501"
        assert not self.obs._is_gotcha()

    def test_is_gotcha_none(self):
        self.obs._ws_state.variant = None
        assert not self.obs._is_gotcha()

    def test_extract_variant_from_payload(self):
        v = self.obs._extract_variant({"variant": "Gotcha"})
        assert v == "Gotcha"

    def test_extract_variant_nested(self):
        v = self.obs._extract_variant({"data": {"variant": "Cricket"}})
        assert v == "Cricket"

    def test_extract_variant_none(self):
        v = self.obs._extract_variant({"score": 180})
        assert v is None
