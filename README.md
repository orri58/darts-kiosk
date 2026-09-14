# Darts Kiosk

A production-oriented kiosk and management system for cafés, bars and venues operating electronic dartboards.

The project combines a local kiosk UI, board/session management, revenue tracking and Autodarts integration in one deployable system. It is designed around one Mini-PC per dartboard and focuses on reliable local operation even when central services are unavailable.

## Why this project exists

Running multiple dartboards in a venue involves more than simply starting a game. Staff need to unlock boards, manage sessions, keep pricing consistent and understand usage and revenue without disrupting the customer experience.

Darts Kiosk brings these workflows together in a dedicated local application.

## Core capabilities

- kiosk interface for customer-facing board access
- local admin panel for board and session management
- unlock / lock workflow for individual dartboards
- session-based pricing and revenue tracking
- Autodarts integration through browser automation
- WebSocket-based live updates
- health/status monitoring
- local persistence with SQLite
- release tooling for Windows and Linux
- Docker-based development/deployment option

## Tech stack

### Backend
- Python
- FastAPI
- SQLAlchemy
- SQLite
- JWT-based authentication
- WebSockets
- Playwright for Autodarts browser automation

### Frontend
- React
- browser-based kiosk and admin interfaces
- real-time state updates

### Delivery & operations
- Docker / Docker Compose
- Linux installer and release scripts
- automated regression tests
- architecture, testing and operations documentation

## Architecture

```text
┌─────────────────────────────────────────────┐
│              Mini-PC per dartboard          │
│                                             │
│  ┌────────────┐  ┌────────────┐  ┌────────┐│
│  │ React UI   │──│ FastAPI    │──│ SQLite ││
│  │ Kiosk/Admin│  │ API/Logic  │  │        ││
│  └────────────┘  └─────┬──────┘  └────────┘│
│                        │                    │
│                 ┌──────▼───────┐            │
│                 │ Autodarts    │            │
│                 │ Playwright   │            │
│                 └──────────────┘            │
└─────────────────────────────────────────────┘
```

More detail is available in `docs/ARCHITECTURE.md`.

## Current project status

The local kiosk core is the current stable baseline. Central management and licensing features were intentionally disabled after regressions and are being reintroduced in controlled layers.

| Area | Status |
|---|---|
| Local admin panel | Stable baseline |
| Kiosk UI | Stable baseline |
| Board/session control | Stable baseline |
| Autodarts integration | Stable baseline |
| Revenue/reporting | Stable baseline |
| Central server / portal | Disabled pending controlled reintegration |
| Licensing | Disabled pending controlled reintegration |

See `docs/STATUS.md` and `docs/RECOVERY.md` for the detailed recovery and reintegration plan.

## Development setup

### Requirements

- Python 3.11+
- Node.js 18+
- SQLite
- Chrome/Chromium for Autodarts automation

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
yarn start
```

Development credentials and local environment settings should be configured outside the public documentation and changed before any real deployment.

## Testing

```bash
python -m pytest backend/tests/test_v400_recovery_baseline.py -v
python -m pytest backend/tests/test_regression_e2e.py -v
```

The project uses a recovery baseline so that previously stabilized local functionality can be verified before new layers are introduced.

## Repository structure

```text
darts-kiosk/
├── backend/          # FastAPI API, domain logic and tests
├── frontend/         # React kiosk and admin interfaces
├── central_server/   # Central features, currently disabled
├── docs/             # Architecture, runbook, status and testing docs
├── release/          # Build/release tooling
├── memory/           # Product and recovery notes
├── Dockerfile
├── docker-compose.yml
└── install.sh
```

## Engineering approach

This project is intentionally documented like a real software product rather than only as a code demo. Important practices include:

- regression testing around a known stable baseline
- separation of UI, API, services and persistence
- controlled reintegration after regressions
- operational runbooks and architecture documentation
- fail-closed behaviour for authorization/licensing-sensitive flows
- release tooling for repeatable deployment

## Portfolio context

This repository is part of my practical software-development portfolio. It demonstrates work across frontend, backend, persistence, browser automation, testing, deployment and technical documentation in a system built around a real operational use case.

## Documentation

| Document | Purpose |
|---|---|
| `docs/ARCHITECTURE.md` | System design and data flows |
| `docs/RECOVERY.md` | Recovery strategy and reintegration plan |
| `docs/RUNBOOK.md` | Operating and troubleshooting the system |
| `docs/STATUS.md` | Component status matrix |
| `docs/TESTING.md` | Test strategy and verification commands |
| `CONTRIBUTING.md` | Contribution and change rules |

## License

Proprietary. All rights reserved.
