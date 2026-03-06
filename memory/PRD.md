# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Version 1.0.0 (2026-03-06)

### Implemented Features
- Core MVP: Kiosk UI, Admin Panel, JWT+PIN Auth, Board CRUD, Pricing
- Stammkunde Mode (PIN/QR login, player stats, leaderboard)
- Autodarts Integration (Playwright, circuit breaker, soak-tested)
- mDNS Discovery + Secure Pairing
- QR Match Links (24h expiry)
- Custom Palette Editor (live preview, WCAG contrast, JSON import/export)
- Sound Effects (synthetic WAV, admin controls, rate limiting)
- EN/DE i18n (180+ keys, full admin + kiosk coverage)
- Top Stammkunden Rotation on Locked Screen
- System Management (health, backups, logs)

### Bug Fixes (2026-03-06)
- **LAN Access Fix:** `start.bat` now sets `HOST=0.0.0.0` for frontend, auto-detects LAN IP, writes dynamic `REACT_APP_BACKEND_URL`. `CORS_ORIGINS=*` for Windows bundle.
- **Autodarts Trigger Fix:** `/api/kiosk/{board_id}/start-game` now properly triggers Autodarts Playwright integration as background task when board has `autodarts_target_url`. Added `autodarts-status` and `autodarts-reset` endpoints.
- **Package-Safe Imports:** All backend imports converted to absolute `from backend.xxx import ...` form. `server.py` includes `sys.path` adjustment for backward compatibility with `directory=/app/backend` startup. Works with both `uvicorn server:app` (from backend/) and `uvicorn backend.server:app` (from project root).

### Release Packages (v1.0.0)
| Package | File | Size | Description |
|---------|------|------|-------------|
| Windows Test | `darts-kiosk-v1.0.0-windows.zip` | 1.9 MB | Direct Python+Node, BAT scripts, pre-built frontend |
| Linux Prod | `darts-kiosk-v1.0.0-linux.tar.gz` | 1.6 MB | install.sh, systemd, nginx, offline-ready |
| Source | `darts-kiosk-v1.0.0-source.zip` | 484 KB | GitHub-ready, Docker Compose, .env.example |

#### Windows Bundle Contents
- `check_requirements.bat` — Prüft Python 3.11+ & Node 18+
- `setup_windows.bat` — Installiert Backend/Frontend Deps + Playwright
- `start.bat` — One-Click Start (Backend + Frontend), LAN-IP-Erkennung, öffnet Browser
- `stop.bat` — Beendet alle Prozesse
- `README.md` — 3-5 Schritte Anleitung
- Vorkonfigurierte `.env` Dateien (CORS=* für LAN)

#### Linux Bundle Contents
- `install.sh` v2.0.0 — Ubuntu 22.04/24.04, Docker, systemd, Firewall
- Pre-built Frontend (kein Node auf Prod nötig)
- `serve-frontend.py` — Einfacher SPA-Server als Fallback
- nginx.conf, docker-compose.yml

#### Source Bundle Contents
- Kompletter Quellcode ohne Runtime-Artefakte
- `.env.example` für Backend + Frontend
- `RELEASE_NOTES.md` mit Feature-Liste
- `.gitignore` GitHub-ready
- Windows-Scripts unter `scripts/windows/`

## Remaining Backlog
### P0
- [ ] Rebuild release packages with fixed imports + LAN fix + Autodarts trigger

### P1
- [ ] Autodarts DOM Selector Tests

### P2
- [ ] mDNS Discovery Enhancements
