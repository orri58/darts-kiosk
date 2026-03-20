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
- **Build System:** Deterministic builds via `npm ci` + `craco build`, VERSION file as single source of truth

## System Architecture (v3.5.6)
```
                    +-------------------------------+
                    |     Central License Server     |
                    |     (FastAPI, Port 8002)       |
                    |   - Customers, Locations       |
                    |   - Devices, Licenses          |
                    |   - Users (superadmin/operator) |
                    |   - JWT Auth + RBAC            |
                    +---------------+---------------+
                                    |
           +------------------------+------------------------+
           |                        |                        |
     +-----+------+          +-----+------+          +------+-----+
     |  Kiosk PC  |          |  Kiosk PC  |          |  Operator  |
     | (Backend   |          | (Backend   |          |  Portal    |
     |  + Frontend|          |  + Frontend|          |  (Browser) |
     |  Port 8001)|          |  Port 8001)|          |            |
     +------------+          +------------+          +------------+
```

## Build & Release Process (v3.5.6)
- **Source of Truth:** `/app/VERSION` file
- **Build Script:** `release/build_release.sh`
- **Build Steps:**
  1. `rm -rf frontend/build` + `rm -rf release/build/` (clean old artifacts)
  2. `npm ci` (deterministic install from package-lock.json)
  3. `npm run build` (calls `craco build`)
  4. Build verification (checks index.html, JS bundles, VERSION consistency)
- **.bat files read VERSION dynamically** — no hardcoded version strings
- **NO yarn** — exclusively npm

## Roles & Access
- **Superadmin:** Full access to everything (admin panel + central server + operator portal)
- **Operator:** Read-only portal access, scoped to assigned customers only
- **Admin (Kiosk):** Local kiosk administration
- **Staff (Kiosk):** Limited session control (unlock/lock/extend)

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
- v3.5.4: Productization of Token & Registration
- v3.5.5: Superadmin Onboarding Wizard + Build/Deploy Fix
- v3.5.6: Deterministic Build System, Version Consistency, Clean Build Process

## Key DB Schema (Central Server)
- **central_users**: id, username, password_hash, display_name, role, allowed_customer_ids, status
- **customers**: id, name, contact_email, status
- **locations**: id, customer_id (FK), name, address, status
- **devices**: id, location_id (FK), install_id, api_key, device_name, status, binding_status, last_sync_at
- **licenses**: id, customer_id (FK), location_id (FK), plan_type, max_devices, status, starts_at, ends_at, grace_days
- **registration_tokens**: id, token_hash, customer_id, location_id, license_id, expires_at, used_at, is_revoked
- **audit_log**: id, timestamp, action, device_id, install_id, license_id, message

## Key API Endpoints
- POST /api/central/auth/login
- GET /api/central/auth/me
- GET /api/central/licensing/customers|locations|devices|licenses|audit-log (all scoped)
- GET /api/licensing/central-server-url (public, for kiosk registration)
- GET /api/licensing/registration-status (public)
- POST /api/licensing/register-device (public, token-based auth)
