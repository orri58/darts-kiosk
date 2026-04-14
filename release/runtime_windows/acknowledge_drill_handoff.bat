@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "LABEL=%~1"
if "%LABEL%"=="" set "LABEL=board-pc-drill"
set "ATTACHED_BY=%~2"
set "TICKET_STATUS=%~3"
set "NOTE=%~4"
set "TICKET_REFERENCE=%~5"
set "TICKET_URL=%~6"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"

echo [1/1] Bestaetige Ticket-Upload fuer %LABEL%...
if not "%TICKET_URL%"=="" (
    python app\bin\runtime_maintenance.py acknowledge-drill-handoff --label "%LABEL%" --attached-by "%ATTACHED_BY%" --ticket-status "%TICKET_STATUS%" --notes "%NOTE%" --ticket-reference "%TICKET_REFERENCE%" --ticket-url "%TICKET_URL%"
) else if not "%TICKET_REFERENCE%"=="" (
    python app\bin\runtime_maintenance.py acknowledge-drill-handoff --label "%LABEL%" --attached-by "%ATTACHED_BY%" --ticket-status "%TICKET_STATUS%" --notes "%NOTE%" --ticket-reference "%TICKET_REFERENCE%"
) else if not "%NOTE%"=="" (
    python app\bin\runtime_maintenance.py acknowledge-drill-handoff --label "%LABEL%" --attached-by "%ATTACHED_BY%" --ticket-status "%TICKET_STATUS%" --notes "%NOTE%"
) else (
    python app\bin\runtime_maintenance.py acknowledge-drill-handoff --label "%LABEL%" --attached-by "%ATTACHED_BY%" --ticket-status "%TICKET_STATUS%"
)
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if !EXIT_CODE! EQU 0 (
    echo [OK] Ticket-Upload im Drill-Handoff vermerkt.
) else (
    echo [FAIL] Ticket-Upload konnte nicht vermerkt werden.
)
echo [INFO] Aktualisierte Handoff-Dateien:
echo        data\support\drills\%LABEL%\DRILL_HANDOFF.md
echo        data\support\drills\%LABEL%\DRILL_TICKET_COMMENT.txt
if not "%TICKET_REFERENCE%"=="" echo [INFO] Ticket-Referenz wurde mitgespeichert: %TICKET_REFERENCE%
if not "%TICKET_URL%"=="" echo [INFO] Ticket-URL wurde mitgespeichert: %TICKET_URL%
pause
endlocal & exit /b %EXIT_CODE%
