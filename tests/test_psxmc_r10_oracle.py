#!/usr/bin/env python3
"""Mock tests for the round-10 PSXMC place7 instrument (NO emulator boot):
FIX-2 oracle parsing, FIX-1 stability gate, world walk, hotbar chain."""
import os
import sys

import numpy as np
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "scripts"))

import psxmc_r10_lib as L  # noqa: E402

P = 0x30000
RAM = 0x200000


class FakeMem:
    def __init__(self):
        self.buf = bytearray(RAM)

    def u8(self, a):
        return self.buf[a & 0xFFFFFFFF]

    def u16(self, a):
        return int(np.frombuffer(bytes(self.buf[a:a + 2]), "<u2")[0])

    def u32(self, a):
        return int(np.frombuffer(bytes(self.buf[a:a + 4]), "<u4")[0])

    def set32(self, a, v):
        self.buf[a:a + 4] = int(v & 0xFFFFFFFF).to_bytes(4, "little")

    def snapshot(self):
        return bytes(self.buf)


def _snap(fn):
    b = bytearray(RAM)
    fn(b)
    return bytes(b)


# ---------------- FIX-2 oracle parsing --------------------------------------
def test_breaking_candidates_finds_injected_triple():
    pos = [0, int(9.62 * L.ONE_BLOCK), 0]
    cam_y, _ = L.camera_world_y(pos[1])
    base = _snap(lambda b: None)
    hold = _snap(lambda b: (
        b.__setitem__(slice(P + 0x74, P + 0x80),
                      np.array([0, 5, 0], "<i4").tobytes()),
        b.__setitem__(slice(P + 0x84, P + 0x88),
                      np.array([0x60000], "<u4").tobytes())))
    cands = L.breaking_candidates(hold, base, P, cam_y, pos)
    assert any(c["off"] == 0x74 and c["ptr_off"] == 0x84 and
               c["hit"] == [0, 5, 0] for c in cands), cands


def test_breaking_candidates_rejects_above_camera():
    pos = [0, int(9.62 * L.ONE_BLOCK), 0]
    cam_y, _ = L.camera_world_y(pos[1])
    base = _snap(lambda b: None)
    hold = _snap(lambda b: (
        b.__setitem__(slice(P + 0x74, P + 0x80),
                      np.array([0, 47, 0], "<i4").tobytes()),
        b.__setitem__(slice(P + 0x84, P + 0x88),
                      np.array([0x60000], "<u4").tobytes())))
    assert L.breaking_candidates(hold, base, P, cam_y, pos) == []


def test_parse_and_validate_known_hit():
    pos = [0, int(9.62 * L.ONE_BLOCK), 0]
    cam_y, feet = L.camera_world_y(pos[1])
    assert abs(feet - 8.0) < 1e-3 and abs(cam_y - 9.7) < 1e-3
    hit, blk = L.parse_breaking_from_snap(
        _snap(lambda b: (
            b.__setitem__(slice(P + 0x74, P + 0x80),
                          np.array([0, 5, 0], "<i4").tobytes()),
            b.__setitem__(slice(P + 0x84, P + 0x88),
                          np.array([0x60000], "<u4").tobytes()))),
        P, 0x74, 0x84)
    assert hit == [0, 5, 0] and blk == 0x60000
    ok, why = L.validate_known_hit(hit, pos, cam_y)
    assert ok, why
    # a hit 3 blocks ahead is NOT the known straight-down hit
    ok2, why2 = L.validate_known_hit([0, 4, 3], pos, cam_y)
    assert not ok2 and "column" in why2
    # a hit deeper than reach 6 is rejected
    ok3, why3 = L.validate_known_hit([0, 3, 0], pos, cam_y)
    assert not ok3 and "reach" in why3


def test_hit_geometry_matches_raycast_reach():
    pos = [0, 0, 0]
    cam_y = 6.7
    g = L.hit_geometry([0, 4, 0], pos, cam_y)
    assert g["in_reach"] and g["dx"] == 0
    g2 = L.hit_geometry([0, 0, 6], pos, cam_y)
    assert not g2["in_reach"]


def test_expected_surface_y_bumps():
    assert L.expected_surface_y(0, 0) == 5
    assert L.expected_surface_y(1, 1) == 4
    assert L.expected_surface_y(3, 6) == 5
    assert L.expected_surface_y(2, 5) == 4


# ---------------- FIX-1 stability gate --------------------------------------
def test_stability_gate_stable_world():
    frames = {"n": 0}
    frame = np.zeros((4, 4, 3), np.uint8)

    def run(nf):
        frames["n"] += nf

    def grab():
        return frame

    ok, waited, streak = L.StabilityGate(run, grab, n=3, max_wait=20).check()
    assert ok and streak == 3 and waited <= 4


def test_stability_gate_unstable_world():
    frames = {"n": 0}

    def run(nf):
        frames["n"] += nf

    def grab():
        f = np.zeros((4, 4, 3), np.uint8)
        f[0, 0, 0] = frames["n"] % 2
        return f

    ok, waited, streak = L.StabilityGate(run, grab, n=2, max_wait=6).check()
    assert not ok and waited >= 6


def test_stability_gate_settles_after_drift():
    frames = {"n": 0}

    def run(nf):
        frames["n"] += nf

    def grab():
        f = np.zeros((4, 4, 3), np.uint8)
        if frames["n"] < 3:      # drift for the first 3 idle frames only
            f[0, 0, 0] = frames["n"]
        return f

    ok, waited, streak = L.StabilityGate(run, grab, n=3, max_wait=40).check()
    assert ok and streak == 3


# ---------------- pixel band metrics ----------------------------------------
def test_diff_bands_splits_sky_ground_hud():
    a = np.zeros((240, 320, 3), np.uint8)
    b = a.copy()
    b[10, 5, 0] = 30                       # sky band (row < 78)
    b[150, 100, 1] = 40                    # ground band
    b[220, 100, 2] = 50                    # HUD band (x 56..264, y 208..240)
    m = L.diff_bands(a, b)
    assert m["sky_px"] == 1 and m["ground_px"] == 1 and m["hud_px"] == 1
    assert m["world_px"] == 2 and m["max_d"] == 50


# ---------------- world walk (in-world block read) --------------------------
def _build_world(mem):
    """Mock the REAL static ABI (round-10 disasm ground truth):
    World.chunks @ +0x3144 (7x7 Chunk*, ax+7*az, NULL allowed),
    Chunk.blocks @ +0x8C (512 IBlock*, x+8z+64y),
    IBlock+0 = u32 pointer to Block, Block.id = u8 at that pointer."""
    W = 0x40000
    mem.set32(L.A_WORLD, W)
    # window/origin words: origin x/z (W+0/W+8), shifts (W+0x18/W+0x1C)
    mem.set32(W + 0, 0)
    mem.set32(W + 8, 0)
    mem.set32(W + 0x18, 0)
    mem.set32(W + 0x1C, 0)
    chunks_run = W + L.WorldReader.STATIC_CHUNKS_OFF
    C0 = 0x50000
    blocks_arr = C0 + L.WorldReader.STATIC_BLOCKS_OFF
    for i in range(49):
        mem.set32(chunks_run + 4 * i, C0)
    for i in range(512):
        # IBlock* -> per-block instance whose +0 points at a Block struct
        mem.set32(blocks_arr + 4 * i, 0x60000 + 4 * i)
        mem.set32(0x60000 + 4 * i, 0x64000 + 4 * i)
        mem.buf[0x64000 + 4 * i] = 0            # default id = air
    def bid(idx, v):
        mem.buf[0x64000 + 4 * idx] = v
    bid(0 + 0 * L.CHUNK_SIZE + 4 * 64, 2)       # (0,4,0) grass: x+8z+64y
    bid(3 + 3 * L.CHUNK_SIZE + 5 * 64, 58)      # (3,5,3) crafting table
    bid(7 + 7 * L.CHUNK_SIZE + 7 * 64, 1)       # (7,7,7) stone
    return W


def test_world_reader_walk_and_ids():
    mem = FakeMem()
    _build_world(mem)
    wr = L.WorldReader(mem)
    info = wr.discover()
    assert info["offset_source"] == "static-disasm"
    assert info["chunks_off"] == 0x3144 and info["blocks_off"] == 0x8C
    assert wr.block_id(0, 4, 0) == 2
    assert wr.block_id(3, 5, 3) == 58
    assert wr.block_id(7, 7, 7) == 1
    assert wr.block_id(2, 6, 2) == 0            # air cell (id byte 0)
    assert wr.block_id(0, 9, 0) is None         # above WORLD_HEIGHT
    assert wr.block_id(0, -1, 0) is None


def test_world_reader_rejects_bad_world_ptr():
    mem = FakeMem()
    wr = L.WorldReader(mem)
    with pytest.raises(RuntimeError):
        wr.discover()


# ---------------- hotbar chain ----------------------------------------------
def test_find_hotbar_chain_and_stack():
    mem = FakeMem()
    mem.set32(P + 0x58, 0x70000)                # IUI hotbar .self
    mem.buf[0x70008] = 1                        # ui.active
    mem.buf[0x70064] = 0                        # selected_slot = 0
    mem.set32(0x7001C, 0x71000)                 # slots[0].data.item
    mem.set32(0x71000, 58)                      # Item.id
    mem.buf[0x7100C] = 26                       # Item.stack_size
    hb = L.find_hotbar(mem, P)
    assert hb and hb["hotbar_off"] == 0x58 and hb["stack"] == 26
    assert hb["item_id"] == 58 and hb["via"] == "item"
    assert hb["stack_addr"] == 0x7100C


def test_find_hotbar_via_ref_slot():
    mem = FakeMem()
    mem.set32(P + 0x58, 0x70000)
    mem.buf[0x70008] = 0
    mem.buf[0x70064] = 2                        # select slot 2
    mem.set32(0x7002C, 0x72000)                 # slots[2].data = Slot*
    mem.set32(0x72000, 0x71000)                 # Slot.data.item
    mem.set32(0x71000, 58)
    mem.buf[0x7100C] = 24
    hb = L.find_hotbar(mem, P)
    assert hb and hb["via"] == "ref" and hb["stack"] == 24
    assert hb["selected"] == 2


def test_find_hotbar_returns_none_on_garbage():
    mem = FakeMem()
    assert L.find_hotbar(mem, P) is None


def test_find_inventory_is_the_other_iui():
    mem = FakeMem()
    mem.set32(P + 0x58, 0x70000)                # hotbar
    mem.buf[0x70008] = 1
    mem.buf[0x70064] = 0
    mem.set32(0x7001C, 0x71000)
    mem.set32(0x71000, 58)
    mem.buf[0x7100C] = 26
    mem.set32(P + 0x54, 0x73000)                # inventory IUI
    mem.buf[0x73008] = 0                        # ui.active false
    hb = L.find_hotbar(mem, P)
    inv = L.find_inventory(mem, P, hb["hotbar_off"])
    assert inv and inv["inv_off"] == 0x54 and inv["active"] is False


# ---------------- stack scan -------------------------------------------------
def test_stack_scan_itemid_context():
    pre = bytearray(RAM)
    post = bytearray(RAM)
    a = 0x7CDA0
    pre[a] = 26
    post[a] = 25
    pre[a - 8:a - 4] = np.array([58], "<u4").tobytes()
    hits = L.stack_scan(bytes(pre), bytes(post))
    assert any(h["is_stack_addr"] and h["before"] == 26 and h["after"] == 25
               for h in hits)
    # decoy without ItemID context must be skipped
    pre2 = bytearray(pre)
    post2 = bytearray(post)
    pre2[0x9000] = 26
    post2[0x9000] = 25
    assert not any(int(h["addr"], 16) == 0x9000 for h in
                   L.stack_scan(bytes(pre2), bytes(post2)))
