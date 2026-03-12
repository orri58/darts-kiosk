@echo off
REM ============================================================================
REM  DARTS KIOSK - Launcher / Supervisor v3.0.2
REM  Starts and monitors all kiosk services.
REM  Primary startup: via Scheduled Task "DartsKioskLauncher" (at logon)
REM  Fallback: via kiosk_shell.vbs (direct start)
REM  This script must NEVER exit while kiosk is running.
REM ============================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Darts Kiosk Launcher

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
set "BOOT_LOG=!LOG_DIR!\kiosk_boot.log"
set "BACKEND_LOG=!LOG_DIR!\backend.log"
set "LAUNCHER_LOG=!LOG_DIR!\launcher.log"
set "HEALTH_URL=http://127.0.0.1:!BACKEND_PORT!/api/health"
set "KIOSK_URL=http://127.0.0.1:!BACKEND_PORT!/kiosk/!BOARD_ID!"
set "CHECK_INTERVAL=10"
set "RESTART_DELAY=5"
set "MAX_BACKEND_RESTARTS=10"
set "BACKEND_RESTART_COUNT=0"
set "MAX_CHROME_RESTARTS=10"
set "CHROME_RESTART_COUNT=0"

REM === Detect Chrome (if not in config) ===
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

REM === Set working directory ===
cd /d "!INSTALL_DIR!"

REM === Boot logging ===
call :bootlog "========================================"
call :bootlog "[BOOT] launcher task started"
call :bootlog "[BOOT]   Install:  !INSTALL_DIR!"
call :bootlog "[BOOT]   Board:    !BOARD_ID!"
call :bootlog "[BOOT]   Port:     !BACKEND_PORT!"
call :bootlog "[BOOT]   Chrome:   !CHROME_PATH!"
call :bootlog "[BOOT]   Venv:     !VENV_DIR!"

call :log "========================================"
call :log "LAUNCHER START"
call :log "  Install:  !INSTALL_DIR!"
call :log "  Board:    !BOARD_ID!"
call :log "  Port:     !BACKEND_PORT!"
call :log "  Chrome:   !CHROME_PATH!"
call :log "========================================"

REM === Activate Virtual Environment ===
if exist "!VENV_DIR!\Scripts\activate.bat" (
    call "!VENV_DIR!\Scripts\activate.bat"
    call :log "Python venv aktiviert"
    call :bootlog "[BOOT] python venv activated"
) else (
    call :log "WARN: keine .venv gefunden"
    call :bootlog "[BOOT] WARNING: no .venv found - using system python"
    REM Try adding Python to PATH from config
    if defined PYTHON_PATH (
        for %%P in ("!PYTHON_PATH!") do set "PYTHON_DIR=%%~dpP"
        set "PATH=!PYTHON_DIR!;!PATH!"
        call :bootlog "[BOOT] added PYTHON_PATH to PATH: !PYTHON_DIR!"
    )
)

REM ============================================================================
REM  STARTUP SEQUENCE
REM ============================================================================

REM --- 1. Start Backend ---
call :bootlog "[BOOT] starting backend..."
call :log "Backend starten..."
call :start_backend

REM --- 2. Wait for Backend Health ---
call :bootlog "[BOOT] waiting for backend health !HEALTH_URL!"
call :log "Warte auf Backend-Health..."
set "BACKEND_READY=0"
for /L %%i in (1,1,30) do (
    if !BACKEND_READY!==0 (
        curl -sf "!HEALTH_URL!" >nul 2>&1
        if !ERRORLEVEL!==0 (
            set "BACKEND_READY=1"
            call :log "Backend bereit (Versuch %%i)"
            call :bootlog "[BOOT] backend ready (attempt %%i)"
        ) else (
            timeout /t 2 /nobreak >nul
        )
    )
)

if !BACKEND_READY!==0 (
    call :log "WARNUNG: Backend nicht erreichbar nach 60s"
    call :bootlog "[BOOT] WARNING: backend NOT ready after 60s - starting chrome anyway"
) else (
    call :bootlog "[BOOT] backend healthy"
)

REM --- 3. Start Chrome Kiosk ---
call :bootlog "[BOOT] launching chrome kiosk ui"
call :log "Chrome Kiosk starten..."
call :start_chrome

REM --- 4. Start Credits Overlay (optional) ---
if exist "!INSTALL_DIR!\credits_overlay.py" (
    start "Darts Overlay" /MIN python "!INSTALL_DIR!\credits_overlay.py" --board-id "!BOARD_ID!" --api "http://127.0.0.1:!BACKEND_PORT!"
    call :log "Credits-Overlay gestartet"
)

call :bootlog "[BOOT] all services started - entering monitor loop"
call :log "Alle Dienste gestartet - Monitoring aktiv"

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
        call :bootlog "[BOOT] BACKEND_CRASH detected (restart !BACKEND_RESTART_COUNT!)"

        if !BACKEND_RESTART_COUNT! GEQ !MAX_BACKEND_RESTARTS! (
            call :log "KRITISCH: Max Backend-Restarts erreicht - warte 60s dann Reset"
            timeout /t 60 /nobreak >nul
            set "BACKEND_RESTART_COUNT=0"
        )

        timeout /t !RESTART_DELAY! /nobreak >nul
        call :start_backend
        timeout /t 5 /nobreak >nul
    ) else (
        set "BACKEND_RESTART_COUNT=0"
    )

    REM --- Check Chrome ---
    tasklist /FI "IMAGENAME eq chrome.exe" 2>nul | find /I "chrome.exe" >nul
    if !ERRORLEVEL! NEQ 0 (
        set /a "CHROME_RESTART_COUNT+=1"
        call :log "CHROME_CRASH erkannt (Restart !CHROME_RESTART_COUNT!/!MAX_CHROME_RESTARTS!)"
        call :bootlog "[BOOT] CHROME_CRASH detected (restart !CHROME_RESTART_COUNT!)"

        if !CHROME_RESTART_COUNT! GEQ !MAX_CHROME_RESTARTS! (
            call :log "KRITISCH: Max Chrome-Restarts erreicht - warte 60s dann Reset"
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
    REM Kill existing kiosk chrome
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
        call :log "FEHLER: Chrome nicht gefunden"
    )
    goto :eof

:log
    echo [%date% %time%] %~1 >> "!LAUNCHER_LOG!" 2>nul
    goto :eof

:bootlog
    echo [%date% %time%] %~1 >> "!BOOT_LOG!" 2>nul
    goto :eof
