@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Gestartet
cd /d "%~dp0"
echo.
echo ================================================================
echo   DARTS KIOSK - Starten
echo ================================================================
echo.

REM === Pre-flight ===
if not exist "backend\.env" (
    echo [FAIL] Setup nicht durchgefuehrt!
    echo        Bitte zuerst setup_windows.bat ausfuehren.
    pause
    exit /b 1
)

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    echo [OK] Python .venv aktiviert
) else (
    echo [WARN] Keine .venv gefunden - verwende System-Python
)

REM Greenlet sanity check
python -c "import greenlet" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] greenlet kann nicht geladen werden!
    echo        Moegliche Ursache: VC++ Redistributable x64 fehlt
    echo        Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo        Danach: setup_windows.bat erneut ausfuehren
    pause
    exit /b 1
)

if not exist "logs" mkdir logs
if not exist "data\db" mkdir data\db

REM === Kill old ===
echo [1/4] Alte Prozesse beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Frontend" >nul 2>&1
timeout /t 2 /nobreak >nul

REM === Detect LAN IP ===
echo [2/4] Netzwerk-IP erkennen...
set LAN_IP=
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    if not defined LAN_IP (
        for /f "tokens=1" %%b in ("%%a") do set LAN_IP=%%b
    )
)
if not defined LAN_IP (
    echo   [WARN] Keine LAN-IP gefunden, verwende localhost
    set LAN_IP=127.0.0.1
) else (
    echo   [OK]   LAN-IP erkannt: %LAN_IP%
)

REM Write frontend .env with LAN IP (no trailing spaces!)
>frontend\.env echo REACT_APP_BACKEND_URL=http://%LAN_IP%:8001

REM === Start Backend ===
echo [3/4] Backend starten (Port 8001, 0.0.0.0)...
start "Darts Backend" /MIN cmd /c ""%~dp0_run_backend.bat""
echo   [OK] Backend gestartet (Log: logs\backend.log)

echo        Warte auf Backend...
timeout /t 5 /nobreak >nul

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

REM === Start Frontend ===
echo [4/4] Frontend starten (Port 3000, 0.0.0.0)...
start "Darts Frontend" /MIN cmd /c ""%~dp0_run_frontend.bat""
echo   [OK] Frontend gestartet (Log: logs\frontend.log)

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
echo   Logs: logs\backend.log  /  logs\frontend.log
echo   Zum Beenden: stop.bat oder Taste druecken
echo.
echo ================================================================
echo.

timeout /t 3 /nobreak >nul
start "" http://localhost:3000/setup

echo Druecken Sie eine Taste zum Beenden aller Dienste...
pause >nul

taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Frontend" >nul 2>&1
echo Alle Dienste beendet.
