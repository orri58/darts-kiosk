@echo off
chcp 65001 >nul 2>&1
echo.
echo ================================================================
echo   DARTS KIOSK - Autostart konfigurieren
echo ================================================================
echo.
echo Dieses Script richtet den automatischen Start ein:
echo   - Darts Kiosk startet beim Windows-Login automatisch
echo   - Kein Admin-Recht noetig (User-Level Autostart)
echo.

cd /d "%~dp0"

REM === Create a VBS launcher (runs start.bat without visible cmd window) ===
echo Erstelle versteckten Starter...
(
    echo Set WshShell = CreateObject^("WScript.Shell"^)
    echo WshShell.CurrentDirectory = "%~dp0"
    echo WshShell.Run """%~dp0start.bat""", 0, False
) > "%~dp0darts_autostart.vbs"
echo   [OK] darts_autostart.vbs erstellt

REM === Create shortcut in Windows Startup folder ===
echo Erstelle Autostart-Verknuepfung...
set STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup

REM Create shortcut using PowerShell (no admin required)
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%STARTUP_FOLDER%\Darts Kiosk.lnk'); $sc.TargetPath = '%~dp0darts_autostart.vbs'; $sc.WorkingDirectory = '%~dp0'; $sc.Description = 'Darts Kiosk Autostart'; $sc.Save()"

if exist "%STARTUP_FOLDER%\Darts Kiosk.lnk" (
    echo   [OK] Autostart-Verknuepfung erstellt in:
    echo        %STARTUP_FOLDER%
    echo.
    echo   Darts Kiosk startet jetzt automatisch beim naechsten Login.
) else (
    echo   [WARN] Automatische Verknuepfung fehlgeschlagen.
    echo          Bitte manuell erstellen:
    echo          1. Win+R, eingeben: shell:startup
    echo          2. Verknuepfung zu darts_autostart.vbs erstellen
)

echo.
echo ================================================================
echo.
echo   Autostart AKTIVIERT
echo.
echo   Zum Deaktivieren:
echo   1. Win+R, eingeben: shell:startup
echo   2. "Darts Kiosk" Verknuepfung loeschen
echo.
echo ================================================================
echo.
pause
