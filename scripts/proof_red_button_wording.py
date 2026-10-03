"""Proof-red for the update button's own wording (0.7.28).

The defect: `renderUpdateCard` wrote `updateBtn.textContent` ONLY in the
`update_available` branch, so the three other exits left the button holding the
version a previous render offered. A branch update has its own wording - it
names no version at all - and inherited the release wording when it arrived
second, on the SAME node the user clicks.

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
TEST = ROOT / "tests" / "node" / "test_button_wording_truth.js"

# Snapshot taken at sabotage time, EVERY run: a once-only snapshot silently
# reverts the fix the moment the product legitimately changes (point 45).
PRISTINE = ROOT / "scripts" / "artifacts_pristine" / "popup.js.pristine"
PRISTINE.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(POPUP, PRISTINE)
ORIGINAL = PRISTINE.read_bytes()

# (label, anchor, replacement, expected substring unittest/js prints on red)
SABOTAGES = [
    (
        "the button wording seed is gone, so the next state inherits a version",
        "  updateBtn.textContent = '';\n",
        "",
        # Copied from the line the runner PRINTS, which is the NEGATIVE
        # assertion - the run reports `FAIL a dead relay KEEPS the version`, so
        # an expectation saying "does not keep" never matches (point 70).
        "a dead relay keeps the version the button used to offer",
    ),
    (
        "the dead-relay branch keeps the wording it inherited",
        # A literal, never a name the sandbox does not define (point 32).
        "    updateBtn.style.display = 'none';\n    rollbackBtn.style.display = 'none';\n",
        "    updateBtn.style.display = 'none';\n"
        "    updateBtn.textContent = 'Installer v0.7.28';\n"
        "    rollbackBtn.style.display = 'none';\n",
        "a dead relay keeps the version the button used to offer",
    ),
    (
        "the install branch returns before the state can own its wording",
        "    updateChip.textContent = '\u2026';\n    updateMeta.textContent = '';\n",
        "    updateChip.textContent = '\u2026';\n    updateMeta.textContent = '';\n"
        "    updateBtn.textContent = 'updateBtn(0.7.28)';\n",
        "offered version stays on the button through the install",
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
