@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

if "%~1"=="" goto :usage

set "BACKUP_PATH=%~1"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"
echo [1/2] Erzeuge Runtime-Rollback-Manifest...
python app\bin\runtime_maintenance.py prepare-rollback-manifest --backup-path "%BACKUP_PATH%"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Rollback-Manifest konnte nicht sicher vorbereitet werden.
    pause
    exit /b 1
)

echo [2/2] Pruefe Rollback-Manifest...
python app\bin\runtime_maintenance.py validate-update --manifest "data\update_manifest.json"
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Runtime-Rollback vorbereitet. Naechster Schritt: app\bin\update_runtime.bat
) else (
    echo [FAIL] Rollback-Manifest ist noch nicht sauber.
)
echo.
pause
endlocal & exit /b %EXIT_CODE%

:usage
echo Verwendung:
echo   app\bin\prepare_runtime_rollback.bat ^<backup-path^>
echo.
echo Beispiel:
echo   app\bin\prepare_runtime_rollback.bat data\app_backups\runtime-app-4.4.3-to-4.4.4-20260413-120000Z.zip
echo.
pause
endlocal & exit /b 2
