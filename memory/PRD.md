# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Must behave like a real arcade machine on Windows kiosk PCs.

## Observer State Machine (Three-Tier + Debounced)
```
States: closed, idle, in_game, round_transition, finished, unknown, error

DOM Detection (Three-Tier):
  Tier 1: Active match markers (scoreboard, dart-input, etc.) → IN_GAME
  Tier 2: Strong end buttons (Rematch/Share/NewGame text) → FINISHED
  Tier 3: Generic result CSS classes only → ROUND_TRANSITION
  Tier 4: No game markers → IDLE

Observer Loop Logic (when stable=IN_GAME):
  raw IN_GAME          → clear exit counter, continue
  raw ROUND_TRANSITION → RESET exit counter to 0 (turn change, match active)
  raw FINISHED         → increment exit counter, saw_finished=True
  raw IDLE             → increment exit counter (abort scenario)
  exit_polls >= 3      → CONFIRMED exit → callback

Normal poll: every 4s
Debounce: 3 consecutive FINISHED/IDLE polls × 2s = 6s total
ROUND_TRANSITION polls NEVER count toward exit.

Entering in_game: IMMEDIATE (credit consumed promptly)
Exiting in_game: DEBOUNCED with ROUND_TRANSITION immunity

  idle → in_game (immediate):    _on_game_started → credit -1
  in_game → round_transition:    NO ACTION (turn/round change)
  in_game → finished (×3):       CONFIRMED → _on_game_ended("finished")
  in_game → idle (×3):           CONFIRMED → _on_game_ended("aborted")
  finished → idle:               _on_game_ended("post_finish_check")

Lock decision: credits_remaining <= 0 OR time expired → close browser, restore kiosk
```

## Chrome Launch Config
```python
ignore_default_args = [
    "--enable-automation",           # removes automation banner
    "--disable-extensions",          # preserves operator extensions
    "--disable-component-extensions-with-background-pages",
]
```

## Setup Flow
1. `setup_profile.bat` → operator opens Chrome with kiosk profile, logs into Google/Autodarts, installs extensions
2. `start.bat` → reuses prepared profile, extensions + login preserved

## All Implemented Features
- v1.0-1.5: Core system (Kiosk, Admin, Auth, Boards, Pricing, Sessions, Sound, i18n, White-Label, Updates, Observer)
- v1.6.0: Arcade Machine Runtime (overlay, window management)
- v1.6.1-1.6.3: Chrome profile persistence, extension support, automation banner removal
- v1.6.4: Observer Debounce Logic
- v1.6.5: Three-Tier State Detection & ROUND_TRANSITION
  - New ROUND_TRANSITION state prevents turn/round changes from locking the board
  - Strong match-end markers (button text: Rematch/Share/NewGame) required for FINISHED
  - Generic result CSS classes only → ROUND_TRANSITION (no session end)
  - ROUND_TRANSITION resets exit debounce counter
  - Unit tests: 10 scenarios + 5 regression (15 total observer tests)
  - Full API lifecycle verified (26 tests total)

## Remaining Backlog
### P1
- [ ] Autodarts DOM Selector Tests (validate selectors against live site)

### P2
- [ ] Chromium Extension as alternative to Playwright observer
- [ ] PWA Install Prompt for public leaderboard page
