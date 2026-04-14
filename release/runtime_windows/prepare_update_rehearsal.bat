@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set "STAGING_DIR=%~1"
set "TARGET_VERSION=%~2"
set "BACKUP_PATH=%~3"
if "%BACKUP_PATH%"=="" set "BACKUP_PATH=data\app_backups\runtime-pre-update.zip"

echo [1/3] Erzeuge Runtime-Manifest...
python app\bin\runtime_maintenance.py prepare-update-manifest --manifest "data\update_manifest.json" --staging-dir "%STAGING_DIR%" --target-version "%TARGET_VERSION%" --backup-path "%BACKUP_PATH%"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Manifest konnte nicht sicher vorbereitet werden.
    pause
    exit /b 1
)

echo [2/3] Pruefe Runtime-Update-Payload...
python app\bin\runtime_maintenance.py validate-update --manifest "data\update_manifest.json"
if !ERRORLEVEL! NEQ 0 (
    echo [FAIL] Runtime-Update-Payload ist ungueltig.
    pause
    exit /b 1
)

echo [3/3] Rehearsal-Preflight...
python app\bin\runtime_maintenance.py rehearsal --manifest "data\update_manifest.json"
set "EXIT_CODE=!ERRORLEVEL!"

echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Runtime-Update-Rehearsal vorbereitet: data\update_manifest.json
) else (
    echo [FAIL] Rehearsal-Preflight ist noch nicht sauber.
)
echo.
pause
endlocal & exit /b %EXIT_CODE%

:usage
echo Verwendung:
echo   app\bin\prepare_update_rehearsal.bat ^<staging-dir^> ^<target-version^> [backup-path]
echo.
echo Beispiel:
echo   app\bin\prepare_update_rehearsal.bat data\downloads\staged-v4.4.4 4.4.4
echo.
pause
endlocal & exit /b 2
