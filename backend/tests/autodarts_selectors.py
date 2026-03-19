"""
Re-export from backend.autodarts_selectors (production location).
Tests import from here for backward compatibility.
The canonical source is backend/autodarts_selectors.py (included in release builds).
"""
from backend.autodarts_selectors import (  # noqa: F401
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
