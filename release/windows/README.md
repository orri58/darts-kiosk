# Darts Kiosk - Windows Test Bundle (Arcade-Modus)

## Voraussetzungen

| Software   | Version  | Download |
|-----------|----------|----------|
| Python    | 3.11 oder 3.12 | https://www.python.org/downloads/ |
| Node.js   | **20 LTS** (empfohlen) | https://nodejs.org/ → **LTS** wählen |
| Google Chrome | Aktuell | https://www.google.com/chrome/ |
| VC++ Redist x64 | Aktuell | https://aka.ms/vs/17/release/vc_redist.x64.exe |

> **WICHTIG bei Python**: "Add Python to PATH" ankreuzen!
>
> **WICHTIG bei Node.js**: Die **LTS**-Version wählen (z.B. 20.x), **NICHT** "Current" (25.x ist inkompatibel).
>
> **Google Chrome**: Wird fuer die Autodarts-Integration und den Kiosk-Vollbild-Modus verwendet. Der Observer nutzt ein separates Chrome-Profil, damit die Google/Autodarts-Anmeldung erhalten bleibt.
>
> **VC++ Redistributable**: Wird fuer SQLAlchemy (greenlet) benoetigt. Auf den meisten PCs bereits vorhanden.

## Installation (einmalig)

```
1. ZIP entpacken
2. check_requirements.bat  → prueft Python, Node, Chrome, VC++ Redistributable
3. setup_windows.bat       → erstellt .venv, installiert Abhaengigkeiten
```

Das Setup erstellt eine isolierte Python-Umgebung (`.venv`) im Projektordner.

## Starten (Arcade-Modus)

```
4. start.bat               → startet alles automatisch
```

`start.bat` macht folgendes:
1. Backend starten (Port 8001, LAN-Zugriff auf 0.0.0.0)
2. Frontend starten (Port 3000, LAN-Zugriff auf 0.0.0.0)
3. **Credits-Overlay** starten (Python-Fenster, immer oben, klick-durchlaessig)
4. **Kiosk im Chrome-Vollbild-Modus** oeffnen (kein Rahmen, kein Adressfeld)

## Arcade-Ablauf

```
GESPERRT     Kiosk-Vollbild zeigt "GESPERRT" + Preise + Branding
      |
  [Admin/Wirt entsperrt Board per Admin-Panel oder PIN]
      |
ENTSPERRT    Backend startet Autodarts-Chrome (eigenes Profil, Vollbild)
             Kiosk-Fenster geht in den Hintergrund
             Credits-Overlay zeigt sich (immer oben, transparent)
      |
  [Spieler startet Spiel in Autodarts]
      |
IM SPIEL     Observer erkennt Spielstart → Credits -1
             Overlay aktualisiert Anzeige
      |
  [Spiel endet / Credits leer / Zeit abgelaufen]
      |
GESPERRT     Autodarts-Chrome schliesst sich
             Kiosk-Fenster kehrt in den Vordergrund
             Overlay versteckt sich
```

## Credits-Overlay

Das Overlay ist ein **separates Python-Fenster** (nicht Teil des Browsers), das:
- **Immer oben** ueber allen Fenstern liegt (auch ueber Fullscreen-Chrome)
- **Klick-durchlaessig** ist (Mausklicks gehen durch zum darunterliegenden Fenster)
- **Transparenten Hintergrund** hat (nur die Anzeige ist sichtbar)
- Sich **automatisch zeigt/versteckt** basierend auf dem Session-Status

Es zeigt:
- Verbleibende Spiele ("SPIELE UEBRIG: 3")
- Verbleibende Zeit im Zeit-Modus
- "LETZTES SPIEL" Warnung mit Upsell-Text

## Persistente Autodarts-Anmeldung

Der Observer verwendet ein **eigenes Chrome-Profil** pro Board:
- Gespeichert unter `data/chrome_profile/BOARD-1/`
- Google-Login und Autodarts-Anmeldung bleiben ueber Sessions erhalten
- Spieler muessen sich **nur einmal** anmelden

## URLs

| Seite          | Von diesem PC | Von anderen Geraeten (LAN) |
|---------------|---------------|--------------------------|
| Setup-Wizard  | http://localhost:3000/setup | http://\<LAN-IP\>:3000/setup |
| Admin-Panel   | http://localhost:3000/admin | http://\<LAN-IP\>:3000/admin |
| Kiosk         | http://localhost:3000/kiosk/BOARD-1 | http://\<LAN-IP\>:3000/kiosk/BOARD-1 |
| Backend-API   | http://localhost:8001/api/health | http://\<LAN-IP\>:8001/api/health |

Die LAN-IP wird automatisch von `start.bat` erkannt und angezeigt.

## Board-ID aendern

Standard ist `BOARD-1`. Um eine andere Board-ID zu verwenden:
1. `start.bat` oeffnen
2. `set BOARD_ID=BOARD-1` aendern (z.B. `set BOARD_ID=MEIN-BOARD`)

## Beenden

- `stop.bat` ausfuehren, oder
- Im `start.bat`-Fenster eine Taste druecken

`stop.bat` beendet: Backend, Frontend, Credits-Overlay, und Kiosk-Chrome.

## Logs

- `logs\backend.log` — Backend-Ausgaben und Fehler
- `logs\frontend.log` — Frontend-Kompilierung

## Fehlerbehebung

**"greenlet kann nicht geladen werden":**
- Microsoft VC++ Redistributable x64 installieren: https://aka.ms/vs/17/release/vc_redist.x64.exe
- Danach `setup_windows.bat` erneut ausfuehren

**Backend startet nicht:**
- `logs\backend.log` pruefen
- Port 8001 belegt? → `stop.bat`, dann `start.bat`

**Frontend startet nicht / "ENOTFOUND":**
- `logs\frontend.log` pruefen
- Node.js Version pruefen: `node --version` (muss 18-22 sein, NICHT 25+)
- Port 3000 belegt? → `stop.bat`, dann `start.bat`

**Autodarts-Chrome oeffnet sich nicht:**
- Google Chrome installiert? `start.bat` zeigt "Chrome gefunden" oder Warnung
- Playwright installiert? `.venv\Scripts\activate` → `python -m playwright install chromium`
- `logs\backend.log` nach "BROWSER LAUNCH" Eintraegen suchen

**Credits-Overlay erscheint nicht:**
- Overlay startet automatisch, zeigt sich aber erst bei aktiver Session
- Board entsperren → Overlay sollte nach 3 Sekunden erscheinen
- Pruefen: `python credits_overlay.py --board-id BOARD-1 --api http://localhost:8001`

**LAN-Zugriff funktioniert nicht (vom Handy):**
- Windows-Firewall: Port 3000 und 8001 freigeben
- Beide Geraete im gleichen Netzwerk?

## Dateistruktur

```
darts-kiosk-v1.0.0-windows/
├── .venv/                     ← Python-Umgebung (nach Setup)
├── backend/
│   ├── .env                   ← Backend-Konfiguration
│   └── ...
├── frontend/
│   ├── .env                   ← Frontend-URL (wird automatisch gesetzt)
│   └── ...
├── data/
│   ├── db/darts.sqlite        ← Datenbank
│   ├── chrome_profile/        ← Persistente Chrome-Profile (Autodarts-Login)
│   ├── kiosk_chrome_profile/  ← Chrome-Profil fuer Kiosk-UI
│   ├── assets/sounds/         ← Sound-Dateien
│   └── backups/               ← Automatische Backups
├── logs/
├── check_requirements.bat     ← Schritt 1: Voraussetzungen
├── setup_windows.bat          ← Schritt 2: Einrichtung
├── start.bat                  ← Schritt 3: Starten (Arcade-Modus)
├── stop.bat                   ← Beenden
├── credits_overlay.py         ← Credits-Overlay (Python/Tkinter)
├── run_backend.py             ← Windows-Backend-Starter
├── _run_backend.bat           ← (intern)
└── _run_frontend.bat          ← (intern)
```
