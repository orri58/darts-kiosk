# Darts Kiosk v3.5.3 - Windows Board PC

Production-Setup fuer den Windows Board-PC mit zentraler Lizenzverwaltung.

## Schnellstart

```
1. setup_windows.bat        (einmalig: .venv, Pakete, Playwright)
2. backend\.env pruefen     (CENTRAL_SERVER_URL, JWT_SECRET aendern!)
3. start.bat                (startet Backend + Agent + Overlay + Chrome Kiosk)
4. stop.bat                 (beendet alle Dienste)
```

## Voraussetzungen

- Windows 10/11 (64-bit)
- Python 3.11+ (python.org, PATH aktiviert)
- Google Chrome (fuer Kiosk-Modus und Autodarts-Observer)
- Microsoft Visual C++ Redistributable x64
- Internetverbindung (fuer Lizenz-Sync)

## Dateien

| Datei | Beschreibung |
|---|---|
| `setup_windows.bat` | Einmalige Einrichtung (.venv, Pakete, Playwright) |
| `start.bat` | Startet alle Dienste (Backend, Agent, Overlay, Chrome) |
| `stop.bat` | Beendet alle Dienste |
| `autostart.bat` | Richtet Windows-Autostart ein |
| `update.bat` | Fuehrt ein heruntergeladenes Update aus |
| `_run_backend.bat` | Interner Helper: startet Backend mit .venv |
| `run_backend.py` | Backend-Launcher mit Watchdog |
| `credits_overlay.py` | Credits-Overlay (Tkinter, always-on-top) |

## Verzeichnisse

| Verzeichnis | Beschreibung |
|---|---|
| `backend/` | FastAPI Backend-Server |
| `frontend/` | React Frontend (pre-built) |
| `agent/` | Windows Agent (Autostart, Monitoring) |
| `central_server/` | Zentraler Lizenzserver (optional, fuer Self-Hosting) |
| `data/` | Datenbank, Assets, Chrome-Profil |
| `logs/` | Log-Dateien |

## Zugriff

Alle Dienste laufen auf Port **8001**:

| Seite | Lokal | LAN |
|---|---|---|
| Kiosk | http://localhost:8001/kiosk/BOARD-1 | http://LAN-IP:8001/kiosk/BOARD-1 |
| Admin-Panel | http://localhost:8001/admin | http://LAN-IP:8001/admin |
| Betreiber-Portal | http://localhost:8001/operator | http://LAN-IP:8001/operator |
| API Health | http://localhost:8001/api/health | http://LAN-IP:8001/api/health |

Die LAN-IP wird beim Start automatisch erkannt und angezeigt.

## Zentrale Lizenzierung

Der Kiosk synchronisiert automatisch mit dem zentralen Server:

- **CENTRAL_SERVER_URL**: https://api.dartcontrol.io (in backend\.env)
- **Sync**: Automatisch im Hintergrund (konfigurierbar im Admin-Panel)
- **Offline-Betrieb**: Kiosk funktioniert mit lokalem Cache auch ohne Server
- **Device Registration**: Einmal-Token fuer sichere Erstregistrierung
- **Betreiber-Portal**: Unter /operator (read-only Uebersicht fuer Betreiber)

## Architektur

```
Port 8001 (einziger Port):
  /api/*         -> FastAPI Backend (REST + WebSocket)
  /api/central/* -> Proxy zum zentralen Lizenzserver
  /static/*      -> Frontend JS/CSS/Images
  /*             -> SPA catch-all (index.html)

Kein Node.js zur Laufzeit noetig.
Das Backend ist der einzige Serverprozess.
```

## Fehlerbehebung

- Backend startet nicht: `logs\backend.log` pruefen
- Chrome startet nicht: Chrome manuell pruefen, Pfad in start.bat
- greenlet-Fehler: VC++ Redistributable x64 installieren
- LAN-Zugriff: Windows-Firewall fuer Port 8001 freigeben
- Lizenz-Sync fehlt: `CENTRAL_SERVER_URL` in backend\.env pruefen
- Agent startet nicht: `agent\AGENT_DEPLOYMENT.md` lesen

Ausfuehrliche Anleitung: MANUAL_DEPLOYMENT.md
