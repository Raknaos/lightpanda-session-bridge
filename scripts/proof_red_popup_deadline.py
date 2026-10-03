"""Proof-red for the popup relay deadline.

Sabotages ONE thing at a time in extension/popup.js, runs the real Node suite,
and must observe the intended test go RED (by NAME, not by message - under
sabotage the first failure may be a calibration check, not the target).

Restores from a pristine copy written to disk BEFORE the edit - never
`git checkout`, which restores HEAD and would discard the uncommitted work
(skill point 31).

Usage: python scripts/proof_red_popup_deadline.py
"""
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POPUP = ROOT / "extension" / "popup.js"
SUITE = ROOT / "tests" / "node" / "test_relay_deadline.js"
PRISTINE = POPUP.with_suffix(".js.pristine-proofred")

# (label, pattern, replacement, test name that must fail)
SABOTAGES = [
    (
        "delai retire (relayFetch sans AbortController)",
        r"const controller = new AbortController\(\);",
        "const controller = { signal: {}, abort() {} };",
        "un relais muet termine en RelayTimeoutError",
    ),
    (
        "mapping i18n des codes du relais supprime",
        r"const RELAY_ERROR_KEYS = \{[\s\S]*?\n\};",
        "const RELAY_ERROR_KEYS = {};",
        "les codes du relais deviennent du texte traduit",
    ),
]


def run_suite():
    proc = subprocess.run(
        ["node", str(SUITE)], capture_output=True, text=True, timeout=180, cwd=str(ROOT)
    )
    return proc.returncode, proc.stdout + proc.stderr


def sanity(popup_text):
    """A sabotaged run that prints NOTHING and exits 0 is not a green run - it
    is a suite that died before its first assertion (observed once: a heredoc
    truncation removed half the file, so every symbol vanished and the async
    IIFE exited silently). Refuse to score it."""
    for marker in ("class RelayTimeoutError", "function relayErrorText",
                   "async function relayFetch", "const RELAY_ERROR_KEYS"):
        if marker not in popup_text:
            return f"fichier incomplet (absent: {marker})"
    return None


def main():
    if not PRISTINE.exists():
        shutil.copy2(POPUP, PRISTINE)
    original = PRISTINE.read_text(encoding="utf-8")
    print(f"pristine copy: {PRISTINE.name}")

    results = []
    try:
        for label, pattern, repl, expect in SABOTAGES:
            sabotaged, n = re.subn(pattern, repl, original, count=1)
            if n != 1:
                print(f"ABORT: sabotage '{label}' did not match ({n} matches)")
                return 2
            # A subn that MATCHES can still produce identical text (e.g. the
            # value was already the sabotaged one). Proving "RED" on an
            # unchanged file is a vacuous proof - refuse it outright.
            if sabotaged == original:
                print(f"ABORT: sabotage '{label}' produced NO change")
                return 2
            POPUP.write_text(sabotaged, encoding="utf-8", newline="")
            problem = sanity(sabotaged)
            if problem:
                print(f"ABORT: sabotage '{label}' corrompt le fichier: {problem}")
                return 2
            rc, out = run_suite()
            named = re.search(rf"FAIL {re.escape(expect)}", out)
            results.append((label, rc != 0, bool(named), out))

            # Restore immediately so each sabotage is independent.
            POPUP.write_text(original, encoding="utf-8", newline="")
            print(f"  restored after '{label}': "
                  f"{'ok' if POPUP.read_text(encoding='utf-8') == original else 'MISMATCH'}")
    finally:
        POPUP.write_text(original, encoding="utf-8", newline="")
        ok_restored = POPUP.read_text(encoding="utf-8") == original
        print(f"final restore verified: {ok_restored}")
        print(f"production marker present: {'const controller = new AbortController();' in original}")
        if not ok_restored:
            print("FATAL: file not restored from the pristine copy")
            PRISTINE.unlink(missing_ok=True)
            sys.exit(2)          # in finally: a bare `return` is a SyntaxWarning
        PRISTINE.unlink(missing_ok=True)

    rc, out = run_suite()
    green = rc == 0 and bool(out.strip())
    if rc == 0 and not out.strip():
        print("ABORT: sabotage-free run produced no output at all")
        return 2
    print(f"\nsabotage-free run: {'GREEN' if green else 'RED'}")

    print("\n--- per sabotage ---")
    all_red = True
    named_n = unnamed_n = invalid_n = 0
    for label, nonzero, named, out in results:
        status = "RED (named)" if (nonzero and named) else "NOT PROVEN"
        if nonzero and named:
            named_n += 1
        elif nonzero:
            # A red the harness could not attribute to this defect proves only
            # that SOMETHING broke (point 24) - its own column, never the red one.
            unnamed_n += 1
        else:
            invalid_n += 1
        if not (nonzero and named):
            all_red = False
        print(f"  {status:12} {label}")
        if not (nonzero and named):
            print("\n".join("      " + l for l in out.strip().splitlines()[-8:]))

    # Tally line is a CONTRACT with scripts/acceptance.py (points 44/58/78).
    print("\n%d/%d named red, %d unnamed, %d invalid"
          % (named_n, len(results), unnamed_n, invalid_n))
    print(f"\nPROOF RED: {'yes' if (all_red and green) else 'NO'}")
    return 0 if (all_red and green) else 1


if __name__ == "__main__":
    sys.exit(main())
