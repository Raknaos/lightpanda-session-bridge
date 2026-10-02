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

def relay_healthy(timeout=6):
    """True only if the relay answers AND is attached to Lightpanda.

    A bare urlopen() is not enough. Before v0.6.1 the watchdog treated any 200
    from /health as "relay fine", while the CDP connection could be dead: the
    watchdog then left a half-working relay alone and, when it did act, raced
    the running one. /health now carries `attached`, so the watchdog checks the
    thing it actually cares about - a relay that can carry a sync.
    """
    try:
        with urllib.request.urlopen(HEALTH, timeout=timeout) as r:
            if r.status != 200:
                return False
            data = json.loads(r.read().decode("utf-8", "replace"))
    except Exception:
        return False
    attached = data.get("attached")
    if attached is False:
        log("watchdog: relay answers but is NOT attached to Lightpanda")
        return False
    return True

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
    # Two independent questions. "Is the relay process serving?" is what we
    # can fix by restarting it. "Is Lightpanda reachable?" is not the relay's
    # fault: the relay opens the CDP socket on demand, so a Lightpanda that is
    # simply not running yet must NOT trigger a restart (that is how the
    # watchdog used to race a perfectly healthy relay).
    relay_ok = relay_healthy()
    cdp_ok = up(CDP)
    if relay_ok:
        if not cdp_ok:
            log("watchdog: relay healthy, Lightpanda not reachable "
                "(relay connects on demand - not restarting)")
        return  # nothing to do
    log(f"watchdog: relay={relay_ok} cdp={cdp_ok} exe={sys.executable} -> (re)starting")
    if start_daemon_task():
        for _ in range(20):
            time.sleep(1)
            # Same check as the entry gate: a relay that answers while not
            # attached is not "up", it is the exact failure we are here for.
            if relay_healthy():
                log("watchdog: relay is up and attached")
                return
        log("watchdog: relay still down (or unattached) after daemon start")
    else:
        # Fallback: legacy direct start (works when run interactively).
        try:
            r = subprocess.run(START, cwd=REPO, capture_output=True, timeout=180)
            log(f"watchdog: direct start rc={r.returncode} out={r.stdout[-400:]!r} err={r.stderr[-400:]!r}")
        except Exception as e:
            log(f"watchdog: direct start failed: {e!r}")

if __name__ == "__main__":
    main()
