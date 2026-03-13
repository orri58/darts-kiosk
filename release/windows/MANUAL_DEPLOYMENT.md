# Darts Kiosk - Manuelle Windows-Bereitstellung

## Uebersicht

Diese Anleitung beschreibt den empfohlenen Deployment-Pfad fuer Windows.
Der Ansatz ist bewusst manuell und transparent - jeder Schritt ist nachvollziehbar.

## Systemanforderungen

- Windows 10/11 (64-bit)
- Python 3.11+ (https://python.org/downloads)
  - WICHTIG: Bei Installation "Add to PATH" aktivieren
- Google Chrome (https://google.com/chrome)
- Netzwerkverbindung fuer LAN-Zugriff (optional)

## Schritt 1: Dateien entpacken

ZIP entpacken nach `C:\DartsKiosk` (oder beliebiger Pfad):

```
C:\DartsKiosk\
  backend\
  frontend\
  setup_windows.bat
  start.bat
  stop.bat
  run_backend.py
  VERSION
```

## Schritt 2: Einmalige Einrichtung

```
Doppelklick auf: setup_windows.bat
```

Das Script erledigt automatisch:
1. Verzeichnisse erstellen (data, logs)
2. backend\.env aus Vorlage erstellen
3. Python Virtual Environment (.venv) erstellen
4. Backend-Pakete installieren (FastAPI, SQLAlchemy, etc.)
5. Playwright Chromium installieren
6. Frontend-Pakete installieren

Dauer: ca. 5-10 Minuten beim ersten Mal.

## Schritt 3: System starten

```
Doppelklick auf: start.bat
```

Das Script:
1. Aktiviert die Python .venv
2. Startet den Backend-Server (Port 8001)
3. Oeffnet Chrome im Kiosk-Modus

## Schritt 4: System stoppen

```
Doppelklick auf: stop.bat
```

Oder: Im start.bat-Fenster `S` druecken.

---

## Automatischer Start (Task Scheduler)

Fuer den Dauerbetrieb kann der Start automatisiert werden.

### Variante A: Task Scheduler GUI

1. `Win+R` -> `taskschd.msc` -> Enter
2. Rechts: "Aufgabe erstellen..."
3. Tab "Allgemein":
   - Name: `DartsKiosk`
   - "Mit hoechsten Privilegien ausfuehren" aktivieren
   - Konfigurieren fuer: Windows 10
4. Tab "Trigger":
   - Neu -> "Bei Anmeldung"
   - Ggf. spezifischen Benutzer waehlen
5. Tab "Aktionen":
   - Neu -> "Programm starten"
   - Programm: `cmd.exe`
   - Argumente: `/c "C:\DartsKiosk\start.bat"`
   - Starten in: `C:\DartsKiosk`
6. Tab "Einstellungen":
   - "Aufgabe bei Bedarf ausfuehren" aktivieren
   - "Aufgabe nicht beenden" waehlen bei Zeitlimit
7. OK -> Fertig

### Variante B: Kommandozeile (als Administrator)

```cmd
schtasks /create ^
    /tn "DartsKiosk" ^
    /tr "cmd.exe /c \"C:\DartsKiosk\start.bat\"" ^
    /sc onlogon ^
    /rl highest ^
    /f
```

### Task entfernen

```cmd
schtasks /delete /tn "DartsKiosk" /f
```

### Task manuell ausfuehren

```cmd
schtasks /run /tn "DartsKiosk"
```

---

## Chrome Kiosk-Modus (manuell)

Falls Chrome separat gestartet werden soll:

```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
    --kiosk ^
    --user-data-dir="C:\DartsKiosk\data\kiosk_ui_profile" ^
    --no-first-run ^
    --disable-infobars ^
    --disable-session-crashed-bubble ^
    --disable-translate ^
    "http://localhost:8001/kiosk/BOARD-1"
```

Chrome Kiosk-Modus beenden: `Alt+F4`

---

## Backend manuell starten

```cmd
cd C:\DartsKiosk
.venv\Scripts\activate.bat
python run_backend.py
```

Backend-Health pruefen:
```
http://localhost:8001/api/health
```

Admin-Panel:
```
http://localhost:8001/admin
```

---

## LAN-Zugriff

Der Backend-Server bindet standardmaessig auf `0.0.0.0:8001`.
Andere Geraete im LAN koennen zugreifen via:

```
http://<IP-DES-KIOSK-PC>:8001
```

### Firewall-Regel (als Administrator)

```cmd
netsh advfirewall firewall add rule ^
    name="DartsKiosk Backend" ^
    dir=in action=allow ^
    protocol=TCP localport=8001
```

---

## Energieoptionen (Standby deaktivieren)

```cmd
powercfg -change -standby-timeout-ac 0
powercfg -change -monitor-timeout-ac 0
```

---

## Verzeichnisstruktur nach Einrichtung

```
C:\DartsKiosk\
  backend\          Backend-Quellcode + .env
  frontend\         React-Build (statisch)
  data\
    db\             SQLite-Datenbank
    assets\         Uploads, Sounds
    backups\        Automatische DB-Backups
    chrome_profile\ Autodarts Chrome-Profil
    kiosk_ui_profile\ Kiosk Chrome-Profil
  logs\             Log-Dateien
  .venv\            Python Virtual Environment
  start.bat         Start-Script
  stop.bat          Stop-Script
  setup_windows.bat Einmaliges Setup
  run_backend.py    Backend-Starter
  VERSION           Versionsnummer
```

---

## Troubleshooting

### Backend startet nicht
1. `.venv\Scripts\activate.bat` ausfuehren
2. `python run_backend.py` manuell starten
3. Fehlermeldung lesen

### Chrome zeigt Fehler
1. `data\kiosk_ui_profile` loeschen (Chrome-Cache)
2. Chrome neu starten

### Autodarts-Login abgelaufen
1. Chrome-Profil unter `data\chrome_profile\BOARD-1` pruefen
2. Ggf. manuell bei Autodarts einloggen

### Port 8001 belegt
1. `netstat -ano | findstr 8001`
2. Prozess beenden oder Port in backend\.env aendern

---

## Spaetere Haertung (optional, nicht fuer Erstbetrieb)

Die folgenden Schritte sind OPTIONAL und sollten erst durchgefuehrt werden,
wenn die Runtime stabil laeuft und manuell verifiziert wurde.

### 1. Dedizierter Kiosk-Benutzer erstellen (als Administrator)

```cmd
net user DartsKiosk <PASSWORT> /add
net localgroup Users DartsKiosk /add
wmic useraccount where "name='DartsKiosk'" set PasswordExpires=false
```

Berechtigungen fuer den Kiosk-User setzen:
```cmd
icacls "C:\DartsKiosk" /grant "DartsKiosk:(OI)(CI)F" /T
```

### 2. Windows Auto-Login (als Administrator)

```cmd
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon /t REG_SZ /d "1" /f
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultUserName /t REG_SZ /d "DartsKiosk" /f
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultPassword /t REG_SZ /d "<PASSWORT>" /f
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultDomainName /t REG_SZ /d "%COMPUTERNAME%" /f
```

Auto-Login deaktivieren:
```cmd
reg add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon /t REG_SZ /d "0" /f
```

### 3. Taskleiste automatisch ausblenden

Rechtsklick auf Taskleiste -> Taskleisteneinstellungen:
- "Taskleiste automatisch ausblenden" aktivieren

Oder per Registry (erfordert Ab-/Anmeldung):
```cmd
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\StuckRects3" /v Settings /t REG_BINARY /d ... /f
```
(Manuelle Einstellung per GUI ist zuverlaessiger)

### 4. Windows Update Neustart verhindern (als Administrator)

```cmd
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /t REG_DWORD /d 1 /f
```

### 5. Benachrichtigungen reduzieren

```cmd
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\Explorer" /v DisableNotificationCenter /t REG_DWORD /d 1 /f
```

### 6. Energieoptionen (ausfuehrlich)

```cmd
powercfg -change -standby-timeout-ac 0
powercfg -change -monitor-timeout-ac 0
powercfg -change -hibernate-timeout-ac 0
powercfg -change -standby-timeout-dc 0
powercfg -change -monitor-timeout-dc 0
```

### 7. Firewall fuer LAN-Zugriff (als Administrator)

```cmd
netsh advfirewall firewall add rule name="DartsKiosk Backend" dir=in action=allow protocol=TCP localport=8001
```

Regel entfernen:
```cmd
netsh advfirewall firewall delete rule name="DartsKiosk Backend"
```

### 8. Chrome immer im Vollbild starten

Chrome mit `--kiosk` Flag startet automatisch im Vollbild-Modus.
Die start.bat macht das bereits. Kiosk-Modus beenden: `Alt+F4`.

---

## NICHT empfohlen (experimentell)

Die folgenden Massnahmen sind EXPERIMENTELL und koennen das System
in einen nicht-bootfaehigen Zustand versetzen:

- Windows Shell ersetzen (explorer.exe -> custom script)
- Task-Manager per Policy komplett deaktivieren
- Desktop/Explorer per Policy komplett deaktivieren
- Globale Kiosk-Policies anwenden

Dateien dafuer finden sich unter `kiosk_experimental\`.
NUR verwenden mit:
- Funktionierendem System-Backup / Recovery-Medium
- Zugang zum abgesicherten Modus
- Verstaendnis der Registry-Aenderungen
- Getesteter Runtime (alle Flows stabil)
