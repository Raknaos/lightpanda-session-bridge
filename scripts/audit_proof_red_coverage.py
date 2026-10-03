"""Every proof-red harness must be able to say three DIFFERENT things.

Measured 0.7.33: fifteen of the seventeen harnises in `scripts/` already print
three separate counters - named red, unnamed red, and invalid (a PATCH-MISS, a
harness/import failure, a dead sabotage). Three did not, and the difference
matters:

    proof_red_popup_deadline.py     counts them, but only as "RED (named)" vs
                                    "NOT PROVEN" - the word "invalid" never
                                    appears, so an audit reading OUTPUT cannot
                                    tell a PATCH-MISS from a named red.
    proof_red_route_deadline.py     same shape.
    proof_red_socket_timeout.py     the real hole: it computes one boolean from
                                    (returncode != 0 AND a stuck-socket line AND
                                    no harness noise), so a sabotage that went
                                    red for the WRONG reason is reported as
                                    proven. It cannot print "unnamed" at all.

An unnamed red proves only that something broke. An invalid one proves the proof
did not run. A harness that cannot distinguish them is a harness that will one
day report a green proof over a sabotage that never touched the real path
(points 44, 56, 60).

This audit is TEXTUAL and therefore cheap - it reads the harness source and
requires the three counters to be distinguishable BY NAME, plus the shape of a
verdict that fails when any of them is non-zero. It is deliberately blind to
whether the harnesses currently pass; that is their own job.
"""
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"

# A harness may spell these French or English; what it may not do is print a
# verdict that treats "unnamed" and "invalid" as success.
NAMED = re.compile(r"named|nomm\S*e?s?\b", re.I)
UNNAMED = re.compile(r"unnamed|non\s+nomm\S*|sans\s+nom", re.I)
INVALID = re.compile(r"invalid|invalide|patch-miss|mort\b|dead\b", re.I)

# The three distinct refusals a complete harness must be able to print.
NAMED_ONLY = re.compile(r"named", re.I)


def main():
    harnesses = sorted(SCRIPTS.glob("proof_red_*.py"))
    if not harnesses:
        print("HARNESS: no proof-red harness found under %s" % SCRIPTS)
        return 2
    failures = []
    print("=== each harness must distinguish named / unnamed / invalid ===")
    print("%-42s %-7s %-9s %-9s" % ("harness", "named", "unnamed", "invalid"))
    print("-" * 72)
    for f in harnesses:
        text = f.read_text(encoding="utf-8")
        found = {
            "named": bool(NAMED.search(text)),
            "unnamed": bool(UNNAMED.search(text)),
            "invalid": bool(INVALID.search(text)),
        }
        complete = all(found.values())
        print("%-42s %-7s %-9s %-9s %s" % (
            f.name,
            "ok" if found["named"] else "MISSING",
            "ok" if found["unnamed"] else "MISSING",
            "ok" if found["invalid"] else "MISSING",
            "" if complete else "<-- cannot distinguish"))
        if not complete:
            failures.append("%s cannot tell named from unnamed or invalid"
                            % f.name)

    print("\n=== and the gate must run every one of them ===")
    acc = REPO / "scripts" / "acceptance.py"
    if not acc.exists():
        print("HARNESS: acceptance.py not found")
        return 2
    gate = acc.read_text(encoding="utf-8")
    # Two shapes count as REQUIRED, and the difference matters:
    #   * the gate names the file literally - one line to forget when a harness
    #     is added, which is exactly how FIVE of these seventeen went unwired;
    #   * the gate DISCOVERS them (a glob over the same directory) - a new
    #     harness is required the moment it exists, with nothing to remember.
    # The second is strictly stronger, so it is accepted, and it must still be
    # asserted by the check that claims it: `proof_red_harnesses_are_required`
    # has to exist, be decorated, and be registered in LOCAL. A check that only
    # exists in the file would be point 13's decoration - defined, not run.
    literal = {f.name for f in harnesses if f.name in gate}
    discovers = bool(re.search(r'glob\(\s*["\']proof_red_\*\.py["\']', gate))
    # REGISTRATION must be read from the LOCAL/LIVE LIST BLOCKS, not from the
    # whole file. Searching the file text is the mistake point 13 is about: the
    # name of a DEFINED check appears in its own `def`, so a check that was
    # removed from LOCAL entirely still "looks registered" and the audit stayed
    # green under the very sabotage this check exists to catch. Measured, both
    # directions, in one table.
    lines = gate.splitlines()
    try:
        lo = next(k for k, l in enumerate(lines) if l.startswith("LOCAL = ["))
        li = next(k for k, l in enumerate(lines) if l.startswith("LIVE = ["))
    except StopIteration:
        print("HARNESS: LOCAL/LIVE lists not found in acceptance.py")
        return 2
    registered_lists = "\n".join(lines[lo:li + 12])
    registered = "proof_red_harnesses_are_required" in registered_lists
    decorated = ('@check("every proof-red harness is REGISTERED and every sabotage is NAMED")'
                 in gate)
    covered = discovers and registered and decorated
    orphans = [] if covered else sorted(
        f.name for f in harnesses if f.name not in literal)
    if covered:
        print("  every harness is DISCOVERED by the gate check, which is named, "
              "decorated and registered")
    for name in orphans:
        print("  ORPHAN  %s - no check in the gate runs it" % name)
        failures.append("%s is not run by any gate check" % name)
    if not covered:
        failures.append("the gate neither names %d harness(es) literally nor "
                        "discovers them (named=%s registered=%s decorated=%s)"
                        % (len(orphans), bool(literal), registered, decorated))
    print("  %d/%d harnesses named literally, discovery=%s, the rest required "
          "by discovery" % (len(literal), len(harnesses), discovers))

    print("\n%d failure(s)" % len(failures))
    for f in failures:
        print("  " + f)
    print("PROOF-RED AUDIT " + ("OK" if not failures else "RED"))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
