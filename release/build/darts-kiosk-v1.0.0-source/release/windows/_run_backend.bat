@echo off
REM Helper: activates venv and launches backend via dedicated Windows launcher
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)
python run_backend.py > logs\backend.log 2>&1
