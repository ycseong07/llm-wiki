# Wrapper invoked by Windows Task Scheduler.
# Sets working directory, runs ingest pipeline, appends to dated log file.
# Do not run directly — use scripts/register_ingest_task.ps1 once, then Task Scheduler triggers this hourly.

$ErrorActionPreference = "Continue"

$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $projectRoot

$logDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logFile = Join-Path $logDir ("ingest_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
$header = "=== {0} ===" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Add-Content -Path $logFile -Value $header -Encoding utf8

uv run python scripts/ingest_now.py *>&1 | Add-Content -Path $logFile -Encoding utf8
