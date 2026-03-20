# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, scope-based access, centralized management, telemetry, and revenue mirroring.
Complete architectural refactoring: unified portal, stripped-down local panel, hierarchical config, remote device control.
Business-first Config UI with Standard/Advanced modes.
**Config Runtime Integration**: Central config flows to kiosk runtime via sync → apply → local DB → UI.

## System Architecture (v3.9.1)
```
     +-----------------------------------------------------+
     |            Central License Server                    |
     |            (FastAPI, Port 8002)                      |
     |                                                      |
     |  Modules: Auth, RBAC, Scope, Licensing, Telemetry,  |
     |  Config Profiles, Remote Actions, Audit Log          |
     +------------------------+----------------------------+
                              |
         +--------------------+---------------------+
         |                    |                      |
   +-----+------+     +------+------+     +---------+--+
   |  Kiosk PC  |     |  Kiosk PC   |     |  /portal   |
   | Config Sync|     | Config Sync |     |  Dashboard |
   | Heartbeat  |     | Heartbeat   |     |  Config UI |
   | Telemetry  |     | Telemetry   |     |  Device    |
   | Action Poll|     | Action Poll |     |  Control   |
   +------+-----+     +------+------+     +------------+
          |                   |
     /admin (local)     /admin (local)
     3 pages only       3 pages only
```

## Config Runtime Integration (v3.9.1)
### Data Flow
```
Central Server (config_profiles) 
  → GET /api/config/effective 
  → config_sync_client.py (polls every 5 min)
  → config_apply.py (maps central keys → local settings keys)
  → Local SQLite (settings table)
  → REST API (/api/settings/*)
  → Frontend SettingsContext (polls config-version every 30s)
  → UI components
```

### Key Services
| Service | File | Function |
|---------|------|----------|
| Config Sync | config_sync_client.py | Polls central server, caches to disk |
| Config Apply | config_apply.py | Maps central config sections to local settings table |
| Action Poller | action_poller.py | Polls for remote actions (force_sync, restart, reload_ui) |
| Config Version | settings.py | /api/settings/config-version for lightweight frontend polling |

## Config UI (v3.9.1 — Business-First)
### Standard Mode (Default)
| Tab | Felder |
|-----|--------|
| Preise | Modell, Preis/Credit, Standard-Credits, Mindestbetrag |
| Branding | Name, Untertitel, Logo URL |
| Farben | Primaer, Sekundaer, Akzent + Preview |
| Kiosk | Auto-Lock, Idle Timeout, Auto-Start, Vollbild |
| Texte | Willkommen Titel/Untertitel, Gesperrt, Game-Over |
| Sprache | Standard-Sprache, Sprachwechsel erlauben |
| Sound | Aktiviert, Lautstaerke (Slider), Ruhezeiten |
| QR/Sharing | QR-Code, Oeffentliche Ergebnisse, Leaderboard |

### Erweiterter Modus (Toggle oben rechts)
- JSON Editor fuer aktuellen Scope-Override
- Layer-Badges + Merge-Info
- Raw JSON der effektiven Config

## Key API Endpoints
### Config Sync & Status
- GET /api/settings/config-version — lightweight version polling for frontend
- GET /api/settings/config-sync/status — full sync/poller/version status
- POST /api/settings/config-sync/force — admin-only: trigger immediate sync

### Config (Central Server)
- GET /api/config/effective?device_id=X — merged config
- GET /api/config/profiles — list profiles
- PUT /api/config/profile/{scope}/{id} — upsert + audit

### Remote Actions (Central Server)
- POST /api/remote-actions/{device_id} — issue (force_sync|restart_backend|reload_ui)
- GET /api/remote-actions/{device_id}/pending — device polling
- POST /api/remote-actions/{device_id}/ack — acknowledge

### Device Detail
- GET /api/telemetry/device/{device_id} — enriched detail

## Test Credentials
- **Central Portal superadmin**: superadmin / admin
- **Local Admin Panel**: admin / admin123
