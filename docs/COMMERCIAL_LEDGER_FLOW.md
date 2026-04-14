# Commercial Ledger Flow

## Ziel

Alle umsatz- und lizenzrelevanten Ereignisse werden zentral als **append-only Ledger** gespeichert.

Der lokale Kern ist weiterhin Runtime-Truth für den Live-Ablauf, aber **nicht die einzige dauerhafte Quelle** für Commercial-Truth.

---

## 1. Grundprinzipien

1. **Append-only**
   - Keine stillen In-Place-Überschreibungen als Truth-Modell.
   - Korrekturen passieren über Folgeereignisse, nicht durch unsichtbares Umschreiben von Historie.

2. **Idempotent**
   - Wiederholte Zustellung desselben Events darf keine Doppelbuchung erzeugen.

3. **Ack-basiert**
   - Ein Event ist erst zentral dauerhaft gesichert, wenn die Zentrale es akzeptiert und bestätigt hat.

4. **Realtime-first**
   - Revenue-kritische Events werden sofort gesendet, nicht erst gesammelt am Tagesende.

5. **Local outbox, central ledger**
   - Lokal: Retry-/Outbox-Mechanik
   - Zentral: dauerhafte Ledger-Truth

---

## 2. Ledger-relevante Eventtypen

### Monetisierungsereignisse
- `board_unlocked`
- `session_topped_up`
- `session_closed`
- `refund_issued`
- `manual_credit_adjustment`

### Lizenz-/Trust-Ereignisse
- `license_activated`
- `license_suspended`
- `license_revoked`
- `device_rebound`
- `device_replaced`
- `lease_issued`
- `lease_expired`

### Operative Ereignisse mit kommerzieller Relevanz
- `license_block_encountered`
- `monetization_denied_no_lease`
- `high_risk_remote_action_executed`

---

## 3. Event-Struktur

Pflichtfelder:
- `event_id`
- `event_type`
- `event_version`
- `device_id`
- `tenant_id`
- `location_id`
- `session_id` optional
- `occurred_at`
- `sent_at`
- `sequence_no`
- `currency` falls finanziell relevant
- `amount` falls finanziell relevant
- `payload`
- `integrity_proof`

### Beispiel

```json
{
  "event_id": "01JXYZ...",
  "event_type": "session_topped_up",
  "event_version": 1,
  "device_id": "dev_123",
  "tenant_id": "cust_456",
  "location_id": "loc_789",
  "session_id": "sess_abc",
  "occurred_at": "2026-04-13T09:30:00Z",
  "sent_at": "2026-04-13T09:30:02Z",
  "sequence_no": 42,
  "currency": "EUR",
  "amount": 10.00,
  "payload": {
    "credits_added": 4,
    "operator_user_id": "usr_mgr_1"
  },
  "integrity_proof": "..."
}
```

---

## 4. Lokale Outbox

Der lokale Kern hält eine persistente Outbox-Tabelle.

Minimum-Felder:
- `event_id`
- `sequence_no`
- `payload_json`
- `status` (`pending|sent|acked|dead_letter`)
- `attempt_count`
- `last_attempt_at`
- `acked_at`

### Regeln
- Events werden lokal zuerst persistent in die Outbox geschrieben
- dann sofort an central gesendet
- bei Erfolg → `acked`
- bei Fehler → Retry mit Backoff
- keine Löschung vor Ack

---

## 5. Ack-Semantik

Central antwortet mit:
- `status=accepted|duplicate|rejected`
- `ack_id`
- `accepted_at`
- optional `reason`

### Bedeutung
- `accepted` → Event dauerhaft im zentralen Ledger verbucht
- `duplicate` → Event war schon da; lokal ebenfalls als abgeschlossen behandeln
- `rejected` → Event fachlich/technisch abgelehnt; lokale Runtime muss definierte Reaktion auslösen

---

## 6. Flows

## 6.1 Unlock Flow
1. lokaler Unlock wird ausgelöst
2. lokales Event `board_unlocked` wird in Outbox geschrieben
3. Event wird sofort gesendet
4. Ack kommt zurück
5. zentraler Ledger kennt den Unlock

### Policy
Für V1 kann Unlock noch innerhalb eines gültigen Leases lokal starten, aber muss sofort zentral gespiegelt werden.

## 6.2 Top-up Flow
1. Staff/Manager führt Top-up aus
2. lokales Event `session_topped_up`
3. sofortiger Send + Ack
4. erst bestätigtes Event zählt als durable commercial truth

## 6.3 Session Close Flow
1. Session endet lokal autoritativ
2. lokales `session_closed`-Event wird geschrieben
3. Revenue-Summary-Daten werden mitgegeben
4. central acked und persistiert das Ergebnis

### Ziel
Wenn der PC danach stirbt, bleibt der bestätigte Umsatz zentral erhalten.

---

## 7. Offline- und Fehlerpolitik

## Grundsatz
Absolute Nullverlustrhetorik ist unehrlich.

Korrekt ist:
- was zentral bestätigt wurde, ist dauerhaft gesichert
- was lokal noch nicht bestätigt wurde und der PC verliert Strom/Platte/etc., kann verloren gehen

### Deshalb gilt
- monetisierte Nutzung nur mit gültigem Lease
- Revenue-kritische Flows sofort senden
- kurze bounded grace period
- keine endlosen Offline-Operationen

### Grace-Policy
Wenn central ausfällt:
- bestehende Session darf sauber enden
- neue monetisierte Aktionen nur begrenzt / nach Policy
- nach Grace-Ablauf keine neuen Unlocks/Top-ups

---

## 8. Reconciliation

Central kann periodisch prüfen:
- fehlen Sequenzen?
- gibt es Lücken im Eventstrom?
- weichen Session-Summaries von erwarteten Ledger-Summen ab?

### Reconciliation-Arten
- event gap detection
- duplicate detection
- session close vs top-up sum checks
- device last ack age monitoring

---

## 9. Read Models

Aus dem Ledger werden Read Models gebaut für:
- Umsatz nach Standort
- Umsatz nach Gerät
- Tages-/Wochen-/Monatsübersichten
- Lizenz-/Lease-Historie
- Rebind/Replace-Historie

Wichtig:
Read Models sind ableitbar.
Das Ledger ist die dauerhafte Commercial-Truth.

---

## 10. Korrekturen / Storno

Fehler werden nicht durch heimliches Ändern alter Zeilen gelöst.

Stattdessen:
- `refund_issued`
- `manual_credit_adjustment`
- `session_corrected` falls nötig

So bleibt die Historie nachvollziehbar.

---

## 11. V1-Entscheidungen

V1 muss liefern:
- append-only ledger
- lokale Outbox
- Ack-Semantik
- Unlock/Top-up/Session-Close als zentrale Commercial-Events
- grundlegende Reconciliation

V1 muss noch nicht liefern:
- vollständige Buchhaltung
- Steuer-/Rechnungslogik
- externe Payment-Settlement-Engine

Aber:
V1 muss eine belastbare Commercial-Durability haben.
