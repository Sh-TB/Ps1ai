"""Offline tests for the Issue #5 controller fix (ContinueLedger) and
telemetry v3 (flags_word field + game_over_flags event)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "scripts"))

from issue5_controller import ContinueLedger  # noqa: E402


class TestContinueLedger(unittest.TestCase):
    def test_score_progress_resets_streak(self):
        led = ContinueLedger(no_progress_limit=2)
        led.observe(900)
        led.on_continue_restart()          # first continue, no baseline
        self.assertEqual(led.continues, 1)
        led.observe(1200)                  # new life scores higher
        led.on_continue_restart()
        stop, _ = led.should_stop()
        self.assertFalse(stop)
        self.assertEqual(led.no_progress_streak, 0)

    def test_no_progress_accumulates_to_stop(self):
        led = ContinueLedger(no_progress_limit=2, progress_epsilon=50)
        led.observe(900)
        led.on_continue_restart()          # baseline = 900
        led.on_continue_restart()          # max still 900 -> streak 1
        stop, _ = led.should_stop()
        self.assertFalse(stop)             # streak(1) <= limit(2)
        led.on_continue_restart()          # streak 2
        stop, _ = led.should_stop()
        self.assertFalse(stop)
        led.on_continue_restart()          # streak 3 > limit
        stop, reason = led.should_stop()
        self.assertTrue(stop)
        self.assertIn("STOP_ATTRITION_LOOP", reason)
        self.assertIn("continues=4", reason)

    def test_epsilon_and_growth(self):
        led = ContinueLedger(no_progress_limit=1, progress_epsilon=50)
        led.observe(900)
        led.on_continue_restart()
        led.observe(940)                   # within epsilon -> no progress
        led.on_continue_restart()          # streak 1 == limit
        stop, _ = led.should_stop()
        self.assertFalse(stop)             # stop needs streak > limit
        led.on_continue_restart()          # streak 2 > limit 1
        stop, _ = led.should_stop()
        self.assertTrue(stop)
        led2 = ContinueLedger(no_progress_limit=1, progress_epsilon=50)
        led2.observe(900)
        led2.on_continue_restart()
        led2.observe(1000)                 # beyond epsilon -> progress
        led2.on_continue_restart()
        stop, _ = led2.should_stop()
        self.assertFalse(stop)


class TestTelemetryV3(unittest.TestCase):
    def test_schema_and_flags_field(self):
        from ps1play import telemetry as T

        class FakeMem:
            def __init__(self, vals):
                self.vals = vals

            def u8(self, a):
                return self.vals.get(("u8", a), 0)

            def u16(self, a):
                return self.vals.get(("u16", a), 0)

            def u32(self, a):
                return self.vals.get(("u32", a), 0)

        class FakeP:
            def __init__(self):
                self.mem = FakeMem({
                    ("u32", T.ADDR_SCORE): 42,
                    ("u8", T.ADDR_GRENADES): 9,
                    ("u32", T.ADDR_CAMERA): 1 << 20,
                    ("u16", T.ADDR_PAD_MIRROR): 32,
                    ("u8", T.ADDR_ACTION_LATCH): 1,
                    ("u32", T.ADDR_FLAGS_WORD): 0xFFFFFFFF,
                })

        tel = T.TelemetryAdapter(FakeP())
        s = tel.snapshot(buttons=["RIGHT"], frame=1)
        self.assertEqual(s["schema"], "ps1play-telemetry/3")
        self.assertEqual(s["flags_word"], 0xFFFFFFFF)
        self.assertEqual(s["provenance"]["flags_word"], "OBSERVED")
        self.assertIsNone(s["lives"])          # still unknown, honest
        # game_over_flags event on transition to saturated word
        prev = dict(s, flags_word=0x1)
        evs = tel.events(prev, s)
        self.assertTrue(any(e["type"] == "game_over_flags" for e in evs))
        # no event when unchanged
        self.assertFalse(any(e["type"] == "game_over_flags"
                             for e in tel.events(s, s)))


if __name__ == "__main__":
    unittest.main()
