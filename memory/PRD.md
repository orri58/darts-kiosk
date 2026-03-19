# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs.
Must behave like a real arcade machine on Windows kiosk PCs.

## Core Architecture
- **Backend:** FastAPI + SQLAlchemy + SQLite — serves BOTH API and static frontend
- **Frontend:** React (pre-built static files served by backend — NO dev server needed)
- **Central Server:** Separate FastAPI app for licensing, multi-tenant management, and operator portal
- **Deployment:** Windows .bat scripts (non-Docker) for kiosk PCs
- **Integration:** Playwright for Autodarts browser automation
- **Update System:** GitHub Releases -> Admin Panel -> External Updater (updater.py)

## System Architecture (v3.5.3)
```
                    ┌───────────────────────────────┐
                    │     Central License Server     │
                    │     (FastAPI, Port 8002)       │
                    │   - Customers, Locations       │
                    │   - Devices, Licenses          │
                    │   - Users (superadmin/operator) │
                    │   - JWT Auth + RBAC            │
                    └─────────────┬─────────────────┘
                                  │
           ┌──────────────────────┼──────────────────────┐
           │                      │                      │
     ┌─────┴──────┐        ┌─────┴──────┐        ┌─────┴──────┐
     │  Kiosk PC  │        │  Kiosk PC  │        │  Operator  │
     │ (Backend   │        │ (Backend   │        │  Portal    │
     │  + Frontend│        │  + Frontend│        │  (Browser) │
     │  Port 8001)│        │  Port 8001)│        │            │
     └────────────┘        └────────────┘        └────────────┘
```

## Roles & Access
- **Superadmin:** Full access to everything (admin panel + central server + operator portal)
- **Operator:** Read-only portal access, scoped to assigned customers only
- **Admin (Kiosk):** Local kiosk administration
- **Staff (Kiosk):** Limited session control (unlock/lock/extend)

## Operator Portal (v3.5.3)
- Separate frontend experience at `/operator` route
- Own auth context (CentralAuthContext) — strictly separated from kiosk auth
- Connects via backend proxy `/api/central/` -> Central Server (localhost:8002)
- Pages: Dashboard, Devices, Licenses, Customers, Locations, Audit
- Read-only, business-focused UI with problem highlighting

## All Implemented Features
- v1.0-1.5: Core system (Kiosk, Admin, Auth, Boards, Pricing, Sessions, Sound, i18n, White-Label)
- v1.6.x: Arcade Machine Runtime, Chrome profiles, extension support
- v1.7.x: Update System, Production Hardening, Bug Fixes
- v1.8.x: Event-Driven Observer, iOS PWA Fix
- v1.9.x: Playwright Native WS Observer, False Lock Fix, Chrome Profile Fix, Page Management
- v1.10.0: Gotcha Mode Support + Match Activity Detection
- v2.0.x-2.9.x: State Machine Rewrite, Finalize Chain, Observer Lifecycle, Watchdog, Auth Detection
- v3.0.x: Hard-Kiosk Deployment, Installer, Boot Stability
- v3.1.x: Manual-First Deployment
- v3.2.x: Kiosk Control Features, Stability Hotfixes, Finalize Chain Reliability
- v3.3.x: Focus-Steal Fix, System Controls, Gotcha Variant Guard, DOM Selector Tests, Windows Kiosk Controls
- v3.4.x: Windows Agent, Agent Autostart, Licensing MVP, License Enforcement, Device Binding/Tracking, Cyclic License Check
- v3.5.0: Central License Server + Hybrid Sync
- v3.5.1: Device Registration Flow with One-Time Tokens
- v3.5.2: Role-Based Access Control / Multi-Tenant
- v3.5.3: Operator Portal V1 (read-only business portal for operators)

## Key DB Schema (Central Server)
- **central_users**: id, username, password_hash, display_name, role (superadmin/operator), allowed_customer_ids (JSON), status
- **customers**: id, name, contact_email, status
- **locations**: id, customer_id (FK), name, address, status
- **devices**: id, location_id (FK), install_id, api_key, device_name, status, binding_status, last_sync_at, sync_count
- **licenses**: id, customer_id (FK), location_id (FK), plan_type, max_devices, status, starts_at, ends_at, grace_days, grace_until
- **registration_tokens**: id, token_hash, customer_id, location_id, license_id, expires_at, used_at, is_revoked
- **audit_log**: id, timestamp, action, device_id, install_id, license_id, message

## Key API Endpoints (Central Server, via /api/central/)
- POST /api/central/auth/login — JWT login
- GET /api/central/auth/me — current user info
- GET /api/central/licensing/customers — list customers (scoped)
- GET /api/central/licensing/locations — list locations (scoped)
- GET /api/central/licensing/devices — list devices (scoped)
- GET /api/central/licensing/licenses — list licenses (scoped)
- GET /api/central/licensing/audit-log — audit log (scoped)
- GET /api/central/health — health check
