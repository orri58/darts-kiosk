# Darts Kiosk v3.0 — Hard-Kiosk Deployment Guide

## Uebersicht

Dieses System verwandelt einen normalen Windows-PC in ein dediziertes Darts-Kiosk-Terminal.

**Nach der Installation:**
- PC startet automatisch in den Kiosk-Modus
- Kein Desktop, keine Taskleiste, kein Explorer
- Nur das Darts-System ist sichtbar
- Automatische Dienst-Ueberwachung und -Wiederherstellung

## Systemanforderungen

- Windows 10/11 (64-bit)
- Python 3.11+ installiert und im PATH
- Google Chrome installiert
- Administratorrechte fuer die Installation
- Netzwerkverbindung (fuer LAN-Zugriff)

## Installation

### Schritt 1: Release entpacken
Entpacke `darts-kiosk-vX.X.X-windows.zip` in einen beliebigen Ordner.

### Schritt 2: Installer ausfuehren
```
Rechtsklick auf setup_kiosk.bat -> "Als Administrator ausfuehren"
```

Der Installer:
1. Prueft Systemanforderungen (Python, Chrome)
2. Kopiert alle Dateien nach `C:\DartsKiosk`
3. Erstellt Python Virtual Environment
4. Erstellt Kiosk-Benutzer `DartsKiosk`
5. Konfiguriert Windows Auto-Login
6. Ersetzt die Windows-Shell durch den Kiosk-Launcher
7. Haertet den Kiosk-Benutzer (kein Task-Manager, kein Desktop, etc.)
8. Konfiguriert Firewall, Energieoptionen, Benachrichtigungen
9. Bietet Neustart an

### Schritt 3: Neustart
Nach dem Neustart:
- Windows meldet sich automatisch als `DartsKiosk` an
- Der Kiosk-Launcher startet Backend + Chrome
- Chrome oeffnet die Kiosk-UI im Vollbildmodus

## Architektur

```
C:\DartsKiosk\
  kiosk_shell.vbs       <-- Windows-Shell (startet statt explorer.exe)
  darts_launcher.bat    <-- Service-Supervisor (startet Backend + Chrome)
  maintenance.bat       <-- Wartungs-Tool (Passwort-geschuetzt)
  uninstall_kiosk.bat   <-- Rollback / Deinstallation
  kiosk_config.bat      <-- Konfiguration (vom Installer generiert)
  run_backend.py        <-- Backend-Starter mit Watchdog
  backend/              <-- FastAPI Backend
  frontend/             <-- React Frontend (pre-built)
  data/                 <-- Datenbank, Chrome-Profile, Assets
  logs/                 <-- Log-Dateien
  .venv/                <-- Python Virtual Environment
```

## Shell-Ersetzung

### Wie es funktioniert
```
Windows Login
  -> Kiosk-User: kiosk_shell.vbs -> darts_launcher.bat -> Backend + Chrome
  -> Admin-User: kiosk_shell.vbs -> explorer.exe (normaler Desktop)
```

`kiosk_shell.vbs` prueft den Benutzernamen:
- **DartsKiosk**: Startet den Kiosk-Launcher (kein Desktop)
- **Jeder andere User**: Startet explorer.exe normal

### Warum VBS statt .bat?
Ein `.bat`-File als Shell wuerde ein sichtbares Konsolenfenster zeigen.
Das VBS-Skript startet den Launcher unsichtbar im Hintergrund.

## Maintenance / Wartung

### Zugang zum Admin-Konto
1. `Strg+Alt+Entf` druecken
2. "Benutzer wechseln" waehlen
3. Als Administrator anmelden
4. `DartsKiosk Maintenance.bat` auf dem Desktop ausfuehren

### Maintenance-Optionen
| Option | Funktion |
|--------|----------|
| 1 | Explorer temporaer starten |
| 2 | Kiosk-Modus neu starten |
| 3 | Alle Dienste stoppen |
| 4 | Backend-Status pruefen |
| 5 | Backend-Logs anzeigen |
| 6 | Launcher-Logs anzeigen |
| 7 | System-Update |
| 8 | Vollstaendige Deinstallation |
| 9 | System neu starten |

## Prozess-Ueberwachung (Watchdog)

Der Launcher ueberwacht alle 10 Sekunden:
- **Backend**: Health-Check via `http://localhost:8001/api/health`
- **Chrome**: Prozesscheck via `tasklist`

Bei Absturz:
- Automatischer Neustart
- Log-Eintrag in `logs\launcher.log`
- Max 10 Restarts, danach 60s Pause

## Deinstallation / Rollback

```
Als Administrator: C:\DartsKiosk\uninstall_kiosk.bat
```

Der Uninstaller:
1. Stoppt alle Dienste
2. Stellt `Shell = explorer.exe` wieder her
3. Deaktiviert Auto-Login
4. Entfernt Kiosk-Richtlinien
5. Entfernt Firewall-Regel
6. Optional: Loescht Kiosk-Benutzer
7. Bietet Neustart an

**Hinweis:** Anwendungsdateien in `C:\DartsKiosk` werden NICHT geloescht.
Die Datenbank und Einstellungen bleiben erhalten.

## Troubleshooting

### Kiosk startet nicht nach Neustart
1. `Strg+Alt+Entf` -> Benutzer wechseln -> Admin
2. `C:\DartsKiosk\logs\launcher.log` pruefen
3. `C:\DartsKiosk\logs\shell.log` pruefen

### Backend laeuft nicht
1. Maintenance-Tool -> Option 4 (Status)
2. Maintenance-Tool -> Option 5 (Logs)
3. Manuell: `python C:\DartsKiosk\run_backend.py`

### Chrome zeigt Fehlermeldung
1. Chrome-Profil zuruecksetzen:
   Loeschen: `C:\DartsKiosk\data\kiosk_ui_profile`
2. Kiosk neu starten (Maintenance -> Option 2)

### Notfall: Shell wiederherstellen
Falls kein Admin-Zugang moeglich:
1. Im abgesicherten Modus starten (F8 beim Boot)
2. `regedit` oeffnen
3. `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon`
4. `Shell` auf `explorer.exe` setzen
5. Normal neu starten
