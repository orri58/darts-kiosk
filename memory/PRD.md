# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Architecture
- **Autodarts Observer MVP** (`AUTODARTS_MODE=observer`): On unlock, the backend launches Autodarts fullscreen via Playwright. The kiosk UI hands off the screen to Autodarts. Only the small credits overlay remains visible on top.
- **Master/Agent**: MASTER controls all boards, AGENTs are autonomous offline
- **Tech Stack**: FastAPI + SQLAlchemy/SQLite (backend), React + Tailwind/Shadcn (frontend)

## Observer Mode Kiosk UX Flow
```
LOCKED:   Kiosk fullscreen → locked screen visible
UNLOCK:   Playwright opens Autodarts fullscreen (covers kiosk)
          Kiosk shows minimal dark "handoff" screen behind Autodarts
          Credits overlay stays on top as small floating window
ACTIVE:   Autodarts is main app, overlay shows credits/time
          If Autodarts fails to open → FALLBACK screen with retry
END:      Autodarts closes → kiosk returns to locked screen
```

## Implemented Features

### v1.0.0 - Core
- [x] Kiosk UI, Admin Panel, JWT+PIN Auth, Boards, Pricing, Sessions
- [x] Stammkunde Mode, QR Match Links, Leaderboards, Sound Effects, i18n

### v1.1.0 - White-Label & Polish
- [x] All branding removed, PWA, Custom Kiosk Texts, Responsive Sidebar

### v1.2.0 - Update System, Tests, QR
- [x] GitHub Update System, Autodarts DOM Selector Tests, Public Leaderboard QR

### v1.3.0 - Credits Overlay
- [x] Real-time overlay, "LETZTES SPIEL" warning, configurable upsell

### v1.4.0 - Update System, Legacy Cleanup, mDNS
- [x] Enhanced Updates (download, changelog, history, backup-before-update)
- [x] Legacy Code Removal (health_monitor → observer terminology)
- [x] mDNS Improvements (periodic cleanup, re-scan, stats)

### v1.4.1 - Background Update Checker + Snooze
- [x] Background scheduler (24h), dashboard notification banner
- [x] Snooze (48h) + permanent dismiss per-version

### v1.5.0 - Observer Mode Kiosk Handoff (2026-03-09)
- [x] **HANDOFF screen**: Minimal dark backdrop when Autodarts browser is open. Autodarts covers the kiosk fullscreen. Only a tiny status line at the bottom if user alt-tabs.
- [x] **FALLBACK screen**: Shown when Autodarts browser failed to open. Clear error message, retry button, credits display, staff/end buttons.
- [x] `GET /boards/{id}/session` returns `observer_browser_open` and `observer_state` fields
- [x] KioskLayout routes: LOCKED → locked screen, OBSERVER_ACTIVE → handoff/fallback, old SetupScreen completely bypassed
- [x] `AUTODARTS_HEADLESS=false` default for real kiosk deployment (visible Playwright browser)
- [x] Credits overlay endpoint works alongside observer flow
- [x] Release packages rebuilt

## Key Data-TestIDs
- `observer-handoff-screen` — dark backdrop when Autodarts is covering
- `observer-fallback-screen` — error/retry when Autodarts browser failed
- `observer-retry-btn` — retry opening Autodarts
- `handoff-credits`, `fallback-credits` — credit display
- `handoff-call-staff`, `fallback-call-staff-btn` — staff call

## Remaining Backlog
### P2
- [ ] Chromium extension for Autodarts overlay
- [ ] PWA Install Prompt for public leaderboard
