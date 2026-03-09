# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Must behave like a real arcade machine on Windows kiosk PCs.

## Architecture
- **Arcade Machine Runtime**: On unlock, system Chrome opens Autodarts fullscreen. Kiosk window hidden via Win32 API. Credits overlay always-on-top. On lock, Chrome closes, kiosk restored.
- **Persistent Chrome Profile**: `launch_persistent_context` with `channel="chrome"`. `ignore_default_args` removes `--enable-automation`, `--disable-extensions`, `--disable-component-extensions-with-background-pages`. Extensions and Google login preserved.
- **Window Manager**: Win32 ctypes with retry logic (3 attempts, 1s delay). Identifies kiosk by title 'DartsKiosk'.
- **Setup Flow**: `setup_profile.bat` → operator logs in, installs extensions → `start.bat` → kiosk uses prepared profile.

## Observer State Machine
```
Transitions:
  * → in_game:        _on_game_started (credit -1)
  in_game → finished: _on_game_ended("finished")
  in_game → idle:     _on_game_ended("aborted")
  finished → idle:    _on_game_ended("post_finish_check")

Lock decision: credits_remaining <= 0 (per_game) OR now >= expires_at (per_time)
Session-end chain: finalize DB → broadcast → _safe_close_observer → close browser → restore kiosk
```

## Chrome Launch Config
```python
ignore_default_args = [
    "--enable-automation",           # removes automation banner
    "--disable-extensions",          # preserves operator-installed extensions
    "--disable-component-extensions-with-background-pages",
]
chrome_args = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-background-timer-throttling",
    "--no-first-run",
    "--no-default-browser-check",
    "--autoplay-policy=no-user-gesture-required",
    "--start-fullscreen",
    "--kiosk",
]
```

## All Implemented Features
- v1.0-1.5: Core Kiosk, Admin, Auth, Boards, Pricing, Sessions, Stammkunde, QR, Leaderboards, Sound, i18n, White-Label, Update System, Observer Mode
- v1.5.1: Windows Playwright Fix (ProactorEventLoop)
- v1.6.0: Arcade Machine Runtime (overlay, window management)
- v1.6.1: Runtime UX Fixes (automation banner, window hiding, profile reuse)
- v1.6.2: Session-End Logic Fix (unified _on_game_ended, abort handling)
- v1.6.3: Chrome Profile & Extension Persistence
  - ignore_default_args expanded: +--disable-extensions, +--disable-component-extensions
  - chrome_args cleaned: removed --disable-default-apps, --disable-sync, --disable-translate
  - Profile content logging: cookies, extensions directory, entry count
  - Window manager retry logic (3 attempts, 1s delay)
  - New setup_profile.bat for operator profile preparation
  - Release packages rebuilt

## Remaining Backlog
### P2
- [ ] Autodarts DOM Selector Tests
- [ ] Chromium extension for Autodarts overlay
- [ ] PWA Install Prompt
