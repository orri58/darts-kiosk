# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Architecture
- **Autodarts Observer MVP**: On unlock, Playwright opens Autodarts fullscreen. Kiosk hands off screen. Only credits overlay stays visible on top.
- **MVP Observer Scope**: Observer only tracks browser sessions launched by THIS system. Manually opened external browser windows are NOT detected/supported.
- **Master/Agent**: MASTER controls all boards, AGENTs are autonomous offline
- **Tech Stack**: FastAPI + SQLAlchemy/SQLite (backend), React + Tailwind/Shadcn (frontend)

## Observer Mode UX Flow
```
LOCKED:   Kiosk fullscreen, locked screen visible
UNLOCK:   Playwright opens Autodarts fullscreen (covers kiosk)
          Kiosk shows minimal dark handoff screen (hidden behind Autodarts)
          Credits overlay stays on top as separate window
ACTIVE:   Autodarts is main visible app, observer tracks game state
          Credits decrement on game start (idle → in_game)
FAILED:   If browser launch fails → Fallback screen (retry, staff, end buttons)
LOCK/END: Autodarts browser closes → kiosk returns to locked screen
```

## Windows Playwright Fix (v1.5.1 - 2026-03-09)
### Root Cause
`NotImplementedError` from `asyncio.create_subprocess_exec` because uvicorn on Windows uses `SelectorEventLoop`. Playwright requires `ProactorEventLoop` for subprocess execution.

### Fix
- **`run_backend.py`**: Dedicated Windows launcher that sets `WindowsProactorEventLoopPolicy` BEFORE uvicorn creates its event loop
- **`_run_backend.bat`**: Updated to `python run_backend.py` (not `python -m uvicorn`)
- **`reload=False`**: Disabled uvicorn reloader (reloader spawns subprocess that resets event loop)
- **`setup_windows.bat`**: Added Playwright browser validation step after install
- **Observer logging**: 6-step detailed launch trace (import → runtime → chromium → context → page → navigate)
- **Error handling**: Concise error messages (first line, max 200 chars) for frontend display
- **Session endpoint**: Returns `observer_browser_open`, `observer_state`, `observer_error`

### Kiosk Screens
- `observer-handoff-screen`: Minimal dark backdrop when Autodarts is fullscreen on top
- `observer-fallback-screen`: Shown when browser launch failed - error + retry + staff + end

## All Implemented Features
- v1.0.0: Core (Kiosk, Admin, Auth, Boards, Pricing, Sessions, Stammkunde, QR, Leaderboards, Sound, i18n)
- v1.1.0: White-Label (PWA, Custom Texts, Responsive Sidebar)
- v1.2.0: Update System, DOM Selector Tests, Public Leaderboard QR
- v1.3.0: Credits Overlay (real-time, "LETZTES SPIEL" warning, upsell)
- v1.4.0: Enhanced Updates, Legacy Cleanup, mDNS Improvements
- v1.4.1: Background Update Checker + Snooze (48h) / Dismiss per-version
- v1.5.0: Observer Mode Handoff/Fallback UX
- v1.5.1: Windows Playwright Fix (ProactorEventLoop, run_backend.py, detailed logging)

## Remaining Backlog
### P2
- [ ] Chromium extension for Autodarts overlay
- [ ] PWA Install Prompt for public leaderboard
