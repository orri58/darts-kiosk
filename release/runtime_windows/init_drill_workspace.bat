@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "LABEL=%~1"
if "%LABEL%"=="" set "LABEL=board-pc-drill"
set "DEVICE_ID=%~2"
set "OPERATOR=%~3"
set "SERVICE_TICKET=%~4"
set "NOTES=%~5"
set "DEVICE_ARG="
set "OPERATOR_ARG="
set "TICKET_ARG="
set "NOTES_ARG="
if not "%DEVICE_ID%"=="" set "DEVICE_ARG=--device-id %DEVICE_ID%"
if not "%OPERATOR%"=="" set "OPERATOR_ARG=--operator %OPERATOR%"
if not "%SERVICE_TICKET%"=="" set "TICKET_ARG=--service-ticket %SERVICE_TICKET%"
if not "%NOTES%"=="" set "NOTES_ARG=--notes %NOTES%"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"
echo [1/1] Initialisiere Drill-Arbeitsordner fuer %LABEL%...
python app\bin\runtime_maintenance.py init-drill-workspace --label "%LABEL%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG% %NOTES_ARG%
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Drill-Ordner vorbereitet: data\support\drills\%LABEL%\
) else (
    echo [FAIL] Drill-Ordner konnte nicht vorbereitet werden.
)
echo.
pause
endlocal & exit /b %EXIT_CODE%
