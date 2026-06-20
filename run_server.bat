@echo off
title Audit Document Converter Server
echo =========================================================
echo   FS & SINGLE AUDIT CONVERTER WEB SERVER
echo   Starting at http://localhost:5000
echo   Minimize this window to keep the server running.
echo   To stop the server, close this window.
echo =========================================================
echo.

:: %~dp0 is a special Windows variable that resolves to the directory containing this script.
:: This makes the launcher fully portable on any user's computer.
cd /d "%~dp0"
python app_server.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo ✗ ERROR: Server failed to start.
    echo Please make sure python is installed and run:
    echo pip install -r "%~dp0requirements.txt"
    echo.
    pause
)
