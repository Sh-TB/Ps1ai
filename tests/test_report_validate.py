"""Level-A unit tests: report_validate.py (§2.3).

The validator MUST fail on the original v0.5 report (its shipped
contradictions) and pass on a consistent v0.6-style report."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ps1play.agent.report_validate import validate_report    # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(_REPO, "download", "ps1play_v4_mission1",
                       "mission1_report.json")


def _codes(findings):
    return {f["code"] for f in findings}


class TestOriginalV4ReportFails(unittest.TestCase):
    """The shipped v0.5 report is the regression fixture."""

    @classmethod
    def setUpClass(cls):
        if os.path.exists(FIXTURE):
            with open(FIXTURE) as f:
                cls.report = json.load(f)
            cls.have_fixture = True
        else:
            # synthetic reproduction of the SAME faulty conditions:
            cls.report = {
                "mode": "legit-inputs-only",
                "play": {"score_start": 200, "score_end": 200,
                         "kills_est": 27, "continues": 18,
                         "cleared": False},
                "telemetry": [
                    {"chunk": 24, "score": 96, "bombs": 0},
                    {"chunk": 149, "score": 172, "bombs": 21},
                    {"chunk": 224, "score": 200, "bombs": 4},
                    {"chunk": 524, "score": 52, "bombs": 3},
                ],
                "events": {"score+100": 19},
                "camera": {"addr": 828130, "verified": False},
            }
            cls.have_fixture = False

    def test_score_range_contradiction_found(self):
        self.assertIn("SCORE_RANGE_CONTRADICTION",
                      _codes(validate_report(self.report)))

    def test_unverified_kills_found(self):
        self.assertIn("KILLS_NOT_EVIDENCED",
                      _codes(validate_report(self.report)))

    def test_bombs_implausible_jump_found(self):
        # 0 -> 21 between rows: grenades only decrement
        self.assertIn("BOMBS_IMPLAUSIBLE_JUMP",
                      _codes(validate_report(self.report)))

    def test_validator_reports_multiple_findings(self):
        findings = validate_report(self.report)
        self.assertGreaterEqual(len(findings), 3)


class TestConsistentReportPasses(unittest.TestCase):
    def _consistent(self, **over):
        r = {
            "mode": "legit-inputs-only",
            "play": {"score_start": 0, "score_end": 300,
                     "score_resets": 1, "kills_estimated": 2,
                     "kills_verified": 0, "continues": 1,
                     "cleared": False},
            "telemetry": [{"chunk": 24, "score": 100, "bombs": 10},
                          {"chunk": 49, "score": 200, "bombs": 9},
                          {"chunk": 74, "score": 0, "bombs": 8}],
            "events": {"counts": {}},
            "camera": {"addr": 828130, "verified": False},
        }
        r["play"].update(over)
        return r

    def test_clean_report_passes(self):
        self.assertEqual(validate_report(self._consistent()), [])

    def test_reported_reset_explains_excursion(self):
        # start==end==200 but a reset WAS reported -> no contradiction
        r = self._consistent(score_start=200, score_end=200,
                             score_resets=2)
        r["telemetry"] = [{"chunk": 24, "score": 100, "bombs": 10},
                          {"chunk": 49, "score": 250, "bombs": 9}]
        self.assertEqual(validate_report(r), [])

    def test_unreset_excursion_flagged(self):
        r = self._consistent(score_start=200, score_end=200,
                             score_resets=0)
        r["telemetry"] = [{"chunk": 24, "score": 40, "bombs": 10}]
        self.assertIn("SCORE_RANGE_CONTRADICTION",
                      _codes(validate_report(r)))

    def test_verified_kills_must_be_backed_by_events(self):
        r = self._consistent(kills_verified=3)
        self.assertIn("KILLS_VERIFIED_UNBACKED",
                      _codes(validate_report(r)))

    def test_clear_without_corroboration_flagged(self):
        r = self._consistent(cleared=True)
        r["mission_clear"] = {"verified": True}
        self.assertIn("CLEAR_NOT_VERIFIED",
                      _codes(validate_report(r)))

    def test_progress_claim_needs_verified_camera(self):
        r = self._consistent()
        r["play"]["progress_claim"] = {"addr": "0xca2e2"}
        self.assertIn("PROGRESS_FROM_UNVERIFIED_SIGNAL",
                      _codes(validate_report(r)))

    def test_bombs_out_of_range_flagged(self):
        r = self._consistent()
        r["telemetry"] = [{"chunk": 24, "score": 100, "bombs": 63}]
        self.assertIn("BOMBS_OUT_OF_RANGE",
                      _codes(validate_report(r)))


if __name__ == "__main__":
    unittest.main()
