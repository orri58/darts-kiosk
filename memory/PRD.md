# Darts Kiosk SaaS — Product Requirements Document

## Original Problem Statement
Production-ready "Darts Kiosk + Admin Control" SaaS platform for cafes. Mini-PC per dartboard, central admin portal for multi-board management. MASTER/AGENT architecture over LAN.

## Current Focus: Stabilization (v3.15.x)
**NO NEW FEATURES.** All development focused on:
- Eliminating HTTP 500 errors from corrupt/legacy production data
- Hardening all ORM-dependent endpoints against data inconsistencies
- Comprehensive E2E regression testing

## Architecture
- **Backend:** FastAPI + SQLAlchemy + SQLite
- **Frontend:** React + Tailwind + Shadcn/UI
- **Central Server:** Separate FastAPI instance for multi-device management
- **Proxy:** Local backend proxies central server calls via `/api/central/`

## Key Endpoints (Hardened in v3.15.2)
- `/api/telemetry/device/{id}` — Device detail (3-tier fallback: ORM → session rollback + raw SQL → fresh session raw SQL → error dict)
- `/api/licensing/devices` — Device list (fresh session raw SQL fallback)
- `/api/telemetry/dashboard` — Telemetry dashboard (defensive ORM with rollback)
- `/api/dashboard` — Main dashboard (defensive ORM with rollback)

## Completed (v3.15.2)
- HTTP 500 fix: Global try/except + fresh-session raw-SQL fallback on ALL device endpoints
- Session rollback after ORM errors before raw SQL retry
- Dashboard endpoints hardened
- Telemetry dashboard hardened
- 26/26 E2E regression tests passing (including 4 corruption patterns)
- Release packages built: Windows, Linux, Source

## Pending: User Verification
- User must test v3.15.2 Windows build in production environment

## Backlog
- P2: Autodarts DOM Selector Tests
- P2: mDNS Discovery Enhancements
