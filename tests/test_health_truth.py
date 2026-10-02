"""The relay must never report "attached" for a connection it cannot use.

A user who opens the popup after Lightpanda restarted sees the relay badge turn
green - "Relay online" - while every sync fails. That is the same class of bug as
v0.5.7 (an import that could never finish): the UI told a reassuring story about
a resource that was dead.

Three real defects, all in this area:

1. ``_ensure_connection`` returned early whenever ``_CDP_TRANSPORT is not None``.
   A dead socket is still a live Python object, so after WSL/Lightpanda went away
   the relay kept that stale transport forever and never reopened it. Every
   subsequent call raised on the dead socket; only an explicit resync saved it.
2. ``/health`` derived ``attached`` from ``_CDP_SESSION_ID is not None``, a flag
   that is never cleared when the socket dies. It answered 200 attached=true for
   a dead connection - a health endpoint that lies.
3. ``CdpTransport.request`` skipped unsolicited CDP events with no bound: a
   target emitting a console event per millisecond kept the loop spinning until
   the socket timeout, on the thread that serves the HTTP request.

The tests below each revert-proof a fix: every one goes red without the fix.
"""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "relay"))

import server as relay  # noqa: E402  (relay/ is the daemon's import root)


class DeadSocket:
    """A socket whose peer is gone - the WinError 10053 shape."""

    def send(self, _):
        raise OSError(10053, "connection aborted")

    def recv(self):
        raise OSError(10053, "connection aborted")

    def close(self):
        pass


class ClosedSocket:
    """A socket the peer closed gracefully: recv() returns b"" forever."""

    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)

    def recv(self):
        return b""

    def close(self):
        pass


class QuietSocket:
    """A socket that answers exactly what it is asked."""

    def __init__(self):
        self.sent = []
        self.reply_id = -1

    def send(self, payload):
        self.sent.append(payload)
        self.reply_id = json.loads(payload)["id"]

    def recv(self):
        return json.dumps({"id": self.reply_id, "result": {"ok": 1}})

    def close(self):
        pass


class EventStormSocket:
    """Answers nothing; only ever emits unsolicited events (no "id")."""

    LIMIT = 5000

    def __init__(self):
        self.sent = []

    def send(self, payload):
        self.sent.append(payload)

    def recv(self):
        if len(self.sent) > self.LIMIT:
            raise AssertionError(
                "recv() called %d times waiting for one reply: the event-skip "
                "loop is unbounded" % len(self.sent))
        return json.dumps({"method": "Runtime.consoleAPICalled", "params": {}})

    def close(self):
        pass


class _RelayState:
    """Save/restore the four CDP globals so tests cannot leak into each other."""

    def __init__(self):
        self.saved = None

    def __enter__(self):
        self.saved = (relay._CDP_TRANSPORT, relay._CDP_SESSION_ID,
                      relay._CDP_SOCKET, relay._CDP_TARGET_ID)
        return self

    def __exit__(self, *exc):
        (relay._CDP_TRANSPORT, relay._CDP_SESSION_ID,
         relay._CDP_SOCKET, relay._CDP_TARGET_ID) = self.saved
        return False

    @staticmethod
    def install(transport):
        relay._CDP_TRANSPORT = transport
        relay._CDP_SESSION_ID = "sess-1"
        relay._CDP_SOCKET = getattr(transport, "socket", None)
        relay._CDP_TARGET_ID = "tgt-1"


class TransportLearnsItDied(unittest.TestCase):
    def test_a_failed_command_marks_the_transport_dead(self):
        """The core fix, and the precondition for both other fixes: the transport
        must be able to say it is dead. Without this, defect 1 is unfixable and
        /health can only guess."""
        transport = relay.CdpTransport(DeadSocket())
        self.assertTrue(transport.alive(),
                        "a socket that has never been used must count as alive "
                        "(tearing it down would wipe the cookie jar)")
        with self.assertRaises(OSError):
            transport.request("Target.getTargets")
        self.assertFalse(transport.alive(),
                         "a socket that just failed still reports itself alive")

    def test_a_graceful_close_marks_the_transport_dead(self):
        """recv() returning b"" is not an empty reply, it is a finished socket.
        json.loads(b"") used to raise a JSONDecodeError, which is not an OSError,
        so the caller could not tell 'peer closed' from 'malformed reply' and the
        transport stayed 'alive'."""
        transport = relay.CdpTransport(ClosedSocket())
        with self.assertRaises(OSError):
            transport.request("Target.getTargets")
        self.assertFalse(transport.alive())

    def test_a_healthy_transport_stays_alive(self):
        transport = relay.CdpTransport(QuietSocket())
        transport.request("Target.getTargets")
        transport.request("Target.getTargets")
        self.assertTrue(transport.alive())

    def test_an_event_storm_does_not_spin_forever(self):
        """Defect 3: skipping unsolicited events had no bound. A page logging to
        the console every millisecond kept the serving thread busy until the
        socket timeout - the request never completed and nothing said why."""
        transport = relay.CdpTransport(EventStormSocket())
        with self.assertRaises((OSError, RuntimeError)):
            transport.request("Target.getTargets")


class EnsureConnectionReopensWhatItMust(unittest.TestCase):
    def _patch_reopen(self):
        reopened = {"count": 0}

        class FakeTransport:
            def __init__(self, sock):
                self.socket = sock
                self.dead = False

            def alive(self):
                return True

        def fake_create(url, **kwargs):
            reopened["count"] += 1
            return FakeTransport(None)

        self.addCleanup(setattr, relay.websocket, "create_connection",
                        relay.websocket.create_connection)
        self.addCleanup(setattr, relay, "attach_page", relay.attach_page)
        relay.websocket.create_connection = fake_create
        relay.attach_page = lambda transport, origin: ("tgt", "sess-new")
        return reopened

    def test_a_dead_socket_is_reopened(self):
        """Defect 1: a transport that proved it is dead must be discarded, not
        reused forever. This is the sequence a user hits when WSL restarts."""
        with _RelayState():
            transport = relay.CdpTransport(DeadSocket())
            _RelayState.install(transport)
            with self.assertRaises(OSError):
                transport.request("Target.getTargets")   # the real failure
            reopened = self._patch_reopen()
            relay._ensure_connection("https://example.com")
            self.assertEqual(reopened["count"], 1,
                             "a dead socket was reused instead of reopened")

    def test_a_healthy_idle_socket_is_preserved(self):
        """The other half, and the reason the guard is 'dead', not 'used': a
        working connection must never be torn down - Lightpanda scopes its cookie
        jar per connection, so dropping it silently logs the user out of every
        session they synced."""
        with _RelayState():
            _RelayState.install(relay.CdpTransport(QuietSocket()))
            before = relay._CDP_TRANSPORT
            reopened = self._patch_reopen()
            relay._ensure_connection("https://example.com")
            self.assertEqual(reopened["count"], 0,
                             "a healthy connection was torn down")
            self.assertIs(relay._CDP_TRANSPORT, before)


class HealthTellsTheTruth(unittest.TestCase):
    def test_health_reports_a_dead_connection_as_not_attached(self):
        """Defect 2: /health derived attached from a flag that is never cleared.
        It answered 200 attached=true while every sync failed."""
        with _RelayState():
            transport = relay.CdpTransport(DeadSocket())
            _RelayState.install(transport)
            with self.assertRaises(OSError):
                transport.request("Target.getTargets")
            status, body = relay.health_payload()
            self.assertEqual(status, 200)
            self.assertFalse(body["attached"],
                             "/health claims attached over a dead socket")

    def test_health_reports_attached_when_the_socket_works(self):
        """The fix must not simply always answer false - that would be a health
        endpoint that lies the other way."""
        with _RelayState():
            _RelayState.install(relay.CdpTransport(QuietSocket()))
            _status, body = relay.health_payload()
            self.assertTrue(body["attached"])

    def test_health_is_sanitized(self):
        """Whatever /health exposes must stay sanitized: no origin, no page URL,
        no cookie name, no token."""
        with _RelayState():
            _RelayState.install(relay.CdpTransport(QuietSocket()))
            _status, body = relay.health_payload()
        blob = json.dumps(body)
        for banned in ("http://", "https://", "cookie", "token", "secret"):
            self.assertNotIn(banned, blob, "/health exposes %r" % banned)


if __name__ == "__main__":
    unittest.main()
