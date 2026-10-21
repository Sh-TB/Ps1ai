"""Issue #6 Phase C — experiment harness: JSONL trace, budgets, hang
detection, bounded watch, first-divergence compare, explicit capability
errors. Uses a deterministic fake core (no emulator needed)."""
import json

import numpy as np
import pytest

from ps1play.harness import CapabilityError, ExperimentHarness, _ram_hash


class FakeCore:
    """Deterministic fake core: RAM evolves by frame counters + input.

    state[i] advances when RIGHT held (region 0x100..0x13F as u32 LE
    positions), a frame counter ticks at 0x200, and nothing else moves —
    so branches diverge causally and deterministically.
    """

    def __init__(self):
        self.ram = bytearray(2048)
        self.frames_run = 0
        self._buttons = set()
        self._saved = {}

    def run(self, frames, buttons=None):
        self._buttons = buttons or set()
        for _ in range(frames):
            self.frames_run += 1
            # frame counter at 0x200 (u32)
            v = int.from_bytes(self.ram[0x200:0x204], "little")
            self.ram[0x200:0x204] = ((v + 1) & 0xFFFFFFFF).to_bytes(
                4, "little")
            if "RIGHT" in self._buttons:
                for i, a in enumerate(range(0x100, 0x140, 4)):
                    v = int.from_bytes(self.ram[a:a+4], "little")
                    self.ram[a:a+4] = ((v + 1) & 0xFFFFFFFF).to_bytes(
                        4, "little")

    def reset(self):
        self.ram = bytearray(2048)
        self.frames_run = 0

    def serialize(self):
        return bytes(self.ram)

    def unserialize(self, blob):
        self.ram = bytearray(blob)


class FakeMem:
    def __init__(self, core):
        self.core = core

    def snapshot(self):
        return bytes(self.core.ram)

    def u8(self, a):
        return self.core.ram[a]

    def u16(self, a):
        return int.from_bytes(self.core.ram[a:a+2], "little")

    def u32(self, a):
        return int.from_bytes(self.core.ram[a:a+4], "little")


class FakeStates:
    def __init__(self, core):
        self.core = core
        self.d = {}

    def save(self, core, name, meta=None):
        self.d[name] = core.serialize()
        return {"bytes": len(self.d[name])}

    def load(self, core, name):
        core.unserialize(self.d[name])
        return {"name": name}


class FakePlay:
    def __init__(self):
        self.core = FakeCore()
        self.mem = FakeMem(self.core)
        self.states = FakeStates(self.core)

    def boot(self):
        self.core.frames_run = 0
        return {"core": "fake 1.0", "serial": None, "plugin": "generic",
                "ram_bytes": len(self.core.ram)}

    def save_state(self, name):
        return self.states.save(self.core, name)

    def load_state(self, name):
        return self.states.load(self.core, name)

    def observe(self):
        return {"changed_bytes": 0}


@pytest.fixture()
def play():
    return FakePlay()


def _mk(play, tmp_path, **kw):
    return ExperimentHarness(play, str(tmp_path / "ev"), **kw)


def test_boot_logs_versions_and_trace_is_jsonl(play, tmp_path):
    h = _mk(play, tmp_path)
    info = h.boot()
    assert info["plugin"] == "generic"
    row = json.loads(open(str(tmp_path / "ev" / "trace.jsonl")).readline())
    assert row["op"] == "boot" and row["plugin"] == "generic"


def test_act_records_causal_change_and_hash(play, tmp_path):
    h = _mk(play, tmp_path)
    h.boot()
    idle = h.act(set(), 60)
    moved = h.act({"RIGHT"}, 60)
    assert idle["changed"] > 0      # frame counter ticks
    assert moved["changed"] > idle["changed"]
    assert len(moved["ram_hash"]) == 16


def test_frame_budget_raises_explicit_error(play, tmp_path):
    h = _mk(play, tmp_path, max_frames=100)
    h.boot()
    with pytest.raises(CapabilityError, match="frame budget"):
        h.step_frames(200)


def test_hang_detection_after_static_windows(play, tmp_path):
    # freeze the frame counter region to simulate a hung game
    class StuckCore(FakeCore):
        def run(self, frames, buttons=None):
            self.frames_run += frames
    play.core = StuckCore()
    play.mem = FakeMem(play.core)
    h = _mk(play, tmp_path, hang_window=240)
    h.boot()
    for _ in range(3):
        h.act(set(), 60)
    assert h._activity[-3:] == [0, 0, 0]
    rows = [json.loads(l) for l in
            open(str(tmp_path / "ev" / "trace.jsonl"))]
    assert any(r["op"] == "hang_suspected" for r in rows)


def test_watch_is_bounded_and_samples_fields(play, tmp_path):
    h = _mk(play, tmp_path)
    h.boot()
    s = h.watch({"fc": (0x200, "u32")}, frames=120, every=60)
    assert len(s) == 2                       # 120/60
    assert s[1]["fc"] > s[0]["fc"]
    assert s[0]["fc"] == 60                  # sampled AFTER the block


def test_checkpoint_restore_roundtrip(play, tmp_path):
    h = _mk(play, tmp_path)
    h.boot()
    h.act({"RIGHT"}, 30)
    h.checkpoint("cp1")
    h.act({"RIGHT"}, 30)
    x_after_more = play.mem.u32(0x100)
    h.restore("cp1")
    assert play.mem.u32(0x100) == x_after_more - 30


def test_replay_is_deterministic(play, tmp_path):
    h = _mk(play, tmp_path)
    h.boot()
    h.act({"RIGHT"}, 10)
    h.checkpoint("origin")
    r1 = h.replay("origin", 50, {"RIGHT"})
    r2 = h.replay("origin", 50, {"RIGHT"})
    assert r1["end_hash"] == r2["end_hash"]


def test_compare_finds_first_divergence(play, tmp_path):
    h = _mk(play, tmp_path)
    h.boot()
    h.checkpoint("origin")
    # branch A: idle; branch B: RIGHT — both 120 frames
    res = h.compare("origin", "origin", frames=120,
                    buttons_a=set(), buttons_b={"RIGHT"})
    assert res["first_divergent_chunk"] == 0   # RIGHT changes chunk 0
    assert res["byte_diff"]["bytes"] == 16     # 0x100..0x13F = 64B... u8 diff
    # chunk 0 = 60 frames -> each of 16 u32 slots changed at least once;
    # byte-level diff counts CHANGED BYTES, slots differ in low bytes
    assert res["byte_diff"]["first"] is not None


def test_compare_identical_branches_no_divergence(play, tmp_path):
    h = _mk(play, tmp_path)
    h.boot()
    h.checkpoint("origin")
    res = h.compare("origin", "origin", frames=120,
                    buttons_a=set(), buttons_b=set())
    assert res["first_divergent_chunk"] is None
    assert res["byte_diff"] is None


def test_stop_writes_summary(play, tmp_path):
    h = _mk(play, tmp_path)
    h.boot()
    h.act(set(), 60)
    s = h.stop()
    assert s["ops"] >= 2          # boot + act rows recorded pre-stop
    assert s["frames_run"] == 60
    assert (tmp_path / "ev" / "summary.json").exists()
    assert h.stop() is None                   # idempotent
