@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "LABEL=%~1"
if "%LABEL%"=="" set "LABEL=board-pc-drill"
set "TESTED_BY=%~2"
set "OVERALL_STATUS=%~3"
set "DEVICE_ID=%~4"
set "OPERATOR=%~5"
set "SERVICE_TICKET=%~6"
set "NOTES=%~7"
set "TESTED_ARG="
set "OVERALL_ARG="
set "DEVICE_ARG="
set "OPERATOR_ARG="
set "TICKET_ARG="
set "NOTES_ARG="
if not "%TESTED_BY%"=="" set "TESTED_ARG=--tested-by %TESTED_BY%"
if not "%OVERALL_STATUS%"=="" set "OVERALL_ARG=--overall-status %OVERALL_STATUS%"
if not "%DEVICE_ID%"=="" set "DEVICE_ARG=--device-id %DEVICE_ID%"
if not "%OPERATOR%"=="" set "OPERATOR_ARG=--operator %OPERATOR%"
if not "%SERVICE_TICKET%"=="" set "TICKET_ARG=--service-ticket %SERVICE_TICKET%"
if not "%NOTES%"=="" set "NOTES_ARG=--notes %NOTES%"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"

echo [1/1] Erfasse Board-PC-Postflight fuer %LABEL%...
python app\bin\runtime_maintenance.py capture-board-pc-postflight --label "%LABEL%" %TESTED_ARG% %OVERALL_ARG% %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG% %NOTES_ARG% --boot-status pass --admin-health-status pass --session-status pass --update-leg-status pass --rollback-leg-status pass --reopen-status pass
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if !EXIT_CODE! EQU 0 (
    echo [OK] Postflight-Artefakte geschrieben.
) else (
    echo [WARN] Postflight zeigt noch offene oder fehlgeschlagene Machine-Checks. Details pruefen.
)
echo [INFO] Artefakte:
echo        data\support\drills\%LABEL%\BOARD_PC_POSTFLIGHT.json
echo        data\support\drills\%LABEL%\BOARD_PC_POSTFLIGHT.md
echo [INFO] Fuer feinere Statuswerte direkt nutzen:
echo        python app\bin\runtime_maintenance.py capture-board-pc-postflight --label %LABEL% --boot-status pass^|fail^|pending --admin-health-status ...
pause
endlocal & exit /b %EXIT_CODE%
