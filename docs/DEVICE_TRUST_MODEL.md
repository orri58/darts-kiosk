# Device Trust Model

## Ziel

Ein produktives Gerät darf nur dann monetisiert betrieben werden, wenn es:
- als eindeutiges Gerät registriert ist
- kryptografisch an seine zentrale Identität gebunden ist
- einen gültigen Lease / eine gültige Lizenz besitzt
- nicht durch simples Dateikopieren dupliziert werden kann

---

## 1. Bedrohungsmodell

Wir schützen gegen:
- Kopieren des App-Ordners auf einen zweiten PC
- Kopieren von DB/Config/Secrets
- gestohlene API-Keys
- unkontrollierte Rebinds
- manuelle Manipulation von Lizenzdateien
- gefälschte Devices, die sich als echtes Gerät ausgeben

Nicht realistisch garantiert werden kann:
- absolute physische Manipulationsresistenz auf normaler Standardhardware

Deshalb bauen wir auf:
- kryptografische Device-Identity
- serverseitige Bindung
- revocable trust
- begrenzte offline lease windows

---

## 2. Zentrale Entitäten

### Enrollment Token
Einmal-Token für Erstregistrierung oder kontrollierten Rebind.

Eigenschaften:
- kurzlebig
- scoped auf Tenant / Location / Device-Slot
- revocable
- auditiert
- optional an ausführenden Nutzer/Partner gebunden

### Device Record
Zentrale Repräsentation eines Geräts.

Felder (Beispiel):
- `device_id`
- `tenant_id`
- `location_id`
- `status`
- `trust_status`
- `public_key` / `certificate_thumbprint`
- `created_at`
- `last_seen_at`
- `revoked_at`
- `replacement_of_device_id` optional

**Aktueller Skeleton-Stand (Central Rebuild groundwork):**
- additive Device-Felder für `trust_status`, `credential_status`, `credential_fingerprint`
- additive Lease-Metadaten am Device (`lease_status`, `lease_id`, `lease_expires_at`, `lease_grace_until`)
- separate Placeholder-Tabellen für `device_credentials` und `device_leases`
- zentral erzeugtes `signed_bundle`-Leaseformat (`schema=darts.device_lease.v1`) als vorbereitende Vertragsform für spätere echte Signatur-/Verifikationspfade
- normalisierte CSR-/Public-Key-Aufnahme inkl. abgeleitetem `fingerprint` und stabilem `key_id`
- explizite zentrale Placeholder-Endpoints für Credential-Issuance und Revocation, damit Lifecycle-/Audit-Pfade schon jetzt testbar sind
- Lease-Metadaten referenzieren das aktive Credential über `credential_key_id` und `credential_id`, damit spätere Runtime-Validatoren eine saubere Bindung prüfen können
- Placeholder-Signing hat jetzt ein zentrales Issuer-/Signing-Profil (`issuer`, `key_id`, `algorithm`, `schema`) statt verstreuter Hardcodes; das schafft eine saubere Basis für spätere echte Key-Rotation / PKI-Anbindung
- zentrale Readback-/Serializer-Pfade liefern jetzt additive `verification`-Blöcke für Placeholder-Credentials und Lease-Bundles
- diese Verifikation prüft bereits HMAC-Bundle-Konsistenz, Schema, Timingstatus, Issuer-/Signing-Key-Konsistenz sowie `key_id`↔`fingerprint`-Kohärenz
- zusätzlicher zentraler Reconciliation-Helper bündelt Credential-/Lease-/Device-Readback in maschinenlesbare Findings für spätere Audit-/Repair-Flows
- adminseitige Readbacks liefern jetzt zusätzlich `reconciliation` + `reconciliation_summary` (Severity-/Source-Zählung, Timingstatus, Bundle-Quelle)
- gespeicherte Lease-Bundles werden gegen die aktuelle zentrale Rekonstruktion auf Drift geprüft, ohne daraus bereits lokale Enforcement-Entscheidungen abzuleiten
- additive zentrale Signing-Key-Registry (`CENTRAL_DEVICE_TRUST_SIGNING_REGISTRY`) kann jetzt aktive / retired / revoked Issuer-Keys beschreiben; Credential-/Lease-Readbacks markieren bekannte vs. unbekannte Issuer-Keys und heben retired/revoked-Metadaten in `verification` / `reconciliation` hervor
- scoped Admin-/Device-Readbacks liefern jetzt zusätzlich einen dedizierten `signing_registry`-Diagnostikblock: Registry-Größe, Statusverteilung, referenzierte `key_id`s (active profile / credential / lease / device), einfache Konsistenzchecks sowie additive Key-Lineage-Hinweise (`parent_key_id`, ancestors/descendants, rotation depth) für Rotation-/Drift-Fälle
- Credential-/Lease-Readbacks tragen jetzt additive Rotations-/Lineage-Hinweise (`replacement_for_credential_id`-Kette für Credentials, Signing-Key-Lineage für Credentials und Leases), damit zentrale Operatoren Vor-/Nachfolger einer Rotation lesen können ohne daraus bereits lokale Enforcement-Entscheidungen abzuleiten
- diese Readbacks liefern jetzt zusätzlich kompakte `rotation_summary` / `signing_key_lineage_summary`-Blöcke für Support- und Operator-Sichten, damit Rotationstiefe, Parent/Child-Lage und grobe Risikohinweise ohne Parsen der Vollstruktur lesbar bleiben
- additive `issuer_profiles`-Readbacks erklären jetzt explizit `active_profile` vs. `configured_profile` vs. `effective_profile` sowie eine zentrale `history` der aus Credential-/Lease-Metadaten sichtbaren Issuer-Key-Nutzung; Support muss damit die verwendete Issuer-/Signing-Kette nicht mehr aus rohen Env-/Registry-Dumps rekonstruieren
- `issuer_profiles.support_summary` verdichtet effektive Quelle (`lease` / `credential` / `active_profile`), `effective_key_id`, Registry-Status, History-Umfang und Rotations-Tiefe für schnelle Support-Einschätzung
- `issuer_profiles.support_summary.transition` verdichtet jetzt zusätzlich kompakte Übergangs-/Drift-Ursachen (`transition_state`, `mismatch_reasons`, aktive vs. effektive/configured/credential/lease `key_id`s), damit Support Rotations- oder Fehlkonfigurationslagen als Ein-Zeilen-Hinweis lesen kann statt mehrere Profile manuell zu vergleichen
- `issuer_profiles.readback_summary` ergänzt dazu eine support-lesbare Erklärungsebene: warum genau eine Quelle effektiv ist, ob `configured`/`active` gegen `effective` matchen, welche Status in der sichtbaren Issuer-Historie vorkommen und ob die effektive Key-Lage eher `standalone`, `rotated`, `retired` oder `revoked` ist
- der dedizierte Support-Endpoint (`/api/device-trust/devices/{device_id}/support-diagnostics`) trägt jetzt zusätzlich einen expliziten `diagnostics_timestamp` plus `endpoint_summary` mit kompaktem Issuer-/Signing-Narrativ, Material-Zeitstempeln (`credential_*`, `lease_*`) und Material-Alignment-Hinweisen, damit Support Rotation/Drift/Revocation schneller lesen kann ohne Vollstrukturen manuell zusammenzusetzen
- issuer-profile Diagnostik enthält jetzt zusätzlich ein kompaktes `history_summary` (latest/previous Credential, Status-Zählung, narrative Ein-Zeilen-Erklärung für Rotation vs. Revocation vs. Einzelzustand); derselbe Block spiegelt sich in `reconciliation_summary` und der Support-Endpoint übernimmt die Narrative in `endpoint_summary.support_notes.history_narrative`
- `issuer_profiles.history_summary` trägt jetzt außerdem kompakte Zustandsmarker (`replacement_relation`, `narrative_state`), damit Support und Summary-Sichten einen „neueste sichtbare Credential hat ersetzt und ist inzwischen widerrufen“-Fall konsistent von einfachem Revocation- oder Rotationswortlaut unterscheiden können, ohne Rohhistorie nachzubauen
- Support-/Reconciliation-Readbacks tragen jetzt zusätzlich ein kompaktes `material_history` für Credential-/Lease-Material selbst (visible count, latest/previous Einträge, current-vs-latest Narrative), damit Support erkennbare Drift zwischen aktuellem aktiven Material und zuletzt sichtbaren Datensätzen ohne Rohlisten lesen kann
- `material_history.readback_summary` verdichtet diese Materialsicht zusätzlich auf kompakte Alignment-/Narrativ-Hinweise (`aligned` / `drifted` / `latest_only` / `empty` samt Status-Zählungen), damit Support aktuelle-vs.-neueste Credential-/Lease-Lage in Summary- und operator-safe Views konsistent lesen kann
- neue kompakte `issuer_profiles.lineage_explanation` bündelt für Summary-/Support-Sichten die operative Key-Lineage in einem stabilen Block (`effective_key_id`, `effective_source`, `lineage_state`, `lineage_note`, `transition_state`, `rotation_depth`, `parent_key_id`, `terminal_status`), damit Reconciliation- und Support-Readbacks dieselbe Rotations-/Lineage-Erklärung tragen statt ähnliche Hinweise mehrfach leicht unterschiedlich zu formulieren
- `issuer_profiles.readback_summary` trägt denselben `lineage_explanation`-Block jetzt ebenfalls direkt als stabilen Compact-Contract; operator-safe Serializer backfillen ihn bei älteren/incompleten Inputs aus vorhandener Summary-/Lineage-Metadaten, damit Support-/Owner-Sichten denselben Schlüsselpfad behalten
- `endpoint_summary.support_notes` übernimmt jetzt zusätzlich einen kompakten `history_state`-Markerblock (`history_state`, `replacement_relation`, `narrative_state`, `history_count`), damit die Support-Narrative nicht nur als Freitext, sondern auch als stabile Ein-Zeilen-Klassifikation weitergereicht wird
- `endpoint_summary.contract_summary` ergänzt diese Support-Sicht jetzt um eine explizite Compact-Contract-Klammer (`schema`, `detail_level`, `issuer_state`, `material_state`, `signing_state`), damit Support/operator-safe Clients die grobe Klassifikation nicht aus mehreren Freitext-/Note-Feldern rekonstruieren müssen
- Wave 24 verfeinert diesen Compact-Contract weiter: die verbleibenden verschachtelten Summary-Blöcke (`contract_summary.issuer_state|material_state|signing_state` sowie `support_notes.lineage_explanation|history_state|material_alignment`) tragen nun ebenfalls explizite `detail_level`-Marker, damit zentrale Support-/Owner-/device-safe Readbacks ihren zugeschnittenen Shape selbst beschreiben statt implizit vom Parent-Level zu erben
- zentrale Compact-Summaries bevorzugen bereits vorhandene `readback_summary.lineage_explanation`-Blöcke vor Rekonstruktion aus Fallback-Metadaten; dadurch bleiben Support-, Reconciliation- und operator-safe Views wording-stabil, wenn ein Upstream-Readback die kompakte Lineage-Erklärung schon explizit gesetzt hat
- Wave 25 ergänzt `endpoint_summary.support_notes.source_contracts`: ein kompakter Herkunftsblock zeigt jetzt explizit, auf welche upstream-Compact-Contracts (`issuer_profile_readback`, `issuer_history`, `material_history_readback`) sich die Support-Zusammenfassung stützt, inklusive eigener `schema`-/`detail_level`-Marker und grober Zustandsklassifikation; dadurch müssen Support-/Owner-Sichten die Herkunft der Narrative nicht mehr implizit aus Nachbarfeldern erraten
- `signing_registry.support_summary` verdichtet bekannte Problemindikatoren (`unknown` / `retired` / `revoked` referenzierte Keys, inkonsistente Referenzen, Rotationstiefen) als additive Support-Diagnostik
- operator-safe Support-Readbacks halten diese Verdichtung jetzt konsistent: Signing-Registry zeigt kompakte Credential-Rotationszähler plus terminalen Key-Status je Referenz, ohne rohe Ancestor-/Bundle-/Metadaten freizugeben
- `reconciliation_summary` enthält jetzt auch einen verdichteten Snapshot der Signing-Registry (`registry_size`, `status_counts`, grobe `rotation_depths`, `support_summary`) plus kompakte Issuer-Profile-Hinweise (`effective_key_id`, `effective_source`, `history_count`, `rotation_depth`, `lineage_explanation`, `readback_summary`), damit Operatoren Revocation-/Retirement-/Rotation-Wellen sehen können ohne den kompletten Detailblock selbst auszuwerten
- `reconciliation_summary.issuer_profiles.transition` spiegelt denselben kompakten Transition-Hinweis, damit Support-/Audit-Sichten die Rotations- oder Drift-Ursache direkt im Summary sehen
- Wave 26 schließt hier die letzte offensichtliche Shaping-Lücke im operator-safe Reconciliation-Readback: sowohl `reconciliation_summary.issuer_profiles.transition` als auch ein eingebettetes `reconciliation_summary.issuer_profiles.readback_summary.lineage_explanation` tragen jetzt ebenfalls explizite `detail_level`-Marker, damit zentrale Support-/Owner-/device-safe Clients nicht zwischen gestempelten Parent-Blöcken und impliziten Child-Blöcken springen müssen
- Wave 27 zieht dieselbe Self-Identification jetzt auch in den operator-safe Issuer-Profile-Detailblock nach: `issuer_profiles.support_summary.transition` trägt nun ebenfalls explizit `detail_level`, sodass Support-/Owner-Sichten denselben Transition-Hinweis konsistent lesen können wie die verdichtete Reconciliation-Summary statt implizit vom Parent-Level zu erben
- Wave 27 spiegelt jetzt auch die kompakte Herkunfts-/Provenance-Sicht (`source_contracts`) aus dem Support-Endpoint in `reconciliation_summary.issuer_profiles`; operator-safe Shaping stempelt diese Subblöcke ebenfalls explizit. Dadurch teilen Support-, Trust-Detail- und device-safe Summary-Sichten denselben Compact-Contract-Pfad dafür, auf welche upstream-Compact-Contracts sich ihre Narrative stützt
- Wave 28 poliert diesen Provenance-Contract weiter, ohne neue Enforcement-Logik einzuführen: `source_contracts.issuer_profile_readback` markiert jetzt zusätzlich, ob Source-Reason- und Mismatch-Hinweise vorhanden sind, `issuer_history` trägt kompakte Presence-/Replacement-Marker (`replacement_relation`, `has_narrative`), und `material_history_readback` spiegelt auch die sichtbaren Credential-/Lease-History-Counts. Support-/Owner-Clients können dadurch fehlende vs. absichtlich leere Upstream-Compact-Signale stabiler unterscheiden, ohne Rohdetails oder lokale Kernpfade anzufassen
- Wave 29 macht diese Herkunfts-Sicht noch expliziter: jeder `source_contracts.*`-Block trägt jetzt zusätzlich `present` + `source_state`, damit Support-/Owner-Readbacks klar zwischen wirklich vorhandenem Upstream-Compact-Contract, bewusst fehlendem Contract und aus `material_history` abgeleiteter Fallback-Readback (`derived_from_material_history`) unterscheiden können. Das bleibt rein zentral/additiv und hilft vor allem bei Support-Diagnosen, wenn kompakte Summary-Pfade rekonstruiert statt direkt geliefert wurden
- Wave 30 ergänzt darüber noch eine kleine Provenance-Rollup-Sicht (`source_contract_summary`): statt drei `source_contracts.*`-Unterblöcke einzeln auswerten zu müssen, sehen Support-/Owner-/device-safe Clients jetzt auch kompakt den Gesamtzustand (`complete` / `partial` / `derived_present` / `missing`), Counts je Herkunftszustand sowie eine stabile Namensliste der vorhandenen/abgeleiteten/fehlenden Compact-Contracts. Das bleibt rein lesend, zentral-side und dient nur besserer Support-/Issuer-Diagnostik.
- Wave 32 poliert diesen Provenance-Rollup-Contract weiter: `source_contract_summary` weist jetzt zusätzlich explizit aus, ob die kanonische Compact-Contract-Menge vollständig beobachtet wurde (`coverage_state`, `expected_contract_count`, `observed_contract_count`, `expected_names`, `observed_names`) statt stillschweigend nur die gerade mitgelieferten Unterblöcke zu zählen. Das verbessert Support-/Readback-Klarheit bei älteren oder partiell rekonstruierten Payloads, bleibt vollständig zentral/read-only und ändert keine lokale Enforcement-Logik.
- Wave 33 zieht die Self-Identification noch eine Stufe tiefer in diesen Provenance-Rollup hinein: sowohl `source_contract_summary.state_counts` als auch `source_contract_summary.source_states` tragen jetzt explizite `detail_level`-Marker in raw compact support summaries und in operator-safe/finalized central readbacks. Dadurch müssen Support-/Owner-/device-safe Clients die verschachtelten Herkunfts-Maps nicht mehr implizit vom Parent-Rollup erben.
- Wave 33 macht denselben Rollup-Contract noch etwas support-tauglicher, ohne neue Enforcement-Logik einzuführen: `source_contract_summary` benennt jetzt zusätzlich explizit fehlende erwartete vs. unerwartet beobachtete Compact-Contracts (`missing_expected_names`, `unexpected_names`) samt stabilen Count-/Bool-Markern (`missing_expected_count`, `observed_extra_count`, `has_missing_expected_contracts`, `has_unexpected_contracts`). Dadurch können Support-/Owner-/device-safe Clients rekonstruierte oder vorgezogene Compact-Contracts klarer einordnen, ohne Differenzen selbst aus Namenslisten abzuleiten.
- Wave 34 zieht dieselbe Contract-Selbstbeschreibung noch in die übrigen kompakten History-/Readback-Zähler hinein: `history_state.status_counts`, `material_history.{credential,lease}_history.status_counts` und `material_readback_summary.{credential,lease}_history.status_counts` tragen jetzt in raw support summaries ebenfalls explizit `detail_level=support_compact`; operator-safe/finalized Readbacks stempeln diese Nested-Maps analog mit. Das bleibt rein zentral/additiv und verbessert vor allem Support-/Issuer-Readback-Klarheit bei verdichteten Diagnosen.
- Wave 35 ergänzt den Top-Level-Compact-Contract um `contract_summary.provenance_state`: Support-/Owner-/device-safe Clients sehen damit den groben Upstream-Contract-Zustand (`overall_state`, `coverage_state`, present/derived/missing Counts) direkt neben `issuer_state` / `material_state` / `signing_state`, statt für die gleiche Einordnung immer erst in `support_notes.source_contract_summary` hinabzusteigen. Die Änderung bleibt rein zentral/read-only und verbessert nur Provenance-/Readback-Klarheit.
- Wave 36 macht diesen Top-Level-Provenance-Block noch etwas selbständiger: `contract_summary.provenance_state` trägt jetzt zusätzlich kompakte Gap-/Extra-Marker (`missing_expected_count`, `observed_extra_count`, `has_missing_expected_contracts`, `has_unexpected_contracts`) plus die einzeilige Rollup-`summary`. Support-/Owner-/device-safe Clients können damit Readback-/Contract-Drift direkt im groben Top-Level-Contract erkennen, ohne für häufige Fälle erst in `support_notes.source_contract_summary` hinabzusteigen.
- Wave 37 zieht diese Selbständigkeit noch einen Schritt weiter: derselbe Top-Level-Block spiegelt jetzt auch die stabilen Contract-Namenslisten (`present_names`, `derived_names`, `missing_names`, `missing_expected_names`, `unexpected_names`) aus dem tieferen Provenance-Rollup. Support-/Owner-/device-safe Clients sehen damit nicht nur Counts, sondern direkt, welche upstream Compact-Contracts das Readback geprägt haben oder fehlen – weiterhin rein zentral/read-only und ohne lokale Enforcement-Änderungen.
- Wave 38 macht `contract_summary.provenance_state` endgültig zu einem voll lesbaren Rollup statt nur zu einer Kurzfassung: der Top-Level-Block spiegelt jetzt zusätzlich auch die Coverage-/Inventory-Metadaten aus `support_notes.source_contract_summary` (`total_contracts`, `expected_contract_count`, `observed_contract_count`, `expected_names`, `observed_names`). Support-/Owner-/device-safe Clients können damit Provenance-/Readback-Vollständigkeit direkt aus dem groben Compact-Contract lesen, ohne für einfache Coverage-Fragen in den tieferen Source-Contract-Rollup abzutauchen. Rein zentral, additiv, read-only.
- Wave 39 ergänzt diese Provenance-Rollups um eine kleine, stabile Klassifikationsschicht: sowohl `support_notes.source_contract_summary` als auch das gespiegelte `contract_summary.provenance_state` tragen jetzt zusätzlich `verdict` + `verdict_text` (`canonical_complete`, `canonical_derived`, `contracts_incomplete`, `contracts_extended`, `contracts_drifted`, `contracts_missing`). Support-/Owner-/device-safe Clients können damit Upstream-Compact-Contract-Vollständigkeit oder Drift direkt lesen, ohne Name-Arrays zu diffen oder `overall_state`/Coverage-Flags selbst zu kombinieren. Rein zentral, additiv, read-only.
- Wave 31 poliert diesen Rollup-Contract weiter, ohne neue Enforcement-Logik einzuführen: `source_contract_summary` trägt jetzt zusätzlich stabile Zähler-/Bool-Felder (`total_contracts`, `*_contract_count`, `has_*_contracts`), damit Support-/device-safe Clients Vorhandensein, partielle Herkunft und Readback-Lücken direkt aus dem Rollup lesen können statt Namenslisten oder `state_counts` selbst interpretieren zu müssen.
- klare, additive Statusableitung für `active` / `grace` / `expired` / `revoked` ohne lokale Enforcement-Änderung
- rein beobachtend / vorbereitend, noch **nicht** hart durchsetzend im lokalen Runtime-Pfad

### Device Certificate / Credential
Vom Server ausgestellte Device-Identity.

### Lease
Zeitlich begrenzte Betriebsfreigabe für monetisierte Nutzung.

---

## 3. Enrollment-Flow (V1 Zielbild)

## Schritt 1 — Enrollment vorbereiten
Central erzeugt ein Enrollment Token für:
- bestimmten Tenant
- bestimmten Standort
- optional konkreten Device-Slot

## Schritt 2 — Gerät erzeugt Schlüssel
Beim ersten Start erzeugt das Gerät lokal:
- asymmetrisches Keypair
- private key lokal geschützt
- public key / CSR für central

## Schritt 3 — Enrollment Request
Gerät sendet:
- enrollment token
- public key / CSR
- Geräte-Metadaten
- Installationskontext

## Schritt 4 — Server prüft und bindet
Server:
- validiert Token
- legt Device Record an oder nutzt reservierten Slot
- speichert Public Key / Thumbprint
- stellt Device Credential / Zertifikat aus

## Schritt 5 — Lokale Persistenz
Gerät speichert:
- private key (geschützt)
- device credential
- device metadata ohne frei herumliegende rohe Secrets

---

## 4. Schutz des privaten Schlüssels lokal

Bevorzugt:
- Windows DPAPI / maschinengebundene Schutzmechanismen
- TPM, wenn sinnvoll verfügbar

Minimum:
- private key lokal verschlüsselt gespeichert
- kein Klartext-API-Key in einfachen JSON-Dateien
- keine freie Mehrfachablage desselben Secrets

Wichtig:
- ein kopierter Datenordner allein darf nicht genügen, um das Device zu klonen
- die zentrale Gegenstelle muss bei verdächtigen Identitätswechseln Alarm schlagen

---

## 5. Lease-Modell

## Zweck
Der Lease ist die betriebliche Freigabe für monetisierte Nutzung.

Er enthält:
- `lease_id`
- `device_id`
- `license_id`
- `issued_at`
- `expires_at`
- `grace_policy`
- `signature`
- ein kanonisches Payload-Format für spätere Verifikation (`schema`, Status, Capability-Overrides, Credential-Metadaten)

**Central-Rebuild Wave-3 Placeholder:**
- Signatur aktuell als serverseitig stabiler HMAC-Placeholder, nicht als finale PKI-Signatur
- dient für Kontrakt-, Serialisierungs- und Übergabetests zwischen Central und späterem Runtime-Validator
- lokale Runtime wertet dieses Bundle aktuell noch nicht hart aus

**Wave-4 additive Erweiterung:**
- Credential-Records können jetzt zentral von `pending` → `active` → `revoked` überführt werden, ohne den lokalen Kern zu ändern
- Placeholder-Credentials erhalten ein deterministisches `key_id` und ein klar markiertes Dummy-`certificate_pem`, damit nachfolgende PKI-Arbeit nicht bei null startet
- Lease-Revoke und Credential-Revoke setzen konsistente Device-Trust-Snapshots (`trust_status`, `lease_status`, `credential_status`) für Portal-/Audit-Sicht

## Regeln
- nur Geräte mit gültiger Identity erhalten einen Lease
- Lease ist kurzlebig genug, um Missbrauch zu begrenzen
- Lease wird lokal gecached, aber nicht dauerhaft als ewige Freischaltung behandelt
- nach Ablauf kein neuer monetisierter Unlock/Top-up

---

## 6. Rebind / Replace / Recovery

## Rebind
Wenn dasselbe physische Gerät an anderen Scope soll:
- nur kontrolliert via central approval
- alte Bindung dokumentiert
- neuer Scope auditiert

## Replace Device
Wenn ein PC kaputtgeht:
- altes Gerät wird ersetzt / revoked
- neues Gerät erhält neues Enrollment Token
- neuer Schlüssel / neues Credential
- alter Trust wird entzogen
- Commercial History bleibt zentral erhalten

## Recovery
Wenn Gerät neu aufgesetzt werden muss:
- kein blindes Kopieren des alten App-/Datenordners
- Recovery nur über kontrollierten Re-enrollment-/Restore-Flow

---

## 7. Revocation

Ein Gerät kann zentral entzogen werden bei:
- Verdacht auf Klon/Missbrauch
- Geräteverlust
- Vertrags-/Lizenzende
- schwerem Sicherheitsproblem

Folgen:
- Trust status → revoked
- aktive Leases verfallen oder werden serverseitig ungültig
- Gerät fällt lokal in Support-/Provisioning-Modus

---

## 8. Anti-Cloning-Regeln

1. Eine kopierte lokale DB darf keine neue valide Device-Identity erzeugen.
2. Ein kopierter App-Ordner darf ohne gültigen Schlüssel + gültigen Lease nicht monetisiert laufen.
3. Device-Credentials sind an `device_id` + Scope gebunden.
4. Gleicher Credential-Fingerprint von mehreren Hosts ist verdächtig und muss alarmieren.
5. Rebinds und Replacements sind separate, auditierten Flows.

---

## 9. V1-Entscheidungen

### V1 muss liefern
- Enrollment Token
- Device Keypair
- signiertes Device Credential
- Lease-Mechanismus
- Revoke/Rebind/Replace-Flows
- Auditierbarkeit

### V1 muss noch nicht liefern
- vollständige Hardware-Attestation auf Enterprise-Niveau
- plattformspezifische Secure-Enclave-Magie auf jedem Gerät

Aber:
V1 muss deutlich besser sein als `install_id + plaintext api_key`.

---

## 10. Operative Prüfungen

Bei jedem produktiven Device-Release prüfen:
- gibt es genau eine zentrale Device-Identity?
- liegt kein rohes frei wiederverwendbares Secret offen herum?
- funktioniert Revoke sauber?
- funktioniert Replace sauber?
- blockiert das Gerät monetisierte Nutzung ohne gültigen Lease?
