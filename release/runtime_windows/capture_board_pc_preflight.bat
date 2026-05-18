@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "LABEL=%~1"
if "%LABEL%"=="" set "LABEL=board-pc-drill"
set "DEVICE_ID=%~2"
set "OPERATOR=%~3"
set "SERVICE_TICKET=%~4"
set "EXPECTED_VERSION=%~5"
set "NOTES=%~6"
set "DEVICE_ARG="
set "OPERATOR_ARG="
set "TICKET_ARG="
set "EXPECTED_ARG="
set "NOTES_ARG="
if not "%DEVICE_ID%"=="" set "DEVICE_ARG=--device-id %DEVICE_ID%"
if not "%OPERATOR%"=="" set "OPERATOR_ARG=--operator %OPERATOR%"
if not "%SERVICE_TICKET%"=="" set "TICKET_ARG=--service-ticket %SERVICE_TICKET%"
if not "%EXPECTED_VERSION%"=="" set "EXPECTED_ARG=--expected-version %EXPECTED_VERSION%"
if not "%NOTES%"=="" set "NOTES_ARG=--notes %NOTES%"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"

echo [1/1] Erfasse Board-PC-Preflight fuer %LABEL%...
python app\bin\runtime_maintenance.py capture-board-pc-preflight --label "%LABEL%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG% %EXPECTED_ARG% %NOTES_ARG%
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if !EXIT_CODE! EQU 0 (
    echo [OK] Preflight-Artefakte geschrieben.
) else (
    echo [WARN] Preflight zeigt repo-/Versionsluecken. Details pruefen.
)
echo [INFO] Artefakte:
echo        data\support\drills\%LABEL%\BOARD_PC_PREFLIGHT.json
echo        data\support\drills\%LABEL%\BOARD_PC_PREFLIGHT.md
echo [INFO] Danach auf echter Hardware weitermachen: Autostart, Admin-Health, Autodarts, Update, Rollback.
pause
endlocal & exit /b %EXIT_CODE%
