# Darts Kiosk System - Release Notes

## Version 1.0.0 (2026-03-06)

### Core Features
- **Kiosk UI** — Locked, Setup, In-Game, Finished, QR-Code screens
- **Admin Panel** — Dashboard, Boards, Settings, Users, Logs, Revenue, Health, System, Discovery, Leaderboard
- **JWT + PIN Auth** — Admin full access, Staff limited to session control
- **Pricing Models** — Per game, per time, per player
- **White-Label Branding** — Logo upload, cafe name, 8 default + custom color palettes

### Game & Player Features
- **Stammkunde Mode** — Registered players with nickname + 4-6 digit PIN, QR-code login
- **Player Statistics** — Games played, won, win rate, avg score, best checkout, highest throw
- **Leaderboard** — Multi-period (Today/Week/Month/All), sortable, podium display
- **QR Match Links** — Public, temporary (24h) match results with QR code post-game
- **Top Stammkunden Rotation** — Configurable display on locked kiosk screen

### Sound System
- **Synthetic WAV Generation** — 5 events (start, 180!, checkout, bust, win), pure Python
- **Admin Controls** — Enable/disable, volume, sound pack, quiet hours, rate limiting
- **Smart Playback** — Web Audio API, autoplay-unlock, per-event + global rate limits

### Internationalization
- **DE/EN Toggle** — ~180 translation keys, admin language setting
- **Full Coverage** — Sidebar navigation, page headings, kiosk screens, settings tabs

### Infrastructure
- **Custom Palette Editor** — Create/edit/delete with live preview, WCAG contrast warnings, JSON import/export
- **Autodarts Integration** — Playwright browser automation with circuit breaker
- **mDNS Discovery** — Automatic agent PC detection on LAN with secure pairing
- **Real-time Updates** — WebSocket for live board status
- **System Management** — Health checks, automated backups, log viewer
- **Deployment** — Docker Compose, install.sh for Ubuntu, Windows test bundle

### Architecture
- **Backend:** FastAPI, SQLAlchemy (SQLite), Pydantic, APScheduler
- **Frontend:** React 19, Tailwind CSS, Shadcn/UI, React Router
- **Modular:** 12 API router modules, 6 service modules
- **Security:** JWT auth, PIN hashing (bcrypt), rate limiting, CORS, LAN-only firewall

---

### System Requirements

#### Windows (Testing)
- Python 3.11+
- Node.js 18+

#### Linux (Production)
- Ubuntu 22.04 / 24.04 LTS
- 2 GB RAM, 5 GB disk
- Docker + Docker Compose

#### Hardware
- Mini-PC per dartboard (Intel N100 or better)
- Network: LAN (Ethernet recommended)
