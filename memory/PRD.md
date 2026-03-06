# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Implementation History

### Phase 1-1.5 (2026-03-03) - Core MVP + Production
- SQLAlchemy models, JWT+PIN auth, Board CRUD, Kiosk + Admin UI
- Playwright Autodarts, Docker Compose, Session Scheduler

### Phase 3 (2026-03-03) - Enterprise Hardening
- Setup Wizard, Security, JSON logging, Backups, Updates, Circuit breaker

### Phase 4 (2026-03-03) - Installer + System Management
- install.sh v2.0.0, /admin/system page, System APIs

### P1: Live Stability (2026-03-04)
- Autodarts Soak Test, WebSocket real-time, Modular refactoring
- mDNS Discovery + Secure Pairing

### P2: QR-Code Match-Link (2026-03-04)
- MatchResult with public token, 24h expiry, kiosk QR screen

### P2: Player Statistics & Leaderboard (2026-03-04)
- Guest-first model, stats per player, leaderboard API, admin page

### P0: Stammkunde Mode (2026-03-04)
- Player model with nickname+PIN, QR token, registration/login
- Auto guest Player creation on game end, stats tracking
- Frontend PIN dialog, registration flow, verified badges

### Top Stammkunden Rotation (2026-03-04)
- `GET /api/stats/top-registered` with 45s cache, highlight priority
- Admin settings: toggle, period, interval, max entries, nickname truncation
- Kiosk LockedScreen: rotation with rank badge, stats, highlight, CTA fallback

### Custom Palette Editor (2026-03-04)
- Create/edit/delete custom color palettes, live preview
- WCAG contrast warnings, JSON import/export
- 8 default palettes protected from deletion

### Kiosk Sound Effects (2026-03-06) - COMPLETED
- **Sound Generator** (`services/sound_generator.py`): Pure Python WAV synthesis
  - 5 events: start (0.5s), one_eighty (0.7s), checkout (0.4s), bust (0.5s), win (0.8s)
  - ADSR envelopes, normalized volume, 22050Hz/16-bit/mono
  - Auto-generated on first access to `/data/assets/sounds/default/`
- **Backend**:
  - `GET/PUT /api/settings/sound` - Config (enabled=false, volume=70, pack, quiet hours, rate_limit_ms=1500)
  - `GET /api/sounds/packs` - List available packs
  - `GET /api/sounds/{pack}/{event}.wav` - Serve with `Cache-Control: public, max-age=86400, immutable`
  - `POST /api/kiosk/{board_id}/sound` - Manual trigger via WS broadcast
  - WS `sound_event` broadcast on game start + end
- **Frontend** (`hooks/useSoundManager.js`):
  - Web Audio API with AudioContext, preload all sounds on first touch
  - Autoplay-unlock via click/touchstart/keydown listeners
  - Per-event rate limit (configurable, default 1.5s) + global max 30/min
  - Quiet hours check, volume control
- **Admin Settings > Sound tab**: Enable toggle, volume slider, pack selection, test buttons, rate limit slider, quiet hours with time inputs
- Tests: 17 backend + full frontend, 100% pass

### EN/DE Language Toggle (i18n) (2026-03-06) - COMPLETED
- **Translations** (`i18n/translations.js`): ~150 DE/EN keys covering:
  - Kiosk: locked, setup, stammkunde, in-game, finished screens
  - Admin: all settings tabs (branding, pricing, palette, stammkunde, sound, language)
- **I18nContext** (`context/I18nContext.js`):
  - Fetches language from `GET /api/settings/language` on mount
  - `t(key, params)` function with interpolation (`{name}`, `{count}`)
  - `switchLang(lang)` for runtime switching
  - Falls back to DE keys if EN key missing
- **Backend**: `GET/PUT /api/settings/language` (default: `{language: "de"}`)
- **Admin Settings > Sprache tab**: DE/EN flag buttons with checkmark, save
- **Kiosk LockedScreen**: All texts use `t()` - LOCKED/GESPERRT, Prices/Preise, etc.
- **Kiosk SetupScreen**: All texts use `t()` - game prep, player names, stammkunde flow
- Tests: Backend verified via curl + pytest, frontend verified via screenshots (EN shows "LOCKED", "PRICES", "TOP REGULARS")

## Code Architecture
```
/app/backend/
  routers/: auth, boards, kiosk, settings, admin, backups, updates, agent, discovery, matches, stats, players
  services/: autodarts, scheduler, backup, health_monitor, update, setup_wizard, system, ws_manager, mdns, pairing, sound_generator
  models/: User, Board, Session, AuditLog, Settings, TrustedPeer, MatchResult, Player

/app/frontend/src/
  context/: AuthContext, SettingsContext, I18nContext
  hooks/: useBoardWS, useSoundManager
  i18n/: translations.js
  pages/admin/: Dashboard, Boards, Settings (6 tabs), Users, Logs, Revenue, Health, System, Discovery, Leaderboard
  pages/kiosk/: LockedScreen, SetupScreen, InGameScreen, MatchResultScreen, ErrorScreen
```

## Remaining Backlog

### P1 - Upcoming
- [ ] Autodarts DOM Selector Tests (stability against Autodarts website changes)

### P2 - Future
- [ ] mDNS Discovery Enhancements
