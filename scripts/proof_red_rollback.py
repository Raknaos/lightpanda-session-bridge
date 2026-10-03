#!/usr/bin/env python3
"""Preuve rouge : l'annulation doit etre joignable quand une sauvegarde existe.

Un seul sabotage : retablir l'ecrasement qui rendait le bouton injoignable.
Il doit produire un rouge NOMME, et popup.js doit etre restaure a l'octet.

Le point interessant est ce que le test PRouve aussi : une fois la ligne
d'ecrasement remise, les cinq autres assertions restent vertes. Un test qui
 rougirait partout n'aurait pas designe ce defaut-la, il aurait designe "le
fichier a change".

Run: python scripts/proof_red_rollback.py
"""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POPUP = ROOT / "extension" / "popup.js"
TEST = ROOT / "tests" / "node" / "test_rollback_reachable.js"
PRISTINE = ROOT / "scripts" / "artifacts_pristine" / "popup.js.proof_red_rollback"

SABOTAGE = (
    "    updateBtn.style.display = 'none';\n"
    "    // Measured 0.7.26: `rollbackBtn.style.display` was already computed correctly",
    "    updateBtn.style.display = 'none';\n"
    "    rollbackBtn.style.display = 'none';\n"
    "    // Measured 0.7.26: `rollbackBtn.style.display` was already computed correctly",
)
EXPECTED = "undo joignable apres une installation (backup present)"


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
    if PRISTINE.read_bytes() != original:
        code, out = run_test()
        if code != 0:
            print("ECHEC : popup.js est rouge et differe de la copie pristine.")
            print(out[-1200:])
            return 2
        PRISTINE.write_bytes(original)
        print("copie pristine rafraichie (popup.js a change legitimement)")

    code, out = run_test()
    if code != 0:
        print("ECHEC : le test est rouge AVANT toute correction")
        print(out[-1500:])
        return 2
    print("etat de depart :", out.strip().splitlines()[-1])

    text = original.decode("utf-8")
    if SABOTAGE[0] not in text:
        print("\n  PATCH-MISS : le motif n'existe plus dans popup.js")
        print("\n0/1 named red, 1 invalid - PAS PREUVE")
        return 1

    POPUP.write_text(text.replace(SABOTAGE[0], SABOTAGE[1], 1),
                     encoding="utf-8", newline="")
    # The restore is inside `finally` because the ONLY thing between the sabotage
    # and the restore is the test run, and that is exactly what can hang or raise
    # (point 31: a killed process never runs its `finally`). Written inline, a
    # failure here leaves popup.js carrying a dead `rollbackBtn.style.display`
    # and no test in the suite can tell, because the suite is also sabotaged.
    try:
        code, out = run_test()
    finally:
        POPUP.write_bytes(original)
        restored = POPUP.read_bytes() == original

    red = [ln for ln in out.splitlines() if ln.startswith("  FAIL")]
    print("\nA. l'ecrasement du bouton est retabli")
    if code == 0:
        print("  ROUGE MANQUANT : le sabotage ne fait pas echouer le test")
        print("\n0/1 named red, 1 invalid - PAS PREUVE")
        return 1
    if not any(EXPECTED in ln for ln in red):
        print("  ROUGE NON NOMME : aucun FAIL contenant %r" % EXPECTED)
        print("\n0/1 named red, 1 invalid - PAS PREUVE")
        return 1
    print("  ROUGE NOMME")
    for ln in red:
        print("   " + ln.strip()[:150])
    # The summary line is the one carrying "N passed"; the failure LIST below it
    # ends with a "- <name>" bullet, so taking `splitlines()[-1]` printed a
    # failure name instead of the count and read like a wrong number.
    summary = next((l.strip() for l in out.splitlines()
                    if re.search(r"\d+\s+passed", l)), "(pas de compteur)")
    print("  compteur :", summary, "(les autres assertions restent vertes)")

    print("\n" + "=" * 66)
    print("1/1 named red, 0 invalid")
    print("popup.js restaure a l'octet :", POPUP.read_bytes() == original)
    return 0


if __name__ == "__main__":
    sys.exit(main())