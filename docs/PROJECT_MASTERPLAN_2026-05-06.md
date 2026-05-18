# Darts Kiosk — Professioneller Masterplan 2026-05-06

## Ziel

Darts Kiosk soll von einem technisch gewachsenen, in Teilen bereits starken Produkt zu einem **klar verständlichen, professionell strukturieren, release-governed und marktfähigen System** werden.

Wichtigste Leitplanke:

> **Der lokale Kern bleibt geschützt und lokal autoritativ.**
> Central / Operator / Portal / Commercial werden professionell darauf aufgebaut — nicht umgekehrt.

---

# 1. Zielbild

## Produkt-Zielbild
Ein Produkt mit **einer klaren Identität** und **drei sauber getrennten Betriebsmodi**:

1. **Kiosk Mode**
   - venue-facing
   - touch-first
   - hoch lesbar
   - emotional klar und direkt

2. **Console Mode**
   - Admin + Operator
   - strukturierte operative Steuerung
   - Triage, Diagnose, Commercial, Review, Aktionen

3. **Read-only Mode**
   - Portal
   - read-only Sicht auf Betrieb, Lizenz- und Flottenlage
   - keine schwache Kopie von Operator, sondern ein eigener Modus derselben Designfamilie

---

# 2. Architektur-Zielbild

## 2.1 Bounded Contexts

### A. Local Runtime Core
Besitzt:
- Board-Status
- Session-Lifecycle
- Match-/Observer-Autorität
- Pricing-/Capacity-Anwendung
- lokale Kiosk-/Admin-Läufe
- lokale Persistenz

### B. Local Adapter / Sync Layer
Besitzt:
- Outbox / Retry
- Telemetrie-Sync
- Remote-Action-Inbox
- Config-Fetch / Merge
- Central-Bridge ohne Live-Autoritätswechsel

### C. Central Control Plane
Besitzt:
- Customers / Locations / Devices
- Users / Roles / Scopes
- Licenses / Commercial-Readiness
- Remote Actions / Review / Audit
- Fleet Visibility / Diagnostics

### D. Device Trust Layer
Besitzt:
- Enrollment
- Credential-/Lease-Issuance
- Rebind / Replace
- Revocation
- Trust-Status

### E. Shared Contracts
Besitzt:
- DTOs / Schemas
- API Contracts
- Settings Contracts
- Severity / Status / Outcome Taxonomy

---

## 2.2 Repo-Zielstruktur

```text
apps/
  local-runtime/
  central-control-plane/
  operator-frontend/
  portal-frontend/

packages/
  contracts/
  shared-ui/
  shared-utils/

docs/
  architecture/
  reference/
  operations/
  project/
  adr/
  history/

deploy/
  windows/
  docker/

scripts/

tests/
  unit/
  contract/
  integration/
  field/
```

Nicht zwingend sofort physisch in einem Sprint, aber das ist das **Zielbild**, auf das refaktoriert wird.

---

# 3. Design-System-Zielbild

## Prinzip
Nicht vier Designwelten, sondern **ein System mit Modus-Varianten**.

## Shared Product Components
Diese Bausteine sollen verbindlich werden:
- `AppShell`
- `PageHeader`
- `StatusStrip`
- `KpiRow`
- `TriagePanel`
- `EntityTable`
- `EntityCard`
- `DetailSection`
- `StatusBadge`
- `ActionBar`
- `FilterToolbar`
- `InlineNotice`
- `EmptyState`
- `ConfirmationSheet`

## Visuelle Leitlinie
**Operational premium, nicht Startup-Spielzeug.**

Eigenschaften:
- robust
- ruhig
- hoch lesbar
- unter Druck verständlich
- leicht industriell
- markant, aber nicht verspielt

---

# 4. Dokumentations-Zielbild

## Kanonische Top-Level-Dokumente
Am Ende sollen wenige klare Einstiegsdokumente reichen:

- `README.md`
- `DEVELOPING.md`
- `OPERATIONS.md`
- `RELEASING.md`
- `CONTRIBUTING.md`

## docs/ Struktur

```text
docs/
  architecture/
    overview.md
    local-core.md
    central-surfaces.md
    session-lifecycle.md
    autodarts-observer.md
  reference/
    env-vars.md
    api-surfaces.md
    settings-contracts.md
    test-matrix.md
  operations/
    installation.md
    runbook.md
    updates-and-rollback.md
    support-diagnostics.md
  project/
    status.md
    roadmap.md
    handoff.md
  adr/
    0001-local-first-core.md
    0002-central-as-optional-adapter.md
    0003-observer-authority-model.md
  history/
    waves/
    audits/
    legacy/
```

## Harte Doku-Regeln
- Nur **eine** Front Door
- Nur **eine** Architekturübersicht
- Historische Docs klar als historisch markiert oder verschoben
- Versions- und Produktstatus müssen mit `VERSION` übereinstimmen

---

# 5. Qualitäts- und Release-Modell

## Gate A — PR / Change Gate
Pflicht bei Änderungen:
- fokussierte Backend-Regressionssuite
- Frontend Production Build
- Frontend Unit-/Interaction-Tests
- Python Compile/Import Sanity
- Packaging Smoke / Artefaktstruktur

## Gate B — Release Candidate Gate
Pflicht vor Tag:
- Gate A grün
- Release Script auf clean workspace
- Changelog / VERSION / Release Notes konsistent
- Artefakt-Integrität geprüft
- Update-/Rollback-Sanity

## Gate C — Field Release Gate
Pflicht vor Feld-/Venue-Anspruch:
- echter Windows-Board-PC-Lauf
- Start/Stop/Smoke
- Observer-/Autodarts-Verhalten
- Unlock / Match Start / Match Finish / Top-Up
- Reboot-/Recovery-Test
- Update-/Rollback-Drill
- Soak / längerer Stabilitätslauf

---

# 6. Roadmap

## Phase 0 — Truth Reset
Ziel: Verwirrung und Drift stoppen.

### Tasks
- Root README auf aktuellen Produktzustand ziehen
- veraltete Setup-/Deploy-Guides als legacy markieren oder ersetzen
- Status-Matrix einführen:
  - supported baseline
  - optional/in progress
  - legacy/historical
- Repo-Artefakt-/Runtime-Müll sauber trennen oder dokumentiert quarantänen

### DoD
- neuer Entwickler versteht nach 15–30 Minuten:
  - was das Produkt heute ist
  - was Kern vs optional vs alt ist

---

## Phase 1 — Central Structural Refactor
Ziel: `central_server` aus dem Monolithen holen.

### Tasks
- `central_server/server.py` modular aufteilen in:
  - auth
  - users
  - devices
  - licenses
  - remote actions
  - trust
  - telemetry
- Service-Layer einführen
- DTO-/Schema-Disziplin erhöhen
- Startup-Migrationslogik in echte Migrationsstrategie überführen

### DoD
- zentrale API ist modular, testbarer, mit klaren Boundaries

---

## Phase 2 — Design System / Surface Unification
Ziel: Admin, Operator, Portal in ein System bringen.

### Tasks
- gemeinsames Shell-System definieren
- Login-Flächen vereinheitlichen
- Severity-/Badge-/Status-Semantik normieren
- Portal als read-only mode schärfen
- Settings architektonisch gruppieren statt nur weiterfüllen

### DoD
- Console Mode und Read-only Mode sehen aus wie derselbe Produktstamm

---

## Phase 3 — Commercial / Operator Workflow Finish
Ziel: marktfähige Flächen statt halbfertige Power-UIs.

### Tasks
- Renewal-/Capacity-Aktionspfade sauber definieren
- Token-/Activation-/License-Flows komplettieren
- Dashboard → Portfolio → Detail → Action lückenlos machen
- Remote-Action-Triage weiter professionalisieren

### DoD
- Operator kann aus Flächen wirklich handeln, nicht nur lesen

---

## Phase 4 — Quality / Release Professionalization
Ziel: kein „wird schon gutgehen“-Release mehr.

### Tasks
- echte PR-CI einführen
- package manager vereinheitlichen
- Packaging-Logik auf eine Quelle ziehen
- Testmatrix formal machen
- Warnings aus Gate-Suiten entfernen

### DoD
- jede Release-Aussage stützt sich auf klare Gates, nicht nur Erfahrung

---

## Phase 5 — Field Confidence / Supportability
Ziel: professionelle Betriebsreife.

### Tasks
- strukturierte Logs / Correlation IDs
- bessere Fleet-/Incident-Telemetrie
- echte Windows/Autodarts-Feldzertifizierung pro Release-Linie
- Support-/SOP-/Severity-Modell

### DoD
- Support und Operatoren können Probleme reproduzierbar lesen, triagieren und lösen

---

# 7. Was wir nicht tun

- keinen Full Rewrite des kompletten Produkts
- keinen Wechsel der lokalen Autorität auf Central
- keine endlosen Seitenpolishes ohne Designregeln
- kein weiteres unstrukturiertes Anwachsen von `central_server/server.py`
- keine weiteren historischen Identitäten gleichzeitig als „aktuell“ verkaufen

---

# 8. Sofortmaßnahmen mit höchstem ROI

Wenn nur die ersten 10 Hebel gezogen werden, dann diese:

1. README / Front-Door korrigieren
2. Legacy-Setup-Guide markieren oder ersetzen
3. Canonical status matrix anlegen
4. `central_server/server.py` in Module schneiden
5. echte CI für Backend subset + Frontend build + tests
6. Package-Manager / Release-Weg vereinheitlichen
7. AppShell / PageHeader / StatusBadge / TriagePanel standardisieren
8. Portal als read-only mode schärfen
9. Test-Matrix dokumentieren
10. Release-Governance in klaren Gates festschreiben

---

# 9. Entscheidung für das Team

## Was andere Entwickler künftig verstehen sollen
Ein neuer Entwickler muss schnell beantworten können:
- Was ist der **geschützte Kern**?
- Was ist **optional / central / in progress**?
- Welche Flächen sind **supportet**, welche experimentell?
- Welche Docs sind **kanonisch**, welche historisch?
- Welche Tests muss ich für meinen Change laufen lassen?
- Wie wird released?
- Was darf ich sicher refactoren und was nicht?

Wenn das nicht in 30 Minuten klar wird, ist das Projekt noch nicht professionell genug dokumentiert.

---

# 10. Schlussfolgerung

Das Projekt hat genug Substanz, um **nicht neu gebaut werden zu müssen**.

Aber es braucht jetzt diszipliniertes Produkt- und Architekturmanagement statt weiteres reines Feature-Aufsammeln.

**Leitsatz ab jetzt:**

> **Local Core bewahren. Central und Produktflächen professionell neu ordnen. Repo, Doku, Design und Release-Governance auf ein Niveau bringen, das andere Entwickler sofort verstehen und sicher weiterführen können.**
