@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Gestartet
echo.
echo ================================================================
echo   DARTS KIOSK - Starten
echo ================================================================
echo.

:: Check setup was done
if not exist "backend\.env" (
    echo [FAIL] Setup nicht durchgefuehrt!
    echo        Bitte zuerst setup_windows.bat ausfuehren.
    pause
    exit /b 1
)

:: Create logs dir
if not exist "logs" mkdir logs

:: Kill any existing instances
echo [1/3] Alte Prozesse beenden...
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Frontend" >nul 2>&1
timeout /t 2 /nobreak >nul

:: Start Backend
echo [2/3] Backend starten (Port 8001)...
start "Darts Backend" /MIN cmd /c "cd /d %~dp0backend && python -m uvicorn server:app --host 0.0.0.0 --port 8001 --reload > ..\logs\backend.log 2>&1"
echo   [OK] Backend gestartet (Log: logs\backend.log)

:: Wait for backend
echo        Warte auf Backend...
timeout /t 5 /nobreak >nul

:: Quick health check
curl -sf http://localhost:8001/api/health >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Backend antwortet noch nicht, warte weitere 10s...
    timeout /t 10 /nobreak >nul
    curl -sf http://localhost:8001/api/health >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo   [WARN] Backend nicht erreichbar. Pruefe logs\backend.log
    ) else (
        echo   [OK]   Backend laeuft!
    )
) else (
    echo   [OK]   Backend laeuft!
)

:: Start Frontend
echo [3/3] Frontend starten (Port 3000)...
start "Darts Frontend" /MIN cmd /c "cd /d %~dp0frontend && set PORT=3000 && set BROWSER=none && call yarn start > ..\logs\frontend.log 2>&1"
echo   [OK] Frontend gestartet (Log: logs\frontend.log)

:: Wait for frontend compile
echo        Warte auf Frontend-Kompilierung...
timeout /t 15 /nobreak >nul

echo.
echo ================================================================
echo.
echo   Darts Kiosk laeuft!
echo.
echo   Admin-Panel:  http://localhost:3000/admin
echo   Kiosk:        http://localhost:3000/kiosk/BOARD-1
echo   Setup-Wizard: http://localhost:3000/setup
echo   Backend-API:  http://localhost:8001/api/health
echo.
echo   Beim ersten Start: http://localhost:3000/setup oeffnen
echo   und Admin-Passwort, Staff-PIN und Branding einrichten.
echo.
echo   Logs:
echo     Backend:  logs\backend.log
echo     Frontend: logs\frontend.log
echo.
echo   Zum Beenden: stop.bat ausfuehren
echo                oder dieses Fenster schliessen
echo.
echo ================================================================
echo.

:: Open browser
timeout /t 3 /nobreak >nul
start "" http://localhost:3000/setup

:: Keep window open
echo Druecken Sie eine Taste zum Beenden aller Dienste...
pause >nul

:: Cleanup on exit
taskkill /F /FI "WINDOWTITLE eq Darts Backend" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq Darts Frontend" >nul 2>&1
echo Alle Dienste beendet.
