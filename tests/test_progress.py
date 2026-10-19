"""Level-A unit tests: progress.py (§4). Synthetic series only —
covers valid monotonic, false candidate, camera lock, reset, wrap,
and invalidation/stale handling."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ps1play.agent.progress import (                            # noqa: E402
    rank_candidates, ProgressSignal)


def _series(vals):
    return list(vals)


class TestRankCandidates(unittest.TestCase):
    def _trials(self, idle, right, left, run):
        return {0xCA2E2: {"idle": _series(idle),
                          "right": _series(right),
                          "left": _series(left),
                          "run": _series(run)}}

    def test_valid_monotonic_candidate_passes(self):
        trials = self._trials(
            idle=[100, 100, 101, 100],
            right=[100, 180, 260, 340],
            left=[100, 40, 20, 10],
            run=[100, 160, 220, 280, 340, 400])
        out = rank_candidates(trials)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0]["valid"])
        self.assertEqual(out[0]["addr"], 0xCA2E2)

    def test_false_candidate_right_only_rejected(self):
        # rises under RIGHT but does NOT fall under LEFT (e.g. a timer
        # or a menu cursor) — must be rejected
        trials = self._trials(
            idle=[5, 5, 5, 5],
            right=[5, 200, 400, 600],
            left=[5, 5, 5, 5],                 # <- no left response
            run=[5, 200, 400, 600, 800, 1000])
        res = rank_candidates(trials, return_all=True)
        self.assertEqual(res["valid"], [])     # nothing trustworthy
        self.assertFalse(res["all"][0]["valid"])

    def test_noisy_candidate_rejected(self):
        # right/left symmetric but non-monotonic over the run (dips)
        trials = self._trials(
            idle=[50, 50, 50, 50],
            right=[50, 150, 250, 350],
            left=[50, 10, 5, 2],
            run=[50, 200, 100, 260, 160, 320])   # dips < -4
        res = rank_candidates(trials, return_all=True)
        self.assertEqual(res["valid"], [])
        self.assertFalse(res["all"][0]["valid"])

    def test_idle_drift_rejected(self):
        trials = self._trials(
            idle=[50, 90, 130, 170],           # drifts while idle
            right=[50, 150, 250, 350],
            left=[50, 10, 5, 2],
            run=[50, 150, 250, 350, 450, 550])
        res = rank_candidates(trials, return_all=True)
        self.assertEqual(res["valid"], [])
        self.assertFalse(res["all"][0]["valid"])

    def test_no_candidates_returns_empty(self):
        trials = self._trials(
            idle=[1, 2, 3, 4], right=[1, 2, 3, 4],
            left=[1, 2, 3, 4], run=[1, 2, 3, 4, 5, 6])
        self.assertEqual(rank_candidates(trials), [])

    def test_return_all_preserves_rejections(self):
        trials = self._trials(
            idle=[1, 2, 3, 4], right=[1, 2, 3, 4],
            left=[1, 2, 3, 4], run=[1, 2, 3, 4, 5, 6])
        res = rank_candidates(trials, return_all=True)
        self.assertEqual(len(res["all"]), 1)
        self.assertEqual(res["valid"], [])


class TestProgressSignal(unittest.TestCase):
    def test_unverified_never_claims_progress(self):
        s = ProgressSignal(0xCA2E2, verified=False)
        s.update(10, churn=5000)
        s.update(80, churn=5000)
        self.assertFalse(s.claims_progress)
        d = s.to_dict()
        self.assertEqual(d["status"], "UNVERIFIED")

    def test_progress_and_stall_states(self):
        s = ProgressSignal(0x1000, verified=True, lock_churn=3500)
        self.assertEqual(s.update(0, churn=1000), ProgressSignal.PROGRESS)
        self.assertEqual(s.update(60, churn=1000), ProgressSignal.PROGRESS)
        # frozen with low churn repeatedly -> STALLED
        for _ in range(5):
            st = s.update(60, churn=300)
        self.assertEqual(st, ProgressSignal.STALLED)

    def test_camera_lock_distinct_from_stall(self):
        s = ProgressSignal(0x1000, verified=True, lock_churn=3500)
        s.update(100, churn=500)
        st = s.update(100, churn=9000)          # frozen + high churn
        self.assertEqual(st, ProgressSignal.CAMERA_LOCKED)

    def test_reset_detection(self):
        s = ProgressSignal(0x1000, verified=True, reset_drop=100)
        s.update(500, churn=1000)
        s.update(560, churn=1000)
        st = s.update(30, churn=4000)           # camera jumped back
        self.assertEqual(st, ProgressSignal.RESET)

    def test_u16_wraparound(self):
        s = ProgressSignal(0x1000, verified=True)
        s.update(0xFFF0, churn=1000)
        st = s.update(0x0010, churn=1000)       # wrapped +0x20
        self.assertEqual(st, ProgressSignal.PROGRESS)

    def test_invalidate_makes_signal_dead(self):
        s = ProgressSignal(0x1000, verified=True)
        s.update(100, churn=100)
        s.invalidate("mission reload remap")
        self.assertFalse(s.verified)
        self.assertEqual(s.status, ProgressSignal.INVALID)
        self.assertFalse(s.claims_progress)
        # updates after invalidation do not resurrect it
        s.update(200, churn=9000)
        self.assertEqual(s.status, ProgressSignal.INVALID)

    def test_to_dict_carries_evidence(self):
        s = ProgressSignal(0xCA2E2, verified=True)
        s.update(5, churn=100)
        d = s.to_dict()
        self.assertEqual(d["addr"], "0xca2e2")
        self.assertIn("counts", d)
        self.assertTrue(d["claims_progress"])


if __name__ == "__main__":
    unittest.main()
