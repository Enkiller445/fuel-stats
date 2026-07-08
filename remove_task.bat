@echo off
rem ----------------------------------------------------------------------
rem  Delete the twice-a-day scheduled task (when you no longer need data).
rem  Just double-click this file. Collected data and dashboards stay intact.
rem ----------------------------------------------------------------------
echo Removing scheduled task "FuelStatsMoscow" ...
powershell -NoProfile -Command "try { Unregister-ScheduledTask -TaskName 'FuelStatsMoscow' -Confirm:$false -ErrorAction Stop; Write-Host 'Done: task removed. Data and dashboards are kept.' -ForegroundColor Green } catch { Write-Host 'Task not found (already removed?).' -ForegroundColor Yellow }"
echo.
pause
