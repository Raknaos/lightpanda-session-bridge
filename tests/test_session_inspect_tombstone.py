"""The /v1/session/inspect tombstone, and why this file has two layers.

The route once returned cookie names, the origin and the page URL/title to any
caller. It was removed - and a removal with no test is a removal with no
ratchet: the next edit that helpfully "restores" or "tidies up" that branch
would leak again and every suite would still be green.

So the 404 is pinned twice, because one layer is measurably not enough.

MEASURED, not assumed: deleting the `elif` branch leaves the request
answering 404 anyway - the final `else:` of `do_GET` sends the same
{"ok": false, "error": "not found"}. A purely HTTP test is BLIND to the
regression: identical status, identical body, no red. So this file has

  layer 1 (HTTP)   - what a caller actually observes, on every path variant
                     and every verb, and that no removed field comes back;
  layer 2 (AST)    - the tombstone exists as its OWN branch that answers 404,
                     read at its cause. Deleting it turns layer 2 red.

Layer 2 is a separate test method on purpose: one failure must name which
layer broke, instead of a single assert that says "something about inspect".

SELF-CONTAINED, same reason as test_session_expiry_chain.py: it serves the
REAL Handler on an ephemeral port with its own token. It never reads the
operator's ~/.config secret and never stops the running relay.
"""
import ast
import http.client
import json
import pathlib
import sys
import threading
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "relay"))

import server  # noqa: E402

EXT_ID = "fcigkjkchglchhohedljlenopbkgnino"
TEST_TOKEN = "test-token-not-a-secret-0000"
SERVER_PY = ROOT / "relay" / "server.py"
INSPECT = "/v1/session/inspect"


# Fields the route used to hand out. Their absence is the point of the 404.
REMOVED_FIELDS = ("cookies", "cookie", "url", "title", "origin", "pages",
                  "expires_hint", "session_id")


class _LiveRelay:
    """The real Handler on an ephemeral port, with our own token."""

    def __enter__(self):
        self._real_secret = server._load_secret
        server._load_secret = lambda: TEST_TOKEN
        self.srv = server.RelayServer(("127.0.0.1", 0), server.Handler)
        self.port = self.srv.server_address[1]
        self.thread = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()
        server._load_secret = self._real_secret
        return False

    def call(self, method, path, timeout=25):
        """One request with a VALID token and a PINNED extension origin.

        Authorization is deliberately correct: the tombstone must hold for an
        authorised caller, not merely because the caller was rejected.
        """
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=timeout)
        try:
            body = b"" if method in ("POST", "PUT", "PATCH") else None
            headers = {"X-Bridge-Token": TEST_TOKEN,
                       "Origin": "chrome-extension://" + EXT_ID}
            if body is not None:
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=body, headers=headers)
            resp = conn.getresponse()
            raw = resp.read().decode("utf-8", "replace")
            try:
                return resp.status, json.loads(raw)
            except ValueError:
                return resp.status, {"raw": raw}
        finally:
            conn.close()


def _is_inspect_test(node):
    """True when `node` is exactly `self.path == "/v1/session/inspect"`.

    Compares the PARSED value, not `ast.unparse` text: unparse re-normalises
    the quotes to single ones, which is how an earlier probe of mine compared
    unequal to its own target and cried "no tombstone".
    """
    if not isinstance(node, ast.Compare) or len(node.ops) != 1:
        return False
    if not isinstance(node.ops[0], ast.Eq):
        return False
    left = node.left
    if not (isinstance(left, ast.Attribute) and left.attr == "path"
            and isinstance(left.value, ast.Name) and left.value.id == "self"):
        return False
    right = node.comparators[0]
    return (isinstance(right, ast.Constant) and right.value == INSPECT)


def _sent_status(node):
    """The first literal status passed to a `self.send_json(...)` in a body."""
    for stmt in node.body:
        if not isinstance(stmt, ast.Expr) or not isinstance(stmt.value, ast.Call):
            continue
        fn = stmt.value.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "send_json"):
            continue
        if stmt.value.args and isinstance(stmt.value.args[0], ast.Constant):
            return stmt.value.args[0].value
    return None


def _elif_chain(stmt):
    """Walk an if/elif chain, returning every link in it.

    Taking the `ast.If` NODE out of the chain to mutate it drags its whole
    `orelse` - the rest of the chain plus the terminal else - which is how a
    faithful "delete one branch" mutation turns into a broken module.
    """
    chain = [stmt]
    while chain[-1].orelse and len(chain[-1].orelse) == 1 \
            and isinstance(chain[-1].orelse[0], ast.If):
        chain.append(chain[-1].orelse[0])
    return chain


def inspect_branch(source):
    """The one do_GET branch whose test is `self.path == INSPECT`, or None."""
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.FunctionDef) and node.name == "do_GET"):
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.If):
                continue
            for link in _elif_chain(stmt):
                if _is_inspect_test(link.test):
                    return link
    return None


def inspect_branches(source):
    """Every explicit `if`/`elif` in do_GET matching INSPECT, as a list.

    The COUNT is what the regression turns on, and it is deliberately not
    inferred from HTTP behaviour: the terminal `else:` answers 404 on its own,
    so HTTP cannot see the branch disappear. Raises if do_GET is absent, so a
    renamed or deleted method fails loudly instead of reading as "no branch".
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.FunctionDef) and node.name == "do_GET"):
            continue
        for stmt in node.body:
            if isinstance(stmt, ast.If):
                for link in _elif_chain(stmt):
                    if _is_inspect_test(link.test):
                        found.append(link)
    if not found and not any(isinstance(n, ast.FunctionDef) and n.name == "do_GET"
                             for n in ast.walk(ast.parse(source))):
        raise AssertionError("do_GET not found in relay/server.py")
    return found


def _sole_inspect_branch(source):
    """The single inspect branch, or a failure naming the count.

    Used where the branch's identity is the premise, so "zero branches" must
    read as a red assertion about the tombstone, never as an IndexError trace
    that hides which expectation broke.
    """
    branches = inspect_branches(source)
    if len(branches) != 1:
        raise AssertionError(
            "expected exactly ONE explicit /v1/session/inspect branch in "
            "do_GET, found %d - the tombstone is gone (HTTP still answers 404 "
            "via do_GET's terminal else, so only this assertion sees it)"
            % len(branches))
    return branches[0]


class TestInspectIsGoneOverHttp(unittest.TestCase):
    """LAYER 1 - what a caller observes. Blind to the branch being deleted."""

    @classmethod
    def setUpClass(cls):
        cls.relay = _LiveRelay().__enter__()
        cls.addClassCleanup(cls.relay.__exit__, None)

    def test_authorised_get_is_404_not_found(self):
        status, payload = self.relay.call("GET", INSPECT)
        self.assertEqual(404, status, "GET %s must stay a deliberate 404" % INSPECT)
        self.assertEqual({"ok": False, "error": "not found"}, payload)

    def test_no_removed_field_comes_back(self):
        _, payload = self.relay.call("GET", INSPECT)
        blob = json.dumps(payload).lower()
        for field in REMOVED_FIELDS:
            self.assertNotIn(field, blob,
                             "the 404 body re-exposes a removed field: %r" % field)

    def test_path_variants_are_not_a_way_in(self):
        """No spelling of the route reaches anything but the 404.

        The dispatch is a raw `self.path == "..."` with no urlparse, so a
        query string, a fragment or a trailing slash is a different key.
        """
        variants = [INSPECT, INSPECT + "/", INSPECT + "?", INSPECT + "?x=1",
                    INSPECT + "#frag", INSPECT.upper(), "//v1/session/inspect",
                    INSPECT + "%20", INSPECT + "/..", "/v1/session/../session/inspect"]
        with _LiveRelay() as relay:
            for variant in variants:
                status, _ = relay.call("GET", variant)
                self.assertEqual(404, status,
                                 "variant %r leaked past the tombstone" % variant)

    def test_other_verbs_do_not_leak(self):
        """POST and friends are covered too: none may serve the route.

        Measured baseline: GET hits the tombstone (404), POST falls through to
        do_GET's terminal else (404), and HEAD/PUT/DELETE/PATCH are answered
        501 by BaseHTTPRequestHandler because Handler defines no such verb.
        The test asserts the invariant - nothing but 404/501 - not the
        bookkeeping, so adding a verb later cannot turn this red spuriously.
        """
        with _LiveRelay() as relay:
            for method in ("POST", "PUT", "DELETE", "PATCH", "HEAD"):
                status, _ = relay.call(method, INSPECT)
                self.assertIn(status, (404, 501),
                              "%s %s served the removed route" % (method, INSPECT))


class TestTheTombstoneBranchExists(unittest.TestCase):
    """LAYER 2 - the cause. Red when the branch is deleted, green otherwise."""

    @classmethod
    def setUpClass(cls):
        cls.source = SERVER_PY.read_text(encoding="utf-8")
        cls.lines = cls.source.splitlines(keepends=True)

    def test_exactly_one_inspect_branch_and_it_sends_404(self):
        branches = inspect_branches(self.source)
        self.assertEqual(1, len(branches),
                         "expected exactly ONE explicit inspect branch, got %d "
                         "(deleting it leaves do_GET's terminal else answering "
                         "404, so HTTP alone cannot see it)" % len(branches))
        self.assertEqual(404, _sent_status(branches[0]),
                         "the inspect branch must answer 404 explicitly")

    def test_branch_is_documented_as_a_removal(self):
        """The 404 is a decision; the comment is what keeps it a decision.

        Read from the SOURCE LINES, not the AST: the note at relay/server.py
        L1372 is a `#` comment, which the tree does not carry at all. Only the
        source segment can see it - an AST-only probe reported this green with
        the comment deleted.
        """
        branch = _sole_inspect_branch(self.source)
        segment = "".join(self.lines[branch.lineno - 1:branch.end_lineno])
        comment = "\n".join(line for line in segment.splitlines()
                            if line.strip().startswith("#"))
        self.assertIn("removed", comment.lower(),
                      "the inspect tombstone lost the note explaining that its "
                      "404 is deliberate:\n%s" % segment)


class TestLayerTwoIsNotBlind(unittest.TestCase):
    """The meta-test: prove layer 2 goes red on the mutation it exists for.

    Without this, layer 2 is an assertion nobody has ever seen fail, and an
    assertion that was never seen to fail is not a ratchet. Deleting ONLY the
    inspect branch's lines - the faithful mutation, leaving the elif chain and
    the terminal else intact - must drop the branch count to 0.
    """
    def test_deleting_the_branch_is_detected(self):
        """Mutate the source: remove exactly the branch, keep the chain.

        Header line through the end of the branch body ONLY. Taking the ast.If
        node out would drag the whole orelse chain - /v1/diagnostics and the
        terminal else - and the module would then fail to parse, which is how
        an earlier probe of mine reported a false negative.
        """
        source = SERVER_PY.read_text(encoding="utf-8")
        lines = source.splitlines(keepends=True)
        branches = inspect_branches(source)
        self.assertEqual(1, len(branches), "need exactly one branch to mutate")
        start, end = branches[0].lineno, branches[0].end_lineno
        mutated = "".join(lines[:start - 1] + lines[end:])
        self.assertEqual([], inspect_branches(mutated),
                         "deleting lines %d-%d did NOT turn layer 2 red - the "
                         "ratchet does not bite" % (start, end))


if __name__ == "__main__":
    unittest.main()