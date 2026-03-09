@echo off
:: Helper script — called by start.bat to launch the frontend
:: Keeps env vars clean (no trailing whitespace from && chaining)
cd /d %~dp0frontend
set "PORT=3000"
set "HOST=0.0.0.0"
set "BROWSER=none"
call yarn start > ..\logs\frontend.log 2>&1
