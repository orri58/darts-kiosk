# Darts‑Kiosk – Vollständiger Implementierungs‑ und Roll‑out‑Plan

## 1. Ziel & Grundprinzipien

| Prinzip | Beschreibung |
|---|---|
| **Frozen‑Core** | Der lokale Kern (Board‑/Session‑Logik, Pricing, Autodarts‑Observer) bleibt unverändert und muss zu jeder Zeit funktionsfähig sein – selbst wenn sämtliche Zentral‑Dienste ausfallen. |
| **Trennung von Runtime‑Truth und Commercial‑Truth** | Der lokale Kern ist die *Source of Truth* für den Live‑Spielstatus. Die Zentrale ist die *Source of Truth* für Lizenzen, Entitlements und den dauerhaften Umsatz‑Ledger. |
| **Feature‑Flag‑Isolation** | Alle zentralen Adapter, Portale und Call‑Staff‑Funktionen sind per Laufzeit‑Flag `ENABLE_…` standardmäßig **off**. Änderungen dürfen nur über Feature‑Flags aktiviert werden. |
| **Security‑First** | Kein Feature geht live, bevor Auth‑/Authz‑Modell, Secrets‑Management, Device‑Identity und Remote‑Action‑Safety nachweislich implementiert sind. |
| **Echtzeit‑Synchronisation** | Umsatz‑kritische Events (Unlock, Top‑Up, Session‑Close, Lizenz‑Änderungen) werden **append‑only** sofort an die Zentrale gestreamt und dort dauerhaft gespeichert. Der lokale Kern hält nur eine Cache‑/Retry‑Queue. |
| **Keine Lizenz → Keine Monetarisierung** | Ohne gültige zentrale Lizenz/Lease darf das Gerät nur im **Provisioning/Support‑Modus** booten – keine Boards freischalten, keine Credits verbrauchen. |
| **Anti‑Cloning** | Geräte‑Identität ist an ein eindeutiges, server‑seitig ausgestelltes Zertifikat bzw. Schlüssel‑Paar gebunden. Ein bloßer Daten‑Ordner‑Klon funktioniert nicht. |
| **Minimaler Device‑Footprint** | Auf dem lokalen Gerät liegen nur produktive Runtime‑Artefakte, Konfiguration, Logs und Daten – keine unnötigen Dev‑Dateien, Tests, Doku‑Sammlungen oder Repo‑Historie. |

---

## 2. Rollen‑ & Berechtigungs‑Modell (Capability‑basiert)

| Rolle | Beschreibung | Kern‑Capabilities (Beispiele) |
|---|---|---|
| **Superadmin** | Plattform‑weite Kontrolle, Notfall‑Reset, globale Policies. | `admin.all`, `license.manage`, `remote.action.high`, `user.role.manage` |
| **Partner / Agent** | Verantwortlich für ein oder mehrere Aufsteller/Standorte. | `customer.create`, `device.provision`, `license.assign`, `report.view` |
| **Aufsteller** | Betreibt mehrere Filialen/Standorte. | `location.manage`, `device.overview`, `license.revoke`, `support.ticket.create` |
| **Manager (Filial‑Leiter)** | Operativer Betreiber einer oder mehrerer Filialen. | `board.unlock`, `session.topup`, `revenue.view`, `device.rebind` (mit Approval) |
| **Staff / Wirt** | Front‑Desk‑Operator, führt tägliche Auf‑/Ab‑Schlüsse aus. | `board.unlock`, `session.topup`, `session.end`, `support.bundle.export` |

**Hinweis:** Für Spezial‑Cases (z. B. Finanz‑Reporting, Auditing) können **Zusatz‑Capabilities** (`finance.report`, `audit.log.read`) zu bestehenden Rollen hinzugefügt werden – statt neue Rollen zu erzeugen.

---

## 3. Architektur – Bounded Contexts

```
+----------------------+   +---------------------------+   +-----------------------+
|  1. Local Runtime    |   |  2. Central Control Plane |   | 3. Device Trust Layer |
|   – Board/Session    |   |   – Identity & RBAC       |   |   – Enrollment        |
|   – Pricing/Observer |   |   – Customer/Location     |   |   – Zertifikate/Keys  |
|   – Local DB (SQLite)|   |   – Lizenz‑Entitlements   |   |   – Re‑bind/Replace   |
|   – WS‑Push/Poll     |   |   – Telemetrie/Support    |   |   – Revocation        |
|   – Admin‑UI (Kiosk) |   |   – Remote‑Action Engine  |   |   – Anti‑Cloning      |
+----------------------+   +---------------------------+   +-----------------------+
                 ^                     ^                         ^
                 |                     |                         |
   Runtime‑Truth ↔︎ Commercial‑Truth (Append‑Only Events)    Device‑Identity ↔︎ Central Auth
```

**Wichtige Verträge**
- **Event‑Schema** (unlock, top‑up, session‑close, licence‑change) – JSON, `event_id`, Signatur, `device_id`, `tenant_id`, Zeitstempel.
- **Snapshot‑API** – Zentrale kann den aktuellen lokalen State (Board‑Status, Session‑Summary) lesen, aber nicht schreiben.
- **Config‑Sync‑Contract** – Nur lesend, Änderungen werden über **Feature‑Flags** und **Approval‑Workflow** eingespielt.

### 3.1 Device Runtime Footprint (Zielbild)

Auf produktiven lokalen Geräten soll **nicht das gesamte Repo** liegen, sondern nur eine minimale, kontrollierte Runtime-Struktur:

```text
/app
  /backend_runtime        # verpackte Backend-Runtime
  /frontend_build         # statische gebaute Frontend-Artefakte
  /agent_runtime          # nur falls wirklich benötigt
  /bin                    # Start-/Service-Skripte
/data
  /db                     # SQLite / lokale Runtime-Daten
  /logs                   # rotierte Logs
  /backups                # lokale Kurzzeit-Backups
  /cache                  # Retry-/Outbox-/temporäre Runtime-Caches
  /support                # temporäre Support-Bundles
/config
  app.env                 # minimale lokale Konfiguration
  device.json             # device binding metadata (ohne rohe Secrets)
```

**Nicht auf dem Gerät:**
- `.git`
- Tests / Testreports / Fixtures
- Quell-Dokumentation für Entwicklung
- Build-Skripte, die nur im Dev-/CI-Kontext gebraucht werden
- alte Release-Artefakte ohne Rollback-Zweck
- unnötige Node-/Python-Dev-Dateien
- Repo-interne Analyse-/Migrationsnotizen

**Prinzipien für das Geräte-Dateisystem:**
- `app/` möglichst read-only bzw. update-kontrolliert
- `data/` ist der einzige regulär beschreibbare Runtime-Bereich
- `config/` nur minimale, produktive Gerätekonfiguration
- Secrets nicht frei verstreut in mehreren Dateien
- Logs, Downloads, Update-ZIPs und Support-Bundles mit Retention/Cleanup

---

## 4. Sicherheitsarchitektur (Kern‑Requirements)

1. **Secrets & Defaults**
   - Keine Default‑Secrets mehr (z. B. `central-jwt-secret-change-me`).
   - Start‑Fail bei fehlenden/unsicheren Secrets (Env‑Variable, Vault, Secret‑Manager).
   - Verwaltung von JWT/Session‑Secrets via **HS256** (kurze TTL) oder **RS256** (asymmetric) – Rotation verpflichtend.
2. **Passwort‑Hashing**
   - `argon2id` oder `bcrypt` mit Salt und angemessener Cost‑Factor.
3. **Device‑Authentisierung**
   - **mTLS** oder **Signed‑Device‑Certificates**. Gerät erzeugt bei Erster‑Registrierung ein Schlüsselpaar, sendet CSR, bekommt ein signiertes Zertifikat. 
   - API‑Key‑Modell wird nur als **hashed‑store** verwendet, Schlüssel werden nur einmalig angezeigt.
4. **Endpoint‑Absicherung**
   - Jeder device‑spezifische Endpunkt (`/api/remote‑actions/*`, `/api/config/effective`) prüft **Device‑Identity**.
   - Alle Admin‑Endpunkte prüfen **JWT‑RBAC**.
   - CORS: `allow_origins` strikt auf bekannte Domains, keine Wildcards mit `allow_credentials`.
5. **Remote‑Action‑Safety**
   - Klassifizierung nach Risiko (Low / Medium / High).
   - Hohe Aktionen (Unlock, Lizenz‑Sperre, Rebind) benötigen **Dual‑Control** (Approval‑Ticket + MFA).
   - Idempotente `action_id`, Ablauf (`expires_at`), Signatur.
   - Vollständiges Audit‑Log.
6. **Datenbank‑Back‑End**
   - Central‑DB **PostgreSQL** (oder MySQL) – keine SQLite‑Produktions‑DB.
   - ACID, Rollback, Backups, Rollen‑basierte DB‑Permissions.
7. **Rate‑Limit & Abuse‑Protection**
   - Pro IP/Device/Account‑Bucket, bricht bei Fehlversuchen ab, optional Captcha.
8. **Monitoring & Alerting**
   - Health‑Endpoint (`/api/system/readiness`).
   - Log‑Aggregation (ELK/Prometheus). 
   - Alert bei Lizenz‑Verletzung, Remote‑Action‑Missbrauch.

---

## 5. Daten‑ & Umsatz‑Synchronisation

| Ereignistyp | Richtung | Garantie | Speicherung |
|---|---|---|---|
| **Unlock / Top‑Up** | Local → Central | **Ack innerhalb 5 s** (Retry‑Queue sonst) | Append‑Only Ledger (PostgreSQL) |
| **Session‑Close (Revenue)** | Local → Central | **Ack** (sonst Retry) | Ledger + `Session.price_total` |
| **License‑Change** | Central → Local | Pull‑Mechanismus, Event‑Push (optional) | Lokaler Cache; bei Ausfall nur read‑only |
| **Telemetry / Health** | Local → Central (batch) | Best‑Effort | Zeitreihen‑DB |

**Offline‑Verhalten:**
- Lokaler Queue speichert Ereignisse persistent (SQLite‑Tabelle `outbox`). Beim nächsten Online‑Kontakt werden sie atomisch an die Zentrale übermittelt und anschließend gelöscht.
- Monetarisierte Aktionen **dürfen erst** ausgeführt werden, wenn das vorherige Event bereits per Ack bestätigt ist. Bei Netzwerk‑Ausfall stoppt der Operator das weitere Freischalten (Grace‑Period von 2 min, danach automatisch deaktiviert).

---

## 6. Rollen‑Matrix (Access‑Control‑List – exemplarisch)

```json
{
  "Superadmin": ["*"],
  "Partner": ["customer.*", "device.provision", "license.assign", "report.view"],
  "Aufsteller": ["location.manage", "device.overview", "license.revoke", "support.ticket.create"],
  "Manager": ["board.unlock", "session.topup", "session.end", "revenue.view", "device.rebind"],
  "Staff": ["board.unlock", "session.topup", "session.end", "support.bundle.export"]
}
```

**Zusatz‑Capabilities** (nach Bedarf aktivierbar):
- `finance.report`
- `audit.log.read`
- `remote.action.high`
- `device.key.rotate`

---

## 7. Phasen‑ und Sprint‑Plan (8 Wochen‑Sprint‑Zyklus)

### Phase 0 – Governance & Freeze (1 Woche)
- **Task 0.1** : `docs/IMPLEMENTATION_GOVERNANCE.md` finalisieren (Roadmap → Epic → Sprint → Ticket). ✅
- **Task 0.2** : Protected‑Core‑Modul‑Liste festlegen, Feature‑Flags setzen (`ENABLE_CENTRAL_ADAPTERS=false`). ✅
- **Task 0.3** : CI‑Gate einrichten (Backend‑Test‑Suite, Frontend‑Build, Release‑Build). ✅

### Sprint 1 – Security Baseline (2 Wochen)
| Ticket | Beschreibung | DoD |
|---|---|---|
| **S1‑01** | Secrets‑Management (Env‑Vars → Vault) – Fehlende Secrets aborten Startup. | App startet nur bei gültigen JWT‑Secret, Admin‑Token, Device‑Key. |
| **S1‑02** | Passwort‑Hashing zu Argon2id. | Alle Auth‑Flows prüfen Argon2id‑Hash. |
| **S1‑03** | Device‑Enrollment: CSR‑Flow, Zertifikats‑Ausstellung, DB‑Modell. | Gerät kann nur nach erfolgreichem Zertifikat registrieren; API‑Key wird gehasht gespeichert. |
| **S1‑04** | Remote‑Action‑Safety‑Engine (Risk‑Klassen, Idempotenz, Audit). | Hohe Aktionen benötigen Ticket‑ID + MFA; Audit‑Log prüfbar. |
| **S1‑05** | CORS‑Lock‑Down & Rate‑Limit‑Middleware. | Nur whitelist‑Domain; 100 req/min/User. |
| **S1‑06** | Migration von SQLite → PostgreSQL für Central DB (Docker‑Compose). | Central Server startet mit PostgreSQL, Datensicherung automatisiert. |
| **S1‑07** | Test‑Coverage ≥ 80 % für Security‑Code (Auth, Device, Remote). | CI schlägt bei < 80 % fehl. |
| **S1‑08** | Device-Footprint-Policy und Packaging-Manifest definieren. | Es gibt eine verbindliche Allowlist, welche Dateien/Ordner auf produktive Geräte dürfen. |

### Sprint 2 – Adapter‑Seam Extraction (2 Wochen)
| Ticket | Beschreibung | DoD |
|---|---|---|
| **S2‑01** | Interface‑Definition `CentralAdapter` (CRUD, Events, Config). | Lokaler Core importiert nur das Interface, keine implizite Logik. |
| **S2‑02** | Feature‑Flag‑Gate für Adapter‑Initialisierung. | App funktioniert ohne Adapter (Adapter‑Flag = off). |
| **S2‑03** | Unit‑Tests für Fehlertoleranz (Adapter‑Ausfall → kein Crash). | Lokaler Unlock/Start/Finish bleibt stabil bei Adapter‑Fehler. |
| **S2‑04** | Dokumentation `docs/CENTRAL_CONTRACT.md` (Event‑Schema, Snapshots). | Vollständige Spezifikation, verlinkt im Code. |
| **S2‑05** | Runtime-Packaging-Konzept für Geräte ableiten (Repo ≠ Device). | Es gibt ein separates Device-Artefakt, das nur Runtime-Dateien enthält. |

### Sprint 3 – Read‑Only Central Visibility (2 Wochen)
| Ticket | Beschreibung | DoD |
|---|---|---|
| **S3‑01** | Read‑Model‑Export: `/api/central/board_status`, `/api/central/session_summary`. | JSON‑Payload mit allen Boards, Sessions, Lizenz‑Status. |
| **S3‑02** | Heartbeat‑/Readiness‑Endpoint (`/api/system/readiness`). | Liefert vollständige Check‑Liste, muss grün sein. |
| **S3‑03** | Dashboard‑UI für zentrale Sicht (nur Viewer). | Admin‑UI zeigt aktuelle Boards, Devices, Lizenz‑Status. |
| **S3‑04** | Offline‑Grace‑Policy (2 min) bei fehlender Central‑Verbindung. | Lokaler Core stoppt monetisierte Aktionen nach Grace‑Period. |
| **S3‑05** | Device-Cleanup-/Retention-Mechanik für Logs, Downloads, Update-Artefakte und Support-Bundles. | Gerät hält definierte Speichergrenzen ein und sammelt keinen Müll an. |

### Sprint 4 – Licensing / Entitlement v1 (2 Wochen)
| Ticket | Beschreibung | DoD |
|---|---|---|
| **S4‑01** | Datenmodell `License`, `Entitlement`, `Lease` (Device‑bound). | DB‑Tabellen + API‑Endpoints (`/api/license/*`). |
| **S4‑02** | License‑Check Middleware (vor Unlock, Top‑Up). | Ohne gültige Lizenz → Fehlermeldung, kein Umsatz. |
| **S4‑03** | Anti‑Cloning‑Checks (Device‑Certificate‑Fingerprint). | Kopierter Install‑Ordner kann nicht ohne neues Zertifikat aktivieren. |
| **S4‑04** | Revocation‑Flow (License revokes → sofortiger Local‑Block). | Log‑Eintrag, Geräte‑Cache leert, Nutzer wird abgemeldet. |
| **S4‑05** | Test‑Suite für Lizenz‑Lifecycle (activate, suspend, renew, rebind). | 100 % Pass.

### Sprint 5 – Config‑Sync & Fleet Governance (2 Wochen)
| Ticket | Beschreibung | DoD |
|---|---|---|
| **S5‑01** | Ownership‑Map `docs/CONFIG_SYNC_OWNERSHIP.md` (lokal vs zentral). | Alle Settings kategorisiert. |
| **S5‑02** | Sync‑Engine (pull‑basierend, Konflikt‑Strategie „central wins, local fallback“). | Konfig‑Änderungen werden innerhalb von 30 s propagiert. |
| **S5‑03** | Staged‑Rollout‑Mechanismus (nach Board‑Label). | 10 % Boards erhalten neues Config‑Set, Monitoring. |
| **S5‑04** | Rollback‑Playbook für Config‑Fehler. | Dokumentiert, automatisierte Revert‑API. |

### Sprint 6 – Commercial Foundation (optional, v2) (2 Wochen)
| Ticket | Beschreibung | DoD |
|---|---|---|
| **S6‑01** | Revenue‑Ledger‑Schema (append‑only, immutable). | Ereignisse (unlock, top‑up, session‑close) werden unveränderlich gespeichert. |
| **S6‑02** | Export‑API für Finanz‑Reporting (CSV, JSON). | Berechtigte Rollen (`finance.report`). |
| **S6‑03** | Integration zu Payment‑Provider (Stripe‑Webhook‑Skeleton). | Test‑Webhook‑Flow, kein Live‑Charge. |
| **S6‑04** | UI‑Erweiterung → Revenue‑Dashboard (nur lesend). | Zeigt Umsatz pro Standort, Gerät, Zeitraum. |

---

## 8. Release‑Gates & Rollback‑Strategie
1. **Gate A** – Lokaler Core‑Suite (Backend‑Tests ≥ 90 %, Frontend‑Build, Release‑Build) grün.
2. **Gate B** – Security‑Baseline (keine Default‑Secrets, Argon2id, mTLS‑Handshake) erfolgreich.
3. **Gate C** – Adapter‑Seam‑Tests (Adapter‑Ausfall‑Simulation) bestanden.
4. **Gate D** – Read‑Only Visibility‑Demo (Dashboard‑UI, Heartbeat) live on Staging.
5. **Gate E** – Licensing‑Middleware‑Test (Unlock ohne Lizenz → Fehlermeldung).
6. **Gate F** – Feld‑Validierung: realer Windows‑Board‑PC + Autodarts‑Session, 3‑durchlaufende Szenarien (unlock, block‑pending, top‑up, finish). ✅

**Rollback**
- Jeder Central‑Feature‑Release hat einen **Feature‑Flag** und ein **Kill‑Switch** (`ENABLE_…=false`).
- Bei Fehlverhalten: Flag deaktivieren → sofortige De‑Aktivierung ohne Deploy‑Rollback.
- Datenbank‑Migrations‑Scripts sind **reversible** (`upgrade.sql` / `downgrade.sql`).
- vorheriger Release‑Tag bleibt als Docker‑Image (`darts‑kiosk:2026‑04‑13‑v4.4.3`) verfügbar.

---

## 9. Dokumentations‑ und Artefakt‑Übersicht
| Datei | Zweck |
|---|---|
| `docs/IMPLEMENTATION_GOVERNANCE.md` | Roadmap → Epic → Sprint → Ticket, Release‑Gates, Rollback. |
| `docs/CENTRAL_CONTRACT.md` | Event‑Schema, Snapshot‑API, Fehlermeldungen. |
| `docs/DEVICE_TRUST_MODEL.md` | Enrollment, Zertifikate, Re‑bind, Revocation. |
| `docs/ACCESS_CONTROL_MATRIX.md` | Rollen, Capabilities, Zusatz‑Permissions. |
| `docs/COMMERCIAL_LEDGER_FLOW.md` | Append‑Only Revenue‑Events, Ack‑Mechanik. |
| `docs/CONFIG_SYNC_OWNERSHIP.md` | Welche Settings gehören wo hin. |
| `docs/SECURITY_CHECKLIST.md` | Check‑Liste für jedes Release (Secrets, CORS, Rate‑Limit, DB‑Backup). |
| `docs/DEVICE_FOOTPRINT_POLICY.md` | Exakte Allowlist/Blocklist für produktive lokale Geräte, Verzeichnislayout, Retention und Cleanup-Regeln. |
| `docs/ROLLBACK_PLAYBOOK.md` | Schritt‑für‑Schritt‑Anleitung (Feature‑Flag, DB‑Downgrade, Container‑Rollback). |
| `docs/TESTING.md` | Test‑Pyramide (Unit → Integration → System → Feld). |
| `docs/README.md` | Projekt‑Übersicht, Getting‑Started (lokaler Core). |

---

## 10. Validierungs‑ und Test‑Strategie (Test‑Pyramide)
1. **Unit‑Tests** – Kern‑Services (`session_pricing`, `auth`, `device_trust`). Ziel ≥ 90 %.
2. **Integration‑Tests** – API‑Contracts (Unlock, Remote‑Action, License‑Check). 
3. **System‑Tests** – End‑to‑End‑Flow auf Staging (Docker‑Compose mit PostgreSQL, mTLS, Mock‑Payment).
4. **Field‑Tests** – Real‑Hardware (Windows‑Board‑PC) – 3‑Szenarien (normaler Flow, Netzwerk‑Ausfall, Lizenz‑Entzug).
5. **Security‑Tests** – Pen‑Test‑Suite (OWASP Top 10) + Fuzzing der Device‑Endpoints.
6. **Performance‑Tests** – Event‑Throughput ≥ 500 ev/s, Latency ≤ 100 ms für Revenue‑Ack.

---

## 11. Nächste unmittelbare Schritte (Kick‑off)
1. **Kick‑off‑Meeting** (30 min) – Rollen‑Zuweisung, Sprint‑Plan‑Abstimmung.
2. **Task‑Board** anlegen (GitHub‑Projects → Epic = „Central Rebuild“, Sprint = 1‑6). 
3. **Feature‑Flag‑Setup** in `backend/runtime_features.py` einpflegen (Standard off).
4. **Security‑Baseline** starten (Ticket S1‑01 … S1‑07) – dies ist Blocker für alle weiteren Phasen.
5. **CI‑Pipeline** anpassen (Security‑Checks, DB‑Migration, Docker‑Build). 
6. **Stakeholder‑Review** nach Sprint 1 (Review‑Meeting, Demo, Feedback). 
7. **Device-Footprint-Audit** des aktuellen lokalen Pakets (was liegt heute unnötig auf dem Gerät?).
8. **Packaging-Refactor vorbereiten**: separates Runtime-Artefakt statt Repo-Deploy auf Geräte.

---

# Fazit
Der Plan liefert **klare Trennung**, **sichere Lizenz‑Durchsetzung**, **echtzeit‑sichere Umsatz‑Replikation** und **eine schrittweise, test‑getriebene Umsetzung**. Mit den definierten Gates, der Rollen‑Matrix und den detaillierten Sprint‑Tickets können wir sofort starten, ohne die aktuelle stabile lokale Kern‑Version zu gefährden.

---

*Alle genannten Dokumente wurden bereits im Repository angelegt bzw. aktualisiert; sie finden Sie unter `docs/`.*