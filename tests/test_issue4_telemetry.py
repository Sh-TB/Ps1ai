"""Offline tests for Issue #4 Phase 2/3: telemetry adapter, provenance
grades, wrap-safe scroll math, event derivation, JSONL trace, and the
conservative clear-candidate rule.  No emulator required."""
import json
import os
import sys
import tempfile

import numpy as np
import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.telemetry import (                             # noqa: E402
    TelemetryAdapter, JsonlTrace, replay_gain, is_clear_candidate,
    PROVENANCE, UNKNOWN_FIELDS, ADDR_SCORE, ADDR_GRENADES,
    ADDR_CAMERA, ADDR_BOMBS_DIGIT, ADDR_PAD_MIRROR,
    CLEAR_MIN_SCORE_GAIN, CLEAR_SCROLL_FROZEN_CHUNKS)

RAM_SIZE = 0x200000


class FakeMem:
    def __init__(self):
        self.ram = np.zeros(RAM_SIZE, dtype=np.uint8)

    def set_u32(self, addr, v):
        self.ram[addr:addr + 4] = np.frombuffer(
            int(v & 0xFFFFFFFF).to_bytes(4, "little"), dtype=np.uint8)

    def u8(self, a):
        return int(self.ram[a])

    def u16(self, a):
        return int(self.ram[a] | (self.ram[a + 1] << 8))

    def u32(self, a):
        return int.from_bytes(self.ram[a:a + 4], "little")


class FakePlay:
    def __init__(self):
        self.mem = FakeMem()


@pytest.fixture
def play():
    p = FakePlay()
    p.mem.set_u32(ADDR_SCORE, 244)
    p.mem.ram[ADDR_GRENADES] = 10
    p.mem.set_u32(ADDR_CAMERA, 0x00210000)       # 33.0 px camera
    p.mem.ram[ADDR_BOMBS_DIGIT] = 0x4B + 8       # tile digit '8'
    p.mem.ram[ADDR_PAD_MIRROR] = 0x20
    return p


# ---------------- provenance / evidence grades ----------------------
class TestProvenance:
    def test_verified_fields_have_two_plus_experiments(self):
        for name in ("score", "grenades", "pad_mirror"):
            ev = PROVENANCE[name]["evidence"]
            assert PROVENANCE[name]["grade"] == "VERIFIED"
            assert len(ev) >= 2, f"{name} needs >=2 experiments"

    def test_camera_is_observed_until_live_confirm(self):
        assert PROVENANCE["camera_fx"]["grade"] == "OBSERVED"

    def test_demo_scroll_is_context_bound(self):
        ev = " ".join(PROVENANCE["demo_scroll_fx"]["evidence"])
        assert "real play" in ev

    def test_action_latch_is_observed_not_verified(self):
        assert PROVENANCE["action_latch"]["grade"] == "OBSERVED"

    def test_pace_sensor_is_heuristic_never_timer(self):
        assert PROVENANCE["pace_sensor"]["grade"] == "HEURISTIC"
        assert "NOT a timer" in PROVENANCE["pace_sensor"]["evidence"][0]

    def test_unknown_fields_complete(self):
        for f in ("lives", "continues", "hp", "mission_clear", "timer",
                  "enemies", "player_x", "bombs_reserve"):
            assert f in UNKNOWN_FIELDS


# ---------------- snapshot semantics --------------------------------
class TestSnapshot:
    def test_unknown_fields_are_none_never_guessed(self, play):
        tel = TelemetryAdapter(play)
        s = tel.snapshot(buttons=["RIGHT"], frame=123)
        for f in UNKNOWN_FIELDS:
            assert s[f] is None, f"{f} must stay None"

    def test_verified_fields_read_from_ram(self, play):
        tel = TelemetryAdapter(play)
        s = tel.snapshot()
        assert s["score"] == 244
        assert s["grenades"] == 10
        assert s["camera_x"] == 0x00210000 >> 16
        assert s["bombs_digit"] == 8
        assert s["pad_mirror"] == 0x20

    def test_bombs_digit_out_of_range_is_none(self, play):
        tel = TelemetryAdapter(play)
        play.mem.ram[ADDR_BOMBS_DIGIT] = 0x10     # not a tile digit
        assert tel.snapshot()["bombs_digit"] is None

    def test_pace_sensor_hidden_by_default(self, play):
        tel = TelemetryAdapter(play)
        assert tel.snapshot()["pace_sensor"] is None
        play.mem.ram[0x0D47D4] = 112
        tel2 = TelemetryAdapter(play, include_unknown=False)
        assert tel2.snapshot()["pace_sensor"] is None


# ---------------- scroll math ---------------------------------------
class TestScrollMath:
    def test_plain_gain(self, play):
        tel = TelemetryAdapter(play)
        a = tel.snapshot()
        play.mem.set_u32(ADDR_CAMERA, 0x00210000 + 60 * 65536)
        b = tel.snapshot()
        assert tel.scroll_gain(a, b) == 60

    def test_wrap_safe_gain(self, play):
        tel = TelemetryAdapter(play)
        b = tel.snapshot()
        play.mem.set_u32(ADDR_CAMERA, 0xFFFF0010)
        c0 = tel.snapshot()
        play.mem.set_u32(ADDR_CAMERA, 0x00000110)
        c = tel.snapshot()
        assert tel.scroll_gain(c0, c) == 1

    def test_replay_gain_series(self):
        series = [0x81000000, 0x81060000, 0x81060000, 0x81060001]
        assert replay_gain(series) == [6, 0, 0]

    def test_replay_gain_wrap(self):
        # 0xFFFF0000 + 65536 fx wraps to exactly 0: +1 px
        assert replay_gain([0xFFFF0000, 0x00000000]) == [1]
        # sub-unit fx carry (0x200 = 0.0078 px) must NOT count as a pixel
        assert replay_gain([0xFFFFFF00, 0x00000100]) == [0]


# ---------------- event derivation -----------------------------------
class TestEvents:
    def test_score_gain_event(self, play):
        tel = TelemetryAdapter(play)
        a = tel.snapshot()
        play.mem.set_u32(ADDR_SCORE, 244 + 300)
        b = tel.snapshot()
        evs = tel.events(a, b)
        assert any(e["type"] == "score_gain" and e["delta"] == 300
                   for e in evs)

    def test_death_candidate_on_collapse(self, play):
        tel = TelemetryAdapter(play)
        a = tel.snapshot()
        play.mem.set_u32(ADDR_SCORE, 0)
        b = tel.snapshot()
        evs = tel.events(a, b)
        d = [e for e in evs if e["type"] == "death_candidate"]
        assert len(d) == 1 and d[0]["grade"] == "DERIVED"

    def test_grenade_events_both_directions(self, play):
        tel = TelemetryAdapter(play)
        a = tel.snapshot()
        play.mem.ram[ADDR_GRENADES] = 8
        assert any(e["type"] == "grenade_used" and e["delta"] == 2
                   for e in tel.events(a, tel.snapshot()))
        a2 = tel.snapshot()
        play.mem.ram[ADDR_GRENADES] = 10
        assert any(e["type"] == "grenade_refill" and e["delta"] == 2
                   for e in tel.events(a2, tel.snapshot()))

    def test_no_events_between_identical_snapshots(self, play):
        tel = TelemetryAdapter(play)
        a = tel.snapshot()
        assert tel.events(a, tel.snapshot()) == []


# ---------------- clear-candidate rule --------------------------------
class TestClearCandidate:
    def test_requires_frozen_and_big_gain(self):
        assert not is_clear_candidate(0, 99999)
        assert not is_clear_candidate(CLEAR_SCROLL_FROZEN_CHUNKS, 100)
        assert not is_clear_candidate(1, CLEAR_MIN_SCORE_GAIN)
        assert is_clear_candidate(3, CLEAR_MIN_SCORE_GAIN)
        assert is_clear_candidate(5, 12000)

    def test_small_kill_scores_never_candidate(self):
        assert not is_clear_candidate(10, 244)


# ---------------- JSONL trace -----------------------------------------
class TestJsonlTrace:
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "t.jsonl")
            tr = JsonlTrace(path)
            tr.write({"type": "chunk", "n": 1})
            tr.write({"type": "chunk", "n": 2})
            tr.close()
            rows = [json.loads(l) for l in open(path)]
            assert [r["n"] for r in rows] == [1, 2]
            assert all("ts_utc" in r for r in rows)
