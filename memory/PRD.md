# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs.
Must behave like a real arcade machine on Windows kiosk PCs.

## Core Architecture
- **Backend:** FastAPI + SQLAlchemy + SQLite — serves BOTH API and static frontend
- **Frontend:** React (pre-built static files served by backend — NO dev server needed)
- **Deployment:** Windows .bat scripts (non-Docker) for kiosk PCs
- **Integration:** Playwright for Autodarts browser automation
- **Update System:** GitHub Releases → Admin Panel → External Updater (updater.py)

## Production Architecture (v1.7.1)
```
Single Server (Port 8001):
  /api/*     → FastAPI routes (REST + WebSocket)
  /static/*  → Frontend JS/CSS/images (from frontend/build/static/)
  /*         → SPA catch-all returns index.html

No Node.js required at runtime. No dev server.
Backend is the ONLY process (+ Chrome overlay).
```

## Observer State Machine
```
Detection Priority (FIXED in v1.7.1):
  1. Strong match-end buttons (Rematch/Share/NewGame TEXT) → FINISHED
     ALWAYS wins, even if in_game markers still present in DOM.
  2. in_game markers WITHOUT strong end markers → IN_GAME
  3. Generic result CSS classes only → ROUND_TRANSITION
  4. Nothing → IDLE

Debounce (exit from IN_GAME):
  ROUND_TRANSITION → resets exit counter (turn change, match active)
  FINISHED         → increments exit counter (saw_finished=True)
  IDLE             → increments exit counter (abort scenario)
  3 consecutive exit polls confirm → callback fired

Last-Credit Lock (FIXED in v1.7.1):
  Match ends → FINISHED confirmed → _on_game_ended("finished")
  → credits_remaining <= 0 → should_lock=True
  → close observer/browser → lock board → restore kiosk
```

## Windows Startup (v1.7.1)
```
start.bat:
  1. Activate .venv
  2. Kill old processes
  3. Detect LAN IP
  4. Start backend (run_backend.py with watchdog)
  5. Health check with retry
  6. Launch Chrome kiosk mode (fullscreen, pointing to localhost:8001)
  7. Launch credits overlay

run_backend.py:
  - Sets Windows ProactorEventLoop policy
  - Binds to 0.0.0.0:8001
  - Watchdog: auto-restart on crash (max 5 within 5 min)

autostart.bat:
  - Creates VBS hidden launcher + Windows Startup folder shortcut
  - No admin rights required (user-level autostart)
```

## All Implemented Features
- v1.0-1.5: Core system (Kiosk, Admin, Auth, Boards, Pricing, Sessions, Sound, i18n, White-Label)
- v1.6.0: Arcade Machine Runtime (overlay, window management)
- v1.6.1-1.6.3: Chrome profile persistence, extension support, automation banner removal
- v1.6.4: Observer Debounce Logic
- v1.6.5: Three-Tier State Detection & ROUND_TRANSITION
- v1.7.0: GitHub-based Update System (check, download, install, rollback, admin UI)
- v1.7.1: Production Hardening
  - Frontend served as static build by FastAPI (no Node.js/dev server at runtime)
  - SPA routing: all non-API routes → index.html
  - WebSocket URL auto-detection for same-origin mode
  - Windows watchdog (auto-restart on crash, max 5 within 5 min)
  - Windows autostart (VBS launcher + Startup folder, no admin required)
  - Simplified start.bat (backend + overlay only, no frontend process)
  - Observer fix: strong match-end markers override in_game (Rematch/Share buttons)
  - Detailed finalization logging (should_lock, lock_reason, credits)
  - Private repo download fix: uses GitHub API URL with Accept: application/octet-stream
  - 401 handling for invalid/expired tokens, clear error messages
  - 30/30 tests passed (16 unit + 15 API/UI)

## Remaining Backlog
### P1
- [ ] Autodarts DOM Selector Tests (validate selectors against live Autodarts site)

### P2
- [ ] Chromium Extension as alternative to Playwright observer
- [ ] PWA Install Prompt for public leaderboard page
