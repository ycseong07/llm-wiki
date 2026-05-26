# One-shot: register the daily 07:00 digest builder as a Windows Scheduled Task.
# Idempotent — re-running unregisters the existing task and registers fresh.
#
# Run as the user (no admin needed):
#   powershell -ExecutionPolicy Bypass -File scripts\register_digest_task.ps1
#
# To remove later: Unregister-ScheduledTask -TaskName llm_wiki_digest -Confirm:$false

$ErrorActionPreference = "Stop"

$taskName = "llm_wiki_digest"
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$wrapper = Join-Path $projectRoot "scripts\_run_digest.ps1"

if (-not (Test-Path $wrapper)) {
    throw "Wrapper not found: $wrapper"
}

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Output "Unregistering existing task '$taskName'..."
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$wrapper`"" `
    -WorkingDirectory $projectRoot

# Daily at 07:00. StartWhenAvailable kicks in if PC was off/asleep at trigger time.
$trigger = New-ScheduledTaskTrigger -Daily -At 7am

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Daily digest builder (PROJECT_PLAN Phase 5, 07:00 KST)" | Out-Null

Write-Output "Registered '$taskName'. Next run: tomorrow 07:00."
Write-Output "Log:     $projectRoot\logs\digest_<date>.log"
Write-Output "Test:    Start-ScheduledTask -TaskName $taskName"
Write-Output "Inspect: Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo"
