# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, scope-based access, centralized management, telemetry, and revenue mirroring.
Complete architectural refactoring: unified portal, stripped-down local panel, hierarchical config, remote device control.
Business-first Config UI with Standard/Advanced modes.

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

## Config UI (v3.9.1 — Business-First)
### Standard Mode (Default — 95% der Nutzer)
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

### Scope (technisch gleich, UX anders):
- "Einstellungen fuer: Alle (Globale Vorgabe)" — nicht "global JSON"
- "Einstellungen fuer: Fuer Kunde" — nicht "customer scope"

## Key API Endpoints
### Config
- GET /api/config/effective?device_id=X — merged config
- GET /api/config/profiles — list profiles
- PUT /api/config/profile/{scope}/{id} — upsert + audit

### Remote Actions
- POST /api/remote-actions/{device_id} — issue (force_sync|restart_backend|reload_ui)
- GET /api/remote-actions/{device_id}/pending — device polling
- POST /api/remote-actions/{device_id}/ack — acknowledge

### Device Detail
- GET /api/telemetry/device/{device_id} — enriched detail

## Test Credentials
- **Central Portal superadmin**: superadmin / admin
- **Local Admin Panel**: admin / admin123
