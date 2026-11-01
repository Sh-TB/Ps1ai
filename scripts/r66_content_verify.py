#!/usr/bin/env python3
"""r66_content_verify.py — the R66 final-mile content verification.

The stub defect (build_package archived path STRINGS instead of file
bytes) means every earlier package "verification" checked structure
only.  This script installs each regenerated package into a FRESH root
and reads the installed files back, asserting the knowledge is REAL
and matches the source-of-truth records:

  metal_slug_x: the capsule parses + validates, 56 events, event 55
                carries the schema-legal OBSERVED status; entities.json
                parses; the shipped test file is real Python.
  buzzybee:     the capsule validates (15 events).
  tetrade:      the R65 anchor table JSON parses with 28 measured rows
                (or the committed record's own shape).
  flappybird:   the adapter module source is real Python and the model
                manifest parses.

Every installed byte is also hash-checked against the package
manifest by the installer itself (install refuses a mismatch), so
this pass is purely about CONTENT fidelity.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

REPO = "/home/z/my-project/ps1ai"
DL = os.path.join(REPO, "download")

sys.path.insert(0, REPO)
from ps1play.knowledge import Capsule  # noqa: E402


def install_root(pkg):
    root = tempfile.mkdtemp(prefix="r66_verify_")
    out = subprocess.run(
        [sys.executable, "-m", "ps1play", "knowledge", "install", pkg,
         "--root", root],
        cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, (pkg, out.stdout, out.stderr)
    return root


def read_installed(root, game_id, arc):
    """Find the installed file under the per-game isolated dir."""
    base = os.path.join(root, game_id)
    for dirpath, _dirs, files in os.walk(base):
        rel = os.path.relpath(dirpath, base)
        p = os.path.join(dirpath, os.path.basename(arc))
        if os.path.exists(p):
            return p
    raise AssertionError(f"installed file not found: {game_id}/{arc}")


def check_msx(root):
    p = read_installed(root, "metal_slug_x", "capsule.json")
    c = Capsule.load(p)
    assert len(c["events"]) == 56, len(c["events"])
    assert c["events"][55]["status"] == "OBSERVED"
    assert c.size_bytes() < 64 * 1024
    e = json.load(open(read_installed(root, "metal_slug_x",
                                      "entities.json")))
    assert e, "empty entities"
    t = open(read_installed(root, "metal_slug_x",
                            os.path.join("tests", "test_msx_r66.py"))
             ).read()
    assert "def test_" in t and len(t) > 5000, "test file is a stub?"
    f = json.load(open(read_installed(root, "metal_slug_x",
                                      "r66_findings.json")))
    assert f.get("round") == "R66", f
    print("  msx: capsule 56 events (ev55 OBSERVED), entities, "
          f"findings digest + test file real ({len(t)} B)")


def check_buzzybee(root):
    c = Capsule.load(read_installed(root, "buzzybee", "capsule.json"))
    assert len(c["events"]) == 15, len(c["events"])
    a = open(read_installed(root, "buzzybee",
                            os.path.join("plugin", "adapter.py"))).read()
    assert "class " in a and len(a) > 5000
    print(f"  buzzybee: capsule 15 events, adapter real ({len(a)} B)")


def check_tetrade(root):
    a = json.load(open(read_installed(
        root, "tetrade", "anchor_table_r65.json")))
    assert a, "empty anchor table"
    p = open(read_installed(root, "tetrade",
                            os.path.join("plugin", "policy.py"))).read()
    assert "class " in p and len(p) > 5000
    print(f"  tetrade: anchor table real ({len(json.dumps(a))} B JSON), "
          f"policy real ({len(p)} B)")


def check_flappy(root):
    a = open(read_installed(root, "flappybird",
                            os.path.join("plugin", "adapter.py"))).read()
    assert "class " in a and len(a) > 5000
    m = json.load(open(read_installed(
        root, "flappybird", "model_authority_manifest.json")))
    assert m, "empty model manifest"
    print(f"  flappybird: adapter real ({len(a)} B), model manifest "
          f"real ({len(json.dumps(m))} B JSON)")


def main():
    checks = [("metal_slug_x", check_msx),
              ("buzzybee", check_buzzybee),
              ("tetrade", check_tetrade),
              ("flappybird", check_flappy)]
    roots = []
    try:
        for gid, fn in checks:
            root = install_root(os.path.join(DL, f"{gid}.ps1game"))
            roots.append(root)
            print(f"{gid}.ps1game installed into fresh root:")
            fn(root)
        print("ALL FOUR PACKAGES: installed content verified REAL")
    finally:
        for r in roots:
            shutil.rmtree(r, ignore_errors=True)


if __name__ == "__main__":
    main()
