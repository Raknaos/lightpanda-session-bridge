#!/usr/bin/env python3
"""Proof-red for the diagnostic report's update facts.

Measured defect (0.7.21): the report published `update_available` and nothing
else, so a user pasting it could not tell "nothing new" from "an update is
pending but unreachable". Adding the reason introduced a SECOND, worse defect
that only this script found: `update_note` is written by the RELAY, so it is
foreign text, but it lived in a dict this module builds and therefore trusted -
and a note reading "Authorization: Bearer ghp_A1...Q7r8" shipped 12 characters
of the token in a report meant to be pasted in public.

Four sabotages, four NAMED reds, zero invalid. A PATCH-MISS or an import
failure exits non-zero and is reported separately (points 44 / 51 / 56 / 57).
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TARGET = ROOT / "relay" / "diagnostics.py"
PY = ROOT / ".venv" / "Scripts" / "python.exe"

# (label, old, new, substring the AssertionError must actually print)
SABOTAGES = [
    ("note leaks a truncated credential into the public report",
     '        "update_note": scrub(data.get("note") or "") or None,',
     '        "update_note": _short(data.get("note"), 40) or None,',
     "ghp_A1"),

    ("note eaten by the scrubber (the reason is lost)",
     '        "update_note": scrub(data.get("note") or "") or None,',
     '        "update_note": "[redacted]",',
     "cb4bdf5"),

    ("update_state absent: the reason is no longer published",
     '        "update_state": data.get("shipped_tree"),',
     '        # state removed',
     "update_state"),

    ("the note is no longer published at all",
     '        "update_note": scrub(data.get("note") or "") or None,',
     '        # note removed',
     "update_note"),
]

HARNESS_SHAPES = ("unittest.loader._FailedTest", "ModuleNotFoundError",
                   "Failed to import test module")


def run_suite() -> str:
    """Discover by pattern, never by dotted name: `tests/` is not a package
    (point 57)."""
    proc = subprocess.run(
        [str(PY), "-m", "unittest", "discover", "-s", "tests",
         "-p", "test_diagnostics.py"],
        cwd=str(ROOT), capture_output=True, text=True, timeout=400)
    return proc.stdout + proc.stderr


def main() -> int:
    pristine = TARGET.read_bytes()          # bytes, so CRLF survives (point 55)
    source = pristine.decode("utf-8")
    named = unnamed = invalid = 0

    for label, old, new, expect in SABOTAGES:
        if old not in source:
            print("PATCH-MISS  %s\n             the motive no longer matches; "
                  "this proof did NOT run (point 56)" % label)
            invalid += 1
            continue
        TARGET.write_text(source.replace(old, new, 1), encoding="utf-8", newline="")
        try:
            out = run_suite()
            if any(shape in out for shape in HARNESS_SHAPES):
                print("HARNIS      %s\n             the suite failed to load; "
                      "this is a harness fault, not a red (point 57)" % label)
                invalid += 1
                continue
            messages = [ln.strip() for ln in out.splitlines()
                        if ln.strip().startswith("AssertionError")]
            hit = [m for m in messages if expect in m]
            if hit:
                # An AssertionError on a whole-rendered report carries the
                # entire report; quote the verdict, not the payload.
                print("ROUGE       %s\n             %s" % (label, hit[0][:200]))
                named += 1
            else:
                print("SANS NOM    %s\n             red but unnamed: it proves "
                      "something broke, not that this guard can fail (point 51)"
                      % label)
                unnamed += 1
        finally:
            TARGET.write_bytes(pristine)   # bytes back, never git checkout (31)

    total = len(SABOTAGES)
    print("\n%d/%d rouges nommes, %d sans nom, %d invalides" %
          (named, total, unnamed, invalid))
    if TARGET.read_bytes() != pristine:
        print("RESTORE FAILED - the file no longer matches the pre-run bytes")
        return 2
    print("fichier restaure a l'octet pres")
    return 0 if (named == total and unnamed == 0 and invalid == 0) else 1


if __name__ == "__main__":
    sys.exit(main())