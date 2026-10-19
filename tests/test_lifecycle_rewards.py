"""Level-A unit tests: lifecycle.py (§6) + rewards.py (§12)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ps1play.agent.lifecycle import Lifecycle                 # noqa: E402
from ps1play.agent.rewards import RewardAudit                 # noqa: E402


class TestLifecycle(unittest.TestCase):
    def _happy_path(self, lc):
        lc.transition("GAME_IDENTIFIED", "boot ok")
        lc.transition("TITLE_OR_MENU", "menus seen")
        lc.transition("GAMEPLAY_CANDIDATE", "activity gate")
        lc.transition("INPUT_CONTROL_VERIFIED", "responsive()")
        lc.transition("MISSION_1_VERIFIED", "mission 1 HUD")
        lc.transition("OBSERVATION_CALIBRATED", "anchor + camera")
        lc.transition("PLAYING", "run starts")
        return lc

    def test_full_happy_path(self):
        lc = self._happy_path(Lifecycle())
        self.assertEqual(lc.state, "PLAYING")
        lc.transition("MISSION_CLEAR_DETECTED", "byte changed")
        lc.transition("MISSION_CLEAR_VERIFIED", "sustained+corroborated")
        self.assertEqual(lc.state, "MISSION_CLEAR_VERIFIED")
        self.assertEqual(len(lc.history), 9)

    def test_recovery_loop_is_legal(self):
        lc = self._happy_path(Lifecycle())
        lc.transition("DEATH_OR_CONTINUE", "gate failed")
        lc.transition("RECOVERY", "recover_v2")
        lc.transition("INPUT_CONTROL_REVERIFIED", "gate re-passed")
        lc.transition("OBSERVATION_RECALIBRATED", "re-anchor")
        lc.transition("PLAYING", "resume")
        self.assertEqual(lc.state, "PLAYING")

    def test_cannot_skip_input_control_gate(self):
        lc = Lifecycle()
        lc.transition("GAME_IDENTIFIED", "boot ok")
        with self.assertRaises(ValueError):
            # RAM churn alone must NEVER jump straight to PLAYING
            lc.transition("PLAYING", "ram churned a lot")

    def test_cannot_enter_playing_from_title(self):
        lc = Lifecycle()
        lc.transition("GAME_IDENTIFIED", "boot ok")
        lc.transition("TITLE_OR_MENU", "title")
        with self.assertRaises(ValueError):
            lc.transition("PLAYING", "looks like gameplay")

    def test_unknown_state_rejected(self):
        lc = Lifecycle()
        with self.assertRaises(ValueError):
            lc.transition("NARNIA", "wardrobe")

    def test_transitions_are_structured_records(self):
        lc = Lifecycle()
        rec = lc.transition("GAME_IDENTIFIED", "boot ok",
                            evidence={"serial": "SLUS-01212"})
        self.assertEqual(rec["from"], "BOOT")
        self.assertEqual(rec["to"], "GAME_IDENTIFIED")
        self.assertEqual(rec["evidence"], {"serial": "SLUS-01212"})
        self.assertEqual(rec["outcome"], "ok")


class TestRewardAudit(unittest.TestCase):
    def test_unverified_sensors_yield_zero_reward(self):
        audit = RewardAudit(sensor_status={})       # nothing verified
        row = audit.accumulate(0, score_delta=1000.0,
                               progress_delta=50.0, kills_verified=3,
                               deaths=2)
        self.assertEqual(row["components"]["score_delta"], 0.0)
        self.assertEqual(row["components"]["progress_delta"], 0.0)
        self.assertEqual(row["components"]["verified_kill"], 0.0)
        self.assertEqual(row["components"]["death_penalty"], 0.0)

    def test_verified_sensors_unlock_components(self):
        audit = RewardAudit(sensor_status={
            "score": True, "progress": True, "kill_verified": True,
            "lives_hp": True})
        row = audit.accumulate(1, score_delta=100.0, progress_delta=30.0,
                               kills_verified=1, deaths=1)
        self.assertEqual(row["components"]["score_delta"], 100.0)
        self.assertEqual(row["components"]["progress_delta"], 30.0)
        self.assertEqual(row["components"]["verified_kill"], 1.0)
        self.assertEqual(row["components"]["death_penalty"], -1.0)

    def test_time_and_novelty_always_available(self):
        audit = RewardAudit(sensor_status={})
        row = audit.accumulate(2, novelty=1.5)
        self.assertNotEqual(row["components"]["time_penalty"], 0.0)
        self.assertEqual(row["components"]["exploration_novelty"], 1.5)

    def test_enabled_map_is_honest(self):
        audit = RewardAudit(sensor_status={"score": True})
        self.assertTrue(audit.enabled("score_delta"))
        self.assertFalse(audit.enabled("progress_delta"))
        d = audit.to_dict()
        self.assertTrue(d["note"].startswith("audit only"))

    def test_totals_accumulate(self):
        audit = RewardAudit(sensor_status={"progress": True})
        audit.accumulate(0, progress_delta=10.0)
        audit.accumulate(1, progress_delta=5.0)
        self.assertAlmostEqual(audit.totals["progress_delta"], 15.0)


if __name__ == "__main__":
    unittest.main()
