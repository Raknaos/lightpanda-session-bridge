# -*- coding: utf-8 -*-
"""Proof-red for the class-level socket deadline.

Reverts the fix in relay/server.py and asserts that the new tests go RED for
the RIGHT reason - a connection that sends nothing stays open - rather than for
a harness reason (NameError, a missing attribute, an unbound port).

NEVER `git checkout <file>` for this: relay/server.py carries uncommitted
work. The pristine copy is written to disk BEFORE the edit and restored from it.

If this script is ever killed mid-run, the sabotage stays in the tree. Run
`python scripts/proof_red_socket_timeout.py --repair` to put it back; it reads
the on-disk marker and cannot re-sabotage anything. Same flag, same meaning in
scripts/proof_red_update_report.py for relay/diagnostics.py.
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


def repair() -> int:
    """Restore relay/server.py from the marker, byte-exactly. Standalone.

    Measured 2026-10-05: a 420s tool timeout killed this harness mid-run, so
    neither the edit nor its `finally` completed and the tree kept `timeout =
    45`. The gate caught it a step later, but only the gate. `python
    proof_red_socket_timeout.py --repair` puts the recovery in one command that
    cannot re-sabotage anything, so the next person (or the next agent) does not
    have to re-derive the fix by hand the way I had to.
    """
    marker = SERVER.with_suffix(".py.sabotaged-by-socket-timeout")
    if not marker.exists():
        print("nothing to repair: no marker at", marker)
        return 0
    pristine = marker.read_bytes()
    current = SERVER.read_bytes()
    if current == pristine:
        print("tree already pristine; retiring marker")
        marker.unlink()
        return 0
    print("repairing: %d bytes on disk, %d pristine in marker"
          % (len(current), len(pristine)))
    SERVER.write_bytes(pristine)
    assert SERVER.read_bytes() == pristine, "repair not byte-exact"
    marker.unlink()
    print("repaired byte-exactly")
    return 0


def main() -> int:
    if "--repair" in sys.argv:
        return repair()
    original = SERVER.read_text(encoding="utf-8")
    backup = pathlib.Path(tempfile.mkdtemp(prefix="lp-proofred-")) / "server.py"
    backup.write_text(original, encoding="utf-8", newline="")
    assert backup.read_text(encoding="utf-8") == original, "backup not faithful"

    # A kill -9, a timeout, or a closed laptop leaves the `finally` restore
    # unrun, and the sabotage becomes the tree the NEXT run verifies against -
    # exactly how `timeout = 15` silently became `timeout = 45` on 2026-10-05.
    # The marker is written BEFORE the edit and removed only on a clean restore,
    # and it carries the PRISTINE BYTES rather than just their hash: the marker
    # that survived that kill had a hash and no way to act on it, so the only
    # recovery was re-deriving the fix by hand. With the source in the marker,
    # repair() can put the tree back byte-exactly without re-running this
    # harness (which would re-sabotage the file).
    marker = SERVER.with_suffix(".py.sabotaged-by-socket-timeout")
    marker.write_bytes(original.encode("utf-8"))
    assert marker.read_bytes() == original.encode("utf-8"), "marker not faithful"

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
    # A subn that MATCHES can still produce an identical string, and then the
    # whole run is vacuous: sabotaged == original means the "proof red" would be
    # testing the shipped code. An audit flagged exactly this on the earlier 600s
    # version (production was 15, the regex still matched, and sabotage was a
    # no-op - PROOF RED could only ever pass vacuously). Assert it here instead
    # of trusting the pattern.
    if sabotaged == original:
        print("ABORT: the sabotage produced an IDENTICAL file - the proof "
              "would be vacuous (production deadline is already 45?)")
        return 2
    if not re.search(r"^\s*timeout = 15$", original, re.MULTILINE):
        print("ABORT: production deadline is not 15s; re-derive SABOTAGE and the "
              "test's ATTEND_WINDOW before trusting this script")
        return 2
    SERVER.write_text(sabotaged, encoding="utf-8", newline="")
    budget = 420
    restored = False
    try:
        proc = subprocess.run(
            [PY, "-m", "unittest", "discover", "-s", "tests",
             "-p", "test_socket_timeout.py"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=budget)
    finally:
        SERVER.write_text(original, encoding="utf-8", newline="")
        restored = SERVER.read_text(encoding="utf-8") == original
        assert restored, "restore failed"
        # Only a VERIFIED byte-exact restore retires the marker. If the restore
        # raised, `unlink` below never runs, so the marker survives and the next
        # run still knows the tree owes a restore.
        if restored:
            marker.unlink(missing_ok=True)
        print("fix restored:", restored)

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

    # An import failure or a failed PATCH-MISS means the PROOF never ran; it is
    # INVALID, never a red (points 56/57/70).
    import_broke = [ln for ln in out.splitlines()
                    if "unittest.loader._FailedTest" in ln
                    or ln.startswith(("ModuleNotFoundError", "ImportError"))]

    print("--- sabotage: class timeout 15 -> 45 ---")
    for ln in summary:
        print(" ", ln)
    for ln in fails:
        print("  ", ln)
    ok = (proc.returncode != 0 and stuck and not harness_noise and not import_broke)
    print("PROOF RED:", "yes" if ok else "NO")
    if not ok:
        if not stuck:
            print("  -> the failure does not NAME the defect (stuck socket)")
        if import_broke:
            print("  -> the suite could not be imported - harness failure, not a red")
            for ln in import_broke[:5]:
                print("     ", ln)
        if harness_noise:
            print("  -> harness noise present:")
            for ln in harness_noise[:5]:
                print("     ", ln)
    # Tally line is a CONTRACT with scripts/acceptance.py (points 44/58/78):
    # one sabotage, so the tally is 1/1 named or the two refuse columns explain why.
    if ok:
        named_n, unnamed_n, invalid_n = 1, 0, 0
    elif stuck and not harness_noise and not import_broke:
        named_n, unnamed_n, invalid_n = 0, 1, 0
    else:
        named_n, unnamed_n, invalid_n = 0, 0, 1
    print("\n%d/1 named red, %d unnamed, %d invalid" % (named_n, unnamed_n, invalid_n))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())