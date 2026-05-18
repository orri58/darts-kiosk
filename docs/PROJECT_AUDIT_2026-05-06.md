# Darts Kiosk — Vollaudit 2026-05-06

## Executive Summary

**Kurzurteil:**
- **Kein Full Rewrite.**
- **Aber auch nicht einfach stumpf so weiterpflegen.**
- Die richtige Richtung ist ein **teilweiser Neuaufbau / strukturierter Umbau** bei **eingefrorenem lokalem Kern**.

## Gesamtbewertung

### Was stark ist
- Der **lokale Runtime-Kern** ist real, brauchbar und schützenswert.
- Das Projekt hat inzwischen eine erkennbare strategische Linie:
  - **local-first**
  - **protected local core**
  - **central/control-plane nur optional und fehlertolerant**
- Der Kiosk und Teile des neueren Admin-/Operator-Systems zeigen bereits echtes Produktniveau.
- Die letzten Wellen auf Central / Operator / Commercial waren nicht sinnloser Feature-Staub, sondern haben eine echte Control-Plane-Richtung erzeugt.
- Es gibt deutlich mehr Doku, Tests und Release-Disziplin als in einem typischen Bastelprojekt.

### Was nicht professionell genug ist
- Das Repo wirkt noch wie **Source + Runtime + Build-Artefakte + Labortisch gleichzeitig**.
- Die Architekturidee ist besser als ihre aktuelle strukturelle Umsetzung.
- `central_server/server.py` ist zu groß und zu monolithisch.
- Dokumentation ist inhaltlich stark, aber als Einstieg **zu konkurrierend und teils widersprüchlich**.
- Das UX-/Design-System ist noch nicht einheitlich genug:
  - Kiosk
  - Admin
  - Operator
  - Portal
  wirken noch zu oft wie verschiedene Produktgenerationen.
- Release-/Qualitäts-Governance ist besser als früher, aber noch nicht auf dem Niveau eines wirklich professionell release-governed Produkts.

---

## Empfehlung auf einen Satz

**Local Core erhalten, Central/Operator/Portal systematisch neu formen, Repo und Doku radikal klarer machen, Design-/Shell-System vereinheitlichen, Quality Gates professionalisieren.**

---

## 1. Architektur-Audit

## Urteil
**Partial rebuild.**

### Behalten
- lokaler Runtime-Kern
- Observer-/Board-/Session-Lifecycle-Grundmodell
- Pricing-/Capacity-Grundlogik
- Windows-Board-PC-Richtung
- local-first Autorität

### Umbauen
- `central_server` strukturell
- API-/Contract-Disziplin
- Repo-Grenzen und Packaging-Sauberkeit
- Migration-/Schema-Disziplin
- Trust-/License-/Remote-Action-Subsysteme als klarere Module

### Harte Probleme
- `central_server/server.py` ist zu groß und zu eng gekoppelt.
- Zu viel `dict`-/JSON-Blob-Logik statt konsequenter Verträge.
- Migrations-/Bootstrap-Logik steckt zu stark im App-Startup.
- Sicherheitsdefaults sind für Marktprodukt noch zu weich.
- Modulare Grenzziehung ist stärker dokumentiert als technisch erzwungen.

### Architektur-Zielbild
Trennung in wenige klare Kontexte:
1. **Local Runtime Core**
2. **Local Central Adapter / Sync Layer**
3. **Central Control Plane**
4. **Device Trust / Credential Authority**
5. **Shared Contracts / DTOs / Schemas**

---

## 2. UX-/Design-Audit

## Urteil
**Kein kompletter Redesign-Reset.**
Aber: **iterativer Redesign mit teilweisem Reset gemeinsamer Patterns**.

### Was gut ist
- Kiosk ist die stärkste Produktfläche.
- Neuere Admin-Flächen haben bereits brauchbare Produktqualität.
- Operator ist funktional und wird ernstzunehmend, aber noch zu dicht und zu sehr aus Features akkumuliert.

### Hauptprobleme
- Die Flächen wirken noch wie **mehrere UI-Generationen parallel**.
- Portal wirkt zu oft wie **abgespeckte Operator-Kopie** statt klarer read-only Modus.
- Login-/Shell-/Sidebar-/Header-Systeme sind uneinheitlich.
- Status-/Badge-/Severity-Semantik ist nicht durchgängig normiert.
- Zu viele lokale Styling-Entscheidungen statt harter gemeinsamer Produktbausteine.
- Settings sind mächtig, aber immer noch eine klassische Akkretionszone.

### Zielrichtung
**Ein Brand, drei Modi:**
1. **Kiosk Mode**
2. **Console Mode** (Admin + Operator)
3. **Read-only Mode** (Portal)

Nicht vier lose Teilprodukte.

---

## 3. Doku- / Developer-Experience-Audit

## Urteil
**Substanz gut, Einstieg schlecht kuratiert.**

### Positiv
- Es gibt echte Architektur-, Status-, Testing- und Runbook-Dokumente.
- Die Kernidee des local-first protected core ist mehrfach dokumentiert.
- Es gibt ernsthafte Handoff-/Governance-Versuche.

### Probleme
- Zu viele „wichtige“ Dokumente konkurrieren.
- Root- / Front-Door-Doku driftet teils gegenüber aktuellem Release-Stand.
- Historische Modelle und aktuelle Modelle sind nicht hart genug getrennt.
- Repo enthält zu viele Build-/Runtime-/Temp-Artefakte und erschwert das Verständnis.
- Ein neuer Entwickler wird die Produktidentität nicht schnell genug sauber verstehen.

### Größte Doku-Fallen
- widersprüchliche Front-Door-Signale
- mehrere Deployment-Epochen gleichzeitig im Sichtfeld
- fehlende harte Trennung zwischen **kanonisch** und **historisch**

---

## 4. Qualität / Release / Ops-Audit

## Urteil
**Seriöses internes Produkt / fortgeschrittener Beta-Stand, aber noch keine voll professionalisierte Release-Operation.**

### Gut
- fokussierte Backend-Gates existieren
- Frontend-Build ist benutzbar
- Packaging / Release-Artefakte existieren
- Runbook-/Supportbundle-/Readiness-Denke ist da
- Release-Changelog-/Notes-Disziplin ist spürbar besser geworden

### Nicht gut genug
- CI ist noch nicht hart genug als Qualitäts-Governance
- Testfläche ist groß, aber nicht sauber konsolidiert
- Feld-/Windows-/Autodarts-Beweis bleibt der kritischste echte Praxisblocker
- Packaging-/Workflow-Logik ist noch nicht sauber genug aus einer Quelle abgeleitet
- Beobachtbarkeit ist eher support-getrieben als operations-getrieben

---

## 5. Die wichtigsten professionellen Defizite auf einen Blick

1. **Repo-Sauberkeit / Source-vs-Artefakt-Grenze**
2. **Central-Monolith / fehlende modulare Trennung**
3. **Doku-Frontdoor / Drift / kanonische Struktur**
4. **Uneinheitliches Design-/Shell-/Portal-/Operator-System**
5. **Noch nicht ausreichend harte Release-/CI-/Ops-Gates**
6. **Trust-/License-/Commercial-Richtung richtig, aber noch nicht vollständig produktreif**

---

## 6. Rebuild-Entscheidung

## Nicht empfohlen
- alles wegwerfen
- kompletter Neuaufbau des ganzen Produkts

## Empfohlen
- **lokalen Kern einfrieren**
- **Central strukturell neu schneiden**
- **Doku und Repo-IA aufräumen**
- **Design-/Shell-System auf gemeinsame Regeln ziehen**
- **Qualitäts-/Release-Modell härten**

Das ist am effizientesten und realistischsten.

---

## 7. Prioritäts-Rangfolge

### Sofort
- kanonische Produktidentität dokumentieren
- Repo-/Doku-Einstieg korrigieren
- Central in modulare Services/Router schneiden
- Shell-/Portal-/Operator-System vereinheitlichen

### Kurzfristig
- Release-/CI-/Test-Matrix professionalisieren
- Frontend-/Interaction-Regressionsschutz für Operator-/Commercial-Flows erhöhen
- Portal klarer als read-only Modus statt Halb-Kopie positionieren

### Mittelfristig
- Device Trust / Licensing / Remote Actions in stärker produktreife Verträge und Migrationsdisziplin überführen
- professionelle Beobachtbarkeit / Incident-/Support-/Fleet-Telemetrie ausbauen

---

## 8. Klare Entscheidung

**Fazit:**
Das Projekt ist **nicht kaputt genug für einen Neustart**, aber **zu unordentlich für reines Weiterpolieren**.

Die richtige Antwort ist:

> **gezielter teilweiser Neuaufbau bei erhaltener Produktkern-Logik**

und genau darauf sollte der Masterplan ausgerichtet werden.
