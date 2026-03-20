# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, scope-based access, centralized management, telemetry, and revenue mirroring.
Architectural refactoring to create a unified SaaS platform experience with consolidated portal.

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
     |  - Audit Log                               |
     +-------------------+------------------------+
                         |
        +----------------+----------------+
        |                |                |
  +-----+------+  +-----+------+  +------+-----+
  |  Kiosk PC  |  |  Kiosk PC  |  |  /portal   |
  | Heartbeat  |  | Heartbeat  |  |  Unified   |
  | Telemetry  |  | Telemetry  |  |  Login +   |
  | Revenue    |  | Revenue    |  |  Dashboard |
  +------+-----+  +------+-----+  +------------+
         |               |
    /admin (local)  /admin (local)
    Diagnostics     Diagnostics
```

## Key URL Structure (v3.8.0)
| Path | Purpose | Auth System |
|------|---------|-------------|
| `/portal/login` | Central login for all human users | CentralAuthContext (central JWT) |
| `/portal/*` | Central management (Dashboard, Customers, Devices, etc.) | CentralAuthContext |
| `/admin/login` | Local device/service panel login | AuthContext (local JWT) |
| `/admin/*` | Local diagnostics, boards, settings | AuthContext |
| `/kiosk` | Kiosk UI for players | None (public) |
| `/operator/*` | **DEPRECATED** — redirects to `/portal/*` | N/A (redirect) |

## Role Hierarchy
| Role | Level | Can Create | Access |
|------|-------|-----------|--------|
| superadmin | 4 | all roles | all data |
| installer | 3 | owner, staff | scoped to assigned customers |
| owner | 2 | staff | scoped to own business |
| staff | 1 | none | read-only within scope |

## Key Features (v3.8.0)
- **Unified Portal**: Single `/portal` entry point for all central management
- **Role-based Navigation**: Nav items shown/hidden based on user role
- **Legacy Redirects**: All `/operator/*` routes redirect to `/portal/*`
- **Dual Auth**: CentralAuthContext for /portal, AuthContext for /admin (independent)
- **Telemetry**: Heartbeat (60s), event queue, batch upload (5min), idempotent via event_id
- **Revenue Mirroring**: credits_added events with revenue_cents -> device_daily_stats
- **Operations Dashboard**: KPIs (online/offline, revenue, sessions, games, warnings)

## Key API Endpoints
### Central Server
- POST /api/auth/login, GET /api/auth/me, GET /api/roles
- GET/POST /api/users, PUT /api/users/{id}
- GET /api/scope/customers|locations|devices
- GET /api/dashboard — scoped overview
- GET/POST /api/licensing/customers|locations|devices|licenses
- GET /api/licensing/audit-log

### Telemetry (v3.7.0)
- POST /api/telemetry/heartbeat — device heartbeat (X-License-Key auth)
- POST /api/telemetry/ingest — batch event upload (X-License-Key auth, idempotent)
- GET /api/telemetry/dashboard — scoped KPIs (JWT auth)
- GET /api/telemetry/device-stats — per-device daily stats (JWT auth)

### Local Kiosk
- GET /api/licensing/registration-status|central-server-url|status|sync-config
- POST /api/licensing/register-device|force-sync

## DB Schema (Central)
### Telemetry (v3.7.0)
- **telemetry_events**: id, event_id (unique), device_id, event_type, timestamp, data (JSON)
- **device_daily_stats**: id, device_id, date, revenue_cents, sessions, games, credits_added, errors, heartbeats

### Core
- central_users, customers, locations, devices, licenses, registration_tokens, audit_log

## Test Credentials
- **Central Portal superadmin**: superadmin / admin
- **Local Admin Panel**: admin / admin123, PIN: 1234
