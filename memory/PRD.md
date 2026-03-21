# Darts Kiosk SaaS Platform — PRD

## Original Problem Statement
Multi-tenant Darts Kiosk SaaS platform with central management portal and local kiosk clients. The system manages dartboard kiosks across multiple locations with remote configuration, monitoring, and control capabilities.

## Core Requirements
- **Central Portal**: Multi-tenant management with RBAC (superadmin, installer, owner, staff)
- **Local Kiosk Clients**: Autonomous operation with config sync and remote action polling
- **Configuration Management**: Scoped configs (global/customer/location/device), version history, rollback, export/import
- **Device Management**: Registration, licensing, health monitoring, binding verification
- **Real-time Push**: WebSocket-based push system for instant config/action delivery (polling as fallback)
- **Autodarts Integration**: Playwright-based browser automation for game control
- **White-Label**: Custom branding, color palettes, logos per customer
- **i18n**: Full German/English support across portal and kiosk

## Architecture
- **Central Server**: FastAPI (Python) — `/app/central_server/server.py` — port 8002
- **Local Backend**: FastAPI — `/app/backend/server.py` — port 8001
- **Frontend**: React + Tailwind + Shadcn/UI — `/app/frontend/`
- **Database**: SQLite via SQLAlchemy (both central and local)
- **WebSocket Hub**: `/ws/devices` on central server, `ws_push_client` on device backend

## User Personas
| Role | Access |
|------|--------|
| Superadmin | Full platform access, all customers/devices |
| Installer | Assigned customer management, device provisioning |
| Owner | Own scope only, config + device management |
| Staff | Limited session control only |

## Credentials
- **Central Portal**: superadmin / admin

## Key Technical Decisions
- Config scoping: global → customer → location → device (inheritance)
- WebSocket push as enhancement, polling as fallback (no single point of failure)
- Push events scoped to affected devices only (via _resolve_affected_devices)
- Persistent offline queue for network outage resilience
- Exponential backoff for WS reconnect (5s → 60s max)

## Feature Status
See CHANGELOG.md for completed features and ROADMAP.md for upcoming work.
