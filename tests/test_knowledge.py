"""tests/test_knowledge.py — Issue #10 Part 7A: capsule, provenance,
cache, CLI delegation, and the ground-truth gate."""
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from ps1play.knowledge import (AnalysisCache, Capsule, CapsuleError,  # noqa
                               require_observable)


def _ident(**over):
    d = {"game_id": "t", "title": "T", "serial": "SLUS-00000",
         "region": "NTSC-U", "exe_sha256": "ab" * 32}
    d.update(over)
    return d


def test_identity_required():
    c = Capsule.new({"game_id": "t"})
    with pytest.raises(CapsuleError):
        c.validate()


def test_status_enum_and_provenance_gate():
    c = Capsule.new(_ident())
    c.add_field(0x8000, 4, "score", "VERIFIED", {"source": "x"})
    with pytest.raises(CapsuleError):  # VERIFIED needs evidence too
        c.validate()
    c["memory_fields"][0]["provenance"]["evidence"] = "frame 12"
    assert c.validate() > 0
    c.add_field(0x8004, 4, "lives", "MADE_UP", {"source": "x",
                                                "evidence": "y"})
    with pytest.raises(CapsuleError):
        c.validate()


def test_observed_needs_provenance_inferred_not():
    c = Capsule.new(_ident())
    c.add_event("e", "OBSERVED", {"source": "probe-1", "evidence": "f1"})
    c.validate()
    c.add_event("e2", "INFERRED", {})
    c.validate()  # inferred may lack provenance, but cannot be promoted


def test_cannot_use_unverified_as_ground_truth():
    f = {"game_status": "INFERRED"}
    with pytest.raises(CapsuleError):
        require_observable(f)
    ok = {"game_status": "VERIFIED"}
    assert require_observable(ok)
    ev = {"status": "OBSERVED"}
    assert require_observable(ev)
    bad = {"status": "CONTRADICTED"}
    with pytest.raises(CapsuleError):
        require_observable(bad)


def test_artifacts_need_hash_and_path():
    c = Capsule.new(_ident())
    c["artifacts"].append({"id": "x"})
    with pytest.raises(CapsuleError):
        c.validate()


def test_size_hard_limit(tmp_path):
    c = Capsule.new(_ident())
    c["unknowns"] = ["x" * 200] * 2000  # >128 KiB
    with pytest.raises(CapsuleError):
        c.validate()


def test_queries():
    c = Capsule.new(_ident())
    c.add_field(0x800EE318, 4, "score_p1", "INFERRED", {})
    c.add_field(0x800EE320, 4, "score_p2", "INFERRED", {})
    c.add_function(0x800A41D8, "damage", "VERIFIED",
                   {"source": "s", "evidence": "e"})
    assert len(c.fields_by_role("score_p1")) == 1
    assert c.field(0x800EE320)["role"] == "score_p2"
    near = c.functions_near(0x800A4000, radius=0x400)
    assert len(near) == 1
    # verified-only query promotes nothing:
    with pytest.raises(CapsuleError):
        c.fields_by_role("score_p1", min_status=True)


def test_roundtrip(tmp_path):
    c = Capsule.new(_ident())
    c.add_field(0x8000, 2, "hp", "OBSERVED",
                {"source": "probe", "evidence": "frames 100-200"})
    p = tmp_path / "c.json"
    c.save(str(p))
    c2 = Capsule.load(str(p))
    assert c2.field(0x8000)["provenance"]["evidence"] == "frames 100-200"


def test_cache_hit_miss_and_invalidation(tmp_path):
    from ps1play.knowledge.cache import key
    cache = AnalysisCache(str(tmp_path / "cache"))
    k1 = key("msx", {"exe": "aaa"}, "ghidra", {"v": 1})
    assert cache.get(k1) is None
    cache.put_with_meta(k1, {"fns": 2931}, "msx", "ghidra",
                        {"exe": "aaa"}, {"v": 1})
    assert cache.get(k1)["value"]["fns"] == 2931
    k2 = key("msx", {"exe": "bbb"}, "ghidra", {"v": 1})  # input changed
    assert cache.get(k2) is None                          # no false hit
    assert cache.invalidate("other") == 0
    assert cache.invalidate("msx") == 1


def test_unsupported_address_type_exists():
    from ps1play.knowledge.cache import UnsupportedAddress
    with pytest.raises(LookupError):
        raise UnsupportedAddress("0x99999999 not mapped")


def test_cli_delegation_and_builders():
    from capsule_builders import BUILDERS
    for gid, fn in BUILDERS.items():
        cap = fn()
        cap.validate()  # every builder output must validate
    # the proposed ps1play_cli.py interface delegates to knowledge CLI
    out = subprocess.run(
        [sys.executable, os.path.join(REPO, "scripts", "ps1play_cli.py"),
         "capsule-validate",
         os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")],
        capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    j = json.loads(out.stdout)
    assert j["ok"] and j["game_id"] == "msx"


def test_shipped_capsules_validate_and_size():
    for gid in ("buzzybee", "mspsx", "msx"):
        p = os.path.join(REPO, "data", "knowledge", gid, "capsule.json")
        c = Capsule.load(p)
        assert c.size_bytes() < 64 * 1024, gid
