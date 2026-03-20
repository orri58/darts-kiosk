# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, scope-based access, centralized management, telemetry, and revenue mirroring.
Architectural refactoring to create a unified SaaS platform with consolidated portal and stripped-down local panel.

## System Architecture (v3.8.0)
```
     +-------------------------------------------+
     |        Central License Server              |
     |        (FastAPI, Port 8002)                |
     |                                            |
     |  4-Tier RBAC:                              |
     |  superadmin > installer > owner > staff    |
     |                                            |
     |  Endpoints:                                |
     |  - Auth + Users + Roles                    |
     |  - Scope (customers/locations/devices)     |
     |  - Licensing CRUD + Sync                   |
     |  - Telemetry (heartbeat, ingest, dashboard)|
     |  - Config (hierarchical: global→cust→loc→dev)
     |  - Audit Log                               |
     +-------------------+------------------------+
                         |
        +----------------+----------------+
        |                |                |
  +-----+------+  +-----+------+  +------+-----+
  |  Kiosk PC  |  |  Kiosk PC  |  |  /portal   |
  | Config Sync|  | Config Sync|  |  Unified   |
  | Heartbeat  |  | Heartbeat  |  |  Login +   |
  | Telemetry  |  | Telemetry  |  |  Dashboard |
  +------+-----+  +------+-----+  +------------+
         |               |
    /admin (local)  /admin (local)
    Diagnostics     Diagnostics
    (3 pages only)  (3 pages only)
```

## URL Structure (v3.8.0)
| Path | Purpose | Auth | Pages |
|------|---------|------|-------|
| `/portal/login` | Central login | CentralAuth JWT | Login form |
| `/portal/*` | Central management | CentralAuth JWT | Dashboard, Customers, Locations, Devices, Licenses, Users, Audit |
| `/admin/login` | Local device panel login | Local JWT | Login form |
| `/admin` | Board-Kontrolle (lock/unlock) | Local JWT | Dashboard only |
| `/admin/health` | System & Health | Local JWT | Services, Config Sync, Agents, Backups, Errors |
| `/admin/licensing` | Lizenz-Status (read-only) | Local JWT | Status view |
| `/kiosk` | Kiosk UI for players | None | Game UI |
| `/operator/*` | DEPRECATED | N/A | Redirects to /portal/* |

## REMOVED from Local Admin (now in /portal):
- Users management → /portal/users
- Revenue analytics → /portal (dashboard)
- Settings (global) → /portal config
- Discovery (mDNS) → /portal/devices
- Leaderboard management → /portal
- Reports → /portal
- Boards CRUD → /portal/devices
- System updates → /portal

## Hierarchical Config System (v3.8.0)
```
Merge order: global → customer → location → device
(narrower scope wins on conflict)
```
- **global**: Default config for all devices
- **customer**: Overrides for a specific customer
- **location**: Overrides for a specific location
- **device**: Overrides for a specific device
- Deep merge: nested objects are merged, not replaced
- Config sync client on each kiosk pulls effective config every 5min
- Cached locally for offline fallback

## Role Hierarchy
| Role | Level | Can Create | Access |
|------|-------|-----------|--------|
| superadmin | 4 | all roles | all data, global config |
| installer | 3 | owner, staff | scoped customers |
| owner | 2 | staff | own business |
| staff | 1 | none | read-only within scope |

## Key API Endpoints
### Central Config (v3.8.0)
- GET /api/config/effective?device_id=X — merged config (unauthenticated, for devices)
- GET /api/config/profiles — list all profiles (owner+)
- GET /api/config/profile/{scope_type}/{scope_id} — single profile (owner+)
- PUT /api/config/profile/{scope_type}/{scope_id} — upsert profile (owner+, superadmin for global)

### Local Config Sync (v3.8.0)
- GET /api/licensing/config-sync-status — sync status (unauthenticated)
- POST /api/licensing/force-config-sync — force sync (admin only)
- GET /api/licensing/effective-config — cached config (unauthenticated)

### Central Server (existing)
- POST /api/auth/login, GET /api/auth/me
- GET/POST /api/users
- GET /api/scope/customers|locations|devices
- GET /api/dashboard
- POST /api/telemetry/heartbeat|ingest, GET /api/telemetry/dashboard

## DB Schema — Config (v3.8.0)
- **config_profiles**: id, scope_type (global|customer|location|device), scope_id, config_data (JSON), version (int), updated_by, timestamps

## Visual Themes
- **/portal**: Indigo/business SaaS theme (Shield icon, "DartControl Portal")
- **/admin**: Cyan/technical debug theme (Terminal icon, "LOCAL SERVICE", font-mono)

## Test Credentials
- **Central Portal superadmin**: superadmin / admin
- **Local Admin Panel**: admin / admin123, PIN: 1234
