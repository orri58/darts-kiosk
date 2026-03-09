# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN. Must behave like a real arcade machine on Windows kiosk PCs.

## Architecture
- **Arcade Machine Runtime**: On unlock, system Chrome opens Autodarts fullscreen. Kiosk window is HIDDEN via Win32 API. Separate always-on-top credits overlay stays visible. On lock, Chrome closes, kiosk window restored to foreground.
- **Persistent Chrome Profile**: Uses Playwright `launch_persistent_context` with `channel="chrome"` and `ignore_default_args=["--enable-automation"]`. Preserves Google/Autodarts login. No automation banner.
- **Window Manager**: `window_manager.py` uses Win32 ctypes to hide/restore the kiosk Chrome window.
- **Credits Overlay**: Separate Python/tkinter window, always-on-top, click-through, transparent. Polls backend API every 3s.
- **Tech Stack**: FastAPI + SQLAlchemy/SQLite (backend), React + Tailwind/Shadcn (frontend)

## Observer State Machine & Session-End Logic
```
States: closed, idle, in_game, finished, unknown, error

Transitions and callbacks:
  * → in_game:        _on_game_started   → credit decremented
  in_game → finished: _on_game_ended("finished")  → check lock, create match result
  in_game → idle:     _on_game_ended("aborted")   → check lock, no refund
  finished → idle:    _on_game_ended("post_finish_check") → safety net

Lock decision (in _on_game_ended):
  per_game:  credits_remaining <= 0 → lock
  per_time:  now >= expires_at → lock

Session-end chain (when should_lock=True):
  1. session.status = FINISHED, board.status = LOCKED
  2. broadcast board_status=locked
  3. asyncio.create_task(_safe_close_observer(board_id))
     → observer_manager.close(board_id)
     → Chrome closed, kiosk window restored
```

## All Implemented Features
- v1.0-1.5: Core Kiosk, Admin, Auth, Boards, Pricing, Sessions, Stammkunde, QR, Leaderboards, Sound, i18n, White-Label, Update System, Observer Mode
- v1.5.1: Windows Playwright Fix (ProactorEventLoop)
- v1.6.0: Arcade Machine Runtime (overlay, window management)
- v1.6.1: Runtime UX Fixes (automation banner, window hiding, profile reuse)
- v1.6.2: Session-End Logic Fix
  - Unified _on_game_ended(board_id, reason) for ALL game-end scenarios
  - New abort handler: in_game → idle triggers lock check
  - _safe_close_observer with explicit error logging
  - New /simulate-game-abort test endpoint
  - Explicit logging: transition_detected, session_end_decision, board_lock_triggered, browser_close_triggered

## Remaining Backlog
### P2
- [ ] Autodarts DOM Selector Tests (stability against UI changes)
- [ ] Chromium extension for Autodarts overlay
- [ ] PWA Install Prompt for public leaderboard
