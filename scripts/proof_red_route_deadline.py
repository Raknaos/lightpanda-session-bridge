"""Proof-red for the per-route deadline bound.

Sabotages relay/server.py, one at a time, and must see the intended test go RED
BY NAME. Restores from a pristine copy written to disk BEFORE the edit - never
`git checkout` (skill point 31).

Usage: python scripts/proof_red_route_deadline.py
"""
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "relay" / "server.py"
TEST = ROOT / "tests" / "test_route_deadline_bound.py"
PRISTINE = SERVER.with_suffix(".py.pristine-proofred")

SABOTAGES = [
    (
        "une route elargit a 600s sans etre declaree",
        r"self\.connection\.settimeout\(30\)",
        "self.connection.settimeout(600)",
        "test_no_route_can_widen_the_deadline_without_being_declared",
    ),
    (
        "le backstop de classe disparait",
        r"^    timeout = 15$",
        "    timeout = None",
        "test_the_class_deadline_is_still_present_and_sane",
    ),
    (
        "le backstop devient enorme (300s)",
        r"^    timeout = 15$",
        "    timeout = 300",
        "test_the_class_deadline_is_still_present_and_sane",
    ),
    (
        "la route volontairement plus large disparait",
        r"self\.connection\.settimeout\(30\)",
        "self.connection.settimeout(10)",
        "test_the_deliberate_wider_route_still_exists_and_is_bounded",
    ),
]

# setUpClass raises on a missing class deadline, which unittest reports as an
# ERROR for the whole class - so a class-wide match is the honest expectation
# there, not a single named FAIL.
CLASS_WIDE = {"test_the_class_deadline_is_still_present_and_sane"}


def run():
    p = subprocess.run(
        [str(ROOT / ".venv" / "Scripts" / "python.exe"), "-m", "unittest",
         "discover", "-s", "tests", "-p", "test_route_deadline_bound.py"],
        capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    return p.returncode, p.stdout + p.stderr


def main():
    if not PRISTINE.exists():
        shutil.copy2(SERVER, PRISTINE)
    original = PRISTINE.read_text(encoding="utf-8")
    results = []
    try:
        for label, pattern, repl, expect in SABOTAGES:
            sabotaged, n = re.subn(pattern, repl, original, count=1, flags=re.M)
            if n != 1:
                print(f"ABORT: sabotage '{label}' n'a pas matche ({n})")
                return 2
            if sabotaged == original:
                print(f"ABORT: sabotage '{label}' n'a produit AUCUN changement")
                return 2
            SERVER.write_text(sabotaged, encoding="utf-8", newline="")
            rc, out = run()
            if expect in CLASS_WIDE:
                red = rc != 0 and (f"FAIL: {expect}" in out or "ERROR" in out)
            else:
                red = rc != 0 and f"FAIL: {expect}" in out
            results.append((label, red, out))
            SERVER.write_text(original, encoding="utf-8", newline="")
            ok = SERVER.read_text(encoding="utf-8") == original
            print(f"  restaure apres '{label}': {'ok' if ok else 'MISMATCH'}")
            if not ok:
                print("FATAL: restauration incomplete")
                return 2
    finally:
        SERVER.write_text(original, encoding="utf-8", newline="")
        ok_restored = SERVER.read_text(encoding="utf-8") == original
        print(f"restaure finale verifie: {ok_restored}")
        print(f"marqueur production present: {'    timeout = 15' in original}")
        PRISTINE.unlink(missing_ok=True)
        if not ok_restored:
            sys.exit(2)

    rc, out = run()
    green = rc == 0 and bool(out.strip())
    print(f"\nrun sans sabotage: {'GREEN' if green else 'RED'}")

    all_red = True
    named_n = unnamed_n = invalid_n = 0
    print("\n--- par sabotage ---")
    for label, red, out in results:
        status = "RED (nomme)" if red else "NON PROUVE"
        if red:
            named_n += 1
        else:
            # Not red and not attributable: the sabotage did not prove anything,
            # which is INVALID, not a red that happened to be unnamed (point 44).
            invalid_n += 1
        if not red:
            all_red = False
        print(f"  {status:14} {label}")
        if not red:
            print("\n".join("      " + l for l in out.strip().splitlines()[-6:]))

    # Tally line is a CONTRACT with scripts/acceptance.py (points 44/58/78).
    print("\n%d/%d named red, %d unnamed, %d invalid"
          % (named_n, len(results), unnamed_n, invalid_n))
    print(f"\nPROOF RED: {'yes' if (all_red and green) else 'NO'}")
    return 0 if (all_red and green) else 1


if __name__ == "__main__":
    sys.exit(main())
