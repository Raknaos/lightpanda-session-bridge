"""Verify the running Comet extension serves the released code.

Answers one question: does the extension that Comet has loaded match the tree
this repository ships? It prints the served version, the version the repo ships,
and whether the served `popup.js` contains the markers of the current code.

Two bugs made this script lie, both fixed by routing everything through
scripts/cdp_utils.py:

  * EXT_ID was hardcoded with 33 characters, so it verified an error page and
    reported `chrome-error://chromewebdata/` (which was then worked around
    instead of fixed);
  * the expected version was hardcoded to "0.4.3", so from v0.4.4 onwards a
    correct extension was reported as broken.

Exit codes: 0 = serving the repo version, 1 = serving something else,
2 = the extension does not answer at all.

Never prints a cookie, a token or any page content.
"""
import sys
import time

import cdp_utils as cdp

MARKERS = [
    "errPartialStorage",           # v0.4.3: partial transfer is a loud failure
    "errStorageExtract",           # v0.4.3: extraction failure is not swallowed
    "updateChipNew",               # v0.5.4: the chip says the state
    "sessionsClearShort",          # v0.5.4: compact pill in the card header
]


def main() -> int:
    expected = cdp.repo_version()
    ext_id = cdp.extension_id()
    print("depot livre: v%s | extension id: ...%s (%d car)" % (expected, ext_id[-4:], len(ext_id)))
    try:
        ws = cdp.connect()
    except Exception as err:
        print("extension introuvable: Comet ne repond pas sur 9223 (%s)" % err)
        return 2
    try:
        served = cdp.popup_version(ws)
        print("version servie: %s" % served)
        if not served:
            print("L'extension ne repond pas a cet id: mauvaise cible ou extension dechargee.")
            return 2

        target, sid = cdp.open_page(ws, cdp.popup_url(ext_id))
        for _ in range(10):
            if cdp.evaluate(ws, sid, "typeof chrome !== 'undefined' && !!chrome.runtime"):
                break
            time.sleep(0.5)
        code = cdp.evaluate(
            ws, sid,
            "fetch(chrome.runtime.getURL('popup.js')).then(r => r.text())"
            ".then(t => %s.map(k => k + '=' + t.includes(k)).join(' '))" % MARKERS,
            await_promise=True)
        cdp.close_page(ws, target)
    finally:
        ws.close()

    print("marqueurs du code servi: %s" % code)
    missing = [pair for pair in (code or "").split() if pair.endswith("=false")]
    if served != expected:
        print("FAILED: Comet sert v%s, le depot livre v%s - lance scripts/reload_extension.py."
              % (served, expected))
        return 1
    if missing:
        print("FAILED: le popup servi vient d'un autre code, marqueurs absents: %s"
              % ", ".join(m.split("=")[0] for m in missing))
        return 1
    print("OK: Comet sert v%s, code du depot, %d marqueurs presents." % (served, len(MARKERS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
