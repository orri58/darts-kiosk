# Darts Kiosk SaaS Platform — PRD

## Original Problem Statement
Multi-tenant Darts Kiosk SaaS platform with central management portal and local kiosk clients. The system manages dartboard kiosks across multiple locations with remote configuration, monitoring, and control capabilities.

## Core Requirements
- **Central Portal**: Multi-tenant management with RBAC (superadmin, installer, owner, staff)
- **License Lifecycle**: Create→Token→Register→Bind→Monitor→Deactivate/Archive
- **Device Onboarding**: Token-based registration with max_devices enforcement, runtime reconfigure
- **Configuration Management**: Scoped configs, version history, rollback, export/import
- **Real-time Push**: WebSocket push (polling as fallback)
- **White-Label**: Custom branding, color palettes, logos per customer

## Architecture
- **Central Server**: FastAPI — `/app/central_server/server.py` — port 8002
- **Local Backend**: FastAPI — `/app/backend/server.py` — port 8001
- **Frontend**: React + Tailwind + Shadcn/UI — `/app/frontend/`
- **Database**: SQLite via SQLAlchemy

## Key Endpoints
- `/api/licensing/licenses/{id}` — License detail with devices + token history
- `/api/licensing/licenses/{id}/token` — Get/create activation token
- `/api/register-device` — Device registration with max_devices + license_id binding
- `/api/internal/reconfigure-sync` — Runtime reconfigure sync services after registration
- `/api/telemetry/device/{id}` — Device detail with license_id, binding_status
- `/ws/devices` — WebSocket push for real-time events
- `/api/config/export|import|rollback` — Config management

## Credentials
- **Central Portal**: superadmin / admin

## Feature Status
See CHANGELOG.md for completed features and ROADMAP.md for upcoming work.
