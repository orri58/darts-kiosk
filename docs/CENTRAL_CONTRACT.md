# Central Contract

## Zweck

Dieses Dokument definiert die verbindlichen Verträge zwischen:
- lokalem Runtime-Kern
- zentraler Control Plane
- Device-Trust-/Licensing-Schicht

Es ist die wichtigste Grenzziehung, damit Central den lokalen Kern nicht destabilisiert.

---

## 1. Nicht verhandelbare Grundsätze

1. **Local Runtime bleibt autoritativ für Live-Board-/Session-State**
   - `locked`, `unlocked`, `in_game`, `blocked_pending`, `offline`
   - observer-authoritative start/finish
   - lokale Pricing-/Capacity-Anwendung

2. **Central bleibt autoritativ für Trust und Commercial Control**
   - Lizenzgültigkeit
   - Device-Bindung
   - Rollen / Scopes / Berechtigungen
   - Commercial Ledger
   - Remote-Action-Orchestrierung

3. **Central darf lokale Runtime nicht implizit überschreiben**
   - kein stilles Überfahren von Session-/Match-State
   - keine versteckte Abhängigkeit im lokalen Unlock/Start/Finish-Pfad

4. **Alle zentralen Integrationen sind feature-flagged**
   - Default: local-safe

---

## 2. Bounded Contexts und Ownership

## 2.1 Local Runtime Core owns
- Board state
- Session lifecycle
- local pricing/capacity logic
- observer integration
- local UI state
- local persistence
- retry/outbox queue for central delivery

## 2.2 Central Control Plane owns
- customer / location / device inventory
- users / roles / scopes / capabilities
- license / entitlement / lease status
- remote-action definitions and approvals
- durable commercial ledger
- fleet visibility / diagnostics aggregation

## 2.3 Device Trust Layer owns
- enrollment tokens
- device key / certificate binding
- trust status
- revocation and re-enrollment

---

## 3. Source-of-truth-Regeln

### Runtime Truth
Quelle: lokal

Beispiele:
- Board wurde entsperrt
- Match ist gestartet
- Match ist beendet
- Credits wurden lokal angewandt
- Board ist blockiert wegen fehlender Credits

### Commercial Truth
Quelle: central

Beispiele:
- Gerät darf monetisiert betrieben werden
- Lizenz ist aktiv / suspendiert / revoked
- Umsatzereignis wurde dauerhaft verbucht
- Device-Rebind ist genehmigt / abgelehnt

### Konsequenz
Ein lokales Gerät darf nur monetisieren, wenn:
- gültige Device-Identity vorliegt
- gültiger zentraler Lease/Lizenzstatus vorliegt
- Revenue-kritische Flows die zentrale Ack-/Lease-Regel einhalten

---

## 4. Runtime Feature Flags

Minimum-Flags:
- `ENABLE_CENTRAL_ADAPTERS=false`
- `ENABLE_CENTRAL_READ_MODEL=false`
- `ENABLE_REMOTE_ACTIONS=false`
- `ENABLE_LICENSE_ENFORCEMENT=false` (nur bis v1 fertig ist)
- `ENABLE_CONFIG_SYNC=false`
- `ENABLE_COMMERCIAL_LEDGER=false`

### Regel
Ein Flag darf nur standardmäßig auf `true`, wenn:
- Tests grün
- Doku aktuell
- Rollback klar
- Feldvalidierung erfolgt

---

## 5. Vertragsflächen

## 5.1 Local → Central: Event Ingest

Pfadidee:
- `POST /api/devices/{device_id}/events`

Typen:
- `board_unlocked`
- `session_topped_up`
- `match_started`
- `match_finished`
- `session_closed`
- `license_block_encountered`
- `device_health_snapshot`
- `support_bundle_created`

### Pflichtfelder
- `event_id` (UUID/ULID)
- `event_type`
- `event_version`
- `device_id`
- `tenant_id`
- `location_id`
- `occurred_at`
- `sent_at`
- `sequence_no`
- `payload`
- `signature` oder äquivalenter Integritätsschutz

### Antwort
- `ack_id`
- `accepted_at`
- `status=accepted|duplicate|rejected`
- optional `server_actions`

### Regeln
- idempotent via `event_id`
- duplicates sind erlaubt und müssen sauber erkannt werden
- local darf retryen, ohne doppelt zu buchen

---

## 5.2 Local → Central: Heartbeat / Readiness

Pfadidee:
- `POST /api/devices/{device_id}/heartbeat`

Enthält:
- current health summary
- app version
- lease status seen locally
- last successful ledger ack timestamp
- runtime warnings
- storage pressure indicators

### Semantik
- best-effort, aber regelmäßig
- kein harter Runtime-Blocker für Board-Lifecycle
- dient Fleet Visibility, nicht Billing-Truth

---

## 5.3 Central → Local: Lease / License Validation

Pfadidee:
- `GET /api/devices/{device_id}/lease`

Antwort enthält:
- `license_status`
- `lease_id`
- `lease_expires_at`
- `grace_policy`
- `capability_overrides`
- `revoked_at` optional

### Semantik
- signed response oder über vertrauenswürdigen mTLS-Kanal
- lokale Runtime cached den Lease befristet
- nach Lease-Ablauf kein neuer monetisierter Flow

---

## 5.4 Central → Local: Remote Actions

Pfadidee:
- `GET /api/devices/{device_id}/remote-actions/pending`
- `POST /api/devices/{device_id}/remote-actions/{action_id}/ack`

### Regeln
- nur für authentisierte Devices
- action envelope enthält:
  - `action_id`
  - `action_type`
  - `issued_at`
  - `expires_at`
  - `risk_level`
  - `params`
  - `approval_ref` falls nötig
  - `signature`
- Device lehnt stale/ungültige/falsch gescopte Actions ab
- Ack enthält `result_code`, `finished_at`, `details`

### V1 erlaubt
- reversible Wartungsaktionen
- Health Snapshot anfordern
- Config Refresh anfordern
- App/Agent-Neustart nur streng kontrolliert

### V1 nicht erlaubt
- zentrale Autorität über lokalen Match-Lifecycle
- stilles Überschreiben von Session-State
- ungesicherte Unlock-/Revenue-Manipulation

---

## 5.5 Central Read Model

Pfadidee:
- `GET /api/central/read-model/boards`
- `GET /api/central/read-model/sessions`
- `GET /api/central/read-model/devices`

Zweck:
- Operator-/Fleet-Sicht
- Read-only
- basiert auf bestätigten Events/Snapshots

---

## 6. Fehlersemantik

## Local darf weiterlaufen bei:
- Heartbeat-Fehlern
- Telemetry-Ingest-Fehlern
- Central Dashboard nicht erreichbar
- Config Fetch Timeout

## Local darf NICHT monetisiert weiterlaufen bei:
- fehlender gültiger Device Identity
- fehlendem gültigen Lease nach Grace-Policy
- Ablehnung zentraler Lizenzprüfung in einem monetisierungspflichtigen Pfad

## Grace-Policy
- kurze bounded grace period
- keine endlose Offline-Freischaltung
- nach Ablauf: Provisioning/Support-only mode

---

## 7. Versionierung

Jeder Contract ist versioniert:
- `event_version`
- `read_model_version`
- `remote_action_version`
- `lease_version`

Breaking changes brauchen:
- neue Version
- Migrationspfad
- dokumentierten Fallback

---

## 8. Nicht-Ziele

Dieses Contract-Dokument definiert nicht:
- konkrete UI-Gestaltung
- Payment-Provider-Integration
- vollständige Finanzbuchhaltung
- interne Datenbanktabellen im letzten Detail

Es definiert die **Schnittstellen- und Ownership-Grenzen**, damit die technische Umsetzung sauber bleibt.
