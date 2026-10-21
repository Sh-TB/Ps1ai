"""test_explore_cadence.py — UNIT regression tests for the cheat-assisted
exploration cadence contract (issue #5 continuation §2).

Offline (no emulator): fakes for core/session/mem prove SCHEDULING
LOGIC ONLY — they do NOT prove gameplay or RAM effects.

Contract under test:
  C1  segment buttons are actually APPLIED in every branch (the pad
      latches; the pre-fix non-pit branch computed `btns` and never
      set it — the player stood still for the whole run)
  C2  the GameShark engine ticks after EVERY run_frame in every
      branch (freeze never silently stops)
  C3  the pit-cadence button schedule derives from a GLOBAL frame
      phase — chunk partitioning cannot change the timeline
  C4  buttons are set BEFORE the first frame of each gs_run group
      (pad latching means a late set_buttons is next-frame input)
  C5  shared recovery helpers (mission.recover / responsive /
      ensure_mission / run_mission1_legit.recover_v2) thread an
      optional per-frame GS tick so freezes survive recovery windows
"""
import os
import sys
import unittest
from types import SimpleNamespace

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from issue5_explore_invuln import (                    # noqa: E402
    gs_run, run_segment_frames, PIT_B_PERIOD, PIT_B_LEN,
    PIT_AA_PERIOD, PIT_AA_LEN)


# ------------------------------------------------------------------
# fakes
# ------------------------------------------------------------------
class FakeCore:
    """Records the (frame, buttons) timeline; latches buttons exactly
    like the libretro pad (set_buttons persists until changed)."""

    def __init__(self):
        self.buttons = frozenset()
        self.frames = 0
        self.timeline = []

    def set_buttons(self, spec):
        self.buttons = frozenset(spec) if spec else frozenset()

    def run_frame(self):
        self.frames += 1
        self.timeline.append((self.frames, frozenset(self.buttons)))

    def run(self, frames, buttons=None):
        if buttons is not None:
            self.set_buttons(buttons)
        for _ in range(frames):
            self.run_frame()


class FakeGS:
    def __init__(self):
        self.ticks = 0

    def tick(self):
        self.ticks += 1


class FakeSession:
    def __init__(self):
        self.gs = FakeGS()


class FakeMem:
    def u16(self, addr):
        return 0

    def snapshot(self):
        # fresh random bytes each call -> churn > 900 always
        return np.random.default_rng(int(np.random.randint(1 << 30))). \
            integers(0, 255, 64, dtype=np.uint8)


def make_p():
    return SimpleNamespace(core=FakeCore(), mem=FakeMem(),
                           _advance=lambda: 0)


def segs_from_buttons(buttons_per_60, n=1):
    """Policy-shaped segments: n 60-frame segments per button set."""
    return [{"btns": list(b), "frames": 60} for b in buttons_per_60
            for _ in range(n)]


# ------------------------------------------------------------------
# C1 + C2 + C4: gs_run basics
# ------------------------------------------------------------------
class TestGsRun(unittest.TestCase):

    def test_buttons_applied_before_first_frame(self):
        p, s = make_p(), FakeSession()
        gs_run(p, s, 10, {"RIGHT", "Y"})
        first = p.core.timeline[0]
        self.assertIn("RIGHT", first[1])
        self.assertIn("Y", first[1])
        # C4: the FIRST frame already sees the new buttons (no 1-frame
        # drift from a previous empty set)
        self.assertEqual(p.core.timeline[0][1], frozenset({"RIGHT", "Y"}))

    def test_empty_buttons_release_pad(self):
        p, s = make_p(), FakeSession()
        p.core.set_buttons({"RIGHT"})
        gs_run(p, s, 5, set())
        self.assertEqual(p.core.timeline[0][1], frozenset())

    def test_tick_every_frame(self):
        p, s = make_p(), FakeSession()
        gs_run(p, s, 37, {"RIGHT"})
        self.assertEqual(s.gs.ticks, 37)
        self.assertEqual(p.core.frames, 37)

    def test_phase_accumulates(self):
        p, s = make_p(), FakeSession()
        ph = gs_run(p, s, 30, {"RIGHT"}, 100)
        ph = gs_run(p, s, 15, set(), ph)
        self.assertEqual(ph, 145)


# ------------------------------------------------------------------
# C1 + C2: run_segment_frames both branches
# ------------------------------------------------------------------
class TestRunSegmentFrames(unittest.TestCase):

    def test_nonpit_applies_segment_buttons(self):
        p, s = make_p(), FakeSession()
        segs = [{"btns": ["RIGHT"], "frames": 20},
                {"btns": ["RIGHT", "Y"], "frames": 20},
                {"btns": [], "frames": 20}]
        run_segment_frames(p, s, segs, pit_mode=False)
        btns0 = p.core.timeline[0][1]
        btns25 = p.core.timeline[25][1]
        btns45 = p.core.timeline[45][1]
        self.assertEqual(btns0, frozenset({"RIGHT"}))
        self.assertEqual(btns25, frozenset({"RIGHT", "Y"}))
        self.assertEqual(btns45, frozenset())
        # released at the end (no leakage into the next caller)
        self.assertEqual(p.core.buttons, frozenset())

    def test_tick_equals_frames_every_branch(self):
        for pit in (False, True):
            p, s = make_p(), FakeSession()
            segs = [{"btns": ["RIGHT"], "frames": 60},
                    {"btns": ["Y"], "frames": 60}]
            run_segment_frames(p, s, segs, pit_mode=pit)
            self.assertEqual(s.gs.ticks, 120, f"pit={pit}")
            self.assertEqual(p.core.frames, 120, f"pit={pit}")

    def test_pit_mode_layers_hazard_cadence(self):
        p, s = make_p(), FakeSession()
        segs = [{"btns": ["RIGHT"], "frames": PIT_B_PERIOD}]
        run_segment_frames(p, s, segs, pit_mode=True)
        with_b = [f for f, b in p.core.timeline if "B" in b]
        self.assertEqual(len(with_b), PIT_B_LEN)
        self.assertEqual(with_b[0], 1)          # burst starts at phase 0
        with_aa = [f for f, b in p.core.timeline if "UP" in b]
        self.assertEqual(len(with_aa), PIT_AA_LEN)


# ------------------------------------------------------------------
# C3: chunk-partition independence (the §2 regression demand)
# ------------------------------------------------------------------
class TestPartitionIndependence(unittest.TestCase):

    def _timeline(self, total, split, pit):
        p, s = make_p(), FakeSession()
        segs, left = [], total
        for n in split:
            segs.append({"btns": ["RIGHT"], "frames": n})
            left -= n
        assert left == 0
        run_segment_frames(p, s, segs, pit_mode=pit)
        return [b for _, b in p.core.timeline]

    def test_pit_cadence_independent_of_segment_split(self):
        total = 180
        ref = self._timeline(total, [total], True)
        for split in ([60, 60, 60], [30, 90, 60], [1, 59, 120],
                      [45, 45, 45, 45], [119, 61]):
            self.assertEqual(self._timeline(total, split, True), ref,
                             f"split {split} changed the pit schedule")

    def test_nonpit_independent_of_segment_split(self):
        total = 120
        ref = self._timeline(total, [total], False)
        for split in ([60, 60], [30, 30, 30, 30], [1, 119], [7, 113]):
            self.assertEqual(self._timeline(total, split, False), ref,
                             f"split {split} changed the schedule")


# ------------------------------------------------------------------
# C5: recovery helpers thread the GS tick
# ------------------------------------------------------------------
class TestRecoveryTickThreading(unittest.TestCase):

    def test_mission_recover_ticks_every_frame(self):
        import mission
        p, s = make_p(), FakeSession()
        mission.recover(p, log=lambda *a: None, tick=s.gs.tick)
        self.assertEqual(s.gs.ticks, 15 + 90)
        self.assertEqual(p.core.frames, 105)

    def test_mission_recover_untouched_without_tick(self):
        import mission
        p, s = make_p(), FakeSession()
        mission.recover(p, log=lambda *a: None)
        self.assertEqual(s.gs.ticks, 0)
        self.assertEqual(p.core.frames, 105)

    def test_recover_v2_ticks_every_frame(self):
        import run_mission1_legit as rml
        orig = rml.responsive_live
        rml.responsive_live = lambda p: (True, (0, 0))
        try:
            p, s = make_p(), FakeSession()
            ok = rml.recover_v2(p, log=lambda *a: None, tick=s.gs.tick)
            self.assertTrue(ok)
            self.assertEqual(s.gs.ticks, 6 + 75)
        finally:
            rml.responsive_live = orig

    def test_responsive_ticks_every_frame(self):
        import mission
        p, s = make_p(), FakeSession()
        mission.responsive(p, tick=s.gs.tick)
        # 6 + 3*10 + 8 + 6 + 60
        self.assertEqual(s.gs.ticks, 110)
        self.assertEqual(p.core.frames, 110)


if __name__ == "__main__":
    unittest.main()
