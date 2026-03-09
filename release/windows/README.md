# Darts Kiosk - Windows Board PC

Production-Setup fuer den Windows Board-PC.
Das Backend bedient sowohl die API als auch das Frontend auf einem einzigen Port.

## Schnellstart

```
1. setup_windows.bat        (einmalig: .venv, Pakete, Playwright)
2. start.bat                (startet Backend + Overlay + Chrome Kiosk)
3. stop.bat                 (beendet alle Dienste)
```

## Voraussetzungen

- Windows 10/11 (64-bit)
- Python 3.11+ (python.org, PATH aktiviert)
- Google Chrome (fuer Kiosk-Modus und Autodarts-Observer)
- Microsoft Visual C++ Redistributable x64

## Dateien

| Datei | Beschreibung |
|---|---|
| `setup_windows.bat` | Einmalige Einrichtung (.venv, Pakete, Playwright) |
| `start.bat` | Startet alle Dienste (Backend, Overlay, Chrome) |
| `stop.bat` | Beendet alle Dienste |
| `autostart.bat` | Richtet Windows-Autostart ein |
| `update.bat` | Fuehrt ein heruntergeladenes Update aus |
| `_run_backend.bat` | Interner Helper: startet Backend mit .venv |
| `run_backend.py` | Backend-Launcher mit Watchdog |
| `credits_overlay.py` | Credits-Overlay (Tkinter, always-on-top) |

## Zugriff

Alle Dienste laufen auf Port **8001**:

| Seite | Lokal | LAN |
|---|---|---|
| Kiosk | http://localhost:8001/kiosk/BOARD-1 | http://LAN-IP:8001/kiosk/BOARD-1 |
| Admin-Panel | http://localhost:8001/admin | http://LAN-IP:8001/admin |
| API Health | http://localhost:8001/api/health | http://LAN-IP:8001/api/health |

Die LAN-IP wird beim Start automatisch erkannt und angezeigt.

## Architektur (Production)

```
Port 8001 (einziger Port):
  /api/*     -> FastAPI Backend (REST + WebSocket)
  /static/*  -> Frontend JS/CSS/Images
  /*         -> SPA catch-all (index.html)

Kein Node.js zur Laufzeit noetig.
Kein separater Frontend-Server.
Das Backend ist der einzige Serverprozess.
```

## Fehlerbehebung

- Backend startet nicht: `logs\backend.log` pruefen
- Chrome startet nicht: Chrome manuell pruefen, Pfad in start.bat
- greenlet-Fehler: VC++ Redistributable x64 installieren
- LAN-Zugriff: Windows-Firewall fuer Port 8001 freigeben
- Overlay fehlt: `credits_overlay.py` muss im Installationsverzeichnis liegen
