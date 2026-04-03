# Ops / Maintenance / Installation Pass — 2026-04-03

## Goal
Finish and unify the repo's existing operator-facing maintenance/setup/update code paths instead of introducing a parallel control plane.

## Main gaps closed

### 1) First-run / setup coherence
- `frontend/src/pages/admin/Login.js`
  - redirects incomplete installs to `/setup`
- `backend/services/setup_wizard.py`
  - now exposes preflight checks, DB path, env presence, and local URLs
  - now detects the seeded admin quick PIN problem
  - now rotates quick PINs for existing admin/staff users during setup completion
- `frontend/src/pages/admin/SetupWizard.js`
  - now shows preflight state and local operator URLs directly in the wizard

### 2) Device ops / Windows maintenance
- `frontend/src/components/admin/AgentTab.js`
  - existing UI component was kept and completed with autostart controls
- `frontend/src/pages/admin/System.js`
  - integrates the AgentTab as a dedicated `Device Ops` tab
- `backend/routers/admin_agent.py`
  - new admin route surface matching the existing frontend expectations
  - agent-first execution with safe fallback to local backend services
  - covers:
    - status
    - Autodarts ensure/restart
    - backend restart
    - reboot/shutdown
    - shell switching
    - Task Manager enable/disable
    - autostart register/remove
- `backend/app_layers.py`
  - mounts the new router

### 3) Update / rollback flow coherence
- `backend/services/update_service.py`
  - downloaded assets now expose `filename`, `path`, and `size_bytes`
  - this matches what install/update routes already expect
- result: the handoff between download list and install path is no longer internally inconsistent

### 4) Backup / diagnostics coherence
- `backend/database.py`
  - added a configured SQLite path helper
- `backend/services/backup_service.py`
- `backend/services/system_service.py`
  - now use the configured DB file instead of assuming a stale fixed path
- `backend/routers/admin.py`
  - support bundle export now includes runtime JSON snapshots in addition to logs

## Validation performed

### Succeeded
```bash
python3 -m compileall backend agent
cd frontend && npm run build
```

### Not performed here
- pytest: host environment lacked `pytest`
- real Windows runtime validation: still needed for shell switching, task scheduler autostart, reboot/shutdown, and full updater behavior

## Follow-up validation recommended on a real board PC
1. Fresh install from Windows scripts
2. Confirm `/admin/login` redirects to `/setup`
3. Complete setup wizard and confirm admin password + quick PIN rotation
4. Open `System -> Device Ops`
5. Validate:
   - agent online/offline behavior
   - Explorer restore
   - kiosk shell re-enable
   - Task Manager enable/disable
   - autostart register/remove
   - backend restart
6. Download support bundle
7. Run one full update + rollback drill on a non-production board
