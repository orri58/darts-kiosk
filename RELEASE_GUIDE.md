# Darts Kiosk — Release & Update Guide

## Uebersicht

Dieses Dokument beschreibt den vollstaendigen Workflow fuer das Erstellen,
Veroeffentlichen und Installieren von Updates fuer das Darts Kiosk System.

---

## 1. Versions-Management

### Single Source of Truth: `VERSION` Datei

Die Datei `VERSION` im Projektroot enthaelt die aktuelle Version als einzelne Zeile:

```
1.6.5
```

Diese Datei wird gelesen von:
- Backend: `/api/system/version` Endpoint
- Update Service: Vergleich mit GitHub Release
- Build Script: Paketnamen

### Version hochzaehlen

Vor jedem Release die VERSION Datei aktualisieren:

```bash
echo "1.7.0" > VERSION
```

### Semantische Versionierung

Format: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking Changes (z.B. neue Datenbank-Migration noetig)
- **MINOR**: Neue Features (z.B. neues Admin-Panel Tab)
- **PATCH**: Bugfixes (z.B. Observer-Fix)

---

## 2. GitHub Repository Struktur

### Was committed wird:

```
backend/           # Python Backend
frontend/          # React Frontend (Source)
release/           # Build Scripts
  windows/         # Windows-spezifische Scripts
  build_release.sh # Release Builder
updater.py         # Standalone Updater (wird ins Paket kopiert)
VERSION            # Versions-Datei
install.sh         # Linux Installer
.gitignore         # Repo Konfiguration
RELEASE_GUIDE.md   # Diese Dokumentation
```

### Was NICHT committed wird (siehe .gitignore):

```
data/              # Datenbank, Assets, Downloads, Backups
logs/              # Log-Dateien
chrome_profile/    # Chrome Kiosk-Profil
*.sqlite*          # Datenbank-Dateien
*.env              # Umgebungsvariablen + Secrets
frontend/build/    # Kompiliertes Frontend
frontend/node_modules/
__pycache__/
release/build/     # Generierte Pakete
release/*.zip
release/*.tar.gz
```

---

## 3. Release erstellen (Developer Workflow)

### Schritt 1: Version aktualisieren

```bash
echo "1.7.0" > VERSION
git add VERSION
git commit -m "Bump version to 1.7.0"
```

### Schritt 2: Release-Pakete bauen

```bash
cd release
bash build_release.sh
```

Dies erstellt drei Pakete in `release/build/`:

| Paket | Dateiname | Inhalt |
|-------|-----------|--------|
| Windows | `darts-kiosk-v1.7.0-windows.zip` | Backend + Frontend Build + Scripts + updater.py |
| Linux | `darts-kiosk-v1.7.0-linux.tar.gz` | Backend + Frontend Build + Docker/Nginx |
| Source | `darts-kiosk-v1.7.0-source.zip` | Kompletter Quellcode |

### Schritt 3: GitHub Release erstellen

1. Gehe zu `https://github.com/{owner}/{repo}/releases/new`
2. Tag: `v1.7.0` (mit `v` Prefix!)
3. Titel: `v1.7.0 - Beschreibung`
4. Release Notes / Changelog eintragen
5. Assets hochladen:
   - `darts-kiosk-v1.7.0-windows.zip`
   - `darts-kiosk-v1.7.0-linux.tar.gz`
   - (Optional) `darts-kiosk-v1.7.0-source.zip`
6. "Publish release" klicken

### Asset Naming Convention

**WICHTIG:** Das exakte Format ist:

```
darts-kiosk-v{VERSION}-windows.zip
darts-kiosk-v{VERSION}-linux.tar.gz
darts-kiosk-v{VERSION}-source.zip
```

Der Updater erkennt Windows-Pakete am Namensmuster `*windows*`.

---

## 4. Release-Paket Struktur (Windows)

Inhalt von `darts-kiosk-v1.7.0-windows.zip`:

```
darts-kiosk-v1.7.0-windows/
  VERSION                    # Versions-Datei
  backend/                   # Anwendungscode
    routers/
    services/
    database/
    server.py
    schemas.py
    dependencies.py
    requirements.txt
  frontend/
    build/                   # Pre-built React App
    src/                     # Source (fuer Dev-Modus)
    package.json
  start.bat                  # Dienste starten
  stop.bat                   # Dienste stoppen
  update.bat                 # Update ausfuehren
  setup_windows.bat          # Erstinstallation
  setup_profile.bat          # Chrome-Profil einrichten
  run_backend.py             # Backend Starter
  credits_overlay.py         # Credits Overlay
  updater.py                 # Standalone Updater
  README.md                  # Anleitung
```

**NICHT im Paket enthalten:**
- `data/` (Datenbank, Assets, Downloads)
- `logs/`
- `chrome_profile/`
- `.env` Dateien
- `node_modules/`

---

## 5. Update installieren (Admin Workflow)

### Ueber das Admin-Panel (empfohlen)

1. **System > Updates** oeffnen
2. **"Auf Updates pruefen"** klicken
3. Wenn Update verfuegbar: **"Update vorbereiten"** klicken
4. Windows-Paket **herunterladen** (Server-Button)
5. Nach Download: **"v{version} installieren"** klicken
6. Das System:
   - Erstellt automatisch ein App-Backup
   - Validiert das Paket
   - Startet den externen Updater
   - Stoppt alle Dienste
   - Ersetzt Anwendungsdateien
   - Startet Dienste neu
   - Fuehrt Health-Check durch
7. **Erfolgsmeldung** oder automatischer Rollback

### Manuell (ueber update.bat)

Falls das Admin-Panel nicht erreichbar ist:

1. Heruntergeladenes Paket nach `data/downloads/` kopieren
2. `update.bat` ausfuehren
3. Anweisungen folgen

---

## 6. Geschuetzte Verzeichnisse

Der Updater ueberschreibt **NIEMALS**:

| Pfad | Inhalt |
|------|--------|
| `data/` | Datenbank, Assets, Downloads, Backups |
| `logs/` | Alle Log-Dateien |
| `chrome_profile/` | Chrome Kiosk-Profil (Login, Extensions) |
| `backend/.env` | Backend-Konfiguration |
| `frontend/.env` | Frontend-Konfiguration |

---

## 7. Rollback

### Ueber das Admin-Panel

1. **System > Backups** oeffnen
2. Im Abschnitt **"Anwendungs-Backups"** das gewuenschte Backup finden
3. **"Rollback"** klicken und bestaetigen
4. Das System stellt die vorherige Version wieder her

### Automatischer Rollback

Wenn nach einem Update der Health-Check fehlschlaegt:

1. Der Updater erkennt den Fehler
2. Stellt automatisch aus dem Backup wieder her
3. Startet die Dienste mit der vorherigen Version
4. Schreibt das Ergebnis in `data/update_result.json`

---

## 8. Konfiguration

### Umgebungsvariablen (backend/.env)

```env
# GitHub Repository fuer Update-Checks
GITHUB_REPO=owner/darts-kiosk

# Optional: GitHub Token fuer private Repos / hoehere Rate-Limits
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Update-Pruefung aktivieren
UPDATE_CHECK_ENABLED=true

# Pruef-Intervall in Stunden
UPDATE_CHECK_INTERVAL_HOURS=24
```

### Private Repositories

Fuer private Repos:
1. GitHub Personal Access Token erstellen (Settings > Developer settings > Tokens)
2. Berechtigung: `repo` (read)
3. Token in `backend/.env` als `GITHUB_TOKEN` eintragen

**WICHTIG:** Token darf NIEMALS im Git-Repository committed werden!

---

## 9. API Endpoints

| Methode | Endpoint | Beschreibung |
|---------|----------|--------------|
| GET | `/api/system/version` | Installierte Version |
| GET | `/api/health` | Health-Check |
| GET | `/api/updates/check` | GitHub Releases pruefen |
| GET | `/api/updates/status` | Version + History |
| POST | `/api/updates/download` | Release-Asset herunterladen |
| GET | `/api/updates/downloads` | Heruntergeladene Assets |
| POST | `/api/updates/backups/create` | App-Backup erstellen |
| GET | `/api/updates/backups` | App-Backups auflisten |
| POST | `/api/updates/install` | Update installieren |
| POST | `/api/updates/rollback` | Rollback ausfuehren |
| GET | `/api/updates/result` | Letztes Update-Ergebnis |
| POST | `/api/updates/result/clear` | Ergebnis bestaetigen |

---

## 10. Update-Ablauf (Technisch)

```
Admin Panel                  Backend                    updater.py
    |                           |                           |
    |--- Check for Updates ---->|                           |
    |<-- Latest Release --------|                           |
    |--- Download Asset ------->|                           |
    |<-- Progress --------------|                           |
    |--- Install Update ------->|                           |
    |                           |--- Create App Backup      |
    |                           |--- Extract & Validate     |
    |                           |--- Write Manifest         |
    |                           |--- Launch updater.py ---->|
    |                           |                           |--- Wait 5s
    |                           |  (backend still running)  |--- Stop Services
    |                           X  (backend stopped)        |--- Replace Files
    |                           |                           |--- Start Services
    |                           |  (backend restarting)     |--- Health Check
    |                           |<--------------------------|
    |--- Poll for Result ------>|                           |
    |<-- Update Result ---------|                           |
```

Bei Fehler im Health-Check:
```
    updater.py
        |--- Health Check FAILED
        |--- Stop Services
        |--- Restore from Backup
        |--- Start Services
        |--- Health Check (rollback)
        |--- Write Result (rolled_back=true)
```
