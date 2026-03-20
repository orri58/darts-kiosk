# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, scope-based access, centralized management, telemetry, and revenue mirroring.

## System Architecture (v3.7.0)
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
  |  Kiosk PC  |  |  Kiosk PC  |  |  Operator  |
  | Heartbeat  |  | Heartbeat  |  |  Portal    |
  | Telemetry  |  | Telemetry  |  | (Dashboard)|
  | Revenue    |  | Revenue    |  |            |
  +------------+  +------------+  +------------+
```

## Key Features (v3.7.0)
- **Telemetry**: Heartbeat (60s), event queue, batch upload (5min), idempotent via event_id
- **Revenue Mirroring**: credits_added events with revenue_cents → device_daily_stats
- **Online/Offline**: Heartbeat < 5min = online, audit log for state transitions
- **Operations Dashboard**: KPIs (online/offline, revenue today/7d, sessions, games, warnings)
- **Fail-Open**: Telemetry errors never block local game operation

## Role Hierarchy
| Role | Level | Can Create | Access |
|------|-------|-----------|--------|
| superadmin | 4 | all roles | all data |
| installer | 3 | owner, staff | scoped to assigned customers |
| owner | 2 | staff | scoped to own business |
| staff | 1 | none | read-only within scope |

## Key API Endpoints
### Telemetry (v3.7.0)
- POST /api/telemetry/heartbeat — device heartbeat (X-License-Key auth)
- POST /api/telemetry/ingest — batch event upload (X-License-Key auth, idempotent)
- GET /api/telemetry/dashboard — scoped KPIs (JWT auth)
- GET /api/telemetry/device-stats — per-device daily stats (JWT auth)

### Central Server
- POST /api/auth/login, GET /api/auth/me, GET /api/roles
- GET/POST /api/users, PUT /api/users/{id}
- GET /api/scope/customers|locations|devices
- GET /api/dashboard — scoped overview
- GET/POST /api/licensing/customers|locations|devices|licenses
- GET /api/licensing/audit-log

### Local Kiosk
- GET /api/licensing/registration-status|central-server-url|status|sync-config
- POST /api/licensing/register-device|force-sync

## DB Schema (Central)
### New (v3.7.0)
- **telemetry_events**: id, event_id (unique, idempotency), device_id, event_type, timestamp, data (JSON)
- **device_daily_stats**: id, device_id, date, revenue_cents, sessions, games, credits_added, errors, heartbeats

### Extended (v3.7.0)
- **devices**: +last_heartbeat_at, +reported_version, +last_error, +last_activity_at

### Existing
- central_users, customers, locations, devices, licenses, registration_tokens, audit_log
