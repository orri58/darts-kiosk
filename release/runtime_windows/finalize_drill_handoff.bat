@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "LABEL=%~1"
if "%LABEL%"=="" set "LABEL=board-pc-drill"
set "NOTES=%~5"
set "UPDATE_LEG=data\support\drills\%LABEL%\drill-leg-update-%LABEL%.json"
set "ROLLBACK_LEG=data\support\drills\%LABEL%\drill-leg-rollback-%LABEL%.json"
set "SUMMARY_JSON=data\support\drills\%LABEL%\paired-drill-summary-%LABEL%.json"
set "SUMMARY_MD=data\support\drills\%LABEL%\paired-drill-summary-%LABEL%.md"
set "BUNDLE_PATH=data\support\drills\%LABEL%\runtime-support-bundle-paired-%LABEL%.zip"
set "BEFORE_PATH=data\support\drills\%LABEL%\field_state_update_before.json"
set "AFTER_PATH=data\support\drills\%LABEL%\field_state_rollback_after.json"

if not "%~2"=="" set "UPDATE_LEG=%~2"
if not "%~3"=="" set "ROLLBACK_LEG=%~3"
if not "%~4"=="" set "BUNDLE_PATH=%~4"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"

echo [1/1] Finalisiere Drill-Handoff fuer %LABEL%...
if not "%NOTES%"=="" (
    python app\bin\runtime_maintenance.py finalize-drill-handoff --label "%LABEL%" --update-leg "%UPDATE_LEG%" --rollback-leg "%ROLLBACK_LEG%" --summary "%SUMMARY_JSON%" --summary-md "%SUMMARY_MD%" --bundle "%BUNDLE_PATH%" --before "%BEFORE_PATH%" --after "%AFTER_PATH%" --report "%SUMMARY_MD%" --notes "%NOTES%"
) else (
    python app\bin\runtime_maintenance.py finalize-drill-handoff --label "%LABEL%" --update-leg "%UPDATE_LEG%" --rollback-leg "%ROLLBACK_LEG%" --summary "%SUMMARY_JSON%" --summary-md "%SUMMARY_MD%" --bundle "%BUNDLE_PATH%" --before "%BEFORE_PATH%" --after "%AFTER_PATH%" --report "%SUMMARY_MD%"
)
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if !EXIT_CODE! EQU 0 (
    echo [OK] Drill-Handoff ist versandbereit.
) else (
    echo [WARN] Drill-Handoff wurde aktualisiert, aber Empfehlung ist nicht ship. Bitte Manifest pruefen.
)
echo [INFO] Ticket-Handoff lesen unter:
echo        data\support\drills\%LABEL%\DRILL_HANDOFF.md
echo        data\support\drills\%LABEL%\DRILL_HANDOFF.json
echo [INFO] Ticket-Kommentar zum Einfuegen:
echo        data\support\drills\%LABEL%\DRILL_TICKET_COMMENT.txt
echo        data\support\drills\%LABEL%\DRILL_TICKET_COMMENT.md
if not "%NOTES%"=="" echo [INFO] Operator-Notiz wurde ins Handoff uebernommen.
echo [INFO] Pair-Summary / Bundle:
echo        data\support\drills\%LABEL%\paired-drill-summary-%LABEL%.json/.md
echo        data\support\drills\%LABEL%\runtime-support-bundle-paired-%LABEL%.zip
echo [INFO] Nach erfolgreichem Ticket-Upload optional bestaetigen mit:
echo        app\bin\acknowledge_drill_handoff.bat %LABEL% ^<attached-by^> ^<ticket-status^> [note] [ticket-reference] [ticket-url]
echo [INFO] Falls die Pair-Artefakte spaeter neu gebaut wurden, Re-Upload/Re-Bestaetigung mit:
echo        app\bin\reacknowledge_drill_handoff.bat %LABEL% [attached-by] [ticket-status] [note] [ticket-reference] [ticket-url]
pause
endlocal & exit /b %EXIT_CODE%
