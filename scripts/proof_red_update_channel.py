"""Proof-red for the update channel's content comparison.

The wolf-crying chip: `check_update` decided "install this" by comparing COMMITS,
and the commit recorded on install is whatever tip the last fetch saw - routinely
a commit that touched only scripts/ or docs. Measured on 0.7.18: installed
045eac3, newest commit touching extension/ 37e958d, and BOTH carry the tree
c1090d37 - so the popup offered an update that installs identical bytes, and no
install could ever clear it.

Each sabotage breaks one link and the named test must go red. Exit 0 means every
sabotage was red AND named; a `PATCH-MISS`, a `HARNESS` failure or a `NOT RED`
makes the proof INVALID, never green.
"""
import hashlib
import pathlib
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRISTINE = ROOT / "scripts" / "artifacts_pristine"
PY = ROOT / ".venv" / "Scripts" / "python.exe"
TEST = "test_updater.py"
UP = "relay/updater.py"

SABOTAGES = [
    ("compare les COMMITS au lieu des OCTETS",
     [("            if same_shipped_commit or identical_tree:",
       "            if same_shipped_commit:")],
     "octets identiques"),
    ("la note ne dit plus pourquoi rien n'est a installer",
     [('"main moved to %s, but the deployed tree is byte-identical"',
       '"main moved to %s, but the deployed tree looks the same"')],
     "byte-identical"),
    ("le hash local utilise un autre schema que le distant",
     [("            entries.append((rel, hashlib.sha1(\n"
       "                b\"blob %d\\0\" % len(blob) + blob).hexdigest()))",
       "            entries.append((rel, hashlib.sha256(blob).hexdigest()))")],
     "schema de blob git"),
    ("le hash local ose le prefixe extension/, donc plus aucun arbre ne correspond",
     [('            rel = "extension/" + os.path.relpath(full, ext_dir).replace(os.sep, "/")',
       '            rel = os.path.relpath(full, ext_dir).replace(os.sep, "/")')],
     "schema de blob git"),
    (".build-info.json entre dans le hash du tree",
     [('            if rel == "extension/" + BUILD_INFO or rel.endswith("/.DS_Store"):',
       '            if rel.endswith("/.DS_Store"):')],
     "build-info.json change"),
    # La branche SANS PROVENANCE : elle ne comparait que les versions, donc une
    # version egale se lisait comme une MAJ a faire (mesure : from 0.7.19 ->
    # to 0.7.19, update_available True).
    ("la branche sans provenance ignore les octets deposes",
     [("            if installed and published and installed == published:",
       "            if False:")],
     "identical bytes must not offer an update"),
    ("la branche sans provenance ne dit pas ce qu'elle a refuse",
     [('"note": "release %s is byte-identical to the deployed "',
       '"note": "release %s matches the installed "')],
     "byte-identical"),
    # L'inverse exact : si on saute la comparaison d'arbre DANS le sens qui
    # offre la MAJ, on masque une vraie mise a jour derriere un 'a jour'.
    ("la branche sans provenance masque une vraie MAJ",
     [("            if not identical:\n"
       "                if installed and published and installed[:3] <= published[:3]:",
       "            if False:\n"
       "                if installed and published and installed[:3] <= published[:3]:")],
     "different bytes IS an install worth making"),
    ("un downgrade vers la release redevient possible",
     [("                if installed and published and installed[:3] <= published[:3]:",
       "                if installed and published:")],
     "must not be pulled back"),
]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def pristine(rel):
    dst = PRISTINE / rel.replace("/", "__")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / rel, dst)
    return dst


def run_tests():
    # `tests/` is not a package: naming the module fails with ModuleNotFoundError
    # and every sabotage reads as red. Discover it instead, by pattern.
    r = subprocess.run([sys.executable, "-m", "unittest", "discover",
                        "-s", "tests", "-p", TEST],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=400)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    if not PY.exists():
        print("FAIL: .venv absent - le projet doit etre teste avec son propre "
              "interpreteur (point 1 du gate)")
        return 1
    results = []
    for label, edits, expect in SABOTAGES:
        target = ROOT / UP
        pristine(UP)
        before = sha(target)
        original = target.read_text(encoding="utf-8")
        text = original
        missing = None
        for a, b in edits:
            if a not in text:
                missing = a.strip().splitlines()[0][:70]
                break
            text = text.replace(a, b, 1)
        if missing:
            results.append((label, "PATCH-MISS", "motif absent: " + missing))
            shutil.copy2(PRISTINE / UP.replace("/", "__"), target)
            continue
        target.write_text(text, encoding="utf-8", newline="")
        if sha(target) == before:
            results.append((label, "PATCH-MISS", "le sabotage n'a rien change"))
            shutil.copy2(PRISTINE / UP.replace("/", "__"), target)
            continue
        try:
            code, out = run_tests()
            # Detect the TRACEBACK shape. Matching the phrase "Failed to import
            # test module" alone was not enough: unittest prints it on the line
            # AFTER the phrase, and a docstring quoting it reads as a real
            # failure - three fake reds in a row before this was tightened.
            if "unittest.loader._FailedTest" in out or (
                    "ModuleNotFoundError" in out and "Traceback" in out):
                results.append((label, "HARNESS",
                                "le module de test n'a pas charge - preuve invalide"))
                continue
            red = code != 0
            named = expect.lower() in out.lower()
            status = ("RED (named)" if red and named
                      else "RED (unnamed)" if red else "NOT RED")
            detail = out.strip().splitlines()[-1][:88] if out.strip() else "?"
            results.append((label, status, detail))
        finally:
            shutil.copy2(PRISTINE / UP.replace("/", "__"), target)
            if sha(target) != before:
                print("ERREUR: la restauration de %s n'est pas identique" % UP)
                return 1

    print("PROOF RED")
    reds = named_reds = 0
    invalid = 0
    for label, status, detail in results:
        print("  %-14s %s" % (status, label))
        print("                 %s" % detail)
        if status.startswith("RED"):
            reds += 1
        if status == "RED (named)":
            named_reds += 1
        if status in ("PATCH-MISS", "HARNESS", "NOT RED", "RED (unnamed)"):
            invalid += 1
    print("\n%d sabotage(s), %d rouge(s), %d nomme(s), %d invalide(s)"
          % (len(results), reds, named_reds, invalid))
    if invalid:
        print("un sabotage n'a pas ete correctement evalue - preuve INVALIDE")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())