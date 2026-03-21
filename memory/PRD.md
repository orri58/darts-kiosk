# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, scope-based access, centralized management, telemetry, and revenue mirroring.
Complete architectural refactoring: unified portal, stripped-down local panel, hierarchical config, remote device control.
Business-first Config UI with Standard/Advanced modes.
Config Runtime Integration: Central config flows to kiosk runtime via sync → apply → local DB → UI.
**System Hardening v3.9.2**: Robustness, idempotency, retry, persistence, fail-open, production logging.

## System Architecture (v3.9.2)
```
     +-----------------------------------------------------+
     |            Central License Server                    |
     |            (FastAPI, Port 8002)                      |
     |                                                      |
     |  Modules: Auth, RBAC, Scope, Licensing, Telemetry,  |
     |  Config Profiles, Remote Actions, Audit Log          |
     +------------------------+----------------------------+
                              |
         +--------------------+---------------------+
         |                    |                      |
   +-----+------+     +------+------+     +---------+--+
   |  Kiosk PC  |     |  Kiosk PC   |     |  /portal   |
   | Config Sync|     | Config Sync |     |  Dashboard |
   | Action Poll|     | Action Poll |     |  Config UI |
   | Telemetry  |     | Telemetry   |     |  Device    |
   | Health Mon.|     | Health Mon. |     |  Control   |
   +------+-----+     +------+------+     +------------+
```

## Hardening v3.9.2 — Design Decisions

### Idempotency
- Action IDs persisted to `/app/data/action_history.json` (OrderedDict, FIFO 200 entries)
- Actions in history are skipped with re-ack (safe for Central Server dedup)
- `processing` set prevents same action from running twice concurrently

### Retry & Backoff
- Config Sync: exponential backoff 30s → 60s → 120s → 240s → cap 300s
- Action Ack: 3 retries with doubling backoff (2s, 4s, 8s), skip retry on 4xx
- After max retries: mark failed, log error, continue operation

### Persistence (survives restarts)
- `/app/data/config_cache.json` — last-known central config
- `/app/data/config_applied_version.json` — frontend polling version counter
- `/app/data/action_history.json` — executed action IDs with status

### Race Condition Protection
- `asyncio.Lock` on `sync_now()` — prevents concurrent periodic + force sync
- `asyncio.Lock` on `_poll_once()` — prevents concurrent poll cycles

### Fail-Open
- Central server unreachable → cache used → kiosk operates normally
- Action poller not configured → silently skipped
- Per-section error isolation in config_apply → one corrupt section cannot block others

### Health Check
- `healthy` → everything normal
- `degraded` → config_sync 3+ consecutive errors OR action_poller 5+ consecutive errors OR agents offline
- `unhealthy` → observer success rate < 50%

## Key API Endpoints
### Config Sync & Status
- GET /api/settings/config-version — lightweight version polling
- GET /api/settings/config-sync/status — full sync/poller/version status with error counts
- POST /api/settings/config-sync/force — admin-only: trigger immediate sync

### Health
- GET /api/health — simple ping (no auth)
- GET /api/health/detailed — full health with config_sync, action_poller, observer (admin auth)

## Test Credentials
- **Central Portal superadmin**: superadmin / admin
- **Local Admin Panel**: admin / admin123
