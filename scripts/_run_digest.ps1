# Wrapper invoked by Windows Task Scheduler.
# Builds the daily digest and appends to a dated log file.
# Do not run directly — use scripts/register_digest_task.ps1 once.

$ErrorActionPreference = "Continue"

$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $projectRoot

$logDir = Join-Path $projectRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logFile = Join-Path $logDir ("digest_{0}.log" -f (Get-Date -Format "yyyy-MM-dd"))
$header = "=== {0} ===" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Add-Content -Path $logFile -Value $header -Encoding utf8

uv run python scripts/build_digest_now.py *>&1 | Add-Content -Path $logFile -Encoding utf8
