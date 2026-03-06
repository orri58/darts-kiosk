@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Windows Setup
echo.
echo ================================================================
echo   DARTS KIOSK - Einmalige Einrichtung
echo ================================================================
echo.

:: Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Python nicht gefunden! Bitte erst check_requirements.bat ausfuehren.
    pause
    exit /b 1
)

:: Check Node
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Node.js nicht gefunden! Bitte erst check_requirements.bat ausfuehren.
    pause
    exit /b 1
)

:: Create data directories
echo [1/6] Verzeichnisse erstellen...
if not exist "data" mkdir data
if not exist "data\db" mkdir data\db
if not exist "data\assets" mkdir data\assets
if not exist "data\assets\sounds" mkdir data\assets\sounds
if not exist "data\backups" mkdir data\backups
if not exist "logs" mkdir logs
echo   [OK]

:: Create .env if not exists
echo [2/6] Backend-Konfiguration pruefen...
if not exist "backend\.env" (
    echo   Erstelle backend\.env ...
    (
        echo DATABASE_URL=sqlite+aiosqlite:///./data/db/darts.sqlite
        echo SYNC_DATABASE_URL=sqlite:///./data/db/darts.sqlite
        echo DATA_DIR=./data
        echo JWT_SECRET=darts-local-dev-secret-change-in-production
        echo AGENT_SECRET=agent-local-dev-secret
        echo CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
        echo MODE=STANDALONE
        echo BOARD_ID=BOARD-1
        echo AUTODARTS_URL=https://play.autodarts.io
        echo AUTODARTS_MOCK=false
    ) > backend\.env
    echo   [OK] backend\.env erstellt
) else (
    echo   [OK] backend\.env existiert bereits
)

:: Create frontend .env
if not exist "frontend\.env" (
    echo   Erstelle frontend\.env ...
    echo REACT_APP_BACKEND_URL=http://localhost:8001> frontend\.env
    echo   [OK] frontend\.env erstellt
) else (
    echo   [OK] frontend\.env existiert bereits
)

:: Install backend dependencies
echo.
echo [3/6] Python-Pakete installieren (kann 2-3 Min dauern)...
cd backend
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt 2>&1 | findstr /I "error fail" && (
    echo   [WARN] Einige Pakete hatten Probleme, versuche Basis-Pakete...
)
:: Install core packages explicitly in case full requirements fails
python -m pip install fastapi uvicorn sqlalchemy aiosqlite pydantic python-jose passlib bcrypt python-multipart python-dotenv apscheduler slowapi pillow qrcode zeroconf websockets >nul 2>&1
echo   [OK] Backend-Pakete installiert
cd ..

:: Install Playwright
echo.
echo [4/6] Playwright-Browser installieren (kann 3-5 Min dauern)...
cd backend
python -m playwright install chromium 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Playwright konnte nicht installiert werden
    echo          Autodarts-Integration wird nicht funktionieren
    echo          Manuelle Installation: python -m playwright install chromium
) else (
    echo   [OK] Playwright Chromium installiert
)
cd ..

:: Install frontend dependencies
echo.
echo [5/6] Frontend-Pakete installieren (kann 3-5 Min dauern)...
cd frontend

:: Install yarn if not available
call yarn --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   yarn nicht gefunden, installiere via npm...
    call npm install -g yarn >nul 2>&1
)

call yarn install --frozen-lockfile 2>&1 || call yarn install 2>&1
echo   [OK] Frontend-Pakete installiert
cd ..

:: Summary
echo.
echo [6/6] Fertig!
echo.
echo ================================================================
echo   SETUP ABGESCHLOSSEN!
echo.
echo   Naechster Schritt: start.bat ausfuehren
echo ================================================================
echo.
pause
