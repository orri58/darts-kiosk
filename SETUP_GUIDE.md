# Darts Kiosk System - Setup Guide

## Inhaltsverzeichnis
1. [Systemanforderungen](#systemanforderungen)
2. [Architektur-Übersicht](#architektur-übersicht)
3. [Master-PC Einrichtung](#master-pc-einrichtung)
4. [Board-PC (Agent) Einrichtung](#board-pc-agent-einrichtung)
5. [Netzwerk-Konfiguration](#netzwerk-konfiguration)
6. [Kiosk-Modus (Vollbild)](#kiosk-modus-vollbild)
7. [Board-Registrierung](#board-registrierung)
8. [Troubleshooting](#troubleshooting)

---

## Systemanforderungen

### Hardware (pro Board-PC)
- Mini-PC (Intel NUC, Beelink, o.ä.)
- RAM: mindestens 4 GB
- Storage: mindestens 16 GB SSD
- Touch-Monitor (empfohlen: 21-27 Zoll)
- Netzwerk: LAN-Anschluss (WiFi möglich, aber LAN stabiler)

### Software
- Windows 10/11 oder Ubuntu 22.04 LTS
- Docker & Docker Compose
- Chrome/Edge Browser (für Kiosk-Modus)
- Autodarts (separat installiert auf jedem Board-PC)

---

## Architektur-Übersicht

```
┌─────────────────────────────────────────────────────────────┐
│                        LAN (192.168.1.x)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐     ┌─────────────────┐                │
│  │   MASTER-PC     │     │    BOARD-1      │                │
│  │  192.168.1.100  │     │  192.168.1.101  │                │
│  ├─────────────────┤     ├─────────────────┤                │
│  │ - Admin Panel   │◄───►│ - Kiosk UI      │                │
│  │ - Board Registry│     │ - Agent API     │                │
│  │ - Central DB    │     │ - Autodarts     │                │
│  └─────────────────┘     │ - Local DB      │                │
│                          └─────────────────┘                │
│                                                             │
│                          ┌─────────────────┐                │
│                          │    BOARD-2      │                │
│                          │  192.168.1.102  │                │
│                          ├─────────────────┤                │
│                          │ - Kiosk UI      │                │
│                          │ - Agent API     │                │
│                          │ - Autodarts     │                │
│                          │ - Local DB      │                │
│                          └─────────────────┘                │
│                                                             │
│  ┌─────────────────┐                                        │
│  │  Staff Tablet   │     Admin Panel: http://192.168.1.100  │
│  │  (any device)   │───► Kiosk URLs:  http://192.168.1.101  │
│  └─────────────────┘                  http://192.168.1.102  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Master-PC Einrichtung

Der Master-PC hostet das zentrale Admin Panel und verwaltet alle Boards.

### 1. Docker installieren

**Windows:**
```powershell
# Docker Desktop herunterladen und installieren
# https://docs.docker.com/desktop/install/windows-install/
```

**Ubuntu:**
```bash
# Docker installieren
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Docker Compose installieren
sudo apt install docker-compose-plugin
```

### 2. Projekt klonen/entpacken
```bash
# In gewünschtes Verzeichnis wechseln
cd /opt
git clone <repository-url> darts-kiosk
cd darts-kiosk
```

### 3. Umgebungsvariablen konfigurieren
```bash
# .env Datei erstellen
cp .env.example .env

# Bearbeiten:
nano .env
```

**Wichtige Einstellungen für MASTER:**
```env
MODE=MASTER
JWT_SECRET=ein-sicherer-geheimer-schluessel-aendern
AGENT_SECRET=agent-kommunikations-geheimnis-aendern
```

### 4. Container starten
```bash
# Development (mit Hot-Reload)
docker-compose up -d app

# Production (mit nginx)
docker-compose --profile production up -d
```

### 5. Zugriff testen
- Admin Panel: `http://192.168.1.100/admin`
- Default Login: `admin` / `admin123`
- Default PIN: `1234`

---

## Board-PC (Agent) Einrichtung

Jeder Board-PC läuft als Agent mit eigenem Kiosk.

### 1. Docker installieren (wie oben)

### 2. Projekt auf Board-PC kopieren
```bash
cd /opt
git clone <repository-url> darts-kiosk
cd darts-kiosk
```

### 3. Agent-Konfiguration
```bash
cp .env.example .env
nano .env
```

**Einstellungen für AGENT:**
```env
MODE=AGENT
BOARD_ID=BOARD-1
JWT_SECRET=gleicher-schluessel-wie-master
AGENT_SECRET=gleicher-agent-secret-wie-master
MASTER_URL=http://192.168.1.100:8001
```

### 4. Container starten
```bash
docker-compose up -d app
```

### 5. Autodarts installieren
Autodarts separat auf dem Board-PC installieren:
- Download: https://autodarts.io
- Installation gemäß Autodarts-Dokumentation
- Dartboard kalibrieren

---

## Netzwerk-Konfiguration

### Feste IP-Adressen (DHCP Reservation)

Im Router konfigurieren:
- Master-PC: `192.168.1.100`
- Board-1:   `192.168.1.101`
- Board-2:   `192.168.1.102`
- usw.

### Firewall-Ports öffnen

| Port | Dienst | Richtung |
|------|--------|----------|
| 80   | HTTP (nginx) | Eingehend |
| 8001 | Backend API | Eingehend |
| 3000 | Frontend Dev | Eingehend (nur Dev) |

**Windows Firewall:**
```powershell
netsh advfirewall firewall add rule name="Darts Kiosk HTTP" dir=in action=allow protocol=tcp localport=80
netsh advfirewall firewall add rule name="Darts Kiosk API" dir=in action=allow protocol=tcp localport=8001
```

**Ubuntu UFW:**
```bash
sudo ufw allow 80/tcp
sudo ufw allow 8001/tcp
```

---

## Kiosk-Modus (Vollbild)

### Windows - Chrome Kiosk

1. **Verknüpfung erstellen:**
   - Rechtsklick Desktop → Neu → Verknüpfung
   - Ziel: `"C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk --disable-pinch --overscroll-history-navigation=0 http://localhost/kiosk`

2. **Autostart einrichten:**
   ```powershell
   # Task Scheduler öffnen
   taskschd.msc
   
   # Neue Aufgabe erstellen:
   # - Trigger: Bei Anmeldung
   # - Aktion: Programm starten (Verknüpfung von oben)
   ```

3. **Automatische Anmeldung:**
   ```powershell
   # Registry bearbeiten
   netplwiz
   # "Benutzer muss Benutzernamen und Kennwort eingeben" deaktivieren
   ```

### Windows - Edge Kiosk (empfohlen)

Windows 10/11 hat einen eingebauten Kiosk-Modus:

1. **Einstellungen → Konten → Familie & andere Benutzer**
2. **Kiosk einrichten → "+" → Zugewiesener Zugriff**
3. Microsoft Edge auswählen, URL eingeben: `http://localhost/kiosk`

### Ubuntu - Chrome Kiosk

1. **Startskript erstellen:**
```bash
sudo nano /home/kiosk/start-kiosk.sh
```

```bash
#!/bin/bash
# Bildschirmschoner deaktivieren
xset s off
xset -dpms
xset s noblank

# Warten auf Netzwerk
sleep 10

# Chrome im Kiosk-Modus starten
/usr/bin/chromium-browser \
    --kiosk \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-restore-session-state \
    --noerrdialogs \
    --disable-translate \
    --no-first-run \
    --fast \
    --fast-start \
    --disable-features=TranslateUI \
    --disk-cache-dir=/dev/null \
    http://localhost/kiosk
```

```bash
chmod +x /home/kiosk/start-kiosk.sh
```

2. **Autostart einrichten:**
```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/kiosk.desktop
```

```ini
[Desktop Entry]
Type=Application
Name=Darts Kiosk
Exec=/home/kiosk/start-kiosk.sh
X-GNOME-Autostart-enabled=true
```

3. **Automatische Anmeldung (Ubuntu):**
```bash
sudo nano /etc/gdm3/custom.conf
```

```ini
[daemon]
AutomaticLoginEnable=True
AutomaticLogin=kiosk
```

### Watchdog - Auto-Restart bei Crash

**Windows (Task Scheduler):**
```powershell
# Neuer Task:
# - Trigger: Bei Ereignis → System → Fehler
# - Aktion: Neustart des Kiosk-Tasks
```

**Ubuntu (Systemd Service):**
```bash
sudo nano /etc/systemd/system/darts-kiosk.service
```

```ini
[Unit]
Description=Darts Kiosk Browser
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=kiosk
ExecStart=/home/kiosk/start-kiosk.sh
Restart=always
RestartSec=10

[Install]
WantedBy=graphical.target
```

```bash
sudo systemctl enable darts-kiosk
sudo systemctl start darts-kiosk
```

---

## Board-Registrierung

### Im Admin Panel

1. **Anmelden:** `http://MASTER-IP/admin`
2. **Boards → Neues Board**
3. **Konfiguration:**
   - Board ID: `BOARD-1` (muss mit Agent-Config übereinstimmen)
   - Name: `Dartboard Ecke Links`
   - Standort: `Erdgeschoss`
   - Agent API URL: `http://192.168.1.101:8001` (IP des Board-PC)

### Agent Secret

Das `AGENT_SECRET` muss auf Master und allen Agents identisch sein.
Es wird für die sichere Kommunikation zwischen Master und Agents verwendet.

---

## Troubleshooting

### Container startet nicht
```bash
# Logs prüfen
docker-compose logs -f app

# Container neu starten
docker-compose restart app
```

### Kiosk zeigt "Gesperrt"
- Normal! Das Board muss erst im Admin Panel freigeschaltet werden.

### Autodarts-Automation funktioniert nicht
```bash
# Mock-Modus aktivieren für Tests
echo "AUTODARTS_MOCK=true" >> .env
docker-compose restart app
```

### Board im Admin Panel "Offline"
- Netzwerkverbindung prüfen
- Agent-Container auf Board-PC prüfen
- Firewall-Regeln prüfen

### Datenbank zurücksetzen
```bash
# Alle Daten löschen (Vorsicht!)
docker-compose down -v
docker-compose up -d
```

### Logs einsehen
```bash
# Backend-Logs
docker-compose logs -f app

# Alle Container
docker-compose logs -f
```

---

## Kontakt & Support

Bei Problemen oder Fragen:
- GitHub Issues: [Link]
- Email: support@example.com
