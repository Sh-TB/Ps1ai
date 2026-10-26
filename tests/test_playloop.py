"""tests/test_playloop.py — mock-harness unit tests for the reusable
game-loop driver (no emulator needed): policy loop, terminal detect,
restart cycle, report/verdict composition."""
import os
import sys

import numpy as np
import pytest

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

from playloop import Observation, Playloop, verdict_from  # noqa: E402


class FakeCore:
    def __init__(self, frames):
        self.frames = frames
        self.i = 0
        self.ran = []

    def frame_rgb(self):
        f = self.frames[min(self.i, len(self.frames) - 1)]
        return f

    def run(self, n, btns):
        self.ran.append((n, frozenset(btns)))
        self.i += n


class FakeMem:
    def __init__(self):
        self.data = b"\x00\x41\xff\xff" * 4

    def snapshot(self):
        return self.data


class FakePlay:
    def __init__(self, frames):
        self.core = FakeCore(frames)
        self.mem = FakeMem()
        self.waited = []

    def boot(self):
        return True

    def wait(self, n):
        self.waited.append(n)


class ScriptedPolicy:
    NAME = "scripted"

    def __init__(self, script):
        self.script = script          # list of (buttons|None, frames)
        self.i = 0
        self.terminals = []

    def act(self, step, obs):
        if self.i >= len(self.script):
            return None
        cmd = self.script[self.i]
        self.i += 1
        return cmd

    def terminal(self, obs):
        return None


class TerminalPolicy(ScriptedPolicy):
    def terminal(self, obs):
        if obs.step >= 2:
            return "stop"
        return None


def _frames(n, h=8, w=8):
    base = np.zeros((h, w, 3), dtype=np.uint8)
    return [base.copy() for _ in range(n)]


def test_playloop_runs_policy_and_reports():
    frames = _frames(10)
    fp = FakePlay(frames)
    loop = Playloop.__new__(Playloop)     # skip real boot
    loop.p = fp
    loop.journal = lambda ev: None
    loop.t0 = 0.0
    import time
    loop.t0 = time.time()
    pol = ScriptedPolicy([({"UP"}, 4), (set(), 2), ({"B"}, 6)])
    rep = loop.run(pol, max_steps=5)
    assert rep["steps"] == 5
    assert rep["policy"] == "scripted"
    assert ("UP" in fp.core.ran[0][1])
    assert ("B" in fp.core.ran[2][1])


def test_terminal_stops_loop():
    frames = _frames(8)
    fp = FakePlay(frames)
    loop = Playloop.__new__(Playloop)
    loop.p = fp
    loop.journal = lambda ev: None
    import time
    loop.t0 = time.time()
    pol = TerminalPolicy([({"A"}, 2)] * 6)
    rep = loop.run(pol, max_steps=10)
    assert rep["steps"] == 3               # stops at step 2
    assert rep["terminals"][-1]["kind"] == "stop"


def test_observation_madiff_and_padbuff():
    a = np.zeros((4, 4, 3), dtype=np.uint8)
    b = np.full((4, 4, 3), 40, dtype=np.uint8)
    o1 = Observation(0, b, a, 2, None)
    assert o1.madiff == pytest.approx(40.0)
    assert o1.padbuff_hits == 2
    o2 = Observation(1, a.copy(), a, 0, None)
    assert o2.madiff == pytest.approx(0.0)


def test_verdict_composition():
    assert verdict_from({}, False, False) == "FAILED"
    assert verdict_from({}, True, False) == "INCONCLUSIVE"
    assert verdict_from({"state_change_confirmed": True},
                        True, True) == "STATE_CHANGE_CONFIRMED"
    assert verdict_from({"gameplay_confirmed": True},
                        True, True) == "GAMEPLAY_CONFIRMED"
    assert verdict_from({}, True, True) == "BOOTED"


def test_pong_policy_restart_on_static():
    from playloop import PongLoopPolicy
    pol = PongLoopPolicy(cycles=2)
    blank = np.zeros((240, 320, 3), dtype=np.uint8)
    burst = np.full((240, 320, 3), 90, dtype=np.uint8)
    # play -> burst (scene change) -> static run -> game over -> X
    prev = None
    cmd = None
    for f in (blank, blank, burst, blank, blank, blank, blank):
        obs = Observation(0, f, prev, 1, None)
        cmd = pol.act(0, obs)
        prev = f
    assert pol.game_overs >= 1
    assert any(e["ev"] == "restart" for e in pol.events)
