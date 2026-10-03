#!/usr/bin/env python3
"""Proof-red for the popup's "you are AT the tip of main" branch (0.7.21 addendum).

The relay publishes `shipped_tree: 'same'` for TWO materially different
situations, and the popup must not give them the same sentence:

  * main moved on, but only on commits outside `extension/` (since 0.7.19) -
    "the branch has moved on" is TRUE and useful;
  * the deployed tree IS the tip of main (measured 0.7.21) - nothing moved, so
    claiming it did is a lie in exactly the case where the user is fully up to
    date.

`tests/node/test_update_card_truth.js` asserts the distinction. This script
proves those assertions can go RED, and that each red NAMES the defect it is
supposed to catch (skill points 24 / 44 / 56 / 60 / 65).

    python scripts/proof_red_update_tip.py

Exits non-zero unless every sabotage was red AND named, and unless the real
tree is green with the file restored byte for byte.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "extension" / "popup.js"
SUITE = ["node", "tests/node/test_update_card_truth.js", str(ROOT)]

# ---- the real anchors, read from the source, not remembered (point 60) ------
ARM = b"    if (atTip) {"
ARM_GONE = b"    if (updateInfo.shipped_tree === 'same') {"
GUARD = (
    b"    const atTip = updateInfo.current_commit && updateInfo.latest_commit\n"
    b"      && updateInfo.current_commit === updateInfo.latest_commit;"
)
GUARD_FLIPPED = (
    b"    const atTip = updateInfo.current_commit && updateInfo.latest_commit\n"
    b"      && updateInfo.current_commit !== updateInfo.latest_commit;"
)
NO_FALLBACK = (
    b"      updateMeta.textContent = updateInfo.current_version\n"
    b"        ? t('updateUpToDate', updateInfo.current_version)\n"
    b"        : t('updateChipOk');"
)
DANGLING = b"      updateMeta.textContent = t('updateUpToDate', updateInfo.current_version || '');"

# Each sabotage: (id, mutation, the phrase the suite prints when IT catches the
# defect). Expecting a paraphrase demotes a real red to INVALID - take the
# substring from the FAIL line unittest actually prints (point 65).
SABOTAGES = [
    (
        "A",
        "delete the atTip arm - the 'moved on' sentence can no longer be rendered",
        (ARM, ARM_GONE),
        "branche a avance, il rend la phrase exacte",
    ),
    (
        "B",
        "invert the guard (=== -> !==) - the two situations get SWAPPED",
        (GUARD, GUARD_FLIPPED),
        "ne rend PAS la phrase",
    ),
    (
        "C",
        "drop the versionless fallback - a missing version renders a dangling 'v'",
        (NO_FALLBACK, DANGLING),
        "dangling",
    ),
]


def run() -> tuple[int, list[str]]:
    proc = subprocess.run(
        SUITE, capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=ROOT
    )
    return proc.returncode, [ln for ln in proc.stdout.splitlines() if ln.startswith("FAIL")]


def main() -> int:
    original = TARGET.read_bytes()
    pristine = ROOT / "scripts" / "artifacts_pristine" / "popup.js"
    pristine.parent.mkdir(parents=True, exist_ok=True)
    pristine.write_bytes(original)  # snapshot EVERY run (point 45)

    rc, fails = run()
    if rc != 0 or fails:
        print(f"FAIL etat reel : la suite doit etre verte avant de saboter ({rc})")
        for line in fails[:6]:
            print("   ", line[:170])
        return 1
    print("ok   etat reel vert (0 failed)")

    named_red = unnamed_red = invalid = dead = 0
    try:
        for tag, motive, (needle, repl), expect in SABOTAGES:
            if needle not in original:
                print(f"{tag:<4} PATCH-MISS  {motive}")
                invalid += 1
                continue
            mutated = original.replace(needle, repl, 1)
            if mutated == original:  # str.replace never raises: catch it here
                print(f"{tag:<4} SABOTAGE MORT (no-op silencieux)  {motive}")
                dead += 1
                continue
            TARGET.write_bytes(mutated)
            rc, fails = run()
            hit = [ln for ln in fails if expect in ln]
            if rc == 1 and hit:
                named_red += 1
                status = "ROUGE NOMME"
            elif rc == 1 and fails:
                unnamed_red += 1
                status = "ROUGE NON NOMME"
            else:
                invalid += 1
                status = "INVALIDE (exit %d)" % rc
            print(f"{tag:<4} {status:<16} {motive}")
            for line in fails[:4]:
                print("      ", line[:170])
    finally:
        TARGET.write_bytes(original)
        restored = TARGET.read_bytes() == original

    rc, fails = run()
    clean = rc == 0 and not fails
    print()
    print("etat reel apres restauration :", "vert" if clean else "ROUGE")
    print("fichier restaure a l'octet   :", restored)
    # The tally line is a CONTRACT with scripts/acceptance.py: it regex-parses
    # "N/M rouges nommes, K sans nom, I invalides" and FAILS when it cannot find
    # it. Printing my own shape here would have produced a green harness whose
    # measurement the gate silently discarded (point 58, one level up).
    print(
        "\n%d/%d rouges nommes, %d sans nom, %d invalides, %d morts"
        % (named_red, len(SABOTAGES), unnamed_red, invalid, dead)
    )
    if not restored:
        print("FAIL le fichier n'a pas ete restaure a l'octet")
    if len({sab[3] for sab in SABOTAGES}) < len(SABOTAGES):
        print("NOTE deux sabotages partagent le meme `expect` : ils peuvent "
              "rendre la meme sortie")
    ok = named_red == len(SABOTAGES) and invalid == 0 and dead == 0 and clean and restored
    print("RESULT:", "OK" if ok else "ECHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())