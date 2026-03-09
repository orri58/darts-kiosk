# Darts Kiosk - Windows Test Bundle

## Voraussetzungen

| Software   | Version  | Download |
|-----------|----------|----------|
| Python    | 3.11 oder 3.12 | https://www.python.org/downloads/ |
| Node.js   | **20 LTS** (empfohlen) | https://nodejs.org/ → **LTS** wählen |
| VC++ Redist x64 | Aktuell | https://aka.ms/vs/17/release/vc_redist.x64.exe |

> **WICHTIG bei Python**: "Add Python to PATH" ankreuzen!
>
> **WICHTIG bei Node.js**: Die **LTS**-Version wählen (z.B. 20.x), **NICHT** "Current" (25.x ist inkompatibel).
>
> **VC++ Redistributable**: Wird für SQLAlchemy (greenlet) benötigt. Auf den meisten PCs bereits vorhanden. Falls Backend-Start fehlschlägt, bitte installieren.

## Installation (einmalig)

```
1. ZIP entpacken
2. check_requirements.bat  → prüft Python, Node, VC++ Redistributable
3. setup_windows.bat       → erstellt .venv, installiert Abhängigkeiten
```

Das Setup erstellt eine isolierte Python-Umgebung (`.venv`) im Projektordner.

## Starten

```
4. start.bat               → startet Backend + Frontend
5. Browser öffnet sich     → Setup-Wizard durchlaufen
```

`start.bat` aktiviert die `.venv` automatisch und prüft greenlet beim Start.

## URLs

| Seite          | Von diesem PC | Von anderen Geräten (LAN) |
|---------------|---------------|--------------------------|
| Setup-Wizard  | http://localhost:3000/setup | http://\<LAN-IP\>:3000/setup |
| Admin-Panel   | http://localhost:3000/admin | http://\<LAN-IP\>:3000/admin |
| Kiosk         | http://localhost:3000/kiosk/BOARD-1 | http://\<LAN-IP\>:3000/kiosk/BOARD-1 |
| Backend-API   | http://localhost:8001/api/health | http://\<LAN-IP\>:8001/api/health |

Die LAN-IP wird automatisch von `start.bat` erkannt und angezeigt.

## Beenden

- `stop.bat` ausführen, oder
- Im `start.bat`-Fenster eine Taste drücken

## Logs

- `logs\backend.log` — Backend-Ausgaben und Fehler
- `logs\frontend.log` — Frontend-Kompilierung

## Fehlerbehebung

**"greenlet kann nicht geladen werden":**
- Microsoft VC++ Redistributable x64 installieren: https://aka.ms/vs/17/release/vc_redist.x64.exe
- Danach `setup_windows.bat` erneut ausführen

**Backend startet nicht:**
- `logs\backend.log` prüfen
- Port 8001 belegt? → `stop.bat`, dann `start.bat`

**Frontend startet nicht / "ENOTFOUND":**
- `logs\frontend.log` prüfen
- Node.js Version prüfen: `node --version` (muss 18-22 sein, NICHT 25+)
- Port 3000 belegt? → `stop.bat`, dann `start.bat`

**Playwright/Autodarts funktioniert nicht:**
- `.venv\Scripts\activate` → `python -m playwright install chromium`

**LAN-Zugriff funktioniert nicht (vom Handy):**
- Windows-Firewall: Port 3000 und 8001 freigeben
- Beide Geräte im gleichen Netzwerk?

## Dateistruktur

```
darts-kiosk-v1.0.0-windows/
├── .venv/                  ← Python-Umgebung (nach Setup)
├── backend/
│   ├── .env                ← Backend-Konfiguration
│   └── ...
├── frontend/
│   ├── .env                ← Frontend-URL (wird automatisch gesetzt)
│   └── ...
├── data/
│   ├── db/darts.sqlite     ← Datenbank
│   ├── assets/sounds/      ← Sound-Dateien
│   └── backups/            ← Automatische Backups
├── logs/
├── check_requirements.bat  ← Schritt 1: Voraussetzungen
├── setup_windows.bat       ← Schritt 2: Einrichtung
├── start.bat               ← Schritt 3: Starten
├── stop.bat                ← Beenden
├── _run_backend.bat        ← (intern, nicht manuell starten)
└── _run_frontend.bat       ← (intern, nicht manuell starten)
```
