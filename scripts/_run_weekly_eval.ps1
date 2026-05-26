# Wrapper invoked by Windows Task Scheduler. Runs weekly synthetic eval and appends to log.

$ErrorActionPreference = "Continue"

$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $projectRoot

$logDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logFile = Join-Path $logDir ("weekly_eval_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
$header = "=== {0} ===" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Add-Content -Path $logFile -Value $header -Encoding utf8

uv run python scripts/weekly_eval.py *>&1 | Add-Content -Path $logFile -Encoding utf8
