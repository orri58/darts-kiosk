@echo off
REM ============================================================================
REM  DARTS KIOSK — Maintenance Tool
REM  Provides admin access to manage the kiosk system.
REM  Requires the kiosk maintenance password.
REM ============================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Darts Kiosk — Maintenance

REM === Load Configuration ===
set "INSTALL_DIR=%~dp0"
if "!INSTALL_DIR:~-1!"=="\" set "INSTALL_DIR=!INSTALL_DIR:~0,-1!"

if exist "!INSTALL_DIR!\kiosk_config.bat" (
    call "!INSTALL_DIR!\kiosk_config.bat"
)

REM === Defaults ===
if not defined BOARD_ID set "BOARD_ID=BOARD-1"
if not defined BACKEND_PORT set "BACKEND_PORT=8001"

echo.
echo ================================================================
echo   DARTS KIOSK — MAINTENANCE TOOL
echo ================================================================
echo.

REM ============================================================================
REM  AUTHENTICATION
REM ============================================================================

REM Check if running as admin — if so, skip password
net session >nul 2>&1
if !ERRORLEVEL!==0 (
    echo   [OK] Administrator-Rechte erkannt — Zugang gewaehrt
    goto :menu
)

REM Otherwise require maintenance password
set "KEY_FILE=!INSTALL_DIR!\data\.maintenance_key"
if not exist "!KEY_FILE!" (
    echo   [WARN] Keine Passwort-Datei gefunden — erlaube Zugang
    goto :menu
)

set /f "STORED_HASH=" < "!KEY_FILE!" 2>nul
set /p "INPUT_PASS=Maintenance-Passwort: "
if "!INPUT_PASS!"=="" (
    echo   [FEHLER] Kein Passwort eingegeben.
    timeout /t 3
    exit /b 1
)

REM Hash input and compare
for /f "tokens=*" %%h in ('powershell -NoProfile -Command "[BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes('!INPUT_PASS!'))).Replace('-','')"') do set "INPUT_HASH=%%h"

set /p STORED_HASH=< "!KEY_FILE!"
set "STORED_HASH=!STORED_HASH: =!"

if /i not "!INPUT_HASH!"=="!STORED_HASH!" (
    echo.
    echo   [FEHLER] Falsches Passwort!
    timeout /t 3
    exit /b 1
)

echo   [OK] Passwort korrekt — Zugang gewaehrt
echo.

REM ============================================================================
REM  MAIN MENU
REM ============================================================================
:menu
echo.
echo ================================================================
echo   Maintenance-Optionen:
echo ================================================================
echo.
echo   [1] Explorer temporaer starten (Desktop anzeigen)
echo   [2] Kiosk-Modus neu starten
echo   [3] Alle Kiosk-Dienste stoppen
echo   [4] Backend-Status pruefen
echo   [5] Backend-Logs anzeigen
echo   [6] Launcher-Logs anzeigen
echo   [7] System-Update durchfuehren
echo   [8] Kiosk vollstaendig deinstallieren
echo   [9] System neu starten
echo   [0] Beenden
echo.
set /p "CHOICE=Auswahl [0-9]: "

if "!CHOICE!"=="1" goto :start_explorer
if "!CHOICE!"=="2" goto :restart_kiosk
if "!CHOICE!"=="3" goto :stop_all
if "!CHOICE!"=="4" goto :check_status
if "!CHOICE!"=="5" goto :show_backend_logs
if "!CHOICE!"=="6" goto :show_launcher_logs
if "!CHOICE!"=="7" goto :update
if "!CHOICE!"=="8" goto :uninstall
if "!CHOICE!"=="9" goto :reboot
if "!CHOICE!"=="0" goto :exit_tool
goto :menu

REM ============================================================================
REM  OPTION 1 — Start Explorer Temporarily
REM ============================================================================
:start_explorer
echo.
echo   Explorer wird gestartet...
echo   HINWEIS: Explorer laeuft nur bis zum naechsten Neustart.
echo            Beim naechsten Login startet wieder der Kiosk-Modus.
echo.
start explorer.exe
echo   [OK] Explorer gestartet
goto :menu

REM ============================================================================
REM  OPTION 2 — Restart Kiosk
REM ============================================================================
:restart_kiosk
echo.
echo   Kiosk-Dienste werden neu gestartet...

REM Kill everything
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Overlay" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DartsKiosk*" >nul 2>&1
timeout /t 2 /nobreak >nul

REM Restart launcher
if exist "!INSTALL_DIR!\darts_launcher.bat" (
    start "" /MIN "!INSTALL_DIR!\darts_launcher.bat"
    echo   [OK] Launcher neu gestartet
) else (
    echo   [FEHLER] darts_launcher.bat nicht gefunden
)
goto :menu

REM ============================================================================
REM  OPTION 3 — Stop All Services
REM ============================================================================
:stop_all
echo.
echo   Alle Kiosk-Dienste werden gestoppt...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Overlay" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DartsKiosk*" >nul 2>&1
REM Also kill any chrome instances from kiosk profile
taskkill /F /IM chrome.exe >nul 2>&1
echo   [OK] Alle Dienste gestoppt
goto :menu

REM ============================================================================
REM  OPTION 4 — Check Backend Status
REM ============================================================================
:check_status
echo.
echo   Backend-Status:
curl -s "http://localhost:!BACKEND_PORT!/api/health" 2>nul
if !ERRORLEVEL! NEQ 0 (
    echo   [FEHLER] Backend nicht erreichbar!
) else (
    echo.
    echo   [OK] Backend laeuft
)
echo.
goto :menu

REM ============================================================================
REM  OPTION 5 — Show Backend Logs
REM ============================================================================
:show_backend_logs
echo.
if exist "!INSTALL_DIR!\logs\backend.log" (
    echo   === Letzte 30 Zeilen Backend-Log ===
    powershell -NoProfile -Command "Get-Content '!INSTALL_DIR!\logs\backend.log' -Tail 30"
) else (
    echo   Kein Backend-Log gefunden.
)
echo.
goto :menu

REM ============================================================================
REM  OPTION 6 — Show Launcher Logs
REM ============================================================================
:show_launcher_logs
echo.
if exist "!INSTALL_DIR!\logs\launcher.log" (
    echo   === Letzte 30 Zeilen Launcher-Log ===
    powershell -NoProfile -Command "Get-Content '!INSTALL_DIR!\logs\launcher.log' -Tail 30"
) else (
    echo   Kein Launcher-Log gefunden.
)
echo.
goto :menu

REM ============================================================================
REM  OPTION 7 — Update System
REM ============================================================================
:update
echo.
echo   System-Update...
if exist "!INSTALL_DIR!\updater.py" (
    python "!INSTALL_DIR!\updater.py"
) else (
    echo   [WARN] updater.py nicht gefunden
    echo   Manuelle Aktualisierung:
    echo     1. Neues Release-ZIP herunterladen
    echo     2. Dienste stoppen (Option 3^)
    echo     3. Dateien ueberschreiben (NICHT data\ loeschen^)
    echo     4. Kiosk neu starten (Option 2^)
)
echo.
goto :menu

REM ============================================================================
REM  OPTION 8 — Full Uninstall
REM ============================================================================
:uninstall
echo.
echo   ACHTUNG: Dies deinstalliert den Kiosk-Modus vollstaendig!
set /p "CONFIRM=Wirklich deinstallieren? (J/N): "
if /i not "!CONFIRM!"=="J" goto :menu

if exist "!INSTALL_DIR!\uninstall_kiosk.bat" (
    call "!INSTALL_DIR!\uninstall_kiosk.bat"
) else (
    echo   [FEHLER] uninstall_kiosk.bat nicht gefunden
)
goto :menu

REM ============================================================================
REM  OPTION 9 — Reboot
REM ============================================================================
:reboot
echo.
set /p "CONFIRM=System wirklich neu starten? (J/N): "
if /i not "!CONFIRM!"=="J" goto :menu
shutdown /r /t 5 /c "Darts Kiosk Maintenance — Neustart"
exit /b 0

REM ============================================================================
REM  OPTION 0 — Exit
REM ============================================================================
:exit_tool
echo.
echo   Maintenance beendet.
endlocal
exit /b 0
