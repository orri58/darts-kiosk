@echo off
chcp 65001 >nul 2>&1
title Darts Kiosk - Voraussetzungen pruefen
cd /d %~dp0
echo.
echo ================================================================
echo   DARTS KIOSK - Voraussetzungen pruefen
echo ================================================================
echo.

set "ERRORS=0"
set "WARNS=0"

:: ---------------------------------------------------------------
:: 1. Python
:: ---------------------------------------------------------------
echo [1/4] Python pruefen...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] Python nicht gefunden!
    echo          Download: https://www.python.org/downloads/
    echo          WICHTIG: Bei Installation "Add to PATH" ankreuzen!
    set "ERRORS=1"
) else (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set "PYVER=%%i"
    echo   [OK]   Python %PYVER%

    :: Check Python version >= 3.11
    for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
        if %%a LSS 3 (
            echo   [FAIL] Python 3.11+ erforderlich! Installiert: %PYVER%
            set "ERRORS=1"
        ) else if %%a EQU 3 if %%b LSS 11 (
            echo   [FAIL] Python 3.11+ erforderlich! Installiert: %PYVER%
            set "ERRORS=1"
        )
    )
)

:: pip
pip --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] pip nicht gefunden, wird mit setup installiert
    set "WARNS=1"
) else (
    echo   [OK]   pip vorhanden
)

:: ---------------------------------------------------------------
:: 2. Node.js — Node 20 LTS empfohlen
:: ---------------------------------------------------------------
echo.
echo [2/4] Node.js pruefen...
node --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [FAIL] Node.js nicht gefunden!
    echo          Download: https://nodejs.org/
    echo          WICHTIG: Node 20 LTS installieren (NICHT Node 25+)
    set "ERRORS=1"
) else (
    for /f %%i in ('node --version 2^>^&1') do set "NODEVER=%%i"
    echo   [INFO] Node.js %NODEVER%

    :: Extract major version number (strip leading 'v')
    set "NODEMAJOR="
    for /f "tokens=1 delims=." %%a in ("%NODEVER:~1%") do set "NODEMAJOR=%%a"

    if defined NODEMAJOR (
        if !NODEMAJOR! GEQ 23 (
            echo   [WARN] Node %NODEVER% ist zu neu und moeglicherweise inkompatibel!
            echo          Empfohlen: Node 20 LTS
            echo          Download: https://nodejs.org/en/download/
            echo          Waehle "LTS" ^(Long Term Support^), NICHT "Current"
            set "WARNS=1"
        ) else if !NODEMAJOR! LSS 18 (
            echo   [FAIL] Node %NODEVER% ist zu alt! Mindestens Node 18 erforderlich.
            echo          Download: https://nodejs.org/ — Node 20 LTS empfohlen
            set "ERRORS=1"
        ) else (
            echo   [OK]   Node.js %NODEVER% — kompatibel
        )
    )
)

:: ---------------------------------------------------------------
:: 3. Paketmanager (yarn / npm)
:: ---------------------------------------------------------------
echo.
echo [3/4] Paketmanager pruefen...
call yarn --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    npm --version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo   [FAIL] Weder yarn noch npm gefunden!
        set "ERRORS=1"
    ) else (
        echo   [OK]   npm vorhanden (yarn wird bei Setup installiert)
    )
) else (
    echo   [OK]   yarn vorhanden
)

:: ---------------------------------------------------------------
:: 4. Microsoft Visual C++ Redistributable
:: ---------------------------------------------------------------
echo.
echo [4/4] Microsoft Visual C++ Redistributable pruefen...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo   [WARN] VC++ Redistributable x64 moeglicherweise nicht installiert!
    echo          Wird fuer greenlet/SQLAlchemy benoetigt.
    echo          Download: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo          Falls Backend-Start fehlschlaegt, bitte installieren.
    set "WARNS=1"
) else (
    echo   [OK]   VC++ Redistributable x64 vorhanden
)

:: ---------------------------------------------------------------
:: Summary
:: ---------------------------------------------------------------
echo.
echo ================================================================
if %ERRORS% NEQ 0 (
    echo   FEHLER gefunden! Bitte fehlende Software installieren.
    echo   Danach erneut ausfuehren.
) else if %WARNS% NEQ 0 (
    echo   WARNUNGEN vorhanden — Setup kann trotzdem versucht werden.
    echo   Bei Problemen bitte die Warnungen oben beachten.
) else (
    echo   ALLES OK — Bereit fuer setup_windows.bat
)
echo.
echo   Empfohlene Versionen:
echo     Python:  3.11 oder 3.12  (python.org)
echo     Node.js: 20 LTS          (nodejs.org — LTS waehlen!)
echo     VC++:    x64 Redistributable (aka.ms/vs/17/release/vc_redist.x64.exe)
echo ================================================================
echo.
pause
