# Darts Kiosk v3.4.5 — Installations- und Betriebshandbuch

## Schnellstart (Windows)

### 1. Voraussetzungen
- Windows 10/11
- Python 3.10+ (python.org)
- Git (optional, fuer Updates)

### 2. Erstinstallation
```
1. darts-kiosk-v3.4.5-windows.zip entpacken
2. setup_windows.bat ausfuehren (als Administrator)
   → Python-Umgebung wird erstellt
   → Abhaengigkeiten installiert
   → .env-Dateien aus .env.example erstellt
3. start.bat ausfuehren
   → Backend startet auf Port 8001
   → Frontend startet auf Port 3000
4. Browser oeffnen: http://localhost:3000
5. Setup-Wizard durchlaufen (Admin-Account anlegen)
```

### 3. Agent starten
```
1. agent\start_agent.bat ausfuehren
   → Agent startet auf Port 8002
2. Autostart einrichten:
   python agent\setup_autostart.py
   → Erstellt Task Scheduler Eintrag
```

### 4. LAN-Zugriff
Backend und Frontend muessen auf `0.0.0.0` gebunden sein:
- Backend: In `start.bat` ist `--host 0.0.0.0` gesetzt
- Frontend: Erreichbar ueber IP des PCs (z.B. http://192.168.1.100:3000)

---

## Lizenz einrichten

### Schritt 1: Kunde anlegen
Admin Panel → Lizenzierung → Tab "Kunden" → Neuen Kunden erstellen

### Schritt 2: Standort erstellen
Tab "Standorte" → Standort anlegen und Kunden zuweisen

### Schritt 3: Lizenz erstellen
Tab "Lizenzen" → Neue Lizenz:
- Kunde und Standort waehlen
- Plan-Typ (standard/premium/test)
- Laufzeit (ends_at)
- Max. Geraete

### Schritt 4: Geraet binden
Tab "Geraete" → Neues Geraet:
- Board-ID eingeben (z.B. BOARD-1, muss mit BOARD_ID in .env uebereinstimmen)
- Standort zuweisen
- install_id wird automatisch beim ersten Game-Start gebunden

### Schritt 5: Pruefen
- Tab "Dashboard": Lizenzstatus pruefen
- Tab "Audit-Log": Events nachverfolgen

---

## Geraetebindung (Device Binding)

### Automatische Bindung
- Beim ersten `Start Game` wird die install_id des Kiosks automatisch an das Geraet gebunden
- Die install_id wird in `data/device_identity.json` gespeichert
- Diese ID bleibt persistent ueber Neustarts

### Mismatch
Wenn ein anderer PC mit der gleichen Lizenz startet:
1. **Grace-Zeitraum** (Standard 48h): Sessions bleiben erlaubt, Warnung im UI
2. **Nach Ablauf**: Sessions werden blockiert
3. **Loesung**: Im Admin Panel → Geraete → "Neu binden" klicken

### Binding Grace konfigurieren
Admin Panel → Lizenzierung → "Binding Settings" Endpoint:
- Standard: 48 Stunden
- Aenderbar: POST /api/licensing/binding-settings { "binding_grace_hours": 72 }

---

## Zyklische Lizenzpruefung

- Laeuft automatisch im Hintergrund (alle 6 Stunden)
- Prueft Lizenzstatus und aktualisiert lokalen Cache
- Laeuft auch beim Serverstart
- Bei Netzwerkfehler: Letzter gueltiger Status bleibt aktiv
- Manuell ausloesen: Admin Panel → Lizenzierung → Audit-Log → "Jetzt pruefen"

---

## Troubleshooting

### Agent offline
**Symptom**: Im Admin Panel zeigt der Agent-Tab "Offline" an

**Ursachen**:
1. Agent-Prozess nicht gestartet → `agent\start_agent.bat` ausfuehren
2. Port blockiert → Firewall-Regel fuer Port 8002 pruefen
3. Autostart nicht eingerichtet → `python agent\setup_autostart.py` ausfuehren

**Pruefung**: `http://localhost:8002/status` im Browser oeffnen

### Lizenz blockiert
**Symptom**: Kiosk zeigt "Lizenz blockiert" Overlay

**Ursachen**:
1. Lizenz abgelaufen → Im Admin Panel verlaengern (Tab "Lizenzen" → "Verlaengern")
2. Lizenz durch Admin gesperrt → "Aktivieren" klicken
3. Kunde gesperrt → Kundenstatus pruefen

**Quick-Fix**: Wenn keine Lizenz konfiguriert ist, laeuft das System im "Fail-Open" Modus (erlaubt alles)

### Geraete-Mismatch
**Symptom**: "Geraet nicht autorisiert" im Kiosk

**Ursachen**:
1. Anderer PC versucht gleiche Lizenz zu nutzen
2. Hardware-Wechsel (neue install_id)
3. data/device_identity.json wurde geloescht

**Loesung**:
1. Admin Panel → Lizenzierung → Tab "Geraete"
2. Betroffenes Geraet finden (zeigt "Mismatch" Badge)
3. "Neu binden" klicken → Bindet an aktuelle install_id
4. ODER: device_identity.json vom alten PC kopieren

### Kein Netzwerkzugriff
**Symptom**: Andere Geraete im LAN koennen nicht auf den Kiosk zugreifen

**Pruefung**:
1. `ipconfig` ausfuehren → IP-Adresse notieren
2. Firewall-Regeln pruefen (Port 8001 und 3000 freigeben)
3. Backend muss auf `0.0.0.0` gebunden sein (nicht `127.0.0.1`)

### Audit-Log pruefen
Bei Problemen immer zuerst das Audit-Log pruefen:
- Admin Panel → Lizenzierung → Tab "Audit-Log"
- Filtert nach Event-Typ (z.B. BIND_BLOCKED, LICENSE_CHECK_FAILED)
- Zeigt Zeitstempel, Akteur und Details zu jedem Event
