# Registers a Windows Scheduled Task that collects fuel stats twice a day.
# ASCII-only: Windows PowerShell 5.1 reads BOM-less scripts as ANSI and would
# mangle Cyrillic, so the task name and messages are kept in Latin.
#
# RUN (normal PowerShell, from this folder):
#     powershell -File .\setup_task.ps1
#
# Check now:   Start-ScheduledTask -TaskName "FuelStatsMoscow"
# Remove:      double-click remove_task.bat  (or run remove_task.ps1)
#
# Times are in $times below (default 09:00 and 21:00, local machine time).
# The task runs when you are logged on; a run missed while the PC was off
# fires at next boot (StartWhenAvailable).

$ErrorActionPreference = "Stop"
$dir      = Split-Path -Parent $MyInvocation.MyCommand.Definition
$taskName = "FuelStatsMoscow"
$times    = @("09:00", "21:00")

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python not found in PATH. Install Python 3 from python.org and retry."
}

$bat = Join-Path $dir "run_collect.bat"
if (-not (Test-Path $bat)) { throw "Not found: $bat" }

$action   = New-ScheduledTaskAction -Execute $bat -Argument "/quiet" -WorkingDirectory $dir
$triggers = foreach ($t in $times) { New-ScheduledTaskTrigger -Daily -At $t }
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable `
              -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
              -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers `
    -Settings $settings -Force `
    -Description "Collect fuel prices (petrolplus) and availability (gdebenz), twice a day" | Out-Null

Write-Host "Task '$taskName' registered for $($times -join ' and ') (local time)." -ForegroundColor Green
Write-Host "Test now:  Start-ScheduledTask -TaskName `"$taskName`"   then open dashboard.html"
