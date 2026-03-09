# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Must behave like a real arcade machine on Windows kiosk PCs.

## Observer State Machine (Debounced)
```
Normal poll: every 4s
Debounce: 3 consecutive non-in_game polls × 2s = 6s total

Entering in_game: IMMEDIATE (credit consumed promptly)
Exiting in_game: DEBOUNCED (prevents false exits from turn changes)

  idle → in_game (immediate):    _on_game_started → credit -1
  in_game → non-in_game (poll 1): _exit_polls=1, continue polling at 2s
  in_game → in_game (recovered):  _exit_polls=0, "RECOVERED" logged
  in_game → non-in_game (poll 3): CONFIRMED → _on_game_ended(reason)
    reason = "finished" if any exit poll saw FINISHED
    reason = "aborted" otherwise
  finished → idle: _on_game_ended("post_finish_check")

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
  - DEBOUNCE_EXIT_POLLS=3, DEBOUNCE_POLL_INTERVAL=2s → 6s total
  - Turn changes (brief DOM flicker) no longer trigger false lock
  - Real abort/finish still detected after sustained state change
  - Unit tests: 5 scenarios (turn change, real abort, real finish, alternating flicker, config)

## Remaining Backlog
### P2
- [ ] Autodarts DOM Selector Tests
- [ ] PWA Install Prompt
