# Architecture

## Overview

The Darts Kiosk system has two architectural layers:

1. **Local Device** (stable, frozen core) — runs on each Mini-PC connected to a dartboard
2. **Central Server** (disabled, planned reintegration) — manages multiple devices from a single admin portal

This document describes both layers. The local device layer is production-ready. The central server layer is disabled in v4.0.0-recovery and will be reintroduced in controlled phases.

---

## Local Device Architecture

```
┌─ Mini-PC ─────────────────────────────────────────────┐
│                                                        │
│  ┌─ Frontend (React, Port 3000) ───────────────────┐  │
│  │                                                  │  │
│  │  /admin/*          /kiosk/:boardId               │  │
│  │  ┌──────────┐      ┌───────────────────┐        │  │
│  │  │ Admin    │      │ Kiosk UI          │        │  │
│  │  │ Panel    │      │ (Locked/Setup/    │        │  │
│  │  │          │      │  InGame/Finished) │        │  │
│  │  └──────────┘      └───────────────────┘        │  │
│  └──────────────────────────────────────────────────┘  │
│           │                      │                     │
│           ▼                      ▼                     │
│  ┌─ Backend (FastAPI, Port 8001) ──────────────────┐  │
│  │                                                  │  │
│  │  Routers:                                        │  │
│  │  ├── auth.py      JWT login (username + PIN)     │  │
│  │  ├── boards.py    Board CRUD, unlock/lock        │  │
│  │  ├── kiosk.py     Kiosk state, game flow         │  │
│  │  ├── admin.py     Revenue, logs, reports         │  │
│  │  ├── settings.py  Branding, pricing, language    │  │
│  │  ├── players.py   Player stats, Stammkunde       │  │
│  │  ├── matches.py   Match results, QR sharing      │  │
│  │  └── stats.py     Leaderboards                   │  │
│  │                                                  │  │
│  │  Services:                                       │  │
│  │  ├── autodarts_observer.py  Playwright browser   │  │
│  │  ├── ws_manager.py         WebSocket broadcasts  │  │
│  │  ├── health_monitor.py     System health         │  │
│  │  ├── sound_generator.py    Game sounds (WAV)     │  │
│  │  ├── mdns_service.py       Network discovery     │  │
│  │  ├── backup_service.py     DB backup/restore     │  │
│  │  └── scheduler.py          Periodic tasks        │  │
│  │                                                  │  │
│  └──────────────────────────────────────────────────┘  │
│           │                                            │
│           ▼                                            │
│  ┌─ SQLite Database ───────────────────────────────┐  │
│  │  darts_kiosk.sqlite                             │  │
│  │  Tables: users, boards, sessions, settings,     │  │
│  │          players, match_results, audit_logs      │  │
│  └─────────────────────────────────────────────────┘  │
│                                                        │
│  ┌─ Autodarts (Playwright) ────────────────────────┐  │
│  │  Chrome/Chromium → play.autodarts.io            │  │
│  │  Observer watches for game start/end events     │  │
│  └─────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

### Data Flow: Board Unlock → Game → Lock

```
Admin clicks "Unlock"
  → POST /api/boards/{id}/unlock
    → Creates Session (status=active, pricing, players)
    → Board.status = unlocked
    → WebSocket broadcast: board_update
    → Kiosk UI switches to SetupScreen

Player starts game
  → POST /api/kiosk/{id}/start-game
    → Autodarts observer opens browser
    → Navigates to play.autodarts.io
    → Monitors for game events
    → Board.status = in_game

Game ends (autodarts callback or manual)
  → Session.status = finished
  → Session.ended_at = now
  → Board.status = locked (auto-lock)
  → WebSocket broadcast: board_update
  → Kiosk UI switches to LockedScreen

Admin can also manually lock
  → POST /api/boards/{id}/lock
    → Ends active session
    → Board.status = locked
```

---

## Central Server Architecture (DISABLED)

The central server is a separate FastAPI application that manages multiple local devices. It is currently **disabled** in v4.0.0-recovery due to stability regressions.

```
┌─ Central Server (Port 8002) ───────────────────────┐
│                                                     │
│  central_server/server.py                           │
│  ├── Auth (superadmin/staff)                        │
│  ├── Device management                              │
│  ├── License management                             │
│  ├── Remote actions (unlock/lock via portal)        │
│  ├── Telemetry (heartbeat, events, stats)           │
│  ├── Config sync (push config to devices)           │
│  └── WebSocket hub (real-time device status)        │
│                                                     │
│  SQLite: central_licenses.sqlite                    │
│  Tables: devices, customers, locations, licenses,   │
│          remote_actions, telemetry_events            │
└─────────────────────────────────────────────────────┘
         │
         │ HTTP API
         ▼
┌─ Local Device ──────────────────────────────────────┐
│  (proxied via /api/central/*)                       │
│                                                     │
│  Post-baseline services (currently disabled):       │
│  ├── action_poller.py      Polls remote actions     │
│  ├── config_sync_client.py Fetches config           │
│  ├── license_service.py    License enforcement      │
│  ├── ws_push_client.py     WS to central            │
│  └── telemetry_sync_client.py  Sends telemetry      │
└─────────────────────────────────────────────────────┘
```

### Configuration Hierarchy (when central is active)

```
Priority (highest to lowest):
  1. Device-specific config (per device override)
  2. Location config
  3. Customer config
  4. Global config (system defaults)
```

### Reintegration Plan

See `docs/RECOVERY.md` for the layered reintroduction strategy.

---

## Database Schema (Local)

### Core Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `users` | Admin/staff accounts | username, hashed_password, role, pin_hash |
| `boards` | Dartboard registrations | board_id, name, status (locked/unlocked/in_game) |
| `sessions` | Game sessions | board_id, status, pricing_mode, price_total, started_at, ended_at |
| `settings` | Key-value config store | key, value (JSON) |
| `players` | Registered players (Stammkunde) | nickname, pin_hash, qr_token |
| `match_results` | Shared match data | public_token, board_id, game_data (JSON) |
| `audit_logs` | Admin action log | action, user_id, details, created_at |

### Board States

```
locked → unlocked → in_game → locked
                         ↑
                    (autodarts callback or manual lock)
```

### Session States

```
active → finished
active → cancelled
```

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11, FastAPI, SQLAlchemy, Pydantic |
| Frontend | React 18, Tailwind CSS, Shadcn/UI |
| Database | SQLite (local), SQLite (central) |
| Browser Automation | Playwright (Chromium) |
| Real-time | WebSocket (native FastAPI) |
| Audio | pydub (WAV generation) |
| Network Discovery | Zeroconf (mDNS) |
| i18n | Custom context (DE/EN) |
| Auth | JWT (HS256) |
