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

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"
echo [1/1] Stage + Manifest + Rehearsal aus Runtime-ZIP...
if "%OUTPUT_DIR%"=="" (
    if "%BACKUP_PATH%"=="" (
        python app\bin\runtime_maintenance.py prepare-runtime-update --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%"
    ) else (
        python app\bin\runtime_maintenance.py prepare-runtime-update --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --backup-path "%BACKUP_PATH%"
    )
) else (
    if "%BACKUP_PATH%"=="" (
        python app\bin\runtime_maintenance.py prepare-runtime-update --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --output-dir "%OUTPUT_DIR%"
    ) else (
        python app\bin\runtime_maintenance.py prepare-runtime-update --runtime-zip "%RUNTIME_ZIP%" --target-version "%TARGET_VERSION%" --output-dir "%OUTPUT_DIR%" --backup-path "%BACKUP_PATH%"
    )
)
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if "%EXIT_CODE%"=="0" (
    echo [OK] Runtime-ZIP wurde staging-, manifest- und rehearsal-fertig vorbereitet.
    echo      Naechster Schritt: app\bin\update_runtime.bat
) else (
    echo [FAIL] Runtime-ZIP Vorbereitung/Rehearsal nicht sauber.
)
echo.
pause
endlocal & exit /b %EXIT_CODE%

:usage
echo Verwendung:
echo   app\bin\prepare_runtime_update_from_zip.bat ^<runtime-zip^> ^<target-version^> [output-dir] [backup-path]
echo.
echo Beispiel:
echo   app\bin\prepare_runtime_update_from_zip.bat data\downloads\darts-kiosk-v4.4.4-windows-runtime.zip 4.4.4 data\downloads\staged-v4.4.4
echo.
pause
endlocal & exit /b 2
