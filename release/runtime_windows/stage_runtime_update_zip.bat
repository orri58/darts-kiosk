@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

if "%~1"=="" goto :usage

set "RUNTIME_ZIP=%~1"
set "OUTPUT_DIR=%~2"
if "%OUTPUT_DIR%"=="" set "OUTPUT_DIR=data\downloads\staged-runtime"

echo [1/2] Entpacke Runtime-ZIP in app-only Staging...
python app\bin\runtime_maintenance.py stage-runtime-zip --runtime-zip "%RUNTIME_ZIP%" --output-dir "%OUTPUT_DIR%"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Runtime-ZIP konnte nicht sicher als app-only Staging vorbereitet werden.
    pause
    exit /b 1
)

echo [2/2] App-only Staging fertig.
echo [OK] App-only Staging vorbereitet unter: %OUTPUT_DIR%
echo.
echo Naechster Schritt:
echo   app\bin\prepare_update_rehearsal.bat "%OUTPUT_DIR%" ^<target-version^>
echo.
pause
endlocal & exit /b 0

:usage
echo Verwendung:
echo   app\bin\stage_runtime_update_zip.bat ^<runtime-zip^> [output-dir]
echo.
echo Beispiel:
echo   app\bin\stage_runtime_update_zip.bat data\downloads\darts-kiosk-v4.4.4-windows-runtime.zip data\downloads\staged-v4.4.4
echo.
pause
endlocal & exit /b 2
