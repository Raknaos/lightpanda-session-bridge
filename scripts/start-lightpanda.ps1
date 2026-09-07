param(
  [int]$Port = 9222,
  [string]$CookieDir = "$HOME\.hermes\lightpanda-a6api"
)
$ErrorActionPreference = 'Stop'
$wslDir = ($CookieDir -replace '\\','/')
$wslDir = $wslDir -replace '^C:', '/mnt/c'
$cmd = "mkdir -p '$wslDir'; export LIGHTPANDA_DISABLE_TELEMETRY=true; exec `"`$HOME/lightpanda`" serve --host 127.0.0.1 --port $Port --cookie-jar '$wslDir/cookies.json' --log-level error"
wsl.exe -d Ubuntu -- bash -lc $cmd
