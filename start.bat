@echo off
title healthAI Server Launcher
setlocal

cd /d "%~dp0"

echo ============================================================
echo    healthAI - Pharmacology Lab ^& Protocol Engine
echo ============================================================
echo.

:: Detect Python executable
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
    echo [*] Using virtual environment: .venv
) else (
    where python >nul 2>&1
    if %errorlevel% equ 0 (
        set "PYTHON_EXE=python"
        echo [*] Using system Python
    ) else (
        echo [ERROR] Python was not found on your system or in .venv.
        echo Please install Python 3.10+ or set up .venv.
        pause
        exit /b 1
    )
)

echo [*] Starting server at http://localhost:8000 ...
echo [*] Press Ctrl+C in this window to stop the server.
echo.

:: Open default browser after brief pause in background
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8000"

:: Start Uvicorn via run_server.py
"%PYTHON_EXE%" run_server.py --host 127.0.0.1 --port 8000

if %errorlevel% neq 0 (
    echo.
    echo [!] Server terminated with an error code.
    pause
)
