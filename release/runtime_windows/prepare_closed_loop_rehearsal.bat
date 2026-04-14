@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set "RUNTIME_ZIP=%~1"
set "TARGET_VERSION=%~2"
set "OUTPUT_DIR=%~3"
set "BACKUP_PATH=%~4"
set "ROLLBACK_MANIFEST=%~5"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"
echo [1/1] Erzeuge Closed-Loop-Rehearsal (Backup + Stage + Update-Manifest + Rollback-Manifest)...
if "%OUTPUT_DIR%"=="" (
    if "%BACKUP_PATH%"=="" (
        if "%ROLLBACK_MANIFEST%"=="" (
            python app\bin\runtime_maintenance.py prepare-closed-loop-rehearsal --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%"
        ) else (
            python app\bin\runtime_maintenance.py prepare-closed-loop-rehearsal --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --rollback-manifest "%ROLLBACK_MANIFEST%"
        )
    ) else (
        if "%ROLLBACK_MANIFEST%"=="" (
            python app\bin\runtime_maintenance.py prepare-closed-loop-rehearsal --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --backup-path "%BACKUP_PATH%"
        ) else (
            python app\bin\runtime_maintenance.py prepare-closed-loop-rehearsal --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --backup-path "%BACKUP_PATH%" --rollback-manifest "%ROLLBACK_MANIFEST%"
        )
    )
) else (
    if "%BACKUP_PATH%"=="" (
        if "%ROLLBACK_MANIFEST%"=="" (
            python app\bin\runtime_maintenance.py prepare-closed-loop-rehearsal --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --output-dir "%OUTPUT_DIR%"
        ) else (
            python app\bin\runtime_maintenance.py prepare-closed-loop-rehearsal --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --output-dir "%OUTPUT_DIR%" --rollback-manifest "%ROLLBACK_MANIFEST%"
        )
    ) else (
        if "%ROLLBACK_MANIFEST%"=="" (
            python app\bin\runtime_maintenance.py prepare-closed-loop-rehearsal --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --output-dir "%OUTPUT_DIR%" --backup-path "%BACKUP_PATH%"
        ) else (
            python app\bin\runtime_maintenance.py prepare-closed-loop-rehearsal --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --output-dir "%OUTPUT_DIR%" --backup-path "%BACKUP_PATH%" --rollback-manifest "%ROLLBACK_MANIFEST%"
        )
    )
)
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Closed-Loop-Rehearsal vorbereitet.
    echo      Update:   data\update_manifest.json
    echo      Rollback: data\rollback_manifest.json
    echo      Naechster Schritt: app\bin\update_runtime.bat
) else (
    echo [FAIL] Closed-Loop-Rehearsal konnte nicht sauber vorbereitet werden.
)
echo.
pause
endlocal & exit /b %EXIT_CODE%

:usage
echo Verwendung:
echo   app\bin\prepare_closed_loop_rehearsal.bat ^<runtime-zip^> ^<target-version^> [output-dir] [backup-path] [rollback-manifest]
echo.
echo Beispiel:
echo   app\bin\prepare_closed_loop_rehearsal.bat data\downloads\darts-kiosk-v4.4.4-windows-runtime.zip 4.4.4 data\downloads\staged-v4.4.4
echo.
pause
endlocal & exit /b 2
