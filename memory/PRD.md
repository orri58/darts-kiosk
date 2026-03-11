# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs.
Must behave like a real arcade machine on Windows kiosk PCs.

## Core Architecture
- **Backend:** FastAPI + SQLAlchemy + SQLite — serves BOTH API and static frontend
- **Frontend:** React (pre-built static files served by backend — NO dev server needed)
- **Deployment:** Windows .bat scripts (non-Docker) for kiosk PCs
- **Integration:** Playwright for Autodarts browser automation
- **Update System:** GitHub Releases -> Admin Panel -> External Updater (updater.py)

## Production Architecture (v1.7.2)
```
Single Server (Port 8001):
  /api/*     -> FastAPI routes (REST + WebSocket)
  /static/*  -> Frontend JS/CSS/images (from frontend/build/static/)
  /*         -> SPA catch-all returns index.html

No Node.js required at runtime. No dev server.
Backend is the ONLY process (+ Chrome overlay).
```

## Observer State Machine (v1.9.0 — Playwright Native WS + Console + DOM)
```
Detection architecture (priority order):
  1. Playwright page.on('websocket') — network-level frame capture
     - Captures ALL WS frames regardless of when connection was created
     - Parses channels: autodarts.matches.{id}.state, .game-events
     - Parses channels: autodarts.boards.{id}.matches, .state
     - Classifications: match_finished_matchshot, match_finished_winner,
       match_finished_state, match_finished_winner_field, match_started,
       round_transition_gameshot, turn_transition, game_event, etc.
     - matchshot / winner / state=finished -> match_finished=True
     - gameshot (without matchFinished) -> ROUND_TRANSITION (leg end only)

  2. Console capture via add_init_script (runs BEFORE page JS loads)
     - "Winner Animation - Initializing" -> winnerDetected + matchFinished
     - "matchshot" -> matchFinished + winnerDetected
     - "gameshot" -> logged only (not match end)
     - Any match/finish/end console output captured

  3. DOM/UI polling (FALLBACK only)
     - Strong match-end buttons (Rematch/Share/NewGame) -> FINISHED
     - in_game markers -> IN_GAME
     - Generic result CSS -> ROUND_TRANSITION
     - Nothing -> IDLE

  Merge: _merge_detection(ws_state, console_state, dom_state)
    - WS FINISHED always wins
    - Console FINISHED overrides DOM
    - WS IN_GAME takes priority
    - No event data -> DOM fallback

Diagnostic endpoint:
  GET /api/kiosk/{board_id}/ws-diagnostic
  Returns: ws_state, captured_frames (last 30), debounce state
  Use this on the real board PC to see exactly what events Autodarts sends.

Previous approach (BROKEN, replaced):
  JS injection via page.evaluate() AFTER page.goto() completed.
  This never captured WS frames because Autodarts' WebSocket connection
  was already established before the injection script ran.
```

## Finalization Chain (v1.7.2)
```
_on_game_ended(board_id, reason):
  1. Check credits/time -> decide should_lock
  2. If should_lock: update session (FINISHED), set board (LOCKED)
  3. Broadcast board_status=locked via WebSocket
  4. Schedule _safe_close_observer:
     step_1: Close observer (Autodarts browser)
     step_2: Kill credits overlay process (window_manager.kill_overlay_process)
     step_3: Verify board locked in DB
  5. Observer close_session:
     - Cancel observe loop
     - Close Playwright context (Chrome)
     - Restore kiosk window (window_manager.restore_kiosk_window)
```

## Update System (v1.7.2)
```
Install flow:
  1. Create app backup
  2. Find downloaded asset
  3. Extract & validate ZIP structure
  4. Write update manifest
  5. Launch external updater process
  6. If launch fails -> HTTP 500 with error detail to frontend

External updater.py:
  - File-based logging to logs/updater.log
  - Absolute path resolution for all operations
  - Step-by-step logging (project_root, staging_dir, backup_path)
  - Windows: subprocess.Popen with CREATE_NEW_CONSOLE (no close_fds)
  - Linux: start_new_session with stdout/stderr redirect
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
  - SPA routing: all non-API routes -> index.html
  - WebSocket URL auto-detection for same-origin mode
  - Windows watchdog (auto-restart on crash, max 5 within 5 min)
  - Windows autostart (VBS launcher + Startup folder, no admin required)
  - Observer fix: strong match-end markers override in_game
  - Private repo download fix: uses GitHub API URL with Accept: application/octet-stream
- v1.7.2: P0 Bug Fixes (2026-03-09)
  - Update installer: proper error propagation (500 with detail instead of silent 200 OK)
  - Update installer: Windows-compatible subprocess.Popen (CREATE_NEW_CONSOLE, no close_fds)
  - External updater.py: file-based logging to logs/updater.log + absolute paths
  - Match-end finalization: 3-step chain (observer close, overlay kill, DB verify)
  - Overlay termination: window_manager.kill_overlay_process() via taskkill/pkill
  - Observer close_session: step-by-step logging for debugging
  - All tests passing: 9/9 backend tests (iteration_30)
- v1.7.3: Regression Fixes (2026-03-09)
  - start.bat: Complete rewrite — `setlocal enabledelayedexpansion`, WMIC removed, robust quoting, file existence checks
  - stop.bat: WMIC removed, simplified to taskkill only
  - PWA: Default manifest.json now has `start_url: /admin` — iPhone "Add to Home Screen" opens Admin Panel
  - Removed manifest-admin.json (redundant) and dynamic manifest swap in AdminLayout.js
  - index.html: Updated apple-mobile-web-app-title and title to "Darts Admin"
  - Port consistency: Removed _run_frontend.bat (dev artifact, port 3000), README updated to 8001 only
  - GH Actions: Fixed REACT_APP_BACKEND_URL to empty string (same-origin, enables LAN access)
  - All tests passing: 11/11 (iteration_31)
- v1.8.0: Event-Driven Observer Refactor (2026-03-09)
  - Observer rewritten: WebSocket/console event capture as PRIMARY match-end detection
  - Injected JS (WS_INTERCEPT_SCRIPT) intercepts Autodarts WS messages + console.log
  - Captures: matchState, matchFinished, winnerDetected, matchshot, gameshot, Winner Animation
  - DOM polling demoted to FALLBACK only via _detect_state_dom()
  - New _merge_detection(): Events always override DOM for FINISHED signals
  - gameshot (leg end) correctly mapped to ROUND_TRANSITION (NOT match end)
  - matchshot/Winner Animation correctly mapped to FINISHED (true match end)
  - All required logs: event_capture, EVENT_SIGNAL, DOM_SIGNAL, merge, finalization chain
  - All tests passing: 14/14 (iteration_32)
- v1.8.1: iOS PWA Touch Fix (2026-03-09)
  - Root cause: Sonner toast container (<section> with pointer-events) blocked header touch on mobile
  - Fix 1: Toast position moved from top-center to bottom-center (no header overlap)
  - Fix 2: CSS pointer-events:none on [data-sonner-toaster], pointer-events:auto on [data-sonner-toast]
  - Fix 3: Safe-area inset support (env(safe-area-inset-top)) on mobile header, sidebar, main content
  - iOS standalone/PWA mode: header buttons now tappable below notch/status bar
  - Desktop layout unaffected (safe-area evaluates to 0px)
  - ZIP rebuilt: darts-kiosk-v1.7.3-windows.zip (1.6 MB)
- v1.9.0: Playwright Native WS Observer (2026-03-11)
  - CRITICAL FIX: Replaced JS injection (page.evaluate) with Playwright page.on('websocket')
  - Old approach was fundamentally broken: WS connections existed BEFORE JS injection ran
  - New approach captures ALL WS frames at network level regardless of connection timing
  - Console capture now uses add_init_script (runs BEFORE page JS loads)
  - Frame classifier: match_finished_matchshot, match_finished_winner, match_finished_state, etc.
  - New /api/kiosk/{board_id}/ws-diagnostic endpoint for real-time event stream debugging
  - Logging: every match-relevant WS frame logged with channel, interpretation, payload fields
  - All tests passing: 12/12 (iteration_33)
  - ZIP rebuilt
- v1.9.1: False Lock Fix + Chrome Profile Fix (2026-03-11)
  - CRITICAL FIX: _classify_frame was too aggressive — state:finished and gameWinner triggered false match_finished
  - Now ONLY matchshot and matchWinner trigger match_finished (true match-end signals)
  - state:finished -> game_state_finished (logged but does NOT trigger lock — could be leg finish)
  - gameWinner removed from match-end signals (leg winner != match winner)
  - Chrome profile path unified: data/chrome_profile/BOARD-1 everywhere (no more kiosk_chrome_profile)
  - Profile diagnostics: logs Default_exists, Cookies_exists, Extensions_exists on browser launch
  - All tests passing: 19/19 (iteration_34)
- v1.9.2: Chrome Profile Lock Fix + Observer Stability (2026-03-11)
  - ROOT CAUSE 1: start.bat launched kiosk UI Chrome with SAME user-data-dir as Playwright observer
  - FIX: start.bat uses separate profile (data/kiosk_ui_profile) for kiosk UI Chrome
  - FIX: Safety check _check_profile_locked() before Playwright launch (lock files + process detection)
  - FIX: Cookie diagnostics checks Default/Cookies AND Default/Network/Cookies
  - ROOT CAUSE 2: Observer Chrome used --kiosk mode, which auto-exits on page close/crash
  - FIX: Observer Chrome now uses --start-maximized instead of --kiosk + --start-fullscreen
  - FIX: Lifecycle event handlers: page.on('close'), page.on('crash'), context.on('close')
  - FIX: Post-launch health checks at 3s, 5s, 10s verify page stays alive
  - FIX: Observe loop browser health check (BROWSER DEAD logging + loop break)
  - FIX: Window manager logs ALL Chrome window titles during enumeration (diagnostics)
  - FIX: Window manager explicitly skips windows with 'autodarts' in title (SKIP log)
  - All tests passing: 26/26 (iteration_36)

## Remaining Backlog
### P1
- [ ] Autodarts DOM Selector Tests (validate selectors against live Autodarts site)

### P2
- [ ] Chromium Extension as alternative to Playwright observer
- [ ] PWA Install Prompt for public leaderboard page
