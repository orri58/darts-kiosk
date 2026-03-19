"""
Autodarts DOM Selector Definitions v3.3.5
==========================================

Central, canonical reference for ALL DOM selectors used by the Observer
to detect match states on play.autodarts.io.

This file is:
  - IMPORTED by the observer at runtime for fallback resolution
  - IMPORTED by the test suite to validate selectors
  - The SINGLE SOURCE OF TRUTH when Autodarts changes their UI

When a selector test fails, update THIS file first.
The observer reads SELECTOR_GROUPS at startup — no code change needed.

v3.3.5: Added prioritized SELECTOR_GROUPS for fallback resolution.
"""
import json

# ═══════════════════════════════════════════════════════════════
# PRIORITIZED SELECTOR GROUPS (v3.3.5)
# Each group: ordered list of selectors (first = primary, rest = fallback)
# The observer tries each selector in order; first match wins.
# ═══════════════════════════════════════════════════════════════
SELECTOR_GROUPS = {
    "in_game_score": [
        {"css": '[class*="scoreboard"]',           "priority": "primary",  "name": "scoreboard"},
        {"css": '[class*="player-score"]',         "priority": "fallback", "name": "player_score"},
        {"css": '[class*="scoring"]',              "priority": "fallback", "name": "scoring"},
        {"css": '[class*="dart-input"]',           "priority": "fallback", "name": "dart_input"},
    ],
    "in_game_match": [
        {"css": '[class*="match-view"]',           "priority": "primary",  "name": "match_view"},
        {"css": '[class*="game-view"]',            "priority": "fallback", "name": "game_view"},
        {"css": '[class*="match"][class*="running"]', "priority": "fallback", "name": "match_running"},
        {"css": '#match',                          "priority": "fallback", "name": "match_id_el"},
        {"css": '[data-testid*="match"]',          "priority": "fallback", "name": "testid_match"},
    ],
    "in_game_turn": [
        {"css": '[class*="turn"]',                 "priority": "primary",  "name": "turn"},
        {"css": '[class*="throw"]',                "priority": "fallback", "name": "throw"},
    ],
    "finished_ui": [
        {"css": '[class*="post-match"]',           "priority": "primary",  "name": "post_match"},
        {"css": '[class*="match-summary"]',        "priority": "fallback", "name": "match_summary"},
        {"css": '[class*="match-end"]',            "priority": "fallback", "name": "match_end"},
        {"css": '[class*="game-over"]',            "priority": "fallback", "name": "game_over"},
    ],
    "result_generic": [
        {"css": '[class*="match-result"]',         "priority": "primary",  "name": "match_result"},
        {"css": '[class*="winner"]',               "priority": "fallback", "name": "winner"},
        {"css": '[class*="result"]',               "priority": "fallback", "name": "result"},
        {"css": '[class*="finished"]',             "priority": "fallback", "name": "finished"},
        {"css": '[class*="leg-result"]',           "priority": "fallback", "name": "leg_result"},
    ],
}

# ═══════════════════════════════════════════════════════════════
# FLAT SELECTOR LISTS (backward compat, derived from SELECTOR_GROUPS)
# ═══════════════════════════════════════════════════════════════
IN_GAME_SELECTORS = (
    SELECTOR_GROUPS["in_game_score"] +
    SELECTOR_GROUPS["in_game_match"] +
    SELECTOR_GROUPS["in_game_turn"]
)
# Deduplicate by name
_seen = set()
_deduped = []
for s in IN_GAME_SELECTORS:
    if s["name"] not in _seen:
        _seen.add(s["name"])
        _deduped.append({"name": s["name"], "css": s["css"], "desc": s.get("desc", s["name"])})
IN_GAME_SELECTORS = _deduped

STRONG_MATCH_END_SELECTORS = [
    {"name": s["name"], "css": s["css"], "desc": s.get("desc", s["name"])}
    for s in SELECTOR_GROUPS["finished_ui"]
]

GENERIC_RESULT_SELECTORS = [
    {"name": s["name"], "css": s["css"], "desc": s.get("desc", s["name"])}
    for s in SELECTOR_GROUPS["result_generic"]
]

# Button text patterns that indicate match end (case-insensitive regex)
MATCH_END_BUTTON_PATTERNS = [
    {"name": "rematch",  "pattern": r"rematch|nochmal spielen|play again|erneut spielen",  "desc": "Rematch/replay button"},
    {"name": "share",    "pattern": r"share|teilen|share result|ergebnis teilen",          "desc": "Share result button"},
    {"name": "new_game", "pattern": r"new game|neues spiel|new match|neues match",         "desc": "New game button"},
]

# ═══════════════════════════════════════════════════════════════
# LOGIN DETECTION
# ═══════════════════════════════════════════════════════════════
LOGIN_URL_PATTERNS = [
    "login.autodarts.io",
    "/login",
]

# ═══════════════════════════════════════════════════════════════
# WEBSOCKET FRAME CLASSIFICATION
# ═══════════════════════════════════════════════════════════════
WS_MATCH_START_EVENTS = ["turn_start", "throw"]
WS_MATCH_END_GAMESHOT_EVENTS = ["game_shot", "gameshot", "game-shot"]
WS_MATCH_END_STATE_FIELDS = ["finished", "gameFinished"]
WS_MATCH_END_KEYWORD = "matchshot"
WS_MATCH_RESET_EVENT = "delete"

WS_CHANNEL_PATTERNS = [
    {"name": "match_state",   "pattern": r"autodarts\.matches\.[\w-]+\.state",       "desc": "Match state channel"},
    {"name": "game_events",   "pattern": r"autodarts\.matches\.[\w-]+\.game-events", "desc": "Game events channel"},
    {"name": "board_matches", "pattern": r"autodarts\.boards\.[\w-]+\.matches",       "desc": "Board matches channel"},
    {"name": "board_state",   "pattern": r"autodarts\.boards\.[\w-]+\.state",         "desc": "Board state channel"},
]

# ═══════════════════════════════════════════════════════════════
# AUTODARTS BASE URL
# ═══════════════════════════════════════════════════════════════
AUTODARTS_BASE_URL = "https://play.autodarts.io"


# ═══════════════════════════════════════════════════════════════
# JS HELPER: Generate the detection script from SELECTOR_GROUPS
# ═══════════════════════════════════════════════════════════════
def build_detect_state_js() -> str:
    """Generate the DOM detection JavaScript from SELECTOR_GROUPS.

    Returns a self-contained JS function string that:
    - Tests each selector group in priority order (primary → fallback)
    - Returns match signals + diagnostics about which selectors hit
    """
    groups_json = json.dumps(SELECTOR_GROUPS)
    buttons_json = json.dumps([bp["pattern"] for bp in MATCH_END_BUTTON_PATTERNS])

    return f"""() => {{
        var groups = {groups_json};
        var buttonPatterns = {buttons_json};

        function resolveGroup(selectors) {{
            for (var i = 0; i < selectors.length; i++) {{
                var s = selectors[i];
                try {{
                    if (document.querySelector(s.css)) {{
                        return {{ found: true, name: s.name, priority: s.priority, css: s.css, index: i }};
                    }}
                }} catch(e) {{ /* invalid selector — skip safely */ }}
            }}
            return {{ found: false, name: null, priority: null, css: null, index: -1 }};
        }}

        var resolved = {{}};
        for (var key in groups) {{
            resolved[key] = resolveGroup(groups[key]);
        }}

        var inGameScore = resolved.in_game_score || {{ found: false }};
        var inGameMatch = resolved.in_game_match || {{ found: false }};
        var inGameTurn  = resolved.in_game_turn  || {{ found: false }};
        var finishedUi  = resolved.finished_ui   || {{ found: false }};
        var resultGen   = resolved.result_generic || {{ found: false }};

        var inGame = inGameScore.found || inGameMatch.found || inGameTurn.found;

        var allButtons = Array.from(document.querySelectorAll('button, a[role="button"], [class*="btn"]'));
        var buttonTexts = allButtons.map(function(b) {{ return (b.textContent || '').trim().toLowerCase(); }});

        var buttonHits = buttonPatterns.map(function(pat) {{
            var re = new RegExp(pat, 'i');
            return buttonTexts.some(function(t) {{ return re.test(t); }});
        }});
        var hasRematchBtn = buttonHits[0] || false;
        var hasShareBtn   = buttonHits[1] || false;
        var hasNewGameBtn = buttonHits[2] || false;

        var strongMatchEnd = hasRematchBtn || hasShareBtn || hasNewGameBtn || finishedUi.found;
        var hasGenericResult = resultGen.found;

        var evidence = [];
        if (inGameScore.found) evidence.push('score');
        if (inGameMatch.found) evidence.push('match');
        if (inGameTurn.found)  evidence.push('turn');

        return {{
            inGame: inGame,
            strongMatchEnd: strongMatchEnd,
            hasGenericResult: hasGenericResult,
            hasRematchBtn: hasRematchBtn,
            hasShareBtn: hasShareBtn,
            hasNewGameBtn: hasNewGameBtn,
            hasPostMatchUI: finishedUi.found,
            _groups: resolved,
            _evidence: evidence,
            _evidenceCount: evidence.length
        }};
    }}"""
