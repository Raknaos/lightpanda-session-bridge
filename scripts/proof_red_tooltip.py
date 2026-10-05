"""Proof-red for the update card's tooltip ownership (0.7.27).

The defect: `renderUpdateCard` wrote `updateMeta.title` in two of its three
exits, so a node kept whatever the previous render gave it. The relay's own
words survived a state change and the whole install.

Each sabotage below must go RED AND NAMED - a sabotage that misses the real path
reports green (points 24/56/60), and a `PATCH-MISS` is a hole in this harness,
not a red (point 44).
"""
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POPUP = ROOT / "extension" / "popup.js"
TEST = ROOT / "tests" / "node" / "test_tooltip_state_truth.js"

# Snapshot taken at sabotage time, EVERY run: a once-only snapshot silently
# reverts the fix the moment the product legitimately changes (point 45).
#
# The unconditional refresh is ALSO the hole `acceptance.py`'s
# "no stored 'pristine' copy can become a false reference" check exists to
# catch, and on 2026-10-05 it caught one for real: a killed
# proof_red_socket_timeout run left `timeout = 45` in relay/server.py, a later
# run refreshed `artifacts_pristine/relay__server.py` FROM that sabotage, and
# from then on every restore-verification compared against a false base. An
# unbounded refresh is only safe because that check runs FIRST and refuses the
# run; do not "optimise" the copy into a guarded or once-only one here without
# re-measuring that ordering (points 45, 101).
PRISTINE = ROOT / "scripts" / "artifacts_pristine" / "popup.js.pristine"
PRISTINE.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(POPUP, PRISTINE)
ORIGINAL = PRISTINE.read_bytes()

# (label, anchor, replacement, expected substring unittest/js prints on red)
SABOTAGES = [
    (
        "the tooltip seed is gone, so a state that does not own it inherits it",
        "  updateMeta.title = '';\n",
        "",
        # Copied from the line the runner PRINTS, not from a paraphrase of what
        # it should print (point 70).
        "a waiting update does not inherit the upstream tooltip",
    ),
    (
        "the install branch returns before the state can own its title",
        # The relay's own words, spelled as a literal: a name that does not
        # exist in the sandbox would raise ReferenceError, which is a harness
        # failure dressed as a red (point 32).
        "    updateChip.textContent = '…';\n    updateMeta.textContent = '';\n",
        "    updateChip.textContent = '…';\n    updateMeta.textContent = '';\n"
        "    updateMeta.title = 'API rate limit exceeded for 203.0.113.9';\n",
        "install in progress clears the tooltip",
    ),
]


def run_test():
    proc = subprocess.run(
        ["node", str(TEST), str(ROOT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


named = 0
invalid = 0
lines = []

try:
    for label, anchor, replacement, expect in SABOTAGES:
        text = ORIGINAL.decode("utf-8")
        if anchor not in text:
            lines.append(("INVALID", label, "PATCH-MISS: the anchor is not in the file"))
            invalid += 1
            continue
        sabotaged = text.replace(anchor, replacement, 1)
        if sabotaged == text:
            # `str.replace` on an absent pattern is a DEAD sabotage that reports
            # green (point 60) - so prove the file really changed.
            lines.append(("INVALID", label, "DEAD SABOTAGE: the file is unchanged"))
            invalid += 1
            continue
        POPUP.write_bytes(sabotaged.encode("utf-8"))

        rc, out = run_test()
        tail = out.strip().splitlines()[-1:] or ["no output"]
        if rc != 0 and expect in out:
            named += 1
            lines.append(("RED", label, expect))
        elif rc == 0:
            lines.append(("INVALID", label, "GREEN - the sabotage missed the real path: %s" % tail[0]))
            invalid += 1
        else:
            lines.append(("INVALID", label, "red but UNNAMED (expected %r): %s" % (expect, tail[0])))
            invalid += 1
finally:
    POPUP.write_bytes(ORIGINAL)

# The restore is the other half of the proof: the file must be back to its bytes.
restored = POPUP.read_bytes() == ORIGINAL
rc, out = run_test()

print("=" * 72)
for kind, label, detail in lines:
    print("%-8s %-62s %s" % (kind, label[:62], detail))
print("=" * 72)
print("%d/%d named red, %d invalid" % (named, len(SABOTAGES), invalid))
print("popup.js restored byte for byte:", restored)
print("suite after restore:", out.strip().splitlines()[-1] if out.strip() else "no output")
print("node exit after restore:", rc)

# The meta-rule: every sabotage red AND named, the file restored, the suite green.
ok = named == len(SABOTAGES) and invalid == 0 and restored and rc == 0
print("\n%s" % ("PREUVE VERTE" if ok else "PREUVE INVALIDE"))
sys.exit(0 if ok else 1)
