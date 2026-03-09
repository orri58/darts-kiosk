# GitHub Setup — Vollstaendige Anleitung fuer das Darts Kiosk Update-System

## Uebersicht

Dieses Dokument ist die exakte Schritt-fuer-Schritt Anleitung zum Einrichten
des GitHub-basierten Update-Systems fuer das Darts Kiosk Projekt.

---

## 1. WAS EMERGENT BEREITS KONFIGURIERT HAT

Die folgenden Dateien sind bereits im Projekt vorbereitet und einsatzbereit:

| Datei | Zweck | Status |
|-------|-------|--------|
| `VERSION` | Single Source of Truth fuer die Versionsnummer | Erstellt (1.6.5) |
| `.gitignore` | Schuetzt Laufzeitdaten, .env, Datenbank vor versehentlichem Commit | Erstellt |
| `.github/workflows/build-release.yml` | GitHub Actions Workflow: baut alle 3 Release-Pakete automatisch | Erstellt |
| `backend/.env.example` | Template fuer Backend-Konfiguration | Erstellt |
| `frontend/.env.example` | Template fuer Frontend-Konfiguration | Erstellt |
| `updater.py` | Standalone Updater (stop → replace → restart → health check → rollback) | Erstellt |
| `release/windows/update.bat` | Windows Wrapper fuer manuelles Update | Erstellt |
| `RELEASE_GUIDE.md` | Dokumentation fuer Release-Workflow | Erstellt |
| `backend/services/update_service.py` | GitHub API Integration (check, download, history) | Erstellt |
| `backend/services/updater_service.py` | Backup, Extract, Validate, Manifest, Launch | Erstellt |
| `backend/routers/updates.py` | REST API fuer alle Update-Operationen | Erstellt |
| `frontend/src/pages/admin/System.js` | Admin UI: Install, Rollback, Backups, Progress | Erstellt |

### Version-Vergleichslogik (verifiziert im Code)

```python
# backend/services/update_service.py, Zeile 74-91
# Semantic Versioning: vergleicht (major, minor, patch) als Integer-Tuple
# Tag-Format: "v1.7.0" → wird zu "1.7.0" → Tuple (1, 7, 0)
# Vergleich: (1, 7, 0) > (1, 6, 5) → True → update_available
```

### Erwartete Umgebungsvariablen (verifiziert im Code)

| Variable | Datei | Pflicht | Beschreibung |
|----------|-------|---------|--------------|
| `GITHUB_REPO` | `backend/.env` | Ja (fuer Updates) | Format: `owner/repo` z.B. `orri/darts-kiosk` |
| `GITHUB_TOKEN` | `backend/.env` | Nein (public repo) / Ja (private) | GitHub PAT |
| `UPDATE_CHECK_ENABLED` | `backend/.env` | Nein (default: true) | Background-Check aktivieren |
| `UPDATE_CHECK_INTERVAL_HOURS` | `backend/.env` | Nein (default: 24) | Pruef-Intervall |

### Erwartete Release-Asset-Dateinamen (exakt!)

Der Code in `update_service.py` Zeile 214-234 erkennt Plattformen anhand von Keywords im Dateinamen:

| Plattform | Dateiname | Erkennungs-Keyword |
|-----------|-----------|-------------------|
| **Windows** | `darts-kiosk-v{VERSION}-windows.zip` | `windows` oder `win` |
| **Linux** | `darts-kiosk-v{VERSION}-linux.tar.gz` | `linux` |
| **Source** | `darts-kiosk-v{VERSION}-source.zip` | `source` (Fallback) |

**WICHTIG:** Der Updater (`updater_service.py` Zeile 147-210) validiert:
- Zip enthaelt `backend/` Ordner (Pflicht)
- Zip enthaelt `VERSION` Datei (Pflicht)
- Zip enthaelt KEIN `data/` Ordner (Warnung)
- VERSION-Inhalt stimmt mit Zielversion ueberein

### Erwartete Tag-/Release-Naming-Convention

```
Tag:      v1.7.0      (mit "v" Prefix)
Release:  v1.7.0      (gleich wie Tag)
Assets:   darts-kiosk-v1.7.0-windows.zip
          darts-kiosk-v1.7.0-linux.tar.gz
          darts-kiosk-v1.7.0-source.zip
```

Der Code in `update_service.py` Zeile 139-140 strippt das "v" Prefix fuer den Versionsvergleich:
```python
tag = r.get("tag_name", "")     # "v1.7.0"
version = tag.lstrip("v")       # "1.7.0"
```

---

## 2. MANUELLE GITHUB-CHECKLISTE

### A. PFLICHT — Muss konfiguriert werden

#### A1. GitHub Repository erstellen

```
GitHub.com → "+" (oben rechts) → New repository

  Repository name:  darts-kiosk
  Visibility:       Public (empfohlen) oder Private
  Initialize:       NICHT ankreuzen (wir pushen bestehenden Code)
  
  → "Create repository"
```

#### A2. Code zum Repository pushen

```bash
# Im Projektverzeichnis auf deinem PC:
cd /pfad/zum/darts-kiosk

git init
git add .
git commit -m "Initial commit v1.6.5"
git branch -M main
git remote add origin https://github.com/orri/darts-kiosk.git
git push -u origin main
```

#### A3. GitHub Actions aktivieren

```
GitHub.com → dein Repository → Settings → Actions → General

  Actions permissions:
    ✅ "Allow all actions and reusable workflows"
  
  Workflow permissions:
    ✅ "Read and write permissions"
    ✅ "Allow GitHub Actions to create and approve pull requests"
    
  → "Save"
```

**WARUM:** Der Workflow braucht `contents: write` um Releases zu erstellen und Assets hochzuladen. Das ist ueber `permissions: contents: write` im Workflow definiert, aber die Repo-Einstellung muss es erlauben.

#### A4. GITHUB_REPO auf dem Board-PC konfigurieren

```
Auf dem Windows Board-PC:

  Oeffne: backend\.env
  
  Aendere:
    GITHUB_REPO=orri/darts-kiosk
    
  Neustart:
    stop.bat
    start.bat
```

#### A5. Ersten Release erstellen (manuell oder via Tag)

**Option 1: Via Git Tag (empfohlen — triggert automatischen Build)**

```bash
# Version in VERSION Datei setzen (falls noch nicht geschehen)
echo "1.7.0" > VERSION
git add VERSION
git commit -m "Bump version to 1.7.0"
git tag v1.7.0
git push origin main --tags
```

→ GitHub Actions baut automatisch alle 3 Pakete und erstellt den Release.

**Option 2: Via Manuellen Workflow Dispatch**

```
GitHub.com → dein Repository → Actions → "Build Release Packages"
  → "Run workflow"
  → Branch: main
  → version_override: (leer lassen oder z.B. "1.7.0")
  → "Run workflow"
```

**Option 3: Komplett manuell (ohne Actions)**

```
GitHub.com → dein Repository → Releases → "Create a new release"

  Tag:                v1.7.0 (neu erstellen)
  Target:             main
  Release title:      v1.7.0 - Beschreibung
  Description:        Changelog hier einfuegen
  
  Attach binaries:
    darts-kiosk-v1.7.0-windows.zip   (lokal gebaut mit build_release.sh)
    darts-kiosk-v1.7.0-linux.tar.gz
    darts-kiosk-v1.7.0-source.zip
    
  → "Publish release"
```

---

### B. OPTIONAL / EMPFOHLEN

#### B1. Branch Protection fuer main (empfohlen)

```
Settings → Branches → Add branch protection rule

  Branch name pattern: main
  ✅ Require pull request reviews before merging
  ✅ Require status checks to pass before merging
  
  → "Create"
```

**WARUM:** Verhindert versehentliches direktes Pushen auf main.

#### B2. Release-Notifications (empfohlen)

```
Settings → Notifications → Releases

  Aktiviere Benachrichtigungen fuer neue Releases.
  Optional: Webhook an externen Service (Slack, Discord, etc.)
```

#### B3. Repository Topics/Description

```
Repository Hauptseite → Zahnrad-Icon neben "About"

  Description:    Darts Kiosk + Admin Control System
  Website:        (falls vorhanden)
  Topics:         darts, kiosk, autodarts, arcade
```

---

### C. NUR FUER PRIVATE REPOSITORIES

#### C1. GitHub Personal Access Token (PAT) erstellen

**Fine-Grained PAT (empfohlen — sicherer, granularer):**

```
GitHub.com → Settings (Profil) → Developer settings → Personal access tokens
  → Fine-grained tokens → "Generate new token"

  Token name:        darts-kiosk-update
  Expiration:        90 days (oder "No expiration" fuer Kiosk-Systeme)
  Repository access: "Only select repositories" → darts-kiosk
  
  Permissions:
    Contents:  ✅ Read-only     (Releases lesen, Assets herunterladen)
    Metadata:  ✅ Read-only     (automatisch gesetzt)
    
  ALLES ANDERE: No access
  
  → "Generate token"
  → Token SOFORT kopieren und sicher speichern!
```

**Classic PAT (Alternative — breiter, einfacher):**

```
GitHub.com → Settings → Developer settings → Personal access tokens
  → Tokens (classic) → "Generate new token"

  Note:        darts-kiosk-update
  Expiration:  90 days
  
  Scopes:
    ✅ repo        (Minimum fuer private Repos)
    
  ALLES ANDERE: nicht ankreuzen
  
  → "Generate token"
```

#### C2. Token auf dem Board-PC konfigurieren

```
Auf dem Windows Board-PC:

  Oeffne: backend\.env
  
  Setze:
    GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx
    
  WICHTIG: Token NIEMALS in Git committen!
```

#### C3. Token erneuern (wenn Ablaufdatum gesetzt)

Setze dir eine Erinnerung fuer das Ablaufdatum des Tokens.
Neuen Token erstellen → in backend/.env ersetzen → Dienste neustarten.

---

### D. NUR FUER ORGANISATIONEN

#### D1. Organisation-Level Workflow Permissions

```
Organization → Settings → Actions → General

  Actions permissions:
    ✅ "Allow all actions and reusable workflows"
    oder
    ✅ "Allow orri, and select non-orri, actions and reusable workflows"
       → "Allow actions created by GitHub" ✅
       → softprops/action-gh-release ✅
       → actions/checkout ✅
       → actions/setup-node ✅
```

#### D2. Organisation Secrets (falls Token org-weit)

```
Organization → Settings → Secrets and variables → Actions

  Neues Secret:
    Name:   DARTS_GITHUB_TOKEN
    Value:  ghp_xxxxxxxxxxxxxxxxxxxx
    
  Im Workflow referenzieren als:
    ${{ secrets.DARTS_GITHUB_TOKEN }}
```

---

## 3. TOKEN-EMPFEHLUNG

### Public Repository (empfohlen fuer dieses Projekt)

| Aspekt | Antwort |
|--------|---------|
| Token noetig? | **NEIN** — GitHub API ist fuer public Repos ohne Token erreichbar |
| Rate Limit ohne Token | 60 Requests/Stunde/IP |
| Rate Limit mit Token | 5.000 Requests/Stunde |
| Empfehlung | Token ist optional aber empfohlen fuer hoehere Rate-Limits |

**Fazit: Ein Public Repo funktioniert OHNE Token.** Wenn du 24h Intervall-Checks machst, brauchst du 1 Request pro Check = 24 Requests/Tag. Das ist weit unter dem Limit von 60/h.

### Private Repository

| Aspekt | Antwort |
|--------|---------|
| Token noetig? | **JA** — ohne Token kommt 404 "Repository not found" |
| Empfohlener Token-Typ | Fine-Grained PAT |
| Minimum-Berechtigungen | Contents: Read-only + Metadata: Read-only |
| Token-Geheimnis | NUR in backend/.env, NIEMALS in Git |

---

## 4. GITHUB ACTIONS — VERWENDETE ACTIONS

| Action | Version | Zweck | Quelle |
|--------|---------|-------|--------|
| `actions/checkout` | v4 | Repository auschecken | GitHub-offiziell |
| `actions/setup-node` | v4 | Node.js installieren | GitHub-offiziell |
| `softprops/action-gh-release` | v2 | Release erstellen + Assets hochladen | Community (900k+ Nutzer) |

**Keine Secrets erforderlich:** Der Workflow nutzt den automatischen `GITHUB_TOKEN` der von GitHub Actions bereitgestellt wird. Kein manuelles Secret noetig.

---

## 5. REPOSITORY SECRETS / VARIABLES — KEINE NOETIG

| Secret/Variable | Noetig? | Grund |
|-----------------|---------|-------|
| `GITHUB_TOKEN` (Actions-intern) | Automatisch | Von GitHub bereitgestellt, kein manuelles Setup noetig |
| Custom Secrets | Nein | Der Workflow braucht keine externen API-Keys |
| Repository Variables | Nein | Alles wird aus VERSION-Datei und Commit gelesen |

---

## 6. "GO LIVE" CHECKLISTE

### Voraussetzungen

- [ ] GitHub Repository erstellt (public oder private)
- [ ] `.github/workflows/build-release.yml` ist im Repository
- [ ] `VERSION` Datei ist im Repository (aktueller Wert: `1.6.5`)
- [ ] `.gitignore` ist im Repository (schuetzt .env, data/, logs/)
- [ ] `updater.py` ist im Repository
- [ ] `backend/.env.example` und `frontend/.env.example` sind im Repository

### GitHub-Einstellungen

- [ ] Actions → General → "Read and write permissions" aktiviert
- [ ] (Falls private) Fine-Grained PAT erstellt mit Contents: Read-only
- [ ] (Falls private) Token in backend/.env als GITHUB_TOKEN eingetragen

### Board-PC Konfiguration

- [ ] `GITHUB_REPO=orri/darts-kiosk` in backend/.env gesetzt
- [ ] (Falls private) `GITHUB_TOKEN=ghp_xxx` in backend/.env gesetzt
- [ ] Dienste neugestartet (stop.bat → start.bat)
- [ ] Admin Panel → System → Updates → "Auf Updates pruefen" funktioniert

### Erster Release-Test

- [ ] VERSION auf `1.7.0` gesetzt, committed, getagged: `git tag v1.7.0 && git push --tags`
- [ ] GitHub Actions Workflow laeuft erfolgreich (gruener Haken)
- [ ] Release wurde erstellt mit 3 Assets (Windows, Linux, Source)
- [ ] Board-PC → Admin Panel → System → Updates → "Auf Updates pruefen"
- [ ] Neue Version wird angezeigt
- [ ] "Update vorbereiten" → Download → "v1.7.0 installieren"
- [ ] Update erfolgreich oder automatischer Rollback bei Fehler
- [ ] Version im Admin Panel zeigt v1.7.0

### Rollback-Test

- [ ] Admin Panel → System → Backups → App-Backup vorhanden
- [ ] "Rollback" klicken → System stellt vorherige Version wieder her
- [ ] Health-Check nach Rollback erfolgreich

---

## 7. FEHLERBEHEBUNG

| Problem | Ursache | Loesung |
|---------|---------|---------|
| "Kein GitHub-Repository konfiguriert" | GITHUB_REPO nicht gesetzt | backend/.env: `GITHUB_REPO=owner/repo` |
| "Repository nicht gefunden" | Falscher Repo-Name oder private ohne Token | Repo-Name pruefen, ggf. GITHUB_TOKEN setzen |
| "Rate-Limit erreicht" | Zu viele API-Calls ohne Token | GITHUB_TOKEN in backend/.env setzen |
| "Download fehlgeschlagen" | Netzwerkproblem oder Asset nicht vorhanden | Internetverbindung pruefen, Asset-Name pruefen |
| "Paket ungueltig" | Zip-Struktur stimmt nicht | build_release.sh erneut ausfuehren, Zip manuell pruefen |
| Actions Workflow schlaegt fehl | Permissions | Settings → Actions → "Read and write permissions" |
| Update installiert, aber Version alt | VERSION Datei nicht im Paket | build_release.sh kopiert VERSION automatisch |
