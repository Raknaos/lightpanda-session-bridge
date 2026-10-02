# -*- coding: utf-8 -*-
"""The DNS verdict cache is bounded.

`_DNS_CACHE` had a TTL, but the TTL only decided when an entry was STALE. Nothing
ever removed it, so the dict grew for the lifetime of the relay - one entry per
distinct hostname ever submitted. A single site minting unique subdomains (asset
hosts, tracking domains, cache busters) grows it without bound.
"""
import pathlib
import sys
import time
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "relay"))

import server  # noqa: E402


class DnsCacheIsBounded(unittest.TestCase):
    """Drive the REAL check, not the helper.

    An earlier version of this file called `_dns_cache_put` directly, so it
    stayed green even when the production call sites were reverted to the raw
    dict assignment. The tests must go through the same path a request takes.
    """

    def setUp(self):
        self._saved = dict(server._DNS_CACHE)
        server._DNS_CACHE.clear()
        real = server.socket.getaddrinfo

        def refusing(*a, **k):
            # every host resolves to a public address: the verdict is cached, so
            # we exercise the write path without touching the network semantics
            return real("github.com", None) if a[0] == "github.com" else [
                (2, 1, 6, "", ("93.184.216.34", 0))]

        server.socket.getaddrinfo = refusing
        self.addCleanup(self._restore)
        self.addCleanup(setattr, server.socket, "getaddrinfo", real)

    def _restore(self):
        server._DNS_CACHE.clear()
        server._DNS_CACHE.update(self._saved)

    def _feed(self, n):
        """Submit n distinct hostnames through the real validation path."""
        for i in range(n):
            server.valid_origin("https://host-%d.example" % i)

    def test_cache_never_exceeds_the_cap(self):
        self._feed(server._DNS_CACHE_MAX * 3)
        self.assertLessEqual(
            len(server._DNS_CACHE), server._DNS_CACHE_MAX,
            "le cache DNS depasse son plafond : %d entrees pour un plafond de %d"
            % (len(server._DNS_CACHE), server._DNS_CACHE_MAX))

    def test_the_cap_is_a_real_number(self):
        self.assertGreater(server._DNS_CACHE_MAX, 0)
        self.assertLessEqual(server._DNS_CACHE_MAX, 10000,
                             "un plafond de 10k n'est pas un plafond")

    def test_stale_entries_are_dropped_on_write(self):
        old = time.time() - server._DNS_CACHE_TTL * 10
        for n in range(50):
            server._DNS_CACHE["stale-%d.example" % n] = (old, True)
        server.valid_origin("https://fresh.example")
        self.assertLessEqual(len(server._DNS_CACHE), 2,
                             "les entrees perimees n'ont pas ete purgees : %d"
                             % len(server._DNS_CACHE))

    def test_a_cached_verdict_is_still_returned(self):
        """The cache must still work - this is not 'always recompute'."""
        calls = []

        def counting(host, *a, **k):
            calls.append(host)
            return [(2, 1, 6, "", ("93.184.216.34", 0))]

        server.socket.getaddrinfo = counting
        first = server.valid_origin("https://example.com")
        second = server.valid_origin("https://example.com")
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1,
                         "le verdict DNS n'a pas ete reutilise : resolu %d fois"
                         % len(calls))

    def test_public_hostname_is_accepted(self):
        """Guard against a cap that quietly breaks legitimate origins."""
        self.assertTrue(server.valid_origin("https://github.com"))

    def test_private_hostname_is_still_refused(self):
        self.assertFalse(server.valid_origin("http://192.168.1.10"))
        self.assertFalse(server.valid_origin("http://localhost"))
        self.assertFalse(server.valid_origin("http://box.internal"))


if __name__ == "__main__":
    unittest.main()
