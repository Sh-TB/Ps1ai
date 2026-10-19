"""Level-A unit tests: events.py (§2/§3/§10). Pure synthetic data —
these tests verify reasoning code, NOT the real game."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ps1play.agent.events import (                              # noqa: E402
    EventLog, ScoreTracker, KillClassifier, MissionClearDetector,
    Event, SCORE_CHANGED, SCORE_RESET, SCORE_SUSPICIOUS,
    ENEMY_KILL_CANDIDATE, ENEMY_KILL_VERIFIED,
    MISSION_CLEAR_DETECTED, MISSION_CLEAR_VERIFIED,
    MISSION_TRANSITION, OBSERVED, ESTIMATED, VERIFIED)


class TestScoreTracker(unittest.TestCase):
    def test_bootstrap_no_delta_invented(self):
        t = ScoreTracker()
        obs = t.feed(200, frame=10, chunk=0, raw=b"\xc8\x00\x00\x00")
        self.assertEqual(obs["kind"], "bootstrap")
        self.assertEqual(obs["delta"], 0)
        self.assertEqual(obs["raw_after"], "c8000000")

    def test_positive_update(self):
        t = ScoreTracker()
        t.feed(200, frame=10, raw=b"\xc8\x00\x00\x00")
        obs = t.feed(300, frame=70, chunk=1, raw=b"\x2c\x01\x00\x00")
        self.assertEqual(obs["kind"], "update")
        self.assertEqual(obs["delta"], 100)
        self.assertEqual(t.cumulative_gain, 100)

    def test_continue_reset_is_reason_coded(self):
        t = ScoreTracker()
        t.feed(300, frame=10, raw=b"\x2c\x01\x00\x00")
        obs = t.feed(0, frame=70, chunk=1, raw=b"\x00\x00\x00\x00")
        self.assertEqual(obs["kind"], "reset")
        self.assertEqual(t.n_resets, 1)
        # cumulative gain must NOT count post-reset growth as pre-reset
        t.feed(100, frame=130, raw=b"\x64\x00\x00\x00")
        self.assertEqual(t.cumulative_gain, 100)

    def test_u32_wraparound(self):
        t = ScoreTracker()
        t.feed(0xFFFFFFF0, frame=1, raw=b"\xf0\xff\xff\xff")
        obs = t.feed(0x14, frame=2, raw=b"\x14\x00\x00\x00")
        self.assertEqual(obs["kind"], "wrap")
        self.assertEqual(obs["delta"], 0x24)      # 0x14 - (-0x10)
        self.assertEqual(t.n_wraps, 1)

    def test_suspicious_jump_not_silent(self):
        t = ScoreTracker()
        t.feed(100, frame=1, raw=b"\x64\x00\x00\x00")
        obs = t.feed(200_000, frame=2, raw=b"\x00\x0d\x03\x00")
        self.assertEqual(obs["kind"], "suspicious")
        self.assertTrue(obs["suspicious"])
        self.assertEqual(t.n_suspicious, 1)

    def test_raw_bytes_recorded(self):
        t = ScoreTracker()
        t.feed(1, frame=1, raw=b"\x01\x00\x00\x00")
        obs = t.feed(2, frame=2, raw=b"\x02\x00\x00\x00")
        self.assertEqual(obs["raw_before"], "01000000")
        self.assertEqual(obs["raw_after"], "02000000")
        self.assertEqual(obs["decoded_before"], 1)
        self.assertEqual(obs["decoded_after"], 2)

    def test_to_dict_encoding_honesty(self):
        t = ScoreTracker()
        d = t.to_dict()
        self.assertIn("PARTIAL", d["encoding_status"])


class TestKillClassifier(unittest.TestCase):
    def _up_obs(self, delta):
        return {"kind": "update", "delta": delta, "addr": 0x0EE318,
                "raw_after": "00"}

    def test_score_delta_alone_is_estimated_only(self):
        evlog = EventLog()
        kc = KillClassifier(min_delta=90)
        kc.on_score_obs(self._up_obs(100), evlog, frame=1, chunk=0)
        ev = evlog.events[-1]
        self.assertEqual(ev.type, ENEMY_KILL_CANDIDATE)
        self.assertEqual(ev.status, ESTIMATED)
        self.assertEqual(kc.estimated, 1)
        self.assertEqual(kc.verified, 0)

    def test_small_delta_no_event(self):
        evlog = EventLog()
        kc = KillClassifier(min_delta=90)
        kc.on_score_obs(self._up_obs(50), evlog)
        self.assertEqual(len(evlog.events), 0)

    def test_reset_never_becomes_kill(self):
        evlog = EventLog()
        kc = KillClassifier(min_delta=90)
        kc.on_score_obs({"kind": "reset", "delta": -300}, evlog)
        self.assertEqual(len(evlog.events), 0)

    def test_verification_requires_entity_evidence(self):
        # a bare Event cannot be VERIFIED without evidence
        with self.assertRaises(ValueError):
            Event(ENEMY_KILL_VERIFIED, VERIFIED)

    def test_upgrade_with_entity_evidence(self):
        evlog = EventLog()
        kc = KillClassifier(min_delta=90)
        kc.on_score_obs(self._up_obs(100), evlog, frame=10)
        ev = kc.verify_with_entity(evlog, addr=0x1234, frame=12)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.status, VERIFIED)
        self.assertEqual(kc.verified, 1)
        self.assertEqual(kc.estimated, 0)
        self.assertIn("entity_slot_death", ev.evidence)

    def test_estimated_never_merges_into_verified(self):
        evlog = EventLog()
        kc = KillClassifier(min_delta=90)
        for _ in range(5):
            kc.on_score_obs(self._up_obs(100), evlog)
        d = kc.to_dict()
        self.assertEqual(d["kills_estimated"], 5)
        self.assertEqual(d["kills_verified"], 0)


class TestMissionClearDetector(unittest.TestCase):
    def test_byte_change_alone_is_detected_not_verified(self):
        evlog = EventLog()
        mcd = MissionClearDetector(baseline_byte=0, sustain_chunks=4)
        mcd.feed(3, frame=100, chunk=10, evlog=evlog)
        self.assertTrue(mcd.detected)
        self.assertFalse(mcd.verified)
        types = [e.type for e in evlog.events]
        self.assertIn(MISSION_CLEAR_DETECTED, types)
        self.assertNotIn(MISSION_CLEAR_VERIFIED, types)

    def test_transient_change_is_rejected(self):
        evlog = EventLog()
        mcd = MissionClearDetector(baseline_byte=0, sustain_chunks=4)
        mcd.feed(3, frame=100, chunk=10, evlog=evlog)
        mcd.feed(0, frame=160, chunk=11, evlog=evlog)
        self.assertFalse(mcd.detected)
        self.assertFalse(mcd.verified)
        self.assertEqual(mcd.rejected, 1)
        types = [e.type for e in evlog.events]
        self.assertIn(MISSION_TRANSITION, types)
        self.assertNotIn(MISSION_CLEAR_VERIFIED, types)

    def test_verified_needs_sustain_and_corroboration(self):
        evlog = EventLog()
        mcd = MissionClearDetector(baseline_byte=0, sustain_chunks=3)
        mcd.feed(3, frame=100, chunk=10, evlog=evlog)
        mcd.corroborate("input_responsive_after_transition")
        mcd.feed(3, frame=160, chunk=11, evlog=evlog)
        self.assertFalse(mcd.verified)            # sustain=2 < 3
        mcd.feed(3, frame=220, chunk=12, evlog=evlog)
        self.assertTrue(mcd.verified)             # sustain=3 + corroboration
        types = [e.type for e in evlog.events]
        self.assertIn(MISSION_CLEAR_VERIFIED, types)
        d = mcd.to_dict()
        self.assertTrue(d["mission_clear_detected"])
        self.assertTrue(d["mission_clear_verified"])
        self.assertIn("corroboration", d["verification_method"])

    def test_sustain_without_corroboration_stays_unverified(self):
        mcd = MissionClearDetector(baseline_byte=0, sustain_chunks=2)
        mcd.feed(3, frame=1, chunk=1)
        mcd.feed(3, frame=2, chunk=2)
        mcd.feed(3, frame=3, chunk=3)
        self.assertTrue(mcd.detected)
        self.assertFalse(mcd.verified)            # no independent evidence

    def test_to_dict_separates_detected_from_verified(self):
        mcd = MissionClearDetector(baseline_byte=7, sustain_chunks=2)
        d = mcd.to_dict()
        self.assertFalse(d["mission_clear_detected"])
        self.assertFalse(d["mission_clear_verified"])
        self.assertEqual(d["mission_state_before"], 7)


if __name__ == "__main__":
    unittest.main()
