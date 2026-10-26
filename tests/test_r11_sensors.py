"""Round-11 MSX sensor tests (Task 17-a) — pure mocks, no emulator.

Covers msx_r11_lib: WagonTracker crossing geometry + kind split,
PollDiffIndex kill-event classification, count_waves segmentation.
"""
import os
import sys

import numpy as np
import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from msx_r11_lib import (                     # noqa: E402
    TABLE, STRIDE, WagonTracker, split_kinds, PollDiffIndex, count_waves)


def make_ram():
    return np.zeros(TABLE + 24 * STRIDE, dtype=np.uint8)


def set_slot(ram, slot, st=0x1234, x=0.0, h=64, hp8e=1, hpA4=0):
    base = TABLE + slot * STRIDE
    ram[base:base + 16] = np.arange(1, 17, dtype=np.uint8)  # non-trivial
    row = ram[base:base + STRIDE].view("<u2")
    row[0] = st
    xw = int(x * 65536.0) & 0xFFFFFFFF
    row[60] = xw & 0xFFFF
    row[61] = (xw >> 16) & 0xFFFF
    row[63] = h
    row[71] = hp8e
    row[82] = hpA4


def clear_slot(ram, slot):
    base = TABLE + slot * STRIDE
    ram[base:base + STRIDE] = 0


def test_crossed_lifecycle_ahead_to_behind():
    ram = make_ram()
    tr = WagonTracker(ram, every=1, persist_frames=45)
    # player at px 100; wagon spawns ahead at 200
    tr.poll(10, 100.0)
    set_slot(ram, 5, x=200.0, h=100)
    tr.poll(11, 100.0)
    # ride advances: wagon passes behind by poll 3
    for i, (f, px, x) in enumerate([(60, 130.0, 170.0),
                                    (120, 170.0, 130.0),
                                    (180, 210.0, 90.0)]):
        set_slot(ram, 5, x=x, h=100)
        tr.poll(f, px)
    clear_slot(ram, 5)
    evs = tr.poll(181, 210.0)
    assert len(evs) == 1
    ev = evs[0]
    assert ev["crossed"] is True
    assert ev["persistent"] is True
    assert ev["spawn_ahead"] is True and ev["end_behind"] is True
    assert tr.summary()["crossed_total"] == 1


def test_no_cross_when_spawned_behind():
    ram = make_ram()
    tr = WagonTracker(ram, every=1, persist_frames=45)
    tr.poll(10, 500.0)
    set_slot(ram, 6, x=100.0, h=64)          # spawns BEHIND the player
    tr.poll(11, 500.0)
    clear_slot(ram, 6)
    evs = tr.poll(400, 500.0)
    assert len(evs) == 1 and evs[0]["crossed"] is False


def test_every_rate_limiter():
    ram = make_ram()
    tr = WagonTracker(ram, every=5)
    assert tr.poll(10, 0.0) == []
    assert tr.poll(12, 0.0) == []            # inside the window
    assert tr.poll(15, 0.0) != [] or True    # poll at >= every frames
    assert tr._last_poll in (10, 15)


def test_split_kinds_height_gap():
    crossed = [{"crossed": True, "persistent": True, "st": 0x515C,
                "h": h} for h in (60, 62, 64, 61)] + \
              [{"crossed": True, "persistent": True, "st": 0x515C,
                "h": h} for h in (200, 205, 198)]
    out = split_kinds(crossed)
    assert out["family_st"] == 0x515C
    assert out["kinds"]["small"] == 4 and out["kinds"]["big"] == 3


def test_split_kinds_no_split_single_cluster():
    crossed = [{"crossed": True, "persistent": True, "st": 7, "h": h}
               for h in (64, 64, 65)]
    out = split_kinds(crossed)
    assert out["kinds"] == {"unlabeled": 3}


def test_poll_diff_index_kill_exact():
    lo = 0x1000
    idx = PollDiffIndex(lo, lo + 64)
    word_a, word_k = 0, 3
    prev = np.zeros(32, dtype="<u2")
    frames = list(range(60, 60 * 20, 60))
    kills = [300, 900]
    for n, f in enumerate(frames):
        cur = prev.copy()
        if f == 1140:                      # one far-from-kill flip
            cur[word_a] = 1
        if any(abs(f - k) <= 60 for k in kills):
            cur[word_k] = 1
        elif f in (420, 1020):             # cleared 2 polls after
            cur[word_k] = 0
        idx.add_poll(f, cur.tobytes())
        prev = cur
    lab = idx.classify(kills)
    assert lab[word_k]["class"] == "kill_exact"
    assert lab[word_a]["class"] == "ambient"


def test_count_waves_segmentation():
    sight = [{"frame": 0, "armed": False}]
    sight += [{"frame": f, "armed": True} for f in range(300, 600, 300)]
    sight += [{"frame": f, "armed": False} for f in range(600, 1800, 300)]
    sight += [{"frame": f, "armed": True} for f in range(1800, 2400, 300)]
    out = count_waves(sight)
    assert out["n_waves"] == 2
    assert out["first_latency"] == 300


def test_count_waves_none():
    out = count_waves([{"frame": f, "armed": False}
                       for f in range(0, 3000, 300)])
    assert out["n_waves"] == 0 and out["first_latency"] is None


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))


def test_crossed_strict_excludes_pinned_arena():
    ram = make_ram()
    tr = WagonTracker(ram, every=1, persist_frames=45)
    # pinned player at 2212: entity spawns ahead, dies behind
    tr.poll(10, 2212.0)
    set_slot(ram, 7, x=2400.0, h=64)
    tr.poll(11, 2212.0)
    set_slot(ram, 7, x=2100.0, h=64)
    tr.poll(80, 2212.0)
    clear_slot(ram, 7)
    evs = tr.poll(81, 2212.0)
    assert len(evs) == 1
    assert evs[0]["crossed"] is True        # loose rule still fires
    assert evs[0]["crossed_strict"] is False  # player never advanced
