# Bridge relay watchdog for Windows
# Keeps the relay daemon alive; auto-restarts if it dies. Designed for
# Windows Task Scheduler (run at logon, every 5 min, silent).
#
# IMPORTANT (learned the hard way): a relay spawned from inside a scheduled
# task dies with the task instance (Task Scheduler reaps the task's process
# tree). This watchdog therefore only ever *starts* the relay through the
# dedicated `LightpandaRelayDaemon` task, which keeps the relay in its own
# long-running task instance. See scripts/install_windows_tasks.ps1.

import json, os, subprocess, sys, time, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
START = [sys.executable, os.path.join(REPO, "bridge.py"), "start"]
HEALTH = "http://127.0.0.1:8765/health"
CDP = "http://127.0.0.1:9222/json/version"
LOG = os.path.join(os.environ.get("TEMP", "/tmp"), "lp-bridge-watchdog.log")
DAEMON_TASK = "LightpandaRelayDaemon"

def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")

def up(url, timeout=4):
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False

def start_daemon_task():
    """Ask Task Scheduler to (re)start the relay in its own task instance."""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Start-ScheduledTask -TaskName '{DAEMON_TASK}'"],
            capture_output=True, timeout=60,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        log(f"watchdog: Start-ScheduledTask {DAEMON_TASK} rc={r.returncode}")
        return r.returncode == 0
    except Exception as e:
        log(f"watchdog: Start-ScheduledTask failed: {e!r}")
        return False

def main():
    relay_ok = up(HEALTH)
    cdp_ok = up(CDP)
    if relay_ok:
        return  # nothing to do
    log(f"watchdog: relay={relay_ok} cdp={cdp_ok} exe={sys.executable} -> (re)starting")
    if start_daemon_task():
        for _ in range(20):
            time.sleep(1)
            if up(HEALTH):
                log("watchdog: relay is up")
                return
        log("watchdog: relay still down after daemon start")
    else:
        # Fallback: legacy direct start (works when run interactively).
        try:
            r = subprocess.run(START, cwd=REPO, capture_output=True, timeout=180)
            log(f"watchdog: direct start rc={r.returncode} out={r.stdout[-400:]!r} err={r.stderr[-400:]!r}")
        except Exception as e:
            log(f"watchdog: direct start failed: {e!r}")

if __name__ == "__main__":
    main()
