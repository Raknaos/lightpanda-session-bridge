"""Every per-route deadline must stay inside the class deadline.

`Handler.timeout` (15s) is the backstop: a socket that sends nothing is released
by StreamRequestHandler.setup(). A route may narrow it (10s body reads), but a
route that WIDENS it reopens the hole the class deadline closed - one client can
then hold a thread for as long as that route allows.

`/v1/cdp` legitimately widens to 30s: it is the only route that makes the relay
talk to Lightpanda (navigate + settle + four injection rounds). So the invariant
is not "every route is narrower" but "every route is BOUNDED, and the widest one
is named here deliberately" - a new `settimeout(600)` fails instead of quietly
becoming the new worst case.

Reads the real constants out of the source; it does not retype them.
"""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "relay" / "server.py"

# The one route allowed to exceed the class deadline, with the reason.
DELIBERATE_WIDER = {"/v1/cdp": 30}


class PerRouteDeadlineBound(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = SERVER.read_text(encoding="utf-8")
        m = re.search(r"^    timeout = (\d+)", cls.src, re.M)
        assert m, "aucun timeout de classe sur Handler: le backstop a disparu"
        cls.class_deadline = int(m.group(1))
        cls.routes = {}
        # Count only REAL calls at the start of a statement, never a mention in
        # prose: the explanation above the class deadline literally reads "The
        # settimeout(10) inside do_GET was already too late", and a naive match
        # reported that sentence as an unrouteable call site.
        for m in re.finditer(r'^[ \t]*(?:self\.connection\.)?settimeout\((\d+)\)',
                             cls.src, re.M):
            line = cls.src[: m.start()].count("\n") + 1
            hits = re.findall(r'(?:el)?if self\.path == "([^"]+)"', cls.src[: m.start()])
            route = hits[-1] if hits else "(avant dispatch)"
            # A settimeout more than 60 lines after its branch header belongs to
            # no branch: do not attribute it silently.
            if hits:
                header = cls.src.rfind(f'if self.path == "{hits[-1]}"', 0, m.start())
                if line - (cls.src[:header].count("\n") + 1) > 60:
                    route = "(hors route)"
            cls.routes.setdefault(route, []).append((line, int(m.group(1))))

    def test_no_route_can_widen_the_deadline_without_being_declared(self):
        undeclared = []
        for route, entries in self.routes.items():
            allowed = DELIBERATE_WIDER.get(route, self.class_deadline)
            for line, value in entries:
                if value > allowed:
                    undeclared.append(f"{route} l.{line}={value}s (> {allowed}s)")
        self.assertEqual(
            undeclared, [],
            "un delai par route depasse la borne declaree: " + "; ".join(undeclared))

    def test_the_deliberate_wider_route_still_exists_and_is_bounded(self):
        # If /v1/cdp were renamed or removed, the exemption would silently cover
        # nothing while the check above still passes.
        found = self.routes.get("/v1/cdp")
        self.assertTrue(found, "/v1/cdp n'existe plus: l'exemption ne couvre plus rien")
        self.assertEqual(found[0][1], DELIBERATE_WIDER["/v1/cdp"])
        self.assertLessEqual(
            found[0][1], 60,
            "le delai de /v1/cdp a derive: 30s etait mesure, pas 30s+")

    def test_every_widening_call_site_is_accounted_for(self):
        # A settimeout outside any `if path ==` branch cannot be attributed to a
        # route, so it escapes the audit above - unless it also happens to be
        # NARROWER than the class deadline, in which case it widens nothing and
        # needs no exemption (the pre-dispatch `settimeout(10)` in do_GET is the
        # legitimate case).
        offenders = []
        for route, entries in self.routes.items():
            if route not in ("(hors route)", "(avant dispatch)"):
                continue
            for line, value in entries:
                if value > self.class_deadline:
                    offenders.append(f"{route} l.{line}={value}s")
        self.assertEqual(
            offenders, [],
            "settimeout elargissant hors route declaree: " + "; ".join(offenders))

    def test_no_unrouteable_widening_call_is_silently_ignored(self):
        # The complement: whatever the attribution, every widening value in the
        # file must be justified by DELIBERATE_WIDER. Catches a new 600s read on
        # an unnamed path no matter where the attribution logic puts it.
        widening = [int(v) for v in re.findall(r'^[ \t]*(?:self\.connection\.)?settimeout\((\d+)\)',
                                              self.src, re.M)]
        widest = max(widening) if widening else 0
        self.assertLessEqual(
            widest, max([self.class_deadline] + list(DELIBERATE_WIDER.values())),
            f"settimeout le plus large = {widest}s, hors bornes declarees")

    def test_the_class_deadline_is_still_present_and_sane(self):
        # Guards against the backstop being removed or grown into uselessness.
        self.assertGreaterEqual(self.class_deadline, 5)
        self.assertLessEqual(
            self.class_deadline, 60,
            f"Handler.timeout={self.class_deadline}s: le thread muet tient trop longtemps")


if __name__ == "__main__":
    unittest.main()
