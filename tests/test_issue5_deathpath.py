"""test_issue5_deathpath.py — UNIT tests for the §4 static death-path
artifacts and the §7 evidence adapter (offline, no emulator).

Covers:
  * death_path.json: schema, curated block, entity-table cross-checks
    (entity[0].HP MUST equal the live-verified freeze word 0x800CA2F6)
  * entities.json: entity_table registered with the same base/stride
  * re_evidence_adapter.py: contract projects VERIFIED refs only,
    keeps statuses, and never promotes PENDING to VERIFIED
"""
import json
import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

KB = os.path.join(_REPO, "data", "games", "SLUS-01212")


class TestDeathPathArtifacts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(KB, "death_path.json")) as f:
            cls.dp = json.load(f)
        with open(os.path.join(KB, "entities.json")) as f:
            cls.ent = json.load(f)

    def test_schema_and_identity(self):
        self.assertIn("hits", self.dp)
        self.assertIn("curated", self.dp)
        self.assertIn("exe_sha256", self.dp["curated"]["identity"])
        self.assertTrue(self.dp["curated"]["identity"]["exe_sha256"]
                        .startswith("1508b532"))

    def test_entity0_hp_equals_live_verified_freeze_word(self):
        et = self.dp["curated"]["entity_table"]
        self.assertEqual(et["base"], "0x800CA268")
        self.assertEqual(et["stride"], 0x14C)
        base = int(et["base"], 16)
        hp = base + 0x8E
        # THE invariant: static entity[0].HP == live-verified pair word
        self.assertEqual(hp, 0x800CA2F6)

    def test_entity1_hp_cross_check(self):
        base = int(self.dp["curated"]["entity_table"]["base"], 16)
        self.assertEqual(base + 0x14C + 0x8E, 0x800CA442)

    def test_death_paths_distinguished(self):
        paths = self.dp["curated"]["death_paths"]
        self.assertIn("path1_hp_damage", paths)
        self.assertIn("path2_instant_pit", paths)
        self.assertEqual(paths["path1_hp_damage"]["status"],
                         "EVIDENCE_BACKED")

    def test_entities_registry_has_entity_table(self):
        et = self.ent["entity_table"]
        self.assertEqual(et["base"], "0x800CA268")
        self.assertEqual(et["entity0_hp"], "0x800CA2F6")


class TestEvidenceAdapter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from re_evidence_adapter import build_contract
        cls.contract = build_contract()

    def test_contract_schema(self):
        self.assertEqual(self.contract["schema"], "ps1play-re-evidence/1")
        self.assertIn("refs", self.contract)
        self.assertIn("overlay", self.contract)

    def test_verified_refs_present(self):
        refs = self.contract["refs"]
        for k in ("hp_pair_0", "hp_pair_1", "flags_word", "score",
                  "grenade_counter", "entity_table_base", "entity_stride",
                  "entity1_hp"):
            self.assertIn(k, refs)
            self.assertEqual(refs[k]["status"], "VERIFIED", k)
        self.assertEqual(refs["hp_pair_0"]["addr"], 0x800CA2F6)

    def test_no_pending_promoted_to_verified(self):
        for k, v in self.contract["refs"].items():
            if k not in ("hp_pair_0", "hp_pair_1", "flags_word", "score",
                         "grenade_counter", "entity_table_base",
                         "entity_stride", "entity1_hp"):
                self.assertNotEqual(v["status"], "VERIFIED",
                                    f"{k} must not claim VERIFIED")

    def test_overlay_mapping_honest(self):
        ov = self.contract["overlay"]
        self.assertEqual(ov["live_dest"], "0x8009C0E8")
        self.assertIn("FALSIFIED", ov["note"])


if __name__ == "__main__":
    unittest.main()
