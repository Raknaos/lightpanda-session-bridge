"""Proof-red: the gate's own wiring guard must go RED when the suite is unwired.

Measured 2026-10-04 while releasing 0.7.41. Two holes were PROVED in
`the_gate_cannot_contain_a_check_that_cannot_be_seen`, both by mutation:

  A. There was a floor for LIVE (`MIN_LIVE_CHECKS`) and NO floor for LOCAL, so
     deleting one entry from LOCAL shrank the local half of the suite from 38 to
     37 registered checks and the guard still answered `ok` with "53 checks".
     A gate that loses checks and reports green is the 0.7.40 defect one level
     down: the message reads like a measurement and there is nothing behind it.

  B. `unwired` EXCLUDED decorated functions (`decorators.get(n) != "check"`),
     while the guard's own docstring claims it catches checks "DEFINED but never
     REGISTERED". So a function wearing @check that no list ever calls could
     never influence the verdict, and the guard reported "nothing is neither" -
     the docstring promised a direction that had never been tested.

WHY A TEMP TREE. `scripts/acceptance.py` is the gate itself and it is NOT in
`scripts/artifacts_pristine/`. `product_survives_the_proof_red_harnesses` hashes
the fenced product files around the whole harness family, so a harness that
edited the gate in place could be killed half-way and leave the gate sabotaged.
Every mutation here happens on a throwaway COPY, imported with importlib so its
module-level `REPO = pathlib.Path(__file__).resolve().parent.parent` follows the
copy. The repo tree is never written to.

Each case FIRST proves its own mutation landed on disk. The first version of
this file did not, and it reported three reds over a sabotage that had never
touched the gate - a harness that cannot tell a dead proof from a live one is
the exact defect point 44 warns about.

Counters, deliberately distinguishable by NAME:
  named red   - the sabotage landed and the guard refused it for the right reason
  unnamed red - something broke, but not in the way this case intended
  invalid     - the mutation never landed; the proof did not run
  control     - the untouched tree must stay `ok`, so a guard that simply
                always-FAILs cannot pass this file
"""
import ast
import importlib.util
import pathlib
import re
import shutil
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
GATE = REPO / "scripts" / "acceptance.py"
GUARD = "the_gate_cannot_contain_a_check_that_cannot_be_seen"
# The two pristine floors do NOT live in GUARD; they sit in this other @check.
PRISTINE = "pristine_copies_match_the_committed_product"
REAL_PRISTINE = REPO / "scripts" / "artifacts_pristine"

# How each sabotage is expected to be refused. Matching on the refusal WORD is
# what makes a red "named": a guard that failed for an unrelated reason still
# returns FAIL, and that would be an unnamed red, not proof.
EXPECT = {
    "A_local_floor": r"MIN_LOCAL|LOCAL registers only|LOCAL is short",
    "B_decorated_never_registered": r"never registered|decorated but never",
    # Added 2026-10-04, same release as A and B. These floors were measured as
    # live code in the gate but NO harness ever made them go red, so a mutation
    # that removed them would have turned this file green while the gate kept
    # answering `ok` on a suite it no longer ran.
    "C_live_floor": r"MIN_LIVE|LIVE registers only|LIVE is short",
    "D_pristine_absent": r"no scripts/artifacts_pristine|stored baseline\(s\) are",
    "E_pristine_pruned": r"stored baseline\(s\) present|stored baselines",
    "F_emptiness": r"is empty, so none of its checks ran|an entire family of checks went unmeasured",
}


def load(text, tag, root=None):
    """Import a COPY of the gate so its REPO points at the temp tree.

    `root` is optional only for convenience; callers that seed a tree (the
    pristine baselines) MUST pass it, because otherwise this function creates a
    second, unseeded tree and the seed is silently invisible to the module."""
    root = pathlib.Path(root or tempfile.mkdtemp(prefix="prw_%s_" % tag))
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    tgt = root / "scripts" / "acceptance.py"
    tgt.write_text(text, encoding="utf-8")
    name = "prw_gate_%s" % tag
    spec = importlib.util.spec_from_file_location(name, tgt)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop(name, None)
    return root, mod


def run_guard(mod, fname=GUARD):
    """Call a DECORATED check, the way the gate's loop does, and read back the
    verdict `record()` actually appended. The wrapper returns a bool; RESULTS is
    the only place the (status, detail) pair exists.

    `fname` exists because the floors are NOT all in the same check: the LOCAL
    and LIVE floors live in the wiring guard, while both pristine floors live in
    `pristine_copies_match_the_committed_product`. One hardcoded name would have
    made three of the five cases unreachable."""
    mod.QUIET = True
    mod.RESULTS[:] = []
    try:
        guard = getattr(mod, fname, None)
        if guard is None:
            return "MISSING", "guard %s absent from the copy" % fname
        guard()
    except Exception as err:
        return "CRASH", "%s: %s" % (type(err).__name__, err)
    if not mod.RESULTS:
        return "CRASH", "the guard recorded no verdict at all"
    status, _name, detail = mod.RESULTS[-1]
    return status, detail


def span(text, tree, listname):
    """1-indexed (first_line, last_line) of a LOCAL/LIVE list literal, read out
    of the AST of THIS text - never guessed from a line number in a comment."""
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == listname
                and isinstance(node.value, ast.List)):
            return node.lineno, node.end_lineno
    raise AssertionError("no %s list literal in the gate copy" % listname)


def list_names(tree, listname):
    for node in tree.body:
        if (isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == listname
                and isinstance(node.value, ast.List)):
            return [e.id for e in node.value.elts if isinstance(e, ast.Name)]
    raise AssertionError("no %s list literal in the gate copy" % listname)


def const_value(text, name):
    """Read a module-level integer CONSTANT out of the gate text with ast, so the
    case below is driven by the floor the file actually declares instead of a
    number copied from a comment."""
    for node in ast.parse(text).body:
        if (isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == name
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, int)):
            return node.value.value
    raise AssertionError("no %s integer constant in the gate" % name)


def drop_from_list(text, victim, listname="LOCAL"):
    """Delete one name from a LOCAL/LIVE literal. Returns (new_text, landed)."""
    tree = ast.parse(text)
    lo, hi = span(text, tree, listname)
    lines = text.splitlines(keepends=True)
    body = "".join(lines[lo - 1:hi])
    pat = re.compile(r"\b%s\b\s*,|(?<=[,(\s])[^\S\n]*,[^\S\n]*\b%s\b\b" % (re.escape(victim), re.escape(victim)))
    new_body, n = pat.subn("", body, count=1)
    if n != 1:
        return text, False
    lines[lo - 1:hi] = [new_body]
    return "".join(lines), True


def add_decorated_check(text, fname):
    """Append a function that wears @check and is in NEITHER list. Counts are
    untouched, so no floor can catch this - only the decorated=>registered
    invariant can. That is what isolates case B from case A."""
    tail = "\n\n@check(\"sabotage: a decorated check that nobody registered\")\ndef %s():\n    return \"ok\", \"never registered\"\n" % fname
    return text + tail


def seed_pristine(root):
    """Copy the REAL baseline set into the temp tree.

    `load()` only materialises scripts/acceptance.py, so the pristine cases would
    otherwise trip the "directory absent" floor instead of the one they mean to
    prove - two different reds for one sabotage. Seeding is what isolates them."""
    dst = root / "scripts" / "artifacts_pristine"
    dst.mkdir(parents=True, exist_ok=True)
    for f in REAL_PRISTINE.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)
    return dst


def build(text, tag, pristine=False):
    """Materialise a temp tree holding a COPY of the gate, optionally with the
    real pristine baseline set in place. `load()` imports that copy, so its REPO
    points at the temp tree - which is the only reason a mutation of the
    FILE can be observed at all."""
    root = pathlib.Path(tempfile.mkdtemp(prefix="prw_%s_" % tag))
    if pristine:
        seed_pristine(root)
    mod = load(text, tag, root)[1]
    return root, mod


def grade(status, detail, expect_key, tag):
    """Name-graded verdict: a FAIL whose detail does not mention the expected
    refusal is an UNNAMED red, not proof. Prints the line and returns
    (ok, kind)."""
    named = status == "FAIL" and re.search(expect_key, detail, re.IGNORECASE)
    print("  %s: status=%s  %s" % (tag, status, detail[:110]))
    if named:
        return True, "named red"
    why = ("guard FAILED, but not on %s - refusing for an unrelated reason"
           % expect_key if status == "FAIL" else
           "guard answered %s to a gate that lost what it had to measure - the "
           "hole this proof exists to catch" % status)
    print("  %s: NOT PROVEN - %s" % (tag, why))
    return False, "unnamed"


def load_real():
    """Import the REAL, untouched gate from the real repo.

    A control's job is "the untouched tree stays green", so for the pristine
    function it must run where git can resolve - a temp tree has no .git, the
    floors pass, resolve() finds no committed source and the check answers SKIP.
    Any rule that tolerates SKIP here is a rubber stamp: it would pass a check
    patched to always SKIP. So this control takes no copy and no temp tree."""
    spec = importlib.util.spec_from_file_location("prw_real_gate", GATE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["prw_real_gate"] = mod
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.modules.pop("prw_real_gate", None)
    return mod


def case_control(clean):
    """The healthy tree must pass, for BOTH checks these cases sabotage.

    Without this, a guard patched to always FAIL would turn this file green while
    the gate refused to run at all.

    The two controls are deliberately different animals:
      * GUARD     - a copy of the gate, because the wiring guard reads only its
                    own source and needs no repository;
      * PRISTINE  - the REAL gate in the REAL repo, seeded baselines included.

    MEASURED, first run: the pristine control answered SKIP, not ok - in a temp
    tree the floors pass, then the git lookup finds no committed source and the
    check declines to answer. Only the floors are in scope for these cases, so a
    SKIP cannot be read as "healthy": it is the absence of an answer."""
    ok = True
    root, mod = build(clean, "control_wiring")
    try:
        status, detail = run_guard(mod, GUARD)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    if status != "ok":
        ok = False
        print("  control GUARD: RED - refused an intact tree: %s" % detail[:90])
    else:
        print("  control GUARD: status=ok  %s" % detail[:70])

    real = load_real()
    status, detail = run_guard(real, PRISTINE)
    if status != "ok":
        ok = False
        print("  control PRISTINE: RED - real tree answered %s: %s"
              % (status, detail[:90]))
    else:
        print("  control PRISTINE: status=ok  %s" % detail[:70])
    return ok


def case_a(clean):
    """Remove one LOCAL entry. The floor must notice."""
    tree = ast.parse(clean)
    local = list_names(tree, "LOCAL")
    live = set(list_names(tree, "LIVE"))
    victims = [n for n in local if n not in live]
    assert victims, "no LOCAL-only check to sabotage; the case is void"
    victim = victims[0]
    mutated, landed = drop_from_list(clean, victim)
    if not landed:
        print("  A: could not delete %r from LOCAL - mutation did not land" % victim)
        return False, "patch-miss"
    after = list_names(ast.parse(mutated), "LOCAL")
    gone = victim not in after and len(after) == len(local) - 1
    print("  A: removed %r from LOCAL  %d -> %d entries, landed=%s"
          % (victim, len(local), len(after), gone))
    if not gone:
        return False, "patch-miss"
    root, mod = load(mutated, "a")
    try:
        status, detail = run_guard(mod)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    named = status == "FAIL" and re.search(EXPECT["A_local_floor"], detail, re.IGNORECASE)
    print("  A: status=%s  %s" % (status, detail[:110]))
    if named:
        return True, "named red"
    # The tally contract has one bucket for "claimed a red, did not prove it":
    # named + unnamed == total. Both remaining outcomes land there, so the
    # distinction has to be said out loud or the log reads as a mystery.
    why = ("guard FAILED, but not on the LOCAL floor - refusing for an "
           "unrelated reason" if status == "FAIL" else
           "guard answered %s to a gate whose LOCAL lost a check - the hole "
           "this proof exists to catch" % status)
    print("  A: NOT PROVEN - %s" % why)
    return False, "unnamed"


def case_b(clean):
    """Add a decorated check that no list registers. Only the decorated =>
    registered invariant can catch it."""
    existing = set(list_names(ast.parse(clean), "LOCAL")) | set(list_names(ast.parse(clean), "LIVE"))
    fname = "z_unregistered_sabotage"
    assert fname not in existing, "sabotage name collides with a real check"
    mutated = add_decorated_check(clean, fname)
    names = {n.name for n in ast.parse(mutated).body
             if isinstance(n, ast.FunctionDef)}
    landed = fname in names
    print("  B: appended @check %s, landed=%s" % (fname, landed))
    if not landed:
        return False, "patch-miss"
    root, mod = load(mutated, "b")
    try:
        status, detail = run_guard(mod)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    named = status == "FAIL" and re.search(EXPECT["B_decorated_never_registered"], detail, re.IGNORECASE)
    print("  B: status=%s  %s" % (status, detail[:110]))
    if named:
        return True, "named red"
    why = ("guard FAILED, but not on the decorated-but-unregistered invariant - "
           "refusing for an unrelated reason" if status == "FAIL" else
           "guard answered %s to a @check no list registers - the hole this "
           "proof exists to catch" % status)
    print("  B: NOT PROVEN - %s" % why)
    return False, "unnamed"


def case_c(clean):
    """Shrink LIVE below its floor. Measured, not guessed: dropping ONE entry
    (16 -> 15) is NOT caught by MIN_LIVE_CHECKS=8 - what refuses that is the
    "decorated but never registered" invariant, the family case B already proves.
    First run of this case proved exactly that and scored an UNNAMED red, which is
    the counter working: a red that did not name its refusal is not proof.

    So the floor can only be proven from BELOW it: drop LIVE to
    MIN_LIVE_CHECKS - 1. The floor is read out of the gate text with ast, so the
    case cannot drift away from the constant it is supposed to exercise."""
    floor = const_value(clean, "MIN_LIVE_CHECKS")
    tree = ast.parse(clean)
    live = list_names(tree, "LIVE")
    assert len(live) > floor, ("LIVE has %d entries, not above the floor %d - "
                               "there is nothing below it to prove" % (len(live), floor))
    must_drop = len(live) - (floor - 1)
    mutated = clean
    for victim in live[:must_drop]:
        nxt, landed = drop_from_list(mutated, victim, "LIVE")
        assert landed, "could not delete %r from LIVE - mutation did not land" % victim
        mutated = nxt
    after = list_names(ast.parse(mutated), "LIVE")
    gone = len(after) == floor - 1 and not (set(after) & set(live[:must_drop]))
    print("  C: dropped %d LIVE entries  %d -> %d, floor MIN_LIVE_CHECKS=%d, "
          "still non-empty=%s, landed=%s"
          % (must_drop, len(live), len(after), floor, bool(after), gone))
    if not gone:
        return False, "patch-miss"
    root, mod = build(mutated, "c")
    try:
        status, detail = run_guard(mod)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return grade(status, detail, EXPECT["C_live_floor"], "C")


def case_d(clean):
    """Delete scripts/artifacts_pristine entirely. The "no directory" floor must
    refuse it and MUST say the baselines are required - a bare "directory missing"
    would leave the reader guessing whether the check ever looked at the count."""
    root, mod = build(clean, "d", pristine=True)
    shutil.rmtree(root / "scripts" / "artifacts_pristine", ignore_errors=True)
    present = (root / "scripts" / "artifacts_pristine").is_dir()
    print("  D: removed scripts/artifacts_pristine, still present=%s" % present)
    if present:
        return False, "patch-miss"
    try:
        status, detail = run_guard(mod, PRISTINE)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return grade(status, detail, EXPECT["D_pristine_absent"], "D")


def floor_value(text, name):
    """Read a floor constant out of the gate source at ANY scope.

    `const_value` only walks module level, which is why case E drifted: its
    floor `MIN_PRISTINE_COPIES` is function-LOCAL (acceptance.py L2189), so
    the module reader could not see it and the case kept a hardcoded
    denominator. Walk every assignment in the tree instead, and fail loudly
    if the name is gone - a harness that silently prunes to the wrong number
    is exactly the unwitnessed-check failure this harness exists to catch.
    """
    for node in ast.walk(ast.parse(text)):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and t.id == name:
                try:
                    return ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    raise AssertionError("%s is not a literal in the gate" % name)
    raise AssertionError("no %s in the gate source" % name)


def case_e(clean):
    """Prune the baseline set BELOW the floor - the directory still exists, so
    the "no directory" floor stays quiet and only MIN_PRISTINE_COPIES can see
    it. This is the case that matters most: the old denominator was
    len(list(iterdir())) - the files PRESENT - so a deletion printed 8/8 green.
    The victim is the lexicographically LAST file so the remaining ones still
    resolve against the temp tree the same way.

    The floor is READ FROM THE GATE, never hardcoded, and the case prunes
    strictly below it. Both halves matter: the repo shipped 10 baselines while
    this case pruned one file to 9 against a floor of 9, and the floor fires on
    `len < floor`, so `9 >= 9` let the check fall through to `resolve()` - no
    `.git` in the temp tree, so it answered SKIP and proved nothing. Reading the
    floor removes the drift; pruning below it removes the boundary."""
    root, mod = build(clean, "e", pristine=True)
    pdir = root / "scripts" / "artifacts_pristine"
    files = sorted(f for f in pdir.iterdir() if f.is_file())
    # The floor is read off the SAME gate text this case is mutating, at any
    # scope (it is function-local in the real file), so it can never drift.
    floor = floor_value(clean, "MIN_PRISTINE_COPIES")
    keep = floor - 1
    if keep < 0 or len(files) <= keep:
        return False, ("denominator drift: %d baselines, floor %d, cannot prune "
                       "strictly below it" % (len(files), floor))
    for victim in files[keep:]:
        victim.unlink()
    left = [f for f in pdir.iterdir() if f.is_file()]
    print("  E: pruned %d -> %d baselines (floor=%d, pruned strictly below),"
          " directory still present=%s"
          % (len(files), len(left), floor, pdir.is_dir()))
    if len(left) != keep:
        return False, "patch-miss: expected %d left, got %d" % (keep, len(left))
    try:
        status, detail = run_guard(mod, PRISTINE)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    return grade(status, detail, EXPECT["E_pristine_pruned"], "E")


def empty_list(text, listname="LOCAL"):
    """Rewrite a LOCAL/LIVE list literal to `[]`, using the AST span of THIS text.

    Emptiness needs its own mutation: deleting entries one at a time stops at the
    floor case, and the defect this release is really about is a list that can be
    emptied to ZERO while the other list still reports green."""
    tree = ast.parse(text)
    lo, hi = span(text, tree, listname)
    lines = text.splitlines(keepends=True)
    lines[lo - 1:hi] = ["%s = []\n" % listname]
    return "".join(lines)


def case_f(clean):
    """Empty LIVE completely, then LOCAL completely. This is the headline defect
    of 0.7.41, so it is the case that MUST have a harness behind it.

    Measured, first run of this file: no case covered emptiness at all - case C
    proved the floor (16 -> 7) and cases A/B proved the wiring invariants, but the
    `LIVE = []` -> READY measurement in the release notes stood on prose alone.

    Note the order in the guard: the emptiness refusal (L1932) comes BEFORE both
    floors, so an emptied list is refused by name and never reaches them."""
    for listname in ("LIVE", "LOCAL"):
        mutated = empty_list(clean, listname)
        after = list_names(ast.parse(mutated), listname)
        if after:
            print("  F: %s still has %d entries - mutation did not land" % (listname, len(after)))
            return False, "patch-miss"
        root, mod = build(mutated, "f_%s" % listname.lower())
        try:
            status, detail = run_guard(mod)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        good, kind = grade(status, detail, EXPECT["F_emptiness"],
                           "F[%s=[]]" % listname)
        if not good:
            return False, kind
    return True, "named red"


def main():
    if not GATE.is_file():
        print("HARNESS: %s not found" % GATE)
        return 2
    clean = GATE.read_text(encoding="utf-8")
    print("=== the wiring guard must refuse a silently unwired gate ===")
    print("gate: %s (%d chars)" % (GATE, len(clean)))
    print("LOCAL=%d LIVE=%d" % (len(list_names(ast.parse(clean), "LOCAL")),
                                 len(list_names(ast.parse(clean), "LIVE"))))

    results = [("A_local_floor", case_a(clean)),
               ("B_decorated_never_registered", case_b(clean)),
               ("C_live_floor", case_c(clean)),
               ("D_pristine_absent", case_d(clean)),
               ("E_pristine_pruned", case_e(clean)),
               ("F_emptiness", case_f(clean))]
    named = sum(1 for _n, (_ok, kind) in results if kind == "named red")
    unnamed = sum(1 for _n, (_ok, kind) in results if kind == "unnamed")
    invalid = sum(1 for _n, (_ok, kind) in results if kind == "patch-miss")

    control_ok = case_control(clean)

    print("")
    print("%d named red, %d unnamed, %d invalid" % (named, unnamed, invalid))
    print("control 1/1 %s" % ("ok" if control_ok else "RED"))
    for label, (ok, kind) in results:
        if not ok:
            print("  NOT PROVEN  %s (%s)" % (label, kind))
    good = named == len(results) and unnamed == 0 and invalid == 0 and control_ok
    print("WIRING PROOF " + ("PROVEN" if good else "RED"))
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main())