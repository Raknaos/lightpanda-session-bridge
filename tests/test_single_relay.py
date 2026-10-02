"""Two relays must never be able to hold the same port on Windows.

Observed live (2026-10-02, 15:54:48): TWO relay processes started in the same
second - the watchdog and the scheduled task both launched one. Only one held
127.0.0.1:8765, so the requests were served by whichever won the bind, and the
other process kept a separate copy of the state in its own memory:

  GET /health           -> {"attached": true,  "sessions": 1}
  GET /v1/diagnostics   -> {"cdp_attached": false, "synced_origins": 0,
                           "cdp_transport": "NoneType"}

Same instant, same port, opposite answers - and a support report built from the
wrong copy tells the user their session does not exist while the agent is using
it.

``allow_reuse_address = False`` alone is NOT enough on Windows: it clears
SO_REUSEADDR, which stops a rebind *after close* but does not stop a second
process binding an already-listening socket. Only SO_EXCLUSIVEADDRUSE does that.
"""
import os
import pathlib
import socket
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "relay"))

import server as relay  # noqa: E402


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class OnlyOneRelayCanHoldThePort(unittest.TestCase):
    def test_the_port_is_bound_exclusively(self):
        """The live defect: a second relay could bind an already-listening
        socket, so the state was split across two processes and /health and
        /v1/diagnostics contradicted each other."""
        port = free_port()
        first = relay.RelayServer(("127.0.0.1", port), relay.Handler)
        self.addCleanup(first.server_close)
        # Same options the daemon uses - if exclusivity is not enforced, this
        # second bind SUCCEEDS and the defect is present.
        second = None
        try:
            second = relay.RelayServer(("127.0.0.1", port), relay.Handler)
        except OSError:
            return   # refused, as it must be
        second.server_close()
        self.fail(
            "a SECOND RelayServer bound port %d already held by the first: "
            "two relays would each keep their own copy of the session "
            "state" % port)

    def test_exclusive_address_use_is_set_on_windows(self):
        """SO_EXCLUSIVEADDRUSE is the flag that actually forbids a second
        binder on Windows; allow_reuse_address only controls SO_REUSEADDR."""
        if os.name != "nt":
            self.skipTest("Windows-specific flag")
        self.assertFalse(relay.RelayServer.allow_reuse_address,
                         "allow_reuse_address must stay False")
        self.assertTrue(getattr(relay.RelayServer, "_exclusive_address_use", False),
                        "RelayServer does not request SO_EXCLUSIVEADDRUSE, so a "
                        "second relay can still bind the port on Windows")

    def test_a_failed_bind_exits_cleanly(self):
        """The daemon exits 0 when the port is taken, so the scheduled task and
        the watchdog do not treat a duplicate start as a crash."""
        port = free_port()
        first = relay.RelayServer(("127.0.0.1", port), relay.Handler)
        self.addCleanup(first.server_close)
        try:
            second = relay.RelayServer(("127.0.0.1", port), relay.Handler)
        except OSError as err:
            # main() turns this into "exit 0, a relay already serves this port".
            self.assertIn(getattr(err, "winerror", None), (None, 10048, 10013),
                          "unexpected OSError: %s" % err)
        else:
            second.server_close()
            self.fail("the second bind was not refused")


class HealthSurvivesAForeignTransportObject(unittest.TestCase):
    def test_health_does_not_raise_on_a_transport_without_alive(self):
        """Found while chasing the split-state bug: health_payload() called
        transport.alive() directly, so any transport object without that method
        raised AttributeError - and do_GET has no try around it, so the HTTP
        thread died instead of answering. _ensure_connection already tolerates
        such an object via a getattr fallback; health must too."""
        class Bare:
            socket = None

        saved = (relay._CDP_TRANSPORT, relay._CDP_SESSION_ID)
        relay._CDP_TRANSPORT = Bare()
        relay._CDP_SESSION_ID = "sess"
        try:
            status, body = relay.health_payload()
        except AttributeError as err:
            self.fail("health_payload() raised on a transport without alive(): %s" % err)
        finally:
            relay._CDP_TRANSPORT, relay._CDP_SESSION_ID = saved
        self.assertEqual(status, 200)
        # A transport we know nothing about is not evidence of death, but it is
        # not proof of life either: say "not attached" rather than guess.
        self.assertIn("attached", body)


if __name__ == "__main__":
    unittest.main()
