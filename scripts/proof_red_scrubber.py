"""Proof-red for the scrubber's alphabet rule.

Three sabotages, each targeting the code under test's REAL path (point 24), each
restored by bytes (point 31), each required to be NAMED - an unnamed red proves
only that something broke.

  S1  put BOTH alphabet arms back under one conjunction (`all(classes)`),
      which is what the code did before 0.7.32. Must red on a value with TWO
      alphabet classes and 19 characters - the shape the conjunction misses and
      the 2-class floor catches.
  S2  delete the `_CREDENTIAL_PREFIXES` short-circuit. Must red on every
      prefixed shape, proving the prefix list is load-bearing rather than
      decorative (point 72: a guard that can be removed without the proof
      noticing is not proven).
  S3  revert the SENTENCE rule to a blind keep. Must red on a credential hiding
      inside a note - the 0.7.20 defect, reintroduced by the "a value with a
      space is a sentence, keep it" shortcut.

Exits non-zero unless every sabotage was red AND named.
"""
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TARGET = ROOT / "relay" / "diagnostics.py"
SUITE = ROOT / "scripts" / "test_scrubber_shapes.py"
PRISTINE = ROOT / "scripts" / "artifacts_pristine" / "diagnostics.py.pristine"

SABOTAGES = [
    # S1 was a DECOY on the first attempt: reverting only the 3-class branch to a
    # conjunction left the 2-class floor in place, and every fixture happened to
    # be caught by THAT one instead - so the suite stayed green and the proof
    # correctly reported UNNAMED. Read why before believing a red (point 24).
    # The honest sabotage puts BOTH alphabet arms back under one conjunction.
    ("S1 the alphabet test is a conjunction again",
     '    if sum(classes) == 3 and len(text) >= _MIN_THREE_CLASSES:\n'
     '        return True\n'
     '    if sum(classes) == 2 and len(text) >= _MIN_TWO_CLASSES:\n'
     '        return True',
     '    if all(classes) and len(text) >= _MIN_THREE_CLASSES:\n'
     '        return True\n'
     '    if all(classes) and len(text) >= _MIN_TWO_CLASSES:\n'
     '        return True',
     "LEAKED a alphabet only, 2 classes, 19 chars credential"),
    ("S2 the credential-prefix short-circuit is gone",
     '    if text.startswith(_CREDENTIAL_PREFIXES):\n        return True',
     '    if False:\n        return True',
     "LEAKED a a GitHub PAT, lowercase body credential"),
    # S3 was ALSO a decoy on the first attempt: it reverted the sentence rule
    # inside `_looks_sensitive_blob`, but `scrub()` short-circuits on
    # `" " in value` BEFORE calling that function, so the sabotaged line was no
    # longer on the path the suite exercises. Green suite, correct product,
    # useless proof - point 37 in its purest form: the sabotage must touch the
    # branch a caller actually reaches. This one breaks the mask inside
    # `scrub_text`, which is the code that decides the verdict for a sentence.
    ("S3 a sentence keeps its credential words",
     '        if stripped and _looks_sensitive_blob(stripped):\n'
     '            out.append(REDACTED)',
     '        if False and _looks_sensitive_blob(stripped):\n'
     '            out.append(REDACTED)',
     "LEAKED a credential inside a sentence"),
]


def run_suite():
    proc = subprocess.run([sys.executable, str(SUITE)], cwd=str(ROOT),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")
    return proc.stdout or "", proc.stderr or "", proc.returncode


def main():
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    PRISTINE.parent.mkdir(parents=True, exist_ok=True)
    # Snapshot taken AT SABOTAGE TIME, every run (point 45).
    pristine = TARGET.read_bytes()
    PRISTINE.write_bytes(pristine)

    named, unnamed, invalid = 0, 0, 0
    try:
        base_out, _, base_rc = run_suite()
        if base_rc != 0:
            print("HARNESS: the suite is red on the UNMODIFIED file")
            print(base_out)
            return 2
        print("baseline: green on the unmodified file\n")

        for name, old, new, expect in SABOTAGES:
            text = pristine.decode("utf-8")
            if old not in text:
                print("INVALID  %s\n         PATCH-MISS: the anchor is gone" % name)
                invalid += 1
                continue
            TARGET.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
            out, err, rc = run_suite()
            if rc == 0:
                print("UNNAMED  %s\n         the suite stayed GREEN - the sabotage "
                      "missed the real path" % name)
                unnamed += 1
            elif expect in out:
                print("RED      %s\n         %s" % (name, expect))
                named += 1
            else:
                print("INVALID  %s\n         red, but not on the expected defect "
                      "(%r)\n%s" % (name, expect, out[-600:]))
                invalid += 1
    finally:
        # Byte-exact restore (point 31) - never git checkout.
        TARGET.write_bytes(pristine)

    # Idempotence: the restore is proven, not assumed.
    restored = TARGET.read_bytes()
    if restored != pristine:
        print("INVALID  the file was NOT restored byte for byte")
        invalid += 1
    else:
        out, _, rc = run_suite()
        print("\nrestore: %d bytes, suite %s" % (
            len(restored), "green" if rc == 0 else "RED"))
        if rc != 0:
            invalid += 1

    print("\n%d named red, %d unnamed, %d invalid" % (named, unnamed, invalid))
    ok = named == len(SABOTAGES) and unnamed == 0 and invalid == 0
    print("PROOF-RED " + ("OK" if ok else "REFUSE"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
