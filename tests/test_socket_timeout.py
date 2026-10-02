# -*- coding: utf-8 -*-
"""A silent socket must be released, and a request slower than the deadline must survive.

Measured before the fix: 25 connections that sent nothing stayed open past 35s.
`Handler` had no class-level timeout, so `StreamRequestHandler.setup()` left the
socket blocking, and the `settimeout(10)` inside do_GET only ran AFTER
handle_one_request had already read the request line and headers - which is
exactly the read a client holds open by sending nothing. /health kept answering,
so this was thread and memory exhaustion, not a hang.

Every test here serves the REAL `server.Handler` class. The first draft
subclassed it with `timeout = 2` to keep the suite fast - which made the suite
BLIND to the production constant: sabotaging `Handler.timeout` to 600 in
server.py left all five tests green. A test that overrides the very value under
test is decoration. Speed now comes from a read-side wait budget scaled to the
real deadline, never from replacing it.
"""
import pathlib
import select
import socket
import sys
import threading
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "relay"))

import server  # noqa: E402

SRC = (REPO_ROOT / "relay" / "server.py").read_text(encoding="utf-8")
# Real production deadline; every wait in this file is derived from it.
DEADLINE = float(server.Handler.timeout)


def _serve(handler_cls=None):
    """Serve the REAL Handler on an ephemeral port."""
    srv = server.RelayServer(("127.0.0.1", 0), handler_cls or server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def _recv_headers(sock):
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            break
        buf += chunk
    return buf


class HandlerHasAClassTimeout(unittest.TestCase):
    def test_the_deadline_is_a_class_attribute(self):
        """setup() reads self.timeout; a per-method settimeout is too late."""
        import ast
        found = None
        for node in ast.parse(SRC).body:
            if isinstance(node, ast.ClassDef) and node.name == "Handler":
                for stmt in node.body:
                    if (isinstance(stmt, ast.Assign)
                            and any(getattr(t, "id", None) == "timeout"
                                    for t in stmt.targets)):
                        found = stmt.value.value
        self.assertIsNotNone(
            found, "Handler n'a pas de timeout de classe : setup() laisse le "
                   "socket en blocage et rien ne ferme une connexion muette")
        self.assertGreaterEqual(found, 5)

    def test_do_get_keeps_its_own_read_deadline(self):
        j = SRC.index("def do_GET")
        self.assertIn("settimeout", SRC[j:SRC.index("\n    def ", j + 10)])


class SilentSocketsDieAtTheDeadline(unittest.TestCase):
    """An ABSOLUTE window, with the sabotage value stated next to it.

    A test must distinguish "closed at 15s" from "closed at 45s", and a RELATIVE
    window cannot: 0.7 x 15 = 10.5 (the good deadline looks unapplied), 0.7 x 45 =
    31.5 (the sabotaged deadline still closes inside it). So the window is an
    absolute constant chosen once: > the shipped deadline, < the sabotaged one.

    There is deliberately NO setUpClass guard. I added one ("skip if the deadline
    exceeds the window") and it inverted the proof: under the 45s sabotage it
    SKIPPED the whole class and the run reported OK(skipped=1) - the guard that
    was supposed to keep the test honest silenced it. A test that skips itself
    when the property under test is wrong is the decoration rule wearing a
    disguise. The two assertions below must BOTH hold, in this order, and a
    sabotage that breaks either one turns the run red.
    """
    ATTEND_WINDOW = 25.0   # > 15 (shipped) and < 45 (sabotage by the proof script)
    SABOTAGE_DEADLINE = 45.0

    def test_the_window_separates_the_shipped_deadline_from_the_sabotage(self):
        """States the calibration as a fact, so a future deadline bump is caught
        HERE with a clear message instead of silently blinding the next test."""
        self.assertGreater(self.ATTEND_WINDOW, DEADLINE,
                           "ATTEND_WINDOW (%.0fs) doit depasser le delai de "
                           "production (%.0fs), sinon le test saute ou faux-"
                           "rougit" % (self.ATTEND_WINDOW, DEADLINE))
        self.assertLess(self.ATTEND_WINDOW, self.SABOTAGE_DEADLINE,
                        "ATTEND_WINDOW (%.0fs) doit rester SOUS le delai "
                        "sabotage (%.0fs), sinon la preuve rouge ne peut pas "
                        "distinguer les deux"
                        % (self.ATTEND_WINDOW, self.SABOTAGE_DEADLINE))

    def test_a_silent_connection_is_open_before_and_closed_after(self):
        # Both bounds above are checked FIRST (in the previous test, same class):
        # if the deadline grew past the window, this wait would be measuring the
        # wrong thing - but that is now a loud, named failure, not a skip.
        srv, port = _serve()
        self.addCleanup(srv.shutdown)
        sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.addCleanup(lambda: sock.close())
        # Headers deliberately truncated: the server blocks in readline() for the
        # rest of the request line / headers, which is the read that used to hang.
        sock.sendall(b"GET /health HTTP/1.1\r\n")

        early, _, _ = select.select([sock], [], [], 1.0)
        self.assertEqual(early, [],
                         "le serveur a coupe une connexion avant son echeance")

        # Absolute window: b"" (EOF) proves the deadline fired and closed us.
        sock.settimeout(self.ATTEND_WINDOW)
        start = time.time()
        closed = False
        while time.time() - start < self.ATTEND_WINDOW:
            try:
                data = sock.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                closed = True
                break
            if data == b"":
                closed = True
                break
        self.assertTrue(
            closed, "une connexion muette est restee ouverte apres %.0fs "
                    "(delai de classe %.0fs) : le delai ne la ferme pas"
                    % (time.time() - start, DEADLINE))

    def test_a_real_request_still_gets_a_real_answer(self):
        srv, port = _serve()
        self.addCleanup(srv.shutdown)
        sock = socket.create_connection(("127.0.0.1", port), timeout=10)
        self.addCleanup(lambda: sock.close())
        sock.sendall(b"GET /health HTTP/1.1\r\nHost: x\r\n\r\n")
        sock.settimeout(DEADLINE + 5)
        self.assertIn(b"200 OK", _recv_headers(sock))


class TheDeadlineIsPerOperationNotABudget(unittest.TestCase):
    """settimeout bounds ONE read/write, not the request's total duration.

    Guards against "fixing" the exhaustion bug by capping the whole request:
    the CDP import path legitimately runs several seconds (navigation settle +
    four injection rounds), and a total-duration cap would silently break it
    while every unit test stayed green.

    The handler is the real one with a route deliberately made slow, so the
    production `timeout` value is the one under test.
    """
    def test_a_handler_slower_than_the_deadline_still_answers_completely(self):
        slow = {"n": 0}

        class _SlowRoute(server.Handler):
            def do_GET(self):
                if self.path == "/slow":
                    slow["n"] += 1
                    # Outlive the deadline before ANY byte is written, then
                    # answer /health's own body. super().do_GET() would 404 here
                    # (no /slow route) - the test would then measure a 404, not
                    # the property it claims.
                    time.sleep(DEADLINE * 2.0)
                    self.send_json(200, {
                        "ok": True, "service": "lightpanda-session-bridge",
                        "slow": True})
                    return
                super().do_GET()

        srv, port = _serve(_SlowRoute)
        self.addCleanup(srv.shutdown)
        sock = socket.create_connection(("127.0.0.1", port), timeout=DEADLINE * 4)
        self.addCleanup(lambda: sock.close())
        started = time.time()
        sock.sendall(b"GET /slow HTTP/1.1\r\nHost: x\r\n\r\n")
        sock.settimeout(DEADLINE * 6)
        buf = b""
        expected = None
        while True:
            try:
                chunk = sock.recv(4096)
            except socket.timeout:
                self.fail("pas de reponse complete : le delai a coupe le travail")
            if not chunk:
                break
            buf += chunk
            if expected is None and b"\r\n\r\n" in buf:
                head = buf.split(b"\r\n\r\n", 1)[0]
                for line in head.split(b"\r\n"):
                    if line.lower().startswith(b"content-length:"):
                        expected = int(line.split(b":", 1)[1].strip())
            if expected is not None and \
                    len(buf.split(b"\r\n\r\n", 1)[1]) >= expected:
                break
        elapsed = time.time() - started
        self.assertEqual(slow["n"], 1, "la route lente n'a pas ete exercee")
        self.assertIn(b"200 OK", buf, buf[:120].decode("latin-1"))
        self.assertIn(b'"slow": true', buf)
        self.assertGreater(elapsed, DEADLINE,
                           "le gestionnaire n'a pas depasse le delai : le test "
                           "n'a pas exerce la propriete qu'il pretend mesurer")


if __name__ == "__main__":
    unittest.main()