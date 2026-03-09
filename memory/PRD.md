# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN. Must behave like a real arcade machine on Windows kiosk PCs.

## Architecture
- **Arcade Machine Runtime**: On unlock, system Chrome opens Autodarts fullscreen. Kiosk window is HIDDEN via Win32 API. Separate always-on-top credits overlay stays visible. On lock, Chrome closes, kiosk window restored to foreground.
- **Persistent Chrome Profile**: Uses Playwright `launch_persistent_context` with `channel="chrome"` and `ignore_default_args=["--enable-automation"]` to reuse the installed Chrome. Preserves Google/Autodarts login. No automation banner.
- **Window Manager**: `window_manager.py` uses Win32 ctypes (EnumWindows, ShowWindow, SetForegroundWindow) to hide/restore the kiosk Chrome window by matching `document.title='DartsKiosk'`.
- **Credits Overlay**: Separate Python/tkinter window, always-on-top, click-through, transparent. Polls backend API every 3s.
- **Tech Stack**: FastAPI + SQLAlchemy/SQLite (backend), React + Tailwind/Shadcn (frontend)

## Arcade Mode UX Flow
```
LOCKED:   Kiosk fullscreen (Chrome --kiosk), locked screen visible, title='DartsKiosk'
UNLOCK:   Backend launches Autodarts in system Chrome (persistent profile, fullscreen)
          → 1.5s delay → window_manager.hide_kiosk_window() → kiosk HIDDEN
          Credits overlay appears (Python/tkinter, always-on-top, click-through)
ACTIVE:   Autodarts is main visible app, observer polls game state
          Credits decrement on game START (idle -> in_game)
FAILED:   If Chrome launch fails → Fallback screen (retry, staff, end buttons)
          Kiosk stays visible since Chrome never opened
LOCK/END: Autodarts Chrome closes → window_manager.restore_kiosk_window()
          → kiosk restored fullscreen foreground → locked screen
          Credits overlay hides
```

## Key Technical Details
### Automation Banner Removal
- `ignore_default_args=["--enable-automation"]` removes the automation flag
- `--disable-blink-features=AutomationControlled` prevents automation fingerprinting
- No `--no-sandbox` or `--disable-extensions-except` flags

### Window Title Stability
- KioskLayout.js sets `document.title = 'DartsKiosk'` after settings load
- SettingsContext.js skips title override on `/kiosk/*` routes
- Window manager uses 'DartsKiosk' pattern for EnumWindows matching

### Profile Persistence
- Profile path: `data/chrome_profile/{board_id}/`
- Profile NEVER recreated — `os.makedirs(exist_ok=True)` only creates directory
- Detects existing profile by checking `Default/` subfolder
- Logs "REUSING (Google login preserved)" or "NEW (first launch — login required)"

## All Implemented Features
- v1.0-1.5: Core Kiosk, Admin, Auth, Boards, Pricing, Sessions, Stammkunde, QR, Leaderboards, Sound, i18n, White-Label, Update System, Observer Mode
- v1.5.1: Windows Playwright Fix (ProactorEventLoop, run_backend.py)
- v1.6.0: Arcade Machine Runtime Architecture (overlay, window management)
- v1.6.1: Runtime UX Fixes
  - Automation banner removed (ignore_default_args)
  - Kiosk window properly hidden via Win32 API (not just blur)
  - Profile reuse detection with clear logging
  - Stable document.title for window identification
  - SettingsContext fixed to not override kiosk title

## Remaining Backlog
### P2
- [ ] Autodarts DOM Selector Tests (stability against UI changes)
- [ ] Chromium extension for Autodarts overlay
- [ ] PWA Install Prompt for public leaderboard
