@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0"

REM === Read version from VERSION file ===
set "APP_VERSION=unknown"
if exist "VERSION" (
    set /p APP_VERSION=<VERSION
)

title Darts Kiosk v!APP_VERSION! - Gestartet
echo.
echo ================================================================
echo   DARTS KIOSK v!APP_VERSION! - Production Start
echo ================================================================
echo.

REM === Configuration ===
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

call :load_env_value BOARD_ID BOARD_ID
if not defined BOARD_ID set "BOARD_ID=BOARD-1"
call :load_env_value BACKEND_PORT BACKEND_PORT

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
if not exist "data\chrome_profile\!BOARD_ID!" mkdir "data\chrome_profile\!BOARD_ID!"
if not exist "data\kiosk_ui_profile" mkdir "data\kiosk_ui_profile"

REM === Kill old processes ===
echo [1/5] Alte Prozesse beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Overlay" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Agent" >nul 2>&1
call :kill_chrome_profile "data\kiosk_ui_profile"
call :kill_chrome_profile "data\chrome_profile\!BOARD_ID!"
timeout /t 2 /nobreak >nul

REM === Detect LAN IP ===
echo [2/5] Netzwerk-IP erkennen...
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
echo [3/5] Backend starten (Port !BACKEND_PORT!, 0.0.0.0)...
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

REM === Start Agent ===
echo [4/5] Windows Agent starten...
if exist "agent\start_agent.bat" (
    start "Darts Agent" /MIN cmd /c "cd /d "%~dp0agent" && start_agent.bat"
    echo   [OK] Agent gestartet
) else (
    echo   [INFO] Kein Agent vorhanden - uebersprungen
)

REM === Launch Kiosk + Overlay ===
echo [5/5] Kiosk-Modus starten...

REM Start Credits Overlay
if exist "%~dp0credits_overlay.py" (
    start "Darts Overlay" /MIN pythonw "%~dp0credits_overlay.py" --board-id "!BOARD_ID!" --api "http://localhost:!BACKEND_PORT!"
    echo   [OK] Credits-Overlay gestartet
) else (
    echo   [WARN] credits_overlay.py nicht gefunden - Overlay uebersprungen
)

REM Launch Kiosk UI in Chrome kiosk mode
if defined CHROME_PATH (
    echo   [OK] Starte Kiosk-UI im Chrome-Vollbild-Modus...
    start "" "!CHROME_PATH!" --kiosk --user-data-dir="%~dp0data\kiosk_ui_profile" --no-first-run --no-default-browser-check --disable-translate --disable-infobars --autoplay-policy=no-user-gesture-required "http://localhost:!BACKEND_PORT!/kiosk/!BOARD_ID!"
) else (
    start "" "http://localhost:!BACKEND_PORT!/kiosk/!BOARD_ID!"
)

echo.
echo ================================================================
echo.
echo   Darts Kiosk v!APP_VERSION! laeuft!
echo   Board: !BOARD_ID!
echo.
echo   === Lokaler Zugriff ===
echo   Kiosk:              http://localhost:!BACKEND_PORT!/kiosk/!BOARD_ID!
echo   Admin-Panel:        http://localhost:!BACKEND_PORT!/admin
echo   Health:             http://localhost:!BACKEND_PORT!/api/health
echo.
echo   === LAN-Zugriff (alle Geraete im Netzwerk) ===
echo   Kiosk:              http://!LAN_IP!:!BACKEND_PORT!/kiosk/!BOARD_ID!
echo   Admin-Panel:        http://!LAN_IP!:!BACKEND_PORT!/admin
echo.
echo   Hinweis: Lokales Spiel haengt nicht von externer Erreichbarkeit ab.
echo            Optionale zentrale/Portal-Surfaces sind nur relevant,
echo            wenn sie bewusst separat konfiguriert wurden.
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
taskkill /F /FI "WINDOWTITLE eq Darts Agent" >nul 2>&1
call :kill_chrome_profile "data\kiosk_ui_profile"
call :kill_chrome_profile "data\chrome_profile\!BOARD_ID!"
echo Alle Dienste beendet.
endlocal
goto :eof

:load_env_value
setlocal enabledelayedexpansion
set "_lookup=%~1"
set "_value="
for /f "tokens=1,* delims==" %%a in ('findstr /R /B /C:"%~1=" "backend\.env" 2^>nul') do (
    if /I "%%a"=="%~1" set "_value=%%b"
)
for /f "tokens=* delims= " %%a in ("!_value!") do set "_value=%%a"
endlocal & if not "%_value%"=="" set "%~2=%_value%"
goto :eof

:kill_chrome_profile
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'chrome.exe' -and $_.CommandLine -like '*%~1*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
goto :eof
