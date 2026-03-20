# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, scope-based access, and centralized management.

## System Architecture (v3.6.0)
```
                    +-------------------------------+
                    |     Central License Server     |
                    |     (FastAPI, Port 8002)       |
                    |   4-Tier RBAC:                 |
                    |   superadmin > installer >     |
                    |   owner > staff                |
                    +---------------+---------------+
                                    |
           +------------------------+------------------------+
           |                        |                        |
     +-----+------+          +-----+------+          +------+-----+
     |  Kiosk PC  |          |  Kiosk PC  |          | Operator   |
     | (read-only |          | (read-only |          | Portal     |
     |  licensing)|          |  licensing)|          | (CRUD/Mgmt)|
     +------------+          +------------+          +------------+
```

## Role Hierarchy (v3.6.0)
| Role | Level | Can Create | Access |
|------|-------|-----------|--------|
| superadmin | 4 | all roles | all data |
| installer | 3 | owner, staff | scoped to assigned customers |
| owner | 2 | staff | scoped to own business |
| staff | 1 | none | read-only within scope |

## Build System
- **Source of Truth:** `/app/VERSION`
- **Build Script:** `release/build_release.sh` (deterministic: rm -rf → npm ci → craco build → verify)
- **.bat files read VERSION dynamically** — no hardcoded versions

## Key API Endpoints
### Central Server (via /api/central/ proxy)
- POST /api/auth/login — login
- GET /api/auth/me — current user
- GET /api/roles — role info + creatable roles
- GET/POST /api/users — RBAC-enforced user management
- PUT /api/users/{id} — update user (role change, deactivate)
- GET /api/scope/customers|locations|devices — scope switcher data
- GET /api/dashboard?customer_id=&location_id= — scoped dashboard
- GET/POST /api/licensing/customers|locations|devices|licenses — CRUD with scope
- PUT /api/licensing/customers|locations|devices|licenses/{id} — update/deactivate
- GET /api/licensing/audit-log — scoped audit log with actor

### Local Kiosk
- GET /api/licensing/registration-status — device registration status
- GET /api/licensing/central-server-url — central server URL
- GET /api/licensing/status — license status (read-only)
- GET /api/licensing/sync-config — sync configuration
- POST /api/licensing/force-sync — trigger manual sync
- POST /api/licensing/register-device — one-time token registration

## Completed Features (v3.6.0 Phase A)
- 4-tier RBAC (superadmin/installer/owner/staff) with backend enforcement
- Scope-based access control (customer/location/device)
- Scope Switcher in Operator Portal (cascading dropdowns)
- User management with role hierarchy enforcement
- Customer/Location/Device/License CRUD with soft-delete/deactivate
- Local Admin stripped to read-only licensing
- Audit log with actor tracking
- Registration auto-redirect after success
- New release packages (Windows/Linux/Source)
