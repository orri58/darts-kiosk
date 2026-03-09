@echo off
REM Helper: launches frontend with clean env vars (no trailing whitespace)
cd /d "%~dp0frontend"
set "PORT=3000"
set "HOST=0.0.0.0"
set "BROWSER=none"
call yarn start > ..\logs\frontend.log 2>&1
