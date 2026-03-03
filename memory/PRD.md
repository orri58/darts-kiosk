# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Each dartboard has its own Mini-PC running the full stack. Owner controls ALL boards from one central admin panel on local network.

## User Personas
1. **Cafe Owner (Admin)**: Full system access - branding, pricing, boards, users, logs, revenue
2. **Staff/Wirt**: Quick unlock/extend/lock sessions, view board status (PIN login in 2s)
3. **Customers**: Touch kiosk - select game, enter names, play

## Core Requirements
- **Kiosk States**: LOCKED → UNLOCKED_SETUP → IN_GAME → FINISHED/ERROR → LOCKED
- **Pricing Models**: per_game (credits), per_time (minutes), per_player
- **Authentication**: JWT + PIN quick-login for staff
- **Multi-Board**: Master/Agent architecture, local LAN only
- **Database**: SQLite (Postgres-ready via SQLAlchemy/Alembic)
- **Theme**: Dark, industrial minimal, 8 color palettes + custom

## What's Been Implemented

### Phase 1 (2026-03-03) - Core MVP
- [x] SQLAlchemy models: User, Board, Session, AuditLog, Settings
- [x] JWT authentication with PIN quick-login
- [x] Role-based access control (Admin/Staff)
- [x] Board management APIs (CRUD, unlock/lock/extend)
- [x] Session tracking with pricing modes
- [x] Settings APIs (branding, pricing, palettes)
- [x] Asset upload (logo)
- [x] Audit logging
- [x] Revenue summary endpoints
- [x] Kiosk UI: Locked, Setup, In-Game screens
- [x] Admin Panel: Dashboard, Boards, Settings, Users, Logs, Revenue
- [x] Touch-optimized UI with virtual keyboard
- [x] 8 color palettes

### Phase 1.5 (2026-03-03) - Production Ready
- [x] **Playwright Autodarts Integration** - Full service layer with:
  - Start game automation (game type, players, start button)
  - Match end detection (DOM polling)
  - Retry logic (3 attempts with delays)
  - Screenshot/HTML dump on errors
  - Logging with session_id, board_id
  
- [x] **Docker Compose** - Production deployment:
  - App service with volumes (/data/db.sqlite, /data/assets, /data/logs)
  - ENV: MODE=MASTER/AGENT, BOARD_ID, JWT_SECRET, AGENT_SECRET
  - nginx reverse proxy (/kiosk, /admin, /api)
  - Healthchecks + restart: unless-stopped
  
- [x] **Session Scheduler** - Background tasks:
  - Session expiry enforcement (per_time mode)
  - Idle timeout (UNLOCKED state → auto-lock after X minutes)
  - Post-game lock check (credits exhausted → lock)
  - Runs every 10 seconds
  
- [x] **Setup Guide** - Complete documentation:
  - Windows + Linux Kiosk Mode (Chrome/Edge fullscreen)
  - Autostart configuration
  - Network setup (fixed IPs, firewall)
  - Board registration in Admin Panel
  - Watchdog for auto-restart
  
- [x] **Error Screen** - Kiosk robustness:
  - "Fehler - bitte Wirt rufen" display
  - "Personal rufen" button
  - "Zurück zu Gesperrt" button
  - Retry option

### Seed Data
- Admin user: admin / admin123 (PIN: 1234)
- Staff user: wirt / wirt123 (PIN: 0000)
- 2 Boards: BOARD-1, BOARD-2
- 8 Color palettes (Industrial, Midnight, Forest, Crimson, Ocean, Sunset, Slate, Emerald)
- Default pricing: per_game @ 2.00€

## Prioritized Backlog

### P0 - Critical (Done ✅)
- [x] Core kiosk flow
- [x] Admin unlock/lock
- [x] Session management
- [x] Authentication
- [x] Autodarts integration layer
- [x] Docker deployment
- [x] Session scheduler
- [x] Setup documentation

### P1 - Important (Phase 2)
- [ ] Real Autodarts DOM selectors (requires access to actual Autodarts)
- [ ] Board heartbeat/offline detection
- [ ] mDNS board discovery
- [ ] Push notifications for staff (WebSocket)

### P2 - Nice-to-Have (Phase 2)
- [ ] Player statistics (Stammkunde mode)
- [ ] Highscore leaderboard
- [ ] Custom palette editor
- [ ] QR code for staff panel
- [ ] Sound effects for kiosk
- [ ] Multi-language support

## Technical Stack
- Backend: FastAPI, SQLAlchemy, SQLite (Alembic migrations ready)
- Frontend: React 19, Tailwind CSS, shadcn/ui, Zustand
- Fonts: Oswald (headings), DM Sans (body), JetBrains Mono (numbers)
- Icons: Lucide React
- Charts: Recharts
- Browser Automation: Playwright
- Deployment: Docker Compose + nginx

## Files Structure
```
/app/
├── backend/
│   ├── server.py              # Main FastAPI app
│   ├── database.py            # SQLAlchemy setup
│   ├── models/__init__.py     # DB models
│   └── services/
│       ├── autodarts_integration.py  # Playwright automation
│       └── scheduler.py              # Background tasks
├── frontend/src/
│   ├── pages/kiosk/           # Kiosk screens
│   ├── pages/admin/           # Admin panel
│   └── context/               # Auth + Settings
├── docker-compose.yml
├── Dockerfile
├── nginx/nginx.conf
├── SETUP_GUIDE.md
└── .env.example
```

## Next Tasks (Phase 2)
1. Test with real Autodarts installation
2. Implement player statistics (optional login)
3. Add WebSocket for real-time board status updates
4. Highscore leaderboard display on kiosk
