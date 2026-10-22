"""test_msx_scene.py — UNIT tests for the canonical Metal Slug X scene
adapter (Issue #5 focused follow-up, Phase 3 + Phase 5).

Fully offline (no emulator, no disc): the adapter is a pure function of
a raw read_world()-shaped dict + a frame index. Proves:

  * schema completeness on the normal path AND the degraded path
  * missing/invalid fields become the "unknown" sentinel (never guessed)
  * invalid slots are dropped and counted
  * stale observations flag the scene
  * falling-projectile candidates: promoted after 2 consecutive downward
    moves with |vx| <= 3; the horizontal-only threat rule (WorldModel.
    threat) MISSES the same object — the before/after policy decision
    differs (advance vs dodge), which is the real behavioral fix
  * unknown observation layer != "no threat" (threat_unknown)
  * every scene-consuming MSX runner routes through the adapter (static
    source check)
"""
import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from ps1play.agent.msx_scene import (          # noqa: E402
    MsxSceneAdapter, UNKNOWN)
from ps1play.agent.policy import SemanticPolicy  # noqa: E402
from ps1play.agent.worldmodel import WorldModel  # noqa: E402

REQUIRED_KEYS = ("schema", "frame", "stale", "player", "enemies",
                 "bullets", "projectiles", "health", "items",
                 "n_enemies", "nearest_enemy", "threat",
                 "threat_unknown", "provenance")


def raw_scene(enemies=(), bullets=(), player=None):
    return {"player": player or {"x": 0x2000, "y": 0x100},
            "enemies": list(enemies), "bullets": list(bullets),
            "items": [], "health": []}


class TestSchema(unittest.TestCase):
    def test_normal_path_schema_complete(self):
        sc = MsxSceneAdapter().build(raw_scene(), frame=100)
        for k in REQUIRED_KEYS:
            self.assertIn(k, sc)
        self.assertEqual(sc["schema"], "ps1play-msx-scene/1")
        self.assertFalse(sc["stale"])
        self.assertEqual(sc["player"]["x"], 0x2000)

    def test_degraded_path_unknown_not_guessed(self):
        sc = MsxSceneAdapter().build({}, frame=0)
        self.assertEqual(sc["player"]["x"], UNKNOWN)
        self.assertEqual(sc["player"]["y"], UNKNOWN)
        self.assertTrue(sc["threat_unknown"])

    def test_invalid_slots_dropped_and_counted(self):
        raw = raw_scene(enemies=[
            {"dx": 100, "dy": 0, "x": 0, "y": 50, "vx": 1},        # x==0
            {"dx": 100, "dy": 0, "x": 0x20000, "y": 50, "vx": 1},  # x big
            {"dx": 0x9000, "dy": 0, "x": 0x9000, "y": 50, "vx": 1},  # far
            {"dx": 100, "dy": 0, "x": 0x2100, "y": 50, "vx": 1},   # ok
        ])
        sc = MsxSceneAdapter().build(raw, frame=10)
        self.assertEqual(sc["n_enemies"], 1)
        self.assertEqual(sc["provenance"]["dropped_invalid"], 3)

    def test_stale_flag_after_quiet_period(self):
        ad = MsxSceneAdapter()
        ad.build(raw_scene(player={"x": 5, "y": 5}), frame=0)
        sc = ad.build(raw_scene(), frame=STALE_FRAMES + 1)
        self.assertTrue(sc["stale"])

    def test_nearest_enemy_none_vs_unknown_layer(self):
        # no enemies OBSERVED with a certified anchor -> clean None
        wm = WorldModel(None)
        wm.player_x_addr = 0x1234          # certified anchor
        sc = MsxSceneAdapter(world_model=wm).build(raw_scene(), frame=1)
        self.assertIsNone(sc["nearest_enemy"])
        self.assertFalse(sc["threat_unknown"])
        # without a certified anchor the layer is unknown
        sc2 = MsxSceneAdapter(world_model=WorldModel(None)).build(
            raw_scene(), frame=1)
        self.assertTrue(sc2["threat_unknown"])


STALE_FRAMES = 600


class TestFallingCandidates(unittest.TestCase):
    def _falling_series(self, adapter, y0=0x800):
        """Feed 3 observations of one slot falling with vx=0."""
        scene = None
        for i, y in enumerate((y0, y0 - 3, y0 - 6)):
            raw = raw_scene(enemies=[{"dx": 20, "dy": y - 0x100,
                                      "x": 0x2020, "y": y, "vx": 0,
                                      "slot": 0xCA3000}])
            scene = adapter.build(raw, frame=i * 10)
        return scene

    def test_falling_candidate_promoted_and_threatening(self):
        sc = self._falling_series(MsxSceneAdapter())
        kinds = [p["kind"] for p in sc["projectiles"]]
        self.assertIn("falling_candidate", kinds)
        self.assertEqual(sc["provenance"]["falling_candidates"], 1)
        self.assertIsNotNone(sc["threat"])
        self.assertEqual(sc["threat"]["kind"], "falling_candidate")

    def test_horizontal_only_rule_misses_it(self):
        """BEFORE behavior: WorldModel.threat() requires |vx| > 3 — the
        same falling object is invisible to it."""
        class FakeWM:
            player_x_addr = None
        raw = raw_scene(enemies=[{"dx": 20, "dy": -3, "x": 0x2020,
                                  "y": 0x7f0, "vx": 0, "slot": 1}])
        import numpy as np
        wm = WorldModel(np.zeros(16, dtype=np.uint8))
        wm.player_x_addr = None
        self.assertIsNone(wm.threat(raw))

    def test_policy_decision_changes_before_after(self):
        """The real behavioral difference: same RAM observation, old
        scene glue vs the adapter — SemanticPolicy must DODGE only with
        the adapter (the falling bomb becomes a threat)."""
        def expand(scene, chunks=3):
            pol = SemanticPolicy()
            for _ in range(chunks):
                pol.decide(60, dict(scene), {"events": []})
            return pol.stats

        raw = raw_scene(enemies=[{"dx": 20, "dy": -6, "x": 0x2020,
                                  "y": 0x7fa, "vx": 0, "slot": 0xCA3000}])
        # OLD glue (run_semantic <= a565b23): threat from wm.threat()
        old_scene = raw_scene(enemies=[{"dx": 20, "dy": -6, "x": 0x2020,
                                        "y": 0x7fa, "vx": 0}])
        old_scene["threat"] = None       # wm.threat() sees nothing
        old_scene["nearest_enemy"] = old_scene["enemies"][0]
        old_scene["n_enemies"] = 1
        # NEW: the adapter (2 prior downward samples already recorded)
        ad = MsxSceneAdapter()
        for i, y in enumerate((0x800, 0x800 - 3)):
            ad.build(raw_scene(enemies=[{"dx": 20, "dy": y - 0x100,
                                         "x": 0x2020, "y": y, "vx": 0,
                                         "slot": 0xCA3000}]),
                     frame=i * 10)
        new_scene = ad.build(
            raw_scene(enemies=[{"dx": 20, "dy": -9, "x": 0x2020,
                                "y": 0x800 - 6, "vx": 0,
                                "slot": 0xCA3000}]), frame=20)

        old_stats = expand(old_scene)
        new_stats = expand(new_scene)
        self.assertEqual(old_stats["dodge"], 0)   # shoot rule instead
        self.assertGreaterEqual(new_stats["dodge"], 1)  # bomb dodged

    def test_not_promoted_on_single_sample(self):
        ad = MsxSceneAdapter()
        raw = raw_scene(enemies=[{"dx": 20, "dy": -3, "x": 0x2020,
                                  "y": 0x7f0, "vx": 0, "slot": 7}])
        sc = ad.build(raw, frame=0)
        self.assertEqual(sc["provenance"]["falling_candidates"], 0)

    def test_drifting_object_not_a_falling_candidate(self):
        ad = MsxSceneAdapter()
        for i, (y, vx) in enumerate(((0x800, 40), (0x800 - 5, 40),
                                     (0x800 - 10, 40))):
            raw = raw_scene(enemies=[{"dx": 20, "dy": -5, "x": 0x2020,
                                      "y": y, "vx": vx, "slot": 9}])
            sc = ad.build(raw, frame=i * 10)
        self.assertEqual(sc["provenance"]["falling_candidates"], 0)


class TestRunnerIntegration(unittest.TestCase):
    """Every scene-consuming MSX runner must route through the adapter
    (static source check — the runners boot the emulator at import, so
    they cannot be imported in unit tests)."""

    RUNNERS = ("scripts/run_semantic.py", "scripts/run_semantic2.py")

    def test_runners_use_the_adapter(self):
        for rel in self.RUNNERS:
            src = open(os.path.join(_REPO, rel)).read()
            self.assertIn("MsxSceneAdapter", src, rel)
            self.assertIn("msx_adapter.build", src, rel)
            # the old inline glue must be gone
            self.assertNotIn('scene["threat"] = wm.threat(scene)',
                             src, rel)
            self.assertNotIn('scene["nearest_enemy"] = wm.nearest(',
                             src, rel)

    def test_worldmodel_entries_carry_slot_identity(self):
        """The adapter's cross-frame tracker needs the generic slot
        identity read_world() now provides (additive key)."""
        src = open(os.path.join(_REPO,
                                "ps1play/agent/worldmodel.py")).read()
        self.assertIn('"slot": s.base', src)


if __name__ == "__main__":
    unittest.main()
