# Darts Kiosk - Windows Test Bundle

## Voraussetzungen

| Software   | Version | Download |
|-----------|---------|----------|
| Python    | 3.11+   | https://www.python.org/downloads/ |
| Node.js   | 18+     | https://nodejs.org/ (LTS) |

> **WICHTIG**: Bei der Python-Installation **"Add Python to PATH"** ankreuzen!

## Installation (einmalig)

```
1. ZIP entpacken
2. check_requirements.bat  ausführen (prüft Python + Node)
3. setup_windows.bat       ausführen (installiert alle Abhängigkeiten)
```

## Starten

```
4. start.bat               ausführen
5. Browser öffnet sich     → Setup-Wizard durchlaufen
```

## URLs

| Seite          | URL |
|---------------|-----|
| Setup-Wizard  | http://localhost:3000/setup |
| Admin-Panel   | http://localhost:3000/admin |
| Kiosk         | http://localhost:3000/kiosk/BOARD-1 |
| Backend-API   | http://localhost:8001/api/health |

## Beenden

- `stop.bat` ausführen, oder
- Im `start.bat`-Fenster eine Taste drücken

## Logs

- `logs\backend.log` — Backend-Ausgaben und Fehler
- `logs\frontend.log` — Frontend-Kompilierung

## Fehlerbehebung

**Backend startet nicht:**
- `logs\backend.log` prüfen
- Port 8001 belegt? → ` `

**Frontend startet nicht:**
- `logs\frontend.log` prüfen  
- Port 3000 belegt? → `stop.bat` ausführen, dann `start.bat`

**Playwright/Autodarts funktioniert nicht:**
- `cd backend && python -m playwright install chromium`

## Daten

- Datenbank: `data\db\darts.sqlite`
- Assets: `data\assets\`
- Sounds: `data\assets\sounds\`
- Backups: `data\backups\`
