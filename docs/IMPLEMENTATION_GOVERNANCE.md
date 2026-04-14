# Implementation Governance

## Zweck

Dieses Dokument ist die operative Steuerung für den Central-Rebuild.

Es definiert:
- Leitplanken
- Zuständigkeiten
- Delivery-Phasen
- Epic- und Sprint-Struktur
- Definition of Done
- Release-Gates
- Rollback-Regeln

Der Grundsatz lautet:

> **Local runtime first. Central as controlled overlay. No regressions on the protected core.**

---

## 1. Leitprinzipien

1. **Frozen Local Core**
   - Der lokale Runtime-Kern ist geschützt.
   - Änderungen an Kernmodulen sind nur mit explizitem Ticket, Regression-Tests und Dokumentationsupdate zulässig.

2. **Central ist kein freier Nebenkriegsschauplatz**
   - Central-Features werden nur entlang des Plans gebaut.
   - Keine spontanen Zusatzfeatures ohne Einordnung in Roadmap/Epic/Sprint.

3. **Security vor Komfort**
   - Kein Internet-/Fleet-/Licensing-Feature ohne belastbares Auth-/Trust-/Audit-Modell.

4. **Repo ≠ Device**
   - Produktionsgeräte erhalten Runtime-Pakete, keine unkontrollierten Repo-Deployments.

5. **Docs + Tests + Code zusammen**
   - Jede relevante Architekturänderung muss im selben Arbeitsblock dokumentiert und validiert werden.

6. **Real hardware truth**
   - Windows-/Autodarts-Feldvalidierung ist Pflicht, kein optionales Nice-to-have.

7. **Model-swap continuity by file, not by memory**
   - Jede substanzielle Welle muss in dauerhaften Repo-Artefakten so festgehalten werden, dass ein anderes Modell/eine spätere Session nahtlos übernehmen kann.
   - `EXECUTION_BOARD.md` und `docs/MODEL_CONTINUITY_PROTOCOL.md` sind dafür verpflichtende Handoff-Anker.

---

## 2. Protected Local Core

Diese Bereiche gelten als geschützt:

- `backend/server.py`
- `backend/models/__init__.py`
- `backend/database.py`
- `backend/dependencies.py`
- `backend/runtime_features.py`
- `backend/routers/boards.py`
- `backend/routers/kiosk.py`
- `backend/routers/settings.py`
- `backend/routers/admin.py`
- `backend/services/session_pricing.py`
- `backend/services/autodarts_observer.py`
- `backend/services/ws_manager.py`
- `backend/services/scheduler.py`
- `frontend/src/pages/kiosk/*`
- `frontend/src/pages/admin/*`
- `frontend/src/context/*`

### Regeln für Kernänderungen

Eine Änderung an Protected-Core-Modulen braucht:
- ein explizites Ticket mit Kernbezug
- dokumentierte Begründung
- fokussierte Regression-Tests
- Nachweis, dass `adapters off` kein Verhalten verändert

---

## 3. Delivery-Struktur

## Roadmap

### Phase 0 — Freeze & Define
- Governance etablieren
- Verträge dokumentieren
- Feature-Flags fixieren
- Release-Gates definieren

### Phase 1 — Security Baseline
- Secrets/Defaults härten
- Device-Trust-Modell festziehen
- Auth/Authz-Modell finalisieren
- Remote-Action-Safety definieren

### Phase 2 — Adapter Seams
- Central von Local entkoppeln
- saubere Interfaces
- Failure-Isolation

### Phase 3 — Read-Only Central Visibility
- Health
- Status
- Session-/Board-Sicht
- Diagnostics

### Phase 4 — Safe Remote Actions
- nur reversible Wartungsaktionen zuerst
- auditierbar, scoped, idempotent

### Phase 5 — Licensing / Entitlements
- zentrale Aktivierung
- Device-Bindung
- Suspend / Renew / Rebind
- bounded offline lease

### Phase 6 — Config Sync / Fleet Governance
- ownership map
- staged rollout
- rollback-fähige sync rules

### Phase 7 — Commercial Foundation
- append-only ledger
- Reporting-Read-Models
- spätere Billing-Anbindung sauber vorbereiten

### Phase 8 — Field Validation & Rollout
- Windows-Board-PC
- Autodarts live
- outage drills
- rollback drills

---

## 4. Epic-Struktur

### Epic A — Governance & Contracts
Artefakte:
- `IMPLEMENTATION_GOVERNANCE.md`
- `CENTRAL_CONTRACT.md`
- `ACCESS_CONTROL_MATRIX.md`
- `DEVICE_TRUST_MODEL.md`
- `COMMERCIAL_LEDGER_FLOW.md`
- `CONFIG_SYNC_OWNERSHIP.md`
- `DEVICE_FOOTPRINT_POLICY.md`

### Epic B — Security Foundation
- secrets
- password hashing
- authn/authz
- rate limits
- audit
- production exposure baseline

### Epic C — Device Trust & Enrollment
- enrollment token
- device keypair/cert
- rebind/replace/revoke
- lease issuance

### Epic D — Central Read Model
- board/session/status export
- heartbeat/readiness
- support visibility

### Epic E — Remote Action Control Plane
- action model
- approval rules
- high-risk restrictions
- ack/result model

### Epic F — Licensing / Entitlement Engine
- license lifecycle
- device binding
- monetization gating

### Epic G — Config Sync & Fleet Ops
- setting ownership
- rollout waves
- rollback policy

### Epic H — Field Proof & Release Readiness
- packaging
- retention/cleanup
- real-machine validation

---

## 5. Sprint-Modell

Jeder Sprint enthält:
- Scope
- Tickets
- Dependencies
- Definition of Done
- Validation commands
- Release/rollback note

### Standard-DoD

Ein Ticket gilt nur als fertig, wenn:
- Code oder Doc-Artefakt erstellt/angepasst wurde
- betroffene Tests ergänzt/aktualisiert wurden
- relevante Doku angepasst ist
- Rollback-/Fehlerverhalten beschrieben ist
- keine lokale Kernregression entsteht

---

## 6. Branch- und Merge-Regeln

### Branching
- `main` → nur shippable, freigegebener Zustand
- `dev` → Integrationszweig
- `feature/central-*` → klar abgegrenzte Arbeitsstränge
- `release/x.y.z` → Stabilisierung ohne Scope-Creep

### Merge-Regeln
Kein Merge ohne:
- Review gegen Governance
- passende Tests
- Doku-Update
- klare Rollback-Notiz

Keine Misch-PRs mit:
- Kernrefactor + neues Zentralfeature + UI-Umbau gleichzeitig

---

## 7. Release-Gates

Ein Release- oder Meilenstein-Stand ist nur freigabefähig, wenn:

1. fokussierte Local-Core-Tests grün sind
2. Frontend-Build grün ist
3. Release-Build grün ist
4. `adapters off` denselben lokalen Baseline-Flow liefert
5. zentrale Ausfälle den lokalen Betrieb nicht blockieren
6. Device-Footprint-Policy eingehalten wird
7. mindestens ein realer Windows-/Autodarts-Validierungslauf erfolgreich war

---

## 8. Rollback-Regeln

Reihenfolge bei Problemen:
1. Central-Feature-Flag deaktivieren
2. Remote Actions deaktivieren
3. Config Sync deaktivieren
4. vorheriges Runtime-Paket / vorherigen Release wiederherstellen

Jede Phase braucht:
- dokumentierten Kill Switch
- dokumentierten Downgrade-Pfad
- Support-Bundle vor/nach Rollback erfassbar

---

## 9. Validierungsroutine pro Sprint

Minimum:
- fokussierte Backend-Suite
- Frontend-Produktionsbuild
- Release-Build
- dokumentierter Smoke-Test

Bei sicherheitsrelevanten Änderungen zusätzlich:
- negative Tests (unauthorized / expired / replay / wrong scope)
- device/auth edge cases
- audit-log assertions

---

## 10. Kontinuitäts- und Handoff-Regel

Jeder relevante Arbeitsblock muss so abgeschlossen werden, dass ein Modellwechsel keine strategische Amnesie erzeugt.

Pflicht dabei:
- `EXECUTION_BOARD.md` auf aktuellen Stand halten
- neue dauerhafte Leitentscheidungen in passende Docs übernehmen
- chat-only Kontext vermeiden
- den nächsten sinnvollen Block klar benennen

Ein übernehmendes Modell liest mindestens:
- `EXECUTION_BOARD.md`
- `docs/MODEL_CONTINUITY_PROTOCOL.md`
- `docs/IMPLEMENTATION_GOVERNANCE.md`
- `docs/IMPLEMENTATION_PLAN.md`
- die jeweils relevanten Fachdocs

## 11. Aktueller Sprint-1-Auftrag

Sprint 1 liefert die Spezifikationsbasis:
- Governance
- Central Contract
- Device Trust Model
- Access Control Matrix
- Commercial Ledger Flow
- Device Footprint Policy

Diese Artefakte definieren das Zielsystem so genau, dass die anschließende technische Umsetzung nicht wieder im Nebel baut.
