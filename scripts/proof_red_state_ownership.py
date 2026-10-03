"""Proof-red for `test_no_value_outlives_its_state.js` (0.7.31).

The audit's whole claim is that it can FIND a surviving value, so it has to be
made to find one. Five sabotages, each reverting a real fix:

  1. `updateMeta.title` seed (0.7.27)  -> the tooltip survives an install
  2. `updateBtn.textContent` seed (0.7.28) -> the wording survives a branch update
  3. `resetClearButton()` call removed from the EMPTY branch (0.7.29) -> the
     armed confirmation survives a refresh that empties the list
  4. `renderUpdateCard()` before `await loadBridgeToken()` (0.7.30) -> the first
     frame again shows `popup.html`'s placeholder
  5. the DECLARED exemption is widened -> the escape hatch starts hiding a real
     defect, which is the failure mode of the guard itself (point 72)

Rules this harness obeys (points 32/44/56/60):
  - 0.7.30's first-frame fix is NOT in this file, and its absence is stated:
    `renderUpdateCard` writes `updateVersion` in EVERY state, so the markup's
    placeholder cannot survive inside it - the first frame belongs to `init()`,
    covered by tests/node/test_card_identity_immediate.js. A sabotage here that
    edits `popup.html` is a GREEN run (measured), i.e. a dead proof.
  - the target line is READ from the file before it is quoted
  - a pattern that no longer matches is INVALID, never a red
  - restore is BYTES, taken at sabotage time, and verified afterwards
"""
import hashlib
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "tests" / "node" / "test_no_value_outlives_its_state.js"
POPUP = ROOT / "extension" / "popup.js"
HTML = ROOT / "extension" / "popup.html"
HARNESS = ROOT / "scripts" / "artifacts_pristine"

SABOTAGES = [
    # 1. the tooltip seed of 0.7.27 - the busy branch returns at line 28, and
    #    line 13 is the ONLY thing that claims the tooltip before it
    ("the update card's tooltip survives the install",
     POPUP, "  updateMeta.title = '';\n", "",
     "updateMeta.title"),

    # 2. the wording seed of 0.7.28 - `update_available` is the only exit that
    #    writes it, so without the seed the version a previous render offered
    #    stays on a button the branch hides
    ("the button's wording survives a branch update",
     POPUP, "  updateBtn.textContent = '';\n", "",
     "updateBtn.textContent"),

    # 3. the shared owner of 0.7.29 - dropping it from the EMPTY branch is what
    #    let an armed confirmation survive a refresh (popup.js:1171)
    ("the armed clear button survives an emptying refresh",
     POPUP, "    resetClearButton();\n    return;", "    return;",
     "clearText"),

    # 4. the escape hatch itself. `a jour` does NOT keep `updateMeta`: line 112
    #    writes its title in every exit of the healthy path. `relay muet` does not
    #    either - it `return`s at line 52, after the line-13 seed. So the state
    #    whose declaration is widened must be one where the survival is REAL.
    #    Measured above: `a jour` -> `installation en cours` keeps nothing on
    #    `updateMeta`, so the honest widened declaration is on `relay muet` for a
    #    node that DOES survive there. `rollbackBtn` is already declared there, so
    #    widening to `updateMeta` would be caught by the overreach guard only if
    #    `updateMeta` survived - it does not. The honest sabotage therefore
    #    REMOVES a node from a declaration that the measurement proves it needs,
    #    which must turn the same pair red.
    ("the declared exemption drops a survival it must keep",
     SUITE, "'relay muet': new Set(['rollbackBtn']),",
     "'relay muet': new Set([]),",
     "rollbackBtn.title"),
]



def restore_all(saved):
    for path, data in saved.items():
        path.write_bytes(data)


def main():
    saved = {}
    for path in {t[1] for t in SABOTAGES} | {SUITE}:
        saved[path] = path.read_bytes()
    before = {p: hashlib.sha256(d).hexdigest() for p, d in saved.items()}

    named = unnamed = invalid = 0
    try:
        for title, path, old, new, expect in SABOTAGES:
            text = path.read_text(encoding="utf-8")
            n = text.count(old)
            if n != 1:
                print("  INVALID  %s : motif present %d fois (1 attendu)" % (title, n))
                invalid += 1
                continue
            path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

            r = subprocess.run(
                ["node", str(SUITE), str(ROOT)],
                cwd=str(ROOT), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=300)
            out = r.stdout + r.stderr
            if "SyntaxError" in out or "TypeError" in out or "ReferenceError" in out:
                print("  INVALID  %s : le harnais a casse" % title)
                print("           " + out.strip().splitlines()[0][:150])
                invalid += 1
                restore_all(saved)
                continue
            if r.returncode == 0:
                print("  (mort)   %s : suite VERTE, la preuve ne prouve rien" % title)
                invalid += 1
                restore_all(saved)
                continue
            hits = [l for l in out.splitlines() if expect in l]
            if hits:
                named += 1
                print("  ROUGE    %s" % title)
                print("           " + hits[0].strip()[:160])
            else:
                unnamed += 1
                print("  ROUGE NON NOMME  %s" % title)
                print("           " + next((l for l in out.splitlines()
                                        if l.startswith("FAIL")), "")[:160])
            restore_all(saved)
    finally:
        restore_all(saved)

    after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in saved}
    intact = after == before
    print("\n%d nomme(s) rouge, %d non nomme(s), %d invalide | restauré a l'octet : %s"
          % (named, unnamed, invalid, intact))
    if not intact:
        for p in saved:
            if before[p] != after[p]:
                print("   RESTORE MANQUANT : " + str(p))
    ok = named == len(SABOTAGES) and unnamed == 0 and invalid == 0 and intact
    print("PROOF-RED " + ("OK" if ok else "REFUSE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())