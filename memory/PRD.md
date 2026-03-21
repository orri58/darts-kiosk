# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, centralized management, telemetry, and revenue mirroring.
Config Runtime Integration, System Hardening, Observability, and now **Stability Package v3.9.4**.

## Stability Package v3.9.4 — Design

### 1. device_id Auto-Resolution
```
Startup → Read license_sync_config from DB
       → If device_id missing + server_url + api_key present:
         → GET {central}/api/device/resolve (X-License-Key header)
         → 200: Persist device_id to license_sync_config in DB
         → 404: Not registered yet (fail-safe, continue without)
         → Error: Log warning, continue without
       → Next startup: Load device_id from DB (no network call)
```
**Edge Cases:**
- API key not registered → 404 → runs without device_id (action poller disabled)
- Central unreachable → timeout → same as 404 behavior
- device_id already present → skips resolution entirely
- No server_url/api_key → skips resolution entirely

### 2. Config Schema Validation
| Section | Field | Rule |
|---------|-------|------|
| pricing | mode | in [per_game, per_time, per_player] |
| pricing | per_game.price_per_credit | number >= 0 |
| pricing | per_game.default_credits | integer >= 1 |
| pricing | per_time.price_per_30/60_min | number >= 0 |
| pricing | min_amount | number >= 0 |
| branding | cafe_name | non-empty string, max 100 chars |
| branding | subtitle | string, max 200 chars |
| branding | primary/secondary/accent_color | #RRGGBB hex format |
| branding | logo_url | http/https URL or null |
| kiosk | auto_lock/idle_timeout_min | number > 0 |
| kiosk | auto_start, fullscreen | boolean |
| texts | * | string, max 200 chars |
| language | default | "de" or "en" |
| language | allow_switch | boolean |
| sound | enabled | boolean |
| sound | volume | 0-100 |
| sound | quiet_hours_start/end | 0-23 |
| sharing | qr_enabled/public_results/leaderboard_public | boolean |

### 3. Config Rollback
```
Upsert Flow:
  1. Validate config_data → 422 if invalid
  2. If profile exists: save current to config_history
  3. Update profile with new data + bump version
  4. Audit log

Rollback Flow:
  1. Find history entry for requested version
  2. Save current profile to history (preserves chain)
  3. Restore history entry's config_data to profile
  4. Bump version (never reuses old number)
  5. Audit log with "rollback v{N}" marker
```

## Key API Endpoints
### Device Identity (Central)
- GET /api/device/resolve — resolve device_id from API key (X-License-Key header)

### Config Validation & Rollback (Central)
- PUT /api/config/profile/{scope}/{id} — upsert with schema validation (422 on error)
- GET /api/config/history/{scope}/{id} — version history with active_version
- POST /api/config/rollback/{scope}/{id}/{version} — rollback to previous version

## Test Credentials
- **Central Portal superadmin**: superadmin / admin
- **Local Admin Panel**: admin / admin123
