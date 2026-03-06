@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Gestartet

:: Resolve to the directory where this .bat lives (project root)
cd /d %~dp0

echo.
echo ================================================================
echo   DARTS KIOSK - Starten
echo ================================================================
echo.

:: Check setup was done
if not exist "backend\.env" (
    echo [FAIL] Setup nicht durchgefuehrt!
    echo        Bitte zuerst setup_windows.bat ausfuehren.
    pause
    exit /b 1
)

:: Create dirs
if not exist "logs" mkdir logs
if not exist "data\db" mkdir data\db

:: Kill any existing instances
echo [1/4] Alte Prozesse beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Frontend" >nul 2>&1
timeout /t 2 /nobreak >nul

:: Detect LAN IP address
echo [2/4] Netzwerk-IP erkennen...
set "LAN_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    for /f "tokens=1" %%b in ("%%a") do (
        if not defined LAN_IP (
            set "LAN_IP=%%b"
        )
    )
)

if not defined LAN_IP (
    echo   [WARN] Keine LAN-IP gefunden, verwende localhost
    set "LAN_IP=127.0.0.1"
) else (
    echo   [OK]   LAN-IP erkannt: %LAN_IP%
)

:: Update frontend .env with detected LAN IP for API calls
echo REACT_APP_BACKEND_URL=http://%LAN_IP%:8001> frontend\.env
echo.>> frontend\.env

:: Start Backend (from project root, uvicorn targets backend/server.py)
echo [3/4] Backend starten (Port 8001, 0.0.0.0)...
start "Darts Backend" /MIN cmd /c "cd /d %~dp0 && python -m uvicorn backend.server:app --host 0.0.0.0 --port 8001 --reload --app-dir . > logs\backend.log 2>&1"
echo   [OK] Backend gestartet (Log: logs\backend.log)

:: Wait for backend
echo        Warte auf Backend...
timeout /t 5 /nobreak >nul

:: Quick health check
curl -sf http://localhost:8001/api/health >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Backend antwortet noch nicht, warte weitere 10s...
    timeout /t 10 /nobreak >nul
    curl -sf http://localhost:8001/api/health >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo   [WARN] Backend nicht erreichbar. Pruefe logs\backend.log
    ) else (
        echo   [OK]   Backend laeuft!
    )
) else (
    echo   [OK]   Backend laeuft!
)

:: Start Frontend (from frontend dir, bind to 0.0.0.0 for LAN access)
echo [4/4] Frontend starten (Port 3000, 0.0.0.0)...
start "Darts Frontend" /MIN cmd /c "cd /d %~dp0frontend && set PORT=3000 && set HOST=0.0.0.0 && set BROWSER=none && call yarn start > ..\logs\frontend.log 2>&1"
echo   [OK] Frontend gestartet (Log: logs\frontend.log)

:: Wait for frontend compile
echo        Warte auf Frontend-Kompilierung...
timeout /t 15 /nobreak >nul

echo.
echo ================================================================
echo.
echo   Darts Kiosk laeuft!
echo.
echo   === Zugriff von DIESEM PC ===
echo   Admin-Panel:  http://localhost:3000/admin
echo   Kiosk:        http://localhost:3000/kiosk/BOARD-1
echo   Setup-Wizard: http://localhost:3000/setup
echo   Backend-API:  http://localhost:8001/api/health
echo.
echo   === Zugriff von ANDEREN Geraeten (Handy, Tablet, etc.) ===
echo   Admin-Panel:  http://%LAN_IP%:3000/admin
echo   Kiosk:        http://%LAN_IP%:3000/kiosk/BOARD-1
echo   Backend-API:  http://%LAN_IP%:8001/api/health
echo.
echo   Beim ersten Start: Setup-Wizard oeffnen
echo   und Admin-Passwort, Staff-PIN und Branding einrichten.
echo.
echo   Logs:
echo     Backend:  logs\backend.log
echo     Frontend: logs\frontend.log
echo.
echo   Zum Beenden: stop.bat ausfuehren
echo                oder dieses Fenster schliessen
echo.
echo ================================================================
echo.

:: Open browser
timeout /t 3 /nobreak >nul
start "" http://localhost:3000/setup

:: Keep window open
echo Druecken Sie eine Taste zum Beenden aller Dienste...
pause >nul

:: Cleanup on exit
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Frontend" >nul 2>&1
echo Alle Dienste beendet.
