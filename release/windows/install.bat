@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Darts Kiosk - Ein-Klick-Installation
cd /d "%~dp0"

set "APP_VERSION=unknown"
if exist "VERSION" (
    set /p APP_VERSION=<VERSION
)

echo.
echo ================================================================
echo   DARTS KIOSK v!APP_VERSION! - Ein-Klick-Installation
echo ================================================================
echo.
echo Dieses Skript:
echo   1. richtet Python/Node-Abhaengigkeiten ein
echo   2. erstellt Build + Laufzeitordner
echo   3. vorbereitet Agent + Autostart
echo   4. startet das System direkt danach
echo.

call "%~dp0setup_windows.bat"
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] setup_windows.bat ist fehlgeschlagen.
    exit /b 1
)

echo.
echo [INFO] Registriere optionalen App-Autostart...
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.CurrentDirectory = "%~dp0"
    echo WshShell.Run """%~dp0start.bat""", 0, False
) > "%~dp0darts_autostart.vbs"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%STARTUP_FOLDER%\Darts Kiosk.lnk'); $sc.TargetPath = '%~dp0darts_autostart.vbs'; $sc.WorkingDirectory = '%~dp0'; $sc.Description = 'Darts Kiosk Autostart'; $sc.Save()" >nul 2>&1
if exist "%STARTUP_FOLDER%\Darts Kiosk.lnk" (
    echo   [OK] App-Autostart vorbereitet
) else (
    echo   [WARN] App-Autostart konnte nicht automatisch eingerichtet werden
)

echo.
echo [HINWEIS] Falls Autodarts noch nie auf diesem Geraet angemeldet wurde:
echo           bitte jetzt einmal setup_profile.bat ausfuehren und Chrome normal schliessen.
echo.
echo [INFO] Starte Darts Kiosk...
start "" "%~dp0start.bat"

echo.
echo ================================================================
echo   INSTALLATION ABGESCHLOSSEN
echo.
echo   Naechste sinnvolle Schritte:
echo   - setup_profile.bat (nur beim ersten Autodarts-Login)
echo   - smoke_test.bat
echo   - Admin: http://localhost:8001/admin
echo ================================================================
echo.
pause
endlocal
