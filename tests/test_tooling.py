# -*- coding: utf-8 -*-
"""Tests for the tooling seams: decoding, ids, and the scripts that verify.

These are the failures that unit tests of the product never saw - a Windows CLI
whose output is not UTF-8, and an extension id copy-pasted with a typo. Both
were found in production, so both get a guard.
"""
import pathlib
import re
import subprocess
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bridge  # noqa: E402
import cdp_utils  # noqa: E402


class CliDecodingTests(unittest.TestCase):
    """`text=True` means utf-8, and Windows CLIs do not speak utf-8."""

    def test_utf16le_output_is_decoded(self):
        # what `wsl.exe -l -q` really writes
        raw = "Ubuntu\n".encode("utf-16-le")
        self.assertEqual(bridge._cli_text(raw).strip(), "Ubuntu")

    def test_utf8_output_is_decoded(self):
        self.assertEqual(bridge._cli_text("Docker Desktop\n".encode("utf-8")).strip(),
                         "Docker Desktop")

    def test_cp850_bytes_never_raise(self):
        # netstat on a French Windows: 0x90 is not valid utf-8
        self.assertTrue(bridge._cli_text(b"TCP    0.0.0.0:8765    \x90\x91 LISTENING"))

    def test_empty_and_none_are_empty(self):
        self.assertEqual(bridge._cli_text(b""), "")
        self.assertEqual(bridge._cli_text(None), "")

    def test_no_windows_cli_is_read_with_text_true(self):
        """The static half: `subprocess.run(..., text=True)` on a Windows tool is
        the bug, so no script may do it."""
        offenders = []
        for path in list(REPO_ROOT.rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel.startswith((".venv/", "neo-upstream/")) or rel.startswith("tests/"):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for num, line in enumerate(text.splitlines(), 1):
                if "subprocess" not in line and "wsl.exe" not in line and "netstat" not in line:
                    continue
                if "text=True" in line and ("wsl" in line or "netstat" in line or "tasklist" in line
                                            or "schtasks" in line):
                    offenders.append("%s:%d" % (rel, num))
        self.assertEqual(offenders, [], "Windows CLI read as utf-8: %s" % offenders)


class ExtensionIdTests(unittest.TestCase):
    """A 33-character id opens an error page, and Chrome says nothing about it."""

    def test_the_real_pin_is_valid(self):
        self.assertRegex(cdp_utils.extension_id(), r"^[a-p]{32}$")

    def test_a_wrong_length_or_alphabet_id_is_refused(self):
        """Lengths are computed, never typed: counting 32 characters by eye is
        precisely how the 33-character id got in."""
        pin = cdp_utils.extension_id()
        samples = {
            "31 car": pin[:31],
            "33 car": pin + "a",
            "alphabet hors a-p": "z" + pin[1:],
            "vide": "",
        }
        for label, candidate in samples.items():
            self.assertIsNone(cdp_utils.ID_RE.match(candidate), "%s accepte" % label)
        self.assertIsNotNone(cdp_utils.ID_RE.match(pin))

    def test_the_scripts_do_not_carry_their_own_id(self):
        """The copy-paste is what broke: every script must go through cdp_utils."""
        for name in ("reload_extension.py", "verify_extension.py"):
            text = (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")
            # the shared fallback constant lives in cdp_utils only
            self.assertNotRegex(text, r"\b[a-p]{31,36}\b", "%s porte un id en dur" % name)
            self.assertIn("cdp_utils", text)

    def test_expected_version_is_never_hardcoded(self):
        """verify_extension.py asserted "0.4.3" for twelve versions, so a correct
        extension was reported broken. It must read the repo manifest."""
        text = (REPO_ROOT / "scripts" / "verify_extension.py").read_text(encoding="utf-8")
        self.assertIn("repo_version()", text)
        self.assertNotRegex(text, r'version ==\s*"0\.\d+\.\d+"')


class AcceptanceScriptTests(unittest.TestCase):
    def test_the_gate_exists_and_declares_its_checks(self):
        text = (REPO_ROOT / "scripts" / "acceptance.py").read_text(encoding="utf-8")
        for named in ("versions agree everywhere", "every language has the same strings",
                      "the popup still fits", "no extension id differs from the pin",
                      "the shared secret is absent", "every element popup.js touches exists"):
            self.assertIn(named, text)
        self.assertIn("READY", text)

    def test_ci_runs_the_gate(self):
        ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        self.assertIn("scripts/acceptance.py --local", ci)


if __name__ == "__main__":
    unittest.main(verbosity=2)
