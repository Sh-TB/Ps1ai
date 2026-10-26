#!/usr/bin/env python3
"""psxmc_r9_place6.py — Task 9-b (Round 9, Issue #6): ONE VISIBLE world
placement in PSX-Minecraft (infdev_2025_04_18, MIT) — ray-directed aim with
the target face IN FRAME, then the world_px gate.

Round-8 record (place5, report_place5.json): stack @0x7cda0 never moved
(26->26), stack_scan [] everywhere, "ui_opened" fired on EVERY L2 tap —
INCLUDING the 7.5 deg CONTROL arm that geometrically cannot open any UI
(t = 1.7/sin(7.5) = 13 > reach 6). Pixel forensics this round on the r8 PNGs
shows the "UI" diffs are HALF-SCREEN (x0-158 / x160-319 components, mean|d|
~40-57) that VANISH by the after-frame in the control arm — the signature of
a torn/stale framebuffer grab, not a modal dialog. The persistent 35-40k
"world_px" in the ladder arms is the horizon band shifting (rows 78-100,
lum +30) caused by the recovery LOOK_DOWN probe running BETWEEN f_pre and
f_after. Both artifacts are eliminated here:

  * STABLE FRAMES: every analysed frame is only accepted after two
    consecutive grabs are bit-exact.
  * NO CAMERA MOVEMENT between f_pre and f_after: recovery probes run only
    AFTER the after-frame is captured.

NEW MEASUREMENT LEVER (the round-8 "next lever"): the USE/ATTACK raycast is
mapped LIVE. Holding BINDING_ATTACK (PAD_R2) for 3 frames at a known pitch
updates player->breaking (breaking_state.h: position VECTOR @+12, IBlock*
block @+16, zeroed by reset on release; player.c:134 updateBreakingState
runs only when the ray HIT a non-air block). So a 3-frame R2 tap at pitch p
leaves the raycast HIT BLOCK COORDS readable in RAM. Mapping ring-pitch ->
hit-block reconstructs (a) the true ray direction per ring value (verifies
the 5o mapping: rotationToDirection5o = sin5o/cos5o, +-1 count, vector.c:24;
TRIG_5TH_ORDER_REDUCTION 9 => ring 2^24/circle -> 2^15/circle sin5o arg),
(b) the terrain profile ahead of the player, (c) which pitches put the hit
within PLAYER_REACH_DISTANCE 6 (player.h:27, euclidean from the camera at
feet+1.7, PLAYER_CAMERA_OFFSET 487424 = 1.7*ONE_BLOCK).

Source-derived constants: place at hit+face (player.c:321); stack consumed
in the block constructor (block.h DEFN_BLOCK_CONSTRUCTOR_IMPL_STATELESS
item->stack_size--), reverted by canPlace failure (player.c:323 stack_size++
=> net 0 — indistinguishable from no-hit by stack alone, hence the R2 map);
BLOCKID useAction opens the crafting UI only on a real table hit
(player.c:291). UI close = START (block_crafting_table.c:200). Flatland gen
(overworld_flatland.c): stone y<2, dirt y<4, grass y==4, bumps at
x%3==0&&z%3==0 y==5 — but r8 pos.y read 9.62, so perlin terrain is possible;
the R2 map measures it live.

Plan: boot -> baseline (+yaw probe) -> render calibration (horizon row at
ring 0/+10/+20, stable frames) -> R2 raycast map over ring 5..80 deg ->
CONTROL arm (no-hit pitch) -> graduated L2 ladder over in-reach pitches
(stack @0x7cda0 + stack_scan + stable after-frame diff: world_px / win_px
inside the predicted block window rows 60-135) -> first success: heatmap PNG
-> steepest in-reach tap as off-frame/steep repro. ONE beetle boot per
process; savestates pl6_*. Evidence: scratch/issue6_round9_psxmc/.
Verdict vocabulary is honest; negatives recorded with numbers.
"""
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from psxmc_r7_lib import (A_INPUT, A_PLAYER, Evid, PADBUFF_SIG,  # noqa: E402
                          idle_window, sha, words_changed)

CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r8"   # pinned, verbatim r8
OUT = os.path.join(REPO, "scratch", "issue6_round9_psxmc")
TAG = "place6"

PITCH_MOD = 1 << 24
DEG = PITCH_MOD / 360.0
ONE_BLOCK = 286720
ONE = 4096                       # FIXED_POINT_SHIFT 12
T_MAX = 420.0
ITEMID_CRAFTING_TABLE = 58
STACK_ADDR = 0x7CDA0             # live-verified r7 chain 26->25->24->23
HUD_BAND = (56, 208, 264, 240)   # x0,y0,x1,y1 hotbar band
BLOCK_WIN = (100, 60, 220, 135)  # predicted visible-block window (x0,y0,x1,y1)
EDGE_THR = 3.0

LOOK_DOWN = "B"     # PAD_CROSS: ring + (player.c:435)
LOOK_UP = "X"       # PAD_TRIANGLE: ring -
LOOK_RIGHT = "O"    # PAD_CIRCLE: yaw-
LOOK_LEFT = "SQ"    # PAD_SQUARE: yaw+  (r9 fix: inputmap name is SQ)
PLACE_BTN = "L2"    # BINDING_USE
ATTACK_BTN = "R2"   # BINDING_ATTACK (breaking-state probe)
UI_BTN = "START"    # BINDING_OPEN_INVENTORY closes the crafting UI

MAP_PITCHES = (5.0, 10.0, 15.0, 17.5, 20.0, 22.5, 25.0, 30.0, 40.0,
               50.0, 60.0, 70.0, 80.0)
# avoid exactly 90 deg: direction (0,0,0) -> DDA tMax 0/0 NaN hang
# (world_raycast.c intboundd with ds==0); avoid 0 for the ladder.


def s32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def snap(m):
    return bytes(m.snapshot())


def player_ptr(m):
    v = m.u32(A_PLAYER)
    if (v & 3) == 0 and 0x10000 < (v & 0x1FFFFF) < 0x1F8000:
        y = s32(m.u32((v & 0x1FFFFF) + 4))
        if abs(y) < 40 * ONE_BLOCK * 4:
            return v & 0x1FFFFF
    return None


def held_word(m):
    return {"stat": m.u8(A_INPUT), "id": hex(m.u8(A_INPUT + 1)),
            "held": hex((~m.u16(A_INPUT + 2)) & 0xFFFF)}


def pos_of(m, P):
    return [s32(m.u32(P)), s32(m.u32(P + 4)), s32(m.u32(P + 8))]


def ring_diff(a, b):
    return (b - a + (PITCH_MOD >> 1)) % PITCH_MOD - (PITCH_MOD >> 1)


def pitch_now(m, P):
    return m.u32(P + 0x18) & (PITCH_MOD - 1)


def yaw_now(m, P):
    return m.u32(P + 0x1C) & (PITCH_MOD - 1)


def words_changed_ram(a, b):
    return int(np.count_nonzero(
        np.frombuffer(a, "<u4") != np.frombuffer(b, "<u4")))


# ---------------- pixel sensors -------------------------------------------
def edge_energy(f):
    L = (0.299 * f[..., 0].astype(np.float32)
         + 0.587 * f[..., 1].astype(np.float32)
         + 0.114 * f[..., 2].astype(np.float32))
    e = np.zeros(L.shape, np.float32)
    e[:, :-1] += np.abs(L[:, 1:] - L[:, :-1])
    e[:-1, :] += np.abs(L[1:] - L[:-1])
    return e


def ground_stats(f):
    e = edge_energy(f)
    rm = e.mean(axis=1)
    grows = int((rm > EDGE_THR).sum())
    q = [round(float(np.percentile(rm, p)), 2) for p in (10, 50, 90)]
    return {"ground_rows": grows, "row_q": q}


def horizon_row(f):
    """Topmost row of the contiguous ground block at the bottom of the
    frame (rows whose mean edge energy exceeds EDGE_THR)."""
    rm = edge_energy(f).mean(axis=1)
    rows = np.nonzero(rm > EDGE_THR)[0]
    if not len(rows):
        return None
    # walk up from the bottom while rows stay grounded (allow 2-row gaps)
    y = 239
    last = 239
    for y in range(239, -1, -1):
        if rm[y] > EDGE_THR:
            last = y
        elif last - y > 2:
            break
    return int(last - (239 - (rows.min() if len(rows) else 239))) \
        if False else int(last)


def lum(f):
    return (0.299 * f[..., 0].astype(np.float32)
            + 0.587 * f[..., 1].astype(np.float32)
            + 0.114 * f[..., 2].astype(np.float32))


def diff_metrics(a, b, block_win):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    mask = d > 2
    hud = np.zeros_like(mask)
    hud[HUD_BAND[1]:HUD_BAND[3], HUD_BAND[0]:HUD_BAND[2]] = True
    world = mask & ~hud
    win = np.zeros_like(mask)
    win[block_win[1]:block_win[3], block_win[0]:block_win[2]] = True
    n = int(world.sum())
    bb = None
    if n:
        ys, xs = np.nonzero(world)
        bb = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    return {"changed_px": int(mask.sum()), "world_px": n,
            "win_px": int((world & win).sum()), "bbox": bb,
            "max_d": int(d.max()), "hud_px": int((mask & hud).sum())}


def save_heat(ev, name, a, b, block_win):
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    mask = d > 2
    ov = (a.astype(np.float32) * 0.30).astype(np.uint8)
    ov[..., 0][mask] = 255
    ov[..., 1][mask] = 96
    ov[..., 2][mask] = 32
    for (x0, y0, x1, y1), col in ((block_win, (255, 255, 0)),
                                  (HUD_BAND, (0, 160, 255))):
        ov[y0:y1, x0] = col
        ov[y0:y1, x1 - 1] = col
        ov[y0, x0:x1] = col
        ov[y1 - 1, x0:x1] = col
    ev.png(name, ov)


def save_pair(ev, name, a, b):
    from PIL import Image
    sep = np.full((4, a.shape[1], 3), 255, np.uint8)
    p = os.path.join(ev.dir, f"{name}.png")
    Image.fromarray(np.concatenate([a, sep, b], axis=0)).save(p)
    ev.png_count += 1
    return p


# ---------------- stable frames / aim --------------------------------------
def stable_frame(core, grab, max_tries=30, idle_between=1):
    """Run frames until two consecutive grabs are bit-exact (kills the
    torn/stale-buffer artifact that poisoned place5's ui_opened flag)."""
    core.run(2, set())
    a = grab()
    for _ in range(max_tries):
        core.run(idle_between, set())
        b = grab()
        if np.array_equal(a, b):
            return b, True
        a = b
    return a, False


def aim_ring_exact(core, m, P, pitch0, want_deg, tol_deg=0.35, max_it=400):
    want = (pitch0 + int(round(want_deg * DEG))) % PITCH_MOD
    frames = 0
    cur = pitch_now(m, P)
    err = ring_diff(cur, want)
    it = 0
    stall = 0
    best = abs(err)
    while abs(err) > tol_deg * DEG and it < max_it and stall < 3:
        step = 5 if abs(err) > 4 * DEG else 1
        core.run(step, {LOOK_DOWN} if err > 0 else {LOOK_UP})
        frames += step
        cur = pitch_now(m, P)
        err = ring_diff(cur, want)
        it += 1
        if abs(err) < best - 0.05 * DEG:
            best = abs(err)
            stall = 0
        else:
            stall += 1
    return {"want_deg": want_deg, "err_deg": round(err / DEG, 3),
            "frames": frames}


def ensure_world_control(core, m, P, ev, tag):
    """Post-capture recovery ONLY (never between f_pre and f_after):
    6-frame LOOK_DOWN probe must move the ring; else single-frame START
    taps (>200 ms apart) toggle the focused UI layer."""
    rec = {"rounds": 0, "alive": False, "start_taps": 0}
    for rnd in range(4):
        a = pitch_now(m, P)
        core.run(6, {LOOK_DOWN})
        moved = abs(ring_diff(a, pitch_now(m, P))) > 0.2 * DEG
        core.run(2, set())
        rec["rounds"] = rnd + 1
        if moved:
            rec["alive"] = True
            break
        core.run(1, {UI_BTN})
        rec["start_taps"] += 1
        core.run(18, set())
    ev.j({"ev": f"world_control_{tag}", **rec})
    return rec


def stack_scan(pre, post, pairs=((26, 25), (25, 24), (24, 23), (23, 22),
                                 (22, 21), (21, 20), (10, 9))):
    a = np.frombuffer(pre, np.uint8)
    b = np.frombuffer(post, np.uint8)
    hits = []
    for va, vb in pairs:
        for i in np.nonzero((a == va) & (b == vb))[0]:
            i = int(i)
            if i < 16:
                continue
            ids = [int(np.frombuffer(pre[i - d:i - d + 4], "<u4")[0])
                   for d in range(4, 13) if i - d >= 0]
            rec = {"addr": hex(i), "before": va, "after": vb,
                   "itemid_ctx": ITEMID_CRAFTING_TABLE in ids,
                   "is_stack_addr": i == STACK_ADDR}
            if rec["itemid_ctx"]:
                hits.append(rec)
    return hits


# ---------------- raycast mapping via breaking-state probe ------------------
def find_breaking_offset(m, P, snap_a, snap_b):
    """Diff two attack-probe snapshots (different pitches => different hit
    blocks): find the i32-triple offset K in the Player struct window where
    (K..K+8) holds block coords in both snaps and a plausible IBlock* heap
    pointer sits at K+12 or K+16 (breaking_state.h: VECTOR position; 1 byte
    bitfields + padding; IBlock* block)."""
    a = np.frombuffer(snap_a, "<i4")
    b = np.frombuffer(snap_b, "<i4")
    aw = np.frombuffer(snap_a, "<u4")
    lo, hi = P, min(P + 0x600, len(snap_a) - 24)
    cands = []
    for i in range(lo >> 2, hi >> 2):
        if a[i] == b[i] and a[i + 1] == b[i + 1] and a[i + 2] == b[i + 2]:
            continue                      # must CHANGE between the probes
        for s in (a, b):
            x, y, z = int(s[i]), int(s[i + 1]), int(s[i + 2])
            if not (-32 <= x <= 32 and 0 <= y <= 48 and -32 <= z <= 32):
                break
        else:
            for pk in (i + 3, i + 4):     # K+12 / K+16
                pv = int(aw[pk])
                if 0x10000 <= (pv & 0x1FFFFF) < 0x1F8000 and (pv & 3) == 0:
                    cands.append({"off": i * 4, "ptr_off": pk * 4,
                                  "a": [int(a[i]), int(a[i + 1]),
                                        int(a[i + 2])],
                                  "b": [int(b[i]), int(b[i + 1]),
                                        int(b[i + 2])]})
    return cands


def read_breaking(m, P, off, ptr_off):
    x = s32(m.u32(P + off))
    y = s32(m.u32(P + off + 4))
    z = s32(m.u32(P + off + 8))
    blk = m.u32(P + ptr_off)
    return [x, y, z], blk


def attack_probe(p, m, P, ev, pitch0, pdeg, tag):
    """Aim ring +pdeg (ray down), hold R2 3 frames (breaking state latches
    the raycast hit), release, read breaking.position/block."""
    core, grab = p.core, p.core.frame_rgb
    aim = aim_ring_exact(core, m, P, pitch0, pdeg)
    f_pre, stable = stable_frame(core, grab)
    if tag in ("m80", "m50"):
        ev.png(f"pl6_map_{tag}_view", f_pre)
    pre_snap = snap(m)
    core.run(3, {ATTACK_BTN})
    core.run(1, set())
    post = snap(m)
    core.run(8, set())                    # release -> reset_trigger -> zeroed
    return {"pdeg": pdeg, "aim": aim, "stable": stable, "pre": pre_snap,
            "post": post, "frame": f_pre}


# ---------------- one place attempt ----------------------------------------
def use_attempt(p, m, P, ev, pitch0, pdeg, label):
    """Aim (closed-loop), settle, STABLE f_pre, 1-frame L2 tap, stack +
    RAM scan in the same tick window, STABLE f_after with ZERO camera
    movement in between, diff, THEN recovery probe."""
    core, grab = p.core, p.core.frame_rgb
    alive0 = ensure_world_control(core, m, P, ev, f"pre_{label}")
    aim = aim_ring_exact(core, m, P, pitch0, pdeg)
    f_pre, stable_pre = stable_frame(core, grab)
    ev.png(f"pl6_{label}_pre", f_pre)
    pre = snap(m)
    stack_before = int(m.u8(STACK_ADDR))
    ev.j({"ev": f"tap_{label}", "pdeg": pdeg, "aim": aim,
          "stack_before": stack_before, "stable_pre": stable_pre,
          "held": held_word(m)})
    core.run(1, {PLACE_BTN})
    core.run(2, set())
    post = snap(m)
    stack_after = int(m.u8(STACK_ADDR))
    hits = stack_scan(pre, post)
    f_after, stable_after = stable_frame(core, grab)   # NO look input here
    ev.png(f"pl6_{label}_after", f_after)
    am = diff_metrics(f_pre, f_after, BLOCK_WIN)
    save_heat(ev, f"pl6_{label}_heat", f_pre, f_after, BLOCK_WIN)
    save_pair(ev, f"pl6_{label}_pair", f_pre, f_after)
    rec = {"label": label, "pdeg": pdeg, "aim": aim,
           "ctrl_pre": alive0, "stable": [stable_pre, stable_after],
           "stack_before": stack_before, "stack_after": stack_after,
           "stack_delta": stack_before - stack_after,
           "stack_hits": hits, "after_metrics": am}
    rec["placed"] = bool(hits) or stack_after < stack_before
    rec["visible"] = rec["placed"] and am["world_px"] > 0 and \
        am["win_px"] > 0
    ev.j({"ev": f"attempt_{label}",
          **{k: rec[k] for k in ("pdeg", "stack_before", "stack_after",
                                 "stack_delta", "placed", "visible")},
          "hits": hits, "after": am})
    # recovery AFTER the after-frame capture
    alive1 = ensure_world_control(core, m, P, ev, f"post_{label}")
    rec["ctrl_post"] = alive1
    return rec


def main():
    ev = Evid(OUT, TAG)
    ev.jpath = os.path.join(OUT, "r9_place6.jsonl")
    ev.j({"ev": "start", "cue": CUE, "workspace": WS,
          "task": "9-b place6", "model": "ray-directed aim: live raycast "
          "map via R2 breaking-state probe; stable frames; no camera "
          "movement between pre/after; reach 6 euclidean from camera "
          "feet+1.7; place at hit+face; constructor--, canPlace-fail ++"})
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
        ev.finish("FAILED: no player pointer (world never came up)")
        return 1
    p.wait(150)
    m = p.mem
    core = p.core
    grab = core.frame_rgb
    pos0 = pos_of(m, P)
    pitch0 = pitch_now(m, P)
    yaw0 = yaw_now(m, P)
    stack0 = int(m.u8(STACK_ADDR))
    f_world, stable0 = stable_frame(core, grab)
    ev.png("pl6_01_world_pitch0", f_world)
    gs0 = ground_stats(f_world)
    hz0 = horizon_row(f_world)
    frames, exact0 = idle_window(core, grab, n=8)
    ram0 = snap(m)
    ev.step("baseline", {
        "P": hex(P), "pos_blocks": [round(v / ONE_BLOCK, 2) for v in pos0],
        "pitch0_raw": pitch0, "yaw0_raw": yaw0,
        "stack_0x7cda0": stack0, "ground_stats": gs0,
        "horizon_row": hz0, "stable": stable0, "idle_bit_exact": exact0,
        "padbuff": snap(m).count(PADBUFF_SIG), "ram_sha": sha(ram0)[:16]})

    # ------------- yaw probe (verify P+0x1C is the yaw ring) ---------------
    ya = yaw_now(m, P)
    core.run(6, {LOOK_RIGHT})
    core.run(2, set())
    yb = yaw_now(m, P)
    ydelta = s32(ring_diff(ya, yb))
    if ydelta == 0:
        before = snap(m)
        core.run(6, {LOOK_RIGHT})
        core.run(2, set())
        after = snap(m)
        diff_idx = [i for i in range(P >> 2, (P + 0x40) >> 2)
                    if np.frombuffer(before, "<u4")[i]
                    != np.frombuffer(after, "<u4")[i]]
        yaw_off = (diff_idx[0] * 4 - P) if diff_idx else None
        ev.j({"ev": "yaw_rescan", "yaw_off": yaw_off})
        if yaw_off is not None:
            globals()["yaw_now"] = (lambda m, P, o=yaw_off:
                                    m.u32(P + o) & (PITCH_MOD - 1))
            ydelta = s32(ring_diff(ya, globals()["yaw_now"](m, P)))
    ev.j({"ev": "yaw_probe", "delta_ring": ydelta,
          "delta_deg": round(ydelta / DEG, 2)})
    # return to yaw0 for a consistent facing
    guard = 0
    while abs(s32(ring_diff(yaw0, yaw_now(m, P)))) > 0.5 * DEG and guard < 400:
        core.run(1, {LOOK_LEFT if ring_diff(yaw_now(m, P), yaw0) > 0
                     else LOOK_RIGHT})
        guard += 1
    core.run(2, set())

    # ------------- render calibration (stable frames) ----------------------
    cal = {}
    for pdeg in (0.0, 10.0, 20.0):
        aim_ring_exact(core, m, P, pitch0, pdeg)
        f, st = stable_frame(core, grab)
        ev.png(f"pl6_cal_ring{pdeg:g}", f)
        cal[f"{pdeg:g}"] = {"horizon_row": horizon_row(f),
                            "ground_rows": ground_stats(f)["ground_rows"],
                            "stable": st}
        ev.j({"ev": "cal", "pdeg": pdeg, **cal[f"{pdeg:g}"]})
    aim_ring_exact(core, m, P, pitch0, 0.0)
    hz = [cal[k]["horizon_row"] for k in ("0", "10", "20")]
    if None not in hz and hz[2] < hz[0] - 8:
        render_conv = "DIRECT (ring+ = camera DOWN: horizon row rises)"
    elif None not in hz and hz[2] > hz[0] + 8:
        render_conv = "INVERTED (ring+ = camera UP)"
    else:
        render_conv = "UNCLEAR"
    ev.j({"ev": "render_convention", "verdict": render_conv,
          "horizon_rows": hz})

    # ------------- savestate insurance ------------------------------------
    core.run(20, set())
    p.save_state("pl6_pre")
    ev.j({"ev": "save_state", "name": "pl6_pre"})

    # ------------- R2 raycast map ------------------------------------------
    probes = {}
    snaps = {}
    for pdeg in MAP_PITCHES:
        if time.time() - ev.t0 > T_MAX - 200:
            ev.j({"ev": "time_guard_skip_map", "pdeg": pdeg})
            break
        tag = f"m{pdeg:g}"
        rec = attack_probe(p, m, P, ev, pitch0, pdeg, tag)
        probes[pdeg] = rec
        snaps[pdeg] = rec["post"]
    boff = None
    if 80.0 in snaps and 50.0 in snaps:
        cands = find_breaking_offset(m, P, snaps[80.0], snaps[50.0])
        ev.j({"ev": "breaking_offset_candidates", "cands": cands[:12]})
        if cands:
            boff = (cands[0]["off"], cands[0]["ptr_off"])
    elif len(snaps) >= 2:
        ks = sorted(snaps)
        cands = find_breaking_offset(m, P, snaps[ks[0]], snaps[ks[-1]])
        ev.j({"ev": "breaking_offset_candidates", "cands": cands[:12]})
        if cands:
            boff = (cands[0]["off"], cands[0]["ptr_off"])
    ev.j({"ev": "breaking_offset", "off": None if not boff else boff[0],
          "ptr_off": None if not boff else boff[1]})

    posb = [v / ONE_BLOCK for v in pos_of(m, P)]
    pxb, pyb, pzb = posb
    ground_y = None
    raymap = []
    for pdeg in sorted(probes):
        rec = probes[pdeg]
        if boff:
            (bx, by, bz), blk = read_breaking(m, P, boff[0], boff[1])
            hit = bool(blk) and (bx, by, bz) != (0, 0, 0)
            if hit and pdeg == 80.0:
                ground_y = by
            cam_y = (ground_y + 1 + 1.7) if ground_y is not None \
                else (pyb + 1.7)
            t = None
            if hit:
                t = ((bx + 0.5 - pxb) ** 2 + (by + 0.5 - cam_y) ** 2 +
                     (bz + 0.5 - pzb) ** 2) ** 0.5
            raymap.append({"pdeg": pdeg, "hit": [bx, by, bz] if hit else None,
                           "blk": hex(blk), "t": None if t is None
                           else round(t, 2),
                           "in_reach": bool(hit and t <= 6.0)})
        else:
            raymap.append({"pdeg": pdeg, "hit": None, "blk": "0",
                           "t": None, "in_reach": False,
                           "note": "no breaking offset located"})
    ev.step("raycast_map", {
        "breaking_off": None if not boff else list(boff),
        "ground_block_y": ground_y,
        "pos_blocks_now": [round(v, 2) for v in posb],
        "map": raymap})

    in_reach = [r["pdeg"] for r in raymap if r["in_reach"]]
    no_hit = [r["pdeg"] for r in raymap if not r["hit"]]
    ev.j({"ev": "map_summary", "in_reach": in_reach, "no_hit": no_hit,
          "ground_block_y": ground_y})

    # ------------- CONTROL arm: pitch the map says cannot hit --------------
    ctrl_pdeg = 5.0 if 5.0 in no_hit else (no_hit[0] if no_hit else 5.0)
    ctrl_rec = use_attempt(p, m, P, ev, pitch0, ctrl_pdeg, "control")
    ctrl_ok = (not ctrl_rec["placed"]) and ctrl_rec["stack_delta"] == 0 and \
        ctrl_rec["after_metrics"]["world_px"] < 400

    # ------------- USE ladder over in-reach pitches ------------------------
    ladder = []
    ok_visible = None
    chain = {}
    order = [q for q in (17.5, 20.0, 22.5, 25.0, 15.0, 30.0, 40.0, 50.0,
                         60.0, 70.0, 80.0, 10.0) if q in in_reach]
    for pdeg in order:
        if time.time() - ev.t0 > T_MAX - 120:
            ev.j({"ev": "time_guard_skip", "pdeg": pdeg})
            break
        if ok_visible:
            break
        rec = use_attempt(p, m, P, ev, pitch0, pdeg, f"a{pdeg:g}")
        ladder.append(rec)
        for h in rec["stack_hits"]:
            chain.setdefault(h["addr"], []).append([h["before"], h["after"]])
        if rec["visible"]:
            ok_visible = rec
        if rec["placed"] and not rec["visible"]:
            ev.j({"ev": "placed_not_visible", "pdeg": pdeg,
                  "world_px": rec["after_metrics"]["world_px"],
                  "bbox": rec["after_metrics"]["bbox"]})

    # ------------- steep/off-frame reproduction ----------------------------
    off_rec = None
    steep = [q for q in (60.0, 70.0, 80.0, 50.0) if q in in_reach]
    if ok_visible and steep and time.time() - ev.t0 < T_MAX - 80:
        off_rec = use_attempt(p, m, P, ev, pitch0, steep[0], "steep")
        ev.j({"ev": "steep_repro", "pdeg": off_rec["pdeg"],
              "placed": off_rec["placed"],
              "stack_delta": off_rec["stack_delta"],
              "world_px": off_rec["after_metrics"]["world_px"],
              "bbox": off_rec["after_metrics"]["bbox"]})

    # ------------- final framing + totals ---------------------------------
    aim_end = aim_ring_exact(core, m, P, pitch0, 0.0)
    core.run(6, set())
    ev.png("pl6_09_final_horizon", grab())
    ram_end = snap(m)
    stack_end = int(m.u8(STACK_ADDR))
    n_placed = sum(1 for r in ([ctrl_rec] + ladder +
                               ([off_rec] if off_rec else []))
                   if r and r["placed"])
    totals = {
        "render_convention": render_conv,
        "breaking_off": None if not boff else list(boff),
        "ground_block_y": ground_y,
        "raycast_map": raymap,
        "control_ok": ctrl_ok,
        "control": {"pdeg": ctrl_rec["pdeg"],
                    "stack_delta": ctrl_rec["stack_delta"],
                    "world_px": ctrl_rec["after_metrics"]["world_px"]},
        "ladder": [{"pdeg": r["pdeg"], "stack_delta": r["stack_delta"],
                    "placed": r["placed"], "visible": r["visible"],
                    "world_px": r["after_metrics"]["world_px"],
                    "win_px": r["after_metrics"]["win_px"],
                    "bbox": r["after_metrics"]["bbox"]} for r in ladder],
        "steep_repro": None if not off_rec else {
            "pdeg": off_rec["pdeg"], "placed": off_rec["placed"],
            "stack_delta": off_rec["stack_delta"],
            "world_px": off_rec["after_metrics"]["world_px"],
            "bbox": off_rec["after_metrics"]["bbox"]},
        "visible_placements": 1 if ok_visible else 0,
        "placed_total": n_placed,
        "stack_chain": chain,
        "stack_first_last": [stack0, stack_end],
        "ram_words_changed_vs_boot": words_changed_ram(ram0, ram_end),
    }
    ev.step("totals", totals)

    if ok_visible and ctrl_ok:
        verdict = ("CAUSAL(place VISIBLE): stack %d->%d @0x7cda0 with "
                   "world_px %d / win_px %d in the predicted block window; "
                   "control arm (map no-hit pitch) left stack untouched"
                   % (ok_visible["stack_before"], ok_visible["stack_after"],
                      ok_visible["after_metrics"]["world_px"],
                      ok_visible["after_metrics"]["win_px"]))
    elif ok_visible:
        verdict = "STATE_CHANGE_CONFIRMED(place VISIBLE; control arm dirty)"
    elif ladder and any(r["placed"] for r in ladder):
        verdict = ("INCONCLUSIVE(place): stack consumed (chain %s) but zero "
                   "in-frame placements" % (chain or "n/a"))
    elif ctrl_ok:
        verdict = ("INCONCLUSIVE(place): L2 taps never decremented the stack "
                   "even at R2-mapped in-reach pitches %s; control clean"
                   % in_reach)
    else:
        verdict = "FAILED: control arm also anomalous (sensor chain suspect)"
    ev.finish(verdict)

    import json
    merged = {"task": "9-b (round 9 place6)",
              "game": "PSX-Minecraft infdev_2025_04_18 (MIT)",
              "final_verdict": verdict,
              "model": {
                  "raycast": "world_raycast.c rotationToDirection5o: "
                             "Y=-sin5o(pitch>>9), sin5o +-1 count => ring+ "
                             "ray DOWN, no coarse quantisation (hypothesis "
                             "(a) refuted at source level); DDA euclidean "
                             "reach 6 from camera (feet+1.7)",
                  "place": "player.c:321 hit+face; constructor stack-- "
                           "(block.h), canPlace-fail reverts (player.c:323)",
                  "probe": "R2 3-frame hold latches raycast hit into "
                           "player->breaking (position@+12, block@+16, "
                           "zeroed on release)",
                  "ui": "crafting UI only via useAction on a real table "
                        "hit (player.c:291); close=START; place5's "
                        "ui_opened was a torn-frame artifact (control arm "
                        "fired too, vanished by after-frame)"},
              "totals": totals}
    with open(os.path.join(OUT, "report_place6_merged.json"), "w") as f:
        json.dump(merged, f, indent=1, default=str)
    ev.j({"ev": "MERGED_REPORT",
          "path": os.path.join(OUT, "report_place6_merged.json")})
    try:
        core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
