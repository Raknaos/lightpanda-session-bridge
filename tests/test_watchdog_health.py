"""The watchdog must distinguish "relay answers" from "relay works".

Live evidence (2026-10-02 15:54:48): the watchdog log recorded
    relay=False cdp=True -> (re)starting
while a relay was ALREADY running and holding 127.0.0.1:8765. The watchdog
started a second one, and the two processes then held separate copies of the
session state: /health said attached:true sessions:1 while the diagnostics
report built from the other copy said cdp_attached:false synced_origins:0.

The cause was `up(HEALTH)`: any 200 counted as "relay fine". It cannot - the
whole point of v0.6.1 was that a 200 no longer implies a usable CDP connection.

Run: .venv/Scripts/python.exe tests/test_watchdog_health.py
"""
import importlib.util
import json
import pathlib
import sys
import unittest
from unittest import mock

REPO = pathlib.Path(__file__).resolve().parent.parent
WATCHDOG = REPO / "scripts" / "watchdog_relay.pyw"


def load_watchdog():
    spec = importlib.util.spec_from_loader(
        "watchdog_relay", importlib.machinery.SourceFileLoader(
            "watchdog_relay", str(WATCHDOG)))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class WatchdogReadsAttached(unittest.TestCase):
    def setUp(self):
        self.wd = load_watchdog()

    def _health(self, payload):
        return mock.patch.object(self.wd.urllib.request, "urlopen",
                                return_value=FakeResponse(payload))

    def test_a_healthy_relay_passes(self):
        with self._health({"ok": True, "attached": True, "sessions": 1}):
            self.assertTrue(self.wd.relay_healthy())

    def test_a_relay_that_answers_but_is_not_attached_fails(self):
        """The live defect: this used to report True, so the watchdog left a
        broken relay alone - or started a second one."""
        with self._health({"ok": True, "attached": False, "sessions": 0}):
            self.assertFalse(self.wd.relay_healthy(),
                             "a relay answering while NOT attached counts as healthy")

    def test_an_old_relay_without_the_field_still_passes(self):
        """An older relay (before v0.6.1) has no `attached` key. Absence of the
        field is not a failure - otherwise every upgrade would restart the
        relay and, before the exclusive-bind fix, spawn a second one."""
        with self._health({"ok": True, "service": "lightpanda-session-bridge"}):
            self.assertTrue(self.wd.relay_healthy())

    def test_a_non_200_fails(self):
        with self._health({"ok": False}):
            self.wd  # keep the name used
        with mock.patch.object(self.wd.urllib.request, "urlopen",
                               return_value=FakeResponse({"ok": False}, status=503)):
            self.assertFalse(self.wd.relay_healthy())

    def test_a_connection_error_fails(self):
        with mock.patch.object(self.wd.urllib.request, "urlopen",
                               side_effect=OSError("refused")):
            self.assertFalse(self.wd.relay_healthy())

    def test_garbage_body_fails_instead_of_crashing(self):
        """A relay that returns HTML (a captive portal, a proxy) must not take
        the watchdog down with a JSONDecodeError."""
        class Html:
            status = 200

            def read(self):
                return b"<html>not json</html>"

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False
        with mock.patch.object(self.wd.urllib.request, "urlopen",
                               return_value=Html()):
            self.assertFalse(self.wd.relay_healthy())


class WatchdogDoesNotFightALiveRelay(unittest.TestCase):
    def setUp(self):
        self.wd = load_watchdog()

    def test_main_starts_nothing_when_relay_and_cdp_are_both_up(self):
        with mock.patch.object(self.wd, "relay_healthy", return_value=True), \
             mock.patch.object(self.wd, "up", return_value=True), \
             mock.patch.object(self.wd, "start_daemon_task") as start:
            self.wd.main()
        start.assert_not_called()

    def test_main_does_nothing_when_only_the_cdp_is_down(self):
        """Lightpanda off, relay fine: restarting the relay cannot help and used
        to race the running instance. The relay connects on demand, so a dead
        CDP is not a relay fault."""
        with mock.patch.object(self.wd, "relay_healthy", return_value=True), \
             mock.patch.object(self.wd, "up", return_value=False), \
             mock.patch.object(self.wd, "start_daemon_task") as start:
            self.wd.main()
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
