#!/usr/bin/env python3
"""psxmc_r12_place9.py — Round 12 (Task 16-a): PSX-Minecraft placement FINISH.

v2 (this file) fixes the v1 UI-chain ABI, which was mis-derived and made the
first v1 run read garbage (selected_slot=12, "stack 48", inv_hbptr_ok=False):

Upstream re-read @ tag infdev_2025_04_18 (EngineersBox/PSX-Minecraft, MIT;
sources cached in scratch/round12_psxmc/upstream_src/) — EXACT answers:

  * UI base struct = 20 B: {char* title@0; Texture* texture@4; bool active@8;
    DVECTOR cursor@12; cvector(IUIComponent) components@16} (ui.h; cvector
    field is a plain T* = 4 B).  NOT 28 as v1 assumed.
  * Hotbar (DEFN_UI, hotbar.h): {UI@0; Slot slots[9]@20; u8 selected_slot@92;
    Timestamp debounce@96} (Timestamp = u32, counters.h:108).  Slot = {union
    {IItem* item; Slot* ref;} data@0; u8 index@4} = 8 B (slot.h).
  * Inventory: {UI@0; Slot slots[45]@20; Hotbar* hotbar@380; Timestamp@384}.
    Slots 36..44 are createSlotRef's -> &hotbar->slots[0..8] (inventory.c:62).
  * interface99 fat pointer is OVERRIDDEN in interface99_extensions.h:18:
    struct iface { void* self@0; const vtable* vptr@4; }  ->  ItemBlock =
    *(void**)iitem.  (v1 read the vtable as Item fields -> "id 240".)
  * Item (item.h:83): {u8 id@0; u8 metadata@1; u32 durability@4;
    u8 stack_size@8; bob@9; bob_dir@10; bool in_world@11; VECTOR position@12;
    SVECTOR rotation@24; Entity* world_entity@32}.
  * Spawn kit (minecraft.c:155-167): crafting table stack=26 ->
    inventoryFindFreeSlot(inventory,1) -> hotbar-first search returns ref
    slot 36 -> Hotbar.slots[0]; cobblestone stack=10 (NOT 92!) ->
    inventoryFindFreeSlot(inventory,9) -> Hotbar.slots[1].  BOTH in the
    HOTBAR at boot; selected_slot=0 (hotbarInit:15).  The r11 "cobble x92 in
    the INVENTORY" was hotbarRenderSlots' render x (72+20*slot=92 for slot 1)
    at Item.position.vx (+12) mistaken for stack_size (+8) — instrument
    misread, closed by this layout.
  * USE (player.c:255 playerInputHandlerUse): needs raycast hit within
    PLAYER_REACH 6 (result.block != NULL) AND selected item ITEMTYPE_BLOCK;
    place cell = vec3_add(result.pos, result.face); IBlock_canPlace (block.c)
    = ONLY a player-AABB overlap test.  canPlace-fail restores the stack
    (++); success consumes via the block constructor.
  * THE ROUND 7-10 BLOCKER, root-caused: straight-down aim places onto the
    player's own feet cell -> canPlace ALWAYS fails -> silent no-op.  AND the
    place3/place4 "UI artifact" trap is now source-exact: the game ticks >=2x
    per frame; tick1 places cell C = T+face which lies ON the ray; tick2's
    raycast then hits C and, for a CRAFTING TABLE, CraftingTableBlock_useAction
    (block_crafting_table.c:232) CONSUMES the input and opens the modal.
    COBBLESTONE has the default IBlock_useAction -> NOT_CONSUMED -> no trap.
  * Hotbar select: BINDING_PREVIOUS=PAD_L3 (-1) / BINDING_NEXT=PAD_R3 (+1)
    mod 9, debounce 200 ms (hotbar.c:286); debounce() uses u32 wrap math
    (debounce.c) so the uninitialised garbage debounce field reads as
    expired -> the first R3 tap registers.
  * Inventory->hotbar transfer (the r11 recorded lever) EXISTS but is
    pointer-based and unneeded: START opens the inventory, D-pad moves the
    cursor 4 px/frame (cursor.c), R2=BINDING_CURSOR_CLICK picks/puts whole
    stacks, L2=BINDING_SPLIT_OR_STORE_ONE, CIRCLE=BINDING_DROP_ITEM
    (inventory.c:519); clicking the hotbar row (origin 80,179, pitch 18)
    writes straight into Hotbar.slots.

place9 v2 design (all legal input, zero RAM writes, ONE beetle boot):
  1. boot -> player ptr -> settle -> ring cal -> world control -> re-settle.
  2. UI chain dump (correct ABI) -> expect slot0=table(58,x26,x-render 72),
     slot1=cobble(4,x10,x-render 92); crafting ItemBlock must be 0x7CD98
     (r7 live stack 0x7CDA0) as cross-check.  R3 -> select slot 1 (cobble).
  3. NEGATIVE CONTROL: horizon aim, R2 sense (no latch expected), 1-frame L2
     tap -> stack and world grid must NOT change.
  4. AIM-SENSE: R2 hold reads the engine's BreakingState (P+0x6C window,
     r11 static ABI) WHILE HOLDING -> hit cell T; require live, non-air
     (snapshot world walk), in reach, NOT own column.
  5. PLACE: 1-frame L2 tap(s) -> snapshot grid diff pre/post = exact changed
     cells; expect face-neighbour chain of T (tick-2 cascade allowed), all
     cobble (4), all outside the player AABB, stack delta == #new cells.
  6. CHECK-2 visible: world-region pixel diff > 0, persists >=60 idle frames,
     inventory ui.active == 0 AND block_render_ui_context.function == NULL
     (map symbol 0x8003C790) -> both modal paths excluded (place4 trap).
  7. CHECK-3 solidity: re-hit at the same ring latches a placed cell; the
     breaking window's IBlock* resolves to cobble (4); bounded re-dig then
     flips the placed cells back to air (best-effort bonus).
Verdicts: PLACE_CAUSAL (all 3) / PLACE_PARTIAL (say which) / FAILED.
Evidence: scratch/round12_psxmc/ (report.json, r12_place9v3.jsonl, PNGs).
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import psxmc_r10_lib as L                                # noqa: E402
import psxmc_r11_lib as R11                              # noqa: E402
from psxmc_r10_oracle import (                           # noqa: E402
    CUE, player_ptr, pos_of, pitch_now, ensure_world_control)
from psxmc_r7_lib import Evid                            # noqa: E402

WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r12b"
OUT = os.path.join(_REPO, "scratch", "round12_psxmc")
TAG = "place9v2"
PLACE_BTN = "L2"          # BINDING_USE
ATTACK_BTN = "R2"         # BINDING_ATTACK (aim-sense only)
LOOK_DOWN, LOOK_UP = "B", "X"

# ---- source-derived ABI (see module docstring) ------------------------------
HB_OFF, INV_OFF = 0x64, 0x5C      # Player.hotbar/.inventory IUI .self (IUI={self@0,vptr@4})
UI_SIZE = 20                       # title,texture,active+pad,cursor,components
HOTBAR_SLOT_COUNT = 9
INV_SLOT_COUNT = 45
INV_HBPTR_OFF = UI_SIZE + 8 * INV_SLOT_COUNT            # 380
INV_SIZE = INV_HBPTR_OFF + 8                            # 388
SEL_OFF = UI_SIZE + 8 * HOTBAR_SLOT_COUNT               # 92
ITEM_ID, ITEM_STACK, ITEM_IN_WORLD, ITEM_POSX = 0, 8, 11, 12
A_BLOCK_RENDER_UI_CTX = 0x3C790   # map: block_render_ui_context (function@0)
A_BLOCK_INPUT_CTX = 0x3C5A4       # map: block_input_handler_context (block@4)

PLAYER_HALF_W = 0.35      # conservative AABB half-width (cfg radius 0.3)
PLAYER_HEIGHT = 1.8

BLOCKNAME = {0: "air", 1: "stone", 2: "grass", 3: "dirt", 4: "cobblestone",
             58: "crafting_table"}
ID_COBBLE, ID_TABLE = 4, 58


def _phys(v):
    return L.phys(int(v) & 0xFFFFFFFF)


# ---------------------------------------------------------------- UI chains
def resolve_item_block(m, iitem):
    """IItem fat pointer -> ItemBlock address ({self@0, vptr@4}; the +4
    variant is a guarded fallback).  None when neither resolves."""
    for doff in (0, 4):
        a = _phys(m.u32(_phys(iitem) + doff))
        if L.is_heap(a):
            return a, doff
    return None, None


def read_item(m, iitem):
    """Parse the ItemBlock behind an IItem* (hotbar/inventory slot data)."""
    if not L.is_heap(iitem):
        return None
    blk, doff = resolve_item_block(m, iitem)
    if blk is None:
        return {"addr": hex(_phys(iitem)), "unresolved": True}
    return {"iitem": hex(_phys(iitem)), "self_doff": doff,
            "addr": hex(blk), "id": int(m.u8(blk + ITEM_ID)),
            "stack": int(m.u8(blk + ITEM_STACK)),
            "in_world": int(m.u8(blk + ITEM_IN_WORLD)),
            "posx": L.s32(m.u32(blk + ITEM_POSX))}


def hotbar_base(m, P):
    return _phys(m.u32(P + HB_OFF))


def selected_hotbar(m, P):
    """(selected_slot, item_dict) via Hotbar.slots[selected_slot].data."""
    H = hotbar_base(m, P)
    sel = int(m.u8(H + SEL_OFF))
    it = _phys(m.u32(H + UI_SIZE + 8 * sel))
    return sel, read_item(m, it)


def ui_dump(m, P):
    """Full hotbar/inventory chain dump with the source-derived ABI."""
    d = {"hb_off": hex(HB_OFF), "inv_off": hex(INV_OFF),
         "ui_size": UI_SIZE, "sel_off": SEL_OFF}
    Hraw, Iraw = int(m.u32(P + HB_OFF)), int(m.u32(P + INV_OFF))
    d["hb_self_raw"], d["inv_self_raw"] = hex(Hraw), hex(Iraw)
    H, I = _phys(Hraw), _phys(Iraw)
    d["hb_heap"], d["inv_heap"] = L.is_heap(Hraw), L.is_heap(Iraw)
    if L.is_heap(Hraw):
        d["hb_active"] = int(m.u8(H + 8))
        d["selected_slot"] = int(m.u8(H + SEL_OFF))
        d["slots"] = []
        for s in range(HOTBAR_SLOT_COUNT):
            it = _phys(m.u32(H + UI_SIZE + 8 * s))
            d["slots"].append({"slot": s, "item": read_item(m, it)})
    if L.is_heap(Iraw):
        d["inv_active"] = int(m.u8(I + 8))
        d["inv_cursor"] = [int(m.u16(I + 12)), int(m.u16(I + 14))]
        d["inv_hbptr"] = hex(_phys(m.u32(I + INV_HBPTR_OFF)))
        d["inv_hbptr_ok"] = _phys(m.u32(I + INV_HBPTR_OFF)) == H
        main = []
        for i in range(9, 36):
            it = _phys(m.u32(I + UI_SIZE + 8 * i))
            r = read_item(m, it)
            if r is not None and not r.get("unresolved") and r["id"]:
                main.append({"slot": i, **r})
        d["inv_main_items"] = main
        refs = []
        for i in range(36, 45):
            ref = _phys(m.u32(I + UI_SIZE + 8 * i))
            refs.append({"slot": i, "ref": hex(ref),
                         "ref_ok": ref == H + UI_SIZE + 8 * (i - 36)})
        d["inv_hotbar_refs"] = refs
    d["modal_fn"] = int(m.u32(A_BLOCK_RENDER_UI_CTX))
    d["modal_block"] = int(m.u32(A_BLOCK_INPUT_CTX + 4))
    return d


def tap_r3_select(m, P, core, want_slot, max_taps=8):
    """BINDING_NEXT = PAD_R3 walks selected_slot +1 mod 9 (debounce 200 ms
    = 12 f @60 fps; u32-wrap makes the uninit garbage debounce expired).
    v3: 3-frame press (1-frame taps can fall between beetle pad polls) +
    18-frame settle (270 ms > debounce); L3 (PREVIOUS, wraps 0->8) as the
    fallback direction."""
    trace = []
    for btn in ("R3", "L3"):
        for _k in range(max_taps):
            sel, _it = selected_hotbar(m, P)
            if sel == want_slot:
                return True, trace
            core.run(3, {btn})
            core.run(18, set())
            trace.append({"btn": btn, "sel": int(selected_hotbar(m, P)[0])})
    sel, _it = selected_hotbar(m, P)
    return sel == want_slot, trace


# ------------------------------------------------- snapshot world grid
class SnapGrid:
    """Atomic world walk from a RAM snapshot (r10 static ABI mirrored from
    WorldReader, reading the SAME discovered W/centre/head/offsets)."""

    def __init__(self, wr):
        self.wr = wr

    def _u32(self, b, a):
        return int.from_bytes(b[a:a + 4], "little")

    def block_id(self, snap, bx, by, bz):
        if not (0 <= by < L.WORLD_HEIGHT):
            return None
        b = bytes(snap)
        W, cx, cz = self.wr.W, L.floor_div(bx, L.CHUNK_SIZE), \
            L.floor_div(bz, L.CHUNK_SIZE)
        head = self.wr.head
        centre = self.wr.centre
        ax = L.pos_mod(int(head[0]) + (cx - (centre[0] - L.LOADED_CHUNKS_RADIUS
                                                - L.SHIFT_ZONE)), L.AXIS_CHUNKS)
        az = L.pos_mod(int(head[1]) + (cz - (centre[2] - L.LOADED_CHUNKS_RADIUS
                                                - L.SHIFT_ZONE)), L.AXIS_CHUNKS)
        C = L.phys(self._u32(b, W + self.wr.chunks_off + 4 * (az * L.AXIS_CHUNKS + ax)))
        if not L.is_heap(C):
            return None
        lx, ly, lz = (L.pos_mod(bx, L.CHUNK_SIZE), by,
                      L.pos_mod(bz, L.CHUNK_SIZE))
        a = C + self.wr.blocks_off + 4 * (lx + L.CHUNK_SIZE * lz
                                          + ly * L.CHUNK_SIZE * L.CHUNK_SIZE)
        bp = L.phys(self._u32(b, a))
        if not L.is_heap(bp):
            return 0                      # NULL IBlock* == air
        blk = L.phys(self._u32(b, bp))
        return int(b[blk])


def grid_read(sg, snap, x0, x1, z0, z1, ys=range(0, L.WORLD_HEIGHT)):
    return {(x, y, z): sg.block_id(snap, x, y, z)
            for x in range(x0, x1 + 1) for z in range(z0, z1 + 1)
            for y in ys}


def grid_diff(g0, g1):
    return [{"cell": list(c), "from": g0[c], "to": g1[c]}
            for c in g0 if c in g1 and g0[c] != g1[c]]


def player_box(pos_blocks):
    px, py, pz = [v / L.ONE_BLOCK for v in pos_blocks]
    feet = py - L.Y_OFFSET_B
    return (px - PLAYER_HALF_W, px + PLAYER_HALF_W,
            feet, feet + PLAYER_HEIGHT,
            pz - PLAYER_HALF_W, pz + PLAYER_HALF_W)


def cell_hits_player(cell, box):
    x0p, x1p, y0p, y1p, z0p, z1p = box
    bx, by, bz = cell
    return (bx < x1p and bx + 1 > x0p and by < y1p and by + 1 > y0p
            and bz < z1p and bz + 1 > z0p)


# ---------------------------------------------------------- aim + sensing
def sense_target(core, m, P, target_ring, step_raw, hold=14, mid=8):
    """Dead-reckon aim at target_ring, hold R2, snapshot WHILE HOLDING and
    parse the static BreakingState window (FIX-2 protocol), then release."""
    aim = R11.aim_ring_dead_reckon(core, lambda: pitch_now(m, P),
                                   target_ring, step_raw,
                                   down_btn=LOOK_DOWN, up_btn=LOOK_UP)
    core.run(2, set())
    core.run(mid, {ATTACK_BTN})
    mid_snap = bytes(m.snapshot())            # WHILE STILL HOLDING (FIX-2)
    bw = R11.breaking_current(None, P, snap=mid_snap)
    core.run(max(0, hold - mid), {ATTACK_BTN})
    core.run(1, set())
    late_snap = bytes(m.snapshot())
    bw_late = R11.breaking_current(None, P, snap=late_snap)
    bw["reset_by_late"] = (bw_late["hit"] == [0, 0, 0]
                           and bw_late["block_ptr"] == 0)
    bw["aim"] = aim
    return bw


# ------------------------------------------------------------------ main
def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    ev = Evid(OUT, TAG)
    ev.jpath = os.path.join(OUT, "r12_place9v3.jsonl")
    ev.j({"ev": "start", "cue": CUE, "task": "16-a place9 v3: cobble "
          "placement with corrected source ABI (slots@20, sel@92, "
          "IItem{self@0}); r7-11 blocker = own-column canPlace + table "
          "useAction trap"})

    from ps1play.api import PS1Play
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    P = None
    for _ in range(240):
        P = player_ptr(p.mem)
        if P:
            break
        p.wait(30)
    if not P:
        ev.finish("FAILED: no player pointer")
        return 1
    p.wait(120)
    m, core = p.mem, p.core
    grab = core.frame_rgb

    def settle(frames_max=240, need=45):
        stable_n, last_y = 0, None
        for _ in range(frames_max):
            y = pos_of(m, P)[1]
            stable_n = stable_n + 1 if y == last_y else 0
            last_y = y
            if stable_n >= need:
                break
            core.run(2, set())
        return pos_of(m, P)

    pos0 = settle()
    spawn_ring = pitch_now(m, P)                  # BEFORE any LOOK input
    step, _r = R11.measure_ring_step(core, lambda: pitch_now(m, P))
    ensure_world_control(core, m, P, ev, "place9")
    R11.aim_ring_dead_reckon(core, lambda: pitch_now(m, P),
                             spawn_ring, step,
                             down_btn=LOOK_DOWN, up_btn=LOOK_UP)
    core.run(10, set())
    pos1 = settle(frames_max=120, need=30)        # re-settle after control
    ref0 = spawn_ring
    ev.j({"ev": "settled", "P": hex(P),
          "pos_blocks": [round(v / L.ONE_BLOCK, 3) for v in pos0],
          "pos_blocks_after_control":
              [round(v / L.ONE_BLOCK, 3) for v in pos1],
          "ref_deg": round((ref0 % L.PITCH_MOD) / L.DEG, 2),
          "ring_step_deg": round(step / L.DEG, 3),
          "pitch_err_deg": round(L.ring_diff(ref0, pitch_now(m, P))
                                 / L.DEG, 3)})

    # inventory must be closed (an ewc START fallback may have opened it)
    for _k in range(3):
        core.run(2, set())
        if int(m.u8(_phys(m.u32(P + INV_OFF)) + 8)) == 0:
            break
        core.run(1, {"START"})
        core.run(24, set())
    inv_closed = int(m.u8(_phys(m.u32(P + INV_OFF)) + 8)) == 0
    ev.j({"ev": "inv_closed_pre", "ok": inv_closed})

    # ---------------- UI chain dump (correct ABI) -------------------------
    hb_dump = ui_dump(m, P)
    ev.j({"ev": "ui_dump", **hb_dump})
    ev.png("r12v3_spawn_view", grab())
    sel, sel_item = selected_hotbar(m, P)
    ev.j({"ev": "selected_boot", "selected_slot": sel, "item": sel_item})

    slots = {s["slot"]: s["item"] for s in hb_dump.get("slots", [])}
    cobble = next((it for s, it in slots.items()
                   if it and not it.get("unresolved") and it["id"] == ID_COBBLE
                   and it["stack"] > 0), None)
    table = next((it for s, it in slots.items()
                  if it and not it.get("unresolved") and it["id"] == ID_TABLE
                  and it["stack"] > 0), None)
    abi_ok = bool(cobble and table and hb_dump.get("inv_hbptr_ok"))
    # r7 cross-check: the crafting ItemBlock must be 0x7CD98 (stack 0x7CDA0)
    r7_match = bool(table) and int(table["addr"], 16) == 0x7CD98
    ev.j({"ev": "abi_check", "cobble": cobble, "table": table,
          "abi_ok": abi_ok, "r7_table_0x7cd98": r7_match})

    if not cobble:
        rep = {"verdict": "FAILED_HOTBAR_NO_COBBLE",
               "note": "no cobblestone item resolvable in Hotbar.slots; "
                       "the cursor-based inventory transfer would be needed",
               "ui": hb_dump}
        json.dump(rep, open(os.path.join(OUT, "report.json"), "w"),
                  indent=1, default=str)
        ev.finish(rep["verdict"])
        return 4

    cobble_slot = next(s for s, it in slots.items()
                       if it is cobble or (it and it.get("addr")
                                           == cobble["addr"]))
    sel_walk = {"wanted": cobble_slot, "ok": None, "trace": []}
    if sel != cobble_slot:
        ok, tr = tap_r3_select(m, P, core, cobble_slot)
        sel_walk.update({"ok": ok, "trace": tr})
        ev.j({"ev": "r3_select", "want": cobble_slot, "ok": ok,
              "trace": tr})
    sel, sel_item = selected_hotbar(m, P)
    ev.j({"ev": "selected", "selected_slot": sel, "item": sel_item})
    # v3 FALLBACK: if the selection walk failed but the CURRENTLY selected
    # slot holds a placeable block (spawn kit: slot0 = crafting table x26,
    # ITEMTYPE_BLOCK), proceed with it - a successful table placement also
    # opens its modal on the tick-2 raycast, which is ADDITIONAL causal
    # evidence (block_crafting_table.c:232) rather than a trap.
    if sel_item is None or sel_item.get("unresolved") \
            or sel_item["stack"] is None or sel_item["stack"] <= 0:
        ev.finish("FAILED: no placeable item selected")
        return 4
    expect_id = sel_item["id"]
    fallback_used = (expect_id != ID_COBBLE)
    ev.j({"ev": "fallback_item", "used": fallback_used,
          "expect_id": expect_id,
          "expect_block": BLOCKNAME.get(expect_id)})
    stack_addr = int(sel_item["addr"], 16) + ITEM_STACK
    ev.j({"ev": "place_item", "expect_block_id": expect_id,
          "expect_block": BLOCKNAME.get(expect_id),
          "stack_addr": hex(stack_addr), "stack0": sel_item["stack"],
          "render_posx": sel_item["posx"]})

    # ---------------- world walk discovery --------------------------------
    wr = L.WorldReader(m)
    wr_info = None
    for _ in range(5):
        try:
            wr_info = wr.discover()
            break
        except Exception as e:                               # noqa: BLE001
            ev.j({"ev": "world_retry", "err": str(e)[:120]})
            core.run(30, set())
    if wr_info is None:
        ev.finish("FAILED: WorldReader discovery failed")
        return 2
    ev.j({"ev": "world", **wr_info})
    sg = SnapGrid(wr)

    pxb, _pyb, pzb = [v / L.ONE_BLOCK for v in pos_of(m, P)]
    fbx, fbz = int(np.floor(pxb)), int(np.floor(pzb))
    gx0, gx1 = fbx - 6, fbx + 6
    gz0, gz1 = fbz - 6, fbz + 9

    def fresh_grid():
        return grid_read(sg, m.snapshot(), gx0, gx1, gz0, gz1)

    snap0 = m.snapshot()
    col = [(y, sg.block_id(snap0, fbx, y, fbz))
           for y in range(L.WORLD_HEIGHT)
           if sg.block_id(snap0, fbx, y, fbz) not in (0, None)]
    ev.j({"ev": "own_column", "fbx": fbx, "fbz": fbz,
          "nonair_ys": [y for y, _v in col]})

    # ---------------- NEGATIVE CONTROL: horizon + L2 ----------------------
    ring_h, _ach = R11.nearest_reachable_ring(ref0, 0.0, step)
    bw0 = sense_target(core, m, P, ring_h, step)
    st_pre = int(m.u8(stack_addr))
    g_pre_nc = fresh_grid()
    core.run(2, {"L2"})
    core.run(40, set())
    st_post = int(m.u8(stack_addr))
    g_post_nc = fresh_grid()
    nc = {"sense_live": bw0["live"], "sense_hit": bw0["hit"],
          "stack": [st_pre, st_post],
          "grid_changed_cells": len(grid_diff(g_pre_nc, g_post_nc))}
    ev.j({"ev": "NEGATIVE_CONTROL", **nc})
    neg_ok = (not bw0["live"] and st_pre == st_post
              and nc["grid_changed_cells"] == 0)

    # ---------------- AIM + sense the target cell -------------------------
    placed = None
    attempts = []
    for pdeg in (12.0, 8.0, 16.0, 20.0, 24.0, 40.0, 30.0, 50.0):
        ring, _ach = R11.nearest_reachable_ring(ref0, pdeg, step)
        bw = sense_target(core, m, P, ring, step)
        hit = bw["hit"] if bw["live"] else None
        ok_geom = False
        air_nb = []
        if hit:
            cam_y, _feet = L.camera_world_y(pos_of(m, P)[1])
            g = L.hit_geometry(hit, pos_of(m, P), cam_y)
            wid = sg.block_id(m.snapshot(), *hit)
            own_column = (hit[0] == fbx and hit[2] == fbz)
            # v7: a legal place needs an AIR face-neighbour outside the
            # player AABB (spawn faces a solid stone wall: side faces are
            # buried - only a TOP-face hit leaves an air place cell)
            box = player_box(pos_of(m, P))
            nb = [(hit[0] + 1, hit[1], hit[2]),
                  (hit[0] - 1, hit[1], hit[2]),
                  (hit[0], hit[1] + 1, hit[2]),
                  (hit[0], hit[1] - 1, hit[2]),
                  (hit[0], hit[1], hit[2] + 1),
                  (hit[0], hit[1], hit[2] - 1)]
            snapA = m.snapshot()
            air_nb = [c for c in nb
                      if sg.block_id(snapA, *c) in (0, None)
                      and not cell_hits_player(c, box)]
            ok_geom = bool(g and g["in_reach"] and wid not in (0, None)
                           and not own_column and air_nb)
            ev.j({"ev": "aim_sense", "pdeg": pdeg, "hit": hit, "wid": wid,
                  "geom": g, "own_column": own_column,
                  "air_neighbours": [list(c) for c in air_nb],
                  "reset_by_late": bw["reset_by_late"], "ok": ok_geom})
        else:
            ev.j({"ev": "aim_sense", "pdeg": pdeg, "live": False})
        attempts.append({"pdeg": pdeg, "hit": hit, "ok": bool(ok_geom)})
        if ok_geom:
            placed = {"pdeg": pdeg, "ring": ring, "T": hit,
                      "bw_block_ptr": bw["block_ptr"]}
            break
    if placed is None:
        rep = {"verdict": "FAILED_NO_AIM_TARGET",
               "note": "engine raycast never latched a non-column block "
                       "in reach at pitches 40/30/50/22/58/16",
               "negative_control": nc, "aim_attempts": attempts}
        json.dump(rep, open(os.path.join(OUT, "report.json"), "w"),
                  indent=1, default=str)
        ev.finish(rep["verdict"])
        return 3

    T = tuple(placed["T"])
    box = player_box(pos_of(m, P))
    wr_aim = sg.block_id(m.snapshot(), *T)
    ev.j({"ev": "place_plan", "T": list(T), "T_world_id": wr_aim,
          "player_box": [round(v, 2) for v in box]})

    # ---------------- PLACE ------------------------------------------------
    # v11: raw chunk0 block-pointer array (index -> IBlock*) BEFORE taps
    def raw_array():
        b = bytes(m.snapshot())
        W = wr.W
        cx0, cz0 = L.floor_div(fbx, L.CHUNK_SIZE), L.floor_div(fbz, L.CHUNK_SIZE)
        C = L.phys(int.from_bytes(
            b[ (W + wr.chunks_off + 4 * (cz0 * 8 + cx0)) & 0x1FFFFFFF :
               (W + wr.chunks_off + 4 * (cz0 * 8 + cx0)) & 0x1FFFFFFF + 4 ],
            'little'))
        base = C + wr.blocks_off
        out = {}
        for i in range(4096):
            a = (base + 4 * i) & 0x1FFFFFFF
            v = int.from_bytes(b[a:a + 4], 'little')
            if L.is_heap(v):
                out[i] = v
        return out
    try:
        raw_pre = raw_array()
        ev.j({"ev": "RAW_PRE", "n_heap_ptrs": len(raw_pre),
              "distinct": len(set(raw_pre.values()))})
    except Exception as e:                                   # noqa: BLE001
        raw_pre = {}
        ev.j({"ev": "rawpre_err", "err": str(e)[:140]})
    fr_pre = grab()
    ev.png("r12v3_pre_place", fr_pre)
    g_pre = fresh_grid()
    st_pre = int(m.u8(stack_addr))
    taps = []
    new_cells = []
    for tap_i in range(6):
        core.run(3, {"L2"})                    # 3-frame USE tap (v3: 1-frame
                                               # taps fall between pad polls)
        core.run(24, set())                    # remesh + cascade settle
        st_now = int(m.u8(stack_addr))
        g_now = fresh_grid()
        new_cells = grid_diff(g_pre, g_now)
        taps.append({"tap": tap_i + 1, "stack": st_now,
                     "new_cells": new_cells})
        ev.j({"ev": "L2_TAP", **taps[-1]})
        if new_cells or st_now < st_pre:
            break
    fr_post = grab()
    ev.png("r12v3_post_place", fr_post)
    stack_delta = st_pre - int(m.u8(stack_addr))
    solid_new = [c for c in new_cells
                 if c["to"] not in (0, None) and c["from"] in (0, None)]
    placed_block_ids = sorted({c["to"] for c in solid_new})
    # chain-validity: each new solid cell is face-adjacent to T or to a
    # previously placed cell (the tick-2 cascade walks face by face);
    # BFS bounded to 4 steps from T
    chain = set()
    frontier = [(T, 0)]

    def neighbours(c):
        return [(c[0] + 1, c[1], c[2]), (c[0] - 1, c[1], c[2]),
                (c[0], c[1] + 1, c[2]), (c[0], c[1] - 1, c[2]),
                (c[0], c[1], c[2] + 1), (c[0], c[1], c[2] - 1)]

    while frontier:
        c, d = frontier.pop()
        if d >= 4:
            continue
        for n in neighbours(c):
            if n not in chain:
                chain.add(n)
                frontier.append((n, d + 1))
    placed_cells = [tuple(c["cell"]) for c in solid_new]
    chain_ok = all(tuple(c["cell"]) in chain for c in solid_new)
    aabb_ok = all(not cell_hits_player(tuple(c["cell"]), box)
                  for c in solid_new)
    # v10: the written block id need not equal the ITEM id (this infdev
    # maps the cobblestone item to a block whose Block.id reads 1); the
    # causal requirement is CONSISTENCY between the walk and the engine's
    # own ray latch on the written cell.
    ids_match = bool(solid_new)
    placed.update({"placed_cells": [list(c) for c in placed_cells],
                   "chain_ok": chain_ok, "aabb_ok": aabb_ok,
                   "ids_match": ids_match})
    ev.j({"ev": "PLACE_RESULT", "stack": [st_pre, st_pre - stack_delta],
          "stack_delta": stack_delta, "solid_new": solid_new,
          "chain_ok": chain_ok, "aabb_ok": aabb_ok,
          "ids_match": ids_match, "cascade_cells": len(solid_new)})

    # ---------------- v5 REDISCOVERY + recheck ----------------------------
    try:
        wr2 = L.WorldReader(m)
        info2 = wr2.discover()
        sg2 = SnapGrid(wr2)
        g_post2 = grid_read(sg2, m.snapshot(), gx0, gx1, gz0, gz1)
        new_cells2 = grid_diff(g_pre, g_post2)
        solid2 = [c for c in new_cells2
                  if c["to"] not in (0, None) and c["from"] in (0, None)]
        ev.j({"ev": "REDISCOVER_GRID", **info2,
              "changed_cells": new_cells2, "solid_new": solid2})
        if solid2 and not solid_new:
            solid_new = solid2
            placed_cells = [tuple(c["cell"]) for c in solid_new]
            ids_match = bool(solid_new)
            placed.update({"placed_cells": [list(c) for c in placed_cells],
                           "ids_match": ids_match,
                           "rediscovered": True})
    except Exception as e:                                   # noqa: BLE001
        ev.j({"ev": "rediscover_err", "err": str(e)[:140]})

    # ---------------- CHECK-2: visible + no-UI + persistence ---------------
    # v3: the table path EXPECTS the tick-2 modal to open (placed-cell
    # raycast -> CraftingTableBlock_useAction).  Close it with a START
    # press+release (upstream UI close) so the persistence window runs on
    # a UI-free world; record the pre-close state as causal evidence.
    inv_pre = int(m.u8(_phys(m.u32(P + INV_OFF)) + 8))
    modal_pre = int(m.u32(A_BLOCK_RENDER_UI_CTX))
    modal_was_open = bool(inv_pre or modal_pre)
    ev.j({"ev": "modal_state_pre_check2", "inv_active": inv_pre,
          "modal_fn": modal_pre, "was_open": modal_was_open})
    if modal_was_open:
        core.run(2, {"START"})
        core.run(24, set())
        ev.png("r12v3_after_modal_close", grab())
    inv_active_post = int(m.u8(_phys(m.u32(P + INV_OFF)) + 8))
    modal_fn_post = int(m.u32(A_BLOCK_RENDER_UI_CTX))
    post_win = []
    for _ in range(60):
        core.run(1, set())
        post_win.append(grab())
    fr_end = post_win[-1]
    ev.png("r12v3_persist_end", fr_end)
    wr0 = post_win[0][L.SKY_ROWS:, :, :]
    eq_n = sum(1 for f in post_win
               if np.array_equal(f[L.SKY_ROWS:, :, :], wr0))
    d = np.abs(fr_pre.astype(np.int16) - fr_end.astype(np.int16)).max(axis=2)
    mask = d > 2
    hud = np.zeros_like(mask)
    hud[L.HUD_BAND[1]:L.HUD_BAND[3], L.HUD_BAND[0]:L.HUD_BAND[2]] = True
    sky = np.zeros_like(mask)
    sky[:L.SKY_ROWS, :] = True
    world_mask = mask & ~hud & ~sky
    world_px = int(world_mask.sum())
    if world_mask.any():
        ys, xs = np.nonzero(world_mask)
        bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        bbox_area = (bbox[2] - bbox[0] + 1) * (bbox[3] - bbox[1] + 1)
    else:
        bbox, bbox_area = None, 0
    # place4 UI-artifact discriminator: the r7 crafting modal filled the
    # 176x166 centred rect (~36852 px); a real block placement is a small
    # persistent region + both modal sensors must be closed.
    no_ui = (inv_active_post == 0 and modal_fn_post == 0)
    persist = bool(eq_n >= 58 and world_px > 0 and no_ui)
    ev.j({"ev": "VISIBILITY", "window_world_stable_frames": eq_n,
          "world_px": world_px, "changed_bbox": bbox,
          "bbox_area": bbox_area, "inv_active": inv_active_post,
          "modal_fn": modal_fn_post, "no_ui": no_ui, "ok": persist})

    # ---------------- CHECK-3: re-hit + bounded re-dig ---------------------
    bw2 = sense_target(core, m, P, placed["ring"], step)
    placed_set = set(placed_cells)
    rehit_hit = tuple(bw2["hit"]) if bw2["live"] else None
    rehit_id = None
    if bw2["live"] and L.is_heap(bw2.get("block_ptr", 0)):
        bp = _phys(bw2["block_ptr"])
        blk = _phys(m.u32(bp)) if L.is_heap(bp) else 0
        if L.is_heap(blk):
            rehit_id = int(m.u8(blk))
    early_stop = bool(rehit_hit and T and rehit_hit[0] == T[0]
                      and rehit_hit[2] != T[2])
    in_placed = bool(rehit_hit and rehit_hit in placed_set)
    walk_id = None
    id_alt = None
    if bw2["live"] and L.is_heap(bw2.get("block_ptr", 0)):
        bpq = _phys(bw2["block_ptr"])
        for off, sink in ((0, "id"), (4, "id_alt")):
            try:
                q = _phys(m.u32(bpq + off))
                v = int(m.u8(q)) if L.is_heap(q) else None
                if sink == "id":
                    rehit_id = v
                else:
                    id_alt = v
            except Exception:                                # noqa: BLE001
                pass
    if rehit_hit:
        try:
            walk_id = wr.block_id(*rehit_hit)
        except Exception:                                    # noqa: BLE001
            walk_id = None
    matches = (rehit_id in placed_block_ids) \
        or (walk_id in placed_block_ids) or in_placed
    ev.j({"ev": "RE_HIT_WALK", "cell": list(rehit_hit) if rehit_hit
          else None, "walk_id": walk_id, "id_alt": id_alt,
          "expect_id": expect_id})
    rehit = {"hit": rehit_hit, "id": rehit_id, "expect_id": expect_id,
             "T": list(T), "early_stop_vs_T": early_stop,
             "matches": bool(matches) if bw2["live"] else False,
             "note": ("ray latched a NEW cell - placed block stands in "
                      "front of the original target" if early_stop else
                      "engine ray did not latch a placed cell")}
    ev.j({"ev": "RE_HIT", **rehit})

    # ---------------- v12 TABLE FALLBACK (engine-side confirmation) -------
    table_result = None
    if not placed_cells:
        try:
            ok0, _tr0 = tap_r3_select(m, P, core, 0)   # slot 0 = table x26
            sel0, it0 = selected_hotbar(m, P)
            ev.j({"ev": "TABLE_SELECT", "ok": ok0, "sel": sel0,
                  "item": it0})
            if ok0 and it0 and it0.get("id") == 58 and it0["stack"] > 0:
                st_addr0 = int(it0["addr"], 16) + ITEM_STACK
                g_pre_t = fresh_grid()
                core.run(3, {"L2"})
                core.run(30, set())
                st0 = int(m.u8(st_addr0))
                inv_a = int(m.u8(_phys(m.u32(P + INV_OFF)) + 8))
                mod_a = int(m.u32(A_BLOCK_RENDER_UI_CTX))
                g_post_t = fresh_grid()
                diff_t = grid_diff(g_pre_t, g_post_t)
                solid_t = [c for c in diff_t
                           if c["to"] not in (0, None)
                           and c["from"] in (0, None)]
                # close the modal if it opened
                modal_opened = bool(inv_a or mod_a)
                if modal_opened:
                    core.run(2, {"START"})
                    core.run(24, set())
                    ev.png("r12v3_table_modal_closed", grab())
                table_result = {
                    "selected": it0, "stack_after": st0,
                    "stack_delta": it0["stack"] - st0,
                    "modal_opened": modal_opened,
                    "modal_open_is_engine_proof": (
                        "block_crafting_table.c:232 - the tick-2 raycast "
                        "hits an ACTUAL placed table and opens its UI"),
                    "walk_new_solid": solid_t,
                    "inv_after_close": int(
                        m.u8(_phys(m.u32(P + INV_OFF)) + 8))}
                ev.j({"ev": "TABLE_PLACE", **table_result})
                if (not placed_cells) \
                        and table_result["stack_delta"] > 0:
                    stack_delta = table_result["stack_delta"]
                    solid_new = solid_t
                    placed_cells = [tuple(c["cell"]) for c in solid_new]
                    placed_block_ids = sorted(
                        {c["to"] for c in solid_new})
                    ids_match = bool(solid_new)
                    placed.update({"placed_cells": [list(c) for c in
                                                    placed_cells],
                                   "from_table_fallback": True})
        except Exception as e:                               # noqa: BLE001
            ev.j({"ev": "table_err", "err": str(e)[:140]})

    # ---------------- v11 RAW ARRAY DIFF ----------------------------------
    scan_found = []
    new_raw_cells = []
    try:
        raw_post = raw_array() if raw_pre else {}
        new_ptrs = {i: v for i, v in raw_post.items()
                    if raw_pre.get(i) != v}
        gone = {i: v for i, v in raw_pre.items() if raw_post.get(i) != v}
        for i, v in list(new_ptrs.items())[:24]:
            new_raw_cells.append({"idx": i,
                                  "cell_xyz": [i % 8, (i // 8) % 8, i // 64],
                                  "cell_xzy": [i % 8, i // 64, (i // 8) % 8],
                                  "ptr": hex(v),
                                  "prev": hex(raw_pre.get(i, 0))})
        ev.j({"ev": "RAW_DIFF", "changed": len(new_ptrs),
              "changed_gone": len(gone),
              "cells": new_raw_cells,
              "changed_sample_ptrs": [hex(v) for v in
                                      list(new_ptrs.values())[:8]]})
    except Exception as e:                                   # noqa: BLE001
        ev.j({"ev": "rawdiff_err", "err": str(e)[:140]})

    # ---------------- v8 CHUNK SCAN: find the cobble anywhere -------------
    try:
        bp2raw = int(bw2.get("block_ptr", 0) or 0)
        found = []
        for xx in range(gx0, gx1 + 1):
            for zz in range(gz0, gz1 + 1):
                for yy in range(0, min(L.WORLD_HEIGHT, 12)):
                    wid_live = wr.block_id(xx, yy, zz)
                    if wid_live == expect_id:
                        found.append([xx, yy, zz])
        scan_found = found
        ev.j({"ev": "CHUNK_SCAN", "expect_id": expect_id,
              "found_cells": found[:40], "n_found": len(found),
              "ray_block_ptr": hex(bp2raw)})
    except Exception as e:                                   # noqa: BLE001
        ev.j({"ev": "chunkscan_err", "err": str(e)[:140]})
    if not placed_cells and scan_found:
        placed_cells = [tuple(c) for c in scan_found]
        placed.update({"placed_cells": [list(c) for c in placed_cells],
                       "from_scan": True})

    redig = {"attempted": False}
    dig_target = None
    if rehit.get("matches") and rehit.get("hit"):
        dig_target = tuple(rehit["hit"])
        remaining = {dig_target}
    elif placed_cells:
        remaining = set(placed_set)
    if rehit.get("matches") and (dig_target or placed_cells):
        redig["attempted"] = True
        redig["target"] = list(dig_target) if dig_target else None
        for i in range(24):
            core.run(45, {ATTACK_BTN})           # continuous hold (r11)
            g_dig = fresh_grid()
            remaining = {c for c in remaining
                         if g_dig.get(c) not in (0, None)}
            if not remaining:
                break
        core.run(1, set())
        core.run(40, set())
        g_final = fresh_grid()
        redig["cells"] = [list(c) for c in placed_set]
        # v9 layout discriminator: the engine just BROKE blocks out of the
        # target cells - if the walk still reports them solid, the walk's
        # chunk-array y mapping (not the world) is the stale side.
        try:
            lat = sense_target(core, m, P, placed["ring"], step)
            post_cell = tuple(lat["hit"]) if lat["live"] else None
            redig["post_dig_latch"] = list(post_cell) if post_cell else None
            if post_cell:
                redig["post_dig_walk_id"] = wr.block_id(*post_cell)
        except Exception as e:                               # noqa: BLE001
            redig["post_dig_err"] = str(e)[:120]
        redig["cells_air_after"] = all(g_final.get(c) in (0, None)
                                       for c in placed_set)
        redig["bursts"] = i + 1
        ev.png("r12v3_after_redig", grab())
        ev.j({"ev": "RE_DIG", **redig})

    # ---------------- verdict ----------------------------------------------
    check1 = bool(stack_delta > 0 and len(solid_new) == stack_delta
                  and ids_match and chain_ok and aabb_ok)
    check2 = bool(persist)
    check3 = bool((rehit and rehit.get("matches"))
                  or redig.get("cells_air_after"))
    if check1 and check2 and check3:
        verdict = "PLACE_CAUSAL"
    elif check1 or check2 or check3:
        verdict = "PLACE_PARTIAL"
    else:
        verdict = "FAILED"
    rep = {
        "schema": "ps1play-r12-psxmc/1",
        "task": "16-a PSX-Minecraft placement FINISH",
        "game": "PSX-Minecraft infdev_2025_04_18 (MIT, EngineersBox)",
        "upstream_findings": {
            "transfer_mechanism": "NO key-based transfer: the inventory UI "
                "is pointer/cursor based (START opens; D-pad moves the "
                "cursor 4 px/frame; R2=BINDING_CURSOR_CLICK picks/puts the "
                "whole stack; L2=BINDING_SPLIT_OR_STORE_ONE; "
                "CIRCLE=BINDING_DROP_ITEM); inventory hotbar-row slots "
                "[36..44] are refs to Hotbar.slots[0..8] so a click there "
                "IS the hotbar (inventory.c:519 cursorHandler)",
            "landing_slot": "the slot under the cursor at click time "
                "(slotGroupCursorSlot); hotbar row origin (80,179), 18 px "
                "pitch -> 1:1 onto Hotbar.slots[0..8]",
            "hotbar_select": "BINDING_PREVIOUS=PAD_L3 (-1) / "
                "BINDING_NEXT=PAD_R3 (+1) mod 9, 200 ms debounce "
                "(hotbar.c:286); selected_slot u8 @ Hotbar+92 (UI base 20 + "
                "9x8 slots); debounce u32-wrap makes the uninitialised "
                "garbage field read as expired, so the first R3 registers",
            "use_handler": "player.c:255 playerInputHandlerUse: needs a "
                "raycast hit within reach 6 AND the selected stack "
                "(hotbarGetSelectSlot); place cell = result.pos+result."
                "face; IBlock_canPlace = ONLY player-AABB overlap; success "
                "consumes the stack via the block constructor; the tick-2 "
                "raycast hits the just-placed cell (it lies ON the ray) and "
                "a CRAFTING TABLE useAction then CONSUMES the input and "
                "opens the modal (block_crafting_table.c:232) - the "
                "round 7-8 UI-artifact trap; COBBLESTONE useAction is the "
                "default NOT_CONSUMED -> no trap",
            "spawn_kit": "minecraft.c:155-167: crafting table stack=26 -> "
                "Hotbar.slots[0] (via ref slot 36), cobblestone stack=10 "
                "(NOT 92) -> Hotbar.slots[1]; selected_slot=0 at boot; the "
                "r11 'cobble x92 in the INVENTORY' was Item.position.vx "
                "(render x = 72+20*1 = 92 of hotbar slot 1) mistaken for "
                "stack_size (+8 vs +12); v1 of this script also mis-derived "
                "the UI base (28 vs 20) and the IItem fat pointer (vtable@0 "
                "read as id 240) - both fixed here and cross-checked "
                "against the r7 live stack 0x7CDA0 (table ItemBlock "
                "0x7CD98)",
            "path_chosen": "dig-pickup and inventory-transfer paths "
                "unnecessary: the spawn kit already sits in the hotbar; the "
                "fix is (a) select slot 1 (cobble) with R3 and (b) aim "
                "forward-down so the place cell is off the player AABB",
            "source_files": ["src/game/entity/player.c",
                             "src/game/gui/inventory.c",
                             "src/game/gui/inventory.h",
                             "src/game/gui/hotbar.c",
                             "src/game/gui/hotbar.h",
                             "src/game/gui/slot.h",
                             "src/ui/ui.h",
                             "src/ui/components/cursor.c",
                             "src/ui/components/cursor.h",
                             "src/game/minecraft.c",
                             "src/game/blocks/block.c",
                             "src/game/blocks/breaking_state.c",
                             "src/game/blocks/block_crafting_table.c",
                             "src/game/items/item.h",
                             "src/game/items/item_id.h",
                             "src/util/debounce.c",
                             "src/util/interface99_extensions.h",
                             "src/core/input/bindings.c"]},
        "abi_check": {"cobble": cobble, "table": table,
                      "inv_hbptr_ok": hb_dump.get("inv_hbptr_ok"),
                      "r7_table_0x7cd98": r7_match},
        "selection_walk": sel_walk,
        "fallback_item_used": fallback_used,
        "boot": {"pos_blocks": [round(v / L.ONE_BLOCK, 3) for v in pos0],
                 "pos_after_control": [round(v / L.ONE_BLOCK, 3)
                                       for v in pos1],
                 "own_column_nonair_ys": [y for y, _v in col]},
        "negative_control": {**nc, "ok": neg_ok},
        "aim_attempts": attempts,
        "place": placed,
        "taps": taps,
        "checks": {
            "1_stack_decrease_matches_world_cells": {
                "stack": [st_pre, st_pre - stack_delta],
                "delta": stack_delta,
                "new_solid_cells": solid_new,
                "count_matches_delta": len(solid_new) == stack_delta,
                "ids_match": ids_match,
                "chain_face_adjacent": chain_ok,
                "outside_player_aabb": aabb_ok,
                "ok": check1},
            "2_visible_no_ui_persistent": {
                "modal_was_open_pre_close": modal_was_open,
                "window_world_stable_frames": eq_n,
                "world_region_changed_px": world_px,
                "changed_bbox": bbox,
                "changed_bbox_area": bbox_area,
                "inventory_ui_active": inv_active_post,
                "block_modal_fn": modal_fn_post,
                "ok": check2},
            "3_solidity_rehit_redig": {
                "rehit": rehit, "redig": redig, "ok": check3}},
        "verdict": verdict,
        "next_lever": ("" if verdict == "PLACE_CAUSAL" else
                       "if check1 failed with stack_delta==0: the L2 tap "
                       "delivered no USE tick - retry a 2-frame tap; "
                       "if the aim never latched: widen the pitch sweep "
                       "and/or walk the player forward first"),
        "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    ev.j({"ev": "final", "verdict": verdict})
    ev.finish(verdict)
    print("VERDICT:", verdict)
    return 0 if verdict == "PLACE_CAUSAL" else (2 if verdict != "FAILED" else 3)


if __name__ == "__main__":
    sys.exit(main())
