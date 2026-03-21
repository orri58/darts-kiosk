# Darts Kiosk + Admin Control System - PRD

## Original Problem Statement
Production-ready, local-first Darts Kiosk + Admin Control system for a cafe.
Central SaaS platform with 4-tier RBAC, centralized management, telemetry, and revenue mirroring.
Config Runtime Integration: Central config flows to kiosk runtime via sync/apply/local DB/UI.
System Hardening v3.9.2: Robustness, idempotency, retry, persistence, fail-open.
**Observability v3.9.3**: Device debug panel in portal with health, logs, action history, config status.

## System Architecture (v3.9.3)
```
Device Heartbeat Flow:
  Kiosk Backend
    → DeviceLogBuffer (ring buffer, 100 entries)
    → TelemetrySyncClient heartbeat (every 60s)
       payload: { version, health_snapshot, logs[last 30] }
    → Central Server (stores in devices table)
    → Portal Device Detail (reads via device detail API)
```

## Observability Data Model (v3.9.3)

### Heartbeat Payload (Device → Central)
```json
{
  "version": "3.9.3",
  "health": {
    "health_status": "healthy|degraded|unknown",
    "config_sync": { "config_version", "last_sync_at", "consecutive_errors", "last_error", "sync_count" },
    "action_poller": { "last_poll_at", "last_action_at", "actions_executed", "actions_failed", "consecutive_poll_errors", "last_error" },
    "config_applied_version": 3
  },
  "logs": [
    { "ts": "ISO8601", "level": "info|warn|error", "src": "config_sync|config_apply|action_poller", "evt": "event_type", "msg": "message", "ctx": {} }
  ]
}
```

### Health Status Rules
- **healthy**: All systems nominal, 0 consecutive sync/poll errors
- **degraded**: 3+ consecutive config sync errors OR 5+ action poller errors
- **offline**: No heartbeat received within threshold (5 min)

### Portal Device Detail Sections
| Section | Data Source | Content |
|---------|-----------|---------|
| Health Badge | health_snapshot.health_status | healthy/degraded/offline with reason |
| Status Grid | health_snapshot + device fields | version, last heartbeat, config version, last sync, last action |
| Health Reason | computed | "3 Sync-Fehler", "Kein Heartbeat / Offline", etc. |
| Config-Sync Card | health_snapshot.config_sync | version, applied version, sync count, errors |
| Action-Poller Card | health_snapshot.action_poller | executed, failed, poll errors |
| Remote Actions | POST /api/remote-actions/{id} | Config-Sync, Backend Restart, UI Reload |
| Action History | remote_actions table | status badges, duration, error messages |
| Device Logs | device_logs column | color-coded (INFO/WARN/ERROR), filterable |
| Daily Stats | device_daily_stats table | last 7 days revenue/sessions/games |
| Recent Events | telemetry_events table | last events with timestamps |

## Key API Endpoints
### Device Observability (Central Server)
- POST /api/telemetry/heartbeat — accepts health + logs payload
- GET /api/telemetry/device/{id} — returns full device detail with health_snapshot + device_logs

### Config Sync & Status (Local Backend)
- GET /api/settings/config-version — lightweight version polling
- GET /api/settings/config-sync/status — full sync/poller status
- POST /api/settings/config-sync/force — admin-only force sync

## Test Credentials
- **Central Portal superadmin**: superadmin / admin
- **Local Admin Panel**: admin / admin123
