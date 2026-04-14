@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
cd /d "%~dp0\..\.."

if "%~1"=="" goto :usage
set "MODE=%~1"
set "LABEL=%~2"
if "%LABEL%"=="" set "LABEL=board-pc-drill"
set "DEVICE_ID=%~3"
set "OPERATOR=%~4"
set "SERVICE_TICKET=%~5"
set "LEG=%~6"
set "DEVICE_ARG="
set "OPERATOR_ARG="
set "TICKET_ARG="
set "STATE_PATH="
set "BEFORE_PATH=data\field_state_before.json"
set "AFTER_PATH=data\field_state_after.json"
set "REPORT_PATH=data\field_report.md"
set "BUNDLE_PATH="
set "SUMMARY_PATH="
if not "%DEVICE_ID%"=="" set "DEVICE_ARG=--device-id %DEVICE_ID%"
if not "%OPERATOR%"=="" set "OPERATOR_ARG=--operator %OPERATOR%"
if not "%SERVICE_TICKET%"=="" set "TICKET_ARG=--service-ticket %SERVICE_TICKET%"

if /I "%LEG%"=="update" (
    set "STATE_PATH=data\support\drills\%LABEL%\field_state_update_before.json"
    set "BEFORE_PATH=data\support\drills\%LABEL%\field_state_update_before.json"
    set "AFTER_PATH=data\support\drills\%LABEL%\field_state_update_after.json"
    set "REPORT_PATH=data\support\drills\%LABEL%\field_report_update.md"
    set "BUNDLE_PATH=data\support\drills\%LABEL%\runtime-support-bundle-update-%LABEL%.zip"
    set "SUMMARY_PATH=data\support\drills\%LABEL%\drill-leg-update-%LABEL%.json"
) else if /I "%LEG%"=="rollback" (
    set "STATE_PATH=data\support\drills\%LABEL%\field_state_rollback_before.json"
    set "BEFORE_PATH=data\support\drills\%LABEL%\field_state_rollback_before.json"
    set "AFTER_PATH=data\support\drills\%LABEL%\field_state_rollback_after.json"
    set "REPORT_PATH=data\support\drills\%LABEL%\field_report_rollback.md"
    set "BUNDLE_PATH=data\support\drills\%LABEL%\runtime-support-bundle-rollback-%LABEL%.zip"
    set "SUMMARY_PATH=data\support\drills\%LABEL%\drill-leg-rollback-%LABEL%.json"
)

if exist "app\.venv\Scripts\activate.bat" call "app\.venv\Scripts\activate.bat"

if /I "%MODE%"=="before" (
    if not "%LEG%"=="" (
        python app\bin\runtime_maintenance.py init-drill-workspace --label "%LABEL%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG% >nul
    )
    if "%STATE_PATH%"=="" set "STATE_PATH=data\field_state_before.json"
    echo [1/1] Erfasse Vorher-Zustand fuer %LABEL%...
    python app\bin\runtime_maintenance.py capture-field-state --state "%STATE_PATH%" --drill-phase before --label "%LABEL%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG%
    set "EXIT_CODE=!ERRORLEVEL!"
    if "!EXIT_CODE!"=="0" echo [OK] Vorher-Zustand gespeichert: %STATE_PATH%
    echo.
    pause
    endlocal & exit /b !EXIT_CODE!
)

if /I "%MODE%"=="after" (
    if not "%LEG%"=="" (
        python app\bin\runtime_maintenance.py init-drill-workspace --label "%LABEL%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG% >nul
    )
    echo [1/3] Erfasse Nachher-Zustand fuer %LABEL%...
    python app\bin\runtime_maintenance.py capture-field-state --state "%AFTER_PATH%" --drill-phase after --label "%LABEL%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG%
    if !ERRORLEVEL! NEQ 0 (
        echo [FAIL] Nachher-Zustand konnte nicht erfasst werden.
        pause
        endlocal & exit /b 1
    )
    echo [2/3] Vergleiche Vorher/Nachher und schreibe Feldreport...
    python app\bin\runtime_maintenance.py compare-field-state --before "%BEFORE_PATH%" --after "%AFTER_PATH%" --report "%REPORT_PATH%" --label "%LABEL%"
    set "EXIT_CODE=!ERRORLEVEL!"
    echo.
    if "!EXIT_CODE!"=="0" (
        echo [OK] Feldreport geschrieben: %REPORT_PATH%
        if /I "%LEG%"=="update" (
            python app\bin\runtime_maintenance.py build-drill-leg-summary --label "%LABEL%" --leg update --before "%BEFORE_PATH%" --after "%AFTER_PATH%" --report "%REPORT_PATH%" --summary "%SUMMARY_PATH%"
            if !ERRORLEVEL! EQU 0 (
                echo [OK] Update-Leg-Summary gespeichert.
            ) else (
                echo [WARN] Update-Leg-Summary zeigt noch keinen sauberen Pass.
            )
        ) else if /I "%LEG%"=="rollback" (
            python app\bin\runtime_maintenance.py build-drill-leg-summary --label "%LABEL%" --leg rollback --before "%BEFORE_PATH%" --after "%AFTER_PATH%" --report "%REPORT_PATH%" --summary "%SUMMARY_PATH%"
            if !ERRORLEVEL! EQU 0 (
                echo [OK] Rollback-Leg-Summary gespeichert.
            ) else (
                echo [WARN] Rollback-Leg-Summary zeigt noch keinen sauberen Pass.
            )
        )
        echo [3/3] Packe Support-Bundle fuer Operator-Handoff...
        if "%BUNDLE_PATH%"=="" (
            python app\bin\runtime_maintenance.py build-support-bundle --label "%LABEL%" --before "%BEFORE_PATH%" --after "%AFTER_PATH%" --report "%REPORT_PATH%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG%
        ) else (
            python app\bin\runtime_maintenance.py build-support-bundle --label "%LABEL%" --bundle "%BUNDLE_PATH%" --before "%BEFORE_PATH%" --after "%AFTER_PATH%" --report "%REPORT_PATH%" %DEVICE_ARG% %OPERATOR_ARG% %TICKET_ARG%
        )
        if !ERRORLEVEL! EQU 0 (
            echo [OK] Support-Bundle unter data\support\ erstellt.
        ) else (
            echo [WARN] Support-Bundle konnte nicht gebaut werden, Report bleibt aber erhalten.
        )
    ) else (
        echo [FAIL] Feldreport zeigt Boundary-Abweichungen. Bitte data\field_report.md pruefen.
    )
    echo.
    pause
    endlocal & exit /b !EXIT_CODE!
)

:usage
echo Verwendung:
echo   app\bin\capture_field_evidence.bat ^<before^|after^> [label] [device-id] [operator] [service-ticket] [update^|rollback]
echo.
echo Beispiele:
echo   app\bin\capture_field_evidence.bat before update-to-4.4.4
echo   app\bin\capture_field_evidence.bat after update-to-4.4.4 BOARD-17 orri TICKET-2048 update
echo   app\bin\capture_field_evidence.bat after rollback-to-4.4.3 BOARD-17 orri TICKET-2048 rollback
echo.
pause
endlocal & exit /b 2
