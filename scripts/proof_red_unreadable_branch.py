#!/usr/bin/env python3
"""Proof-red for the UNREADABLE BRANCH path (0.7.22).

Measured on the live relay path: when GitHub answered for the release but not for
the branch, `head` came back None, `check_update` fell through every arm, and
the relay answered `update_available: False`, `shipped_tree: "unknown"`, no
note - which the popup rendered as "À jour". That is the unmeasured claim
0.7.20 had to retract, reintroduced through a different door.

Two defects, two fixes, five sabotages:

  1. `head is None` had no arm, so `unreachable_branch` was never set.
  2. `head["sha"]` assumed a mapping. `latest_commit` is external data; when it
     returns anything that is not a commit mapping, the TypeError landed INSIDE
     the check and the popup's update path 500'd.

    python scripts/proof_red_unreadable_branch.py

Exits non-zero unless every sabotage produced a NAMED red and the real tree is
green with the files restored byte for byte.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELAY = ROOT / "relay" / "updater.py"
SUITE = ["-m", "unittest", "discover", "-s", "tests", "-p", "test_updater.py"]

# Anchors read from the source, not remembered (point 60).
GUARD_OLD = b"""        if not isinstance(head, dict) or not head.get("sha"):
            head = None"""
GUARD_GONE = b"        head = latest_commit(repo)\n        if True:\n            head = head"

ARM_OLD = b"""        elif head is None:"""
ARM_SILENT = b"""        elif False:"""

SEED_OLD = b'            "unreachable_branch": False,'
SEED_GONE = b"            # unreachable_branch removed by sabotage"

# (id, motive, mutations [(needle, replacement)], expected substring of the
# failure NAME the suite prints - taken from a real run, never paraphrased).
SABOTAGES = [
    (
        "A",
        "remove the `head is None` arm - an unread branch is silent again",
        [(ARM_OLD, ARM_SILENT)],
        "nothing marked the state as unread",
    ),
    (
        "B",
        "remove the non-dict guard - `head['sha']` raises TypeError again",
        [(GUARD_OLD, GUARD_GONE)],
        "'function' object is not subscriptable",
    ),
    (
        "C",
        "remove the seeded key - `unreachable_branch` only exists on failure",
        [(SEED_OLD, SEED_GONE)],
        "not found in",
    ),
]


def run() -> tuple[int, str]:
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    proc = subprocess.run([str(py), *SUITE], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=ROOT)
    return proc.returncode, (proc.stdout or proc.stderr or "")


def main() -> int:
    original = RELAY.read_bytes()
    pristine = ROOT / "scripts" / "artifacts_pristine" / "updater.py"
    pristine.parent.mkdir(parents=True, exist_ok=True)
    pristine.write_bytes(original)  # snapshot EVERY run (point 45)

    rc, out = run()
    if rc != 0:
        print("FAIL etat reel : la suite doit etre verte avant de saboter")
        for line in out.splitlines()[-14:]:
            print("   ", line[:170])
        return 1
    tail = out.strip().splitlines()[-1]
    print("ok   etat reel :", tail)

    named = unnamed = invalid = dead = 0
    try:
        for tag, motive, mutations, expect in SABOTAGES:
            data = original
            missing = False
            for needle, repl in mutations:
                if needle not in data:
                    missing = True
                    break
                data = data.replace(needle, repl, 1)
            if missing:
                print(f"{tag:<4} PATCH-MISS  {motive}")
                invalid += 1
                continue
            if data == original:
                print(f"{tag:<4} SABOTAGE MORT (no-op silencieux)  {motive}")
                dead += 1
                continue
            RELAY.write_bytes(data)
            rc, out = run()
            # Search the WHOLE output, not just the FAIL:/ERROR: header lines:
            # unittest puts the assertion MESSAGE in the FAILURE block, so a
            # harness that only reads the header can never confirm WHICH defect
            # it caught, and reports every real red as unnamed (point 24: an
            # unnamed red proves nothing about the guard).
            headers = [ln for ln in out.splitlines() if ln.startswith(("FAIL:", "ERROR:"))]
            hit = [ln for ln in out.splitlines()
                   if ln.strip().startswith(("AssertionError", "TypeError", "KeyError"))
                   and expect in ln]
            if rc != 0 and hit:
                named += 1
                status = "ROUGE NOMME"
            elif rc != 0 and headers:
                unnamed += 1
                status = "ROUGE NON NOMME"
            else:
                invalid += 1
                status = f"INVALIDE (exit {rc})"
            print(f"{tag:<4} {status:<16} {motive}")
            for line in (hit or headers)[:3]:
                print("      ", line.strip()[:170])
    finally:
        RELAY.write_bytes(original)
        restored = RELAY.read_bytes() == original

    rc, out = run()
    clean = rc == 0
    print()
    print("etat reel apres restauration :", "vert" if clean else "ROUGE")
    print("relay/updater.py restaure   :", restored)
    # Tally line is a CONTRACT with scripts/acceptance.py (see point 58).
    print("\n%d/%d rouges nommes, %d sans nom, %d invalides, %d morts"
          % (named, len(SABOTAGES), unnamed, invalid, dead))
    if not restored:
        print("FAIL relay/updater.py n'a pas ete restaure a l'octet")
    ok = named == len(SABOTAGES) and invalid == 0 and dead == 0 and clean and restored
    print("RESULT:", "OK" if ok else "ECHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())