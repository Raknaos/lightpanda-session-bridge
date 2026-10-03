#!/usr/bin/env python3
"""Preuve rouge : un echec d'installation doit nommer sa cause.

Deux fautes distinctes, deux sabotages distincts. Chaque sabotage doit
produire un FAIL NOMME, et le fichier doit etre restaure a l'octet.

  A. `runUpdate` replaces the relay's refusal with "relay unreachable" again.
     Every refusal collapses onto one sentence.
  B. `t()` stops formatting a string placeholder, so an unmapped code shows a
     literal `{0}` and the code itself never reaches the user.

Harness lessons applied here (each one was a wasted run on this very file):
  - restore by BYTES from the pristine copy, never `git checkout` on uncommitted
    work;
  - assert on the test's OWN printed failure line, not on wording copied from
    a comment;
  - `PATCH-MISS` is a first-class outcome: if a sabotage changes nothing, the
    run is INVALID, not green.

Run: python scripts/proof_red_update_failure.py
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POPUP = ROOT / "extension" / "popup.js"
TEST = ROOT / "tests" / "node" / "test_update_failure_text.js"
PRISTINE = ROOT / "scripts" / "artifacts_pristine" / "popup.js.proof_red_update_failure"

# (label, old, new, the test line that MUST then appear)
SABOTAGES = [
    (
        "A. le catch rebouche sur « relais injoignable »",
        "    } else if (error && error.relayCode) {\n"
        "      reason = relayErrorText(error.relayCode);\n"
        "    } else {\n"
        "      reason = t('errRelayUnreachable');\n"
        "    }",
        "    } else {\n"
        "      reason = t('errRelayUnreachable');\n"
        "    }",
        "ne dit pas \"relais hors ligne\"",
    ),
    (
        "B. t() ne substitue plus {0} dans une chaine",
        "  if (typeof val === 'function') return val(...args);\n"
        "  if (args.length && typeof val === 'string' && val.includes('{0}')) {\n"
        "    return val.replace('{0}', args[0]);\n"
        "  }\n"
        "  return val;",
        "  if (typeof val === 'function') return val(...args);\n"
        "  return val;",
        "aucun {0} residue",
    ),
]


def run_test() -> tuple[int, str]:
    proc = subprocess.run(
        ["node", str(TEST), str(ROOT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, proc.stdout + proc.stderr


def main() -> int:
    if not PRISTINE.exists():
        PRISTINE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(POPUP, PRISTINE)
        print(f"copie pristine creee : {PRISTINE.name}")

    original = POPUP.read_bytes()
    # The pristine copy is the state this harness was written against, so it goes
    # STALE the moment popup.js legitimately changes. Refresh it unless the file
    # on disk is a SABOTAGE (the test red) - otherwise a fresh checkout would
    # refuse to run and read as a broken harness.
    if PRISTINE.read_bytes() != original:
        code, out = run_test()
        if code != 0:
            print("ECHEC : popup.js est rouge et differe de la copie pristine.")
            print(out[-1500:])
            return 2
        PRISTINE.write_bytes(original)
        print("copie pristine rafraichie (popup.js a change legitimement)")

    code, out = run_test()
    if code != 0:
        print("ECHEC : le test est rouge AVANT toute correction")
        print(out[-2000:])
        return 2
    print(f"etat de depart : {out.strip().splitlines()[-1]}")

    named = 0
    invalid = 0
    for label, old, new, expected in SABOTAGES:
        text = original.decode("utf-8")
        if old not in text:
            print(f"\n{label}\n  PATCH-MISS : le motif n'existe plus dans popup.js")
            invalid += 1
            POPUP.write_bytes(original)
            continue

        POPUP.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
        code, out = run_test()
        POPUP.write_bytes(original)

        hit = expected in out
        if code == 0:
            print(f"\n{label}\n  ROUGE MANQUANT : le sabotage ne fait pas echouer le test")
            invalid += 1
            continue
        if not hit:
            print(f"\n{label}\n  ROUGE NON NOMME : aucun FAIL contenant {expected!r}")
            invalid += 1
            continue
        tail = [ln for ln in out.splitlines() if ln.startswith("  FAIL")][:3]
        named += 1
        print(f"\n{label}\n  ROUGE NOMME")
        for ln in tail:
            print("   " + ln.strip()[:150])

    print("\n" + "=" * 66)
    if invalid:
        print(f"{named} named red, {invalid} invalid — PAS PREUVE")
        return 1
    print(f"{named}/{len(SABOTAGES)} named red, 0 invalid")
    print("popup.js restaure a l'octet :", POPUP.read_bytes() == original)
    return 0


if __name__ == "__main__":
    sys.exit(main())