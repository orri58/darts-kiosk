# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe running on Mini-PCs. Master/Agent architecture for multi-board control over LAN.

## Implementation History

### Phase 1-4 (2026-03-03) - Core MVP + Production + Hardening + Installer
### P1: Live Stability (2026-03-04) - WebSocket, Refactoring, mDNS, Pairing
### P2: QR-Code Match-Link + Player Stats + Leaderboard (2026-03-04)
### P0: Stammkunde Mode (2026-03-04) - PIN login, QR token, registration
### Top Stammkunden Rotation (2026-03-04) - Kiosk locked screen display
### Custom Palette Editor (2026-03-04) - Create/edit/delete with live preview

### Kiosk Sound Effects (2026-03-06) - COMPLETED
- Pure Python WAV synthesis (5 events, <=0.8s, ADSR envelopes)
- Admin: enable toggle, volume, quiet hours, sound pack, rate limit
- Frontend: Web Audio API preload, autoplay-unlock, rate limiting
- WS broadcast on game events + manual trigger endpoint

### EN/DE i18n - Full Coverage (2026-03-06) - COMPLETED
- **translations.js**: ~180 DE/EN keys covering ALL UI strings
- **I18nContext**: fetchLang on mount, t(key, params) with interpolation, switchLang()
- **Admin Navigation**: All 10 sidebar labels through t() with stable data-testid
- **Admin Pages**: All 9 page headings (Dashboard, Boards, Settings, Users, Logs, Revenue, Health, System, Discovery, Leaderboard) through t()
- **Dashboard Board Cards**: Status labels (GESPERRT/LOCKED), buttons (FREISCHALTEN/UNLOCK, SPERREN/LOCK, VERLÄNGERN/EXTEND), location label
- **Settings Tabs**: All 6 tab labels (Branding, Preise/Pricing, Farbschema/Color Scheme, Stammkunde/Regular, Sound, Sprache/Language) through t()
- **Kiosk LockedScreen**: All texts (locked message, prices, board, pairing code, top stammkunden, CTA)
- **Kiosk SetupScreen**: Game prep, player names, stammkunde auth flow, PIN dialogs
- **Admin Language Tab**: DE/EN flag buttons with save
- **No hardcoded admin navigation strings left**
- **Language switch updates labels without full page reload** (React context re-render)
- **Active route/menu state remains intact after language change**
- Verified: Screenshots confirm EN mode shows "DASHBOARD", "Settings", "LOCKED", "UNLOCK", "Refresh", "Location:" and DE mode shows "DASHBOARD", "Einstellungen", "GESPERRT", "FREISCHALTEN", "Aktualisieren", "Standort:"

## Code Architecture
```
/app/backend/routers/: auth, boards, kiosk, settings, admin, backups, updates, agent, discovery, matches, stats, players
/app/backend/services/: autodarts, scheduler, backup, health_monitor, update, setup_wizard, system, ws_manager, mdns, pairing, sound_generator
/app/frontend/src/context/: AuthContext, SettingsContext, I18nContext
/app/frontend/src/hooks/: useBoardWS, useSoundManager
/app/frontend/src/i18n/: translations.js (~180 keys DE/EN)
/app/frontend/src/pages/admin/: AdminLayout (i18n sidebar), Dashboard, Boards, Settings (6 tabs), Users, Logs, Revenue, Health, System, Discovery, Leaderboard — ALL using useI18n()
/app/frontend/src/pages/kiosk/: LockedScreen, SetupScreen, InGameScreen, MatchResultScreen, ErrorScreen — key screens using useI18n()
```

## Remaining Backlog
### P1
- [ ] Autodarts DOM Selector Tests
### P2
- [ ] mDNS Discovery Enhancements
