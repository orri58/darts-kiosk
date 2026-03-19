# Darts Kiosk Windows Agent — Deployment Guide
## Version 3.4.1

---

## 1. Voraussetzungen
- Windows 10/11
- Python 3.10+ installiert (empfohlen: in `.venv`)
- Darts Kiosk Backend laeuft auf `localhost:8001`
- `AGENT_SECRET` in `backend/.env` gesetzt

## 2. Installation

### 2.1 Agent-Dateien
Der Agent liegt im Ordner `agent/` des Release-Bundles:
```
agent/
  darts_agent.py          # Hauptprozess
  start_agent.bat         # Manueller Start (mit Konsolenfenster)
  start_agent_silent.vbs  # Unsichtbarer Start (fuer Autostart)
  setup_autostart.py      # Task Scheduler Registrierung
  requirements.txt        # Keine externen Abhaengigkeiten
  AGENT_DEPLOYMENT.md     # Diese Datei
```

### 2.2 AGENT_SECRET pruefen
Der Agent liest das Secret automatisch aus `backend/.env`:
```
AGENT_SECRET=dein-geheimes-passwort
```
Optional kann auch `AGENT_PORT=8002` gesetzt werden (Standard: 8002).

## 3. Manueller Start (Test)
```cmd
cd agent
start_agent.bat
```
Pruefe im Browser: `http://127.0.0.1:8002/status`

## 4. Autostart einrichten (Produktion)

### 4.1 Task Scheduler registrieren
Als Administrator ausfuehren:
```cmd
cd agent
python setup_autostart.py
```

Das erstellt den Task `DartsKioskAgent` mit:
- **Trigger:** Systemstart (+15s Delay) UND Benutzeranmeldung (+5s Delay)
- **Ausfuehrung:** `start_agent_silent.vbs` (kein Konsolenfenster)
- **Rechte:** Hoechste Rechte (SYSTEM)
- **Neustart bei Fehler:** 3x alle 60 Sekunden
- **Single Instance:** Neue Instanz wird ignoriert wenn bereits aktiv

### 4.2 Task pruefen
```cmd
schtasks /Query /TN DartsKioskAgent /FO LIST /V
```
Oder: Task Scheduler oeffnen → `DartsKioskAgent` suchen.

### 4.3 Task entfernen
```cmd
python setup_autostart.py --remove
```

### 4.4 Task manuell neu registrieren
```cmd
python setup_autostart.py --remove
python setup_autostart.py
```

## 5. Logs pruefen
Agent-Logs: `data/logs/agent.log`
```cmd
type data\logs\agent.log
```
Oder im Admin Panel unter System → Agent Tab.

## 6. Single Instance Guard
Der Agent verwendet eine Lockdatei (`data/logs/agent.lock`).
- Beim Start: Prueft ob ein anderer Agent-Prozess laeuft
- Falls ja: Beendet sich sofort mit Logeintrag
- Beim Stopp: Lockdatei wird automatisch entfernt
- Bei Crash: Stale Lock wird beim naechsten Start erkannt und ueberschrieben

## 7. Fallback-Verhalten
Wenn der Agent nicht laeuft:
- Das Backend nutzt automatisch die bestehenden direkten Services
- Im Admin Panel wird `via: Fallback (direkt)` angezeigt
- Alle Funktionen (Autodarts, System, Kiosk) bleiben verfuegbar
- Kein Funktionsverlust

## 8. Fehlerbehebung

| Problem | Loesung |
|---|---|
| Agent startet nicht | `data/logs/agent.log` pruefen |
| Port belegt | `AGENT_PORT=8003` in backend/.env setzen |
| Doppelte Instanz | `data/logs/agent.lock` loeschen, Agent neu starten |
| Task nicht registriert | `python setup_autostart.py` als Admin ausfuehren |
| Kein Python gefunden | `.venv` erstellen oder Python zum PATH hinzufuegen |
