"""Reload the unpacked bridge extension in Comet and *verify* it happened.

Thin wrapper around scripts/cdp_utils.py, which owns the two traps this script
fell into on 2026-09-10:

  * a 33-character extension id - Chrome answers a wrong id with an error page,
    so the script printed `popup ouverte: True` while reloading nothing;
  * `chrome.runtime.reload()` from inside the popup does not refresh the
    manifest (measured: it stayed on 0.5.2 while the extensions page moved it to
    0.5.5 on the first try).

The version is read before and after, so a reload that did not happen fails
loudly instead of printing success.
"""
import sys
import time

import cdp_utils as cdp


def main() -> int:
    ext_id = cdp.extension_id()
    print("extension id: ...%s (%d car, valide)" % (ext_id[-4:], len(ext_id)))
    try:
        ws = cdp.connect()
    except Exception as err:
        print("Comet unreachable on 9223: %s" % err)
        return 2
    try:
        before = cdp.popup_version(ws)
        print("version avant reload: %s" % before)
        if not before:
            print("REFUSED: rien ne repond a cet id, donc un reload serait un no-op.")
            print("         L'extension est-elle toujours chargee ? (chrome://extensions)")
            return 2
        out = cdp.reload_extension(ws)
        print("reload: %s" % out)
        if out != "ok":
            print("FAILED: le rechargement a ete refuse.")
            return 1
    finally:
        ws.close()

    time.sleep(3)
    ws = cdp.connect()
    try:
        after = cdp.popup_version(ws)
    finally:
        ws.close()
    print("version apres reload: %s" % after)
    if not after:
        print("FAILED: le popup n'est pas revenu - recharge l'extension a la main.")
        return 1
    expected = cdp.repo_version()
    if after != expected:
        print("FAILED: le popup sert v%s alors que le depot livre v%s." % (after, expected))
        return 1
    if after != before:
        print("OK: le popup sert maintenant v%s (etait v%s)." % (after, before))
    else:
        print("OK: le popup sert deja v%s, le depot livre la meme version." % after)
    return 0


if __name__ == "__main__":
    sys.exit(main())
