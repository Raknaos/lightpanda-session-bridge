"""Proof-red for the session expiry chain and its translation.

Sabotages one link at a time and confirms a NAMED test goes red. Restores from a
pristine copy written to disk before the edit and verifies the restore is
byte-identical — never `git checkout`, which would restore HEAD and discard the
uncommitted work in these files (skill point 31).
"""
import hashlib
import pathlib
import time
import urllib.request
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")
NODE = shutil.which("node") or "node"
PRISTINE = ROOT / "scripts" / "artifacts_pristine"
PRISTINE.mkdir(exist_ok=True)

UNIT = ("test_session_expiry_chain.py", "tests/test_session_expiry_chain.py")
NODE_TEST = ("test_session_meta_i18n.js", "tests/node/test_session_meta_i18n.js")

SABOTAGES = [
    # (fichier, quoi, marqueur attendu dans la sortie rouge)
    ("extension/popup.js",
     "lien 1: la popup cesse de renommer expirationDate",
     ("popup.js",),
     [("    cookies = cookies.map(c => ({\n      ...c,\n      expires_hint:",
       "    cookies = cookies.map(c => ({\n      ...c,\n      expires_hint_disabled:")],
     "expirationDate"),
    ("extension/popup.js",
     "lien 4: l'expiration n'est plus traduite",
     ("popup.js",),
     [("    meta.textContent = t(s.cookie_count === 1 ? 'sessionCookieOne' : 'sessionCookieUnit', s.cookie_count) +",
       "    meta.textContent = `${s.cookie_count} cookies` +")],
     "session"),
    ("extension/popup.js",
     "fmtExpiry arrondit les heures au lieu de tronquer",
     ("popup.js",),
     [("  if (left >= 3600000) return `~${Math.floor(left / 3600000)}h`;",
       "  if (left >= 3600000) return `~${Math.round(left / 3600000)}h`;")],
     "minutes"),
    ("extension/popup.js",
     "fmtExpiry tronque les jours au lieu de les arrondir",
     ("popup.js",),
     [("  if (left >= 86400000) return `~${Math.ceil(left / 86400000)}d`;",
       "  if (left >= 86400000) return `~${Math.floor(left / 86400000)}d`;")],
     "5 jours"),
    ("relay/server.py",
     "lien 2: expires_hint retiré de l'allow-list",
     ("server.py",),
     [('               "expires", "expires_hint", "url"}',
       '               "expires", "url"}')],
     "allow-list"),
    ("relay/server.py",
     "lien 3: une échéance déjà passée est jetée",
     ("server.py",),
     [("    if isinstance(expires_hint, (int, float)) and expires_hint > 0:\n        item[\"expires_hint\"] = float(expires_hint)",
       "    if isinstance(expires_hint, (int, float)) and expires_hint > time.time():\n        item[\"expires_hint\"] = float(expires_hint)")],
     "passe"),
]

NODE_SABOTAGES = [
    ("liens 1-2: le rendu repasse en litteraux anglais",
     [("    sessionCookieOne: (n) => `${n} cookie`,\n    sessionExpired: \"expired\",",
       "    sessionCookieOne: (n) => `${n} cookies`,\n    sessionExpired: \"expired\",")],
     "ne dit pas"),
    ("fmtExpiry ne dit plus les minutes, seulement '<1h'",
     [("  return `~${Math.max(1, Math.floor(left / 60000))}m`;", "  return '<1h';")],
     "minutes"),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pristine(rel):
    """Snapshot the CURRENT file, every run.

    A cached snapshot is a trap: after a fix, restoring it silently reverted the
    fix (measured - the minutes fix vanished and the proof-red's own assertion
    caught it). The snapshot must be taken at sabotage time, not at first use.
    """
    dst = PRISTINE / rel.replace("/", "__")
    shutil.copy2(ROOT / rel, dst)
    return dst


def restore(rel):
    shutil.copy2(PRISTINE / rel.replace("/", "__"), ROOT / rel)


def _relay_pids():
    ps = ("Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe'\" | "
          "Where-Object { $_.CommandLine -like '*relay*server.py*' } | "
          "Select-Object -ExpandProperty ProcessId")
    got = subprocess.run(["powershell.exe", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, timeout=90)
    return [x for x in (got.stdout or "").split() if x.isdigit()]


def restart_relay():
    """A server.py sabotage is invisible until the RUNNING relay is restarted -
    the test would otherwise measure the previous code and report green.

    Kill EVERY relay, then wait for the port to be FREE. Stopping only the first
    leaves the watchdog's copy holding 8765, so the freshly started one exits 0 on
    "address already in use" and the sabotaged code never runs (measured: the
    restart reported False and two proofs were invalid until all copies were
    stopped AND the port was confirmed free).
    """
    for pid in _relay_pids():
        subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                        "Stop-Process -Id %s -Force" % pid],
                       capture_output=True, timeout=90)
    for _ in range(20):
        time.sleep(1)
        if not _relay_pids():
            break
    if _relay_pids():
        return False
    subprocess.run(["powershell.exe", "-NoProfile", "-Command",
                    # NOT LightpandaBridgeRelay: the relay process is owned by
                    # LightpandaRelayDaemon (watchdog_relay.pyw DAEMON_TASK).
                    # Starting the wrong task reported False forever because the
                    # real daemon never received the sabotaged code.
                    "Start-ScheduledTask -TaskName 'LightpandaRelayDaemon'"],
                   capture_output=True, text=True, timeout=90)
    for _ in range(30):
        time.sleep(1)
        try:
            with urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
    return False

def run(cmd, timeout=400):
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    results = []
    for rel, label, (needle_file,), edits, expect in SABOTAGES:
        target = ROOT / rel
        pristine(rel)
        before = sha(target)
        original = target.read_text(encoding="utf-8")
        try:
            text = original
            for a, b in edits:
                if a not in text:
                    results.append((label, "PATCH-MISS", "le motif du sabotage est absent"))
                    text = None
                    break
                text = text.replace(a, b, 1)
            if text is None:
                continue
            target.write_text(text, encoding="utf-8", newline="")
            assert sha(target) != before, "le sabotage n'a rien change"

            if rel.endswith(".py"):
                if not restart_relay():
                    results.append((label, "RELAY DOWN",
                                    "le relais n'a pas redemarre: mesure impossible"))
                    continue
                code, out = run([PY, "-m", "unittest", "discover",
                                 "-s", "tests", "-p", UNIT[0], "-v"])
            else:
                code, out = run([NODE, NODE_TEST[1], str(ROOT)])
            # Match the TRACEBACK, not the words: a test's own docstring can
            # quote "Failed to import test module", which turned a genuine
            # 3-failure red into a fake HARNESS. unittest prints
            # "ERROR: <name> (unittest.loader._FailedTest.<name>)" for a real
            # import failure and nothing else emits that module path.
            loader_err = ("unittest.loader._FailedTest" in out
                          or ("ModuleNotFoundError" in out and "Traceback" in out
                              and "test_" in out.split("ModuleNotFoundError")[0][-400:]))
            if loader_err:
                # Keep the reason: the WHOLE output is what tells a harness
                # failure from a product failure, and truncating it is how a
                # broken harness gets recorded as a red.
                results.append((label, "HARNESS",
                                (out.strip().splitlines() or ["?"])[-1][:90]))
                continue
            red = code != 0
            named = expect.lower() in out.lower()
            status = "RED (named)" if (red and named) else ("RED (unnamed)" if red else "NOT RED")
            results.append((label, status, out.strip().splitlines()[-1][:90]))
        finally:
            restore(rel)
            assert sha(target) == before, "la restauration n'est pas identique"
            if rel.endswith(".py"):
                restart_relay()

    for label, edits, expect in NODE_SABOTAGES:
        rel = "extension/popup.js"
        pristine(rel)
        before = sha(ROOT / rel)
        original = (ROOT / rel).read_text(encoding="utf-8")
        try:
            text = original
            ok = True
            for a, b in edits:
                if a not in text:
                    results.append((label, "PATCH-MISS", "motif absent"))
                    ok = False
                    break
                text = text.replace(a, b, 1)
            if not ok:
                continue
            (ROOT / rel).write_text(text, encoding="utf-8", newline="")
            code, out = run([NODE, NODE_TEST[1], str(ROOT)])
            red = code != 0
            named = expect.lower() in out.lower()
            status = "RED (named)" if (red and named) else ("RED (unnamed)" if red else "NOT RED")
            results.append((label, status, out.strip().splitlines()[-1][:90]))
        finally:
            restore(rel)
            assert sha(ROOT / rel) == before

    print("PROOF RED")
    reds = 0
    named_reds = 0
    for label, status, detail in results:
        print("  %-14s %s" % (status, label))
        print("                 %s" % detail)
        if status.startswith("RED"):
            reds += 1
        if status == "RED (named)":
            named_reds += 1
    print("\n%d sabotage(s), %d rouge(s), %d nomme(s), %d invalide(s)"
          % (len(results), reds, named_reds,
             sum(1 for _, st, _ in results
                 if st in ("PATCH-MISS", "HARNESS", "RELAY DOWN", "NOT RED"))))
    # A PATCH-MISS means the sabotage no longer matches the source: the proof
    # did not run, it did not pass. It must never be counted as a red.
    if any(st in ("PATCH-MISS", "HARNESS", "RELAY DOWN") for _, st, _ in results):
        print("PATCH-MISS / HARNESS / RELAY DOWN: une sabotage n'a pas ete "
              "evalue - la preuve est INVALIDE, pas verte")
        return 1
    # Every sabotage must be red AND name its defect: an unnamed red proves
    # only that something broke, not that this guard can fail.
    return 0 if named_reds == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
