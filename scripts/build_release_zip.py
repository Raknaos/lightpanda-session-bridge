"""Build the release zip: extension/ at the archive root (same layout as 0.4.2).

The .zip.sha256 sidecar is what the in-product updater verifies before it
writes anything into the live extension directory, so it must be uploaded next
to the zip on every release.
"""
import hashlib
import json
import os
import pathlib
import zipfile

root = pathlib.Path(__file__).resolve().parent.parent
ext = root / "extension"
version = json.loads((ext / "manifest.json").read_text(encoding="utf-8"))["version"]
out = pathlib.Path(os.environ["LOCALAPPDATA"]) / "Temp" / f"lightpanda-session-bridge-{version}.zip"
if out.exists():
    out.unlink()

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ext.rglob("*")):
        if p.is_file():
            arc = "extension/" + p.relative_to(ext).as_posix()
            z.write(p, arc)

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
