# Darts Kiosk SaaS Platform — PRD

## Original Problem Statement
Multi-tenant Darts Kiosk SaaS platform with central management portal and local kiosk clients. The system manages dartboard kiosks across multiple locations with remote configuration, monitoring, and control capabilities.

## Core Requirements
- **Central Portal**: Multi-tenant management with RBAC (superadmin, installer, owner, staff)
- **Local Kiosk Clients**: Autonomous operation with config sync and remote action polling
- **Configuration Management**: Scoped configs (global/customer/location/device), version history, rollback, export/import
- **Device Management**: Registration, licensing, health monitoring, binding verification
- **Autodarts Integration**: Playwright-based browser automation for game control
- **White-Label**: Custom branding, color palettes, logos per customer
- **i18n**: Full German/English support across portal and kiosk

## Architecture
- **Central Server**: FastAPI (Python) — `/app/central_server/server.py`
- **Local Backend**: FastAPI — `/app/backend/server.py`
- **Frontend**: React + Tailwind + Shadcn/UI — `/app/frontend/`
- **Database**: SQLite via SQLAlchemy (both central and local)

## User Personas
| Role | Access |
|------|--------|
| Superadmin | Full platform access, all customers/devices |
| Installer | Assigned customer management, device provisioning |
| Owner | Own scope only, config + device management |
| Staff | Limited session control only |

## Credentials
- **Central Portal**: superadmin / admin
- **Local Admin Panel**: admin / admin123

## Key Technical Decisions
- Pydantic validation for all config changes
- Config scoping: global → customer → location → device (inheritance)
- Persistent sync/action clients with self-recovery
- Structured centralized logging from devices
- Device binding with hardware fingerprint verification
- Config export/import with validation, diff preview, merge/replace modes

## Feature Status
See CHANGELOG.md for completed features and ROADMAP.md for upcoming work.
