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

# Function to test port connectivity silently and instantaneously
function Test-PortSilent([string]$hostAddress, [int]$port) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $iar = $tcp.BeginConnect($hostAddress, $port, $null, $null)
        $wait = $iar.AsyncWaitHandle.WaitOne(200, $false)
        if ($wait) {
            $tcp.EndConnect($iar)
            $tcp.Close()
            return $true
        }
        $tcp.Close()
        return $false
    } catch {
        return $false
    }
}

# Check if Neo4j is running, otherwise launch it
if (Test-Path "$ScriptDir\neo4j\bin\neo4j.bat") {
    $neo4jRunning = Test-PortSilent "127.0.0.1" 7687
    if (-not $neo4jRunning) {
        Write-Host "[*] Starting Neo4j Graph Database in separate window..." -ForegroundColor Yellow
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$ScriptDir\start_neo4j.bat`"" -WindowStyle Minimized
        Start-Sleep -Seconds 2
    } else {
        Write-Host "[*] Neo4j Graph Database is active on bolt://localhost:7687" -ForegroundColor Green
    }
}

# Check if llama-server is running on port 8080, otherwise launch it
if (Test-Path "$ScriptDir\start_llama_server.ps1") {
    $llamaRunning = Test-PortSilent "127.0.0.1" 8080
    if (-not $llamaRunning) {
        Write-Host "[*] Starting llama-server (Unsloth Qwen 3.8 27B UD-Q6_K_M on RTX 5090) in separate window..." -ForegroundColor Yellow
        Start-Process -FilePath "powershell.exe" -ArgumentList "-ExecutionPolicy Bypass -File `"$ScriptDir\start_llama_server.ps1`""
        Start-Sleep -Seconds 2
    } else {
        Write-Host "[*] llama-server is active on http://127.0.0.1:8080" -ForegroundColor Green
    }
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
