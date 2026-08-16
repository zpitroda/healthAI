<#
.SYNOPSIS
    Starts the healthAI FastAPI web application server and opens the browser.
.DESCRIPTION
    Launches uvicorn on http://127.0.0.1:8000 with auto-reload enabled.
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $ScriptDir

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  healthAI - Pharmacology Lab & Protocol Engine" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$PythonExe = ""
if (Test-Path "$ScriptDir\.venv\Scripts\python.exe") {
    $PythonExe = "$ScriptDir\.venv\Scripts\python.exe"
    Write-Host "[*] Using virtual environment: .venv" -ForegroundColor Gray
} else {
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $PythonExe) {
        Write-Error "Python was not found in .venv or PATH. Please install Python 3.10+."
        exit 1
    }
    Write-Host "[*] Using system Python: $PythonExe" -ForegroundColor Gray
}

Write-Host "[*] Launching server on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
Write-Host "[*] Press Ctrl+C in this terminal to stop." -ForegroundColor Yellow
Write-Host ""

# Open browser in a background job after 2 seconds
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://127.0.0.1:8000"
} | Out-Null

& $PythonExe run_server.py --host 127.0.0.1 --port 8000
