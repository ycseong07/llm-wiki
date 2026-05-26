# One-shot: register the hourly Windows Scheduled Task that runs the ingest pipeline.
# Idempotent — re-running unregisters the existing task and registers fresh.
#
# Run as the user who'll own the task (no admin needed for Interactive logon type):
#   powershell -ExecutionPolicy Bypass -File scripts\register_ingest_task.ps1
#
# To remove later: Unregister-ScheduledTask -TaskName llm_wiki_ingest -Confirm:$false

$ErrorActionPreference = "Stop"

$taskName = "llm_wiki_ingest"
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$wrapper = Join-Path $projectRoot "scripts\_run_ingest.ps1"

if (-not (Test-Path $wrapper)) {
    throw "Wrapper not found: $wrapper"
}

# Unregister if already exists.
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "Unregistering existing task '$taskName'..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$wrapper`"" `
    -WorkingDirectory $projectRoot

# First run 2 minutes from now; then every hour, indefinitely.
$start = (Get-Date).AddMinutes(2)
$trigger = New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Hours 1)

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Hourly RAG ingest pipeline (PROJECT_PLAN Phase 2)" | Out-Null

Write-Output "Registered '$taskName'. First run at: $start"
Write-Output "Logs: $projectRoot\logs\ingest_<date>.log"
Write-Output "Test now:  Start-ScheduledTask -TaskName $taskName"
Write-Output "Inspect:   Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo"
