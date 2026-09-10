# install_windows_tasks.ps1 - keep the Lightpanda bridge relay always up on Windows.
#
# Why two tasks:
#   1. LightpandaRelayDaemon  - runs the relay itself. The relay is a long-lived
#      server, so the task instance stays in the "Running" state and Task
#      Scheduler supervises it (auto-restart on failure, no time limit).
#      A relay merely *spawned* from a short-lived task gets reaped together
#      with that task instance, which is why it kept vanishing.
#   2. LightpandaBridgeRelay - a 5-minute watchdog that starts task #1 again if
#      the relay stops answering on http://127.0.0.1:8765/health.
#
# The daemon runs the base interpreter that has websocket-client (the installer
# adds it if missing), because a system Python without that dependency makes the
# relay die instantly and silently.
#
# Usage (no admin needed for the current user):
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\install_windows_tasks.ps1

$ErrorActionPreference = 'Stop'

$Repo  = Split-Path -Parent $PSScriptRoot
# The relay task must run a *single* process so Task Scheduler supervises it:
# a venv pythonw.exe is a launcher shim that exits immediately, orphaning the
# relay and silently ending the task instance (no restart-on-failure anymore).
# Pick a *single-process* interpreter that can actually run the relay. A venv
# pythonw.exe is a launcher shim that exits immediately, orphaning the relay and
# silently ending the task instance (so restart-on-failure never fires). And a
# system Python without websocket-client makes the relay die instantly and
# silently - that is the bug that kept this relay offline for hours.
$cands = @(
  (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
  (Get-Command python.exe -ErrorAction SilentlyContinue).Source
) | Where-Object { $_ -and (Test-Path $_) }
$Py = $null
$savedEap = $ErrorActionPreference; $ErrorActionPreference = 'Continue'   # native stderr must not abort
foreach ($c in $cands) {
  & $c -c "import websocket" 2>$null
  if ($LASTEXITCODE -eq 0) { $Py = $c; break }
}
if (-not $Py) {
  $Py = $cands[0]
  Write-Host "[..] installing websocket-client for $Py"
  & $Py -m pip install --user --quiet websocket-client
}
$ErrorActionPreference = $savedEap
$Pyw = Join-Path (Split-Path -Parent $Py) 'pythonw.exe'
if (-not (Test-Path $Pyw)) { $Pyw = $Py }   # no windowless twin: run visibly
Write-Host "[ok] daemon interpreter: $Py"

$Relay = Join-Path $Repo 'relay\server.py'
$Watch = Join-Path $Repo 'scripts\watchdog_relay.pyw'

if (-not (Test-Path $Relay)) { throw "Missing file: $Relay" }
if (-not (Test-Path $Watch)) { throw "Missing file: $Watch" }

$User = "$env:USERDOMAIN\$env:USERNAME"

$DaemonSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
$DaemonAction   = New-ScheduledTaskAction -Execute $Pyw -Argument ('"' + $Relay + '" --port 8765') -WorkingDirectory $Repo
$DaemonTrigger  = New-ScheduledTaskTrigger -AtLogOn -User $User
Register-ScheduledTask -TaskName 'LightpandaRelayDaemon' -Action $DaemonAction -Trigger $DaemonTrigger -Settings $DaemonSettings -Description 'Lightpanda Session Bridge relay daemon (port 8765), supervised with auto-restart.' -Force | Out-Null
Write-Host '[ok] LightpandaRelayDaemon registered'

$WatchSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew
$WatchAction   = New-ScheduledTaskAction -Execute $Pyw -Argument ('"' + $Watch + '"') -WorkingDirectory $Repo
$WatchTrigger  = New-ScheduledTaskTrigger -AtLogOn -User $User
$WatchTrigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)).Repetition
Register-ScheduledTask -TaskName 'LightpandaBridgeRelay' -Action $WatchAction -Trigger $WatchTrigger -Settings $WatchSettings -Description 'Lightpanda bridge relay watchdog: restarts the relay if port 8765 stops answering.' -Force | Out-Null
Write-Host '[ok] LightpandaBridgeRelay watchdog registered (every 5 min)'

Start-ScheduledTask -TaskName 'LightpandaRelayDaemon'
for ($i = 1; $i -le 20; $i++) {
  Start-Sleep -Seconds 1
  try {
    $h = Invoke-RestMethod -Uri 'http://127.0.0.1:8765/health' -TimeoutSec 2
    if ($h.ok) { Write-Host ('[ok] relay up after ' + $i + 's (attached=' + $h.attached + ')'); exit 0 }
  } catch { }
}
Write-Warning ('relay did not answer within 20s; check ' + $Repo + '\logs\relay.log')
exit 1
