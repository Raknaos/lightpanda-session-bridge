#!/usr/bin/env python3
"""Sabotage proof for `tests/test_cookie_transfer_integrity.py`.

A ratchet that was never seen RED is decoration. This harness breaks
`relay/server.py` in the two ways that used to make a partial cookie
transfer report success, and asserts the new suite catches each one:

  1. "silence"  - the refusal is deleted entirely. Layer 1 must go red:
                   a 2/5 sync goes back to being reported as a success.
  2. "at-least-one" - the gap is computed back with `any(...)`. Layer 2 must
                   go red on the forbidden shape even though a partial
                   transfer still raises by accident.

Neither mutation is allowed to survive. The pristine bytes are written to a
marker BEFORE the first mutation, so an interrupted run leaves a recoverable
state on disk, and the marker is removed only after a byte-exact restore has
been verified by sha256.

Usage:
    scripts/proof_red_session_sync.py            # sabotage, assert red, restore
    scripts/proof_red_session_sync.py --repair   # restore a dirty tree and stop
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
TARGET = ROOT / "relay" / "server.py"
MARKER = ROOT / "relay" / ".server.py.session_sync.bak"

# The refusal block, exactly as it exists in the committed source. Whitespace
# must match byte for byte or the mutation silently no-ops -- which would make
# this harness report a green tree for the wrong reason.
REFUSAL = """        if _LAST_COOKIE_MISSING:
            missing_detail = " (missing: %s)" % ", ".join(
                _short_key(n, 40) for n in _LAST_COOKIE_MISSING[:5]
            )
            raise RuntimeError(
                "cookie transfer incomplete: %d/%d cookies verified%s"
                % (max(_LAST_COOKIE_VERIFIED, 0), _LAST_COOKIE_EXPECTED,
                   missing_detail)
            )
"""

# The by-name gap, as a genuine at-least-one predicate: "did ONE cookie
# survive" is the exact reading that let 2/5 report success.
GAP_BY_NAME = """        _LAST_COOKIE_MISSING = [str(item["name"]) for item in converted
                                if str(item["name"]) not in names]"""
GAP_AT_LEAST_ONE = """        _LAST_COOKIE_MISSING = [] if any(
            str(item["name"]) in names for item in converted
        ) else [str(item["name"]) for item in converted]"""

SUITE = "tests.test_cookie_transfer_integrity"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_marker() -> bytes:
    pristine = TARGET.read_bytes()
    MARKER.write_bytes(pristine)
    return pristine


def _restore_and_verify(expected: bytes) -> None:
    """Put the pristine bytes back and PROVE it, rather than assume it."""
    current = TARGET.read_bytes()
    if current != expected:
        TARGET.write_bytes(expected)
        after = TARGET.read_bytes()
        if after != expected:
            raise SystemExit(
                "RESTORE FAILED: %s is %d bytes/sha256 %s, expected %d/%s\n"
                "marker kept at %s -- run with --repair"
                % (TARGET, len(after), _sha256(after)[:16],
                   len(expected), _sha256(expected)[:16], MARKER))
    if not MARKER.exists():
        return
    MARKER.unlink()
    print("restored: %s byte-identical (sha256 %s)"
          % (len(expected), _sha256(expected)[:16]))


def repair() -> int:
    """Recover a tree left dirty by an interrupted run. Idempotent."""
    if not MARKER.exists():
        print("no marker: tree is clean, nothing to repair")
        return 0
    TARGET.write_bytes(MARKER.read_bytes())
    print("repaired: %s restored from marker" % TARGET.name)
    return repair()


def _run_suite() -> tuple[int, str]:
    proc = subprocess.run(
        [str(PYTHON), "-m", "unittest", SUITE],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def _mutate(pristine: bytes, old: str, new: str, label: str) -> None:
    text = pristine.decode("utf-8")
    if old not in text:
        raise SystemExit(
            "MUTATION %r NO-OP: the anchor is not in relay/server.py.\n"
            "The harness would prove a green tree for the wrong reason -- "
            "update the anchor before trusting this run." % label)
    TARGET.write_bytes(text.replace(old, new, 1).encode("utf-8"))


# Three outcomes, never merged (points 44/78):
#   NAMED    - this sabotage is what turned the suite red, and the suite SAID
#              which test. This is the only column that is evidence.
#   UNNAMED  - the suite went red but printed no FAIL:/ERROR: line to point
#              at. That proves only that something broke, which is worth
#              nothing about the ratchet.
#   INVALID  - the sabotage never ran: the anchor is gone, or the tree was
#              already red. A proof that did not run is not a weak proof, it
#              is no proof at all, so it is its own column and the gate
#              refuses it instead of counting it as a red.
NAMED, UNNAMED, INVALID = "named", "unnamed", "invalid"


def check(label: str, old: str, new: str, pristine: bytes) -> str:
    """One sabotage: mutate, assert the suite goes red BY NAME, restore."""
    _mutate(pristine, old, new, label)
    code, out = _run_suite()
    _restore_and_verify(pristine)

    if code == 0:
        print("  %-8s %-14s suite stayed GREEN -- the ratchet does not bite"
              % (INVALID, label))
        print("  " + out.strip().replace("\n", "\n  ")[-1200:])
        return INVALID

    fails = [ln for ln in out.splitlines() if ln.startswith(("FAIL:", "ERROR:"))]
    if not fails:
        print("  %-8s %-14s suite went RED but named no failure -- that proves "
              "something broke, not this sabotage" % (UNNAMED, label))
        print("  " + out.strip().replace("\n", "\n  ")[-1200:])
        return UNNAMED

    print("  %-8s %-14s suite went RED as required (%d named)"
          % (NAMED, label, len(fails)))
    for ln in fails:
        print("          %s" % ln)
    return NAMED


def main(argv: list[str]) -> int:
    if "--repair" in argv:
        return repair()
    if MARKER.exists():
        print("marker already present: a previous run was interrupted.")
        print("run with --repair first, then re-run this proof.")
        return 2

    pristine = _write_marker()
    print("marker written: %d bytes, sha256 %s"
          % (len(pristine), _sha256(pristine)[:16]))
    print("baseline (unmutated) suite:")
    code, out = _run_suite()
    print("  %s -- %s" % ("GREEN" if code == 0 else "RED",
                           next((ln for ln in out.splitlines()
                                 if ln.startswith("Ran ")), "?")
                           or next((ln for ln in out.splitlines()
                                    if ln.strip()), "?")))
    if code != 0:
        _restore_and_verify(pristine)
        print("ABORT: the suite is already red on a clean tree; fix that first.")
        return 2

    results = [
        check("silence", REFUSAL, "", pristine),
        check("at-least-one", GAP_BY_NAME, GAP_AT_LEAST_ONE, pristine),
    ]

    if TARGET.read_bytes() != pristine:
        raise SystemExit("tree is dirty after the run; repair before committing")

    # The canonical tally, in the shape `acceptance.proof_red_tally` parses.
    # It is printed unconditionally -- including on failure -- because a run
    # that refused MUST say which column it refused on, or the gate sees no
    # tally at all and reports "printed no tally" instead of the real verdict.
    # `total` is the number of sabotages this file RUN, `named` the number the
    # suite proved red BY NAME: the gap between them is what went unnamed.
    named = results.count(NAMED)
    unnamed = results.count(UNNAMED)
    invalid = results.count(INVALID)
    total = len(results)
    print("-" * 72)
    print("%d/%d named red, %d unnamed, %d invalid" % (named, total, unnamed, invalid))

    if named == total and not unnamed and not invalid:
        print("PROOF RED OK: every sabotage was caught by name, tree restored clean")
        return 0
    print("PROOF RED FAILED: a sabotage went unnoticed or was not named")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))