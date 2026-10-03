"""Proof-red for the update card's identity on the FIRST FRAME (0.7.30).

The defect: `init()` wrote the footer version synchronously but rendered the
update card only after `await loadBridgeToken()`, the bootstrap and the relay
probe. `/v1/update/check` answers in 864 ms on the running relay, so for that
whole window the card showed `v0.5.0` - the literal in `popup.html` - on an
extension installed at 0.7.29.

The version is LOCAL knowledge (`chrome.runtime.getManifest()`), so it never had
to wait for anything.

Each sabotage must go RED AND NAMED, and `popup.js` must be restored byte for
byte (points 24/44/56/60: a PATCH-MISS is a hole in this harness, not a red).
"""
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
POPUP = ROOT / "extension" / "popup.js"
TEST = ROOT / "tests" / "node" / "test_card_identity_immediate.js"

# Snapshot taken at sabotage time, EVERY run: a once-only snapshot silently
# reverts the fix the moment the product legitimately changes (point 45).
PRISTINE = ROOT / "scripts" / "artifacts_pristine" / "popup.js.pristine"
PRISTINE.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(POPUP, PRISTINE)
ORIGINAL = PRISTINE.read_bytes()

SABOTAGES = [
    (
        "the first render is gone, so the card waits for the whole chain of awaits",
        "  renderUpdateCard();\n  await loadBridgeToken();",
        "  await loadBridgeToken();",
        "on the first frame the card already names the installed version",
    ),
    (
        # My first second sabotage rewrote `appVersion`, the FOOTER version - a
        # different node the card never reads, so the suite stayed green and the
        # proof refused it. A sabotage must touch the path the defect is on
        # (point 32): the card's own identity comes from `getManifest()` INSIDE
        # renderUpdateCard, so that is what has to break.
        "the card reads the manifest's placeholder instead of the installed version",
        "  updateVersion.textContent = 'v' + deployed;",
        "  updateVersion.textContent = 'v0.5.0';",
        "on the first frame the card already names the installed version",
    ),
]


def run_test():
    proc = subprocess.run(
        ["node", str(TEST), str(ROOT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


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

restored = POPUP.read_bytes() == ORIGINAL
rc, out = run_test()

print("=" * 74)
for kind, label, detail in lines:
    print("%-8s %-58s %s" % (kind, label[:58], detail))
print("=" * 74)
print("%d/%d named red, %d invalid" % (named, len(SABOTAGES), invalid))
print("popup.js restored byte for byte:", restored)
print("suite after restore:", out.strip().splitlines()[-1] if out.strip() else "no output")
print("node exit after restore:", rc)

ok = named == len(SABOTAGES) and invalid == 0 and restored and rc == 0
print("\n%s" % ("PREUVE VERTE" if ok else "PREUVE INVALIDE"))
sys.exit(0 if ok else 1)
