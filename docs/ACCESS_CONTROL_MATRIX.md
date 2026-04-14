# Access Control Matrix

## Ziel

Ein schlankes, gut verständliches Rollenmodell mit klaren Scopes und Capabilities.

Bewusst **keine Rollenexplosion**.

Hauptrollen:
- Superadmin
- Partner
- Aufsteller
- Manager
- Staff

Spezialfälle werden bevorzugt über **Zusatz-Capabilities** statt neue Rollen abgebildet.

---

## 1. Scopes

Berechtigungen gelten immer innerhalb eines Scopes.

### Scope-Typen
- `platform`
- `partner`
- `customer`
- `location`
- `device`

### Regel
Eine Rolle ohne passenden Scope hat keine Berechtigung.

Beispiel:
- Ein Manager mit Scope `location:essen-01` darf nicht auf `location:dortmund-02` zugreifen.

---

## 2. Rollenbeschreibung

## Superadmin
Plattformweit alles.

## Partner
Betreut mehrere Aufsteller/Kundenbereiche oder Regionen.

## Aufsteller
Besitzt / betreibt mehrere Standorte / Geschäfte / Geräte.

## Manager
Operative Verantwortung für einen oder mehrere zugewiesene Standorte.

## Staff
Tagesgeschäft vor Ort.

---

## 3. Capability-Gruppen

### Tenant / Struktur
- `partner.view`
- `partner.manage`
- `customer.view`
- `customer.manage`
- `location.view`
- `location.manage`
- `device.view`
- `device.manage`

### Nutzer / Rollen
- `user.view`
- `user.create`
- `user.update`
- `user.disable`
- `role.assign`

### Runtime / Betrieb
- `board.view`
- `board.unlock`
- `board.lock`
- `session.view`
- `session.topup`
- `session.end`

### Support / Diagnostics
- `health.view`
- `diagnostics.view`
- `support.bundle.export`
- `support.case.create`

### Remote Actions
- `remote.action.low`
- `remote.action.medium`
- `remote.action.high`

### Licensing / Commercial
- `license.view`
- `license.assign`
- `license.suspend`
- `license.revoke`
- `device.rebind`
- `device.replace`
- `revenue.view`
- `report.export`

### Governance / Security
- `audit.view`
- `featureflag.manage`
- `secret.rotate`
- `policy.manage`

---

## 4. Basis-Matrix

| Capability | Superadmin | Partner | Aufsteller | Manager | Staff |
|---|---:|---:|---:|---:|---:|
| partner.view | ✅ | ✅ | ❌ | ❌ | ❌ |
| partner.manage | ✅ | ❌ | ❌ | ❌ | ❌ |
| customer.view | ✅ | ✅ | ✅ | ❌ | ❌ |
| customer.manage | ✅ | ✅ | ✅ | ❌ | ❌ |
| location.view | ✅ | ✅ | ✅ | ✅ | ❌ |
| location.manage | ✅ | ✅ | ✅ | limited | ❌ |
| device.view | ✅ | ✅ | ✅ | ✅ | limited |
| device.manage | ✅ | ✅ | ✅ | limited | ❌ |
| user.view | ✅ | ✅ | ✅ | ✅ | ❌ |
| user.create | ✅ | ✅ | ✅ | limited | ❌ |
| user.update | ✅ | ✅ | ✅ | limited | ❌ |
| user.disable | ✅ | ✅ | ✅ | limited | ❌ |
| role.assign | ✅ | limited | limited | limited | ❌ |
| board.view | ✅ | ✅ | ✅ | ✅ | ✅ |
| board.unlock | ✅ | ✅ | ✅ | ✅ | ✅ |
| board.lock | ✅ | ✅ | ✅ | ✅ | limited |
| session.view | ✅ | ✅ | ✅ | ✅ | ✅ |
| session.topup | ✅ | ✅ | ✅ | ✅ | ✅ |
| session.end | ✅ | ✅ | ✅ | ✅ | ✅ |
| health.view | ✅ | ✅ | ✅ | ✅ | limited |
| diagnostics.view | ✅ | ✅ | ✅ | ✅ | limited |
| support.bundle.export | ✅ | ✅ | ✅ | ✅ | ✅ |
| support.case.create | ✅ | ✅ | ✅ | ✅ | ✅ |
| remote.action.low | ✅ | ✅ | ✅ | limited | ❌ |
| remote.action.medium | ✅ | ✅ | limited | ❌ | ❌ |
| remote.action.high | ✅ | ❌ | ❌ | ❌ | ❌ |
| license.view | ✅ | ✅ | ✅ | limited | ❌ |
| license.assign | ✅ | ✅ | limited | ❌ | ❌ |
| license.suspend | ✅ | ✅ | limited | ❌ | ❌ |
| license.revoke | ✅ | ✅ | ❌ | ❌ | ❌ |
| device.rebind | ✅ | ✅ | limited | ❌ | ❌ |
| device.replace | ✅ | ✅ | limited | ❌ | ❌ |
| revenue.view | ✅ | ✅ | ✅ | ✅ | limited |
| report.export | ✅ | ✅ | ✅ | limited | ❌ |
| audit.view | ✅ | limited | limited | ❌ | ❌ |
| featureflag.manage | ✅ | ❌ | ❌ | ❌ | ❌ |
| secret.rotate | ✅ | ❌ | ❌ | ❌ | ❌ |
| policy.manage | ✅ | ❌ | ❌ | ❌ | ❌ |

`limited` bedeutet: nur im eigenen Scope und teils mit Zusatzbedingung.

---

## 5. Zusatzregeln pro Rolle

## Superadmin
- darf alle Scopes sehen und verwalten
- einzige Rolle mit globalem Policy-/Featureflag-/Secret-Zugriff
- einzige Rolle für High-Risk-Ausnahmen ohne zusätzlichen Scope-Begrenzer

## Partner
- sieht und verwaltet nur zugewiesene Partner-/Kundenbereiche
- darf keine globalen Plattformregeln ändern
- darf keine fremden Partnerbereiche sehen

## Aufsteller
- sieht und verwaltet seine Kunden-/Standort-/Gerätebereiche
- darf Manager/Staff im eigenen Scope verwalten
- darf keine globalen Sicherheitsregeln ändern

## Manager
- ein oder mehrere Standorte
- operativer Betrieb, Umsatzsicht im eigenen Bereich
- keine harte Lizenzhoheit
- kein High-Risk-Remote-Zugriff

## Staff
- Betrieb vor Ort
- Unlock / Top-up / Session-Ende / Support-Bundle
- keine Rollenverwaltung
- keine Lizenzverwaltung
- keine kritischen Remote-Aktionen

---

## 6. Zusatz-Capabilities statt Zusatzrollen

Optional zuweisbar, falls nötig:
- `finance.report`
- `audit.log.read`
- `device.key.rotate`
- `remote.action.medium`
- `remote.action.high` (sehr restriktiv)
- `license.override.approval`

### Regel
Zusatz-Capabilities sind Ausnahmeinstrumente, keine neue Standardhierarchie.

---

## 7. High-Risk-Aktionen

Als High Risk gelten mindestens:
- Lizenz revoken
- Device rebind/replace finalisieren
- kritische Remote-Action mit Betriebs-/Umsatzwirkung
- Policy-/Featureflag-Änderungen
- globale Secret-/Trust-Rotation

### Anforderungen
- Begründung / Reason Pflichtfeld
- Audit-Eintrag
- optional Approval-Referenz
- MFA / re-auth für sensible Aktionen

---

## 8. UI-Regel

Die UI darf nur Funktionen zeigen, die die Rolle + Scope + Capability tatsächlich ausführen darf.

Keine Scheinbuttons.
Keine grauen Zombie-Menüs ohne realen Zweck.

---

## 9. V1-Entscheidung

Für V1 reichen diese 5 Rollen.

Wenn später Spezialfälle entstehen, wird zuerst geprüft:
1. reicht ein Scope?
2. reicht eine Zusatz-Capability?
3. erst dann neue Rolle
