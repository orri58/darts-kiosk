"""
Autodarts DOM Selector Definitions v3.3.4
==========================================

Central, canonical reference for ALL DOM selectors used by the Observer
to detect match states on play.autodarts.io.

This file is:
  - READ by the test suite to validate selectors
  - REFERENCE for the observer (observer uses these inline for performance)
  - The SINGLE SOURCE OF TRUTH when Autodarts changes their UI

When a selector test fails, update THIS file first, then propagate
the change into autodarts_observer.py > _detect_state_dom().
"""

# ═══════════════════════════════════════════════════════════════
# IN-GAME STATE SELECTORS
# At least ONE must match when a match is actively being played.
# ═══════════════════════════════════════════════════════════════
IN_GAME_SELECTORS = [
    {"name": "scoreboard",      "css": '[class*="scoreboard"]',                  "desc": "Main scoreboard container"},
    {"name": "dart_input",      "css": '[class*="dart-input"]',                  "desc": "Dart input/scoring area"},
    {"name": "throw",           "css": '[class*="throw"]',                       "desc": "Throw indicator/area"},
    {"name": "scoring",         "css": '[class*="scoring"]',                     "desc": "Scoring panel"},
    {"name": "game_view",       "css": '[class*="game-view"]',                   "desc": "Game view wrapper"},
    {"name": "match_view",      "css": '[class*="match-view"]',                  "desc": "Match view container"},
    {"name": "player_score",    "css": '[class*="player-score"]',                "desc": "Per-player score display"},
    {"name": "turn",            "css": '[class*="turn"]',                        "desc": "Turn indicator"},
    {"name": "match_running",   "css": '[class*="match"][class*="running"]',     "desc": "Match + running class combo"},
    {"name": "testid_match",    "css": '[data-testid*="match"]',                 "desc": "data-testid containing match"},
    {"name": "match_id_el",     "css": '#match',                                "desc": "Element with id=match"},
]

# ═══════════════════════════════════════════════════════════════
# MATCH END SELECTORS (STRONG — POST-MATCH UI)
# These indicate the match is definitively over.
# ═══════════════════════════════════════════════════════════════
STRONG_MATCH_END_SELECTORS = [
    {"name": "post_match",      "css": '[class*="post-match"]',                  "desc": "Post-match container"},
    {"name": "match_summary",   "css": '[class*="match-summary"]',               "desc": "Match summary/stats"},
    {"name": "match_end",       "css": '[class*="match-end"]',                   "desc": "Match-end UI"},
    {"name": "game_over",       "css": '[class*="game-over"]',                   "desc": "Game over screen"},
]

# Button text patterns that indicate match end (case-insensitive regex)
MATCH_END_BUTTON_PATTERNS = [
    {"name": "rematch",    "pattern": r"rematch|nochmal spielen|play again|erneut spielen",  "desc": "Rematch/replay button"},
    {"name": "share",      "pattern": r"share|teilen|share result|ergebnis teilen",          "desc": "Share result button"},
    {"name": "new_game",   "pattern": r"new game|neues spiel|new match|neues match",         "desc": "New game button"},
]

# ═══════════════════════════════════════════════════════════════
# GENERIC RESULT SELECTORS (WEAK — may appear during round transitions)
# ═══════════════════════════════════════════════════════════════
GENERIC_RESULT_SELECTORS = [
    {"name": "result",          "css": '[class*="result"]',                      "desc": "Result display"},
    {"name": "winner",          "css": '[class*="winner"]',                      "desc": "Winner indicator"},
    {"name": "finished",        "css": '[class*="finished"]',                    "desc": "Finished state marker"},
    {"name": "match_result",    "css": '[class*="match-result"]',                "desc": "Match result panel"},
    {"name": "leg_result",      "css": '[class*="leg-result"]',                  "desc": "Leg result panel"},
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
# Maps event names / payload patterns to lifecycle signals.
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
