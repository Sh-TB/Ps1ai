"""Level-A unit tests: perception observation contract (§5) — no
emulator required (stubbed host/memory). Proves:
  * every public role is reported with an honest status
  * the bombs anchor being VERIFIED does NOT verify other roles
  * invalidate() drops dynamic roles and marks them INVALID
  * validate_anchor() rejects out-of-range and rising counters
    (the v0.5 bombs=30 failure mode)
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ps1play.agent.perception import PerceptionGuard, PUB    # noqa: E402


class FakeMem:
    """Minimal MemoryView stand-in over a 2 MB array."""

    def __init__(self):
        self.ram = np.zeros(0x200000, np.uint8)

    def u16(self, a):
        return int(self.ram[a] | (self.ram[a + 1] << 8))

    def u32(self, a):
        return int.from_bytes(bytes(self.ram[a:a + 4]), "little")

    def snapshot(self):
        return self.ram.copy()


class FakeCore:
    def __init__(self, mem):
        self.mem = mem
        self.frames_run = 0

    def run(self, frames, buttons=None):
        self.frames_run += frames

    def run_frame(self):
        self.frames_run += 1

    def set_buttons(self, spec):
        pass


class FakePlay:
    def __init__(self):
        self.mem = FakeMem()
        self.core = FakeCore(self.mem)

    def save_state(self, name):
        pass

    def load_state(self, name):
        pass

    def _advance(self):
        pass


def _poke_u16(mem, addr, val):
    mem.ram[addr] = val & 0xFF
    mem.ram[addr + 1] = (val >> 8) & 0xFF


class TestObservationContract(unittest.TestCase):
    def test_all_roles_present_and_pending_by_default(self):
        g = PerceptionGuard(FakePlay())
        contract = g.observation_contract()
        self.assertEqual(set(contract.keys()), set(PUB.keys()))
        for role, entry in contract.items():
            self.assertEqual(entry["status"], "PENDING")
            self.assertIsNone(entry["address"])
            self.assertFalse(entry["valid_for_current_mission"])

    def test_bombs_anchor_does_not_verify_other_roles(self):
        g = PerceptionGuard(FakePlay())
        g._set_role("bombs", 0xCAF9C, "VERIFIED",
                    "grenade event", confidence=0.95)
        contract = g.observation_contract()
        self.assertEqual(contract["bombs"]["status"], "VERIFIED")
        for role in contract:
            if role != "bombs":
                self.assertEqual(contract[role]["status"], "PENDING",
                                 f"{role} must not inherit verification")

    def test_invalidate_drops_dynamic_roles(self):
        g = PerceptionGuard(FakePlay())
        g._set_role("bombs", 0xCAF9C, "VERIFIED", "grenade event")
        g._set_role("timer", 0xCAF9C + 0x100, "PENDING", "translation")
        g.invalidate("death/continue reload")
        self.assertNotIn("bombs", g.addrs)
        self.assertNotIn("timer", g.addrs)
        self.assertEqual(g.verification["bombs"]["status"], "INVALID")

    def test_validate_anchor_rejects_out_of_range(self):
        play = FakePlay()
        g = PerceptionGuard(play)
        g._set_role("bombs", 0x1000, "VERIFIED", "grenade event")
        _poke_u16(play.mem, 0x1000, 99)          # > 40: implausible
        res = g.validate_anchor()
        self.assertFalse(res["ok"])
        self.assertNotIn("bombs", g.addrs)       # invalidated

    def test_validate_anchor_rejects_rising_counter(self):
        # v0.5 failure mode: a wrong field that INCREASES over the window
        play = FakePlay()
        g = PerceptionGuard(play)
        g._set_role("bombs", 0x1000, "VERIFIED", "grenade event")
        _poke_u16(play.mem, 0x1000, 10)
        _poke_u16(play.mem, 0x1002, 0x0200)      # something that will rise
        # make the word at 0x1000 rise over the "30 idle frames" by
        # simulating via the fake core: run() mutates nothing, so instead
        # patch the second read through a mutating fake mem
        class RisingMem(FakeMem):
            reads = 0

            def u16(self, a):
                if a == 0x1000:
                    RisingMem.reads += 1
                    _poke_u16(self, 0x1000, 10 + RisingMem.reads)
                return super().u16(a)
        play.mem = RisingMem()
        g.p = play
        res = g.validate_anchor()
        self.assertFalse(res["ok"])
        self.assertIn("rose", res["reason"])
        self.assertNotIn("bombs", g.addrs)

    def test_validate_anchor_accepts_stable_counter(self):
        play = FakePlay()
        g = PerceptionGuard(play)
        g._set_role("bombs", 0x1000, "VERIFIED", "grenade event")
        _poke_u16(play.mem, 0x1000, 6)
        res = g.validate_anchor()
        self.assertTrue(res["ok"])

    def test_read_returns_none_for_unknown_role(self):
        g = PerceptionGuard(FakePlay())
        self.assertIsNone(g.read("lives"))

    def test_state_reads_only_anchored_roles(self):
        play = FakePlay()
        g = PerceptionGuard(play)
        g._set_role("bombs", 0x1000, "VERIFIED", "grenade event")
        _poke_u16(play.mem, 0x1000, 4)
        st = g.state()
        self.assertEqual(st["bombs"], 4)
        self.assertIsNone(st["hp"])             # never anchored -> None


if __name__ == "__main__":
    unittest.main()
