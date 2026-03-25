# Darts Kiosk — Cafe Dartboard Management System

A production-grade kiosk system for cafes and bars with dartboards. Each dartboard gets a dedicated Mini-PC running this software. Staff unlock boards for customers, the system manages sessions, pricing, and integrates with [Autodarts](https://autodarts.io) for automated scoring.

## Current Status: `v4.0.0-recovery`

The system underwent a recovery to restore stability after a series of regressions introduced by central server / licensing features (v3.4–v3.15). The **local core** is now stable and fully tested. Central/portal features are disabled and will be reintroduced in controlled layers.

| Component | Status | Notes |
|-----------|--------|-------|
| Local Admin Panel | **Stable** | Full CRUD, board management, settings, revenue |
| Kiosk UI | **Stable** | Lock/unlock screens, autodarts integration |
| Board Control | **Stable** | Unlock, lock, session flow |
| Autodarts Integration | **Stable** | Observer mode, browser automation via Playwright |
| Revenue & Reporting | **Stable** | Session-based revenue tracking |
| Central Server / Portal | **Disabled** | Planned reintegration in layers (see `docs/RECOVERY.md`) |
| Licensing | **Disabled** | Planned reintegration as Layer B |

See `docs/STATUS.md` for the full component matrix.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│                 Mini-PC (per dartboard)      │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐ │
│  │ React    │  │ FastAPI  │  │ SQLite    │ │
│  │ Frontend │──│ Backend  │──│ Database  │ │
│  │ (Kiosk + │  │ (API +   │  │           │ │
│  │  Admin)  │  │ Services)│  └───────────┘ │
│  └──────────┘  └──────────┘                 │
│                      │                      │
│              ┌───────┴────────┐             │
│              │ Autodarts      │             │
│              │ (Playwright    │             │
│              │  Browser Auto) │             │
│              └────────────────┘             │
└─────────────────────────────────────────────┘
```

See `docs/ARCHITECTURE.md` for the full system design.

---

## Quick Start (Development)

### Prerequisites
- Python 3.11+
- Node.js 18+
- SQLite3

### Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn backend.server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend
```bash
cd frontend
yarn install
yarn start    # Starts on port 3000
```

### First Login
The system creates a default admin on first start:
- **Username:** `admin`
- **Password:** `admin123`
- **PIN:** `1234`

A staff account is also created:
- **Username:** `wirt`
- **Password:** `wirt123`

---

## Repository Structure

```
darts-kiosk/
├── backend/                 # FastAPI backend (FROZEN CORE)
│   ├── server.py            # Main application entry point
│   ├── database.py          # SQLite + SQLAlchemy setup
│   ├── models/              # ORM models
│   ├── routers/             # API route handlers
│   │   ├── auth.py          # Authentication (JWT)
│   │   ├── boards.py        # Board CRUD + unlock/lock
│   │   ├── kiosk.py         # Kiosk state + game flow
│   │   ├── admin.py         # Revenue, logs, reports
│   │   ├── settings.py      # Branding, pricing, language
│   │   ├── players.py       # Player stats + Stammkunde
│   │   └── ...
│   ├── services/            # Business logic services
│   │   ├── autodarts_observer.py   # Playwright automation
│   │   ├── ws_manager.py           # WebSocket broadcasts
│   │   ├── health_monitor.py       # System health
│   │   └── ...
│   └── tests/               # Test suites
├── frontend/                # React frontend (FROZEN CORE)
│   └── src/
│       ├── App.js           # Routing (admin + kiosk only)
│       ├── pages/admin/     # Admin panel pages
│       ├── pages/kiosk/     # Kiosk UI screens
│       ├── context/         # React contexts (auth, settings, i18n)
│       └── hooks/           # Custom hooks (WS, sound)
├── central_server/          # Central management server (DISABLED)
├── docs/                    # Documentation
│   ├── ARCHITECTURE.md      # System architecture
│   ├── RECOVERY.md          # Recovery strategy
│   ├── RUNBOOK.md           # Operations guide
│   ├── STATUS.md            # Component status matrix
│   └── TESTING.md           # Testing guide
├── release/                 # Build scripts + release artifacts
├── memory/                  # Project memory (PRD, changelog)
├── VERSION                  # Current version string
├── Dockerfile               # Container build
├── docker-compose.yml       # Docker orchestration
├── install.sh               # Linux production installer
└── CONTRIBUTING.md          # Contribution guidelines
```

---

## Build & Deploy

### Windows (Test Environment)
```bash
bash release/build_release.sh
# Output: release/build/darts-kiosk-v4.0.0-recovery-windows/
# Run: start.bat
```

### Linux (Production)
```bash
bash release/build_release.sh
# Output: release/build/darts-kiosk-v4.0.0-recovery-linux.tar.gz
# Install: tar xzf ... && cd darts-kiosk && ./install.sh
```

### Docker
```bash
docker-compose up --build
```

---

## Testing

```bash
# Run baseline recovery tests
cd /app && python -m pytest backend/tests/test_v400_recovery_baseline.py -v

# Run full regression suite
python -m pytest backend/tests/test_regression_e2e.py -v
```

See `docs/TESTING.md` for the complete testing guide.

---

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/ARCHITECTURE.md` | System design and data flows |
| `docs/RECOVERY.md` | Why recovery was needed, reintegration plan |
| `docs/RUNBOOK.md` | How to run, verify, and debug the system |
| `docs/STATUS.md` | Component status matrix |
| `docs/TESTING.md` | Test categories, commands, checklists |
| `CONTRIBUTING.md` | Contribution rules and frozen core policy |
| `memory/FROZEN_CORE.md` | List of frozen modules |
| `memory/PRD.md` | Product requirements |
| `memory/CHANGELOG.md` | Version history |

---

## Key Concepts

- **Frozen Core:** The local admin/kiosk/board/autodarts modules restored from v3.3.1-hotfix2. No modifications allowed without explicit approval.
- **Recovery Layers:** Central features will be reintroduced in order: visibility → licensing → board control → config sync. Each must be verified before the next starts.
- **Fail-Closed:** Any license or authorization check that fails must block the action, never silently allow it.
- **Autodarts Observer:** Uses Playwright to automate the Autodarts web app. Requires Chrome/Chromium installed on the target machine.

---

## License

Proprietary. All rights reserved.
