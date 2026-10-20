"""test_cheat_profiles.py — UNIT tier tests for the Issue #2 cheat
experiment classes (ps1play.agent.cheatprof + gameshark).

Fully offline: a fake RAM numpy view replaces the emulator. They prove
CONTRACT LOGIC ONLY — parse validity, opt-in enforcement, profile
isolation, activation/disable byte restoration, registry gating. They
do NOT prove any in-game cheat effect (that is the live protocol in
scripts/validate_cheats.py).
"""
import json
import os
import sys
import tempfile
import unittest

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

from ps1play.agent.gameshark import GameShark, GSCode     # noqa: E402
from ps1play.agent.cheatprof import (                     # noqa: E402
    CheatSession, CheatRegistry, ProfileViolation,
    CHEAT_ASSISTED, LEGIT, PROFILES,
    ST_CANDIDATE, ST_VERIFIED, ST_FAILED)

RAM_BYTES = 0x200000


class FakeCore:
    """Headless stand-in: set_buttons + run_frame only."""

    def __init__(self, play):
        self._play = play
        self._btns = set()

    def set_buttons(self, btns):
        self._btns = set(btns)

    def run_frame(self):
        self._play.t += 1


class FakePlay:
    """Minimal stand-in exposing .mem.ram (writable), .core and .t."""

    def __init__(self):
        rng = np.random.default_rng(7)
        self.ram = rng.integers(0, 256, RAM_BYTES, dtype=np.uint8)
        from ps1play.core.memory import MemoryView
        self.mem = MemoryView(self.ram)
        self.t = 0
        self.core = FakeCore(self)

    def u16(self, a):
        return int(self.ram[a]) | (int(self.ram[a + 1]) << 8)


class TestGSParsing(unittest.TestCase):
    def test_w16_code_parses(self):
        c = GSCode("8002DCE6 2400")
        self.assertEqual(c.kind, "w16")
        self.assertEqual(c.addr, 0x2DCE6 & 0x1FFFFF)
        self.assertEqual(c.val, 0x2400)

    def test_w8_code_parses(self):
        c = GSCode("300D4213 00FF")
        self.assertEqual(c.kind, "w8")
        self.assertEqual(c.val, 0xFF)

    def test_invalid_rejected(self):
        for bad in ("8002DCE6", "XYZ", "8002DCE6 2400 extra",
                    "9002DCE6 2400", ""):
            with self.assertRaises(ValueError, msg=bad):
                GSCode(bad)

    def test_lowercase_ok(self):
        c = GSCode("8002dce6 2400")
        self.assertEqual(c.raw, "8002DCE6 2400")


class TestGameSharkEnableDisable(unittest.TestCase):
    def setUp(self):
        self.play = FakePlay()
        self.gs = GameShark(self.play.mem)
        self.addr = 0x2DCE6
        self.orig = bytes(self.play.ram[self.addr:self.addr + 2])

    def test_enable_patches_and_disable_restores(self):
        self.gs.enable("t", [GSCode("8002DCE6 2400")])
        self.gs.tick()
        self.assertEqual(self.play.u16(0x2DCE6), 0x2400)
        self.gs.disable("t")
        self.assertEqual(bytes(self.play.ram[0x2DCE6:0x2DCE6 + 2]),
                         self.orig)

    def test_disable_unknown_returns_false(self):
        self.assertFalse(self.gs.disable("nope"))

    def test_tick_reapplies_every_frame(self):
        self.gs.enable("t", [GSCode("8002DCE6 2400")])
        for _ in range(5):
            self.play.ram[0x2DCE6:0x2DCE6 + 2] = (0xAA, 0xBB)
            self.gs.tick()
            self.assertEqual(self.play.u16(0x2DCE6), 0x2400)

    def test_tick_interval_logging_on_change(self):
        s = CheatSession(self.play, CHEAT_ASSISTED, opt_in=True)
        s.enable("b", ["800398BE 2400"])
        s.run_frames(5, set())
        s.disable("b")
        s.run_frames(5, set())
        s.finalize_intervals()
        on = [iv for iv in s.intervals if iv["cheats"] == ["b"]]
        self.assertEqual(len(on), 1)
        self.assertEqual(on[0]["end"] - on[0]["start"], 5)


class TestCheatSessionOptIn(unittest.TestCase):
    def setUp(self):
        self.play = FakePlay()

    def test_cheat_mode_requires_opt_in(self):
        with self.assertRaises(ProfileViolation):
            CheatSession(self.play, CHEAT_ASSISTED, opt_in=False)

    def test_cheat_mode_with_opt_in_enables(self):
        s = CheatSession(self.play, CHEAT_ASSISTED, opt_in=True)
        s.enable("bombs", ["800398BE 2400"])
        self.assertEqual(s.active_names(), ["bombs"])
        self.assertIn("bombs", s.gs.enabled)

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ProfileViolation):
            CheatSession(self.play, "SOMETHING_ELSE", opt_in=True)

    def test_legit_refuses_enable(self):
        s = CheatSession(self.play, LEGIT)
        with self.assertRaises(ProfileViolation):
            s.enable("bombs", ["800398BE 2400"])
        self.assertEqual(s.active_names(), [])

    def test_legit_assert_clean_violation(self):
        s = CheatSession(self.play, LEGIT)
        # force-enable behind the session's back -> hard violation
        s.gs.enable("rogue", [GSCode("800398BE 2400")])
        with self.assertRaises(ProfileViolation):
            s.assert_clean("mid-run")

    def test_legit_assert_clean_passes_when_clean(self):
        s = CheatSession(self.play, LEGIT)
        self.assertTrue(s.assert_clean("pre-run"))

    def test_intervals_record_frames(self):
        s = CheatSession(self.play, CHEAT_ASSISTED, opt_in=True)
        s.enable("bombs", ["800398BE 2400"])
        s.run_frames(30, set())
        s.disable("bombs")
        s.run_frames(10, set())
        s.finalize_intervals()
        on = [iv for iv in s.intervals if iv["cheats"] == ["bombs"]]
        self.assertTrue(on)
        self.assertGreaterEqual(on[0]["end"] - on[0]["start"], 30)
        off = [iv for iv in s.intervals if not iv["cheats"]]
        self.assertTrue(off)


REG = {
    "bombs": {"name": "bombs", "effect": "infinite bombs",
              "codes": ["800398BE 2400"], "status": ST_VERIFIED},
    "invuln": {"name": "invuln", "effect": "invulnerability",
               "codes": ["8003273E 2400", "80032764 00C8",
                         "80032766 2405"], "status": ST_CANDIDATE},
}


class TestCheatRegistry(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "cheats.json")
            r = CheatRegistry(path, dict(REG))
            r.save()
            r2 = CheatRegistry.load(path)
            self.assertEqual(r2.entries["bombs"]["status"], ST_VERIFIED)
            self.assertEqual(len(r2.entries["invuln"]["codes"]), 3)

    def test_validate_detects_missing_fields(self):
        bad = {"x": {"name": "x", "status": "WEIRD"}}
        r = CheatRegistry("/tmp/never.json", bad)
        problems = r.validate()
        self.assertTrue(any("codes" in p for p in problems))
        self.assertTrue(any("status" in p for p in problems))

    def test_verified_gating(self):
        r = CheatRegistry("/tmp/never.json", dict(REG))
        self.assertEqual(r.verified_names(), ["bombs"])
        codes = r.codes_for(["bombs"])
        self.assertEqual(codes, [("bombs", "800398BE 2400")])

    def test_candidate_code_refused(self):
        r = CheatRegistry("/tmp/never.json", dict(REG))
        with self.assertRaises(ProfileViolation):
            r.codes_for(["invuln"])          # CANDIDATE, not VERIFIED

    def test_unknown_name_refused(self):
        r = CheatRegistry("/tmp/never.json", dict(REG))
        with self.assertRaises(ProfileViolation):
            r.codes_for(["ghost"])

    def test_update_status_transitions(self):
        r = CheatRegistry("/tmp/never.json", dict(REG))
        r.update_status("invuln", ST_VERIFIED,
                        evidence={"protocol": "unit-test placeholder"})
        self.assertEqual(r.entries["invuln"]["status"], ST_VERIFIED)
        self.assertTrue(r.entries["invuln"]["evidence"])
        with self.assertRaises(ValueError):
            r.update_status("invuln", "NOT_A_STATUS")

    def test_profiles_are_the_documented_pair(self):
        self.assertEqual(PROFILES,
                         (CHEAT_ASSISTED, LEGIT))


if __name__ == "__main__":
    unittest.main()
