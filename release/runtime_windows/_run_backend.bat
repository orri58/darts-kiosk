@echo off
setlocal
cd /d "%~dp0\..\.."
if exist "app\.venv\Scripts\activate.bat" (
    call "app\.venv\Scripts\activate.bat"
)
if not exist "data\logs" mkdir "data\logs"
python app\bin\run_backend.py > data\logs\backend.log 2>&1
endlocal
