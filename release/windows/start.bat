@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Darts Kiosk - Gestartet
cd /d "%~dp0"
echo.
echo ================================================================
echo   DARTS KIOSK - Starten (Production)
echo ================================================================
echo.

REM === Configuration ===
set "BOARD_ID=BOARD-1"
set "BACKEND_PORT=8001"

REM === Pre-flight: .env ===
if not exist "backend\.env" (
    if exist "backend\.env.example" (
        copy "backend\.env.example" "backend\.env" >nul
        echo [INFO] backend\.env aus Vorlage erstellt
    ) else (
        echo [FAIL] Kein backend\.env gefunden!
        echo        Bitte zuerst setup_windows.bat ausfuehren.
        pause
        exit /b 1
    )
)

REM === Pre-flight: venv ===
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    echo [OK] Python .venv aktiviert
) else (
    echo [WARN] Keine .venv gefunden - verwende System-Python
)

REM === Pre-flight: greenlet ===
python -c "import greenlet" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] greenlet kann nicht geladen werden!
    echo        VC++ Redistributable x64 fehlt: https://aka.ms/vs/17/release/vc_redist.x64.exe
    pause
    exit /b 1
)

REM === Pre-flight: required files ===
if not exist "_run_backend.bat" (
    echo [FAIL] _run_backend.bat nicht gefunden!
    pause
    exit /b 1
)
if not exist "run_backend.py" (
    echo [FAIL] run_backend.py nicht gefunden!
    pause
    exit /b 1
)

REM === Create directories ===
if not exist "logs" mkdir "logs"
if not exist "data\db" mkdir "data\db"
if not exist "data\downloads" mkdir "data\downloads"
if not exist "data\app_backups" mkdir "data\app_backups"
if not exist "data\kiosk_chrome_profile" mkdir "data\kiosk_chrome_profile"

REM === Kill old processes ===
echo [1/4] Alte Prozesse beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Overlay" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DartsKiosk*" >nul 2>&1
timeout /t 2 /nobreak >nul

REM === Detect LAN IP ===
echo [2/4] Netzwerk-IP erkennen...
set "LAN_IP="
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
    if not defined LAN_IP (
        for /f "tokens=1" %%b in ("%%a") do set "LAN_IP=%%b"
    )
)
if not defined LAN_IP (
    echo   [WARN] Keine LAN-IP gefunden, verwende localhost
    set "LAN_IP=127.0.0.1"
) else (
    echo   [OK]   LAN-IP: !LAN_IP!
)

REM === Detect Google Chrome ===
set "CHROME_PATH="
for %%G in (
    "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    "%LocalAppData%\Google\Chrome\Application\chrome.exe"
) do (
    if exist "%%~G" (
        if not defined CHROME_PATH set "CHROME_PATH=%%~G"
    )
)
if defined CHROME_PATH (
    echo   [OK]   Chrome: !CHROME_PATH!
) else (
    echo   [WARN] Chrome nicht gefunden
)

REM === Start Backend ===
echo [3/4] Backend starten (Port !BACKEND_PORT!, 0.0.0.0)...
start "Darts Backend" /MIN "%~dp0_run_backend.bat"
echo   [OK] Backend gestartet

echo        Warte auf Backend...
timeout /t 5 /nobreak >nul

REM Health check with retry
set "BACKEND_READY=0"
for /L %%i in (1,1,6) do (
    if !BACKEND_READY!==0 (
        curl -sf "http://localhost:!BACKEND_PORT!/api/health" >nul 2>&1
        if !ERRORLEVEL!==0 (
            set "BACKEND_READY=1"
            echo   [OK]   Backend laeuft!
        ) else (
            timeout /t 3 /nobreak >nul
        )
    )
)
if !BACKEND_READY!==0 (
    echo   [WARN] Backend nicht erreichbar. Pruefe logs\backend.log
)

REM === Launch Kiosk + Overlay ===
echo [4/4] Kiosk-Modus starten...

REM Start Credits Overlay
if exist "%~dp0credits_overlay.py" (
    start "Darts Overlay" /MIN pythonw "%~dp0credits_overlay.py" --board-id "!BOARD_ID!" --api "http://localhost:!BACKEND_PORT!"
    echo   [OK] Credits-Overlay gestartet
) else (
    echo   [WARN] credits_overlay.py nicht gefunden - Overlay uebersprungen
)

REM Launch Kiosk in Chrome kiosk mode
if defined CHROME_PATH (
    echo   [OK] Starte Kiosk im Chrome-Vollbild-Modus...
    start "" "!CHROME_PATH!" --kiosk --user-data-dir="%~dp0data\kiosk_chrome_profile" --no-first-run --no-default-browser-check --disable-translate --disable-infobars --autoplay-policy=no-user-gesture-required "http://localhost:!BACKEND_PORT!/kiosk/!BOARD_ID!"
) else (
    start "" "http://localhost:!BACKEND_PORT!/kiosk/!BOARD_ID!"
)

echo.
echo ================================================================
echo.
echo   Darts Kiosk laeuft!
echo   Board: !BOARD_ID!
echo.
echo   === Zugriff (alle Geraete im LAN) ===
echo   Kiosk:        http://!LAN_IP!:!BACKEND_PORT!/kiosk/!BOARD_ID!
echo   Admin-Panel:  http://!LAN_IP!:!BACKEND_PORT!/admin
echo   Backend-API:  http://!LAN_IP!:!BACKEND_PORT!/api/health
echo.
echo   === Lokal ===
echo   Kiosk:        http://localhost:!BACKEND_PORT!/kiosk/!BOARD_ID!
echo   Admin-Panel:  http://localhost:!BACKEND_PORT!/admin
echo.
echo   Zum Beenden: stop.bat oder Taste druecken
echo.
echo ================================================================
echo.

echo Druecken Sie eine Taste zum Beenden aller Dienste...
pause >nul

echo Alle Dienste werden beendet...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Overlay" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DartsKiosk*" >nul 2>&1
echo Alle Dienste beendet.
endlocal
