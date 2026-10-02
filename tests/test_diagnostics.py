"""The support report must be safe to paste in a public issue.

These tests are the guarantee. A diagnostic that leaks the thing it is
diagnosing is worse than no diagnostic, so each one plants a realistic secret
and then searches the whole rendered report for it.
"""
import json
import os
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from relay import diagnostics  # noqa: E402


# Values that must never appear in a rendered report, in any form.
FAKE_COOKIE = "ghp_FAKEfakeFAKE1a2B3c4D5e6F7g8H9i0J"
FAKE_LS = "eyJhbGciOiJIUzI1NiJ9.ZmFrZS1sb2NhbC1zdG9yYWdlLXZhbHVl"
FAKE_URL = "https://github.com/someone/private-account-xyz"
FAKE_SECRET = "s3cr3t-TOKEN-value-Zz9"


class ReportIsSanitized(unittest.TestCase):
    def test_report_builds_without_a_live_session(self):
        report = diagnostics.collect()
        self.assertEqual(report["schema"], 1)
        # The fields that explain a failed sync must be PRESENT, not scrubbed.
        for key in ("storage_expected", "storage_applied", "last_sync_cookies",
                    "cdp_attached", "synced_origins"):
            self.assertIn(key, report["state"])

    def test_product_fields_survive(self):
        """Regression: a too-broad scrubber blanked the product name, the
        timestamps and the file fingerprints - the fields the report is for."""
        report = diagnostics.collect()
        self.assertEqual(report["product"]["name"], "lightpanda-session-bridge")
        self.assertTrue(report["generated_at"])
        self.assertIn("sha256:", report["artifacts"]["manifest"])
        # CI contradiction, fixed: on a runner there is no installed commit and
        # check_update returns None for it, so the report said deployed_commit
        # = None (str(None)[:12]) and this assertion failed on GitHub while
        # passing here. Either a hex sha or the honest "unknown".
        self.assertRegex(report["product"]["deployed_commit"], r"^([0-9a-f]{7,12}|unknown)$")

    def test_missing_deployment_reports_unknown_not_none(self):
        """A fresh checkout / CI runner has no .build-info.json. The report must
        say "unknown", never the string "None" and never a crash."""
        import relay.updater as updater
        saved = updater.check_update
        updater.check_update = lambda: {"current_version": None, "current_commit": None}
        try:
            self.assertEqual(diagnostics._deployed_commit(), "unknown")
            self.assertEqual(diagnostics._deployed_version(), "unknown")
            self.assertEqual(diagnostics.collect()["product"]["deployed_commit"], "unknown")
        finally:
            updater.check_update = saved

    def test_text_form_contains_no_planted_secret(self):
        blob = json.dumps(diagnostics.collect(), ensure_ascii=False)
        text = diagnostics.to_text(diagnostics.collect())
        for label, secret in (("cookie", FAKE_COOKIE), ("localStorage", FAKE_LS),
                              ("url", FAKE_URL), ("token", FAKE_SECRET)):
            self.assertNotIn(secret, blob, "%s leaked into the json report" % label)
            self.assertNotIn(secret, text, "%s leaked into the text report" % label)

    def test_scrubber_redacts_credentials_but_keeps_metadata(self):
        # a credential under a credential-named key disappears entirely
        self.assertEqual(diagnostics.scrub({"value": FAKE_COOKIE}), {})
        self.assertNotIn(FAKE_SECRET, json.dumps(diagnostics.scrub({"api_key": FAKE_SECRET})))
        # metadata that must survive: versions, shas, counts, plain names
        self.assertEqual(diagnostics.scrub("0.5.8"), "0.5.8")
        self.assertEqual(diagnostics.scrub("900 B sha256:ae35d3da97e6"),
                         "900 B sha256:ae35d3da97e6")
        self.assertEqual(diagnostics.scrub({"lightpanda-session-bridge": 1}),
                         {"lightpanda-session-bridge": 1})
        self.assertEqual(diagnostics.scrub(FAKE_URL), diagnostics.REDACTED)

    def test_timestamps_and_fingerprints_are_not_secrets(self):
        """Regression, caught on the real relay: the audit writer emits ISO
        timestamps, which the entropy rule blanked ("at = [redacted]"), so the
        report lost WHEN each install happened - the ordering a support
        conversation needs."""
        for value in ("2026-09-14T18:15:40+0200", "2026-10-02T13:46:58+0200"):
            self.assertEqual(diagnostics.scrub(value), value)
        self.assertEqual(diagnostics.scrub("900 B sha256:ae35d3da97e6"),
                         "900 B sha256:ae35d3da97e6")
        # ... while a real credential of the same shape still goes
        for secret in (FAKE_COOKIE, FAKE_LS, FAKE_SECRET, FAKE_URL):
            self.assertNotEqual(diagnostics.scrub(secret), secret,
                                "%s must stay scrubbed" % secret[:12])

    def test_install_log_is_scrubbed_but_counted(self):
        """The log is the only foreign data in the report: it must be
        scrubbed, while a clean line survives."""
        lines = diagnostics.scrub([
            {"event": "install", "version": "0.5.8", "sha256": FAKE_SECRET},
            {"event": "install", "version": "0.5.7", "commit": "abc1234"},
        ])
        rendered = json.dumps(lines)
        self.assertNotIn(FAKE_SECRET, rendered)
        self.assertIn("0.5.7", rendered)

    def test_report_survives_a_broken_relay(self):
        """The report must be producible when the thing it reports is broken."""
        import relay.server as relay
        saved = (relay._CDP_TRANSPORT, relay._CDP_SESSION_ID, relay._LAST_SESSION)
        class Boom:
            def request(self, *a, **k):
                raise OSError(10053, "aborted")
            @property
            def connected(self):
                raise OSError("nope")
        relay._CDP_TRANSPORT = Boom()
        relay._CDP_SESSION_ID = "sess"
        relay._LAST_SESSION = {"origin": "https://x.com", "cookies": [{"value": FAKE_COOKIE}]}
        try:
            report = diagnostics.collect()
            self.assertIn("state", report)
            self.assertEqual(report["state"]["last_sync_cookies"], 1)
            self.assertNotIn(FAKE_COOKIE, json.dumps(report))
        finally:
            relay._CDP_TRANSPORT, relay._CDP_SESSION_ID, relay._LAST_SESSION = saved


class ImportContext(unittest.TestCase):
    """The relay is not a package. `relay/server.py` runs with `relay/` as its
    import root (flat `import updater`), while the test suite imports the
    package from the repo root (`from relay import updater`). A module reachable
    only one way passes every unit test and 500s in the live process - which is
    exactly what happened to /v1/diagnostics: `from relay import diagnostics`
    raised ModuleNotFoundError on the running relay while 133 tests were green.
    """

    def test_works_from_the_repo_root(self):
        r = subprocess.run([sys.executable, "-c",
                            "import sys; sys.path.insert(0, %r);\n"
                            "from relay import diagnostics;\n"
                            "print(diagnostics.collect()['schema'])" % str(ROOT)],
                           cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")

    def test_works_from_inside_the_relay_directory(self):
        """The live process's own cwd and import root."""
        r = subprocess.run([sys.executable, "-c",
                            "import diagnostics;\n"
                            "print(diagnostics.collect()['schema'])"],
                           cwd=str(ROOT / "relay"), capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")

    def test_main_is_used_when_it_really_is_the_relay(self):
        """THE THIRD TRAP, and the one that bit live.

        `relay/server.py` runs as the entry point, so its module is registered
        under ``__main__`` and ``sys.modules`` holds NO ``server`` key at all.
        ``_sibling("server")`` therefore imported a SECOND copy of server.py and
        the report read that copy's globals - always empty.

        Measured live on 2026-10-02: ``/health`` answered ``attached: true,
        sessions: 1`` while the very same ``/v1/diagnostics`` answered
        ``cdp_attached: false, synced_origins: 0, cdp_transport: "NoneType"``.
        The support report - the one artefact a user pastes into a bug report -
        was describing a module that never ran.
        """
        daemon = type(sys)("__main__")
        daemon.__file__ = str(ROOT / "relay" / "server.py")
        saved_main = sys.modules.get("__main__")
        saved_server = sys.modules.pop("server", None)
        saved_dotted = sys.modules.pop("relay.server", None)
        sys.modules["__main__"] = daemon
        try:
            found = diagnostics._sibling("server")
            self.assertIs(found, daemon,
                         "the live daemon's __main__ module was not reused: the "
                         "report reads a fresh, empty copy of server.py")
        finally:
            if saved_main is not None:
                sys.modules["__main__"] = saved_main
            for key, val in (("server", saved_server),
                             ("relay.server", saved_dotted)):
                if val is None:
                    sys.modules.pop(key, None)
                else:
                    sys.modules[key] = val

    def test_a_test_runner_as_main_does_not_hijack_the_lookup(self):
        """The flip side: under `python -m unittest`, __main__ is the runner.
        Trusting the NAME alone would make the report read the runner's globals
        instead of the relay's - a bug that only appears in CI."""
        sentinel = type(sys)("pretend_main")
        sentinel.__file__ = str(ROOT / "tests" / "test_diagnostics.py")
        saved = sys.modules.get("__main__")
        sys.modules["__main__"] = sentinel
        try:
            found = diagnostics._sibling("server")
            self.assertIsNot(found, sentinel,
                             "__main__ was returned even though it is not server.py")
        finally:
            if saved is not None:
                sys.modules["__main__"] = saved

    def test_sibling_import_returns_the_module_not_the_package(self):
        """__import__("updater") returns the TOP package when relay is a
        package, so updater.extension_dir raised AttributeError."""
        mod = diagnostics._sibling("updater")
        self.assertTrue(hasattr(mod, "extension_dir"),
                        "_sibling returned %r, not the updater module" % (mod,))


class Fingerprint(unittest.TestCase):
    def test_absent_empty_and_present(self):
        self.assertEqual(diagnostics._fingerprint(""), "unset")
        self.assertEqual(diagnostics._fingerprint(str(ROOT / "nope.json")), "absent")
        got = diagnostics._fingerprint(str(ROOT / "extension" / "manifest.json"))
        self.assertIn(" B sha256:", got)

    def test_listing_hides_credential_file_names(self):
        listing = diagnostics._listing(str(ROOT / "extension"))
        self.assertNotIn("secret", json.dumps(listing).lower())


if __name__ == "__main__":
    unittest.main()
