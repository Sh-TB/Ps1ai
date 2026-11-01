"""R65 knowledge-package tests — the .ps1game system (Part B).

Offline only: exporter roundtrip, hash tampering, manifest tampering,
ZIP path traversal rejection, install isolation, CLI-level helpers.
"""
import json
import os
import sys
import zipfile

import pytest

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

from ps1play.knowledge.package import (  # noqa: E402
    MANIFEST_NAME, PackageError, build_package, export_game,
    exportable_games, install_package, make_manifest,
    read_installed_manifest, spec_for_game, validate_package,
    verify_manifest)

OUT = "/tmp/r65_pkg_tests"


def _mini_spec(**kw):
    spec = {
        "game_id": "minigame", "title": "Mini Game", "version": "1.0.0",
        "maturity": "BOOT_VERIFIED",
        "serial": "SLUS-99999", "region": "NTSC", "revision": "1",
        "files": [({"pin": True}, "knowledge/pin.json", "disc_knowledge"),
                  ("README", "docs/a.md", "doc")],
        "readme": "# mini",
        "runtime": {"runtime_version_compat": ["1.0.0"]},
        "capabilities": {"autonomous_play": False},
        "legal": {"assets_included": False},
    }
    # turn the inline doc entry into a real file entry
    spec["files"][1] = (os.path.join(REPO, "worklog.md"),
                        "docs/a.md", "doc")
    spec.update(kw)
    return spec


@pytest.fixture(scope="module")
def exported():
    import shutil
    shutil.rmtree(OUT, ignore_errors=True)   # idempotent re-runs
    os.makedirs(OUT, exist_ok=True)
    return export_game("flappybird", OUT)


class TestExportRoundtrip:
    def test_export_validates_itself(self, exported):
        man = validate_package(exported["path"])
        assert man["package"]["game_id"] == "flappybird"
        assert man["package"]["maturity"] in (
            "PARTIAL_AUTONOMOUS_PLAYER",)

    def test_sidecar_hash_matches(self, exported):
        import hashlib
        h = hashlib.sha256(open(exported["path"], "rb").read())
        assert h.hexdigest() == exported["sha256"]

    def test_every_game_with_a_spec_exports(self):
        for g in exportable_games():
            spec = spec_for_game(g)
            assert spec["game_id"] == g
            assert spec["maturity"] in (
                "EXPERIMENTAL", "BOOT_VERIFIED", "INPUT_VERIFIED",
                "GAMEPLAY_VERIFIED", "PARTIAL_AUTONOMOUS_PLAYER",
                "OBJECTIVE_VERIFIED",
                "FULL_GAME_COMPLETION_VERIFIED")
            for entry in spec["files"]:
                src = entry[0]
                if isinstance(src, (dict, str)):
                    continue
                assert os.path.exists(src), f"{g}: missing {src}"

    def test_no_cross_game_references(self):
        """The isolation rule: a package's files may not mention
        another game's plugin/policy material by path."""
        import re
        for g in exportable_games():
            spec = spec_for_game(g)
            for entry in spec["files"]:
                arc = entry[1]
                other = [o for o in exportable_games()
                         if o != g and o != "metal_slug_x"]
                for o in other:
                    assert f"/{o}/" not in arc and \
                        not arc.startswith(f"{o}/"), \
                        f"{g}: package references {o}'s file {arc}"


class TestValidation:
    def test_manifest_schema(self):
        man = make_manifest(
            game_id="mini_x", title="X", version="1.0.0",
            maturity="BOOT_VERIFIED", serial="s", region="r",
            revision="1", contents=[{"path": "a.txt",
                                     "sha256": "0" * 64,
                                     "bytes": 1, "role": "doc"}],
            runtime={"runtime_version_compat": ["1.0.0"]},
            capabilities={}, legal={})
        verify_manifest(man)
        body = {k: v for k, v in man.items() if k != "integrity"}
        bad = dict(body)
        bad["package"] = dict(body["package"])
        bad["package"]["maturity"] = "FULL_GAME_COMPLETION_VERIFIED"
        # a modified body must fail the integrity check
        with pytest.raises(PackageError):
            verify_manifest({**bad, "integrity": man["integrity"]})

    def test_bad_maturity_rejected(self):
        with pytest.raises(PackageError):
            make_manifest(game_id="x", title="X", version="1",
                          maturity="GODLIKE", serial="s", region="r",
                          revision="1", contents=[], runtime={},
                          capabilities={}, legal={})

    def test_tampered_content_hash_detected(self, exported):
        path = os.path.join(OUT, "tampered_content.ps1game")
        with zipfile.ZipFile(exported["path"]) as zin, \
                zipfile.ZipFile(path, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith(".md") and \
                        item.filename != MANIFEST_NAME:
                    data += b"tampered\n"
                zout.writestr(item, data)
        with pytest.raises(PackageError) as e:
            validate_package(path)
        assert "sha256 mismatch" in str(e.value) or \
            "size mismatch" in str(e.value)

    def test_manifest_integrity_tamper_detected(self, exported):
        path = os.path.join(OUT, "tampered_manifest.ps1game")
        with zipfile.ZipFile(exported["path"]) as zin, \
                zipfile.ZipFile(path, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename == MANIFEST_NAME:
                    man = json.loads(data)
                    man["package"]["title"] = "HACKED"
                    data = json.dumps(man).encode()
                zout.writestr(item, data)
        with pytest.raises(PackageError) as e:
            validate_package(path)
        assert "integrity" in str(e.value)

    def test_zip_traversal_rejected(self):
        path = os.path.join(OUT, "traversal.ps1game")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("../../evil.txt", "x")
        with pytest.raises(PackageError) as e:
            validate_package(path)
        assert "traversal" in str(e.value)

    def test_absolute_path_rejected(self):
        path = os.path.join(OUT, "absolute.ps1game")
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("/etc/passwd", "x")
        with pytest.raises(PackageError) as e:
            validate_package(path)
        assert "absolute" in str(e.value)

    def test_not_a_zip(self):
        path = os.path.join(OUT, "notzip.ps1game")
        with open(path, "wb") as f:
            f.write(b"definitely not a zip file")
        with pytest.raises(PackageError):
            validate_package(path)


class TestInstall:
    def test_install_and_isolation(self, exported):
        root = os.path.join(OUT, "store")
        r1 = install_package(exported["path"], root)
        assert r1["installed_to"] == os.path.join(
            root, "flappybird", "1.0.0")
        # reinstalling the same version without force fails
        with pytest.raises(PackageError):
            install_package(exported["path"], root)
        # force reinstalls ONLY that game+version
        r2 = install_package(exported["path"], root, force=True)
        assert r2["installed_to"] == r1["installed_to"]
        # another game's tree is never touched
        other = os.path.join(root, "othergame", "9.9.9")
        os.makedirs(other, exist_ok=True)
        with open(os.path.join(other, "keep.txt"), "w") as f:
            f.write("keep")
        spec = _mini_spec(game_id="minigame")
        build_package(spec, OUT)
        install_package(os.path.join(OUT, "minigame.ps1game"), root)
        assert os.path.exists(os.path.join(other, "keep.txt"))

    def test_installed_manifest_reads_back(self, exported):
        root = os.path.join(OUT, "store2")
        install_package(exported["path"], root)
        man = read_installed_manifest(root, "flappybird")
        assert man is not None
        assert man["package"]["game_id"] == "flappybird"

    def test_installed_files_match_hashes(self, exported):
        import hashlib
        root = os.path.join(OUT, "store3")
        r = install_package(exported["path"], root)
        man = validate_package(exported["path"])
        for c in man["contents"]:
            p = os.path.join(r["installed_to"], *c["path"].split("/"))
            assert os.path.exists(p)
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            assert h == c["sha256"]


class TestSpecIntegrity:
    def test_runtime_compat_is_current(self):
        from ps1play.runtime.config import RUNTIME_VERSION
        for g in exportable_games():
            spec = spec_for_game(g)
            assert RUNTIME_VERSION in \
                spec["runtime"]["runtime_version_compat"], \
                f"{g}: runtime compat must include the current " \
                f"runtime version"

    def test_legal_section_honest(self):
        for g in exportable_games():
            spec = spec_for_game(g)
            assert spec["legal"]["assets_included"] is False
            assert spec["legal"]["user_must_provide"]
