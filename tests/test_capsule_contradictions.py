"""tests/test_capsule_contradictions.py — R38 Task 2: the +0x8E semantic
contradiction guard.

The R37 MSX capsule shipped `P1_entity_HP (base+0x8E)` as VERIFIED even
though the truck campaign (docs/truck_blocker_resolution.md, "SUPERSEDED —
the +0x8E = hp label") and the Issue #10 Gate B no-fire control
(docs/tools_matrix_issue10.md caveat) had explicitly killed that
interpretation. These tests pin the fix:

  1. a CONTRADICTED event with `supersedes_role` blocks any memory_field
     with the same role from being retained VERIFIED (loud CapsuleError);
  2. the honest resolution shape (address observation under a NEW role at
     a weaker status) validates;
  3. re-promotion requires an explicit `resolved_by` VERIFIED event;
  4. consumers querying the dead role with a ground-truth gate get a loud
     failure (the old fact cannot silently supply gameplay truth);
  5. the SHIPPED msx capsule itself carries the contradiction and no
     VERIFIED field with the dead role;
  6. all shipped capsules validate and their artifact hashes verify
     (portable repo-relative paths).
"""
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from ps1play.knowledge import Capsule, CapsuleError  # noqa: E402

DEAD_ROLE = "P1_entity_HP (base+0x8E)"


def _ident():
    return {"game_id": "t", "title": "T", "serial": "SLUS-00000",
            "region": "NTSC-U", "exe_sha256": "ab" * 32}


def _capsule_with_contradiction():
    c = Capsule.new(_ident())
    # the exact R37 regression: stale VERIFIED semantic claim
    c.add_field(0x800CA2F6, 2, DEAD_ROLE, "VERIFIED",
                {"source": "old A/B", "evidence": "hp 56 dmg baseline"})
    # the R38 contradiction, with the role it supersedes
    c.add_event("the '+0x8E = HP' label is contradicted (truck 254->254 "
                "under fire while +0xA4 300->0; no-fire decay 3/3)",
                "CONTRADICTED",
                {"source": "truck campaign", "evidence": "uplob9/10"},
                supersedes_role=DEAD_ROLE)
    return c


def test_contradicted_semantic_cannot_stay_verified():
    with pytest.raises(CapsuleError, match="contradiction guard"):
        _capsule_with_contradiction().validate()


def test_address_observation_under_new_role_is_legal():
    """The honest fix shape: same address, NEW role, weaker status."""
    c = Capsule.new(_ident())
    c.add_field(0x800CA2F6, 2,
                "entity_field_+0x8E (slot0 address observation)",
                "OBSERVED",
                {"source": "A/B + Gate B + pincorr1",
                 "evidence": "pair freeze; decay 3/3; 291->81 swings"})
    c.add_event("'+0x8E = HP' contradicted", "CONTRADICTED",
                {"source": "truck campaign", "evidence": "uplob9/10"},
                supersedes_role=DEAD_ROLE)
    assert c.validate() > 0
    assert c.contradicted_roles() == {DEAD_ROLE}


def test_repromotion_requires_resolved_by_verified_event():
    c = _capsule_with_contradiction()
    c.validate  # noqa: B018 - (intentionally not called yet)
    # resolved_by pointing at nothing -> still blocked
    c["events"][0]["resolved_by"] = 7
    with pytest.raises(CapsuleError):
        c.validate()
    # a VERIFIED event with full provenance explicitly resolves it
    c.add_event("new paired trial re-verifies +0x8E as the damage "
                "mediator on this build", "VERIFIED",
                {"source": "r38 paired trial",
                 "evidence": "3/3 bit-identical runs + score events"},
                eid=7)
    c["events"][0]["resolved_by"] = 7
    assert c.validate() > 0


def test_ground_truth_query_on_dead_role_fails_loud():
    """A consumer asking for the dead role with the observable gate gets
    a loud CapsuleError, never a silent result."""
    c = _capsule_with_contradiction()
    with pytest.raises(CapsuleError):
        c.fields_by_role(DEAD_ROLE, min_status=True)


def test_non_role_contradictions_do_not_block():
    """CONTRADICTED events without supersedes_role stay informational."""
    c = Capsule.new(_ident())
    c.add_field(0x8000, 4, "score", "VERIFIED",
                {"source": "s", "evidence": "e"})
    c.add_event("an unrelated claim died", "CONTRADICTED",
                {"source": "s", "evidence": "e"})
    assert c.validate() > 0


def test_shipped_msx_capsule_carries_the_contradiction():
    p = os.path.join(REPO, "data", "knowledge", "msx", "capsule.json")
    c = Capsule.load(p)  # load() validates -> guard active
    assert DEAD_ROLE in c.contradicted_roles()
    assert not [f for f in c["memory_fields"]
                if f["role"] == DEAD_ROLE]
    obs = [f for f in c["memory_fields"]
           if f["va"] == 0x800CA2F6]
    assert len(obs) == 1 and obs[0]["game_status"] == "OBSERVED"
    assert "UNRESOLVED" in obs[0]["role"]
    # the armored-entity HP fact must be present and observable
    a4 = c.fields_by_role(
        "armored_entity_HP (entity_base+0xA4; truck live-verified)",
        min_status=True)
    assert a4 and a4[0]["va"] == 0x800CA30C


def test_shipped_capsules_validate_and_artifacts_verify():
    for gid in ("buzzybee", "mspsx", "msx"):
        p = os.path.join(REPO, "data", "knowledge", gid, "capsule.json")
        c = Capsule.load(p)
        assert c.size_bytes() < 64 * 1024, gid
        for a in c.get("artifacts", []):
            assert not os.path.isabs(a["path"]), (gid, a["path"])
            fs = c.artifact_fs_path(a)
            assert os.path.exists(fs), fs
        c.verify_artifacts()


def test_artifact_hash_mismatch_is_loud(tmp_path):
    c = Capsule.new(_ident())
    f = tmp_path / "blob.bin"
    f.write_bytes(b"payload")
    c.add_artifact("blob", str(f), root=str(tmp_path))
    assert c.verify_artifacts(root=str(tmp_path)) == 1
    f.write_bytes(b"tampered")
    with pytest.raises(CapsuleError, match="mismatch"):
        c.verify_artifacts(root=str(tmp_path))
    with pytest.raises(CapsuleError, match="missing"):
        c.verify_artifacts(root=str(tmp_path / "nowhere"))
