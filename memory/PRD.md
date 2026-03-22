# Darts Kiosk SaaS Platform — PRD

## Original Problem Statement
Multi-tenant Darts Kiosk SaaS platform with central management portal and local kiosk clients. The system manages dartboard kiosks across multiple locations with remote configuration, monitoring, and control capabilities.

## Core Requirements
- **Central Portal**: Multi-tenant management with RBAC (superadmin, installer, owner, staff)
- **Local Kiosk Clients**: Autonomous operation with config sync and remote action polling
- **License Lifecycle**: Create→Token→Register→Bind→Monitor→Deactivate/Archive
- **Configuration Management**: Scoped configs, version history, rollback, export/import
- **Device Management**: Registration with license binding, max_devices enforcement, health monitoring
- **Real-time Push**: WebSocket-based push system (polling as fallback)
- **White-Label**: Custom branding, color palettes, logos per customer
- **i18n**: Full German/English support

## Architecture
- **Central Server**: FastAPI — `/app/central_server/server.py` — port 8002
- **Local Backend**: FastAPI — `/app/backend/server.py` — port 8001
- **Frontend**: React + Tailwind + Shadcn/UI — `/app/frontend/`
- **Database**: SQLite via SQLAlchemy

## Key Endpoints
- `/api/licensing/licenses/{id}` — License detail with devices + token
- `/api/licensing/licenses/{id}/token` — Get/create activation token
- `/api/licensing/licenses/{id}/regenerate-token` — Regenerate token
- `/api/register-device` — Device registration with max_devices enforcement
- `/ws/devices` — WebSocket push for real-time events
- `/api/config/export|import|rollback` — Config management

## Credentials
- **Central Portal**: superadmin / admin

## Feature Status
See CHANGELOG.md for completed features and ROADMAP.md for upcoming work.
