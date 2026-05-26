# One-shot: register weekly synthetic-eval Scheduled Task (Sundays 02:00).

$ErrorActionPreference = "Stop"

$taskName = "llm_wiki_weekly_eval"
$projectRoot = (Resolve-Path "$PSScriptRoot\..").Path
$wrapper = Join-Path $projectRoot "scripts\_run_weekly_eval.ps1"

if (-not (Test-Path $wrapper)) {
    throw "Wrapper not found: $wrapper"
}

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$wrapper`"" `
    -WorkingDirectory $projectRoot

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 2am

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask -TaskName $taskName `
    -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "Weekly synthetic Q&A regression (PROJECT_PLAN Phase 6, Sundays 02:00)" | Out-Null

Write-Output "Registered '$taskName'. Next run: next Sunday 02:00."
Write-Output "Log:     $projectRoot\logs\weekly_eval_<date>.log"
Write-Output "Test:    Start-ScheduledTask -TaskName $taskName"
