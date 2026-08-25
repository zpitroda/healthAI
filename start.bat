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
    goto python_found
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    set "PYTHON_EXE=python"
    echo [*] Using system Python
    goto python_found
)

echo [ERROR] Python was not found on your system or in .venv.
echo Please install Python 3.10+ or set up .venv.
pause
exit /b 1

:python_found

:: Check if Neo4j is present and start it if not running
if not exist "neo4j\bin\neo4j.bat" goto check_llama
"%PYTHON_EXE%" scripts\check_port.py 7687 >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] Neo4j Graph Database is active on bolt://localhost:7687
    goto check_llama
)
echo [*] Starting Neo4j Graph Database in background window...
start "Neo4j Graph Database" /min cmd /c "start_neo4j.bat"
ping 127.0.0.1 -n 3 >nul

:check_llama
:: Check if llama-server is present and start it if not running
if not exist "start_llama_server.bat" goto start_app
"%PYTHON_EXE%" scripts\check_port.py 8080 >nul 2>&1
if %errorlevel% equ 0 (
    echo [*] llama-server is active on http://127.0.0.1:8080
    goto start_app
)
echo [*] Starting llama-server (Qwen 3.8 27B on RTX 5090) in separate window...
start "healthAI - llama-server (RTX 5090)" cmd /c "start_llama_server.bat"
ping 127.0.0.1 -n 3 >nul

:start_app
echo [*] Starting server at http://localhost:8000 ...
echo [*] Press Ctrl+C in this window to stop the server.
echo.

:: Open default browser after brief pause in background
start "" cmd /c "ping 127.0.0.1 -n 3 >nul & start http://localhost:8000"

:: Start Uvicorn via run_server.py
"%PYTHON_EXE%" run_server.py --host 127.0.0.1 --port 8000

if %errorlevel% neq 0 (
    echo.
    echo [!] Server terminated with an error code.
    pause
)
