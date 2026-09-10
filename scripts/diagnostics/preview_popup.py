# -*- coding: utf-8 -*-
"""Render the popup in headless Chrome and measure it - no live browser needed.

Chrome caps an extension popup at 600x800 px. Anything taller is clipped or
scrolled, and a control that ends up under the fold is a control the user
cannot click. That failure is invisible in unit tests and in a diff, so this
tool renders the real popup.html against a stubbed `chrome` API, measures the
height of every block in the shell, and fails (exit 1) when the DEFAULT state
does not fit.

    python scripts/diagnostics/preview_popup.py                 # measure + screenshot
    python scripts/diagnostics/preview_popup.py --state expanded
    python scripts/diagnostics/preview_popup.py --no-shot
    python scripts/diagnostics/preview_popup.py --cap 620

Screenshots land in %LOCALAPPDATA%\\Temp\\lp_preview\\ (never in the repo).
The harness file is created inside extension/ so that the relative
`<script src="popup.js">` resolves, and is deleted on the way out.
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
EXT_DIR = REPO_ROOT / "extension"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]

SESSIONS = """const _sessions = [
  { origin:'https://x.com', host:'x.com', cookie_count:7, expires:(Date.now()/1000)+86400*5, expired:false },
  { origin:'https://a6api.com', host:'a6api.com', cookie_count:3, expires:(Date.now()/1000)+3600*7, expired:false }
];"""

UPDATE = {
    # state name -> (update_available, source, commit) ; None = relay unreachable
    "available": ("true", "main", "a478b90", "d1efe8c"),
    "release":   ("true", "release", "a478b90", "d1efe8c"),
    "uptodate":  ("false", "main", "a478b90", "a478b90"),
    "offline":   None,
}

STUB = """<script>
// ---- preview harness: never shipped, deleted after the run ----
localStorage.setItem('lightpanda-lang', '__LANG__');
__SESSIONS__
const _upd = __UPD__;
const J = (o) => Promise.resolve({ ok:true, status:200, json:() => Promise.resolve(o) });
window.fetch = (u) => { u = String(u);
  if (u.includes('/health')) return J(__HEALTH__);
  if (u.includes('/v1/sessions')) return J({ ok:true, sessions:_sessions });
  if (u.includes('/v1/update/check')) return _upd === null
      ? Promise.resolve({ ok:false, status:503, json:() => Promise.resolve({}) }) : J(_upd);
  return J({ ok:true }); };
window.chrome = {
  runtime: { getManifest: () => ({ version:'__VERSION__' }), reload: () => {},
             onMessage: { addListener: () => {} }, sendMessage: () => Promise.resolve({}) },
  storage: { local: { get: (d,f) => { f && f({}); return Promise.resolve({}); },
                      set: (d,f) => { f && f(); return Promise.resolve(); } } },
  tabs: { query: (q,f) => { const t=[{ id:1, url:'__TAB__' }]; f && f(t); return Promise.resolve(t); } },
  permissions: { contains: (p,f) => { f && f(true); return Promise.resolve(true); } },
  cookies: { getAll: (d,f) => { f && f([]); return Promise.resolve([]); } },
  scripting: { executeScript: (o,f) => { const r=[{ result:{ cookies:0, storage:7 } }]; f && f(r); return Promise.resolve(r); } },
  alarms: { create: () => {}, onAlarm: { addListener: () => {} } }
};
__CLICK__
</script>
"""

MEASURE = """<script>
setTimeout(() => {
  const body = document.body, shell = document.querySelector('.app-shell');
  const open = document.querySelector('#sessions-card').classList.contains('open');
  body.style.maxHeight = 'none'; body.style.overflow = 'visible';
  const rows = [...document.querySelectorAll('.app-shell > *')]
    .map(el => (el.id || el.className.split(' ')[0]) + '=' + Math.round(el.getBoundingClientRect().height));
  const natural = Math.round(shell.getBoundingClientRect().height);
  if (open) { document.querySelector('#sessions-card').classList.remove('open');
              document.title = 'C-EXPANDED=' + natural + '/' + body.scrollHeight
                + '|C-COLLAPSED=' + Math.round(shell.getBoundingClientRect().height)
                + '|C-ROWS=' + rows.join(', '); }
  else      { document.title = 'C-COLLAPSED=' + natural
                + '|C-ROWS=' + rows.join(', '); }
}, 900);
</script>"""


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    found = shutil.which("chrome") or shutil.which("chromium") or shutil.which("msedge")
    if found:
        return found
    sys.exit("no Chrome/Chromium/Edge binary found")


def build_harness(state):
    html = (EXT_DIR / "popup.html").read_text(encoding="utf-8")
    if state == "offline":
        upd = "null"
    else:
        upd = ("{ ok:true, update_available:%s, source:'%s', latest_commit:'%s0deadbeef0123456789abcdef01234567',"
               " current_commit:'%s0000000000000000000000000000000000aa', latest_version:'0.5.9', backup_available:true }"
               % UPDATE[state if state != "expanded" else "available"])
    click = ("setTimeout(() => { const t = document.querySelector('#sessions-toggle');"
             " if (t) t.click(); }, 250);" if state == "expanded" else "")
    stub = (STUB.replace("__LANG__", "fr").replace("__UPD__", upd)
                .replace("__SESSIONS__", SESSIONS)
                .replace("__CLICK__", click)
                .replace("__HEALTH__", "null" if state == "offline" else "{ ok:true, version:'0.5.9' }")
                .replace("__VERSION__", "0.5.4").replace("__TAB__", "https://x.com/home"))
    out = html.replace('  <script src="popup.js"></script>',
                       stub + '  <script src="popup.js"></script>', 1)
    if "preview harness" not in out:
        sys.exit("could not inject the harness: popup.html changed shape")
    return out


def run(chrome, url, extra=()):
    cmd = [chrome, "--headless=new", "--disable-gpu", "--no-first-run",
           "--hide-scrollbars", "--window-size=430,1200",
           "--virtual-time-budget=6000"] + list(extra) + [url]
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if p.returncode != 0 and "unrecognized" in (p.stderr or ""):
        cmd[1] = "--headless"
        p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", default="available",
                    choices=["available", "release", "uptodate", "offline", "expanded"],
                    help="relay/update state to render (default: available)")
    ap.add_argument("--cap", type=int, default=600, help="Chrome's popup height cap")
    ap.add_argument("--no-shot", action="store_true")
    ap.add_argument("--keep", action="store_true", help="keep the harness file")
    args = ap.parse_args()

    chrome = find_chrome()
    harness = build_harness(args.state)
    name = "_preview_harness.html"
    path = EXT_DIR / name
    path.write_text(harness, encoding="utf-8")
    url = path.as_uri()
    tmp = pathlib.Path(tempfile.gettempdir()) / "lp_preview"
    tmp.mkdir(parents=True, exist_ok=True)
    shots = []
    try:
        (EXT_DIR / "_preview_measure.html").write_text(
            harness.replace("</body>", MEASURE + "</body>", 1), encoding="utf-8")
        dom = run(chrome, (EXT_DIR / "_preview_measure.html").as_uri(), ["--dump-dom"]).stdout
        raw = re.search(r"C-(?:EXPANDED|COLLAPSED)[^<]*", dom)
        if not raw:
            sys.exit("measurement failed: the page did not run")
        data = dict(piece.split("=", 1) for piece in raw.group(0).split("|") if "=" in piece)
        print("state: %s" % args.state)
        # The DEFAULT state is what the user sees on every click: it must fit.
        # An expanded list is allowed to scroll - it is opt-in and reversible.
        for key, label in (("COLLAPSED", "default state"), ("EXPANDED", "list open  ")):
            if "C-" + key in data:
                h = int(data["C-" + key].split("/")[0])
                verdict = "OK  " if h <= args.cap else "scroll"
                print("  %s %s %4d px  (cap %d)" % (verdict, label, h, args.cap))
        if "C-ROWS" in data:
            for row in data["C-ROWS"].split(", "):
                print("       - %s" % row)
        if not args.no_shot:
            shot = tmp / ("popup_%s.png" % args.state)
            run(chrome, url, ["--screenshot=" + str(shot)])
            shots.append(shot)
        collapsed = int(data.get("C-COLLAPSED", data.get("C-EXPANDED", "0")).split("/")[0])
        for s in shots:
            print("  screenshot: %s" % s)
        if collapsed > args.cap:
            print("\nFAIL: the default popup is %d px tall, past the %d px cap." % (collapsed, args.cap))
            print("      A button below the fold cannot be clicked.")
            return 1
        print("\nOK: every default-state control fits inside the popup cap.")
        return 0
    finally:
        (EXT_DIR / "_preview_measure.html").unlink(missing_ok=True)
        if not args.keep:
            path.unlink(missing_ok=True)
        else:
            print("  harness kept: %s" % path)


if __name__ == "__main__":
    raise SystemExit(main())
