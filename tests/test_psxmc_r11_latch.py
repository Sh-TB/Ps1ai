#!/usr/bin/env python3
"""Mock tests for the round-11 PSXMC canonical-latch instrument (NO
emulator): static BreakingState window reads (breaking_current),
repeat-latch tracking, disambiguated probe parsing, placement candidate
generation, static-layout invariants."""
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import psxmc_r10_lib as L10  # noqa: E402
import psxmc_r11_lib as R11  # noqa: E402

P = 0x30000
RAM = 0x200000
ONE = 4096


class FakeMem:
    def __init__(self):
        self.buf = bytearray(RAM)

    def u8(self, a):
        return self.buf[a & 0xFFFFFFFF]

    def u32(self, a):
        return int(np.frombuffer(bytes(self.buf[a:a + 4]), "<u4")[0])

    def set32(self, a, v):
        self.buf[a:a + 4] = int(v & 0xFFFFFFFF).to_bytes(4, "little")

    def set8(self, a, v):
        self.buf[a] = v & 0xFF

    def snapshot(self):
        return bytes(self.buf)


def _snap(fn):
    b = bytearray(RAM)
    fn(b)
    return bytes(b)


def _inject_latch(b, hit=(0, 5, 0), blk=0x60000, ticks=(0, 1230, ONE * 2),
                  flags=0x3F):
    b[P + 0x6C:P + 0x70] = np.array([ticks[0]], "<i4").tobytes()
    b[P + 0x70:P + 0x74] = np.array([ticks[1]], "<i4").tobytes()
    b[P + 0x74:P + 0x78] = np.array([ticks[2]], "<i4").tobytes()
    b[P + 0x78:P + 0x84] = np.array(hit, "<i4").tobytes()
    b[P + 0x84] = flags
    b[P + 0x88:P + 0x8C] = np.array([blk], "<u4").tobytes()


class FakeWorldReader:
    """World-arbiter stub: returns 2 (grass) for the injected cells."""

    def __init__(self, ids=None):
        self.ids = ids or {}

    def block_id(self, bx, by, bz):
        return self.ids.get((bx, by, bz), 0)


# ---------------- static layout invariants -----------------------------------
def test_static_layout_matches_disasm():
    # ground truth from updateBreakingState @0x80013C9C:
    #   addiu $s3, $a0, 0x6C ; sw $zero run 0x6C..0x88 ; sw result->pos
    #   -> 0x78/0x7C/0x80 ; sw result->block -> 0x88
    assert R11.BREAKING_OFF == 0x6C
    assert R11.BREAKING_LAYOUT == {
        "ticks_precise": 0x6C, "ticks_per_stage": 0x70,
        "ticks_so_far": 0x74, "position": 0x78, "flags": 0x84,
        "block": 0x88}
    assert R11.BREAKING_LAYOUT["block"] == R11.BREAKING_OFF + 0x1C
    assert R11.BREAKING_LAYOUT["position"] == R11.BREAKING_OFF + 0x0C
    assert R11.STORE_SITE_VA == 0x80013F40
    assert R11.UBS_VA == 0x80013C9C
    assert R11.LATCH_CALL_VA == 0x800144A4


def test_r11_window_is_inside_r10_candidate_convention():
    # the r10 diff scanner used K=triples with a heap ptr at K+12..K+20;
    # the static window (position 0x78, block 0x88 = K+0x10) must satisfy
    # that convention so both instruments can be cross-checked live.
    k = R11.BREAKING_LAYOUT["position"]
    ptr = R11.BREAKING_LAYOUT["block"]
    assert 12 <= ptr - k <= 20


# ---------------- breaking_current -------------------------------------------
def test_breaking_current_from_snapshot():
    snap = _snap(lambda b: _inject_latch(b))
    cur = R11.breaking_current(None, P, snap=snap)
    assert cur["hit"] == [0, 5, 0]
    assert cur["block_ptr"] == 0x60000
    assert cur["ticks"] == {"precise": 0, "per_stage": 1230, "so_far": ONE * 2}
    assert cur["flags"] == 0x3F
    assert cur["live"] is True


def test_breaking_current_live_mem():
    mem = FakeMem()
    _inject_latch(mem.buf)
    cur = R11.breaking_current(mem, P)
    assert cur["hit"] == [0, 5, 0] and cur["block_ptr"] == 0x60000
    assert cur["live"] is True
    # agrees with the r10 generic snapshot parser at the same offsets
    hit, blk = L10.parse_breaking_from_snap(
        mem.snapshot(), P, 0x78, 0x88)
    assert hit == cur["hit"] and blk == cur["block_ptr"]


def test_breaking_current_zero_when_reset():
    mem = FakeMem()
    cur = R11.breaking_current(mem, P)
    assert cur["hit"] == [0, 0, 0] and cur["block_ptr"] == 0
    assert cur["live"] is False and cur["ticks"]["so_far"] == 0
    assert R11.zero_current(mem, P) is True
    _inject_latch(mem.buf, hit=(2, 4, 1), blk=0x61000)
    assert R11.zero_current(mem, P) is False


def test_breaking_current_not_live_with_zero_ptr():
    snap = _snap(lambda b: _inject_latch(b, blk=0))
    assert R11.breaking_current(None, P, snap=snap)["live"] is False
    snap2 = _snap(lambda b: _inject_latch(b, hit=(0, 0, 0), blk=0x60000))
    assert R11.breaking_current(None, P, snap=snap2)["live"] is False


# ---------------- RepeatLatchTracker -----------------------------------------
def _parse_obs(hit=(0, 5, 0), live=True, reset=True, grew=False,
               aim=90.0, blk=0x60000, so_far=ONE * 2):
    return {"hit": list(hit), "block_ptr": blk if live else 0,
            "ticks": {"precise": 0, "per_stage": 1230,
                      "so_far": so_far if live else 0},
            "live": live, "reset_by_late": reset,
            "ticks_grew": grew, "aim_deg": aim}


def test_tracker_live_window_consistent():
    tr = R11.RepeatLatchTracker(min_live=2)
    tr.observe(_parse_obs(aim=90.0, grew=True))
    v = tr.observe(_parse_obs(aim=90.0, grew=True))
    assert v["n_live"] == 2 and v["resets_ok"] and v["ticks_grew"]
    assert v["live"], v


def test_tracker_pos_follows_aim():
    tr = R11.RepeatLatchTracker(min_live=2)
    tr.observe(_parse_obs(hit=(0, 5, 0), aim=90.0))
    v = tr.observe(_parse_obs(hit=(0, 5, 3), aim=20.0))
    assert v["pos_follows_aim"] and v["live"], v


def test_tracker_frozen_stale_mirror():
    tr = R11.RepeatLatchTracker(min_live=2)
    tr.observe(_parse_obs(reset=False))
    v = tr.observe(_parse_obs(reset=False))
    assert not v["resets_ok"] and not v["live"]
    assert "never reset" in v["why"]


def test_tracker_needs_min_live():
    tr = R11.RepeatLatchTracker(min_live=2)
    v = tr.observe(_parse_obs())
    assert not v["live"] and "n_live=1<min" in v["why"]


def test_tracker_dead_probes_only():
    tr = R11.RepeatLatchTracker(min_live=2)
    tr.observe(_parse_obs(live=False))
    v = tr.observe(_parse_obs(live=False))
    assert not v["live"] and v["n_live"] == 0


# ---------------- dead-reckon ring aim ---------------------------------------
DEG = L10.DEG


class RingCore:
    """Fake core: LOOK_DOWN ('B') adds 15 deg/frame, LOOK_UP ('X')
    subtracts; ring wraps mod 2^24 like the game."""

    def __init__(self, ring=0):
        self.ring = ring % L10.PITCH_MOD
        self.frames = []

    def run(self, n, buttons):
        self.frames.append((n, tuple(buttons)))
        for _ in range(n):
            if "B" in buttons:
                self.ring = (self.ring + int(15 * DEG)) % L10.PITCH_MOD
            elif "X" in buttons:
                self.ring = (self.ring - int(15 * DEG)) % L10.PITCH_MOD


def test_nearest_reachable_ring_aligned():
    step = int(15 * DEG)                    # the raw actuator step
    ref = int(2.3 * DEG)
    ring, deg = R11.nearest_reachable_ring(ref, 90.0, step)
    assert deg == 92.3                      # ref + 6*15 (nominal)
    assert ring == (ref + 6 * step) % L10.PITCH_MOD
    ring2, deg2 = R11.nearest_reachable_ring(ref, 88.0, step)
    assert deg2 == 92.3                     # nearest reachable to 88 is 92.3
    assert ring2 == ring


def test_nearest_reachable_ring_wrap_forward():
    step = int(15 * DEG)
    # forward wrap wins: 350 + 15 -> 365 == 5 deg
    ref = int(350.0 * DEG)
    ring, deg = R11.nearest_reachable_ring(ref, 0.0, step)
    assert deg == 5.0
    assert ring == (ref + step) % L10.PITCH_MOD
    # k=0 wins when no grid point is closer: from 355, target 0
    ref0 = int(355.0 * DEG)
    ring0, deg0 = R11.nearest_reachable_ring(ref0, 0.0, step)
    assert deg0 == 355.0 and ring0 == ref0 % L10.PITCH_MOD


def test_aim_ring_dead_reckon_exact():
    step = int(15 * DEG)
    rc = RingCore(ring=int(2.3 * DEG))
    target = (rc.ring + 6 * step) % L10.PITCH_MOD   # REACHABLE target
    aim = R11.aim_ring_dead_reckon(rc, lambda: rc.ring, target, step)
    assert aim["err_deg"] == 0.0 and aim["frames"] == 6
    assert rc.ring == target
    # approaching from above uses LOOK_UP
    rc2 = RingCore(ring=int(200.0 * DEG))
    target2 = (rc2.ring - 7 * step) % L10.PITCH_MOD
    aim2 = R11.aim_ring_dead_reckon(rc2, lambda: rc2.ring, target2, step)
    assert aim2["err_deg"] == 0.0
    assert rc2.ring == target2
    assert any("X" in b for _, b in rc2.frames)


def test_aim_ring_dead_reckon_substep_residual_honest():
    # The LOOK actuator is 15-deg quantized: a 7-deg residual is below
    # half a step, so the honest outcome is NO frame spent (n=0) and a
    # reported residual at the quantization floor.
    step = int(15 * DEG)
    rc = RingCore(ring=int(85.3 * DEG))
    target = int(92.3 * DEG) % L10.PITCH_MOD          # +7 deg
    aim = R11.aim_ring_dead_reckon(rc, lambda: rc.ring, target, step)
    assert aim["frames"] == 0 and rc.ring == int(85.3 * DEG) % L10.PITCH_MOD
    assert abs(aim["err_deg"]) <= 7.5 + 1e-6
    # an 8.3-deg miss rounds UP to one full step (n=1); the residual
    # afterwards (-6.7 deg) is again below half a step -> no nudge,
    # single frame spent, residual reported honestly
    rc3 = RingCore(ring=int(84.0 * DEG))
    target3 = int(92.3 * DEG) % L10.PITCH_MOD         # +8.3 deg
    aim3 = R11.aim_ring_dead_reckon(rc3, lambda: rc3.ring, target3, step)
    assert aim3["frames"] == 1
    assert abs(aim3["err_deg"]) <= 7.5 + 1e-6



# ---------------- placement candidates ---------------------------------------
def test_placement_candidates_neighbourhood():
    c = R11.placement_candidates((2, 4, 3), fwd_sign=1)
    assert c["top"] == (2, 5, 3)
    assert c["near"] == (2, 4, 2) and c["far"] == (2, 4, 4)
    assert c["left"] == (1, 4, 3) and c["right"] == (3, 4, 3)
    c2 = R11.placement_candidates((2, 4, 3), fwd_sign=-1)
    assert c2["near"] == (2, 4, 4) and c2["far"] == (2, 4, 2)


# ---------------- top_nonair (world walk wrapper) ----------------------------
def test_top_nonair_scans_down():
    ids = {(3, 4, 2): 3, (3, 5, 2): 2}
    wr = FakeWorldReader(ids)
    assert R11.top_nonair(wr, 3, 2) == (5, 2)
    assert R11.top_nonair(wr, 9, 9) == (None, None)


# ---------------- stable gate (r11 re-export sanity) -------------------------
def test_stable_gate_bit_exact():
    class FakeCore:
        def __init__(self, m):
            self.m = m

        def run(self, n, buttons):
            pass

    mem = FakeMem()
    ok, t = R11.stable_gate(FakeCore(mem), mem)
    assert ok is True and t < 3
    mem2 = FakeMem()

    class FlipCore:
        i = {"n": 0}

        def run(self, n, buttons):
            FlipCore.i["n"] += 1
            mem2.set32(0x1234, FlipCore.i["n"])

    ok2, t2 = R11.stable_gate(FlipCore(), mem2, tries=2)
    assert ok2 is False and t2 == 2
