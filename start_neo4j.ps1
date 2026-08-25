<#
.SYNOPSIS
    Starts the local Neo4j Community Server for healthAI.
.DESCRIPTION
    Launches Neo4j console mode from the project's local neo4j installation.
    Web Browser Interface: http://localhost:7474
    Bolt Protocol URI:    bolt://localhost:7687
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Neo4jBat = Join-Path $ScriptDir "neo4j\bin\neo4j.bat"

if (-not (Test-Path $Neo4jBat)) {
    Write-Error "Neo4j binary not found at $Neo4jBat."
    exit 1
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  healthAI - Neo4j Graph Database Server" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "[*] Neo4j Browser UI: http://localhost:7474" -ForegroundColor Yellow
Write-Host "[*] Bolt Endpoint:    bolt://localhost:7687" -ForegroundColor Yellow
Write-Host "[*] Default User:     neo4j / password" -ForegroundColor Gray
Write-Host "[*] Press Ctrl+C in this terminal to stop Neo4j." -ForegroundColor Gray
Write-Host ""

& $Neo4jBat console
