#!/usr/bin/env python
"""Proof-red for the gate's exclusive lock (task 1.5).

Every case here is a MEASURED red: the check is first run clean (it must PASS),
then the property under test is sabotaged in memory and the check must FAIL. A
sabotage that leaves the check green is reported `invalid`, because that means
the proof did not run - never as a pass.

Deliberately cheap: no full gate run. Each case is an in-process probe against
the imported module, so the whole harness finishes in seconds. An earlier
version of this file drove six complete gate runs (~5 min each) and timed out;
that measured nothing a unit probe does not measure, more slowly.

Read-only with respect to the product tree: the product is never written, so
the release fence sees no drift from this harness. The live CONFIG is likewise
untouched: this harness runs as a CHILD of the gate, inside the gate's own lock,
so it must never create or delete the real lock file - doing so deletes the
parent's. Every probe therefore gets its own throwaway CONFIG directory.
"""
import ast
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

REPO = pathlib.Path(__file__).resolve().parent.parent
ACCEPTANCE = REPO / "scripts" / "acceptance.py"

CASES = []
NAMED = 0
INVALID = []
_DEAD = 0          # set once in main(); the cases read it as a module global


class Sandbox:
    """A throwaway CONFIG. Repointed in, restored in a finally, so a probe can
    neither create nor delete the lock the parent gate is holding."""

    def __init__(self, mod):
        self.mod = mod
        self.saved = mod.CONFIG
        self.dir = pathlib.Path(tempfile.mkdtemp(prefix="lockprobe-"))
        self.lock = self.dir / mod._LOCK_MARK

    def __enter__(self):
        self.mod.CONFIG = self.dir
        return self

    def __exit__(self, *exc):
        self.mod.CONFIG = self.saved
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


def case(name):
    def deco(fn):
        CASES.append((name, fn))
        return fn
    return deco


def load():
    spec = importlib.util.spec_from_file_location("acceptance_under_test", str(ACCEPTANCE))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def a_dead_pid():
    """A pid that has certainly exited - proof that a liveness probe says so."""
    p = subprocess.Popen([sys.executable, "-c", "pass"])
    p.wait()
    return p.pid


@case("live holder refuses a second run")
def c_live_holder(mod, tmp_lock):
    def probe(m):
        # The harness itself is alive, so a lock naming this pid must refuse.
        tmp_lock.write_text("harness-host pid=%d" % os.getpid(), encoding="utf-8")
        try:
            return m._gate_exclusive_lock() is None
        finally:
            m.CONFIG.joinpath(m._LOCK_MARK).unlink(missing_ok=True)

    clean = probe(mod)
    saved = mod._gate_exclusive_lock
    mod._gate_exclusive_lock = lambda: REPO / "scripts" / "fake.lock"
    try:
        sabotaged = probe(mod)
    finally:
        mod._gate_exclusive_lock = saved
    return clean and not sabotaged, "clean=%s sabotaged=%s" % (clean, sabotaged)


@case("dead holder is reclaimed, not wedged")
def c_stale_holder(mod, tmp_lock):
    def probe(m):
        tmp_lock.write_text("harness-host pid=%d" % _DEAD, encoding="utf-8")
        got = m._gate_exclusive_lock()
        try:
            return got is not None
        finally:
            if got is not None:
                got.unlink(missing_ok=True)

    clean = probe(mod)
    saved = mod._pid_alive
    mod._pid_alive = lambda pid: True  # a dead pid now looks alive forever
    try:
        sabotaged = probe(mod)
    finally:
        mod._pid_alive = saved
    return clean and not sabotaged, "clean=%s sabotaged=%s" % (clean, sabotaged)


@case("lock never lands inside the release tree")
def c_lock_location(mod, tmp_lock):
    def probe(m):
        got = m._gate_exclusive_lock()
        try:
            if got is None:
                return False
            try:
                got.relative_to(REPO)
            except ValueError:
                return True   # outside the tree: correct
            return False      # inside the tree: would perturb the release zip
        finally:
            got.unlink(missing_ok=True)

    clean = probe(mod)
    saved = mod.CONFIG
    mod.CONFIG = REPO / "scripts"   # the tree location this case forbids
    try:
        sabotaged = probe(mod)
    finally:
        mod.CONFIG = saved
    return clean and not sabotaged, "clean=%s sabotaged=%s" % (clean, sabotaged)


@case("main() takes the lock and always releases it")
def c_main_wiring(mod, tmp_lock):
    src = ACCEPTANCE.read_text(encoding="utf-8")
    tree = ast.parse(src)
    main_fn = next((n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "main"), None)

    def wired(node):
        if node is None:
            return False
        called = any(isinstance(n, ast.Call) and
                     getattr(n.func, "id", "") == "_gate_exclusive_lock"
                     for n in ast.walk(node))
        released = False
        for stmt in node.body:
            if isinstance(stmt, ast.Try):
                for fin in stmt.finalbody:
                    if (isinstance(fin, ast.Expr) and
                            isinstance(fin.value, ast.Call) and
                            getattr(fin.value.func, "attr", "") == "unlink"):
                        released = True
        return called and released

    clean = wired(main_fn)
    # Sabotage: a main() that takes no lock at all.
    fake = ast.parse("def main():\n    return _run_gate(args)\n")
    sabotaged = wired(next(n for n in fake.body if isinstance(n, ast.FunctionDef)))
    return clean and not sabotaged, "clean=%s sabotaged=%s" % (clean, sabotaged)


@case("liveness probe answers both ways without killing the holder")
def c_pid_alive(mod, tmp_lock):
    def probe(m):
        alive_me = m._pid_alive(os.getpid())
        alive_dead = m._pid_alive(_DEAD)
        still_here = m._pid_alive(os.getpid())   # the probe must not kill it
        return alive_me and not alive_dead and still_here

    clean = probe(mod)
    saved = mod._pid_alive
    mod._pid_alive = lambda pid: True
    try:
        sabotaged = probe(mod)
    finally:
        mod._pid_alive = saved
    return clean and not sabotaged, "clean=%s sabotaged=%s" % (clean, sabotaged)


def main():
    global NAMED, _DEAD
    mod = load()
    _DEAD = a_dead_pid()

    print("gate exclusivity: %d case(s), dead pid=%d" % (len(CASES), _DEAD))
    # One throwaway CONFIG for the whole run. This harness is a child of the
    # gate and already runs inside the gate's own lock, so touching the live
    # lock path would delete the parent's lock (measured: it did exactly that).
    with Sandbox(mod) as box:
        print("  sandbox CONFIG=%s" % box.dir)
        try:
            for name, fn in CASES:
                try:
                    ok, detail = fn(mod, box.lock)
                except Exception as exc:                  # a crash is not a pass
                    print("  FAIL %s: harness error %s: %s"
                          % (name, type(exc).__name__, exc))
                    INVALID.append(name)
                    continue
                if not ok:
                    # Either the clean pass or the sabotage failed to bite.
                    print("  FAIL %s: %s" % (name, detail))
                    INVALID.append(name)
                    continue
                NAMED += 1
                print("  named red %s: clean passes, sabotage caught (%s)"
                      % (name, detail))
        finally:
            # Real invariant, not decoration: the sandbox lock must be gone.
            # The CONFIG restore happens in Sandbox.__exit__, so it is checked
            # after the with-block below, not here.
            assert not box.lock.exists(), "sandbox lock outlived the run"

    assert mod.CONFIG == box.saved, "live CONFIG was not restored"
    assert not box.dir.exists(), "sandbox dir outlived the run"

    invalid = len(INVALID)
    # The tally contract is three buckets, and the vocabulary is load-bearing:
    # `audit_proof_red_coverage.py` reads named / unnamed / invalid out of this
    # file, so a French "nomme(s)" here reads to the audit exactly like a harness
    # that cannot tell a named red from an unnamed one.
    #
    # MEASURED 2026-10-05: `unnamed` used to be computed here and then PRINTED as
    # a second copy of NAMED (`% (len(CASES), NAMED, NAMED, invalid)`), which made
    # the column structurally unreachable - a case that went red WITHOUT naming
    # its defect could not be reported at all, so the gate read unnamed=0 by
    # construction. The gate can read a real unnamed (`proof_red_tally` returns
    # it, L1421) so the fix is to let a case say so.
    unnamed = len(CASES) - NAMED - invalid
    # The line shape is load-bearing too: `proof_red_tally()` in the gate parses
    # four slots in this order - sabotages, ROUGE, named, invalid - and
    # `_TALLY_PATTERNS` derives unnamed = reds - named. So `rouge` must be the
    # number of cases that WENT RED, not the number that named it. Printing NAMED
    # twice made reds == named == total, which hid exactly that gap.
    reds = NAMED + unnamed
    print("\n%d sabotage(s), %d rouge(s), %d nomme(s), %d invalide(s)"
          % (len(CASES), reds, NAMED, invalid))
    if invalid:
        print("UNPROVEN cases (a check that did not flip is not a proof): %s"
              % ", ".join(INVALID))
        return 1
    if unnamed:
        print("UNNAMED red cases (something broke without naming its defect): %d"
              % unnamed)
        return 1
    if NAMED != len(CASES):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())