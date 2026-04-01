@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Profil einrichten
cd /d "%~dp0"
echo.
echo ================================================================
echo   DARTS KIOSK - Chrome-Profil einrichten
echo ================================================================
echo.
echo   Dieses Script oeffnet Google Chrome mit dem Kiosk-Profil.
echo   Das Profil wird unter data\chrome_profile\BOARD-1 gespeichert.
echo.
echo   Was Sie jetzt tun sollten:
echo.
echo     1. Bei Google anmelden (falls noetig)
echo     2. Autodarts oeffnen (https://play.autodarts.io)
echo     3. Bei Autodarts anmelden
echo     4. Extensions installieren:
echo        - "Tools for Autodarts" (Chrome Web Store)
echo        - andere gewuenschte Extensions
echo     5. Chrome NORMAL schliessen (X-Button oder Strg+W)
echo.
echo   Nach dem Schliessen werden Login und Extensions
echo   dauerhaft im Profil gespeichert und beim naechsten
echo   Kiosk-Start automatisch verwendet.
echo.
echo ================================================================
echo.

REM === Configuration ===
set BOARD_ID=BOARD-1
if exist "backend\.env" call :load_env_value BOARD_ID BOARD_ID

echo   Profilpfad: data\chrome_profile\%BOARD_ID%

REM === Create profile directory ===
if not exist "data\chrome_profile\%BOARD_ID%" (
    mkdir "data\chrome_profile\%BOARD_ID%"
    echo [INFO] Neues Profil-Verzeichnis erstellt: data\chrome_profile\%BOARD_ID%
) else (
    echo [OK]   Vorhandenes Profil wird wiederverwendet: data\chrome_profile\%BOARD_ID%
)

REM === Detect Chrome ===
set CHROME_PATH=
for %%G in (
    "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    "%LocalAppData%\Google\Chrome\Application\chrome.exe"
) do (
    if exist %%G (
        if not defined CHROME_PATH set "CHROME_PATH=%%~G"
    )
)

if not defined CHROME_PATH (
    echo.
    echo [FAIL] Google Chrome nicht gefunden!
    echo        Bitte Chrome installieren: https://www.google.com/chrome/
    pause
    exit /b 1
)

echo [OK]   Chrome gefunden: %CHROME_PATH%
echo.
echo Chrome wird jetzt mit dem Kiosk-Profil geoeffnet...
echo Bitte anmelden und Extensions installieren.
echo.
echo ================================================================
echo   WICHTIG: Chrome danach NORMAL schliessen!
echo   (Nicht dieses Fenster schliessen)
echo ================================================================
echo.

call :kill_chrome_profile "data\chrome_profile\%BOARD_ID%"

REM Open Chrome with the persistent kiosk profile (normal mode, not kiosk)
start "" /WAIT "%CHROME_PATH%" --user-data-dir="%~dp0data\chrome_profile\%BOARD_ID%" --no-first-run --no-default-browser-check "https://play.autodarts.io"

echo.
echo ================================================================
echo   Chrome wurde geschlossen.
echo   Login und Extensions sind jetzt im Profil gespeichert.
echo.

REM === Verify profile ===
if exist "data\chrome_profile\%BOARD_ID%\Default" (
    echo   [OK] Profil-Daten vorhanden: data\chrome_profile\%BOARD_ID%\Default
    if exist "data\chrome_profile\%BOARD_ID%\Default\Cookies" (
        echo   [OK] Cookies gespeichert (Login sollte erhalten bleiben)
    )
    if exist "data\chrome_profile\%BOARD_ID%\Default\Extensions" (
        echo   [OK] Extensions-Verzeichnis vorhanden
    ) else (
        echo   [WARN] Keine Extensions installiert
    )
) else (
    echo   [WARN] Profil-Daten nicht gefunden. Wurde Chrome korrekt geschlossen?
)

echo.
echo   Naechster Schritt: start.bat ausfuehren
echo ================================================================
echo.
pause
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
