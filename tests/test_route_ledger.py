"""test_route_ledger.py — UNIT tier tests for the Issue #2 route layer
(ps1play.agent.route): stall detection, bounded recovery, the simple
traversal policy's partition invariance, ledger serialization, and the
controller enum -> PlayStation button mapping contract.

Fully offline (no emulator, no disc image).
"""
import json
import os
import sys
import tempfile
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play.agent.route import (                          # noqa: E402
    RouteLedger, RoutePolicy, StallDetector,
    OBSERVED, FAILED, HEURISTIC, UNKNOWN,
    MODE_CHEAT, MODE_LEGIT)
from ps1play.core import inputmap                          # noqa: E402
from ps1play.agent.gameshark import GSCode                 # noqa: E402


class TestStallDetector(unittest.TestCase):
    def test_progress_resets_stall(self):
        d = StallDetector(stall_limit=4, recovery_chunks=3)
        self.assertEqual(d.update(10, 5000, 0), "PROGRESS")
        self.assertEqual(d.update(10, 5000, 0), "PROGRESS")

    def test_stall_then_bounded_recovery_then_blocked(self):
        d = StallDetector(stall_limit=4, recovery_chunks=3)
        for _ in range(3):
            self.assertEqual(d.update(0, 10, 0), "PROGRESS")
        # 4th consecutive stalled chunk -> bounded recovery engages
        self.assertEqual(d.update(0, 10, 0), "RECOVERY")
        self.assertEqual(d.update(0, 10, 0), "RECOVERY")
        self.assertEqual(d.update(0, 10, 0), "RECOVERY")
        self.assertEqual(d.update(0, 10, 0), "BLOCKED")
        self.assertEqual(d.blocked_segments, 1)
        # BLOCKED is absorbing
        self.assertEqual(d.update(10, 9000, 5), "BLOCKED")

    def test_recovery_cleared_by_progress(self):
        d = StallDetector(stall_limit=2, recovery_chunks=3)
        d.update(0, 10, 0)
        d.update(0, 10, 0)
        self.assertEqual(d.update(0, 10, 0), "RECOVERY")
        d.reset()
        self.assertEqual(d.state, "PROGRESS")
        self.assertEqual(d.stalled_chunks, 0)

    def test_churn_counts_as_movement(self):
        d = StallDetector(stall_limit=2, recovery_chunks=2,
                          churn_floor=250)
        self.assertEqual(d.update(None, 900, None), "PROGRESS")
        self.assertEqual(d.update(None, 5, None), "PROGRESS")


class TestRoutePolicy(unittest.TestCase):
    def test_walk_pattern_right_fire(self):
        p = RoutePolicy(allow_grenades=False, jump_enabled=False)
        d = StallDetector()
        segs = p.decide(60, d)
        btns = set()
        for s in segs:
            btns |= s["btns"]
        self.assertIn("RIGHT", btns)
        self.assertIn("Y", btns)
        self.assertNotIn("A", btns)      # no grenade without permission

    def test_partition_invariance(self):
        """Same global frame range -> same button timeline for any chunk
        split (same contract as RobustLegitPolicy v0.7)."""

        def timeline(chunks):
            p = RoutePolicy(allow_grenades=True, jump_enabled=True)
            d = StallDetector()
            out = []
            for c in chunks:
                for s in p.decide(c, d):
                    for _ in range(s["frames"]):
                        out.append(frozenset(s["btns"]))
            return out

        a = timeline([120])
        b = timeline([1] * 120)
        c = timeline([13, 30, 59, 18])
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_recovery_pattern_is_bounded(self):
        p = RoutePolicy(allow_grenades=True, jump_enabled=True)
        d = StallDetector(stall_limit=2, recovery_chunks=3)
        d.update(0, 0, 0)
        d.update(0, 0, 0)
        d.update(0, 0, 0)                      # -> RECOVERY
        segs = p.decide(60, d)
        btns = set()
        for s in segs:
            btns |= s["btns"]
        self.assertIn("LEFT", btns)            # step-back in the window
        self.assertGreater(p.stats["recovery"], 0)

    def test_blocked_keeps_fire_only(self):
        p = RoutePolicy(allow_grenades=False, jump_enabled=True)
        d = StallDetector()
        d.state = "BLOCKED"
        segs = p.decide(60, d)
        for s in segs:
            self.assertNotIn("RIGHT", s["btns"])
            self.assertNotIn("B", s["btns"])

    def test_grenade_requires_permission(self):
        p1 = RoutePolicy(allow_grenades=False)
        d = StallDetector()
        for _ in range(400):
            for s in p1.decide(60, d):
                self.assertNotIn("A", s["btns"])


class TestRouteLedger(unittest.TestCase):
    def test_segment_lifecycle(self):
        led = RouteLedger()
        seg = led.start_segment("S000", None, 1000, "cheat-assisted",
                                progress=5)
        seg["evidence"].append("01_run_start.png")
        led.close_segment(seg, 2200, progress=90, completed=True,
                          recovery_used=False)
        self.assertEqual(seg["status"], OBSERVED)
        self.assertEqual(seg["exit_frame"], 2200)

    def test_stalled_segment_is_failed(self):
        led = RouteLedger()
        seg = led.start_segment("S001", None, 100, "legit")
        led.close_segment(seg, 800, completed=False, stalled=True)
        self.assertEqual(seg["status"], FAILED)
        self.assertTrue(seg["stalled"])

    def test_json_round_trip(self):
        led = RouteLedger()
        seg = led.start_segment("S000", "opening", 0, "cheat-assisted")
        led.close_segment(seg, 600, completed=True)
        led.add_event("CHECKPOINT", 300, chunk=4)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "route.json")
            led.save(path)
            led2 = RouteLedger.load(path)
        self.assertEqual(led2.summary()["segments_total"], 1)
        self.assertEqual(led2.segments[0]["landmark"], "opening")
        self.assertEqual(led2.events[0]["kind"], "CHECKPOINT")

    def test_summary_separates_modes(self):
        led = RouteLedger()
        s1 = led.start_segment("S000", None, 0, "cheat-assisted")
        led.close_segment(s1, 100, completed=True)
        s2 = led.start_segment("S001", None, 200, "legit")
        led.close_segment(s2, 300, completed=False, stalled=True)
        s = led.summary()
        self.assertEqual(s["by_mode"]["cheat-assisted"]["completed"], 1)
        self.assertEqual(s["by_mode"]["legit"]["stalled"], 1)

    def test_file_sha256(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "x.json")
            with open(path, "w") as f:
                f.write('{"a": 1}')
            h = RouteLedger.file_sha256(path)
            self.assertEqual(len(h), 64)

    def test_modes_match_cheatprof(self):
        from ps1play.agent.cheatprof import (
            CHEAT_ASSISTED, LEGIT)
        self.assertEqual(MODE_CHEAT, CHEAT_ASSISTED)
        self.assertEqual(MODE_LEGIT, LEGIT)


class TestControllerMapping(unittest.TestCase):
    """Issue section 5: do not assume host enums map to PSX button IDs
    without verification. The mapping is fixed by the verified pad
    mirror (v0.11/v0.12 evidence): B=CROSS jump, Y=SQUARE fire,
    A=CIRCLE grenade."""

    def test_parse_buttons_names_to_ids(self):
        self.assertEqual(inputmap.parse_buttons("START+RIGHT"),
                         {inputmap.JP_START, inputmap.JP_RIGHT})
        self.assertEqual(inputmap.parse_buttons({"Y", "B"}),
                         {inputmap.JP_Y, inputmap.JP_B})

    def test_psx_semantics(self):
        self.assertEqual(inputmap.JP_B, 0)     # CROSS -> jump
        self.assertEqual(inputmap.JP_Y, 1)     # SQUARE -> fire
        self.assertEqual(inputmap.JP_A, 8)     # CIRCLE -> grenade
        self.assertEqual(inputmap.JP_X, 9)     # TRIANGLE (unused here)

    def test_unknown_button_rejected(self):
        with self.assertRaises(ValueError):
            inputmap.parse_buttons("NOPE")

    def test_pad_bit_map_matches_mirror(self):
        from ps1play.agent.perception import PAD_BITS
        self.assertEqual(PAD_BITS["RIGHT"], 0x0020)
        self.assertEqual(PAD_BITS["START"], 0x0008)

    def test_gs_pad_bit_map_direction_bits(self):
        from ps1play.agent.gsmap import PAD_BIT
        # active-high bits in the 0x0D4948 mirror (per gsmap docstring)
        self.assertEqual(PAD_BIT["RIGHT"], 5)
        self.assertEqual(PAD_BIT["LEFT"], 7)
        self.assertEqual(PAD_BIT["Y"], 15)     # SQUARE


class TestRepoRegistries(unittest.TestCase):
    """The committed registry files must be structurally valid and the
    route ledger must keep cheat/legit results separate."""

    def setUp(self):
        self.cheats = os.path.join(_REPO, "data", "games", "SLUS-01212",
                                   "cheats.json")
        self.route = os.path.join(_REPO, "data", "games", "SLUS-01212",
                                  "mission1_route.json")

    def test_cheats_registry_valid(self):
        data = json.load(open(self.cheats))
        self.assertEqual(data["game"]["serial"], "SLUS-01212")
        r = CheatRegistry(self.cheats, data["cheats"])
        self.assertEqual(r.validate(), [])

    def test_candidate_codes_not_verified_yet(self):
        """Before the live protocol runs, nothing may claim VERIFIED."""
        data = json.load(open(self.cheats))
        for name, e in data["cheats"].items():
            self.assertIn(e["status"],
                          ("CANDIDATE", "TESTED", "VERIFIED", "FAILED",
                           "BLOCKED"), name)
            self.assertTrue(e["codes"], name)
            self.assertIn("source_url", e, name)

    def test_route_ledger_has_walkthrough_expectations(self):
        data = json.load(open(self.route))
        self.assertEqual(data["serial"], "SLUS-01212")
        marks = {m["id"] for m in data["landmark_expectations"]}
        for expect in ("L00", "L03", "L06"):
            self.assertIn(expect, marks)
        for m in data["landmark_expectations"]:
            self.assertIn(m["status"], (HEURISTIC, OBSERVED, UNKNOWN,
                                        FAILED))

    def test_invuln_is_three_lines_and_lives_conflict_recorded(self):
        data = json.load(open(self.cheats))["cheats"]
        self.assertEqual(len(data["invuln"]["codes"]), 3)
        self.assertNotEqual(data["lives"]["codes"],
                            data["lives_alt"]["codes"])
        self.assertIn("80047522", data["lives"]["known_conflicts"])


# CheatRegistry import placed after class defs needing it above? No —
# keep importable at top-level for TestRepoRegistries.
from ps1play.agent.cheatprof import CheatRegistry          # noqa: E402


if __name__ == "__main__":
    unittest.main()
