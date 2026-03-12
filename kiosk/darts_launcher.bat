@echo off
REM ============================================================================
REM  DARTS KIOSK — Launcher / Supervisor
REM  Starts and monitors all kiosk services. Runs as Windows shell replacement.
REM  This script must NEVER exit (otherwise Windows logs out the kiosk user).
REM ============================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Darts Kiosk — Launcher

REM === Load Configuration ===
set "INSTALL_DIR=%~dp0"
if "!INSTALL_DIR:~-1!"=="\" set "INSTALL_DIR=!INSTALL_DIR:~0,-1!"

if exist "!INSTALL_DIR!\kiosk_config.bat" (
    call "!INSTALL_DIR!\kiosk_config.bat"
)

REM === Defaults (if config missing) ===
if not defined BOARD_ID set "BOARD_ID=BOARD-1"
if not defined BACKEND_PORT set "BACKEND_PORT=8001"

set "LOG_DIR=!INSTALL_DIR!\logs"
set "DATA_DIR=!INSTALL_DIR!\data"
set "VENV_DIR=!INSTALL_DIR!\.venv"
set "LAUNCHER_LOG=!LOG_DIR!\launcher.log"
set "BACKEND_LOG=!LOG_DIR!\backend.log"
set "HEALTH_URL=http://localhost:!BACKEND_PORT!/api/health"
set "KIOSK_URL=http://localhost:!BACKEND_PORT!/kiosk/!BOARD_ID!"
set "CHECK_INTERVAL=10"
set "RESTART_DELAY=5"
set "MAX_BACKEND_RESTARTS=10"
set "BACKEND_RESTART_COUNT=0"
set "MAX_CHROME_RESTARTS=10"
set "CHROME_RESTART_COUNT=0"

REM === Detect Chrome ===
if not defined CHROME_PATH (
    for %%G in (
        "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
        "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
        "%LocalAppData%\Google\Chrome\Application\chrome.exe"
    ) do (
        if exist "%%~G" (
            if not defined CHROME_PATH set "CHROME_PATH=%%~G"
        )
    )
)

REM === Create directories ===
if not exist "!LOG_DIR!" mkdir "!LOG_DIR!"
if not exist "!DATA_DIR!\db" mkdir "!DATA_DIR!\db"
if not exist "!DATA_DIR!\kiosk_ui_profile" mkdir "!DATA_DIR!\kiosk_ui_profile"

REM === Logging helper ===
call :log "========================================"
call :log "LAUNCHER START"
call :log "  Install:  !INSTALL_DIR!"
call :log "  Board:    !BOARD_ID!"
call :log "  Port:     !BACKEND_PORT!"
call :log "  Chrome:   !CHROME_PATH!"
call :log "========================================"

REM === Set working directory ===
cd /d "!INSTALL_DIR!"

REM === Activate Virtual Environment ===
if exist "!VENV_DIR!\Scripts\activate.bat" (
    call "!VENV_DIR!\Scripts\activate.bat"
    call :log "Python venv aktiviert"
) else (
    call :log "WARN: keine .venv gefunden — verwende System-Python"
)

REM ============================================================================
REM  STARTUP SEQUENCE
REM ============================================================================

REM --- 1. Start Backend ---
call :log "Backend starten..."
call :start_backend

REM --- 2. Wait for Backend Health ---
call :log "Warte auf Backend-Health..."
set "BACKEND_READY=0"
for /L %%i in (1,1,30) do (
    if !BACKEND_READY!==0 (
        curl -sf "!HEALTH_URL!" >nul 2>&1
        if !ERRORLEVEL!==0 (
            set "BACKEND_READY=1"
            call :log "Backend bereit (Versuch %%i)"
        ) else (
            timeout /t 2 /nobreak >nul
        )
    )
)

if !BACKEND_READY!==0 (
    call :log "WARNUNG: Backend nicht erreichbar nach 60s — starte Chrome trotzdem"
)

REM --- 3. Start Chrome Kiosk ---
call :log "Chrome Kiosk starten..."
call :start_chrome

REM --- 4. Start Credits Overlay (optional) ---
if exist "!INSTALL_DIR!\credits_overlay.py" (
    start "Darts Overlay" /MIN pythonw "!INSTALL_DIR!\credits_overlay.py" --board-id "!BOARD_ID!" --api "http://localhost:!BACKEND_PORT!"
    call :log "Credits-Overlay gestartet"
)

call :log "Alle Dienste gestartet — Monitoring aktiv"

REM ============================================================================
REM  MONITOR LOOP (runs forever)
REM ============================================================================
:monitor_loop
    timeout /t !CHECK_INTERVAL! /nobreak >nul

    REM --- Check Backend ---
    curl -sf "!HEALTH_URL!" >nul 2>&1
    if !ERRORLEVEL! NEQ 0 (
        set /a "BACKEND_RESTART_COUNT+=1"
        call :log "BACKEND_CRASH erkannt (Restart !BACKEND_RESTART_COUNT!/!MAX_BACKEND_RESTARTS!)"

        if !BACKEND_RESTART_COUNT! GEQ !MAX_BACKEND_RESTARTS! (
            call :log "KRITISCH: Max Backend-Restarts erreicht — warte 60s dann Reset"
            timeout /t 60 /nobreak >nul
            set "BACKEND_RESTART_COUNT=0"
        )

        timeout /t !RESTART_DELAY! /nobreak >nul
        call :start_backend
        timeout /t 5 /nobreak >nul
    ) else (
        REM Backend is healthy — reset restart counter
        set "BACKEND_RESTART_COUNT=0"
    )

    REM --- Check Chrome ---
    tasklist /FI "IMAGENAME eq chrome.exe" 2>nul | find /I "chrome.exe" >nul
    if !ERRORLEVEL! NEQ 0 (
        set /a "CHROME_RESTART_COUNT+=1"
        call :log "CHROME_CRASH erkannt (Restart !CHROME_RESTART_COUNT!/!MAX_CHROME_RESTARTS!)"

        if !CHROME_RESTART_COUNT! GEQ !MAX_CHROME_RESTARTS! (
            call :log "KRITISCH: Max Chrome-Restarts erreicht — warte 60s dann Reset"
            timeout /t 60 /nobreak >nul
            set "CHROME_RESTART_COUNT=0"
        )

        timeout /t !RESTART_DELAY! /nobreak >nul
        call :start_chrome
    ) else (
        set "CHROME_RESTART_COUNT=0"
    )

goto :monitor_loop

REM ============================================================================
REM  HELPER FUNCTIONS
REM ============================================================================

:start_backend
    REM Kill existing backend
    taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
    timeout /t 1 /nobreak >nul
    REM Start backend via run_backend.py
    if exist "!INSTALL_DIR!\run_backend.py" (
        start "Darts Backend" /MIN python "!INSTALL_DIR!\run_backend.py"
    ) else if exist "!INSTALL_DIR!\_run_backend.bat" (
        start "Darts Backend" /MIN "!INSTALL_DIR!\_run_backend.bat"
    )
    call :log "Backend (re)gestartet"
    goto :eof

:start_chrome
    REM Kill existing kiosk chrome (but NOT the Autodarts observer chrome)
    REM We identify kiosk chrome by window title containing the kiosk URL port
    taskkill /F /FI "WINDOWTITLE eq DartsKiosk*" >nul 2>&1
    timeout /t 1 /nobreak >nul

    if defined CHROME_PATH (
        start "" "!CHROME_PATH!" ^
            --kiosk ^
            --user-data-dir="!DATA_DIR!\kiosk_ui_profile" ^
            --no-first-run ^
            --no-default-browser-check ^
            --disable-translate ^
            --disable-infobars ^
            --disable-session-crashed-bubble ^
            --disable-features=TranslateUI ^
            --autoplay-policy=no-user-gesture-required ^
            --app-name=DartsKiosk ^
            "!KIOSK_URL!"
        call :log "Chrome Kiosk gestartet: !KIOSK_URL!"
    ) else (
        call :log "FEHLER: Chrome nicht gefunden — kann Kiosk-UI nicht starten"
    )
    goto :eof

:log
    echo [%date% %time%] %~1 >> "!LAUNCHER_LOG!" 2>nul
    goto :eof
