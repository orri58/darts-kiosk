@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

set "LABEL=%~1"
if "%LABEL%"=="" set "LABEL=board-pc-drill"

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"

echo [1/1] Zeige kompakte Attachment-/Re-Attach-Uebersicht fuer %LABEL%...
python app\bin\runtime_maintenance.py show-attachment-readiness --label "%LABEL%"
set "EXIT_CODE=!ERRORLEVEL!"
echo.
if !EXIT_CODE! EQU 0 (
    echo [OK] Kompakte Uebersicht ausgegeben.
) else (
    echo [WARN] Uebersicht zeigt fehlende Pflicht-Artefakte oder blockierende Handoff-Luecken.
)
echo [INFO] Vollstaendige Detaildateien:
echo        data\support\drills\%LABEL%\DRILL_HANDOFF.md
echo        data\support\drills\%LABEL%\DRILL_TICKET_COMMENT.txt
pause
endlocal & exit /b %EXIT_CODE%
