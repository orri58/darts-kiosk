@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Darts Kiosk - Windows Setup
cd /d %~dp0
echo.
echo ================================================================
echo   DARTS KIOSK - Einmalige Einrichtung
echo ================================================================
echo.

:: ---------------------------------------------------------------
:: Pre-checks
:: ---------------------------------------------------------------
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Python nicht gefunden! Bitte erst check_requirements.bat ausfuehren.
    pause
    exit /b 1
)

node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] Node.js nicht gefunden! Bitte erst check_requirements.bat ausfuehren.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------
:: 1. Create data directories
:: ---------------------------------------------------------------
echo [1/7] Verzeichnisse erstellen...
if not exist "data" mkdir data
if not exist "data\db" mkdir data\db
if not exist "data\assets" mkdir data\assets
if not exist "data\assets\sounds" mkdir data\assets\sounds
if not exist "data\backups" mkdir data\backups
if not exist "logs" mkdir logs
echo   [OK]

:: ---------------------------------------------------------------
:: 2. Create .env files
:: ---------------------------------------------------------------
echo [2/7] Konfiguration pruefen...
if not exist "backend\.env" (
    echo   Erstelle backend\.env ...
    (
        echo DATABASE_URL=sqlite+aiosqlite:///./data/db/darts.sqlite
        echo SYNC_DATABASE_URL=sqlite:///./data/db/darts.sqlite
        echo DATA_DIR=./data
        echo JWT_SECRET=darts-local-dev-secret-change-in-production
        echo AGENT_SECRET=agent-local-dev-secret
        echo CORS_ORIGINS=*
        echo MODE=STANDALONE
        echo BOARD_ID=BOARD-1
        echo AUTODARTS_URL=https://play.autodarts.io
        echo AUTODARTS_MODE=observer
        echo AUTODARTS_HEADLESS=false
        echo AUTODARTS_MOCK=false
    ) > backend\.env
    echo   [OK] backend\.env erstellt
) else (
    echo   [OK] backend\.env existiert bereits
)

if not exist "frontend\.env" (
    echo   Erstelle frontend\.env ...
    >frontend\.env echo REACT_APP_BACKEND_URL=http://localhost:8001
    echo   [OK] frontend\.env erstellt
) else (
    echo   [OK] frontend\.env existiert bereits
)

:: ---------------------------------------------------------------
:: 3. Create Python venv
:: ---------------------------------------------------------------
echo.
echo [3/7] Python-Umgebung erstellen...
if not exist ".venv" (
    echo   Erstelle virtuelle Umgebung (.venv)...
    python -m venv .venv
    if %ERRORLEVEL% NEQ 0 (
        echo   [FAIL] venv konnte nicht erstellt werden!
        echo          Bitte Python mit venv-Modul installieren.
        pause
        exit /b 1
    )
    echo   [OK] .venv erstellt
) else (
    echo   [OK] .venv existiert bereits
)

:: Activate venv
call .venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] .venv konnte nicht aktiviert werden!
    pause
    exit /b 1
)
echo   [OK] .venv aktiviert

:: ---------------------------------------------------------------
:: 4. Install backend dependencies (in venv)
:: ---------------------------------------------------------------
echo.
echo [4/7] Python-Pakete installieren (kann 2-3 Min dauern)...

:: Upgrade pip first
python -m pip install --upgrade pip >nul 2>&1

:: Install greenlet first (critical dependency)
echo   Installiere greenlet (kritische Abhaengigkeit)...
python -m pip install greenlet 2>&1 | findstr /V /I "already satisfied"

:: Validate greenlet import
python -c "import greenlet; print(f'  [OK] greenlet {greenlet.__version__} funktioniert')" 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   ================================================================
    echo   [FAIL] greenlet konnte nicht geladen werden!
    echo.
    echo   Dies liegt meist an fehlender Microsoft Visual C++ Redistributable.
    echo   Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    echo   Nach Installation VC++ Redistributable: setup_windows.bat erneut starten.
    echo   ================================================================
    pause
    exit /b 1
)

:: Install all requirements
echo   Installiere restliche Pakete...
cd backend
python -m pip install -r requirements.txt 2>&1 | findstr /I "error" && (
    echo   [WARN] Einige Pakete hatten Probleme
)
cd /d %~dp0

:: Fallback: ensure critical packages
python -m pip install fastapi uvicorn sqlalchemy aiosqlite pydantic python-jose passlib bcrypt python-multipart python-dotenv apscheduler slowapi pillow qrcode zeroconf websockets playwright >nul 2>&1
echo   [OK] Backend-Pakete installiert

:: ---------------------------------------------------------------
:: 5. Validate critical imports
:: ---------------------------------------------------------------
echo.
echo [5/7] Kritische Abhaengigkeiten validieren...
set "IMPORT_OK=1"

python -c "import greenlet" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] greenlet
    set "IMPORT_OK=0"
) else (
    echo   [OK]   greenlet
)

python -c "import sqlalchemy" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] sqlalchemy
    set "IMPORT_OK=0"
) else (
    echo   [OK]   sqlalchemy
)

python -c "import uvicorn" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] uvicorn
    set "IMPORT_OK=0"
) else (
    echo   [OK]   uvicorn
)

python -c "import fastapi" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] fastapi
    set "IMPORT_OK=0"
) else (
    echo   [OK]   fastapi
)

if "!IMPORT_OK!"=="0" (
    echo.
    echo   [FAIL] Einige kritische Pakete fehlen!
    echo          Bitte Fehlermeldungen oben pruefen.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------
:: 6. Install Playwright browser
:: ---------------------------------------------------------------
echo.
echo [6/7] Playwright-Browser installieren (kann 3-5 Min dauern)...
python -m playwright install chromium 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Playwright konnte nicht installiert werden
    echo          Autodarts-Integration wird nicht funktionieren
    echo          Manuelle Installation: .venv\Scripts\python -m playwright install chromium
) else (
    echo   [OK] Playwright Chromium installiert
)

:: ---------------------------------------------------------------
:: 7. Install frontend dependencies
:: ---------------------------------------------------------------
echo.
echo [7/7] Frontend-Pakete installieren (kann 3-5 Min dauern)...
cd frontend

call yarn --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   yarn nicht gefunden, installiere via npm...
    call npm install -g yarn >nul 2>&1
)

call yarn install --frozen-lockfile 2>&1 || call yarn install 2>&1
echo   [OK] Frontend-Pakete installiert
cd /d %~dp0

:: ---------------------------------------------------------------
:: Summary
:: ---------------------------------------------------------------
echo.
echo ================================================================
echo   SETUP ABGESCHLOSSEN!
echo.
echo   Naechster Schritt: start.bat ausfuehren
echo.
echo   Hinweise:
echo   - Python-Pakete sind in .venv installiert
echo   - start.bat aktiviert die .venv automatisch
echo   - Bei Problemen: check_requirements.bat erneut ausfuehren
echo ================================================================
echo.
pause
