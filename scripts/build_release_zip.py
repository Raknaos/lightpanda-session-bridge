"""Build the release zip: extension/ at the archive root (same layout as 0.4.2).

The .zip.sha256 sidecar is what the in-product updater verifies before it
writes anything into the live extension directory, so it must be uploaded next
to the zip on every release.
"""
import hashlib
import json
import os
import pathlib
import subprocess
import tempfile
import time
import zipfile

root = pathlib.Path(__file__).resolve().parent.parent
ext = root / "extension"
version = json.loads((ext / "manifest.json").read_text(encoding="utf-8"))["version"]
# mkdir(exist_ok=True) because LOCALAPPDATA is only set on Windows and its Temp
# subdir does not exist on a fresh profile or in CI - the builder used to die
# with a bare FileNotFoundError before writing a single entry.
out_dir = pathlib.Path(os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()) / "Temp"
out_dir.mkdir(parents=True, exist_ok=True)
out = out_dir / f"lightpanda-session-bridge-{version}.zip"
if out.exists():
    out.unlink()

def tracked_files():
    """Only what git tracks. `ext.rglob` shipped the gitignored
    extension/.build-info.json, so every release zip carried the build machine's
    install history - its commit, its timestamp, its previous install - into a
    public download."""
    try:
        out_ = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "extension"],
                              capture_output=True, check=True).stdout
        rels = [r for r in out_.decode("utf-8").split("\0") if r]
        if rels:
            return [root / r for r in sorted(rels)]
    except Exception as err:  # git unavailable: fall back, minus the generated file
        print("git unavailable (%s), falling back to a filtered walk" % err)
    return [p for p in sorted(ext.rglob("*"))
            if p.is_file() and p.name not in (".build-info.json",)]


# Reproducible archive. ZipFile.write() makes the bytes depend on WHO and WHEN
# built it, and the sidecar the updater verifies is a digest of those bytes:
#   - date_time defaults to now    -> rebuild a minute later, different sha256
#   - create_system/external_attr carry the build OS -> a Linux CI build and a
#     Windows release build disagree on identical sources
#   - DEFLATE is not reproducible across build machines. Measured on this very
#     repo: .venv ships zlib 1.3.1, the system python ships 1.3.1.zlib-ng - two
#     different deflate implementations, so the same 148 KB tree compressed to
#     148120 vs 148524 bytes. No compression level fixes that; the algorithms
#     simply differ.
# So the archive is STORED: uncompressed deflate is the only deflate whose
# output is fixed by the input. Cost is the real one and it is small - the
# shipped tree is ~150 KB of HTML/JS/fonts already compressed. What it buys is
# that the published sha256 means "these bytes are the committed tree" on every
# machine, forever, instead of "these bytes are whatever zlib felt like".
COMPRESS_LEVEL = None
FIXED_TIME = time.gmtime(int(os.environ.get("SOURCE_DATE_EPOCH") or 315532800))[:6]


def _entries() -> list:
    files = tracked_files()
    out = []
    for path in files:
        arc = "extension/" + path.relative_to(ext).as_posix()
        info = zipfile.ZipInfo(arc, date_time=FIXED_TIME)
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = 3            # always "unix", whatever the builder
        info.external_attr = 0o644 << 16  # a plain file
        out.append((info, path))
    return out


with zipfile.ZipFile(out, "w", zipfile.ZIP_STORED) as z:
    for info, path in _entries():
        with open(path, "rb") as fh:
            z.writestr(info, fh.read())

digest = hashlib.sha256(out.read_bytes()).hexdigest()
sidecar = out.with_name(out.name + ".sha256")
sidecar.write_text(f"{digest}  {out.name}\n", encoding="utf-8")

with zipfile.ZipFile(out) as z:
    names = z.namelist()
    print(out)
    print(len(names), "entrees")
    print("version dans le zip:", json.loads(z.read("extension/manifest.json").decode("utf-8"))["version"])
print("sha256:", digest)
print(sidecar)
