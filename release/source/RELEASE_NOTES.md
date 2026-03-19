# Darts Kiosk — Release Notes v3.4.5
## Lizenz-System Stabilisierung

### Neue Features seit v3.4.2

#### v3.4.3 — Device Binding
- Persistente Geraete-ID (install_id) fuer Hardware-Bindung
- Auto-Bind beim ersten Game-Start
- Mismatch-Erkennung bei fremden Geraeten
- Rebind durch Superadmin im Admin Panel
- Device Identity Card in der Lizenzverwaltung

#### v3.4.4 — Mismatch Grace
- Konfigurierbarer Grace-Zeitraum (Standard 48h) bei Geraete-Mismatch
- Sessions bleiben waehrend Grace erlaubt (mit Warning)
- Nach Ablauf: automatische Blockierung
- Tracking: mismatch_detected_at, previous_install_id
- Auto-Bind NUR bei Game-Start, nicht bei Unlock

#### v3.4.5 — Zyklische Pruefung + Audit-Log
- Background-Lizenzpruefung alle 6 Stunden (konfigurierbar)
- Fail-Safe: Bei Fehler bleibt letzter gueltiger Status aktiv
- Manueller Trigger via Admin Panel ("Jetzt pruefen")
- Vollstaendiges Audit-Log fuer alle Lizenz-Events
- Neuer "Audit-Log" Tab mit Filter und Event-Badges

### Bekannte Einschraenkungen
- Rollen-basierte Sichtbarkeit noch nicht implementiert (alle Admins sehen alles)
- Kein automatischer Setup-Wizard (manuelle Konfiguration erforderlich)
- Agent-Autostart nur unter Windows via Task Scheduler

### Systemanforderungen
- Windows 10/11 oder Linux (Ubuntu 20.04+)
- Python 3.10+
- Node.js 18+ (nur fuer Development)
- SQLite 3.x (eingebettet)

### Installation
Siehe MANUAL_DEPLOYMENT.md (Windows) oder install.sh (Linux).

### Lizenz einrichten (Kurzanleitung)
1. Admin Panel → Lizenzierung → Kunden anlegen
2. Standort erstellen und Kunden zuweisen
3. Lizenz erstellen (Plan, Laufzeit)
4. Geraet mit Board-ID anlegen (install_id wird automatisch gebunden)
5. Kiosk starten → Lizenz wird automatisch geprueft
