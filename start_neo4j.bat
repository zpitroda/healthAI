@echo off
title healthAI Neo4j Graph Database
setlocal

cd /d "%~dp0"

set "NEO4J_BAT=neo4j\bin\neo4j.bat"

if not exist "%NEO4J_BAT%" (
    echo [ERROR] Neo4j binary not found at %NEO4J_BAT%.
    pause
    exit /b 1
)

echo ============================================================
echo   healthAI - Neo4j Graph Database Server
echo ============================================================
echo [*] Neo4j Browser UI: http://localhost:7474
echo [*] Bolt Endpoint:    bolt://localhost:7687
echo [*] Default Auth:     neo4j / password
echo [*] Press Ctrl+C in this window to stop Neo4j.
echo.

call "%NEO4J_BAT%" console

if %errorlevel% neq 0 (
    echo.
    echo [!] Neo4j terminated with an error.
    pause
)
