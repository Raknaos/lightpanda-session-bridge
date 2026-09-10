#!/usr/bin/env python3
"""Lightpanda Session Bridge — one-command setup & launcher.

Zero-manipulation goal:
  python bridge.py setup     -> installs everything (WSL2 check, Lightpanda, deps)
  python bridge.py start     -> starts Lightpanda + relay daemon (idempotent)
  python bridge.py status    -> is everything up? what's synced?
  python bridge.py install-browser-ext   -> prints the 2-step browser install
  python bridge.py doctor    -> diagnoses any problem with fixes

The relay daemon owns the ONLY CDP connection to Lightpanda (cookie jar is
connection-scoped) and exposes /v1/cdp so agents share the synced sessions.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request

# Windows consoles (and Task Scheduler / pythonw, which default to cp1252 or
# cp850) cannot encode the Unicode check marks printed below: the resulting
# UnicodeEncodeError killed `bridge.py start` *before* it ever reached the relay
# launch step, so scheduled/watchdog runs silently never brought the relay up.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.abspath(__file__))
LP_PORT = 9222
RELAY_PORT = 8765
LP_CDP = f"http://127.0.0.1:{LP_PORT}"
RELAY = f"http://127.0.0.1:{RELAY_PORT}"

IS_WINDOWS = platform.system() == "Windows"


def _http_json(url: str, timeout: float = 3.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def lp_up() -> bool:
    return _http_json(f"{LP_CDP}/json/version") is not None


def relay_up() -> bool:
    h = _http_json(f"{RELAY}/health")
    return bool(h and h.get("ok"))


def _wsl_available() -> bool:
    if not IS_WINDOWS:
        return False
    try:
        r = subprocess.run(["wsl.exe", "-l", "-q"], capture_output=True, text=True, timeout=20)
        return r.returncode == 0 and bool(r.stdout.strip())
    except Exception:
        return False


def _lightpanda_in_wsl() -> bool:
    if not IS_WINDOWS:
        return shutil.which(os.path.expanduser("~/lightpanda")) is not None or os.path.exists(os.path.expanduser("~/lightpanda"))
    try:
        r = subprocess.run(
            ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-lc", "test -x $HOME/lightpanda && echo YES || echo NO"],
            capture_output=True, text=True, timeout=30)
        return "YES" in r.stdout
    except Exception:
        return False


def _pip_install(*pkgs: str) -> bool:
    try:
        r = subprocess.run([sys.executable, "-m", "pip", "install", *pkgs],
                           capture_output=True, text=True, timeout=300)
        return r.returncode == 0
    except Exception:
        return False


# ---------------------------------------------------------------- commands

def cmd_setup(_args) -> int:
    print("🐼 Lightpanda Session Bridge — setup\n")
    ok = True

    # 1. Python deps
    print("[1/5] Python dependencies (websocket-client)…")
    try:
        import websocket  # noqa: F401
        print("      ✓ already installed")
    except ImportError:
        if _pip_install("websocket-client"):
            print("      ✓ installed")
        else:
            print("      ✗ pip install failed — run: pip install websocket-client")
            ok = False

    # 2. WSL2 (Windows only)
    if IS_WINDOWS:
        print("[2/5] WSL2…")
        if _wsl_available():
            print("      ✓ WSL available")
        else:
            print("      ! WSL not found — run: wsl --install -d Ubuntu  (then reboot)")
            ok = False

        # 3. Lightpanda binary
        print("[3/5] Lightpanda binary in WSL…")
        if _lightpanda_in_wsl():
            print("      ✓ ~/lightpanda present")
        else:
            print("      installing into WSL…")
            r = subprocess.run(
                ["wsl.exe", "-d", "Ubuntu", "--", "bash", "-lc",
                 "curl -fsSL https://pkg.lightpanda.io/install.sh | bash"],
                capture_output=True, text=True, timeout=600)
            if r.returncode == 0:
                print("      ✓ installed")
            else:
                print(f"      ✗ install failed: {r.stderr[-200:]}")
                ok = False
    else:
        print("[2/5] Native platform (Linux/macOS) — skipping WSL")
        print("[3/5] Lightpanda binary…")
        if _lightpanda_in_wsl():
            print("      ✓ ~/lightpanda present")
        else:
            print("      installing…")
            r = subprocess.run("curl -fsSL https://pkg.lightpanda.io/install.sh | bash",
                               shell=True, capture_output=True, text=True, timeout=600)
            print("      ✓ installed" if r.returncode == 0 else f"      ✗ {r.stderr[-200:]}")

    # 4. Firewall note
    print("[4/5] Windows Firewall: accept the prompt when Lightpanda first starts.")

    # 5. Start everything now
    print("[5/5] Starting services…")
    return cmd_start(_args)


def _start_lightpanda() -> bool:
    if lp_up():
        return True
    if IS_WINDOWS:
        subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", os.path.join(ROOT, "scripts", "start-lightpanda.ps1")],
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        subprocess.Popen(["bash", os.path.join(ROOT, "scripts", "start-lightpanda.sh")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    for _ in range(30):
        time.sleep(1)
        if lp_up():
            return True
    return False


def _interpreter_has_deps(python_exe: str) -> bool:
    """True if `python_exe` can import the relay's dependencies."""
    try:
        r = subprocess.run([python_exe, "-c", "import websocket"],
                           capture_output=True, timeout=30)
        return r.returncode == 0
    except Exception:
        return False


def _pick_interpreter() -> str:
    """Pick an interpreter that can actually run the relay.

    The relay needs websocket-client. A system Python may not have it, and
    spawning the relay with such an interpreter fails instantly and silently —
    which is exactly how "the relay never comes back up" looked for hours.
    Prefer the project-local venv when present, then the current interpreter.
    """
    candidates = []
    if IS_WINDOWS:
        candidates.append(os.path.join(ROOT, ".venv", "Scripts", "python.exe"))
    else:
        candidates.append(os.path.join(ROOT, ".venv", "bin", "python"))
    candidates.append(sys.executable)
    for exe in candidates:
        if os.path.exists(exe) and _interpreter_has_deps(exe):
            return exe
    return sys.executable


def _start_relay() -> bool:
    if relay_up():
        return True
    python_exe = _pick_interpreter()
    log_path = os.path.join(ROOT, "logs", "relay.log")
    try:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_file = open(log_path, "a", encoding="utf-8", errors="replace")
    except Exception:
        log_file = subprocess.DEVNULL
    cmd = [python_exe, os.path.join(ROOT, "relay", "server.py"), "--port", str(RELAY_PORT)]
    if IS_WINDOWS:
        subprocess.Popen(cmd, cwd=ROOT, stdout=log_file, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        subprocess.Popen(cmd, cwd=ROOT, stdout=log_file, stderr=subprocess.STDOUT,
                         start_new_session=True)
    if not _interpreter_has_deps(python_exe):
        print(f"   ⚠ {python_exe} cannot import websocket-client.")
        print("     Run: python bridge.py setup   (creates .venv and installs deps)")
        return False
    for _ in range(15):
        time.sleep(1)
        if relay_up():
            return True
    print(f"   ⚠ relay did not answer on port {RELAY_PORT}; see {log_path}")
    return False


def cmd_start(_args) -> int:
    print("[start] Lightpanda CDP…", end=" ")
    lp = _start_lightpanda()
    print("✓ up" if lp else "✗ FAILED")

    print("[start] Relay daemon…", end=" ")
    rl = _start_relay()
    print("✓ up" if rl else "✗ FAILED")

    if lp and rl:
        print("\n🐼 Bridge operational:")
        print(f"   - Lightpanda CDP : {LP_CDP}")
        print(f"   - Relay API      : {RELAY}  (agents: POST /v1/cdp)")
        print("   - Extension      : click 'Sync Session' in your browser; agents get the session automatically.")
        return 0
    return 1


def cmd_status(_args) -> int:
    lp, rl = lp_up(), relay_up()
    print(f"Lightpanda CDP ({LP_CDP}): {'✓ UP' if lp else '✗ DOWN'}")
    print(f"Relay daemon  ({RELAY}): {'✓ UP' if rl else '✗ DOWN'}")
    if rl:
        h = _http_json(f"{RELAY}/health")
        print(f"Relay attached to CDP : {'✓' if h.get('attached') else 'not yet'}")
    if not lp:
        print("\nFix: python bridge.py start")
    return 0 if (lp and rl) else 1


def cmd_doctor(_args) -> int:
    print("🐼 Doctor\n")
    checks = [
        ("Lightpanda CDP up", lp_up(), "python bridge.py start"),
        ("Relay daemon up", relay_up(), "python bridge.py start"),
    ]
    try:
        import websocket  # noqa: F401
        checks.append(("websocket-client installed", True, ""))
    except ImportError:
        checks.append(("websocket-client installed", False, "pip install websocket-client"))
    if IS_WINDOWS:
        checks.append(("WSL available", _wsl_available(), "wsl --install -d Ubuntu"))
        checks.append(("Lightpanda binary in WSL", _lightpanda_in_wsl(),
                       "wsl -d Ubuntu -- bash -lc 'curl -fsSL https://pkg.lightpanda.io/install.sh | bash'"))
    all_ok = True
    for name, ok, fix in checks:
        print(f"  {'✓' if ok else '✗'} {name}")
        if not ok:
            all_ok = False
            if fix:
                print(f"      fix → {fix}")
    print("\n" + ("All good — sync a session from your browser and go." if all_ok else "Fix the ✗ items above."))
    return 0 if all_ok else 1


def cmd_install_ext(_args) -> int:
    print("Browser extension install (one-time, ~30 seconds):\n")
    print("  1. Open your browser's extension page:")
    print("     chrome://extensions (Chrome/Comet/Brave/Opera/Vivaldi)")
    print("     edge://extensions (Edge)   arc://extensions (Arc)")
    print("  2. Enable 'Developer mode' (toggle, top-right)")
    print("  3. Click 'Load unpacked' → select the folder:")
    print(f"     {os.path.join(ROOT, 'extension')}")
    print("  4. Pin the 🐼 icon — done. The extension auto-pairs with the relay")
    print("     on first open (relay must be running: python bridge.py start).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="bridge")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup", help="install everything and start (first time)")
    sub.add_parser("start", help="start Lightpanda + relay (idempotent)")
    sub.add_parser("status", help="show what's running")
    sub.add_parser("doctor", help="diagnose problems with fixes")
    sub.add_parser("install-browser-ext", help="how to load the browser extension")
    args = p.parse_args()
    return {
        "setup": cmd_setup,
        "start": cmd_start,
        "status": cmd_status,
        "doctor": cmd_doctor,
        "install-browser-ext": cmd_install_ext,
    }[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
