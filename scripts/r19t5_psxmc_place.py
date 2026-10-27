#!/usr/bin/env python3
"""r19t5_psxmc_place.py — Round 19 train T5: PSX-Minecraft VISIBLE placement.

The one remaining honest gap from r7-r12: USE (L2) consumption is CAUSAL
(chain 26->25->24->23 @0x7CDA0, r7; clean cobble negative control, r12) but
zero VISIBLE world placements were ever captured (world_px 0 every attempt;
r7 attempt-3 raycast HIT a placed table => the world WAS modified, out of
frame; r12 could not localize the write in the walked grid either).

r19 hypothesis v2 (run-2 ground truth): the player spawns ON a 3-4 block
spawn platform whose cells are at y7 (feet 8.0, cam_y 9.7) and WORLD_HEIGHT
is 8 (cells y0..y7) => every in-reach ray from the platform hits a y7
cell and the place cell C = hit + topface = y8 is OUT OF WORLD: the game
EATS the stack (10->9->8->7 measured) but nothing is placed (rehit latches
the SAME T with the same id; world_px 0) - this ALSO explains r12's
"stack consumed, world write NOT localized" mystery.  Fix: WALK OFF the
platform onto the flatland ground (feet ~5.0) so rays hit y4/y5 cells and
C=(x,5,z) / C=(x,6,z) (bump top) are IN WORLD, close and un-occluded.

Method (all legal input, one beetle boot, <=6 min wall):
  0. boot -> player ptr -> settle -> TRUE look-rate measurement (r11
     measure_ring_step has a 1-deg floor bug vs the real 0.44 deg/f rate
     => its 15-deg fallback stalled run-1 aims at the horizon) -> world
     control -> re-settle.
  1. UI chain dump (r12 source ABI); R3-walk to COBBLESTONE slot1 (stack
     10); cross-check table slot0 stack 26 @0x7CD98 (r7 live 0x7CDA0).
  2. NEGATIVE CONTROL: horizon aim, 3-frame L2 tap => stack unchanged.
  3. WALK OFF the platform (D-pad probe: UP/DOWN/LEFT/RIGHT x 15f bursts
     until feet < 7.5) + settle.
  4. Per attempt: aim (dead-reckon, measured rates) => R2 breaking-window
     SENSE (snapshot WHILE HOLDING) => hit T; gate: live, in_reach<=6,
     not own column, T.y < cam_y, T.y <= 6 (C in world), frame stability
     gate (3 bit-exact grabs) + terrain gate (center_std>=8).  pre PNG.
     3-frame L2 tap + 24f settle with 2-frame burst grabs; post PNG;
     band diff + framed-region px + LEFT-EDGE control band (view-jitter
     guard); 60f persistence; UI guard (inv.active, modal fns - the
     hotbar HUD is ALWAYS active=1, excluded).  UI-open => START close.
  5. Stack-drop-but-invisible fallback: re-sense the same ring (a placed
     cell lies ON the ray => the latch must stop EARLIER); dig-revert A/B.
  6. 3 attempts (fresh yaw azimuth each); savestates at ready + built.
Verdict ladder: CONFIRMED(visible place xN) / INCONCLUSIVE(precise reason).
Evidence: scratch/r19t5_psxmc/ (+GIF uploaded to uguu.se).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from psxmc_r7_lib import (  # noqa: E402
    A_INPUT, Evid, PADBUFF_SIG, changed_px, madiff, sha, words_changed)
import psxmc_r10_lib as L  # noqa: E402
import psxmc_r11_lib as R11  # noqa: E402
from psxmc_r10_oracle import (  # noqa: E402
    CUE, ensure_world_control, player_ptr, pitch_now, pos_of, yaw_now)

WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r19t5"
OUT = os.path.join(REPO, "scratch", "r19t5_psxmc")
TAG = "r19t5"

# ---- input (bindings.c @ infdev_2025_04_18) --------------------------------
LOOK_DOWN, LOOK_UP = "B", "X"        # CROSS / TRIANGLE (pitch ring)
LOOK_YAWP, LOOK_YAWM = "SQ", "O"     # SQUARE yaw+ / CIRCLE yaw- (r10 oracle)
PLACE_BTN = "L2"                     # BINDING_USE
ATTACK_BTN = "R2"                    # BINDING_ATTACK (sense + dig)
SEL_NEXT = "R3"                      # BINDING_NEXT (hotbar +1)
UI_BTN = "START"

# ---- source-derived ABI (psxmc_r12_place9v3) -------------------------------
HB_OFF, INV_OFF = 0x64, 0x5C
UI_SIZE = 20
SEL_OFF = 92
ITEM_ID, ITEM_STACK, ITEM_IN_WORLD, ITEM_POSX = 0, 8, 11, 12
A_BLOCK_RENDER_UI_CTX = 0x3C790
A_BLOCK_INPUT_CTX = 0x3C5A4
ID_COBBLE, ID_TABLE = 4, 58

# ---- visibility bands (frame is 320x240) -----------------------------------
FRAME_BOX = (80, 80, 240, 204)       # x0,y0,x1,y1: crosshair-framed ground
CENTER_BOX = (110, 90, 210, 170)     # terrain-gate window around crosshair

T_BUDGET = 330.0                     # wall seconds; hard lab cap 360


def phys(v):
    return L.phys(int(v) & 0xFFFFFFFF)


def snap(m):
    return bytes(m.snapshot())


def _phys(v):
    return phys(v)


# ---------------------------------------------------------------- UI chain
def resolve_item_block(m, iitem):
    for doff in (0, 4):
        a = phys(m.u32(phys(iitem) + doff))
        if L.is_heap(a):
            return a, doff
    return None, None


def read_item(m, iitem):
    if not L.is_heap(iitem):
        return None
    blk, doff = resolve_item_block(m, iitem)
    if blk is None:
        return {"addr": hex(phys(iitem)), "unresolved": True}
    return {"iitem": hex(phys(iitem)), "self_doff": doff, "addr": hex(blk),
            "id": int(m.u8(blk + ITEM_ID)),
            "stack": int(m.u8(blk + ITEM_STACK)),
            "in_world": int(m.u8(blk + ITEM_IN_WORLD)),
            "posx": L.s32(m.u32(blk + ITEM_POSX))}


def hotbar_base(m, P):
    return phys(m.u32(P + HB_OFF))


def ui_sensors(m, P):
    """(inv_active, hb_active, modal_fn, modal_block) — the place4 guards."""
    inv = int(m.u8(phys(m.u32(P + INV_OFF)) + 8))
    hb = int(m.u8(phys(m.u32(P + HB_OFF)) + 8))
    mf = int(m.u32(A_BLOCK_RENDER_UI_CTX))
    mb = int(m.u32(A_BLOCK_INPUT_CTX + 4))
    return inv, hb, mf, mb


def selected_hotbar(m, P):
    H = hotbar_base(m, P)
    sel = int(m.u8(H + SEL_OFF))
    it = phys(m.u32(H + UI_SIZE + 8 * sel))
    return sel, read_item(m, it)


def hotbar_slots(m, P):
    H = hotbar_base(m, P)
    return {s: read_item(m, phys(m.u32(H + UI_SIZE + 8 * s)))
            for s in range(9)}


def tap_r3_select(m, P, core, want_slot, max_taps=8):
    trace = []
    for btn in ("R3", "L3"):
        for _k in range(max_taps):
            if int(selected_hotbar(m, P)[0]) == want_slot:
                return True, trace
            core.run(3, {btn})
            core.run(18, set())
            trace.append({"btn": btn, "sel": int(selected_hotbar(m, P)[0])})
    return int(selected_hotbar(m, P)[0]) == want_slot, trace


# ------------------------------------------------------------- aim helpers
def measure_look_rate(core, m, P, frames=12):
    """TRUE per-frame pitch rates.  NOTE r11 measure_ring_step has a
    threshold bug for this game: its 'no response' floor is 1.0 DEG/frame
    while the real rate is 18432 raw/f = 0.3955 deg/f (r7 measurement,
    90 deg ~= 228 f) => it silently substituted a false 15 deg/f step and
    every 'dead-reckon' aim stalled near the horizon (r19t5 run 1:
    pitch_step_deg logged 15.0, all senses dead).  Measured-rate math only
    here; down/up measured separately (place3 noted asymmetric rates)."""
    r0 = pitch_now(m, P)
    core.run(frames, {LOOK_DOWN})
    r1 = pitch_now(m, P)
    down = abs(L.ring_diff(r0, r1)) // frames
    r2 = pitch_now(m, P)
    core.run(frames, {LOOK_UP})
    r3 = pitch_now(m, P)
    up = abs(L.ring_diff(r2, r3)) // frames
    if down <= 0:
        down = 18432                     # r7 live measurement fallback
    if up <= 0:
        up = down
    return down, up


def aim_to_ring(core, m, P, target_ring, rate_down, rate_up, tag=""):
    """Dead-reckon with per-direction measured rates + one correction pass."""
    cur = pitch_now(m, P)
    d = L.ring_diff(cur, target_ring)
    n = int(round(abs(d) / (rate_down if d > 0 else rate_up)))
    if n:
        core.run(min(n, 400), {LOOK_DOWN if d > 0 else LOOK_UP})
    err = L.ring_diff(pitch_now(m, P), target_ring)
    n2 = 0
    if abs(err) > abs(rate_down) // 2:
        n2 = int(round(abs(err) / (rate_down if err > 0 else rate_up)))
        if n2:
            core.run(min(n2, 400), {LOOK_DOWN if err > 0 else LOOK_UP})
        err = L.ring_diff(pitch_now(m, P), target_ring)
    return {"err_deg": round(err / L.DEG, 3), "frames": abs(n) + abs(n2),
            "rate_down_deg": round(rate_down / L.DEG, 4),
            "rate_up_deg": round(rate_up / L.DEG, 4), "tag": tag}


def measure_yaw_step(core, m, P, frames=6):
    y0 = yaw_now(m, P)
    core.run(frames, {LOOK_YAWP})
    y1 = yaw_now(m, P)
    step = abs(L.ring_diff(y0, y1)) // frames
    if step <= 0:
        step = 61440
    return step, y1


def yaw_dead_reckon(core, m, P, target_yaw, step, btn="SQ"):
    cur = yaw_now(m, P)
    d = L.ring_diff(cur, target_yaw)
    n = int(round(abs(d) / step))
    if n:
        core.run(min(n, 400), {btn if d > 0 else LOOK_YAWM})
    err = L.ring_diff(yaw_now(m, P), target_yaw)
    return {"err_deg": round(err / L.DEG, 2), "frames": n}


# ------------------------------------------------------------------ sensing
def sense_hit(core, m, P):
    """R2 breaking-window raycast read (FIX-2: snapshot WHILE HOLDING)."""
    core.run(3, {ATTACK_BTN})
    mid = snap(m)
    core.run(5, {ATTACK_BTN})
    core.run(1, set())
    core.run(20, set())
    late = snap(m)
    bw = R11.breaking_current(None, P, snap=mid)
    bwl = R11.breaking_current(None, P, snap=late)
    bw["reset_by_late"] = (bwl["hit"] == [0, 0, 0] and bwl["block_ptr"] == 0)
    return bw


# ------------------------------------------------------------- frame metrics
def region_px(f_a, f_b, box):
    x0, y0, x1, y1 = box
    d = np.any(f_a[y0:y1, x0:x1].astype(np.int16)
               != f_b[y0:y1, x0:x1].astype(np.int16), axis=2)
    return int(d.sum())


def center_stats(f):
    x0, y0, x1, y1 = CENTER_BOX
    c = f[y0:y1, x0:x1].astype(np.int16)
    return {"center_std": round(float(c.std()), 1),
            "center_mean": round(float(c.mean()), 1),
            "std": round(float(f.astype(np.int16).std()), 1)}


def world_diff(f_a, f_b):
    """Band-split changed-pixel metrics (cloud drift lives in the sky band)."""
    n, bb = changed_px(f_a, f_b)
    out = {"changed_px": n, "bbox": bb}
    if not bb:
        out.update({"sky_px": 0, "ground_px": 0, "hud_px": 0,
                    "world_px": 0, "framed_px": 0})
        return out
    x0, y0, x1, y1 = bb
    h, w = f_a.shape[:2]
    hud = np.zeros((h, w), bool)
    hud[L.HUD_BAND[1]:L.HUD_BAND[3], L.HUD_BAND[0]:L.HUD_BAND[2]] = True
    sky = np.zeros((h, w), bool)
    sky[:min(L.SKY_ROWS, h), :] = True
    d = np.any(f_a.astype(np.int16) != f_b.astype(np.int16), axis=2)
    world = d & ~hud
    out["sky_px"] = int((world & sky).sum())
    out["ground_px"] = int((world & ~sky).sum())
    out["hud_px"] = int((d & hud).sum())
    out["world_px"] = int(world.sum())
    out["framed_px"] = region_px(f_a, f_b, FRAME_BOX)
    return out


def is_bump_top(T):
    return bool(T) and T[1] == 5


WALK_BTNS = ("UP", "DOWN", "LEFT", "RIGHT")


def walk_off_platform(core, m, P, ev, feet_ok=7.5, max_bursts=14):
    """Probe D-pad buttons in 15-frame bursts until the player leaves the
    y7 spawn platform (feet drop below feet_ok blocks) or every direction
    is exhausted.  The platform sits 3+ blocks above the flatland ground:
    from it, every in-reach ray hits y7 cells whose place cell y8 is OUT
    OF WORLD (stack eaten, nothing placed - run-2 ground truth)."""
    rec = {"moved_btn": None, "bursts": 0, "feet": None}
    feet0 = L.s32(pos_of(m, P)[1]) / L.ONE_BLOCK - L.Y_OFFSET_B
    if feet0 < feet_ok:
        rec.update({"feet": feet0, "note": "already low"})
        return rec
    for btn in WALK_BTNS:
        x0, y0, z0 = pos_of(m, P)
        core.run(15, {btn})
        x1, y1, z1 = pos_of(m, P)
        moved = max(abs(x1 - x0), abs(z1 - z0)) > 0.1 * L.ONE_BLOCK
        if not moved:
            core.run(8, set())
            continue
        rec["moved_btn"] = btn
        for i in range(max_bursts):
            core.run(15, {btn})
            core.run(4, set())
            rec["bursts"] = i + 1
            feet = L.s32(pos_of(m, P)[1]) / L.ONE_BLOCK - L.Y_OFFSET_B
            if feet < feet_ok:
                break
        core.run(30, set())          # let the fall + physics settle
        feet = L.s32(pos_of(m, P)[1]) / L.ONE_BLOCK - L.Y_OFFSET_B
        rec["feet"] = round(feet, 3)
        ev.j({"ev": "walk_off", **rec})
        return rec
    rec["feet"] = round(feet0, 3)
    ev.j({"ev": "walk_off", **rec, "note": "no direction moved"})
    return rec


def stable_frame(core, grab, n=3, max_wait=240):
    """Wait until n consecutive grabs are bit-exact (view settled), then
    return the last grab.  Kills the 1-frame view-lag jitter that produced
    run-2 attempt-3's full-frame texel diff."""
    last = grab()
    streak, waited = 1, 0
    while waited < max_wait:
        if streak >= n:
            return last, waited
        core.run(2, set())
        waited += 2
        f = grab()
        streak = streak + 1 if np.array_equal(last, f) else 1
        last = f
    return last, waited


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    ev = Evid(OUT, TAG)
    ev.jpath = os.path.join(OUT, "r19t5_psxmc.jsonl")
    ev.j({"ev": "start", "cue": CUE, "workspace": WS,
          "task": "r19-t5 VISIBLE placement"})

    from ps1play.api import PS1Play
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    P = None
    for _ in range(240):
        P = player_ptr(p.mem)
        if P:
            break
        if time.time() - t0 > 240:
            break
        p.wait(30)
    if not P:
        ev.finish("FAILED: no player pointer (world never came up)")
        return 1
    p.wait(120)
    m, core = p.mem, p.core
    grab = core.frame_rgb
    ev.j({"ev": "world_ready", "P": hex(P),
          "wall_s": round(time.time() - t0, 1),
          "padbuff": snap(m).count(PADBUFF_SIG),
          "frame_shape": list(np.asarray(grab()).shape)})

    def settle(frames_max=200, need=40):
        stable, last_y = 0, None
        for _ in range(frames_max):
            y = pos_of(m, P)[1]
            stable = stable + 1 if y == last_y else 0
            last_y = y
            if stable >= need:
                break
            core.run(2, set())
        return pos_of(m, P)

    pos0 = settle()
    spawn_ring = pitch_now(m, P)                  # BEFORE any LOOK input
    spawn_yaw = yaw_now(m, P)
    yaw_ring = spawn_yaw
    rate_down, rate_up = measure_look_rate(core, m, P)
    ystep, _y1 = measure_yaw_step(core, m, P)
    ensure_world_control(core, m, P, ev, "boot")
    aim_to_ring(core, m, P, spawn_ring, rate_down, rate_up, "restore")
    core.run(8, set())
    pos1 = settle(frames_max=120, need=30)
    # spawn-altitude watch: the fall may complete late (unloaded chunks)
    if pos1[1] / L.ONE_BLOCK > 7.5:
        core.run(120, set())
        pos1 = settle(frames_max=120, need=30)
    cam_y, feet = L.camera_world_y(pos1[1])
    fbx, fbz = int(np.floor(pos1[0] / L.ONE_BLOCK)), \
        int(np.floor(pos1[2] / L.ONE_BLOCK))
    ev.j({"ev": "settled", "P": hex(P),
          "pos_blocks": [round(v / L.ONE_BLOCK, 3) for v in pos0],
          "pos_after": [round(v / L.ONE_BLOCK, 3) for v in pos1],
          "cam_y": round(cam_y, 2), "feet": round(feet, 2),
          "own_column": [fbx, fbz],
          "pitch_rate_down_deg": round(rate_down / L.DEG, 4),
          "pitch_rate_up_deg": round(rate_up / L.DEG, 4),
          "yaw_step_deg": round(ystep / L.DEG, 3),
          "ref_deg": round((spawn_ring % L.PITCH_MOD) / L.DEG, 2)})

    # inventory must be closed
    for _k in range(3):
        core.run(2, set())
        if int(m.u8(phys(m.u32(P + INV_OFF)) + 8)) == 0:
            break
        core.run(1, {UI_BTN})
        core.run(24, set())

    # ---------------- UI chain dump + cobble selection ----------------------
    slots = hotbar_slots(m, P)
    sel0, it0 = selected_hotbar(m, P)
    ev.png("r19t5_spawn_view", grab())
    table = next((it for it in slots.values()
                  if it and not it.get("unresolved") and it["id"] == ID_TABLE
                  and it["stack"] > 0), None)
    cobble = next((it for it in slots.values()
                   if it and not it.get("unresolved") and it["id"] == ID_COBBLE
                   and it["stack"] > 0), None)
    r7_match = bool(table) and int(table["addr"], 16) == 0x7CD98
    ev.j({"ev": "ui_dump", "selected_boot": sel0, "item_boot": it0,
          "table": table, "cobble": cobble,
          "inv_hbptr_ok": None, "r7_table_0x7cd98": r7_match,
          "sensors": ui_sensors(m, P)})
    cobble_slot = next((s for s, it in slots.items()
                        if it and it.get("addr") == (cobble or {}).get("addr")),
                       None)
    sel_ok, sel_trace = (True, []) if (cobble_slot == sel0) else \
        tap_r3_select(m, P, core, cobble_slot if cobble_slot is not None
                      else sel0)
    sel, sel_item = selected_hotbar(m, P)
    stack_addr = int(sel_item["addr"], 16) + ITEM_STACK
    table_addr = int(table["addr"], 16) + ITEM_STACK if table else None
    ev.j({"ev": "selected", "ok": sel_ok, "trace": sel_trace,
          "sel": sel, "item": sel_item, "stack_addr": hex(stack_addr),
          "table_stack_addr": hex(table_addr) if table_addr else None})
    p.save_state("r19t5_ready")

    # ---------------- NEGATIVE CONTROL (horizon L2) -------------------------
    aim_to_ring(core, m, P, spawn_ring, rate_down, rate_up, "nc")
    core.run(4, set())
    f_nc0 = grab()
    st_nc0 = int(m.u8(stack_addr))
    core.run(3, {PLACE_BTN})
    core.run(30, set())
    st_nc1 = int(m.u8(stack_addr))
    f_nc1 = grab()
    nc = {"stack": [st_nc0, st_nc1], **world_diff(f_nc0, f_nc1),
          "ok": st_nc0 == st_nc1}
    ev.png("r19t5_nc_horizon_post", f_nc1)
    ev.j({"ev": "NEGATIVE_CONTROL", **nc})

    # ---------------- WALK OFF the y7 spawn platform ------------------------
    walk_rec = walk_off_platform(core, m, P, ev)
    core.run(10, set())
    pos1 = settle(frames_max=160, need=30)
    cam_y, feet = L.camera_world_y(pos1[1])
    fbx, fbz = int(np.floor(pos1[0] / L.ONE_BLOCK)), \
        int(np.floor(pos1[2] / L.ONE_BLOCK))
    ev.j({"ev": "pos_after_walk",
          "pos_blocks": [round(v / L.ONE_BLOCK, 3) for v in pos1],
          "cam_y": round(cam_y, 2), "feet": round(feet, 2),
          "own_column": [fbx, fbz], "walk": walk_rec})

    # ---------------- attempts ---------------------------------------------
    # ground level after walk-off: feet ~5.0, cam ~6.7; pitch 30-60 deg hits
    # the y4/y5 ground within reach 6 and C=(x,5,z)/(x,6,z) is IN WORLD.
    PITCH_LADDER = (34.0, 42.0, 50.0, 26.0, 58.0, 66.0)
    attempts = []
    confirmed = 0
    for att in range(1, 4):
        if time.time() - t0 > T_BUDGET - 75:
            ev.j({"ev": "time_guard_skip", "attempt": att})
            break
        # fresh azimuth per attempt (after the first)
        if att > 1:
            yaw_ring = (yaw_ring + int(round(40.0 * L.DEG))) % L.PITCH_MOD
            yaw_dead_reckon(core, m, P, yaw_ring, ystep, btn=LOOK_YAWP)

        # --- framing: pitch ladder + engine sense ---------------------------
        chosen = None
        sense_log = []
        for pdeg in PITCH_LADDER:
            if time.time() - t0 > T_BUDGET - 55:
                break
            ring = (spawn_ring + int(round(pdeg * L.DEG))) % L.PITCH_MOD
            aim = aim_to_ring(core, m, P, ring, rate_down, rate_up,
                              "pdeg%g" % pdeg)
            core.run(4, set())
            achieved = round((((pitch_now(m, P) - spawn_ring)
                               % L.PITCH_MOD) / L.DEG + 180.0)
                             % 360.0 - 180.0, 2)
            bw = sense_hit(core, m, P)
            T = bw["hit"] if bw["live"] else None
            rec = {"pdeg": pdeg, "achieved_deg": achieved,
                   "aim_err_deg": aim["err_deg"],
                   "live": bw["live"], "T": T,
                   "reset_by_late": bw["reset_by_late"]}
            ok = False
            if T and T != [0, 0, 0]:
                g = L.hit_geometry(T, pos_of(m, P), cam_y)
                own = (T[0] == fbx and T[2] == fbz)
                rec.update({"geom_t": g["t"] if g else None,
                            "in_reach": g["in_reach"] if g else False,
                            "own_column": own,
                            "below_cam": T[1] < cam_y,
                            "C_in_world": T[1] <= L.WORLD_HEIGHT - 2,
                            "is_bump_top": is_bump_top(T)})
                ok = bool(g and g["in_reach"] and not own
                          and T[1] < cam_y
                          and T[1] <= L.WORLD_HEIGHT - 2
                          and bw["reset_by_late"])
            rec["ok"] = ok
            sense_log.append(rec)
            if ok and is_bump_top(T):
                chosen = {"pdeg": pdeg, "ring": ring, "T": tuple(T),
                          "bw": bw}
                break
            if ok and chosen is None:
                chosen = {"pdeg": pdeg, "ring": ring, "T": tuple(T),
                          "bw": bw}
        ev.j({"ev": f"framing_a{att}", "sense": sense_log,
              "chosen": chosen["pdeg"] if chosen else None,
              "T": list(chosen["T"]) if chosen else None})

        # --- pre-frame + terrain gate ---------------------------------------
        if not chosen:
            attempts.append({"attempt": att, "result": "NO_FRAMED_TARGET",
                             "sense": sense_log})
            ev.j({"ev": f"attempt_{att}", "result": "NO_FRAMED_TARGET"})
            continue
        aim_to_ring(core, m, P, chosen["ring"], rate_down, rate_up,
                    "pre_a%d" % att)
        core.run(6, set())
        f_pre, st_wait = stable_frame(core, grab, n=3)
        cs = center_stats(f_pre)
        terrain_ok = cs["center_std"] >= 8.0
        ev.png(f"r19t5_a{att}_pre", f_pre)
        ev.j({"ev": f"pre_frame_a{att}", "stats": cs,
              "stability_wait_f": st_wait, "terrain_ok": terrain_ok})
        if not terrain_ok:
            attempts.append({"attempt": att, "result": "FRAME_NOT_TERRAIN",
                             "stats": cs})
            continue

        T = chosen["T"]
        C = (T[0], T[1] + 1, T[2])   # top-face place cell (ray comes from above)
        pre_ram = snap(m)
        st0 = int(m.u8(stack_addr))
        st_tbl0 = int(m.u8(table_addr)) if table_addr else None

        # --- PLACE: up to 3 x 3-frame L2 taps (re-aim between taps) ---------
        # r19t5 run-2 lesson: a single tap at a freshly sensed target can
        # miss (stack unchanged) - retry with dead-reckon re-aim; stop on
        # stack drop or modal (crafting UI opens on a placed-table ray).
        st1, st_tbl1 = st0, st_tbl0
        modal_opened = False
        taps = 0
        burst = []
        for _tap in range(3):
            if _tap:
                aim_to_ring(core, m, P, chosen["ring"], rate_down, rate_up,
                            "retap_a%d" % att)
                core.run(6, set())
                stable_frame(core, grab, n=2)
            core.run(3, {PLACE_BTN})
            taps += 1
            burst = []
            for k in range(12):
                core.run(2, set())
                burst.append(grab())
            st1 = int(m.u8(stack_addr))
            inv_a, hb_a, mf, mb = ui_sensors(m, P)
            if bool(inv_a or mf or mb):
                modal_opened = True
                break
            if st1 < st0:
                break
        f_post = grab()
        st_tbl1 = int(m.u8(table_addr)) if table_addr else None
        inv_a, hb_a, mf, mb = ui_sensors(m, P)
        ui_px = None
        post_for_diff = f_post
        if modal_opened:
            ev.png(f"r19t5_a{att}_modal", f_post)
            ui_px = int(np.any(f_post.astype(np.int16)
                               != f_pre.astype(np.int16), axis=2).sum())
            core.run(2, {UI_BTN})          # place4 recovery: close modal
            core.run(24, set())
            wc = ensure_world_control(core, m, P, ev, f"a{att}_recover")
            aim_to_ring(core, m, P, chosen["ring"], rate_down, rate_up,
                        "recover_a%d" % att)
            core.run(4, set())
            post_for_diff = grab()
            inv_a, hb_a, mf, mb = ui_sensors(m, P)
        for k, f in enumerate(burst):   # keep only frames with framed change
            if region_px(f_pre, f, FRAME_BOX) > 40:
                ev.png(f"r19t5_a{att}_burst_{k:02d}", f)
        ev.png(f"r19t5_a{att}_post", post_for_diff)

        # --- visible metrics + persistence ----------------------------------
        vis = world_diff(f_pre, post_for_diff)
        core.run(30, set())
        f_p1 = grab()
        core.run(30, set())
        f_p2 = grab()
        vis_p = world_diff(f_pre, f_p2)
        vis_pp = world_diff(f_p1, f_p2)
        ev.png(f"r19t5_a{att}_persist", f_p2)
        post_ram = snap(m)

        # walk advisory (may be stale — r12 v9 lesson; never gates)
        walk_read = None
        try:
            wr = L.WorldReader(m)
            wr.discover()
            walk_read = {"T_id": wr.block_id(*T), "C_id": wr.block_id(*C)}
        except Exception as e:  # noqa: BLE001
            walk_read = {"err": str(e)[:100]}

        stack_drop = st1 < st0
        # control band: far-left ground strip outside FRAME_BOX and HUD;
        # a real placement is LOCAL - if the control band changed too, the
        # VIEW jittered (run-2 a3 texel shift) and the diff is not evidence.
        control_px = region_px(f_pre, post_for_diff, (10, 84, 70, 200))
        control_p = region_px(f_pre, f_p2, (10, 84, 70, 200))
        visible = (vis["world_px"] > 0 and vis["framed_px"] > 0
                   and control_px < max(40, vis["framed_px"] // 4))
        ui_clean = (inv_a == 0 and mf == 0 and mb == 0)   # hotbar HUD always 1
        rec = {"attempt": att, "item": sel_item.get("id"),
               "pitch_deg": chosen["pdeg"], "aim_deg": round(
                   (chosen["ring"] % L.PITCH_MOD) / L.DEG
                   - (spawn_ring % L.PITCH_MOD) / L.DEG, 2),
               "T": list(T), "C": list(C),
               "T_is_bump_top": is_bump_top(T), "taps": taps,
               "stack": [st0, st1], "stack_delta": st0 - st1,
               "table_stack": [st_tbl0, st_tbl1],
               "modal_opened": modal_opened, "ui_px": ui_px,
               "ui_sensors_after": {"inv": inv_a, "hb": hb_a,
                                    "modal_fn": mf, "modal_block": mb},
               "ui_clean": ui_clean,
               "pre_stats": cs,
               "control_px": control_px, "control_px_persist": control_p,
               "visible_pre_post": vis, "visible_persist60": vis_p,
               "persist_stability": vis_pp,
               "ram_words_changed": words_changed(pre_ram, post_ram),
               "walk_read": walk_read}
        # stack-drop-but-invisible discriminator: re-sense the same ring
        if stack_drop and not visible:
            bw2 = sense_hit(core, m, P)
            T2 = bw2["hit"] if bw2["live"] else None
            rec["rehit"] = {"live": bw2["live"], "T2": T2,
                            "earlier_than_T": bool(
                                T2 and T2 != list(T)) and bw2["live"],
                            "block_ptr": hex(int(bw2["block_ptr"]) & 0x1FFFFF)}
            if bw2["live"] and L.is_heap(bw2["block_ptr"]):
                bp = phys(bw2["block_ptr"])
                blk = phys(m.u32(bp)) if L.is_heap(bp) else 0
                if L.is_heap(blk):
                    rec["rehit"]["latched_id"] = int(m.u8(blk))
            ev.j({"ev": f"rehit_a{att}", **rec["rehit"]})
        rec["result"] = ("VISIBLE_PLACE" if (stack_drop and visible
                                             and ui_clean) else
                         "STACK_ONLY_INVISIBLE" if stack_drop else
                         "UI_RECOVERED_NO_PLACE" if modal_opened else
                         "NO_PLACE")
        attempts.append(rec)
        ev.j({"ev": f"attempt_{att}", **{k: rec[k] for k in (
            "attempt", "result", "stack", "stack_delta", "modal_opened",
            "visible_pre_post", "visible_persist60", "ui_clean")}})

        # --- dig-revert A/B on a VISIBLE placement (bonus causality) --------
        if rec["result"] == "VISIBLE_PLACE" and \
                time.time() - t0 < T_BUDGET - 40:
            dig = None
            for i in range(6):
                core.run(45, {ATTACK_BTN})
                f_d = grab()
                boxpx = region_px(f_d, f_pre, FRAME_BOX)
                if boxpx < max(8, vis["framed_px"] // 2):
                    break
            f_dig = grab()
            ev.png(f"r19t5_a{att}_dig_after", f_dig)
            dig = {"bursts": i + 1,
                   "framed_px_vs_pre_after_dig": region_px(f_dig, f_pre,
                                                           FRAME_BOX),
                   "framed_px_post_vs_pre": vis["framed_px"]}
            ev.j({"ev": f"dig_revert_a{att}", **dig})
            rec["dig_revert"] = dig
            if rec["result"] == "VISIBLE_PLACE":
                confirmed += 1

    confirmed = sum(1 for a in attempts
                    if a.get("result") == "VISIBLE_PLACE")
    stack_evidence = [a for a in attempts if a.get("stack_delta", 0) > 0]
    if confirmed >= 1:
        verdict = (f"CONFIRMED(visible place x{confirmed}; "
                   f"stack-drop events {len(stack_evidence)}; "
                   f"UI-guard clean; L2=BINDING_USE)")
    elif stack_evidence:
        verdict = ("INCONCLUSIVE(stack consumed x%d but no visible "
                   "world_px in the framed region; reasons: %s)" %
                   (len(stack_evidence),
                    "; ".join(a["result"] for a in attempts)))
    else:
        verdict = "INCONCLUSIVE(no stack consumption; %s)" % \
            "; ".join(a["result"] for a in attempts) or "no attempts"

    # ---------------- structure shots + final state -------------------------
    if confirmed or stack_evidence:
        aim_to_ring(core, m, P, spawn_ring, rate_down, rate_up, "final_h")
        core.run(6, set())
        ev.png("r19t5_final_horizon", grab())
        ring_d = (spawn_ring + int(round(35.0 * L.DEG))) % L.PITCH_MOD
        aim_to_ring(core, m, P, ring_d, rate_down, rate_up, "final_d35")
        core.run(4, set())
        ev.png("r19t5_final_down35", grab())
    p.save_state("r19t5_built")

    # ---------------- GIF from the best visible attempt ---------------------
    gif_info = {"path": None, "bytes": None, "url": None}
    best = next((a for a in attempts if a["result"] == "VISIBLE_PLACE"),
                None)
    if best:
        try:
            from PIL import Image
            att = best["attempt"]
            seq = [("r19t5_a%d_pre" % att, 900)]
            for k in range(12):
                seq.append(("r19t5_a%d_burst_%02d" % (att, k), 160))
            seq += [("r19t5_a%d_post" % att, 900),
                    ("r19t5_a%d_persist" % att, 900)]
            frames, durs = [], []
            for name, dur in seq:
                fp = name if os.path.isabs(name) else \
                    os.path.join(OUT, name + ".png")
                if os.path.exists(fp):
                    frames.append(Image.open(fp).convert("RGB"))
                    durs.append(dur)
            if len(frames) >= 3:
                gif_path = os.path.join(OUT, "r19t5_visible_place.gif")
                frames[0].save(gif_path, save_all=True,
                               append_images=frames[1:], duration=durs,
                               loop=0, optimize=True)
                gif_info["path"] = gif_path
                gif_info["bytes"] = os.path.getsize(gif_path)
                ev.j({"ev": "gif_built", **{k: gif_info[k]
                                            for k in ("path", "bytes")}})
        except Exception as e:  # noqa: BLE001
            ev.j({"ev": "gif_err", "err": str(e)[:160]})
        # prune burst PNGs after GIF (keep evidence dir small)
        for f in os.listdir(OUT):
            if "_burst_" in f and f.endswith(".png"):
                try:
                    os.remove(os.path.join(OUT, f))
                except OSError:
                    pass

    # ---------------- upload to uguu.se -------------------------------------
    if gif_info["path"]:
        for attempt_up in range(2):
            try:
                r = subprocess.run(
                    ["curl", "-sS", "-m", "45", "-F",
                     "files[]=@%s;type=image/gif" % gif_info["path"],
                     "https://uguu.se/upload"],
                    capture_output=True, text=True, timeout=60)
                try:
                    j = json.loads(r.stdout)
                    url = j.get("files", [{}])[0].get("url")
                except Exception:  # noqa: BLE001
                    url = None
                if not url:
                    mm = re.search(r"https://[a-z]?\.?uguu\.se/\S+?\.gif",
                                   r.stdout)
                    url = mm.group(0) if mm else None
                if url:
                    gif_info["url"] = url
                    ev.j({"ev": "gif_uploaded", "url": url})
                    break
                ev.j({"ev": "upload_try", "n": attempt_up,
                      "resp": r.stdout[:200]})
            except Exception as e:  # noqa: BLE001
                ev.j({"ev": "upload_err", "err": str(e)[:160]})

    # ---------------- report ------------------------------------------------
    rep = {"schema": "ps1play-r19t5-psxmc/1",
           "task": "r19-t5 PSX-Minecraft VISIBLE placement",
           "game": "PSX-Minecraft infdev_2025_04_18 (MIT, EngineersBox)",
           "boot": {"P": hex(P),
                    "pos_blocks": [round(v / L.ONE_BLOCK, 3) for v in pos1],
                    "cam_y": round(cam_y, 2), "own_column": [fbx, fbz],
                    "pitch_step_deg": round(rate_down / L.DEG, 3),
                    "yaw_step_deg": round(ystep / L.DEG, 3)},
           "selection": {"selected": sel, "item": sel_item,
                         "stack_addr": hex(stack_addr),
                         "r7_table_0x7cd98": r7_match},
           "negative_control": nc,
           "attempts": attempts,
           "confirmed_places": confirmed,
           "verdict": verdict,
           "gif": {"path": gif_info["path"], "bytes": gif_info["bytes"],
                   "url": gif_info["url"]},
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    ev.finish(verdict)
    print("VERDICT:", verdict)
    try:
        core.close()
    except Exception:  # noqa: BLE001
        pass
    return 0 if confirmed else 2


if __name__ == "__main__":
    sys.exit(main())
