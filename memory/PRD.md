# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Each dartboard has its own Mini-PC running the full stack. Owner controls ALL boards from one central admin panel on local network.

## User Personas
1. **Cafe Owner (Admin)**: Full system access - branding, pricing, boards, users, logs, revenue
2. **Staff/Wirt**: Quick unlock/extend/lock sessions, view board status
3. **Customers**: Touch kiosk - select game, enter names, play

## Core Requirements
- **Kiosk States**: LOCKED → UNLOCKED_SETUP → IN_GAME → FINISHED → LOCKED
- **Pricing Models**: per_game (credits), per_time (minutes), per_player
- **Authentication**: JWT + PIN quick-login for staff
- **Multi-Board**: Master/Agent architecture, local LAN only
- **Database**: SQLite (Postgres-ready via SQLAlchemy/Alembic)
- **Theme**: Dark, industrial minimal, 8 color palettes + custom

## What's Been Implemented (2026-03-03)
### Backend (FastAPI + SQLite)
- [x] SQLAlchemy models: User, Board, Session, AuditLog, Settings
- [x] JWT authentication with PIN quick-login
- [x] Role-based access control (Admin/Staff)
- [x] Board management APIs (CRUD, unlock/lock/extend)
- [x] Session tracking with pricing modes
- [x] Settings APIs (branding, pricing, palettes)
- [x] Asset upload (logo)
- [x] Audit logging
- [x] Revenue summary endpoints
- [x] Agent API endpoints for Master/Agent communication
- [x] Autodarts integration service layer (Playwright-ready)

### Frontend (React + Tailwind)
- [x] Kiosk UI: Locked screen, Setup (game + players), In-Game, auto-lock
- [x] Virtual keyboard (react-simple-keyboard)
- [x] Admin Panel: Dashboard, Boards, Settings, Users, Logs, Revenue
- [x] PIN login for quick staff access
- [x] Dark industrial theme with Oswald/DM Sans fonts
- [x] 8 color palettes selectable in settings
- [x] Touch-optimized large buttons

### Seed Data
- Admin user: admin / admin123 (PIN: 1234)
- Staff user: wirt / wirt123 (PIN: 0000)
- 2 Boards: BOARD-1, BOARD-2
- 8 Color palettes
- Default pricing config

## Prioritized Backlog

### P0 - Critical (Done)
- [x] Core kiosk flow
- [x] Admin unlock/lock
- [x] Session management
- [x] Authentication

### P1 - Important (Next)
- [ ] Playwright Autodarts automation (full implementation)
- [ ] Match end detection from Autodarts DOM
- [ ] Auto-decrement credits on match end
- [ ] Time-based auto-lock (cron/scheduler)
- [ ] Docker Compose setup
- [ ] Setup guide documentation

### P2 - Nice-to-Have
- [ ] Board heartbeat/offline detection
- [ ] mDNS board discovery
- [ ] Custom palette editor
- [ ] QR code for staff panel
- [ ] Sound effects for kiosk
- [ ] Kiosk watchdog (auto-restart on crash)

## Technical Stack
- Backend: FastAPI, SQLAlchemy, SQLite (Alembic migrations ready)
- Frontend: React 19, Tailwind CSS, shadcn/ui, Zustand
- Fonts: Oswald (headings), DM Sans (body), JetBrains Mono (numbers)
- Icons: Lucide React
- Charts: Recharts

## Next Tasks
1. Full Playwright automation for Autodarts
2. Docker Compose configuration
3. Setup guide for deployment
4. Time-based session expiry scheduler
