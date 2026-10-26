#!/usr/bin/env python3
"""psxmc_r8_place5.py — Task 8-b (Round 8, Issue #6): ONE VISIBLE world
placement in PSX-Minecraft (infdev_2025_04_18, MIT).

Round-7 record (commit a0d07d0, report_place4.json): USE taps consume the
selected stack 26->25->24->23 @0x7cda0 (ItemID 58 CRAFTING_TABLE context) —
CAUSAL — but ZERO visible placements (world_px 0 in every attempt); attempt
3's later raycast hit a placed table (ui_px 36852) proving the world WAS
edited out of frame.

NEW SOURCE LEVER this round (upstream clone read at the release tag):
  * src/game/world/world_raycast.c: worldRayCastIntersection aims along
    rotationToDirection5o(&camera->rotation) whose world-space Y component is
    -sin5o(pitch)  ->  pitch ring INCREASE = ray points DOWN.
  * src/core/camera.c:83-87 feeds the same pitch ring into RotMatrix for the
    view matrix; the world direction that projects to screen centre has
    +sin(pitch)  ->  pitch ring INCREASE = camera looks UP.
  => THE CROSSHAIR IS A LIE FOR THE RAYCAST: render and raycast pitch signs
     are OPPOSITE. Round-7 aims of "25-40 deg down" placed blocks 2-4 blocks
     ahead (ray down, t=1.7/sin(p) <= 6 with camera 1.7 blocks above the
     face = PLAYER_CAMERA_OFFSET 487424 over feet-on-surface) while the
     RENDER looked 25-40 deg UP, pushing the new block's elevation span
     (atan(0.7/d)..atan(1.7/d) below horizon) to screen y ~= 270-570 —
     below the 240-line frame. world_px 0 fully explained.
  * Reach: PLAYER_REACH_DISTANCE 6 (player.h:27); placement position =
    raycast hit + face normal (player.c:321); stack consumed in the block
    constructor, reverted by canPlace failure (player.c:324).
  * Placement threshold: t = 1.7/sin(p) <= 6  =>  p >= ~16.5 deg.
  * Visibility (inverted render): at p ~= 16.5-19.5 deg the placed block
    (top atan(0.7/d) ~ 7-8 deg, bottom atan(1.7/d) ~ 17-19 deg below
    horizon) renders at screen y ~= 190-240 — inside the frame just above
    the hotbar HUD band. At p >= ~26 deg it leaves the frame again
    (round-7 anomaly, reproducible on demand).
  * Crafting UI (opened on tick2 after a successful place) is closed by
    BINDING_OPEN_INVENTORY = PAD_START (block_crafting_table.c:200 returns
    INPUT_HANDLER_RELINQUISH). CIRCLE = BINDING_LOOK_RIGHT (bindings.c) —
    NOT a UI-back button; the "CIRCLE/BACK semantics" hypothesis from the
    mission brief is source-refuted. Recovery keeps START single-frame taps
    (place4 technique) with a CIRCLE attempt only as a logged fallback.

Plan: boot -> baseline -> render-convention pixel probe -> CONTROL arm
(ring +7.5 deg: ray t=13 > reach 6, expect NO stack change, proving the
sensor chain) -> graduated USE ladder (15.5/17.5/19.5/22/25 deg): each tap
is 1 frame of L2 (BINDING_USE); read stack @0x7cda0 + ItemID-context scan
in the same tick window; capture UI frame; close UI; capture clean
after-frame; diff metrics (world_px outside HUD, changed px inside the
expected block window) + diff-heatmap PNG. Post-success: OFF-FRAME
reproduction at 30 deg (expect stack decrement with world_px ~= 0) to
close the round-7 anomaly with numbers. Verdict vocabulary is honest.

ONE beetle boot per process. Evidence: scratch/issue6_round8_psxmc/.
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
WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r8"
OUT = os.path.join(REPO, "scratch", "issue6_round8_psxmc")
TAG = "place5"

PITCH_MOD = 1 << 24
DEG = PITCH_MOD / 360.0
ONE_BLOCK = 286720
T_MAX = 420.0
ITEMID_CRAFTING_TABLE = 58
STACK_ADDR = 0x7CDA0                    # live-verified r7 (26->25 chain)
HUD_BAND = (56, 208, 264, 240)          # x0,y0,x1,y1 hotbar band (place4)

LOOK_DOWN = "B"        # PAD_CROSS: ring + (player.c:435)
LOOK_UP = "X"          # PAD_TRIANGLE: ring -
PLACE_BTN = "L2"       # BINDING_USE (bindings.c:21)
UI_BTN = "START"       # BINDING_OPEN_INVENTORY: closes crafting UI
LOOK_RIGHT = "O"       # PAD_CIRCLE: yaw- fallback only (NOT a UI close)

# expected visible-block window under the INVERTED-render model
BLOCK_WIN_INV = (128, 182, 192, 240)    # x0,y0,x1,y1 (bottom band)
BLOCK_WIN_DIR = (128, 80, 192, 140)     # if render turns out NOT inverted
EDGE_THR = 3.0                          # row edge-energy threshold


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


def deg_of(m, P, pitch0):
    return ((pitch_now(m, P) - pitch0) % PITCH_MOD) / DEG


def words_changed_ram(a, b):
    return int(np.count_nonzero(
        np.frombuffer(a, "<u4") != np.frombuffer(b, "<u4")))


# ---------------- pixel sensors -------------------------------------------
def edge_energy(f):
    """Per-pixel luminance gradient magnitude (texture energy)."""
    L = (0.299 * f[..., 0].astype(np.float32)
         + 0.587 * f[..., 1].astype(np.float32)
         + 0.114 * f[..., 2].astype(np.float32))
    e = np.zeros(L.shape, np.float32)
    e[:, :-1] += np.abs(L[:, 1:] - L[:, :-1])
    e[:-1, :] += np.abs(L[1:] - L[:-1])
    return e


def ground_stats(f):
    """(ground_rows, bottom_half_energy_share, row_energy_quartiles)."""
    e = edge_energy(f)
    rm = e.mean(axis=1)
    grows = int((rm > EDGE_THR).sum())
    bot = float(e[120:].mean())
    top = float(e[:120].mean())
    share = bot / (bot + top + 1e-6)
    q = [round(float(np.percentile(rm, p)), 2) for p in (10, 50, 90)]
    return {"ground_rows": grows, "bottom_energy": round(bot, 2),
            "top_energy": round(top, 2), "bottom_share": round(share, 3),
            "row_q": q}


def region_energy(f, box):
    x0, y0, x1, y1 = box
    return round(float(edge_energy(f)[y0:y1, x0:x1].mean()), 2)


def diff_metrics(a, b, block_win):
    """Mask-based diff: total, outside-HUD (world), inside block window."""
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
            "max_d": int(d.max()),
            "hud_px": int((mask & hud).sum())}


def save_heat(ev, name, a, b, block_win):
    """Red heatmap of (b-a) over a dimmed 'before' frame + window outlines."""
    d = np.abs(a.astype(np.int16) - b.astype(np.int16)).max(axis=2)
    mask = d > 2
    ov = (a.astype(np.float32) * 0.30).astype(np.uint8)
    ov[..., 0][mask] = 255
    ov[..., 1][mask] = 96
    ov[..., 2][mask] = 32
    for (x0, y0, x1, y1), col in ((block_win, (255, 255, 0)),
                                  (HUD_BAND, (0, 160, 255)),
                                  ((140, 100, 180, 140), (0, 255, 0))):
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


# ---------------- aim / control --------------------------------------------
def aim_ring_exact(core, m, P, pitch0, want_deg, tol_deg=0.35, max_it=400):
    """Closed-loop ring aim: hold LOOK 1-5 frames at a time and re-read the
    live pitch ring — rate-model-free (round-7's asymmetric-rate residuals
    came from open-loop frame-count arithmetic). Bails out if the residual
    stops improving for 3 consecutive iterations (oscillation guard)."""
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
    """place4 recovery: 6-frame LOOK_DOWN probe must move the ring; else
    single-frame START taps (>200 ms apart) toggle the focused UI layer.
    CIRCLE (LOOK_RIGHT) is tried once as a logged fallback (source says it
    cannot close the crafting UI; kept because the mission asked)."""
    rec = {"rounds": 0, "alive": False, "start_taps": 0, "circle_tried": 0}
    for rnd in range(4):
        a = pitch_now(m, P)
        core.run(6, {LOOK_DOWN})
        moved = abs(ring_diff(a, pitch_now(m, P))) > 0.2 * DEG
        core.run(2, set())
        rec["rounds"] = rnd + 1
        if moved:
            rec["alive"] = True
            break
        btn = UI_BTN if rec["circle_tried"] == 0 or rnd % 2 == 0 else LOOK_RIGHT
        if btn == LOOK_RIGHT:
            rec["circle_tried"] += 1
        else:
            rec["start_taps"] += 1
        core.run(1, {btn})
        core.run(18, set())
    ev.j({"ev": f"world_control_{tag}", **rec})
    return rec


def stack_scan(pre, post, pairs=((26, 25), (25, 24), (24, 23), (23, 22),
                                 (22, 21), (21, 20), (10, 9))):
    """place4 scanner: any byte va->vb with ItemID 58 among the 4 preceding
    words (CRAFTING_TABLE stack slots)."""
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


# ---------------- one place attempt ----------------------------------------
def use_attempt(p, m, P, ev, pitch0, pdeg, label, block_win,
                close_ui=True):
    """Aim ring +pdeg (ray down pdeg), 1-frame L2 tap, read sensors in the
    same tick window, close the crafting UI, capture clean after-frame."""
    core, grab = p.core, p.core.frame_rgb
    ctrl = ensure_world_control(core, m, P, ev, f"pre_{label}")
    aim = aim_ring_exact(core, m, P, pitch0, pdeg)
    core.run(4, set())
    f_pre = grab()
    ev.png(f"r8_{label}_pre", f_pre)
    pre_gs = ground_stats(f_pre)
    pre = snap(m)
    stack_before = int(m.u8(STACK_ADDR))
    ev.j({"ev": f"tap_{label}", "pdeg": pdeg, "aim": aim,
          "stack_before": stack_before, "pre_ground": pre_gs,
          "held": held_word(m)})
    core.run(1, {PLACE_BTN})
    core.run(2, set())
    post = snap(m)
    stack_after = int(m.u8(STACK_ADDR))
    f_ui = grab()
    ev.png(f"r8_{label}_ui", f_ui)
    ui_m = diff_metrics(f_pre, f_ui, block_win)
    hits = stack_scan(pre, post)
    ui_opened = ui_m["changed_px"] > 12000
    rec = {"label": label, "pdeg": pdeg, "aim": aim, "ctrl_pre": ctrl,
           "stack_before": stack_before, "stack_after": stack_after,
           "stack_delta": stack_before - stack_after,
           "stack_hits": hits, "ui_opened": ui_opened, "ui_metrics": ui_m}
    if ui_opened or not ctrl["alive"]:
        rec["recovery"] = ensure_world_control(core, m, P, ev,
                                               f"post_{label}")
    if close_ui and (ui_opened or not ctrl["alive"]):
        core.run(6, set())
    f_after = grab()
    ev.png(f"r8_{label}_after", f_after)
    am = diff_metrics(f_pre, f_after, block_win)
    save_heat(ev, f"r8_{label}_heat", f_pre, f_after, block_win)
    save_pair(ev, f"r8_{label}_pair", f_pre, f_after)
    rec["after_metrics"] = am
    rec["after_ground"] = ground_stats(f_after)
    rec["win_energy_pre"] = region_energy(f_pre, block_win)
    rec["win_energy_after"] = region_energy(f_after, block_win)
    rec["placed"] = bool(hits)
    rec["visible"] = bool(hits) and am["world_px"] > 0 and \
        am["win_px"] > 0
    ev.j({"ev": f"attempt_{label}",
          **{k: rec[k] for k in ("pdeg", "stack_before", "stack_after",
                                 "stack_delta", "placed", "visible",
                                 "ui_opened")},
          "hits": hits, "after": am})
    return rec


def main():
    ev = Evid(OUT, TAG)
    ev.jpath = os.path.join(OUT, f"r8_{TAG}.jsonl")   # round-8 journal name
    ev.j({"ev": "start", "cue": CUE, "workspace": WS,
          "task": "8-b place5", "model": "render/raycast pitch-sign "
          "inversion (camera.c:83 RotMatrix vs world_raycast.c "
          "rotationToDirection5o); reach 6; camera h=1.7 over face"})
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
    stack0 = int(m.u8(STACK_ADDR))
    f_world = grab()
    ev.png("r8_01_world_pitch0", f_world)
    gs0 = ground_stats(f_world)
    frames, exact0 = idle_window(core, grab, n=8)
    ev.png("r8_01b_idle", frames[0])
    ram0 = snap(m)
    ev.step("baseline", {
        "P": hex(P), "pos_blocks": [round(v / ONE_BLOCK, 2) for v in pos0],
        "pitch0_raw": pitch0, "stack_0x7cda0": stack0,
        "ground_stats": gs0, "idle_bit_exact": exact0,
        "padbuff": snap(m).count(PADBUFF_SIG), "ram_sha": sha(ram0)[:16]})

    # ------------- render-convention probe --------------------------------
    core.run(38, {LOOK_DOWN})                 # ring + ~15 deg
    core.run(2, set())
    f_ringp = grab()
    ev.png("r8_02_ring_plus15", f_ringp)
    gs_ringp = ground_stats(f_ringp)
    back1 = aim_ring_exact(core, m, P, pitch0, 0.0)
    core.run(4, set())
    core.run(38, {LOOK_UP})                   # ring - ~15 deg
    core.run(2, set())
    f_ringm = grab()
    ev.png("r8_03_ring_minus15", f_ringm)
    gs_ringm = ground_stats(f_ringm)
    back2 = aim_ring_exact(core, m, P, pitch0, 0.0)
    core.run(4, set())
    g0r, gpr, gmr = (gs0["ground_rows"], gs_ringp["ground_rows"],
                     gs_ringm["ground_rows"])
    if gpr < g0r - 15 and gmr > g0r + 15:
        convention = "INVERTED (ring+ = camera UP; raycast DOWN)"
        block_win = BLOCK_WIN_INV
    elif gpr > g0r + 15 and gmr < g0r - 15:
        convention = "DIRECT (ring+ = camera DOWN; matches raycast)"
        block_win = BLOCK_WIN_DIR
    else:
        convention = "UNCLEAR (ladder stays outcome-driven)"
        block_win = BLOCK_WIN_INV
    ev.step("render_convention_probe", {
        "pitch0": gs0, "ring_plus15": gs_ringp, "ring_minus15": gs_ringm,
        "back_to_0_err_deg": [back1["err_deg"], back2["err_deg"]],
        "convention": convention, "block_win": block_win})

    # ------------- savestate insurance ------------------------------------
    core.run(20, set())
    p.save_state("r8_pre")
    ev.j({"ev": "save_state", "name": "r8_pre"})

    # ------------- CONTROL arm: ray beyond reach ---------------------------
    ctrl_rec = use_attempt(p, m, P, ev, pitch0, 7.5, "control", block_win,
                           close_ui=False)
    ctrl_ok = (not ctrl_rec["placed"]) and ctrl_rec["stack_delta"] == 0 and \
        ctrl_rec["after_metrics"]["world_px"] < 400

    # ------------- USE ladder ---------------------------------------------
    ladder = []
    ok_visible = None
    chain = {}
    for pdeg in (15.5, 17.5, 19.5, 22.0, 25.0):
        if time.time() - ev.t0 > T_MAX - 120:
            ev.j({"ev": "time_guard_skip", "pdeg": pdeg})
            break
        if ok_visible:
            break
        rec = use_attempt(p, m, P, ev, pitch0, pdeg, f"a{pdeg:g}",
                          block_win)
        ladder.append(rec)
        for h in rec["stack_hits"]:
            prev = chain.setdefault(h["addr"], [])
            prev.append([h["before"], h["after"]])
        if rec["visible"]:
            ok_visible = rec
        if rec["placed"] and not rec["visible"]:
            ev.j({"ev": "placed_not_visible", "pdeg": pdeg,
                  "world_px": rec["after_metrics"]["world_px"],
                  "note": "stack consumed but block not in frame window"})

    # ------------- OFF-FRAME reproduction at 30 deg -----------------------
    off_rec = None
    if ok_visible and time.time() - ev.t0 < T_MAX - 80:
        off_rec = use_attempt(p, m, P, ev, pitch0, 30.0, "off30", block_win)
        ev.j({"ev": "off_frame_repro",
              "placed": off_rec["placed"],
              "stack_delta": off_rec["stack_delta"],
              "world_px": off_rec["after_metrics"]["world_px"]})

    # ------------- final framing + totals ---------------------------------
    aim_end = aim_ring_exact(core, m, P, pitch0, 0.0)
    core.run(6, set())
    ev.png("r8_09_final_horizon", grab())
    ram_end = snap(m)
    stack_end = int(m.u8(STACK_ADDR))
    n_placed = sum(1 for r in ([ctrl_rec] + ladder +
                               ([off_rec] if off_rec else []))
                   if r and r["placed"])
    totals = {
        "convention": convention,
        "control_ok": ctrl_ok,
        "control": {"pdeg": ctrl_rec["pdeg"],
                    "stack_delta": ctrl_rec["stack_delta"],
                    "world_px": ctrl_rec["after_metrics"]["world_px"]},
        "ladder": [{"pdeg": r["pdeg"], "stack_delta": r["stack_delta"],
                    "placed": r["placed"], "visible": r["visible"],
                    "world_px": r["after_metrics"]["world_px"],
                    "win_px": r["after_metrics"]["win_px"],
                    "ui_opened": r["ui_opened"],
                    "bbox": r["after_metrics"]["bbox"]} for r in ladder],
        "off_frame_repro": None if not off_rec else {
            "pdeg": off_rec["pdeg"], "placed": off_rec["placed"],
            "stack_delta": off_rec["stack_delta"],
            "world_px": off_rec["after_metrics"]["world_px"]},
        "visible_placements": 1 if ok_visible else 0,
        "placed_total": n_placed,
        "stack_chain": {k: v for k, v in chain.items()},
        "stack_first_last": [stack0, stack_end],
        "idle_bit_exact_at_start": exact0,
        "ram_words_changed_vs_boot": words_changed_ram(ram0, ram_end),
    }
    ev.step("totals", totals)

    if ok_visible and ctrl_ok:
        verdict = ("CAUSAL(place VISIBLE): stack %d->%d @0x7cda0 with "
                   "world_px %d in the crosshair-region window; control arm "
                   "(ray > reach) left stack untouched"
                   % (ok_visible["stack_before"], ok_visible["stack_after"],
                      ok_visible["after_metrics"]["world_px"]))
    elif ok_visible:
        verdict = "STATE_CHANGE_CONFIRMED(place VISIBLE; control arm dirty)"
    elif ladder and any(r["placed"] for r in ladder):
        chn = {k: v for k, v in chain.items()}
        verdict = (("INCONCLUSIVE(place): stack consumed (chain %s) but "
                    "zero in-frame placements" % chn) if chn else
                   "INCONCLUSIVE(place): stack consumed, zero in-frame")
    elif ctrl_ok:
        verdict = "INCONCLUSIVE(place): no placement in the ladder; control clean"
    else:
        verdict = "FAILED: control arm also anomalous (sensor chain suspect)"
    ev.finish(verdict)

    import json
    merged = {"task": "8-b (round 8 place5)",
              "game": "PSX-Minecraft infdev_2025_04_18 (MIT)",
              "final_verdict": verdict,
              "model": {
                  "raycast": "world_raycast.c: rotationToDirection5o Y = "
                             "-sin5o(pitch) => ring+ ray DOWN",
                  "render": "camera.c:83 -> RotMatrix; screen-centre world "
                            "dir has +sin(pitch) => ring+ camera UP",
                  "reach": "player.h:27 PLAYER_REACH_DISTANCE 6; place at "
                           "hit+face (player.c:321); h=1.7 over face "
                           "(PLAYER_CAMERA_OFFSET 487424)",
                  "ui_close": "block_crafting_table.c:200 "
                              "BINDING_OPEN_INVENTORY(START) -> RELINQUISH; "
                              "CIRCLE=BINDING_LOOK_RIGHT is NOT a UI close"},
              "totals": totals}
    with open(os.path.join(OUT, "report_place5_merged.json"), "w") as f:
        json.dump(merged, f, indent=1, default=str)
    ev.j({"ev": "MERGED_REPORT",
          "path": os.path.join(OUT, "report_place5_merged.json")})
    try:
        core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
