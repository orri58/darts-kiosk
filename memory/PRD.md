# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, scope-based access, centralized management, telemetry, and revenue mirroring.
Complete architectural refactoring: unified portal, stripped-down local panel, hierarchical config, remote device control.

## System Architecture (v3.9.0)
```
     +-----------------------------------------------------+
     |            Central License Server                    |
     |            (FastAPI, Port 8002)                      |
     |                                                      |
     |  4-Tier RBAC: superadmin > installer > owner > staff |
     |                                                      |
     |  Core Modules:                                       |
     |  - Auth + Users + Roles                              |
     |  - Scope (customers/locations/devices)               |
     |  - Licensing CRUD + Sync                             |
     |  - Telemetry (heartbeat, ingest, dashboard)          |
     |  - Config Profiles (global→cust→loc→dev, deep merge) |
     |  - Remote Actions (force_sync, restart, reload_ui)   |
     |  - Audit Log                                         |
     +------------------------+----------------------------+
                              |
         +--------------------+---------------------+
         |                    |                      |
   +-----+------+     +------+------+     +---------+--+
   |  Kiosk PC  |     |  Kiosk PC   |     |  /portal   |
   | Config Sync|     | Config Sync |     |  Unified   |
   | Heartbeat  |     | Heartbeat   |     |  Login +   |
   | Telemetry  |     | Telemetry   |     |  Dashboard |
   | Action Poll|     | Action Poll |     |  Config UI |
   +------+-----+     +------+------+     |  Device    |
          |                   |            |  Control   |
     /admin (local)     /admin (local)     +------------+
     3 pages only       3 pages only
```

## URL Structure (v3.9.0)
| Path | Purpose | Pages |
|------|---------|-------|
| `/portal/login` | Central login | Login form |
| `/portal` | Dashboard (KPIs, device health) | Dashboard |
| `/portal/customers` | Customer management | CRUD table |
| `/portal/locations` | Location management | CRUD table |
| `/portal/devices` | Device list (clickable → detail) | Table |
| `/portal/devices/:id` | **NEW** Device detail + remote actions | Detail view |
| `/portal/licenses` | License management | CRUD table |
| `/portal/users` | User management (RBAC) | CRUD table |
| `/portal/config` | **NEW** Hierarchical config editor | Form + JSON |
| `/portal/audit` | Audit log | Event list |
| `/admin` | Local board control | Lock/unlock/extend |
| `/admin/health` | System diagnostics + config sync | Tabs view |
| `/admin/licensing` | License status (read-only) | Status display |

## Hierarchical Config System (v3.9.0)
```
Merge order: global → customer → location → device
Deep merge: nested objects merged, not replaced. Narrower scope wins.
```
### Config Schema:
```json
{
  "pricing": { "mode": "per_game|per_time|per_credit", "per_game": { "price_per_credit": 2.0, "default_credits": 3 } },
  "branding": { "cafe_name": "...", "primary_color": "#f59e0b" },
  "kiosk": { "auto_lock_timeout_min": 5, "idle_timeout_min": 15 }
}
```
### UI Features:
- Tab-based editor: Preise | Branding | Kiosk-Verhalten | JSON
- Scope selector: Global | Kunde | Standort | Geraet
- Right panel: Effective (merged) config + applied layers
- Scope-aware: editing requires selecting appropriate entity via ScopeSwitcher

## Remote Actions System (v3.9.0)
| Action | Description | Effect |
|--------|-------------|--------|
| `force_sync` | Force config pull from central | Next poll cycle |
| `restart_backend` | Restart kiosk backend process | Next poll cycle |
| `reload_ui` | Reload browser/kiosk UI | Next poll cycle |
### Flow:
1. Portal user issues action → stored as `pending` in DB + audit logged
2. Device polls `/api/remote-actions/{id}/pending` (every 60s)
3. Device executes action + acknowledges via POST `.../ack`
4. Status updated to `acked` or `failed`

## Key API Endpoints
### Config (v3.9.0)
- GET /api/config/effective?device_id=X — merged config (unauthenticated, for devices)
- GET /api/config/profiles — list all profiles (owner+)
- GET /api/config/profile/{scope_type}/{scope_id} — single profile
- PUT /api/config/profile/{scope_type}/{scope_id} — upsert profile + audit

### Remote Actions (v3.9.0)
- POST /api/remote-actions/{device_id} — issue action (owner+)
- GET /api/remote-actions/{device_id} — list actions history
- GET /api/remote-actions/{device_id}/pending — device polling endpoint
- POST /api/remote-actions/{device_id}/ack — device acknowledges action

### Device Detail (v3.9.0)
- GET /api/telemetry/device/{device_id} — enriched detail: status, version, events, stats, actions

### Existing
- POST /api/auth/login, GET /api/auth/me
- GET/POST /api/users, /api/licensing/*, /api/scope/*
- POST /api/telemetry/heartbeat|ingest, GET /api/telemetry/dashboard

## DB Schema (v3.9.0)
### Config Profiles
- **config_profiles**: id, scope_type, scope_id, config_data (JSON), version (int), updated_by, timestamps
### Remote Actions
- **remote_actions**: id, device_id, action_type, status (pending|acked|failed), issued_by, issued_at, acked_at, result_message

## Visual Themes
- **/portal**: Indigo/business SaaS theme (Shield icon, "DartControl Portal")
- **/admin**: Cyan/technical debug theme (Terminal icon, "LOCAL SERVICE", font-mono)

## Test Credentials
- **Central Portal superadmin**: superadmin / admin
- **Local Admin Panel**: admin / admin123
