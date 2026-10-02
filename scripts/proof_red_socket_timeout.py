# -*- coding: utf-8 -*-
"""Proof-red for the class-level socket deadline.

Reverts the fix in relay/server.py and asserts that the new tests go RED for
the RIGHT reason - a connection that sends nothing stays open - rather than for
a harness reason (NameError, a missing attribute, an unbound port).

NEVER `git checkout <file>` for this: relay/server.py carries uncommitted
work. The pristine copy is written to disk BEFORE the edit and restored from it.
"""
import pathlib
import re
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SERVER = REPO_ROOT / "relay" / "server.py"
PY = str(REPO_ROOT / ".venv" / "Scripts" / "python.exe")

REDUCED = re.compile(r"^(\s*)timeout = \d+$", re.MULTILINE)


def main() -> int:
    original = SERVER.read_text(encoding="utf-8")
    backup = pathlib.Path(tempfile.mkdtemp(prefix="lp-proofred-")) / "server.py"
    backup.write_text(original, encoding="utf-8", newline="")
    assert backup.read_text(encoding="utf-8") == original, "backup not faithful"

    # The sabotage must be long enough that the 15s deadline cannot explain the
    # failure, and SHORT enough to finish. My first choice, 600s, made the
    # silent-socket test legitimately wait out the whole 600s deadline before
    # declaring a socket stuck - so the run needed ~610s and was killed by the
    # budget twice (400s, then 900s), producing TimeoutExpired instead of a
    # result. 45s proves the same thing (45 >> 15) in 45s of waiting: the test
    # waits DEADLINE+4 = 19s, sees the socket still open, and names the defect.
    sabotaged, n = REDUCED.subn(r"\1timeout = 45", original, count=1)
    if n != 1:
        print("ABORT: no class-level timeout found to sabotage")
        return 2
    SERVER.write_text(sabotaged, encoding="utf-8", newline="")
    budget = 420
    try:
        proc = subprocess.run(
            [PY, "-m", "unittest", "discover", "-s", "tests",
             "-p", "test_socket_timeout.py"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=budget)
    finally:
        SERVER.write_text(original, encoding="utf-8", newline="")
        assert SERVER.read_text(encoding="utf-8") == original, "restore failed"
        print("fix restored:", ("timeout = 15" in original))

    out = proc.stdout + proc.stderr
    summary = [ln for ln in out.splitlines()
               if re.match(r"^(FAILED|OK|Ran )", ln)]
    fails = [ln for ln in out.splitlines() if ln.startswith(("FAIL:", "ERROR:"))]
    harness_noise = [ln for ln in out.splitlines()
                     if re.search(r"(NameError|ModuleNotFoundError|"
                                  r"AttributeError|TypeError)", ln)]
    # The property itself: a silent connection must be released. Match the TEST
    # NAME (which is stable) rather than the message: under sabotage two tests
    # fail - the calibration one first, and my old matcher only looked for the
    # word "muette" in the failure LINE, which the calibration failure lacks, so
    # the proof reported NO even though the run was properly red.
    stuck = [ln for ln in fails
             if "test_a_silent_connection_is_open_before_and_closed_after" in ln]

    print("--- sabotage: class timeout 15 -> 45 ---")
    for ln in summary:
        print(" ", ln)
    for ln in fails:
        print("  ", ln)
    ok = (proc.returncode != 0 and stuck and not harness_noise)
    print("PROOF RED:", "yes" if ok else "NO")
    if not ok:
        if not stuck:
            print("  -> the failure does not NAME the defect (stuck socket)")
        if harness_noise:
            print("  -> harness noise present:")
            for ln in harness_noise[:5]:
                print("     ", ln)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())