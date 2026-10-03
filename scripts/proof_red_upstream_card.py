#!/usr/bin/env python3
"""Proof-red for the UPSTREAM failure card (0.7.24).

Measured live on 0.7.23: `/health` returned 200 with `ok: true`, and the update
card still read "Relay Offline". The relay had answered perfectly - GitHub had
refused - and both failures collapse into `!updateInfo.ok`, so the popup sent the
user to debug a working installation. The relay has been publishing
`error_kind` ("rate_limit" / "unreachable") the whole time; the popup never read
it.

Four sabotages, each of which must produce a NAMED red:

  A. collapse both failures back into `relayOffline`
  B. read `error_kind` but ignore it, so a rate limit renders the generic line
  C. claim a rate limit for ANY upstream error (the false-positive direction)
  D. put the relay's raw message in the panel instead of the tooltip

    python scripts/proof_red_upstream_card.py

Exits non-zero unless every sabotage produced a NAMED red and the real tree is
green with popup.js restored byte for byte.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "extension" / "popup.js"
SUITE = ["node", "tests/node/test_update_card_truth.js", str(ROOT)]

# Anchors read from the source, not remembered (point 60).
UPCALL_OLD = b"""    updateChip.textContent = upstream ? t('updateGitHubDown') : t('relayOffline');"""
UPCALL_FLAT = b"""    updateChip.textContent = t('relayOffline');"""

METACHOICE_OLD = b"""      ? t(kind === 'rate_limit' ? 'updateRateLimited' : 'updateGitHubDown')"""
METACHOICE_FLAT = b"""      ? t('updateGitHubDown')"""

RATE_OVERREACH_OLD = b"""    const kind = (updateInfo && updateInfo.error_kind) || '';"""
RATE_OVERREACH_NEW = b"""    const kind = 'rate_limit';"""

TITLE_OLD = b"""    updateMeta.title = upstream ? String(updateInfo.error || '') : '';"""
TITLE_LEAK = b"""    updateMeta.textContent = upstream ? String(updateInfo.error || '') : '';
    updateMeta.title = '';"""

SABOTAGES = [
    ("A", "collapse both failures back into 'relayOffline'",
     [(UPCALL_OLD, UPCALL_FLAT)],
     "il ne dit PAS que le relais est hors ligne"),
    ("B", "read error_kind and then ignore it - a rate limit renders the generic line",
     [(METACHOICE_OLD, METACHOICE_FLAT)],
     "il rend la phrase dediee"),
    ("C", "claim a rate limit for ANY upstream error",
     [(RATE_OVERREACH_OLD, RATE_OVERREACH_NEW)],
     'pas de faux "limite atteinte"'),
    ("D", "put the relay's raw message in the panel instead of the tooltip",
     [(TITLE_OLD, TITLE_LEAK)],
     "infobulle"),
]

# Distinguish genuine product reds from harness failures (points 44 / 57).
def is_harness_failure(out: str) -> bool:
    return ("ModuleNotFoundError" in out
            or "Failed to import test module" in out
            or "SyntaxError" in out
            or "renderUpdateCard introuvable" in out)


def main() -> int:
    original = TARGET.read_bytes()
    pristine = ROOT / "scripts" / "artifacts_pristine" / "popup.js"
    pristine.parent.mkdir(parents=True, exist_ok=True)
    pristine.write_bytes(original)  # snapshot EVERY run (point 45)

    proc = subprocess.run(SUITE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=ROOT)
    out = proc.stdout or proc.stderr or ""
    if is_harness_failure(out):
        print("HARNESS  la suite n'a pas demarre :")
        for line in out.splitlines()[:12]:
            print("   ", line[:170])
        return 1
    if proc.returncode != 0:
        print("FAIL etat reel : la suite doit etre verte avant de saboter")
        for line in out.splitlines()[-12:]:
            print("   ", line[:170])
        return 1
    print("ok   etat reel :", out.strip().splitlines()[-1])

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
            TARGET.write_bytes(data)
            proc = subprocess.run(SUITE, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", cwd=ROOT)
            out = proc.stdout or proc.stderr or ""
            if is_harness_failure(out):
                print(f"{tag:<4} HARNESS    {motive}")
                invalid += 1
                continue
            lines = [ln for ln in out.splitlines() if ln.startswith("FAIL")]
            hit = [ln for ln in lines if expect in ln]
            if proc.returncode != 0 and hit:
                named += 1
                status = "ROUGE NOMME"
            elif proc.returncode != 0 and lines:
                unnamed += 1
                status = "ROUGE NON NOMME"
            else:
                invalid += 1
                status = f"INVALIDE (exit {proc.returncode})"
            print(f"{tag:<4} {status:<16} {motive}")
            for line in (hit or lines)[:3]:
                print("      ", line[:170])
    finally:
        TARGET.write_bytes(original)
        restored = TARGET.read_bytes() == original

    proc = subprocess.run(SUITE, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=ROOT)
    clean = proc.returncode == 0
    print()
    print("etat reel apres restauration :", "vert" if clean else "ROUGE")
    print("popup.js restaure a l'octet   :", restored)
    # Tally line is a CONTRACT with scripts/acceptance.py (point 58).
    print("\n%d/%d rouges nommes, %d sans nom, %d invalides, %d morts"
          % (named, len(SABOTAGES), unnamed, invalid, dead))
    if not restored:
        print("FAIL popup.js n'a pas ete restaure a l'octet")
    ok = named == len(SABOTAGES) and invalid == 0 and dead == 0 and clean and restored
    print("RESULT:", "OK" if ok else "ECHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())