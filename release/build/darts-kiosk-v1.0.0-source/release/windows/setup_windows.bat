@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Windows Setup
cd /d "%~dp0"
echo.
echo ================================================================
echo   DARTS KIOSK - Einmalige Einrichtung
echo ================================================================
echo.

REM === Pre-checks ===
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

REM === 1. Directories ===
echo [1/7] Verzeichnisse erstellen...
if not exist "data" mkdir data
if not exist "data\db" mkdir data\db
if not exist "data\assets" mkdir data\assets
if not exist "data\assets\sounds" mkdir data\assets\sounds
if not exist "data\backups" mkdir data\backups
if not exist "logs" mkdir logs
echo   [OK]

REM === 2. Backend .env ===
echo [2/7] Konfiguration pruefen...
if exist "backend\.env" (
    echo   [OK] backend\.env existiert bereits
    goto check_frontend_env
)
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
    echo BOARD_ID=BOARD-1
) > backend\.env
echo   [OK] backend\.env erstellt

:check_frontend_env
if exist "frontend\.env" (
    echo   [OK] frontend\.env existiert bereits
    goto create_venv
)
>frontend\.env echo REACT_APP_BACKEND_URL=http://localhost:8001
echo   [OK] frontend\.env erstellt

:create_venv
REM === 3. Python venv ===
echo.
echo [3/7] Python-Umgebung erstellen...
if exist ".venv\Scripts\activate.bat" (
    echo   [OK] .venv existiert bereits
    goto activate_venv
)
echo   Erstelle virtuelle Umgebung (.venv)...
python -m venv .venv
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] venv konnte nicht erstellt werden!
    pause
    exit /b 1
)
echo   [OK] .venv erstellt

:activate_venv
call .venv\Scripts\activate.bat
echo   [OK] .venv aktiviert

REM === 4. Backend dependencies ===
echo.
echo [4/7] Python-Pakete installieren (kann 2-3 Min dauern)...
python -m pip install --upgrade pip >nul 2>&1

echo   Installiere greenlet (kritische Abhaengigkeit)...
python -m pip install greenlet 2>&1 | findstr /V /I "already satisfied"

REM Validate greenlet
python -c "import greenlet; print('  [OK] greenlet', greenlet.__version__, 'funktioniert')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo   [FAIL] greenlet konnte nicht geladen werden!
    echo.
    echo   Dies liegt meist an fehlender Microsoft Visual C++ Redistributable.
    echo   Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    echo   Nach Installation VC++ Redistributable: setup_windows.bat erneut starten.
    pause
    exit /b 1
)

echo   Installiere restliche Pakete...
cd backend
python -m pip install -r requirements.txt 2>&1 | findstr /I "error"
cd /d "%~dp0"

REM Fallback for critical packages
python -m pip install fastapi uvicorn sqlalchemy aiosqlite pydantic python-jose passlib bcrypt python-multipart python-dotenv apscheduler slowapi pillow qrcode zeroconf websockets playwright >nul 2>&1
echo   [OK] Backend-Pakete installiert

REM === 5. Validate critical imports ===
echo.
echo [5/7] Kritische Abhaengigkeiten validieren...
set IMPORT_FAIL=0

python -c "import greenlet" 2>nul
if %ERRORLEVEL% NEQ 0 ( echo   [FAIL] greenlet & set IMPORT_FAIL=1 ) else ( echo   [OK]   greenlet )

python -c "import sqlalchemy" 2>nul
if %ERRORLEVEL% NEQ 0 ( echo   [FAIL] sqlalchemy & set IMPORT_FAIL=1 ) else ( echo   [OK]   sqlalchemy )

python -c "import uvicorn" 2>nul
if %ERRORLEVEL% NEQ 0 ( echo   [FAIL] uvicorn & set IMPORT_FAIL=1 ) else ( echo   [OK]   uvicorn )

python -c "import fastapi" 2>nul
if %ERRORLEVEL% NEQ 0 ( echo   [FAIL] fastapi & set IMPORT_FAIL=1 ) else ( echo   [OK]   fastapi )

if %IMPORT_FAIL% NEQ 0 (
    echo.
    echo   [FAIL] Einige kritische Pakete fehlen!
    pause
    exit /b 1
)

REM === 6. Playwright ===
echo.
echo [6/7] Playwright-Browser installieren (kann 3-5 Min dauern)...
python -m playwright install chromium 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Playwright konnte nicht installiert werden
    echo          Autodarts-Integration wird nicht funktionieren
) else (
    echo   [OK] Playwright Chromium installiert
)

REM Check for Google Chrome (used as channel="chrome" for persistent login)
set CHROME_FOUND=0
for %%G in (
    "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    "%LocalAppData%\Google\Chrome\Application\chrome.exe"
) do (
    if exist %%G set CHROME_FOUND=1
)
if %CHROME_FOUND%==1 (
    echo   [OK] Google Chrome gefunden (fuer persistente Autodarts-Anmeldung)
) else (
    echo   [WARN] Google Chrome nicht installiert!
    echo          Autodarts-Observer benoetigt Chrome fuer persistente Anmeldung.
    echo          Download: https://www.google.com/chrome/
)

REM Validate Playwright browser can launch
echo   Teste Playwright Browser-Start...
python -c "import asyncio; asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy()); from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(headless=True); b.close(); p.stop(); print('  [OK] Playwright Browser startet erfolgreich')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] Playwright Browser-Start fehlgeschlagen
    echo          Playwright-Abhaengigkeiten installieren...
    python -m playwright install-deps chromium 2>nul
) else (
    echo   [OK] Playwright Browser-Validierung bestanden
)

REM === 7. Frontend ===
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
cd /d "%~dp0"

REM === Done ===
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
