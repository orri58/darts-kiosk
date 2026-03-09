# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN. Must behave like a real arcade machine on Windows kiosk PCs.

## Architecture
- **Arcade Machine Runtime**: On unlock, system Chrome opens Autodarts fullscreen. Kiosk window hides. Separate always-on-top credits overlay stays visible. On lock, Chrome closes, kiosk returns to foreground.
- **Persistent Chrome Profile**: Uses Playwright `launch_persistent_context` with `channel="chrome"` to reuse the installed Chrome and preserve Google/Autodarts login between sessions.
- **Credits Overlay**: Separate Python/tkinter window, always-on-top, click-through, transparent. Polls backend API every 3s.
- **MVP Observer Scope**: Observer only tracks browser sessions launched by THIS system.
- **Master/Agent**: MASTER controls all boards, AGENTs are autonomous offline
- **Tech Stack**: FastAPI + SQLAlchemy/SQLite (backend), React + Tailwind/Shadcn (frontend)

## Arcade Mode UX Flow
```
LOCKED:   Kiosk fullscreen (Chrome --kiosk), locked screen visible
UNLOCK:   Backend launches Autodarts in system Chrome (persistent profile, fullscreen)
          Kiosk window goes to background (window.blur)
          Credits overlay appears (Python/tkinter, always-on-top, click-through)
ACTIVE:   Autodarts is main visible app, observer polls game state
          Credits decrement on game START (idle -> in_game)
FAILED:   If Chrome launch fails → Fallback screen (retry, staff, end buttons)
LOCK/END: Autodarts Chrome closes → kiosk returns to foreground (window.focus)
          Credits overlay hides
```

## Windows Deployment Stack
- `start.bat`: Detects LAN IP, starts backend/frontend, launches Chrome kiosk + overlay
- `stop.bat`: Kills all processes (backend, frontend, overlay, Chrome instances)
- `run_backend.py`: Windows launcher with ProactorEventLoop for Playwright
- `credits_overlay.py`: Tkinter overlay with Win32 click-through
- `setup_windows.bat`: Full setup with Chrome detection, Playwright validation

## All Implemented Features
- v1.0.0: Core (Kiosk, Admin, Auth, Boards, Pricing, Sessions, Stammkunde, QR, Leaderboards, Sound, i18n)
- v1.1.0: White-Label (PWA, Custom Texts, Responsive Sidebar)
- v1.2.0: Update System, DOM Selector Tests, Public Leaderboard QR
- v1.3.0: Credits Overlay (real-time, "LETZTES SPIEL" warning, upsell)
- v1.4.0: Enhanced Updates, Legacy Cleanup, mDNS Improvements
- v1.4.1: Background Update Checker + Snooze (48h) / Dismiss per-version
- v1.5.0: Observer Mode Handoff/Fallback UX
- v1.5.1: Windows Playwright Fix (ProactorEventLoop, run_backend.py)
- v1.6.0: Arcade Machine Runtime Architecture
  - Persistent Chrome profile (Google login preserved)
  - Window management (blur/focus on observer state change)
  - ObserverActiveScreen simplified to pure black backdrop + fallback
  - Python/tkinter credits overlay (always-on-top, click-through, transparent)
  - start.bat with Chrome kiosk mode + overlay launch + Chrome detection
  - stop.bat with full cleanup (overlay, Chrome instances)
  - Updated README with arcade mode documentation
  - Release packages rebuilt with all new files

## Remaining Backlog
### P2
- [ ] Autodarts DOM Selector Tests (stability against UI changes)
- [ ] Chromium extension for Autodarts overlay
- [ ] PWA Install Prompt for public leaderboard
