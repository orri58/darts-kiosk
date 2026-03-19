# Darts Kiosk — Server Deploy & Update Anleitung

## Schnell-Update (Normalfall)

```bash
cd /pfad/zum/repo
./deploy_server.sh
```

Das Script führt automatisch aus:
1. `git pull` — neuesten Code holen
2. `docker compose build` — Images neu bauen (inkl. Frontend)
3. `docker compose down && up -d` — Container neu starten
4. `systemctl restart darts-central` — Zentralen Lizenzserver neu starten
5. Healthchecks — prüft ob Backend und Central Server erreichbar sind
6. Status-Übersicht — zeigt Container-Status und URLs

## Voraussetzungen (einmalig)

### Server
- Docker + Docker Compose v2
- Python 3.11+ (für Central Server falls außerhalb Docker)
- Git
- curl

### Erstinstallation
```bash
git clone <repo-url> /opt/darts-kiosk
cd /opt/darts-kiosk

# .env Datei erstellen (einmalig)
cp .env.example .env
# JWT_SECRET, AGENT_SECRET, CENTRAL_ADMIN_PASSWORD anpassen!

# Erstmalig bauen und starten
docker compose build
docker compose up -d
```

## Services

| Service | Port | Typ | Neustart |
|---|---|---|---|
| darts-kiosk-app | 8001 | Docker Container | `docker compose restart app` |
| darts-central | 8002 | systemd Service | `sudo systemctl restart darts-central` |
| nginx (optional) | 80/443 | Docker Container | `docker compose --profile production restart nginx` |

## Healthchecks

```bash
# Kiosk-Backend
curl http://localhost:8001/api/health

# Central Server
curl http://localhost:8002/api/health

# Docker Container Status
docker compose ps
```

## Fehlerbehebung

### Build schlägt fehl
```bash
# Detaillierte Build-Ausgabe
docker compose build --no-cache --progress=plain 2>&1 | tail -30

# Frontend-Dependencies Problem?
cd frontend && npm ci && npm run build
```

### Container startet nicht
```bash
# Logs prüfen
docker compose logs app --tail 50

# Container manuell debuggen
docker compose run --rm app bash
```

### Central Server startet nicht
```bash
# Logs prüfen
sudo journalctl -u darts-central -n 30

# Manuell testen
cd /opt/darts-kiosk
python -m uvicorn central_server.server:app --host 0.0.0.0 --port 8002
```

### Datenbank-Probleme
```bash
# SQLite Datenbank liegt im Docker Volume
docker volume inspect darts-kiosk_darts_data

# Backup erstellen
docker compose exec app sqlite3 /app/data/db/darts.sqlite ".backup '/app/data/backups/backup.sqlite'"
```

### Rollback
```bash
# Auf vorherige Version zurücksetzen
git log --oneline -5
git checkout <commit-hash>
docker compose build && docker compose up -d
```

## systemd Unit für Central Server

Falls nicht vorhanden, erstelle `/etc/systemd/system/darts-central.service`:

```ini
[Unit]
Description=Darts Central License Server
After=network.target

[Service]
Type=simple
User=darts
WorkingDirectory=/opt/darts-kiosk
Environment=CENTRAL_DATA_DIR=/opt/darts-kiosk/central_server/data
Environment=CENTRAL_JWT_SECRET=HIER-SICHERES-SECRET
Environment=CENTRAL_ADMIN_PASSWORD=HIER-SICHERES-PASSWORT
ExecStart=/usr/bin/python3 -m uvicorn central_server.server:app --host 0.0.0.0 --port 8002
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable darts-central
sudo systemctl start darts-central
```
