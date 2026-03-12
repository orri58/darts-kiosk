@echo off
REM ============================================================================
REM  DARTS KIOSK - Automated Installer v3.0.2
REM  Converts a Windows PC into a locked-down Darts Kiosk appliance.
REM ============================================================================
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Darts Kiosk - Installer v3.0.2

REM === Default Configuration ===
set "INSTALL_DIR=C:\DartsKiosk"
set "KIOSK_USER=DartsKiosk"
set "KIOSK_PASS=darts2024"
set "BOARD_ID=BOARD-1"
set "BACKEND_PORT=8001"
set "AUTODARTS_URL=https://play.autodarts.io"

echo.
echo ================================================================
echo   DARTS KIOSK - AUTOMATED INSTALLER v3.0.2
echo ================================================================
echo.

REM ============================================================================
REM  STEP 0 - Administrator Check
REM ============================================================================
echo [Step 0/12] Administrator-Rechte pruefen...
net session >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FEHLER] Dieses Script muss als Administrator ausgefuehrt werden!
    echo          Rechtsklick auf setup_kiosk.bat -^> "Als Administrator ausfuehren"
    echo.
    pause
    exit /b 1
)
echo   [OK] Administrator-Rechte vorhanden

REM ============================================================================
REM  SOURCE ROOT DETECTION
REM ============================================================================
set "SCRIPT_DIR=%~dp0"
if "!SCRIPT_DIR:~-1!"=="\" set "SCRIPT_DIR=!SCRIPT_DIR:~0,-1!"
set "SOURCE_DIR=!SCRIPT_DIR!"

REM If running from the kiosk subfolder, go up one level to project root
if /i "!SOURCE_DIR:~-6!"=="\kiosk" (
    for %%I in ("!SOURCE_DIR!\..") do set "SOURCE_DIR=%%~fI"
)

echo.
echo   [DEBUG] SCRIPT_DIR  = !SCRIPT_DIR!
echo   [DEBUG] SOURCE_DIR  = !SOURCE_DIR!
echo   [DEBUG] INSTALL_DIR = !INSTALL_DIR!
echo.

REM Verify source contains backend
if not exist "!SOURCE_DIR!\backend" (
    echo [FEHLER] backend\ nicht gefunden in !SOURCE_DIR!
    echo          Bitte setup_kiosk.bat aus dem entpackten Release-Ordner starten.
    pause
    exit /b 1
)
echo   [OK] Quellverzeichnis validiert: !SOURCE_DIR!

REM ============================================================================
REM  STEP 1 - Configuration
REM ============================================================================
echo.
echo [Step 1/12] Konfiguration
echo.
echo   Standard-Werte:
echo     Installationspfad:  %INSTALL_DIR%
echo     Kiosk-Benutzer:     %KIOSK_USER%
echo     Board-ID:           %BOARD_ID%
echo     Backend-Port:       %BACKEND_PORT%
echo.

set /p "CONFIRM_DEFAULTS=Standard-Konfiguration verwenden? (J/N) [J]: "
if /i "!CONFIRM_DEFAULTS!"=="" set "CONFIRM_DEFAULTS=J"

if /i not "!CONFIRM_DEFAULTS!"=="J" (
    set /p "INSTALL_DIR=Installationspfad [%INSTALL_DIR%]: "
    if "!INSTALL_DIR!"=="" set "INSTALL_DIR=C:\DartsKiosk"
    set /p "KIOSK_USER=Kiosk-Benutzername [%KIOSK_USER%]: "
    if "!KIOSK_USER!"=="" set "KIOSK_USER=DartsKiosk"
    set /p "BOARD_ID=Board-ID [%BOARD_ID%]: "
    if "!BOARD_ID!"=="" set "BOARD_ID=BOARD-1"
    set /p "BACKEND_PORT=Backend-Port [%BACKEND_PORT%]: "
    if "!BACKEND_PORT!"=="" set "BACKEND_PORT=8001"
)

set /p "KIOSK_PASS=Kiosk-Passwort (fuer Auto-Login + Maintenance): "
if "!KIOSK_PASS!"=="" set "KIOSK_PASS=darts2024"

echo.
echo   Konfiguration:
echo     Installationspfad:  !INSTALL_DIR!
echo     Kiosk-Benutzer:     !KIOSK_USER!
echo     Board-ID:           !BOARD_ID!
echo     Backend-Port:       !BACKEND_PORT!
echo.
set /p "PROCEED=Installation starten? (J/N) [J]: "
if /i "!PROCEED!"=="" set "PROCEED=J"
if /i not "!PROCEED!"=="J" (
    echo Abgebrochen.
    pause
    exit /b 0
)

REM ============================================================================
REM  STEP 2 - System Requirements
REM ============================================================================
echo.
echo [Step 2/12] Systemanforderungen pruefen...

REM Check Python and store full path
set "PYTHON_PATH="
for /f "tokens=*" %%p in ('where python 2^>nul') do (
    if not defined PYTHON_PATH set "PYTHON_PATH=%%p"
)
if defined PYTHON_PATH (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo   [OK] %%v
    echo   [DEBUG] Python: !PYTHON_PATH!
) else (
    echo   [FEHLER] Python nicht gefunden!
    echo            Bitte Python 3.11+ installieren: https://python.org/downloads
    pause
    exit /b 1
)

REM Check Chrome
set "CHROME_PATH="
for %%G in (
    "%ProgramFiles%\Google\Chrome\Application\chrome.exe"
    "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
    "%LocalAppData%\Google\Chrome\Application\chrome.exe"
) do (
    if exist "%%~G" (
        if not defined CHROME_PATH set "CHROME_PATH=%%~G"
    )
)
if defined CHROME_PATH (
    echo   [OK] Chrome gefunden: !CHROME_PATH!
) else (
    echo   [WARN] Chrome nicht gefunden - wird nach Installation benoetigt
    echo          Download: https://google.com/chrome
)

REM Check curl
curl --version >nul 2>&1
if !ERRORLEVEL!==0 (
    echo   [OK] curl verfuegbar
) else (
    echo   [WARN] curl nicht gefunden - Health-Check eingeschraenkt
)

REM ============================================================================
REM  STEP 3 - Create Installation Directory + Copy Files
REM ============================================================================
echo.
echo [Step 3/12] Darts-System installieren nach !INSTALL_DIR!...
echo   [DEBUG] Kopiere von SOURCE_DIR=!SOURCE_DIR!

if not exist "!INSTALL_DIR!" mkdir "!INSTALL_DIR!"
mkdir "!INSTALL_DIR!\data\db" 2>nul
mkdir "!INSTALL_DIR!\data\assets" 2>nul
mkdir "!INSTALL_DIR!\data\backups" 2>nul
mkdir "!INSTALL_DIR!\data\downloads" 2>nul
mkdir "!INSTALL_DIR!\data\chrome_profile\!BOARD_ID!" 2>nul
mkdir "!INSTALL_DIR!\data\kiosk_ui_profile" 2>nul
mkdir "!INSTALL_DIR!\logs" 2>nul

REM Copy backend
if exist "!SOURCE_DIR!\backend" (
    xcopy "!SOURCE_DIR!\backend" "!INSTALL_DIR!\backend\" /E /I /Y /Q >nul
    echo   [OK] Backend kopiert
) else (
    echo   [FEHLER] backend\ nicht gefunden in !SOURCE_DIR!
    pause
    exit /b 1
)

REM Copy frontend
if exist "!SOURCE_DIR!\frontend" (
    xcopy "!SOURCE_DIR!\frontend" "!INSTALL_DIR!\frontend\" /E /I /Y /Q >nul
    echo   [OK] Frontend kopiert
) else (
    echo   [WARN] frontend\ nicht gefunden - uebersprungen
)

REM Copy runtime scripts from project root
for %%F in (run_backend.py credits_overlay.py _run_backend.bat start.bat stop.bat updater.py VERSION) do (
    if exist "!SOURCE_DIR!\%%F" (
        copy "!SOURCE_DIR!\%%F" "!INSTALL_DIR!\%%F" /Y >nul
    )
)
echo   [OK] Scripts kopiert

REM Copy kiosk-specific files (from kiosk subfolder or same dir as script)
for %%F in (kiosk_shell.vbs darts_launcher.bat maintenance.bat uninstall_kiosk.bat README_KIOSK.md) do (
    if exist "!SOURCE_DIR!\kiosk\%%F" (
        copy "!SOURCE_DIR!\kiosk\%%F" "!INSTALL_DIR!\%%F" /Y >nul
    ) else if exist "!SCRIPT_DIR!\%%F" (
        copy "!SCRIPT_DIR!\%%F" "!INSTALL_DIR!\%%F" /Y >nul
    )
)
echo   [OK] Kiosk-Dateien kopiert

REM ============================================================================
REM  STEP 4 - Python Virtual Environment
REM ============================================================================
echo.
echo [Step 4/12] Python-Umgebung einrichten...

if not exist "!INSTALL_DIR!\.venv\Scripts\activate.bat" (
    python -m venv "!INSTALL_DIR!\.venv"
    echo   [OK] Virtual Environment erstellt
) else (
    echo   [OK] Virtual Environment existiert bereits
)

call "!INSTALL_DIR!\.venv\Scripts\activate.bat"

pip install -r "!INSTALL_DIR!\backend\requirements.txt" -q 2>nul
if !ERRORLEVEL!==0 (
    echo   [OK] Python-Pakete installiert
) else (
    echo   [WARN] Einige Pakete konnten nicht installiert werden
)

REM Install Playwright browsers
python -m playwright install chromium >nul 2>&1
echo   [OK] Playwright Chromium installiert

REM ============================================================================
REM  STEP 5 - Create .env Configuration
REM ============================================================================
echo.
echo [Step 5/12] Konfigurationsdateien erstellen...

REM Backend .env (only if not exists - preserve user config)
if not exist "!INSTALL_DIR!\backend\.env" (
    (
        echo DATABASE_URL=sqlite+aiosqlite:///./data/db/darts.sqlite
        echo SYNC_DATABASE_URL=sqlite:///./data/db/darts.sqlite
        echo DATA_DIR=./data
        echo JWT_SECRET=darts-kiosk-!RANDOM!!RANDOM!-secret
        echo AGENT_SECRET=agent-kiosk-!RANDOM!-secret
        echo CORS_ORIGINS=*
        echo MODE=STANDALONE
        echo BOARD_ID=!BOARD_ID!
        echo AUTODARTS_URL=!AUTODARTS_URL!
        echo AUTODARTS_MODE=observer
        echo AUTODARTS_HEADLESS=false
        echo AUTODARTS_MOCK=false
        echo UPDATE_CHECK_ENABLED=true
        echo UPDATE_CHECK_INTERVAL_HOURS=24
    ) > "!INSTALL_DIR!\backend\.env"
    echo   [OK] backend\.env erstellt
) else (
    echo   [OK] backend\.env existiert bereits (nicht ueberschrieben)
)

REM Frontend .env
if not exist "!INSTALL_DIR!\frontend\.env" (
    echo REACT_APP_BACKEND_URL=http://localhost:!BACKEND_PORT!> "!INSTALL_DIR!\frontend\.env"
    echo   [OK] frontend\.env erstellt
)

REM Resolve full python.exe path inside venv for scheduled task
set "VENV_PYTHON=!INSTALL_DIR!\.venv\Scripts\python.exe"
if not exist "!VENV_PYTHON!" set "VENV_PYTHON=!PYTHON_PATH!"

REM Write kiosk config (read by launcher + maintenance + shell)
(
    echo REM === Darts Kiosk Configuration (auto-generated by installer v3.0.2) ===
    echo set "INSTALL_DIR=!INSTALL_DIR!"
    echo set "KIOSK_USER=!KIOSK_USER!"
    echo set "BOARD_ID=!BOARD_ID!"
    echo set "BACKEND_PORT=!BACKEND_PORT!"
    echo set "CHROME_PATH=!CHROME_PATH!"
    echo set "PYTHON_PATH=!PYTHON_PATH!"
    echo set "VENV_PYTHON=!VENV_PYTHON!"
    echo set "KIOSK_DEBUG=0"
) > "!INSTALL_DIR!\kiosk_config.bat"
echo   [OK] kiosk_config.bat erstellt

REM Store maintenance password hash (PowerShell SHA256)
for /f "tokens=*" %%h in ('powershell -NoProfile -Command "[BitConverter]::ToString([System.Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes('!KIOSK_PASS!'))).Replace('-','')"') do set "PASS_HASH=%%h"
echo !PASS_HASH!> "!INSTALL_DIR!\data\.maintenance_key"
echo   [OK] Maintenance-Passwort gespeichert

REM ============================================================================
REM  STEP 6 - Create Kiosk User
REM ============================================================================
echo.
echo [Step 6/12] Kiosk-Benutzer erstellen...

net user "!KIOSK_USER!" >nul 2>&1
if !ERRORLEVEL!==0 (
    echo   [OK] Benutzer '!KIOSK_USER!' existiert bereits
    net user "!KIOSK_USER!" "!KIOSK_PASS!" >nul 2>&1
    echo   [OK] Passwort aktualisiert
) else (
    net user "!KIOSK_USER!" "!KIOSK_PASS!" /add /comment:"Darts Kiosk Auto-Login Account" >nul
    net localgroup Users "!KIOSK_USER!" /add >nul 2>&1
    echo   [OK] Benutzer '!KIOSK_USER!' erstellt
)

REM Password never expires
wmic useraccount where "name='!KIOSK_USER!'" set PasswordExpires=false >nul 2>&1
echo   [OK] Passwort-Ablauf deaktiviert

REM ============================================================================
REM  STEP 7 - Grant File Permissions
REM ============================================================================
echo.
echo [Step 7/12] Dateiberechtigungen setzen...

icacls "!INSTALL_DIR!" /grant "!KIOSK_USER!:(OI)(CI)F" /T /Q >nul 2>&1
echo   [OK] !KIOSK_USER! hat Vollzugriff auf !INSTALL_DIR!

REM ============================================================================
REM  STEP 8 - Force-Create User Profile + Apply Hardening
REM ============================================================================
echo.
echo [Step 8/12] Kiosk-Haertung (Profil + Richtlinien)...

REM Force-create the kiosk user profile so we can load NTUSER.DAT
echo   Erstelle Benutzerprofil fuer !KIOSK_USER!...
powershell -NoProfile -Command "$pw = ConvertTo-SecureString '!KIOSK_PASS!' -AsPlainText -Force; $cred = New-Object System.Management.Automation.PSCredential('%COMPUTERNAME%\!KIOSK_USER!', $pw); try { Start-Process cmd.exe -ArgumentList '/c exit' -Credential $cred -Wait -NoNewWindow -ErrorAction Stop; Write-Host '  [OK] Profil erstellt' } catch { Write-Host '  [WARN] Profil-Erstellung:' $_.Exception.Message }"

REM Small delay for profile creation
timeout /t 2 /nobreak >nul

REM Get SID of kiosk user
set "KIOSK_SID="
for /f "tokens=2 delims==" %%s in ('wmic useraccount where "name='!KIOSK_USER!'" get sid /value 2^>nul ^| findstr /i "SID"') do (
    set "KIOSK_SID=%%s"
)

if not defined KIOSK_SID (
    echo   [WARN] SID nicht gefunden - Haertung uebersprungen
    goto :skip_hardening
)
echo   [DEBUG] Kiosk-User SID: !KIOSK_SID!

REM Find profile path
set "KIOSK_PROFILE="
for /f "tokens=2*" %%a in ('reg query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\!KIOSK_SID!" /v ProfileImagePath 2^>nul ^| findstr /i "ProfileImagePath"') do (
    set "KIOSK_PROFILE=%%b"
)

set "HKU_PATH=HKU\DartsKiosk_Temp"
set "POLICY_LOADED=0"

if defined KIOSK_PROFILE (
    echo   [DEBUG] Profil-Pfad: !KIOSK_PROFILE!
    if exist "!KIOSK_PROFILE!\NTUSER.DAT" (
        reg load "!HKU_PATH!" "!KIOSK_PROFILE!\NTUSER.DAT" >nul 2>&1
        if !ERRORLEVEL!==0 (
            set "POLICY_LOADED=1"
            echo   [OK] NTUSER.DAT geladen
        ) else (
            echo   [WARN] NTUSER.DAT konnte nicht geladen werden (User eingeloggt?)
        )
    ) else (
        echo   [WARN] NTUSER.DAT nicht gefunden in !KIOSK_PROFILE!
    )
) else (
    echo   [WARN] Profil-Pfad nicht gefunden
)

if !POLICY_LOADED!==1 (
    set "POL=!HKU_PATH!\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies"

    REM Disable Task Manager
    reg add "!POL!\System" /v DisableTaskMgr /t REG_DWORD /d 1 /f >nul
    echo   [OK] Task-Manager deaktiviert

    REM Disable Lock Workstation
    reg add "!POL!\System" /v DisableLockWorkstation /t REG_DWORD /d 1 /f >nul
    echo   [OK] Lock-Workstation deaktiviert

    REM Disable Change Password
    reg add "!POL!\System" /v DisableChangePassword /t REG_DWORD /d 1 /f >nul
    echo   [OK] Passwort-Aenderung deaktiviert

    REM Explorer policies
    reg add "!POL!\Explorer" /v NoDesktop /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoStartMenuMorePrograms /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoRun /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoViewContextMenu /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoWinKeys /t REG_DWORD /d 1 /f >nul
    reg add "!POL!\Explorer" /v NoClose /t REG_DWORD /d 0 /f >nul
    echo   [OK] Explorer-Einschraenkungen gesetzt

    REM Unload hive
    reg unload "!HKU_PATH!" >nul 2>&1
    echo   [OK] Kiosk-Haertung angewendet
) else (
    echo   [WARN] Policies nicht angewendet - Profil nicht verfuegbar
    echo          Fuehre den Installer nach dem ersten Login erneut aus.
)

:skip_hardening

REM ============================================================================
REM  STEP 9 - Windows Auto-Login
REM ============================================================================
echo.
echo [Step 9/12] Auto-Login konfigurieren...

set "WINLOGON=HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"

reg add "!WINLOGON!" /v AutoAdminLogon /t REG_SZ /d "1" /f >nul
reg add "!WINLOGON!" /v DefaultUserName /t REG_SZ /d "!KIOSK_USER!" /f >nul
reg add "!WINLOGON!" /v DefaultPassword /t REG_SZ /d "!KIOSK_PASS!" /f >nul
reg add "!WINLOGON!" /v DefaultDomainName /t REG_SZ /d "%COMPUTERNAME%" /f >nul

echo   [OK] Auto-Login fuer '!KIOSK_USER!' konfiguriert

REM ============================================================================
REM  STEP 10 - Shell Replacement + Scheduled Task
REM ============================================================================
echo.
echo [Step 10/12] Shell-Ersetzung + Autostart konfigurieren...

REM Back up current shell value
set "ORIG_SHELL="
for /f "tokens=2*" %%a in ('reg query "!WINLOGON!" /v Shell 2^>nul ^| findstr /i "Shell"') do (
    set "ORIG_SHELL=%%b"
)
if defined ORIG_SHELL (
    echo   [INFO] Aktuelle Shell: !ORIG_SHELL!
    reg add "!WINLOGON!" /v Shell_Backup /t REG_SZ /d "!ORIG_SHELL!" /f >nul
    echo   [OK] Original-Shell gesichert als Shell_Backup
)

REM Shell = VBS readiness gate (safety net, not primary launcher)
set "SHELL_CMD=wscript.exe "!INSTALL_DIR!\kiosk_shell.vbs""
reg add "!WINLOGON!" /v Shell /t REG_SZ /d "!SHELL_CMD!" /f >nul
echo   [DEBUG] Shell registry = !SHELL_CMD!
echo   [OK] Shell ersetzt: wscript.exe kiosk_shell.vbs

REM AlternateShell for Safe Mode recovery
reg add "!WINLOGON!" /v AlternateShell /t REG_SZ /d "cmd.exe" /f >nul
echo   [OK] AlternateShell=cmd.exe fuer Safe Mode gesichert

REM --- Create Scheduled Task for backend/chrome startup (TASK 6) ---
REM This is the PRIMARY startup mechanism. Runs with highest available
REM privileges at kiosk user logon. No UAC prompt needed.
echo.
echo   Scheduled Task erstellen...

REM Remove existing task first
schtasks /delete /tn "DartsKioskLauncher" /f >nul 2>&1

schtasks /create ^
    /tn "DartsKioskLauncher" ^
    /tr "cmd.exe /c \"!INSTALL_DIR!\darts_launcher.bat\"" ^
    /sc onlogon ^
    /ru "!KIOSK_USER!" ^
    /rp "!KIOSK_PASS!" ^
    /rl highest ^
    /f >nul 2>&1

if !ERRORLEVEL!==0 (
    echo   [OK] Scheduled Task 'DartsKioskLauncher' erstellt (at logon, elevated)
    echo   [DEBUG] Task command: cmd.exe /c "!INSTALL_DIR!\darts_launcher.bat"
) else (
    echo   [WARN] Scheduled Task konnte nicht erstellt werden
    echo          Fallback: Shell-Start wird allein verwendet
)

REM ============================================================================
REM  STEP 11 - System Configuration
REM ============================================================================
echo.
echo [Step 11/12] System konfigurieren...

REM === Firewall Rule ===
netsh advfirewall firewall show rule name="DartsKiosk Backend" >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    netsh advfirewall firewall add rule name="DartsKiosk Backend" dir=in action=allow protocol=TCP localport=!BACKEND_PORT! >nul
    echo   [OK] Firewall-Regel erstellt (Port !BACKEND_PORT!)
) else (
    echo   [OK] Firewall-Regel existiert bereits
)

REM === Power Management ===
powercfg -change -standby-timeout-ac 0 >nul
powercfg -change -monitor-timeout-ac 0 >nul
powercfg -change -hibernate-timeout-ac 0 >nul
powercfg -change -standby-timeout-dc 0 >nul
powercfg -change -monitor-timeout-dc 0 >nul
echo   [OK] Sleep/Standby/Bildschirmschoner deaktiviert

REM === Disable Notifications ===
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\Explorer" /v DisableNotificationCenter /t REG_DWORD /d 1 /f >nul 2>&1
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Notifications\Settings" /v NOC_GLOBAL_SETTING_TOASTS_ENABLED /t REG_DWORD /d 0 /f >nul 2>&1
echo   [OK] Windows-Benachrichtigungen deaktiviert

REM === Disable Windows Update Restart Prompts ===
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v NoAutoRebootWithLoggedOnUsers /t REG_DWORD /d 1 /f >nul 2>&1
echo   [OK] Auto-Restart bei Updates deaktiviert

REM ============================================================================
REM  STEP 12 - Finalize
REM ============================================================================
echo.
echo [Step 12/12] Installation abschliessen...

REM Create install marker
(
    echo installed=%date% %time%
    echo version=3.0.2
    echo install_dir=!INSTALL_DIR!
    echo kiosk_user=!KIOSK_USER!
    echo board_id=!BOARD_ID!
    echo backend_port=!BACKEND_PORT!
    echo source_dir=!SOURCE_DIR!
    echo python_path=!PYTHON_PATH!
    echo chrome_path=!CHROME_PATH!
) > "!INSTALL_DIR!\data\.install_info"
echo   [OK] Installationsinfo gespeichert

REM Create desktop shortcut for maintenance (for admin user)
set "ADMIN_DESKTOP=%USERPROFILE%\Desktop"
if exist "!ADMIN_DESKTOP!" (
    (
        echo @echo off
        echo cd /d "!INSTALL_DIR!"
        echo call maintenance.bat
    ) > "!ADMIN_DESKTOP!\DartsKiosk Maintenance.bat"
    echo   [OK] Maintenance-Shortcut auf Admin-Desktop erstellt
)

echo.
echo ================================================================
echo   INSTALLATION ABGESCHLOSSEN!
echo ================================================================
echo.
echo   Installiert in:       !INSTALL_DIR!
echo   Kiosk-Benutzer:       !KIOSK_USER!
echo   Board-ID:             !BOARD_ID!
echo   Backend-Port:         !BACKEND_PORT!
echo.
echo   Startup-Architektur:
echo     1. Scheduled Task 'DartsKioskLauncher' startet Backend + Chrome
echo     2. Shell 'kiosk_shell.vbs' ueberwacht Bereitschaft
echo     3. Bei Fehler: automatischer Recovery-Modus
echo.
echo   Maintenance-Zugang:
echo     - Strg+Alt+Entf -^> Benutzer wechseln -^> Admin-Konto
echo     - maintenance.bat auf dem Admin-Desktop
echo.
echo   Rollback:
echo     - Als Admin: !INSTALL_DIR!\uninstall_kiosk.bat
echo.

set /p "REBOOT=System jetzt neu starten? (J/N) [N]: "
if /i "!REBOOT!"=="J" (
    echo.
    echo System startet in 10 Sekunden neu...
    shutdown /r /t 10 /c "Darts Kiosk Installation - Neustart"
) else (
    echo.
    echo   Bitte starten Sie das System manuell neu,
    echo   um den Kiosk-Modus zu aktivieren.
)

echo.
pause
endlocal
