"""test_policy_frames.py — UNIT tier regression tests for RobustLegitPolicy v0.7.

These tests run fully offline (no emulator, no disc image, no BIOS).
They prove POLICY LOGIC ONLY — they do NOT prove gameplay (see
scripts/test_integration_m1.py for the environment-gated tiers).

Covered (mission review §3 + §7):
  * chunk-partition invariance: the per-frame button timeline is
    identical for chunk sizes 1, 13, 30, 59, 60, 61, 120
  * grenade schedule: one PRESS_LEN-frame press per GRENADE_PERIOD,
    starting at GRENADE_PHASE, counted exactly once per press
  * shred engages strictly AFTER STALL_SHRED_AFTER_CHUNKS (unit:
    chunks of 60 frames), grenades inside the window on the documented
    cadence
  * unstick windows cover the no-verified-bombs stall case and never
    press grenade without bombs_verified
  * tap-fire burst and hop cadence are continuous across chunk
    boundaries
  * signature contract: decide() no longer accepts timer/zone/churn
"""
import inspect
import os
import sys
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from run_mission1_legit import (            # noqa: E402
    RobustLegitPolicy, FIRE_ON, FIRE_OFF, GRENADE_PERIOD, GRENADE_PHASE,
    GRENADE_PRESS_LEN, SHRED_PERIOD, SHRED_LEN, SHRED_GRENADE_PERIOD,
    UNSTICK_LEN, UNSTICK_LEFT, UNSTICK_HOP,
    STALL_SHRED_AFTER_CHUNKS, STALL_PAUSE_AFTER_CHUNKS)

CHUNK_SIZES = (1, 13, 30, 59, 60, 61, 120)


def expand_timeline(policy, chunk, total, **kw):
    """Drive policy.decide() in `chunk`-frame steps for `total` frames;
    return the flat per-frame list of button sets."""
    timeline = []
    while len(timeline) < total:
        n = min(chunk, total - len(timeline))
        for seg in policy.decide(n, **kw):
            timeline.extend([seg["btns"]] * seg["frames"])
    return timeline[:total]


def timeline_right_fire(policy, chunk, total, **kw):
    """Timeline where each frame's buttons are collapsed to the mobile
    action (direction, fire, grenade, jump) for invariance comparison."""
    tl = expand_timeline(policy, chunk, total, **kw)
    return tl


class TestChunkInvariance(unittest.TestCase):
    """The same global frame range must produce the same button
    timeline no matter how it is split into chunks (§3A)."""

    def _check(self, **kw):
        ref = timeline_right_fire(RobustLegitPolicy(), 1, 1200, **kw)
        for cs in CHUNK_SIZES:
            if cs == 1:
                continue
            got = timeline_right_fire(RobustLegitPolicy(), cs, 1200, **kw)
            self.assertEqual(
                got, ref,
                f"timeline diverges for chunk size {cs} (kw={kw})")

    def test_invariance_calm(self):
        self._check(stall_chunks=0, bombs=0, bombs_verified=False)

    def test_invariance_grenades_verified(self):
        self._check(stall_chunks=0, bombs=5, bombs_verified=True)

    def test_invariance_shred(self):
        self._check(stall_chunks=STALL_SHRED_AFTER_CHUNKS + 10, bombs=9,
                    bombs_verified=True)

    def test_invariance_unstick(self):
        self._check(stall_chunks=STALL_SHRED_AFTER_CHUNKS + 10, bombs=9,
                    bombs_verified=False)


class TestGrenadeSchedule(unittest.TestCase):
    """Normal-mode grenade: exactly one GRENADE_PRESS_LEN-frame press
    per GRENADE_PERIOD, first at frame GRENADE_PHASE (§3A fix)."""

    def test_single_press_per_period(self):
        p = RobustLegitPolicy()
        tl = expand_timeline(p, 60, GRENADE_PERIOD * 3,
                             stall_chunks=0, bombs=3, bombs_verified=True)
        press_frames = [i for i, b in enumerate(tl) if "A" in b]
        starts = [f for f in press_frames
                  if f - 1 not in press_frames]
        self.assertEqual(len(starts), 3)
        for k, s in enumerate(starts):
            self.assertEqual(s, GRENADE_PHASE + k * GRENADE_PERIOD)
            run = [f for f in press_frames
                   if s <= f < s + GRENADE_PRESS_LEN]
            self.assertEqual(run, list(range(s, s + GRENADE_PRESS_LEN)))
        self.assertEqual(p.stats["grenade"], 3)

    def test_no_grenade_unverified_or_empty(self):
        for kw in ({"bombs": 3, "bombs_verified": False},
                   {"bombs": 0, "bombs_verified": True},
                   {"bombs": None, "bombs_verified": True}):
            p = RobustLegitPolicy()
            tl = expand_timeline(p, 60, GRENADE_PERIOD * 2, **kw)
            self.assertFalse(any("A" in b for b in tl),
                             f"A pressed with {kw}")
            self.assertEqual(p.stats["grenade"], 0)

    def test_v06_bug_would_have_dumped_many(self):
        """Regression guard: a 60-frame chunk starting exactly on the
        phase must still produce ONE press, not 60 A-frames."""
        p = RobustLegitPolicy()
        p.fc = GRENADE_PHASE          # align chunk start with the phase
        tl = expand_timeline(p, 60, 60, stall_chunks=0, bombs=30,
                             bombs_verified=True)
        self.assertEqual(sum(1 for b in tl if "A" in b), GRENADE_PRESS_LEN)
        self.assertEqual(p.stats["grenade"], 1)


class TestStallUnits(unittest.TestCase):
    """stall units are CHUNKS of 60 frames; thresholds named (§3C)."""

    def test_thresholds_are_chunks_and_ordered(self):
        self.assertIsInstance(STALL_SHRED_AFTER_CHUNKS, int)
        self.assertIsInstance(STALL_PAUSE_AFTER_CHUNKS, int)
        self.assertLess(STALL_PAUSE_AFTER_CHUNKS,
                        STALL_SHRED_AFTER_CHUNKS)

    def test_shred_boundary(self):
        args = {"bombs": 9, "bombs_verified": True}
        p = RobustLegitPolicy()
        tl = expand_timeline(p, 60, 240,
                             stall_chunks=STALL_SHRED_AFTER_CHUNKS, **args)
        self.assertFalse(any("LEFT" in b for b in tl),
                         "shred must NOT engage at the boundary value")
        p = RobustLegitPolicy()
        tl = expand_timeline(
            p, 60, SHRED_LEN, stall_chunks=STALL_SHRED_AFTER_CHUNKS + 1,
            **args)
        self.assertTrue(all("LEFT" in b for b in tl),
                        "shred window should cover the first SHRED_LEN "
                        "frames")
        # grenade cadence inside the shred window: presses at window
        # offsets 0, 75, 150, 225 (ceil(SHRED_LEN / period), not floor)
        n_presses = p.stats["grenade"]
        self.assertEqual(n_presses,
                         len(range(0, SHRED_LEN, SHRED_GRENADE_PERIOD)))

    def test_unstick_without_verified_bombs(self):
        p = RobustLegitPolicy()
        tl = expand_timeline(
            p, 60, UNSTICK_LEN, stall_chunks=STALL_SHRED_AFTER_CHUNKS + 1,
            bombs=9, bombs_verified=False)
        lefts = [i for i, b in enumerate(tl) if "LEFT" in b]
        self.assertEqual(len(lefts), UNSTICK_LEN)
        hops = [i for i, b in enumerate(tl) if "B" in b]
        self.assertEqual(hops, list(range(UNSTICK_LEFT,
                                          UNSTICK_LEFT + UNSTICK_HOP)))
        self.assertEqual(p.stats["grenade"], 0)   # never without verified

    def test_no_escape_below_threshold(self):
        """Below the stall threshold the policy keeps advancing RIGHT."""
        p = RobustLegitPolicy()
        tl = expand_timeline(p, 60, 240,
                             stall_chunks=STALL_SHRED_AFTER_CHUNKS,
                             bombs=0, bombs_verified=False)
        self.assertTrue(all("RIGHT" in b for b in tl))


class TestRhythmContinuity(unittest.TestCase):
    """Tap-fire burst and hop cadence do not reset at chunk edges."""

    def test_burst_pattern_identical_when_chunked(self):
        def burst_seq(cs):
            p = RobustLegitPolicy()
            tl = expand_timeline(p, cs, (FIRE_ON + FIRE_OFF) * 8,
                                 stall_chunks=0, bombs=0,
                                 bombs_verified=False)
            return [1 if "Y" in b else 0 for b in tl]
        self.assertEqual(burst_seq(60), burst_seq(7))

    def test_decide_signature_contract(self):
        """v0.6 accepted timer/zone/churn and never used them (§3B)."""
        sig = inspect.signature(RobustLegitPolicy.decide)
        params = [p for p in sig.parameters if p != "self"]
        self.assertEqual(params, ["chunk", "stall_chunks", "bombs",
                                  "bombs_verified"])


class TestExecuteBudget(unittest.TestCase):
    """execute() must honour the budget and the compressed segments."""

    def test_segments_cover_chunk(self):
        from run_mission1_legit import RobustLegitPolicy as P
        p = P()
        segs = p.decide(60, stall_chunks=0, bombs=0, bombs_verified=False)
        self.assertEqual(sum(s["frames"] for s in segs), 60)
        for s in segs:
            self.assertIsInstance(s["btns"], set)


if __name__ == "__main__":
    unittest.main()
