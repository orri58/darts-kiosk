@echo off
REM Helper: activates venv and launches backend from project root
cd /d "%~dp0"
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)
python -m uvicorn backend.server:app --host 0.0.0.0 --port 8001 --reload > logs\backend.log 2>&1
