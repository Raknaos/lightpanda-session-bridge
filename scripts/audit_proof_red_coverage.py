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

This audit used to read the harness source as TEXT, and it claimed to check "the
shape of a verdict that fails when any of them is non-zero". MEASURED 2026-10-05,
both halves of that were false and both were caught by making the audit red:

    * a docstring alone was enough. A harness with NO counter at all - just a
      prose sentence quoting named/unnamed/invalid - was scored "ok ok ok",
      0 failure(s), PROOF-RED AUDIT OK. The words were found; the proof was not.
    * a lying harness was enough. One printing `named: 0, unnamed: 1, invalid: 1`
      and then `PROOF-RED OK` also scored "ok ok ok" - the words were present and
      the verdict treated them as success, which is precisely what this file
      says a harness "may not do".

So the words were never the thing being audited. Prose is not a counter, and a
word is not a verdict. This audit now parses each harness and looks for the three
words in EXECUTABLE CODE ONLY - docstrings and comments excluded - because
`ast.unparse` re-emits a docstring as a string constant and a check that audits
its own documentation teaches you to ignore it (the same trap
`every_fail_names_a_cause` documents at L1961-1993 of scripts/acceptance.py).

What this audit still deliberately does NOT do is run the harnesses; whether
they currently pass is their own job. It audits the SHAPE, not the verdict.
"""
import ast
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

# A counter is a VALUE, not a word. Measured, this is the difference between a
# harness that reports a count and one that only mentions the word: an honest
# counter interpolates a name into a format string, while the saboteur writes the
# words LITERALLY ("named: 0, unnamed: 1, invalid: 1") beside a verdict that
# treats them as success - exactly what this file header forbids. Looking for the
# words scored both as "ok ok ok".
#
# Regexes over the source were tried first and were WRONG twice: a form-string
# left of a `%` BinOp with its values in the right-hand tuple is the shape 17 of
# 19 harnesses actually use, and no regex for `%(named)s` matched them. So the
# test is structural, on the parse tree: a `print`/`.format` whose format literal
# carries the word AND which interpolates a variable. A word in a docstring is a
# `Constant` and can never reach it.
_PRINT = {"print", "format", "write", "writeln", "format_map"}
# The three refusals, each with the status tokens that make it DISTINGUISHABLE.
TAXONOMY = {
    "named": re.compile(r"named|NAMED|nomm", re.I),
    "unnamed": re.compile(r"unnamed|UNNAMED|non\s*_?nomm", re.I),
    "invalid": re.compile(r"invalid|INVALID|invalide|PATCH-MISS|DEAD|MORT", re.I),
}


def _unpack_format(arg):
    """-> (format_literal, interpolated_values) for any shape a counter takes.

    Three real shapes: `'%d/%d named red, %d invalid' % (a, b, c)` (17 harnesses),
    an f-string, and a bare literal. Only the first two interpolate, and only an
    interpolating one can be a counter.
    """
    if isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Mod):
        left, right = arg.left, arg.right
        if isinstance(left, ast.Constant) and isinstance(left.value, str):
            elts = right.elts if isinstance(right, ast.Tuple) else [right]
            return left.value, elts
    if isinstance(arg, ast.JoinedStr):
        literal = "".join(v.value for v in arg.values
                          if isinstance(v, ast.Constant) and isinstance(v.value, str))
        return literal, [v for v in arg.values if isinstance(v, ast.FormattedValue)]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value, []
    return None, []


def _interpolates_a_variable(values):
    return any(isinstance(v, (ast.Name, ast.Attribute, ast.Subscript, ast.Call))
               for v in values)


def counts(tree, word):
    """True when a printing call counts `word` as a VALUE it interpolated."""
    pattern = TAXONOMY[word]
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
        if func not in _PRINT:
            continue
        literal, values = _unpack_format(node.args[0])
        if literal is None or not _interpolates_a_variable(values):
            continue
        if pattern.search(literal):
            return True
    return False


def distinguishes(tree, word):
    """True when the word is a STATUS the harness can tell apart.

    Needed because a fold is legitimate: 7 harnesses classify an unnamed red and
    then fold it into `invalid`, which is the conservative direction (an anonymous
    red can never report green). Requiring a separate counter for every word went
    red on all 19 - measured - so the rule is a counter OR a distinguishing status.
    A status distinguishes only if it is COMPARED (`ast.Compare`/`ast.If`) or
    BUILT by a conditional (`ast.IfExp`, the shape at L193 of
    proof_red_session_expiry.py). Appearing in a list nobody reads is not enough.
    """
    pattern = TAXONOMY[word]
    statuses = [v.value for v in ast.walk(tree)
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
                and pattern.search(v.value)]
    if not statuses:
        return False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Compare, ast.If)) and pattern.search(ast.unparse(node)):
            return True
        if isinstance(node, ast.IfExp) and pattern.search(ast.unparse(node)):
            if any(pattern.search(ast.unparse(child)) for child in ast.walk(node)):
                return True
    return False


def harness_state(source):
    """-> (found_words, counted_words) for one harness.

    Takes the WHOLE source, not the output of `executable_code`: the structural
    tests walk the parse tree, and re-parsing the unparsed fragments a second time
    is both wasteful and wrong - `executable_code` emits statements one by one and
    the pieces do not re-parse as a module (a stray `-1:` raises SyntaxError, which
    crashed the audit and made every sabotage "RED" for the wrong reason).
    """
    tree = ast.parse(source)
    # `found` is read from the EXECUTABLE code, so a docstring that merely names a
    # refusal does not count as printing it; `counts`/`distinguishes` already only
    # see the tree. Both halves are needed: a saboteur that prints the words
    # literally is caught by `counted`, one that only writes prose by `found`.
    code = executable_code(source)
    found = {w: bool(p.search(code)) for w, p in TAXONOMY.items()}
    counted = {w: counts(tree, w) or distinguishes(tree, w) for w in TAXONOMY}
    return found, counted


# Node types that CONTAIN other nodes: unparsing one re-emits its whole body, so
# walking them would re-print every statement inside it. They are dropped, and
# so is every docstring, leaving only code that can actually run.
_CONTAINERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
               ast.Expr, ast.Return, ast.Assign, ast.AugAssign, ast.AnnAssign,
               ast.If, ast.For, ast.While, ast.With, ast.Try)
_DOCBEARERS = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def executable_code(source):
    """The harness source with every docstring removed.

    Comments never reach here (the parser drops them) but docstrings do: they are
    string constants, and a harness that merely NAMES the three refusals in its
    prose is not a harness that can print them. Returning only code is what makes
    the audit able to go red - measured, a prose-only harness and a lying harness
    both scored "ok ok ok" while this function existed nowhere.
    """
    tree = ast.parse(source)
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, _DOCBEARERS):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docs.add(doc)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, _CONTAINERS):
            continue
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and node.value in docs:
            continue
        out.append(ast.unparse(node))
    return "\n".join(out)


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
        try:
            executable_code(text)
        except SyntaxError as err:
            # A harness that cannot even parse cannot print anything. Scoring it
            # by its raw text would let a broken file pass on prose alone.
            print("%-42s %-7s %-9s %-9s %s" % (
                f.name, "MISSING", "MISSING", "MISSING",
                "<-- does not parse: %s" % err))
            failures.append("%s does not parse: %s" % (f.name, err))
            continue
        found, counted = harness_state(text)
        # The word alone is a comment; the COUNTER is the proof. A harness that
        # names a refusal without ever counting it or making it a status it can
        # tell apart is the saboteur measured above, so naming is necessary but
        # not sufficient.
        words_only = sorted(k for k in found if found[k] and not counted[k])
        complete = all(found.values()) and not words_only
        print("%-42s %-7s %-9s %-9s %s" % (
            f.name,
            "ok" if found["named"] else "MISSING",
            "ok" if found["unnamed"] else "MISSING",
            "ok" if found["invalid"] else "MISSING",
            "" if complete else "<-- cannot distinguish"))
        if not complete:
            missing = sorted(k for k, v in found.items() if not v)
            if missing:
                failures.append("%s names %s only in prose, not in code"
                                % (f.name, "/".join(missing)))
            else:
                failures.append(
                    "%s NAMES %s but never counts it - the words are literals "
                    "beside a verdict, which is the saboteur shape"
                    % (f.name, "/".join(words_only)))

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
