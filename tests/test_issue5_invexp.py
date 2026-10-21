"""Offline tests for issue5_invincible_explore.py pure logic.

Covers the MinTracker dropper extraction (u16 + u8, band + drop) and
the retry-pattern cycle.  The exploration mode itself is DISCLOSED and
never counts as a no-cheat clear; these tests pin the accounting."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "scripts"))

import issue5_invincible_explore as ie  # noqa: E402

import unittest  # noqa: E402


class FakePlay:
    def __init__(self):
        self.mem = FakeMem()


class FakeMem:
    """Minimal RAM stub for MinTracker (0x1FC000 bytes)."""

    SIZE = 0x1FC000

    def __init__(self):
        self.ram = np.zeros(self.SIZE, dtype=np.uint8)

    def set_u16(self, addr, v):
        self.ram[addr] = v & 0xFF
        self.ram[addr + 1] = (v >> 8) & 0xFF


class TestMinTracker(unittest.TestCase):
    def setUp(self):
        self.play = FakePlay()

    def test_u16_dropper_detected(self):
        mem = self.play.mem
        mem.set_u16(0xCABE4, 136)          # full-HP-like word
        tr = ie.MinTracker(self.play)
        mem.set_u16(0xCABE4, 60)           # took damage
        tr.sample(self.play)
        cands = tr.droppers()
        self.assertIn((0xCABE4, 2), cands)

    def test_u8_dropper_detected(self):
        mem = self.play.mem
        mem.ram[0xCA2F7] = 120             # odd-address u8 word
        tr = ie.MinTracker(self.play)
        mem.ram[0xCA2F7] = 30
        tr.sample(self.play)
        cands = tr.droppers()
        self.assertIn((0xCA2F7, 1), cands)

    def test_no_drop_no_candidate(self):
        mem = self.play.mem
        mem.set_u16(0xCABE4, 136)
        tr = ie.MinTracker(self.play)
        tr.sample(self.play)               # unchanged
        self.assertEqual(
            [(a, w) for a, w in tr.droppers() if a == 0xCABE4], [])

    def test_band_excludes_outliers(self):
        mem = self.play.mem
        mem.set_u16(0x1234, 50000)         # far out of the u16 band
        tr = ie.MinTracker(self.play)
        mem.set_u16(0x1234, 40000)
        tr.sample(self.play)
        # the u16 tracker must reject it (the u8 view legitimately
        # sees the two bytes move)
        self.assertEqual(
            [(a, w) for a, w in tr.droppers()
             if a == 0x1234 and w == 2], [])

    def test_value_for_full_hp(self):
        """The freeze must engage at the mission-start (full) value,
        never at the post-death 0 (inv15 lesson)."""
        mem = self.play.mem
        mem.set_u16(0xCABE4, 136)
        tr = ie.MinTracker(self.play)
        mem.set_u16(0xCABE4, 0)            # death dropped it to 0
        tr.sample(self.play)
        self.assertEqual(tr.value_for(0xCABE4, 2), 136)

    def test_retry_pattern_cycles(self):
        self.assertEqual([ie.pick_retry_pattern(i) for i in range(5)],
                         [0, 1, 2, 3, 0])


class TestLivesScan(unittest.TestCase):
    """The lives counter drops EXACTLY -1 per death and is stable
    between deaths (the strict-series protocol that VERIFIED the
    grenades counter).  Freezing it makes the game's own checkpoint
    respawn an infinite-lives loop — the operational invincibility."""

    def test_strict_series_finds_lives_u8(self):
        play = FakePlay()
        mem = play.mem
        # place a lives-like u8 at 0x47500
        mem.ram[0x47500] = 5
        snaps = []
        for v in (5, 4, 3):                # two deaths
            mem.ram[0x47500] = v
            snaps.append(ie.death_snapshot(play))
        cands = ie.lives_candidates(play, [snaps])
        widths = {a for a, w in cands if a == 0x47500}
        self.assertTrue(widths, "lives addr not found at all")

    def test_strict_series_rejects_non_decayers(self):
        play = FakePlay()
        mem = play.mem
        mem.ram[0x47501] = 9               # neighbor: u16 view is out
        mem.ram[0x47600] = 100             # decays by 2 per death
        snaps = []
        for lv, dv in ((5, 100), (4, 98), (3, 96)):
            mem.ram[0x47500] = lv          # strict -1: a real lives
            mem.ram[0x47600] = dv          # -2 per death: not lives
            snaps.append(ie.death_snapshot(play))
        cands = ie.lives_candidates(play, [snaps])
        self.assertIn((0x47500, 1), cands)
        self.assertNotIn((0x47600, 1), cands)


if __name__ == "__main__":
    unittest.main()
