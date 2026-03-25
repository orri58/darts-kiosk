# Runbook — Operations Guide

Practical guide for running, verifying, and debugging the Darts Kiosk system.

---

## Starting the System

### Development (Preview Environment)

Services are managed by Supervisor:
```bash
# Check status
sudo supervisorctl status

# Restart individual services
sudo supervisorctl restart backend
sudo supervisorctl restart frontend

# View logs
tail -f /var/log/supervisor/backend.err.log
tail -f /var/log/supervisor/frontend.err.log
```

Backend runs on port **8001**, frontend on port **3000**.

### Local Development (Manual)

```bash
# Backend
cd /app
pip install -r backend/requirements.txt
uvicorn backend.server:app --host 0.0.0.0 --port 8001 --reload

# Frontend (separate terminal)
cd /app/frontend
yarn install
yarn start
```

### Windows Test Build

```bash
# Build
bash release/build_release.sh

# The Windows bundle is at:
# release/build/darts-kiosk-v{VERSION}-windows/

# On Windows: double-click start.bat
# Or: python -m uvicorn backend.server:app --host 0.0.0.0 --port 8001
```

### Linux Production

```bash
tar xzf darts-kiosk-v{VERSION}-linux.tar.gz
cd darts-kiosk
./install.sh
# Installs systemd service, starts automatically
```

---

## Verifying Core Flows

### 1. Authentication

```bash
API=https://your-host.com  # or http://localhost:8001

# Login
curl -s -X POST "$API/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "
import sys,json
d = json.load(sys.stdin)
print(f'Token: {d[\"access_token\"][:20]}...')
print(f'User: {d[\"user\"][\"username\"]} ({d[\"user\"][\"role\"]})')
"
```

### 2. Board Control

```bash
TOKEN="<from login>"

# List boards
curl -s "$API/api/boards" -H "Authorization: Bearer $TOKEN"

# Unlock
curl -s -X POST "$API/api/boards/BOARD-1/unlock" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"player_count": 2, "player_names": ["Alice", "Bob"]}'

# Lock
curl -s -X POST "$API/api/boards/BOARD-1/lock" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected:** Unlock returns board with `status: "unlocked"` and creates a session. Lock returns board with `status: "locked"`.

### 3. Session Flow

```bash
# Check board detail (shows active_session when unlocked)
curl -s "$API/api/boards/BOARD-1" -H "Authorization: Bearer $TOKEN"
```

### 4. Autodarts Observer

```bash
# Check observer status
curl -s "$API/api/kiosk/BOARD-1/observer-status" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected:** `state: "closed"` when no game is active. `state: "monitoring"` when a game is in progress. Requires Chrome/Chromium installed.

### 5. Settings

```bash
# Read branding
curl -s "$API/api/settings/branding" -H "Authorization: Bearer $TOKEN"

# Update branding
curl -s -X PUT "$API/api/settings/branding" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"value": {"cafe_name": "My Cafe", "subtitle": "Welcome"}}'

# Read pricing
curl -s "$API/api/settings/pricing" -H "Authorization: Bearer $TOKEN"
```

### 6. Revenue

```bash
curl -s "$API/api/revenue/summary?days=30" \
  -H "Authorization: Bearer $TOKEN"
```

**Expected:** Returns `total_revenue` (float) and `total_sessions` (int).

---

## Inspecting Logs

### Backend Logs
```bash
# Supervisor logs
tail -100 /var/log/supervisor/backend.err.log

# Key patterns to search for
grep "ERROR\|CRITICAL\|Traceback" /var/log/supervisor/backend.err.log
grep "LICENSE\|BLOCKED" /var/log/supervisor/backend.err.log
grep "AUTODARTS" /var/log/supervisor/backend.err.log
grep "CONFIG" /var/log/supervisor/backend.err.log
```

### Frontend Logs
```bash
tail -50 /var/log/supervisor/frontend.err.log
# Look for "Module not found" or "Failed to compile"
```

### Central Server Logs (when active)
```bash
tail -100 /var/log/supervisor/central_server.err.log
```

---

## Common Failure Modes

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Backend won't start | Import error in server.py | Check `backend.err.log` for `ModuleNotFoundError` |
| Frontend blank page | JS compile error | Check `frontend.err.log` for `Module not found` |
| Board unlock returns 500 | Missing database tables | Delete `darts_kiosk.sqlite` and restart (recreates) |
| Autodarts "not available" | Chrome not installed | Install `chromium-browser` or set `AUTODARTS_MODE=disabled` |
| Settings not saving | Wrong PUT body format | Use `{"value": {"key": "val"}}` wrapper |
| Revenue shows 0 | No finished sessions | Create and finish a session first |
| WebSocket disconnects | Backend restart | Frontend auto-reconnects within seconds |

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `SECRET_KEY` | auto-generated | JWT signing key |
| `AUTODARTS_MODE` | `observer` | `observer` / `desktop` / `disabled` |
| `AUTODARTS_URL` | `https://play.autodarts.io` | Autodarts web app URL |
| `DATA_DIR` | (project root) | Directory for SQLite DB and assets |
| `AGENT_SECRET` | (from .env) | Shared secret for agent pairing |
| `CENTRAL_SERVER_URL` | (none) | Central server URL (disabled in recovery) |
