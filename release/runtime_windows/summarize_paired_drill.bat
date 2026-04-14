@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "LABEL=%~1"
if "%LABEL%"=="" set "LABEL=board-pc-drill"
set "UPDATE_LEG=data\support\drills\%LABEL%\drill-leg-update-%LABEL%.json"
set "ROLLBACK_LEG=data\support\drills\%LABEL%\drill-leg-rollback-%LABEL%.json"
set "SUMMARY_JSON=data\support\drills\%LABEL%\paired-drill-summary-%LABEL%.json"
set "SUMMARY_MD=data\support\drills\%LABEL%\paired-drill-summary-%LABEL%.md"
set "BUNDLE_PATH=data\support\drills\%LABEL%\runtime-support-bundle-paired-%LABEL%.zip"

if not "%~2"=="" set "UPDATE_LEG=%~2"
if not "%~3"=="" set "ROLLBACK_LEG=%~3"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"

echo [1/2] Baue Pair-Summary fuer %LABEL%...
python app\bin\runtime_maintenance.py build-paired-drill-summary --label "%LABEL%" --update-leg "%UPDATE_LEG%" --rollback-leg "%ROLLBACK_LEG%" --summary "%SUMMARY_JSON%" --summary-md "%SUMMARY_MD%"
set "EXIT_CODE=!ERRORLEVEL!"
if !EXIT_CODE! NEQ 0 (
    echo [FAIL] Pair-Summary fehlgeschlagen oder Closed-Loop noch nicht gruen.
    pause
    endlocal & exit /b !EXIT_CODE!
)

echo [2/2] Optionales Support-Bundle mit Pair-Summary aktualisieren...
python app\bin\runtime_maintenance.py build-support-bundle --label "%LABEL%" --bundle "%BUNDLE_PATH%" --before "data\support\drills\%LABEL%\field_state_update_before.json" --after "data\support\drills\%LABEL%\field_state_rollback_after.json" --report "%SUMMARY_MD%" >nul
if !ERRORLEVEL! EQU 0 (
    echo [OK] Support-Bundle aktualisiert.
) else (
    echo [WARN] Support-Bundle konnte nicht aktualisiert werden.
)

echo.
echo [INFO] Ticket-Handoff lesen unter:
echo        data\support\drills\%LABEL%\DRILL_HANDOFF.md
echo        data\support\drills\%LABEL%\DRILL_HANDOFF.json
echo [INFO] Ticket-Kommentar zum Einfuegen:
echo        data\support\drills\%LABEL%\DRILL_TICKET_COMMENT.txt
echo        data\support\drills\%LABEL%\DRILL_TICKET_COMMENT.md
echo [OK] Pair-Summary liegt unter data\support\drills\%LABEL%\paired-drill-summary-%LABEL%.json/.md
pause
endlocal & exit /b 0
