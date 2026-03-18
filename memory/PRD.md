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

## Finalization Chain (v2.7.0)
```
finalize_match(board_id, trigger):
  GUARDS:
    1. _finalizing guard (in-flight)
    2. _finalized guard (already done)
    3. _last_finalized_match guard (same match_id → SKIP_DUPLICATE_FINALIZE)
  LOGIC:
    4. [CREDIT]    Deduct credit (finished/aborted/manual=yes, crashed=no)
    5. [MATCH_ID]  Store match_id → _last_finalized_match[board_id]
    6. [LOCK]      should_lock = credits_remaining <= 0
    7. [TEARDOWN]  should_teardown = should_lock
    8. [DELAY]     ONLY for trigger="finished" (4s player sees result)
    9. [OBSERVER]  if should_teardown: close browser
                   else: OBSERVER_KEPT_ALIVE (next game ready)
    10.[BROADCAST] Sound + credit_update events
    11.[FINALIZED] Mark as finalized
  FINALLY (guaranteed):
    12.[KIOSK_UI]  return_to_kiosk_ui() ALWAYS runs

Observer Post-Finalize (credits > 0):
  1. MATCH_FINALIZED_ONCE match_id=...
  2. AUTODARTS_RETURN_TO_HOME → navigate to lobby (3 fallbacks)
  3. Full state reset: ws_state, stable_state=IDLE, all flags cleared
  4. OBSERVER_RESET_FOR_NEXT_GAME done
  5. READY_FOR_NEXT_GAME match_id=...

Observer Duplicate Prevention:
  - _last_finalized_match_id checked in _update_ws_state
  - Match END signals for same match → SKIP_DUPLICATE_FINALIZE
  - Abort signals for same match → SKIP_DUPLICATE_FINALIZE
  - Reset on open_session and new game start
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
- v1.9.3: Observer Page Management Fix (2026-03-11)
  - ROOT CAUSE: launch_persistent_context() restores previous session tabs; pages[0] is unreliable
  - Observed: Chrome window showed about:blank while Playwright thought it navigated to Autodarts
  - FIX: Always create FRESH page via context.new_page() — never reuse pages[0]
  - FIX: Log all existing pages + URLs after context launch (diagnostic)
  - FIX: Close all old/stale pages (about:blank, restored tabs) after navigation
  - FIX: Final page inventory logged with (OBSERVED) marker
  - FIX: about:blank detection — logs NAVIGATION FAILED if still on blank after goto
  - FIX: --disable-session-crashed-bubble added to Chrome args
  - All tests passing: 25/25 (iteration_37)
- v1.10.0: Gotcha Mode Support + Match Activity Detection (2026-03-11)
  - ROOT CAUSE: Real Autodarts Gotcha matches end via delete/not-found, not matchshot/matchWinner
  - ROOT CAUSE: match_active was never set — observer only recognized explicit "state: active"
  - FIX 1: match_active now detected from throw/turn/score data (turn_transition, game_event)
  - FIX 2: New classifications: match_deleted, board_match_deleted, match_not_found
  - FIX 3: Teardown signals (delete/not-found) trigger match_finished ONLY if match was active
  - FIX 4: _extract_match_id() tracks match UUID from channel names
  - FIX 5: Observer Chrome uses --start-fullscreen (F11-style, not --kiosk or --start-maximized)
  - FIX 6: --disable-session-crashed-bubble added to Chrome args
  - WSEventState.reset() now also clears last_match_id
  - All tests passing: 35/35 (iteration_38)
- v2.0.0: Complete State Machine Rewrite (2026-03-11)
  - Entire _classify_frame and _update_ws_state rewritten based on real board PC WS diagnostics
  - Match START: event=turn_start or event=throw → match_active=True
  - Match END: game_shot+body.type=match OR finished=true OR gameFinished=true → match_finished=True
  - Post-match: event=delete → full reset (match removed from server, return to lobby)
  - REMOVED old classifications: match_deleted, board_match_deleted, match_not_found, match_started, game_state_finished, turn_transition, game_event, match_state, match_related
  - Credit deduction moved from game START to game END (only on reason=finished, aborted games free)
  - Fast-track debounce: authoritative finish triggers skip normal 3-poll debounce (1 poll)
  - Helpers: _extract_event, _extract_body_type, _extract_bool_field for robust payload parsing
  - _merge_detection simplified (no more ROUND_TRANSITION from WS)
  - All tests passing: 55/55 (iteration_39)
- v2.0.1: Observer Lifecycle Null-Safety (2026-03-11)
  - ROOT CAUSE: close_session() runs via create_task concurrent with observe loop
  - _page set to None while loop/health checks still accessing it → NoneType errors
  - FIX: _page_alive() null-safe helper (checks page and context not None and not closed)
  - FIX: close_session() idempotent via _closing guard (prevents double close)
  - FIX: _cleanup() logs PAGE_SET_NONE, CONTEXT_SET_NONE for full traceability
  - FIX: observe loop stops cleanly with stop_reason (page_not_alive, stopping_flag, cancelled)
  - FIX: _read_console_state returns None when page not alive (no evaluate on dead page)
  - FIX: _detect_state_dom returns UNKNOWN when page not alive
  - FIX: post-launch health checks null-safe
  - FIX: _closing reset in open_session for re-opens
  - All tests passing: 33/33 (iteration_40)
- v2.1.0: Central finalize_match Path (2026-03-11)
  - ROOT CAUSE: Duplicated logic between _on_game_ended and manual end-game
  - Observer close_session mixed Playwright and WindowManager, credits not deducted
  - NEW: finalize_match(board_id, trigger) — single function for ALL end scenarios
  - Steps: credit deduction → board lock → observer close (Playwright) → kiosk restore (WindowManager)
  - Credit logic INDEPENDENT of browser close success (DB first, then browser)
  - Triggers: finished (credit deducted), manual (credit deducted), aborted (free)
  - _finalizing set prevents concurrent finalize calls for same board
  - _on_game_ended: thin wrapper, schedules finalize_match via create_task
  - Observer close_session: ONLY Playwright (no window_manager calls)
  - _safe_close_observer: REMOVED (replaced by finalize_match)
  - Manual end-game endpoint: uses finalize_match("manual") directly
  - All tests passing: 42/42 (iteration_41)
- v2.2.0: Finalize Match Refactor — Conditional Teardown (2026-03-11)
  - ROOT CAUSE 1: Observer was ALWAYS closed after game end, even with credits remaining
  - ROOT CAUSE 2: FINISHED→IDLE triggered second finalize_match via "post_finish_check"
  - ROOT CAUSE 3: No centralized credit policy function
  - FIX 1: _should_deduct_credit(trigger) — centralized policy (finished/manual=deduct, aborted=free)
  - FIX 2: should_teardown flag — observer ONLY closed when credits=0 or trigger=manual
  - FIX 3: OBSERVER_KEPT_ALIVE when credits remain (observer stays for next game)
  - FIX 4: Removed post_finish_check from observer (FINISHED→IDLE = no re-finalize)
  - FIX 5: try/finally ensures _finalizing guard is always released (even on exception)
  - FIX 6: Manual stop always locks board and tears down (session ends)
  - FIX 7: Detailed [FINALIZE] logging: START/END, CREDIT_DEDUCTED/FREE, LOCK_DECISION, OBSERVER_CLOSE/KEPT_ALIVE
  - Verified full 3-game loop: 3→2→1→0 with correct deduction, lock, and teardown at each step
  - All tests passing: 47/47 (iteration_42)
- v2.3.0: Finalize Match — Synchronous + Self-Call Deadlock Fix (2026-03-11)
  - ROOT CAUSE 1: create_task race condition — finalize ran async, old finalize could close NEW observer after re-unlock
  - ROOT CAUSE 2: close_session deadlock — called from within observe_task tried to cancel/await itself
  - ROOT CAUSE 3: No _finalized guard — duplicate WS finish signals triggered multiple finalizations
  - ROOT CAUSE 4: Observe loop continued polling after finalize, causing ~20s delay until stopping_flag
  - FIX 1: _on_game_ended directly AWAITS finalize_match (no asyncio.create_task)
  - FIX 2: close_session detects self-call via asyncio.current_task(), skips cancel on self-call
  - FIX 3: _finalized[board_id] dict blocks duplicate WS signals, manual trigger bypasses it
  - FIX 4: Observer _finalized flag on instance, reset on open_session and IN_GAME transition
  - FIX 5: Observe loop breaks IMMEDIATELY after finalize sets _stopping (no extra polls)
  - FIX 6: _cleanup logs PAGE_CLOSE_DONE, CONTEXT_CLOSE_DONE, PLAYWRIGHT_STOP_DONE
- v2.4.0: Session Finalization Overhaul — Kiosk-tauglich (2026-03-12)
  - NEUE BUSINESS-REGEL: Abbruch/Delete zieht jetzt auch 1 Credit ab
  - Credit-Policy: finished=ja, aborted=ja, manual=ja, crashed=nein
  - Lock-Logik: NUR wenn credits<=0 nach Abzug (nie bei verbleibenden Credits)
  - 4-Sekunden Delay vor Observer-Close (Spieler sieht Ergebnis)
  - should_teardown=True IMMER (ein Observer pro Spiel)
  - Timeout-Schutz: asyncio.wait_for(finalize_match, timeout=15s)
  - NEU: watchdog_service.py — Background-Task überwacht Observer-Gesundheit
    - Auto-Restart bei Crash: Observer tot aber Session aktiv → Recovery
    - Zombie-Cleanup: Observer offen aber keine Session → schließen
    - Prüft alle 5 Sekunden: page alive, observer open, session consistent
  - ObserverManager.open: Dead Observer werden vor neuem Start bereinigt
  - Alle Tests passing: 16/16 (iteration_45)
- v2.5.0: Abort Sofort, Finish mit Delay, Kiosk-Maske zurück (2026-03-12)
  - PROBLEM 1: Abort/Delete ging durch Debounce-Polls statt sofort
  - PROBLEM 2: Kiosk-UI kam nach Finalize nicht zurück
  - PROBLEM 3: Delay auch für Abort (falsch)
  - FIX 1: _abort_detected Flag im Observer → Sofort-Finalize ohne Debounce (471ms statt ~20s)
  - FIX 2: Delay NUR für trigger="finished" (4s), nicht für abort/crashed (0s)
  - FIX 3: Neue return_to_kiosk_ui(board_id, should_lock) — IMMER nach Finalize aufgerufen
  - FIX 4: Detailliertes Credit-Log: credit_before, consume_credit, credit_after
  - FIX 5: Debounce-Skip wenn _finalized oder _abort_detected (keine Doppel-Finalisierung)
  - Timing verifiziert: Abort=471ms, Finished=4440ms
  - Alle Tests passing: 15/15 (iteration_46)
- v2.6.0: Conditional Teardown + Abort Fast-Path + Kiosk-UI Finally (2026-03-12)
  - BUG 1: Observer/Browser wurde nach JEDEM Spiel geschlossen, auch wenn Credits übrig
  - BUG 2: Abort-Erkennung ging immer noch durch sleep/poll (nicht sofort)
  - BUG 3: return_to_kiosk_ui() war nicht in finally — bei Teilfehler keine UI-Wiederherstellung
  - FIX 1: should_teardown = should_lock (Observer NUR schließen wenn Board gesperrt wird)
  - FIX 2: OBSERVER_KEPT_ALIVE wenn Credits > 0 (kein Browser-Neustart zwischen Spielen)
  - FIX 3: Abort-Fast-Path ganz am Anfang der observe_loop, VOR asyncio.sleep()
  - FIX 4: return_to_kiosk_ui() in try...finally Block (GARANTIERT, auch bei Teilfehler)
  - FIX 5: Detaillierte Logs: OBSERVER_KEPT_ALIVE, finally: restoring/restored, ABORT_FAST_PATH
  - Geänderte Dateien: backend/routers/kiosk.py, backend/services/autodarts_observer.py
  - Entscheidungslogik: should_teardown=should_lock (nur bei credits=0 oder Crash)
  - Getestet: 3-Spiel-Zyklus (3→2→1→0) mit korrektem Credit-Abzug und Teardown
  - ZIP neu gebaut: darts-kiosk-v2.6.0-windows.zip (2.1 MB)
- v2.7.0: Navigate-to-Home + Duplicate Match Guard + Full Observer Reset (2026-03-12)
  - BUG 1: Nach Finish mit Credits blieb Autodarts auf der /matches/{id} Ergebnis-Seite
  - BUG 2: Doppelfinalisierung möglich (gleiche Match-ID → zweiter Kreditabzug)
  - BUG 3: Observer-State (ws_match_finished, stable_state) nach Finish nicht vollständig zurückgesetzt
  - FIX 1: _navigate_to_home() — navigiert Autodarts-Page zurück zu Home/Lobby nach Spielende
           3-stufiger Fallback: Autodarts-URL → Base-URL → Page-Reload
  - FIX 2: _last_finalized_match_id (Observer) + _last_finalized_match (kiosk.py)
           → SKIP_DUPLICATE_FINALIZE wenn gleiche Match-ID nochmal finished/delete liefert
           → Kredit wird pro Match genau 1x abgezogen
  - FIX 3: Observer-Reset nach credits>0 Finish: alle WS-Flags, stable_state=IDLE,
           exit_polls=0, abort_detected=False, ws_state.reset()
  - Logs: MATCH_FINALIZED_ONCE, SKIP_DUPLICATE_FINALIZE, AUTODARTS_RETURN_TO_HOME (start/success/fallback),
          OBSERVER_RESET_FOR_NEXT_GAME, READY_FOR_NEXT_GAME
  - Geänderte Funktionen:
    - kiosk.py: _finalize_match_inner(), _on_game_started()
    - autodarts_observer.py: _navigate_to_home() [NEU], _update_ws_state(), _observe_loop()
  - Getestet: 3-Spiel-Zyklus + Doppelfinalisierung-Prävention
  - ZIP: darts-kiosk-v2.7.0-windows.zip (2.1 MB)
- v2.7.1: Window-Focus-Fix — Kiosk immer im Vordergrund nach Matchende (2026-03-12)
  - BUG: Nach Finish mit Credits blieb schwarzes Chrome-/Observer-Fenster im Vordergrund
  - URSACHE: Observer-Loop navigierte NACH return_to_kiosk_ui → Chrome überdeckte Kiosk
  - FIX 1: Reihenfolge korrigiert in finalize_match:
    1. AUTODARTS_RETURN_TO_HOME (Chrome navigiert zu Lobby)
    2. AUTODARTS_WINDOW_HIDE (Chrome minimieren via Win32 SW_MINIMIZE)
    3. return_to_kiosk_ui (Kiosk restore + force foreground) ← LETZTER Schritt
  - FIX 2: _navigate_to_home() aus Observer-Loop entfernt → nur noch von finalize_match gesteuert
  - FIX 3: Neuer force_kiosk_foreground() mit BringWindowToTop + Alt-Trick (zweiter Pass nach 400ms)
  - FIX 4: minimize_observer_window() minimiert alle Chrome-Fenster die NICHT DartsKiosk sind
  - Geänderte Dateien:
    - window_manager.py: minimize_observer_window() [NEU], force_kiosk_foreground() [NEU],
                         _win32_minimize_non_kiosk_chrome() [NEU], _win32_force_foreground() [NEU]
    - kiosk.py: _finalize_match_inner() (navigate+minimize vor finally), return_to_kiosk_ui() (double-focus)
    - autodarts_observer.py: _observe_loop() (_navigate_to_home entfernt aus beiden Pfaden)
  - Logs: AUTODARTS_WINDOW_HIDE start/success, KIOSK_FOCUS_RESTORE start/success,
          FINAL_VISIBLE_WINDOW, FINAL_FOREGROUND_WINDOW
  - ZIP: darts-kiosk-v2.7.1-windows.zip (2.1 MB)
- v2.8.0: Observer-Lifecycle Serialisierung + Chrome-Profil-Lock (2026-03-12)
  - PROBLEM: Race Conditions zwischen start/stop/watchdog/recovery
  - PROBLEM: Chrome-Profil-Lock blockierte Neustart ("Wird in einer aktuellen Browsersitzung geöffnet")
  - PROBLEM: BROWSER LAUNCH SUCCESS geloggt obwohl Health-Check danach fehlschlug
  - FIX 1: Per-Board asyncio.Lock in ObserverManager (serialisiert open/close/recovery)
           Logs: lifecycle_lock acquiring/acquired/released board=X
  - FIX 2: LifecycleState enum (CLOSED/STARTING/RUNNING/STOPPING/ERROR)
           Logs: lifecycle_state: X → Y (gen=N)
  - FIX 3: _find_chrome_pids_for_profile + _kill_pids (via PowerShell/pgrep)
           Erkennt + tötet Chrome-Prozesse mit exaktem user-data-dir Match
           Logs: chrome_pid=X matched user-data-dir=Y, CHROME_KILL pid=X success
  - FIX 4: Health-Check VOR SUCCESS-Log — SUCCESS nur bei page_alive=True
           Bei Health-Failure → lifecycle=ERROR, cleanup
  - FIX 5: session_generation ID — stale generation check in health loop
  - FIX 6: Watchdog lifecycle-aware: skip STARTING/STOPPING, grace period (20s),
           cooldown (15s base), exponential backoff (2^failures, max 16x)
           Logs: watchdog skipped (transitional), recovery throttled
  - Geänderte Dateien:
    - autodarts_observer.py: LifecycleState enum, _set_lifecycle(), _find_chrome_pids_for_profile(),
      _kill_pids(), _check_profile_locked() refactored, open_session(), close_session(),
      ObserverManager mit per-board locks
    - watchdog_service.py: komplett neu geschrieben (lifecycle-aware, cooldown, backoff)
  - ZIP: darts-kiosk-v2.8.0-windows.zip (2.1 MB)
- v2.9.0: Desired State + Close Reason + Auth Detection (2026-03-12)
  - PROBLEM 1: Watchdog startete Recovery nach manuellem Lock/Stop (desired_state fehlte)
  - PROBLEM 2: Chrome landete auf login.autodarts.io → health failure → aggressive Recovery-Schleife
  - FIX 1: desired_state pro Board ("running" | "stopped") in ObserverManager
    - unlock → desired_state=running
    - lock → desired_state=stopped
    - session_end (credits=0) → desired_state=stopped
    - credits>0 → desired_state bleibt running
  - FIX 2: close_reason pro Board (manual_lock, session_end, watchdog_recovery, admin_stop, shutdown)
    - Watchdog suppressed Recovery bei intentional close reasons
  - FIX 3: AUTH_REQUIRED LifecycleState
    - login.autodarts.io / /login / /auth Erkennung nach Navigation + im Health-Check
    - Kein observe loop start, kein kiosk hide bei auth page
    - Watchdog suppressed Recovery bei auth_required
    - Log: AUTH_REQUIRED / AUTH_REDIRECT_DETECTED url=...
  - FIX 4: Watchdog Entscheidungslogik (5 Checks):
    1. desired_state != running → skip
    2. transitional (starting/stopping) → skip
    3. auth_required → skip
    4. intentional close_reason → skip
    5. grace period / cooldown → skip
  - Geänderte Dateien:
    - autodarts_observer.py: LifecycleState.AUTH_REQUIRED, close_session(reason=...), 
      ObserverManager.set_desired_state/get_desired_state/get_close_reason, auth redirect detection
    - watchdog_service.py: desired_state + close_reason checks, INTENTIONAL_CLOSE_REASONS set
    - boards.py: set_desired_state bei lock/unlock
    - kiosk.py: stop_observer_for_board(reason=...), set_desired_state=stopped bei session_end
  - ZIP: darts-kiosk-v2.9.0-windows.zip (2.1 MB)
- v2.9.1: Lifecycle Stability Patch — Final (2026-03-12)
  TASK 1 — WATCHDOG RECOVERY RULES:
    - _should_attempt_recovery() als single decision point (9 explizite Regeln)
    - CLOSED wird NIEMALS recovered (immer intentional)
    - Nur ERROR+desired=running+unhealthy → Recovery
    - Jede Entscheidung geloggt: [WATCHDOG] evaluate board=... + skip reason=...
  TASK 2 — LIFECYCLE SEMANTICS:
    - Profile-Lock-Failure → lifecycle=ERROR (nicht undefiniert)
    - Auth-Redirect → close_reason="auth_required" (zusätzlich zu lifecycle)
    - Generation-Guard im Health-Check (stale gen → abort)
  TASK 3 — PAGE/CONTEXT CLOSE CALLBACKS:
    - PAGE_CLOSED_EXPECTED vs PAGE_CLOSED_UNEXPECTED (lifecycle-aware)
    - CONTEXT_CLOSED_EXPECTED vs CONTEXT_CLOSED_UNEXPECTED
    - Stopping/Closing/Closed → EXPECTED, Running → UNEXPECTED
  TASK 4 — MULTI-CREDIT FINALIZE LOGS:
    - [SESSION] finalize decision board=X credit_before=N credit_after=M should_lock=F should_teardown=F desired_state=running lifecycle=running
    - [RETURN_HOME] start board=X lifecycle=running desired=running page_closed=False context_closed=False
    - [RETURN_HOME] success board=X url=https://play.autodarts.io/ lifecycle=running
  TASK 5 — AUTH REDIRECT:
    - close_reason="auth_required" gesetzt bei Auth-Erkennung
    - Watchdog: skip reason=auth_required
  TASK 6 — WINDOW MANAGER ISOLATION:
    - Verifiziert: Window-Failures escalieren NICHT zu Lifecycle-Failures
  TASK 7 — CRASH ESCALATION:
    - 3 Failures in 5 Minuten → Block für 10 Minuten
    - [WATCHDOG] recovery blocked BOARD-1 failures=3 window=300s blocked_until=...
    - Exponential backoff bei wiederholten Failures
  Geänderte Dateien:
    - autodarts_observer.py: Page/Context-Close callbacks, Auth close_reason, Profile-Lock lifecycle
    - kiosk.py: finalize decision log, RETURN_HOME logs
    - watchdog_service.py: komplett neu (_should_attempt_recovery, escalation, blocking)
  ZIP: darts-kiosk-v2.9.1-windows.zip (2.1 MB)
- v2.9.2: Auth-State Lifecycle Guard (2026-03-12)
  - BUG: AUTH_REQUIRED state was overwritten to ERROR in health-check failure path
  - FIX 1: Guard `if self._lifecycle_state != LifecycleState.AUTH_REQUIRED` before setting ERROR
  - FIX 2: Page/context close callbacks treat auth_required as expected closure
  - FIX 3: Kiosk hide deferred until AFTER health check confirms valid session
  - ZIP: darts-kiosk-v2.9.2-windows.zip (2.1 MB)
- v2.9.3: Auth-State Consistency Fix (2026-03-12)
  - BUG 1: Health-check auth path (Path B) left observer state="idle" while lifecycle="auth_required"
  - BUG 2: ObserverManager close_reason not propagated from observer instance during auth detection
  - FIX 1: Path B now also sets _set_state(ObserverState.ERROR) + browser_open=False
  - FIX 2: ObserverManager.open() propagates obs._close_reason to manager dict after open_session
  - Result: Both auth paths now return identical API state: state=error, lifecycle=auth_required, close_reason=auth_required
  - ZIP: darts-kiosk-v2.9.3-windows.zip (2.1 MB)
- v2.9.4: Multi-Credit Post-Match UI Orchestration Fix (2026-03-12)
  - BUG 1: Keep-alive path (credits>0) minimized Autodarts + restored kiosk = black screen over Autodarts
  - BUG 2: return_to_kiosk_ui() ran unconditionally in finally block, even on keep-alive
  - BUG 3: close_reason="session_end" persisted after keep-alive, causing stale watchdog state
  - FIX 1 (TASK 1): Split finalize into explicit SESSION-END and KEEP-ALIVE branches
    - Session-end: close observer → minimize Autodarts → restore kiosk (existing behavior)
    - Keep-alive: navigate home → ensure Autodarts foreground → NO kiosk restore
  - FIX 2 (TASK 2): New ensure_autodarts_foreground() in window_manager.py
    - Finds Autodarts Chrome window, restores if minimized, forces to foreground
    - Does NOT touch kiosk window
  - FIX 3 (TASK 3): clear_close_reason() in ObserverManager
    - Clears stale close_reason on keep-alive path
    - Clears both manager dict and observer instance
  - FIX 4 (TASK 4): Watchdog now sees clean state after keep-alive:
    desired=running, lifecycle=running, close_reason=None
  - FIX 5 (TASK 5): Explicit branch-selection logs:
    [SESSION] finalize branch ... branch=keep_alive / branch=session_end
    [KEEP_ALIVE_UI] start/skip_kiosk_restore/done
    [KIOSK_UI] session_end_restore start/done
    [SESSION] keep_alive_reset ... close_reason_cleared=True
  - Geänderte Dateien:
    - backend/routers/kiosk.py: _finalize_match_inner (branch split, conditional finally)
    - backend/services/window_manager.py: ensure_autodarts_foreground(), _win32_foreground_autodarts()
    - backend/services/autodarts_observer.py: ObserverManager.clear_close_reason()
  - ZIP: darts-kiosk-v2.9.4-windows.zip (2.1 MB)
- v3.0.0: Hard-Kiosk Deployment + Automated Installer (2026-03-12)
  - FEATURE: Windows Hard-Kiosk Modus — PC bootet direkt ins Darts-System
  - Erstellt:
    - setup_kiosk.bat: Vollautomatischer Installer (10-Schritte-Prozess)
      - Admin-Check, Python/Chrome-Pruefung, Datei-Kopie, venv-Setup
      - Erstellt Kiosk-User, konfiguriert Auto-Login
      - Shell-Ersetzung (explorer.exe → kiosk_shell.vbs)
      - User-spezifische Haertung (DisableTaskMgr, NoDesktop, NoRun, NoWinKeys)
      - Firewall-Regel, Power-Management, Benachrichtigungen deaktiviert
    - kiosk_shell.vbs: Shell-Ersetzung (User-spezifisch)
      - Kiosk-User → startet Launcher unsichtbar
      - Admin-User → startet explorer.exe normal
      - Bleibt alive (Windows loggt sonst aus)
    - darts_launcher.bat: Service-Supervisor
      - Startet Backend + Chrome Kiosk + Credits-Overlay
      - Watchdog-Loop alle 10s: Backend-Health + Chrome-Prozesscheck
      - Auto-Restart bei Absturz (max 10, dann 60s Cooldown)
    - maintenance.bat: Wartungs-Tool
      - Passwort-geschuetzt (SHA256-Hash via PowerShell)
      - Explorer temporaer starten, Dienste stoppen/starten
      - Logs anzeigen, Update, Deinstallation, Reboot
    - uninstall_kiosk.bat: Vollstaendiger Rollback
      - Shell → explorer.exe, Auto-Login aus, Policies entfernt
      - Firewall-Regel entfernt, Optional: User loeschen
    - README_KIOSK.md: Vollstaendige Dokumentation
  - Build-Script aktualisiert: kiosk/ Verzeichnis in Windows-Bundle integriert
  - ZIP: darts-kiosk-v3.0.0-windows.zip (2.1 MB)
- v3.0.1: Installer Fix - Source Root + Shell Command (2026-03-12)
  - BUG 1: SOURCE_DIR zeigte auf kiosk\ Subfolder statt Projekt-Root
    - setup_kiosk.bat suchte backend/frontend unter kiosk\ -> Kopie schlug fehl
    - FIX: Erkennung ob Script aus \kiosk Subfolder laeuft, dann Parent-Dir verwenden
  - BUG 2: Winlogon Shell war raw .vbs Pfad (kein gueltiger Executable-Befehl)
    - Windows konnte kiosk_shell.vbs nicht als Shell starten
    - FIX: Shell = wscript.exe "C:\DartsKiosk\kiosk_shell.vbs"
  - BUG 3: VBS startete .bat direkt (kann Probleme mit Shell-Kontext verursachen)
    - FIX: WshShell.Run "cmd.exe /c ""darts_launcher.bat""", 0, False
  - BUG 4: Kaputte ANSI-Escape-Sequenzen ohne ESC-Zeichen
    - FIX: Alle ANSI-Codes entfernt, reines ASCII
  - BUG 5: Keine Debug-Ausgabe bei Pfaderkennung + Shell-Registry
    - FIX: [DEBUG] Logs fuer SCRIPT_DIR, SOURCE_DIR, INSTALL_DIR, Shell-Wert
  - Geaenderte Dateien: kiosk/setup_kiosk.bat, kiosk/kiosk_shell.vbs
  - ZIP: darts-kiosk-v3.0.1-windows.zip (2.1 MB)
- v3.0.2: Boot/Runtime Stability - Anti-Black-Screen Architecture (2026-03-12)
  - ROOT CAUSE: Black screen because shell launched darts_launcher.bat hidden,
    backend/chrome failed silently (Python not in PATH, no permissions, no fallback)
  - NEW ARCHITECTURE:
    - Scheduled Task "DartsKioskLauncher" = PRIMARY startup (at logon, elevated)
    - kiosk_shell.vbs = SAFETY NET (readiness gate + fallback recovery)
    - darts_launcher.bat = Backend/Chrome supervisor (triggered by scheduled task)
  - TASK 1 (Startup Architecture):
    - Installer creates schtasks "DartsKioskLauncher" at logon with highest privileges
    - Shell VBS triggers task AND starts launcher as fallback if task fails
    - No UAC prompt needed at kiosk boot
  - TASK 2 (Readiness Gate):
    - VBS waits up to 90s for backend health (PowerShell Invoke-WebRequest)
    - Then waits up to 30s for chrome.exe to appear (WMI process check)
    - If Chrome missing but backend OK: VBS starts Chrome directly as fallback
    - NEVER leaves permanent black screen
  - TASK 3 (Failsafe Recovery):
    - If startup fails: opens maintenance.bat visibly
    - If maintenance.bat missing: opens visible cmd with recovery instructions
    - User always gets a visible escape path
  - TASK 4 (Hardening Fix):
    - Force-creates kiosk user profile via PowerShell (Start-Process with Credential)
    - NTUSER.DAT now available immediately for policy application
    - Grants file permissions via icacls (kiosk user -> full access to install dir)
  - TASK 5 (Boot Logging):
    - Unified kiosk_boot.log with [BOOT] prefixed entries from both VBS and launcher
    - Every startup stage logged: shell start, task trigger, health wait, chrome wait, fallback
  - TASK 6 (Scheduled Task):
    - Created: schtasks /create /tn "DartsKioskLauncher" /sc onlogon /rl highest
    - Uninstaller: schtasks /delete /tn "DartsKioskLauncher" /f
  - TASK 7 (No Black Screen Before Chrome):
    - VBS only enters keep-alive after Chrome confirmed running
    - If Chrome not detected: explicit fallback path (never silent failure)
  - Geaenderte Dateien: alle 4 kiosk/ Dateien komplett ueberarbeitet
  - ZIP: darts-kiosk-v3.0.2-windows.zip (2.1 MB)
- v3.0.3: VBScript Syntax Fix + Safe Shell Fallback (2026-03-13)
  - ROOT CAUSE: kiosk_shell.vbs used standalone "GoTo" which is invalid in VBScript
    (only valid in VBA). Windows Script Host error 800A0400 at line 246.
    Because Shell=kiosk_shell.vbs and explorer was replaced, result = black screen.
  - FIX: Complete VBS rewrite - minimal, linear flow, no GoTo, no Sub mid-flow
  - TASK 1 (Syntax): Pure VBScript, all Dim at top, linear control flow, proper quote escaping
  - TASK 2 (Logging): kiosk_shell.log with [KIOSK_SHELL] prefixed entries for every stage
  - TASK 3 (Failsafe): If launcher missing -> log + explorer.exe, never black screen
  - TASK 4 (Debug): KIOSK_DEBUG=1 in kiosk_config.bat -> launcher runs visible (cmd /k, window=1)
  - TASK 5 (Encoding): ASCII only, no non-ASCII characters, no BOM
  - Geaenderte Dateien: kiosk/kiosk_shell.vbs (rewrite), kiosk/setup_kiosk.bat (KIOSK_DEBUG config)
  - ZIP: darts-kiosk-v3.0.3-windows.zip (2.1 MB)
- v3.1.0: Manual-First Deployment (Installer Deprecated) (2026-03-13)
  - DECISION: Automated kiosk installer creates more problems than it solves.
    Shell-Ersetzung, Policy-Haertung und VBS-Startup sind zu fragil.
    Neuer Ansatz: Manuelle Installation zuerst, Haertung spaeter.
  - CHANGE 1: kiosk/ -> kiosk_experimental/ im Release-Bundle
    - Alle Installer-Dateien als EXPERIMENTAL markiert
    - EXPERIMENTAL_WARNING.txt hinzugefuegt
    - Nicht mehr im primaeren Deployment-Pfad
  - CHANGE 2: MANUAL_DEPLOYMENT.md erstellt (Top-Level im Windows-ZIP)
    - Schritt-fuer-Schritt Anleitung: Entpacken, Setup, Start
    - Task Scheduler Guide (GUI + Kommandozeile)
    - Chrome Kiosk-Modus manuell
    - Backend manuell starten
    - LAN-Zugriff + Firewall
    - Energieoptionen
    - Troubleshooting
  - CHANGE 3: Build-Script aktualisiert
    - kiosk_experimental/ statt kiosk/
    - MANUAL_DEPLOYMENT.md als Top-Level-Datei
  - Empfohlener Deployment-Pfad: setup_windows.bat -> start.bat -> Task Scheduler
  - ZIP: darts-kiosk-v3.1.0-windows.zip (2.1 MB)
- v3.1.1: Final Manual-First Deployment Stabilization (2026-03-13)
  - TASK 1-3: v3.1.0 bereits erledigt (manueller Pfad, kiosk_experimental isoliert)
  - TASK 4: MANUAL_DEPLOYMENT.md finalisiert (328 Zeilen)
  - TASK 5: Optionale Haertung als separate Schritte dokumentiert:
    - Kiosk-User erstellen + Berechtigungen
    - Auto-Login per Registry
    - Taskleiste ausblenden
    - Windows Update Neustart verhindern
    - Benachrichtigungen reduzieren
    - Energieoptionen, Firewall, Chrome Vollbild
    - Klare Trennung: empfohlen vs. experimentell (NICHT empfohlen)
  - TASK 6: Runtime-Integritaet verifiziert (observer, watchdog, kiosk router unberuehrt)
  - Geaenderte Dateien: release/windows/MANUAL_DEPLOYMENT.md
  - Nicht geaendert: observer, watchdog, kiosk router, window_manager, start.bat, setup_windows.bat
  - ZIP: darts-kiosk-v3.1.1-windows.zip (2.1 MB)
- v3.2.0: Phase 1 — Kiosk Control Features (2026-03-18)
  - FEATURE 1: Autodarts Desktop Supervision (Minimal)
    - Neuer Service: backend/services/autodarts_desktop_service.py
    - Erkennt ob Autodarts.exe laeuft (Windows tasklist)
    - Startet Autodarts.exe minimiert wenn nicht aktiv
    - Kill/Restart-Funktion
    - Admin-API: GET /api/admin/system/autodarts-desktop-status
    - Admin-API: POST /api/admin/system/restart-autodarts-desktop
    - Settings-API: GET/PUT /api/settings/autodarts-desktop (exe_path, auto_start)
    - Admin UI: Status-Karte auf System > Details-Tab mit Restart-Button
    - Admin UI: Konfiguration auf Einstellungen > Kiosk-Tab (Pfad + Auto-Start)
  - FEATURE 2: Konfigurierbarer Post-Match Delay
    - Neues DB-Setting: post_match_delay (Default: {delay_ms: 5000})
    - Settings-API: GET/PUT /api/settings/post-match-delay
    - kiosk.py _finalize_match_inner() liest Delay aus DB statt Umgebungsvariable
    - Admin UI: Slider (0-15000ms) + numerisches Input auf Einstellungen > Kiosk-Tab
  - FEATURE 3: UI Credit Display Fix — "Letztes Spiel"
    - SetupScreen.js: Zeigt "Letztes Spiel" / "Last Game" wenn credits_remaining === 1
    - Neue i18n-Keys: last_game (DE: Letztes Spiel, EN: Last Game)
  - Neue i18n-Keys fuer Admin-Panel: post_match_delay, autodarts_desktop, etc. (DE + EN)
  - Alle Tests bestanden: 15/15 Backend, Frontend verifiziert
  - Keine Refactoring-Aenderungen an bestehender Logik (observer, watchdog, kiosk-chain)
- v3.2.1: Autodarts Desktop Auto-Start (2026-03-18)
  - ensure_running() Methode mit 60s Cooldown (time.monotonic)
  - Server-Startup: einmaliger Auto-Start-Check wenn auto_start=true
  - Board-Unlock: ensure_running() Check nach Observer-Start, non-blocking try/except
  - SW_SHOWMINNOACTIVE (7) + CREATE_NO_WINDOW: kein Fokus-Steal
  - Max 1 Start-Versuch pro Trigger, 60s Cooldown gegen Loops
  - Status-API erweitert um auto_start_cooldown_s
  - Keine Aenderungen an observer/watchdog/finalize/match-chain
  - Alle Tests bestanden: 13/13 Backend
- v3.2.1-release: Windows Release Build (2026-03-18)
  - darts-kiosk-v3.2.1-windows.zip (2.1 MB)
  - darts-kiosk-v3.2.1-linux.tar.gz (1.7 MB)
  - darts-kiosk-v3.2.1-source.zip (21 MB)
  - autodarts_desktop_service.py im Bundle verifiziert
  - VERSION=3.2.1 im Bundle verifiziert
- v3.2.2: Stability Hotfix (2026-03-18)
  - TASK 1: Final-Credit Lock zuverlässig — normalisierte Entscheidungslogik
    - Einzige autoritative Werte: has_remaining_credits, should_lock, should_teardown
    - Kein trigger-spezifischer Bypass möglich
    - Strukturierter Log: finalize decision + lock_enforced / keep_alive_allowed
  - TASK 2: autodarts_desktop_service gehärtet
    - is_running(): stdout-None-Guard, encoding="utf-8", errors="replace"
    - _SUBPROCESS_SAFE dict für alle subprocess.run Aufrufe
    - ensure_running() mit Exception-Guard
  - TASK 3: Admin restart endpoint NameError behoben
    - get_or_create_setting Import zu admin.py hinzugefügt
  - TASK 4: Windows subprocess decoding
    - Alle subprocess.run Aufrufe in observer, window_manager mit encoding="utf-8", errors="replace"
    - Betrifft: tasklist, taskkill, powershell, pgrep, kill, wmic
  - TASK 5: Manual lock during starting — stale-callback safe
    - _close_requested_gen Guard in Observer
    - PAGE_CLOSED / CONTEXT_CLOSED als EXPECTED wenn close requested
    - Health-check Abort bei close-intent
    - Launch-completion blockiert bei close-intent
  - TASK 6: 10/10 gezielte Tests bestanden
  - Release: darts-kiosk-v3.2.2-windows.zip (2.1 MB), verifiziert
- v3.2.3: Finalize Chain Reliability Hotfix (2026-03-18)
  - ROOT CAUSE: Observe loop exits (page died/crash) before processing accumulated ws.match_finished
  - TASK 1: Single-flight _dispatch_finalize() — exactly-once guarantee with triple guard
    - _finalize_dispatching flag (concurrent guard)
    - _finalized flag (re-dispatch guard)
    - match_id dedup (cross-cycle guard)
  - TASK 2: open_session blocked during active finalize dispatch
  - TASK 3: Full dispatch logging pipeline
    - finalize dispatch accepted/failed in kiosk.py
    - FINALIZE_DISPATCH start/complete/duplicate in observer
    - post_match_delay start/done phase logs
  - TASK 4: Authoritative decision preserved (has_remaining_credits, should_lock, lock_enforced)
  - TASK 5: Duplicate finish signal guard in _update_ws_state
    - First accepted trigger wins, subsequent MATCH_FINISH_DUPLICATE_IGNORED
  - SAFETY NETS:
    - Loop-exit safety net: if ws.match_finished but finalize never ran, dispatch on exit
    - WS-triggered deferred safety: _schedule_finalize_safety after poll_interval + 3s
  - Post-match delay now also applies to match_end_* triggers (not just "finished")
  - 17/17 tests passed (v3.2.2 + v3.2.3)
  - Release: darts-kiosk-v3.2.3-windows.zip (2.1 MB), verifiziert
- v3.2.4: Finalize Deadlock + State Corruption Hotfix (2026-03-18)
  - ROOT CAUSE: Observe loop exits at page_alive check before processing ws.match_finished.
    Observer close (_cleanup) has no timeouts, blocking finalize. Lifecycle lock contention
    between finalize and watchdog creates deadlock. Safety net gap when _stopping is True.
  - WHY TIMEOUT: _cleanup() awaits page.close()/context.close()/playwright.stop() without
    timeout bounds. If Playwright hangs, finalize blocks indefinitely holding lifecycle lock.
  - TASK 1: Priority match-end check at top of observe loop (before page_alive)
    - FINALIZE_PRIMARY_DISPATCH fires immediately when ws.match_finished detected
    - No more lost finalizes due to page death during sleep
  - TASK 2: Close path separation
    - CLOSE_PATH_RESERVED gen=... log on close entry
    - START_PATH_BLOCKED in observer_manager.open() when obs._closing
    - open_session blocks during _finalize_dispatching
  - TASK 3: Close deadlock fix
    - _cleanup() steps bounded: page=3s, context=3s, playwright=5s timeouts
    - close_session observe_task cancel bounded to 5s
    - observer_manager.close() lifecycle lock acquisition bounded to 8s with forced fallback
    - observer_manager.close inside finalize bounded to 10s
    - FINALIZE_TIMING logs for every phase (page, context, playwright, lifecycle, kiosk_restore, total)
  - TASK 4: Primary dispatch happens in observe loop, safety net logs 'skipped reason=already_reserved'
  - TASK 5: Credits never negative (all guard returns use 0), timeout returns should_lock=True,
    finalize committed log, result preserved after error
  - TASK 6: close_reason preservation — once set, never degrades to 'unknown'
  - 24/24 tests passed (v3.2.2 + v3.2.3 + v3.2.4)
  - Release: darts-kiosk-v3.2.4-windows.zip (2.1 MB), verifiziert
- v3.2.5: Immediate Finalize Dispatch + Start/Close Race Fix (2026-03-18)
  - WHY PRIMARY DISPATCH FAILED: Match-end WS signal arrived AFTER observe loop already
    exited (page died). Loop's priority check never saw ws.match_finished. Only the 7s
    deferred safety net eventually dispatched finalize.
  - HOW RACE ELIMINATED: _schedule_immediate_finalize() creates an asyncio task that
    dispatches finalize within 50ms of MATCH_FINISH_ACCEPTED. Single-flight guard ensures
    exactly-once. Safety net becomes true backup only.
  - TASK 1: _schedule_immediate_finalize() — fires within 50ms of WS match-end
  - TASK 2: Safety net logs 'skipped reason=already_reserved' when primary already ran
  - TASK 3: open_session comprehensive START_ABORTED guard (closing/stopping/finalize)
  - TASK 4: All self._page.url references null-safe, page_is_none health check
  - TASK 5: Watchdog _should_attempt_recovery blocks during close_or_finalize_in_progress,
    watchdog close bounded to 10s timeout
  - TASK 6: observer_manager.open() blocks if obs._closing (START_PATH_BLOCKED)
  - NEW EXPECTED TIMING: ~3-5s (50ms dispatch + 3s delay + close) vs ~12s before
  - 31/31 tests passed (v3.2.2-v3.2.5)
  - Release: darts-kiosk-v3.2.5-windows.zip (2.1 MB), verifiziert

- v3.3.0: P0 — Autodarts Desktop Focus-Steal Fix (2026-03-18)
  - ROOT CAUSE: Autodarts.exe stiehlt Fokus beim Starten, Kiosk-UI verdeckt
  - FIX: Zweistufiger Ansatz:
    - Stage 1: SW_SHOWMINNOACTIVE (wShowWindow=7) + CREATE_NO_WINDOW + DETACHED_PROCESS
    - Stage 2: Background-Thread mit PowerShell Win32 API Check/Correction
      - GetForegroundWindow() → Titel prüfen → ShowWindow(SW_MINIMIZE) wenn *Autodarts*
  - Focus-Correction debounced: min 10s zwischen Korrekturen (kein Flicker)
  - Background-Thread: daemon=True, blockiert Event-Loop NICHT
  - Bug-Fixes integriert:
    - NameError: get_or_create_setting Import war bereits korrekt (v3.2.2)
    - NoneType: is_running() und get_status() null-safe mit try/except
    - UnicodeDecodeError: _SUBPROCESS_SAFE mit encoding=utf-8, errors=replace
  - Keine Änderungen an observer, finalize, watchdog, auth, keep_alive
  - 18/18 Tests bestanden (Backend + Frontend)
  - Release: darts-kiosk-v3.3.0-windows.zip (2.1 MB), -linux.tar.gz (1.7 MB), -source.zip (21 MB)

## Remaining Backlog
### P1
- [ ] v3.3.0 Phase 2: Admin System Controls (Restart Backend, Reboot OS, Shutdown OS)
- [ ] v3.3.0 Phase 2: Windows Kiosk Controls (Shell Switch, Task Manager Toggle)
- [ ] v3.3.0 Phase 2: Board Wake/Standby Support (ensure Desktop running on unlock)
- [ ] Autodarts DOM Selector Tests (validate selectors against live Autodarts site)
- [ ] Hard-Kiosk-Modus als optionaler separater Schritt (nach stabiler Runtime)

### P2
- [ ] Finish Experience Safety (Post-Match Delay Verbesserung)
- [ ] Chromium Extension as alternative to Playwright observer
- [ ] PWA Install Prompt for public leaderboard page
- [ ] Persist runtime state to JSON file
