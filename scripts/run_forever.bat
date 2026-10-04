@echo off
REM Run Bale Subdomain Finder Bot with automatic restart on failure
REM Save this as scripts/run_forever.bat

setlocal
cd /d "%~dp0.."

echo [%date% %time%] Starting Subdomain Finder Bot (Bale)...

:RESTART
echo [%date% %time%] Starting bot...
venv\Scripts\python -m bot.bale_main

set EXIT_CODE=%ERRORLEVEL%
if %EXIT_CODE% EQU 0 (
    echo [%date% %time%] Bot stopped gracefully (exit code 0). Exiting.
    exit /b 0
) else (
    echo [%date% %time%] Bot crashed with exit code %EXIT_CODE%. Restarting in 10 seconds...
    timeout /t 10 /nobreak >nul
    goto RESTART
)