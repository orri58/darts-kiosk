@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "LABEL=%~1"
if "%LABEL%"=="" set "LABEL=board-pc-drill"
set "BUNDLE_PATH=%~2"
set "DEVICE_ID=%~3"
set "OPERATOR=%~4"
set "SERVICE_TICKET=%~5"
set "DEVICE_ARG="
set "OPERATOR_ARG="
set "TICKET_ARG="
if not "%DEVICE_ID%"=="" set "DEVICE_ARG=--device-id %DEVICE_ID%"
if not "%OPERATOR%"=="" set "OPERATOR_ARG=--operator %OPERATOR%"
if not "%SERVICE_TICKET%"=="" set "TICKET_ARG=--service-ticket %SERVICE_TICKET%"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"
echo [1/1] Baue Support-Bundle fuer %LABEL%...
if "%BUNDLE_PATH%"=="" (
    python app\bin\runtime_maintenance.py build-support-bundle --label "%LABEL%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG%
) else (
    python app\bin\runtime_maintenance.py build-support-bundle --label "%LABEL%" --bundle "%BUNDLE_PATH%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG%
)
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Support-Bundle gebaut.
) else (
    echo [FAIL] Support-Bundle konnte nicht gebaut werden.
)
echo.
pause
endlocal & exit /b %EXIT_CODE%
