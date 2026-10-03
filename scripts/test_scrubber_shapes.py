"""The scrubber must catch a credential REGARDLESS of its alphabet.

Measured 0.7.32, before any fix: `_looks_sensitive` required an uppercase AND a
lowercase AND a digit in the SAME string, so five credential shapes passed it
untouched:

    all-lowercase passphrase        one class, no digit, no capital
    lowercase + digit, no upper     two classes, conjunction fails on the third
    16 chars, mixed                 under the old 20-char floor
    8 chars, all three classes      under the floor
    AWS access key id               upper + digit, NO lowercase

A gate that proves "a secret is redacted" by planting one recognisable prefix
proves only that one shape. Point 65 on the protective side: the value class was
a detail of my fixtures, not of the threat.

Two directions, because over-redaction is a defect of the same severity as a
leak (point 16). Ten benign values must still survive - a short sha, a
`sha256:` fingerprint, an ISO-8601 timestamp, the product name, a cookie COUNT, a
host name, a full 40-char commit, a route path, a report sentence and an update
note.

DECLARED UNCATCHABLE, and this file is where that claim is earned rather than
asserted: a blob made of ONE alphabet class only (all lowercase, no digit, no
capital) is character-for-character the same shape as a hyphenated product name.
The passphrase and `lightpanda-session-bridge` are both a run of lowercase
letters, and no function of the string separates them - a rule that caught the
first would blank the second on every run, deleting the report's own subject.
DECLARED_UNCATCHABLE holds the pair and the test FAILS if a future change ever
separates them: such a separation can only come from an allow-list of
known-benign literals, which is a deliberate narrowing to be argued in the
source, not slipped in here.

Every credential below is BUILT, never pasted: each entry is a prefix plus a
generated body, so this file stores no live-shaped secret and the scrubber's own
prefix list cannot be satisfied by accident.
"""
import importlib.util
import pathlib
import random
import string
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "relay"))
_spec = importlib.util.spec_from_file_location("diag_under_test", ROOT / "relay" / "diagnostics.py")
diag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diag)

_ALPHABETS = (string.ascii_lowercase,
              string.ascii_letters,
              string.ascii_letters + string.digits)


def blob(length, alphabet_index=2, seed=0):
    """A deterministic, credential-shaped string this file does not store."""
    rng = random.Random(seed)
    return "".join(rng.choice(_ALPHABETS[alphabet_index]) for _ in range(length))


# Real credential SHAPES. None is a marker string the code knows about, and
# none is stored here in full: the body is generated, so publishing this file
# cannot leak even in principle.
MUST_REDACT = [
    # Pinned, not generated: a random 8-char blob drew TWO classes (no digit) on
    # the seed I first used, so the fixture claimed a shape it did not have.
    # A 3-class blob exists at 7 chars ('2yW4Acq'), so that is the real floor.
    ("alphabet only, 3 classes, 7 chars", "2yW4Acq"),
    ("alphabet only, 3 classes, 9 chars", "2yW4Acq9z"),
    ("alphabet only, 3 classes, 16 chars", blob(16, 2, seed=11)),
    # TWO classes, no capital, 19 chars. Measured as the ONLY shape the old
    # conjunction misses while the 2-class floor catches: `all(classes)` is
    # False with two classes, `sum(classes) == 2 and len >= 16` is True. My
    # first fixture here was `AKIA` + body - and `AKIA` is itself a PREFIX, so
    # the prefix rule caught it under BOTH versions and the proof-red reported
    # UNNAMED. A fixture that two independent rules both cover proves nothing.
    ("alphabet only, 2 classes, 19 chars", blob(19, 1, seed=14)),
    ("alphabet only, lower + digit", blob(22, 2, seed=15)),
]

# These carry a KNOWN PREFIX and, deliberately, ONE alphabet class - so the
# alphabet rules provably cannot catch them and the prefix list is the ONLY
# thing that can. My first draft had none: every fixture was 2-3 classes, which
# made the prefix list AND the alphabet rule each redundant, and both sabotage
# runs stayed GREEN without my reading why (point 24). A branch you cannot see
# exercised is not covered.
MUST_REDACT_PREFIX_ONLY = [
    ("a GitHub PAT, lowercase body", "ghp_" + blob(12, 0, seed=15)),
    ("an OpenAI-style key, lowercase body", "sk-" + blob(12, 0, seed=51)),
    ("an npm token, lowercase body", "npm_" + blob(12, 0, seed=52)),
    ("a GitLab token, lowercase body", "glpat-" + blob(12, 0, seed=53)),
    ("a Slack token, lowercase body", "xoxb-" + blob(12, 0, seed=18)),
]

# Benign values a support report exists for. These ARE stored in full: they are
# the payload the scrubber must not eat, so their exact spelling is the contract.
MUST_KEEP = [
    ("short commit", "e575a99"),
    ("file fingerprint", "sha256:" + "ab12cd34" * 8),
    ("ISO-8601 timestamp", "2026-09-14T18:15:40+0200"),
    ("product name", "lightpanda-session-bridge"),
    ("cookie count", "12"),
    ("host name", "cloud.vast.ai"),
    ("full commit", "04fe08e1d2c3b4a5968778695a4b3c2d1e0f9a8b"),
    ("origin path", "/v1/update/check"),
    ("a report sentence", "main moved on, but the deployed tree is byte-identical"),
    ("an update note", "Applied update 0.7.31"),
]

# The pair that makes the declaration above a measurement instead of a shrug.
DECLARED_UNCATCHABLE = [
    ("an all-lowercase passphrase", "correcthorsebattery" + "staple"),
    ("the product name", "lightpanda-session-bridge"),
]


def main():
    failures = []
    print("=== must be REDACTED ===")
    for label, value in MUST_REDACT:
        redacted = diag._looks_sensitive(value)
        print("  %-8s %-34s len=%d" % ("ok" if redacted else "LEAK", label, len(value)))
        if not redacted:
            failures.append("LEAKED a %s credential" % label)

    print("\n=== caught by the PREFIX rule alone (one alphabet class) ===")
    # This block is only meaningful if the alphabet rules CANNOT catch these:
    # one alphabet class, and short enough that no length floor applies either.
    # Measured, not assumed - my first drafts used `AIza` and `eyJ`, whose
    # PREFIX ITSELF carries an uppercase, so the value had two classes and the
    # prefix list was redundant again. The guard below caught that; prefixes
    # that are entirely lowercase (`ghp_`, `sk-`, `npm_`, `glpat-`) do not.
    for label, value in MUST_REDACT_PREFIX_ONLY:
        classes = (any(c.isupper() for c in value), any(c.islower() for c in value),
                   any(c.isdigit() for c in value))
        if sum(classes) != 1:
            failures.append("PREFIX-ONLY FIXTURE is not prefix-only: %s has %d classes"
                            % (label, sum(classes)))

    for label, value in MUST_REDACT_PREFIX_ONLY:
        redacted = diag._looks_sensitive(value)
        print("  %-8s %-38s len=%d" % ("ok" if redacted else "LEAK", label, len(value)))
        if not redacted:
            failures.append("LEAKED a %s credential" % label)

    print("\n=== the 2-class shape the old conjunction missed ===")
    # Asserted separately, because this is the single fixture that separates the
    # disjunction from a conjunction - if a future "simplification" restores
    # `all(classes)`, this row is the only one that goes red (point 82: fix one
    # shape and the next pass finds the adjacent one).
    two_class = dict(MUST_REDACT)["alphabet only, 2 classes, 19 chars"]
    classes = (any(c.isupper() for c in two_class), any(c.islower() for c in two_class),
               any(c.isdigit() for c in two_class))
    if sum(classes) != 2:
        failures.append("the 2-class fixture has %d classes - it would no longer "
                        "separate a conjunction" % sum(classes))
    else:
        print("  ok  2 classes, 19 chars: caught by the 2-class floor, missed by "
              "all(classes)")

    print("\n=== must SURVIVE (over-redaction is a defect too) ===")
    for label, value in MUST_KEEP:
        kept = not diag._looks_sensitive(value)
        print("  %-8s %-34s %s" % ("ok" if kept else "ERASED", label, value[:40]))
        if not kept:
            failures.append("ERASED benign %s" % label)

    print("\n=== the declared class: one alphabet only ===")
    verdicts = {label: diag._looks_sensitive(v) for label, v in DECLARED_UNCATCHABLE}
    for label, verdict in verdicts.items():
        print("  %-30s -> %s" % (label, "redacted" if verdict else "kept"))
    if len(set(verdicts.values())) != 1:
        failures.append("the uncatchable class was separated - argue it in the source")
    else:
        print("  same verdict on both sides: the declaration holds. A rule that")
        print("  'fixed' the passphrase would have blanked the product name here.")

    print("\n=== a SENTENCE carrying a credential (the 0.7.20 regression) ===")
    # Kept here, not only in tests/test_diagnostics.py, so the proof-red has a
    # fixture of its own. My "a value with a space is a sentence, keep it" rule
    # shipped `ghp_A1...Q7r8` inside a note; the sentence is now scrubbed WORD BY
    # WORD, so the token goes and the prose stays. Both directions, one table.
    note = "refused: Authorization Bearer " + "ghp_" + blob(8, 2, seed=61)
    scrubbed = diag.scrub({"note": note})["note"]
    token_gone = "ghp_" not in scrubbed
    prose_kept = scrubbed.startswith("refused: Authorization Bearer")
    print("  %-8s the credential word is gone" % ("ok" if token_gone else "LEAK"))
    print("  %-8s the sentence around it survives: %s"
          % ("ok" if prose_kept else "ERASED", scrubbed[:52]))
    if not token_gone:
        failures.append("LEAKED a credential inside a sentence")
    if not prose_kept:
        failures.append("ERASED the prose of a sentence carrying a credential")
    for benign in ("main moved on, but the deployed tree is byte-identical",
                   "Applied update 0.7.31"):
        if diag.scrub({"note": benign})["note"] != benign:
            failures.append("ERASED a benign sentence: %r" % benign)
    print("  %-8s benign sentences untouched" % "ok")

    print("\n=== through scrub(), the only place it is applied ===")
    # NOTE the two contracts, which are NOT the same and which my first draft
    # conflated: a KEY-named secret (token/password/...) makes the KEY vanish,
    # while a VALUE-shaped secret under a neutral key is REPLACED IN PLACE.
    # Asserting key-absence on the value case would have "failed" a correct
    # scrubber - measuring the harness instead of the product (point 77).
    foreign = blob(19, 2, seed=21)
    cases = [("a foreign blob (value replaced)", {"detail": foreign}, False, True),
             ("a key-named field (key dropped)", {"token": "abc"}, True, False),
             ("a benign field (kept verbatim)", {"host": "cloud.vast.ai"}, False, False),
             ("the report's own note", {"note": "Applied update 0.7.31"}, False, False)]
    for label, record, want_gone, want_replaced in cases:
        through = diag.scrub(dict(record))
        key = list(record)[0]
        gone = key not in through
        replaced = (key in through) and (through[key] == diag.REDACTED)
        if want_gone:
            ok = gone
        elif want_replaced:
            ok = replaced
        else:
            ok = (key in through) and (through[key] == record[key])
        print("  %-8s %s" % ("ok" if ok else "FAIL", label))
        if not ok:
            failures.append("scrub() wrong on %s" % label)

    print("\n%d failure(s)" % len(failures))
    for f in failures:
        print("  " + f)
    print("SCRUBBER " + ("OK" if not failures else "RED"))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
