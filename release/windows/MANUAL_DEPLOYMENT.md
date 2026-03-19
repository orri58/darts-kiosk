# Darts Kiosk v3.5.3 - Windows Deployment Guide

## Uebersicht

Diese Anleitung beschreibt das vollstaendige Deployment eines Darts Kiosk-PCs,
inklusive Anbindung an den zentralen Lizenzserver (api.dartcontrol.io),
Device Registration, Agent-Autostart und Kiosk-Modus.

## Systemanforderungen

- Windows 10/11 (64-bit)
- Python 3.11+ (https://python.org/downloads)
  - WICHTIG: Bei Installation "Add to PATH" aktivieren
- Google Chrome (https://google.com/chrome)
- Netzwerk/Internet (fuer Lizenz-Sync mit api.dartcontrol.io)

## Verzeichnisstruktur

```
C:\DartsKiosk\
  backend\               <- Backend-Server (FastAPI)
  frontend\              <- Frontend (React, pre-built)
  central_server\        <- Zentraler Lizenzserver (optional, nur fuer Self-Hosting)
  agent\                 <- Windows Agent (Autostart, Monitoring)
  kiosk_experimental\    <- Hard-Kiosk-Modus (experimentell)
  data\                  <- Datenbank, Assets, Backups
  logs\                  <- Log-Dateien
  setup_windows.bat      <- Einmalige Einrichtung
  start.bat              <- System starten
  stop.bat               <- System stoppen
  run_backend.py         <- Backend-Launcher mit Watchdog
  VERSION                <- Aktuelle Version
```

---

## Schritt 1: Dateien entpacken

ZIP entpacken nach `C:\DartsKiosk`:

```
Rechtsklick auf darts-kiosk-v3.5.3-windows.zip -> "Alle extrahieren..."
Ziel: C:\DartsKiosk
```

## Schritt 2: Einmalige Einrichtung

```
Doppelklick auf: setup_windows.bat
```

Das Script erledigt automatisch:
1. Verzeichnisse erstellen (data, logs)
2. backend\.env aus Vorlage erstellen
3. Python Virtual Environment (.venv) erstellen
4. Backend-Pakete installieren
5. Playwright Chromium installieren
6. Frontend-Pakete installieren

Dauer: ca. 5-10 Minuten beim ersten Mal.

## Schritt 3: Konfiguration (.env anpassen)

Oeffnen Sie `backend\.env` in einem Texteditor und pruefen Sie:

```env
# === Datenbank ===
DATABASE_URL=sqlite+aiosqlite:///./data/db/darts.sqlite
SYNC_DATABASE_URL=sqlite:///./data/db/darts.sqlite
DATA_DIR=./data

# === Sicherheit (AENDERN!) ===
JWT_SECRET=IHR-SICHERES-PASSWORT-HIER
AGENT_SECRET=IHR-AGENT-GEHEIMNIS-HIER

# === Zentraler Lizenzserver ===
CENTRAL_SERVER_URL=https://api.dartcontrol.io

# === Board-Konfiguration ===
BOARD_ID=BOARD-1
MODE=STANDALONE

# === Autodarts ===
AUTODARTS_URL=https://play.autodarts.io
AUTODARTS_MODE=observer
AUTODARTS_HEADLESS=false
AUTODARTS_MOCK=false

# === Updates ===
UPDATE_CHECK_ENABLED=true
UPDATE_CHECK_INTERVAL_HOURS=24
GITHUB_REPO=
GITHUB_TOKEN=
```

WICHTIG:
- `JWT_SECRET` und `AGENT_SECRET` unbedingt aendern!
- `CENTRAL_SERVER_URL` zeigt auf den produktiven Lizenzserver
- `BOARD_ID` pro Dartboard eindeutig vergeben (BOARD-1, BOARD-2, etc.)

## Schritt 4: System starten

```
Doppelklick auf: start.bat
```

Das Script:
1. Aktiviert die Python .venv
2. Prueft Abhaengigkeiten
3. Erkennt die LAN-IP
4. Startet den Backend-Server (Port 8001, 0.0.0.0)
5. Startet den Windows Agent (Monitoring)
6. Startet Credits-Overlay
7. Oeffnet Chrome im Kiosk-Modus

## Schritt 5: Geraet registrieren

Beim ersten Start zeigt der Kiosk ein "Registrierungs-Overlay".

1. Betreiber-Admin erstellt im Admin-Panel einen Registration-Token
   (Admin -> Licensing -> Tokens -> Neuer Token)
2. Token auf dem Kiosk-PC eingeben
3. Das Geraet registriert sich automatisch beim zentralen Server

Danach synchronisiert der Kiosk regelmaessig seine Lizenz.

## Schritt 6: Lizenz-Sync konfigurieren

Im Admin-Panel unter "Licensing" -> "Sync":
- Server-URL: https://api.dartcontrol.io (sollte vorausgefuellt sein)
- Sync aktivieren
- Interval: z.B. alle 4 Stunden

Der Sync-Client arbeitet offline-faehig:
- Bei Verbindung: Holt aktuelle Lizenz vom Server
- Ohne Verbindung: Verwendet lokalen Cache

---

## Zugriff

### Lokal (auf dem Kiosk-PC)
| Funktion | URL |
|----------|-----|
| Kiosk-UI | http://localhost:8001/kiosk/BOARD-1 |
| Admin-Panel | http://localhost:8001/admin |
| Betreiber-Portal | http://localhost:8001/operator |
| API Health | http://localhost:8001/api/health |

### LAN (andere Geraete im Netzwerk)
| Funktion | URL |
|----------|-----|
| Kiosk-UI | http://[LAN-IP]:8001/kiosk/BOARD-1 |
| Admin-Panel | http://[LAN-IP]:8001/admin |
| Betreiber-Portal | http://[LAN-IP]:8001/operator |

Die LAN-IP wird beim Start angezeigt (z.B. 192.168.1.100).

### Betreiber-Portal
Das Betreiber-Portal unter /operator ist ein separates, read-only Portal fuer
Betreiber. Login mit den Betreiber-Zugangsdaten vom zentralen Server.

Funktionen:
- Uebersicht (Dashboard mit Statusanzeige)
- Geraete (Online/Offline, Binding-Status)
- Lizenzen (Aktiv/Grace/Abgelaufen)
- Kunden und Standorte
- Aktivitaetsprotokoll

---

## Agent (Autostart)

Der Windows Agent ueberwacht den Kiosk-Betrieb.

### Automatischen Start einrichten
```
cd C:\DartsKiosk\agent
python setup_autostart.py
```

Oder manuell ueber Task Scheduler (siehe unten).

### Agent-Funktionen
- Ueberwacht Backend-Prozess
- Startet Backend bei Absturz neu
- Meldet Status an Master-PC (im AGENT-Modus)

---

## Automatischer Start (Task Scheduler)

### Variante A: Task Scheduler GUI

1. `Win+R` -> `taskschd.msc` -> Enter
2. Rechts: "Aufgabe erstellen..."
3. Tab "Allgemein":
   - Name: `DartsKiosk`
   - "Mit hoechsten Privilegien ausfuehren" aktivieren
4. Tab "Trigger":
   - Neu -> "Bei Anmeldung"
5. Tab "Aktionen":
   - Neu -> Programm starten
   - Programm: `C:\DartsKiosk\start.bat`
   - Starten in: `C:\DartsKiosk`
6. Tab "Bedingungen":
   - "Nur starten, wenn Netzwerk verfuegbar" deaktivieren
7. OK

### Variante B: Per Befehl

```cmd
schtasks /create /tn "DartsKiosk" /tr "C:\DartsKiosk\start.bat" /sc onlogon /rl highest
```

---

## System stoppen

```
Doppelklick auf: stop.bat
```

Oder: Im start.bat-Fenster eine Taste druecken.

---

## Troubleshooting

### Backend startet nicht
- Pruefe `logs\backend.log`
- Pruefe ob Port 8001 frei ist: `netstat -an | findstr 8001`
- Pruefe .env Konfiguration

### Lizenz-Sync fehlgeschlagen
- Pruefe Internetverbindung
- Pruefe `CENTRAL_SERVER_URL` in backend\.env
- Pruefe ob api.dartcontrol.io erreichbar ist: `curl https://api.dartcontrol.io/api/health`
- Der Kiosk funktioniert offline mit dem lokalen Cache weiter

### Betreiber-Portal zeigt "Server nicht erreichbar"
- Pruefe ob `CENTRAL_SERVER_URL` korrekt in backend\.env gesetzt ist
- Der Proxy leitet Anfragen an den zentralen Server weiter
- Ohne Verbindung zum zentralen Server ist das Portal nicht nutzbar

### Chrome startet nicht im Kiosk-Modus
- Pruefe ob Chrome installiert ist
- Alle Chrome-Fenster schliessen vor dem Start
- Ggf. Chrome-Profil loeschen: `data\kiosk_ui_profile`

### Agent funktioniert nicht
- Pruefe `agent\AGENT_DEPLOYMENT.md` fuer Details
- Agent benoetigt psutil: `pip install psutil`

---

## Updates

Updates koennen ueber den integrierten Updater eingespielt werden:

1. Im Admin-Panel: System -> Updates pruefen
2. Oder manuell: `python updater.py`

Fuer manuelle Updates:
1. System stoppen (stop.bat)
2. Neues ZIP entpacken (backend/ und frontend/ ersetzen)
3. NICHT ueberschreiben: data/, logs/, backend/.env
4. System starten (start.bat)

---

## Sicherheitshinweise

- `JWT_SECRET` und `AGENT_SECRET` immer aendern (keine Default-Werte!)
- Admin-Passwort nach erstem Login aendern
- Chrome Kiosk-Modus verhindert Zugriff auf andere Anwendungen
- Firewall: Port 8001 nur im lokalen Netzwerk freigeben
- Updates regelmaessig einspielen
