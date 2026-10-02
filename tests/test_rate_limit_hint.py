"""The rate-limit message must state the quota that was actually hit.

The hint used to be a constant: "GitHub API rate limit reached (anonymous is
60/hour per IP)" - raised on EVERY 403/429, including authenticated ones. A user
holding a valid token, which raises the quota from 60/h to 5000/h, was told to
add a token they already had. The real numbers sit in the error's own headers.

Builds real urllib errors with real header objects, so the test drives the
production branch instead of restating it.
"""
import io
import pathlib
import sys
import unittest
import urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "relay"))

import updater  # noqa: E402


def _error(code, headers, body=b"API rate limit exceeded"):
    err = urllib.error.HTTPError(
        "https://api.github.com/x", code, "Forbidden", headers, io.BytesIO(body))
    return err


class RateLimitHintIsTruthful(unittest.TestCase):
    def setUp(self):
        self._real_token = updater.github_token
        updater.github_token = lambda: "t" * 40
        self.addCleanup(lambda: setattr(updater, "github_token", self._real_token))

    def test_authenticated_quota_is_reported_as_authenticated(self):
        err = _error(403, {"X-RateLimit-Limit": "5000", "X-RateLimit-Remaining": "0"})
        msg = str(updater._rate_hint(err))
        self.assertIn("5000", msg, msg)
        self.assertIn("authenticated", msg, msg)
        self.assertNotIn("60/hour", msg,
                         "a 5000/h quota must never be described as 60/hour: "
                         "that sends a token holder to add a token they have")

    def test_anonymous_quota_is_reported_as_anonymous(self):
        updater.github_token = lambda: ""
        err = _error(429, {"X-RateLimit-Limit": "60", "X-RateLimit-Remaining": "0"})
        msg = str(updater._rate_hint(err))
        self.assertIn("anonymous", msg, msg)
        self.assertIn("60", msg, msg)

    def test_missing_headers_do_not_crash_or_invent_a_number(self):
        err = _error(403, {})
        msg = str(updater._rate_hint(err))
        self.assertIn("rate limit", msg.lower())
        self.assertNotIn("None", msg, msg)

    def test_the_raised_error_carries_the_real_hint(self):
        # Drive the production branch: a 403 whose body says "rate limit" must
        # surface the header-derived message, not a constant.
        seen = {}
        real_fetch = updater._fetch

        def fake_fetch(url, limit=None, accept=None):
            seen["url"] = url
            raise _error(403, {"X-RateLimit-Limit": "5000",
                               "X-RateLimit-Remaining": "0"})
        updater._fetch = fake_fetch
        self.addCleanup(lambda: setattr(updater, "_fetch", real_fetch))
        with self.assertRaises(RuntimeError) as ctx:
            updater._fetch_json("https://api.github.com/repos/x/commits/main")
        msg = str(ctx.exception)
        self.assertIn("5000", msg, msg)
        self.assertNotIn("anonymous", msg, msg)


if __name__ == "__main__":
    unittest.main()
