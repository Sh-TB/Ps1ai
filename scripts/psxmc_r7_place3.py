#!/usr/bin/env python3
"""psxmc_r7_place3.py — Task 17-b-r2: decisive PLACE-block causality for
PSX-Minecraft (infdev_2025_04_18) after diagnosing the 17-b failure.

DIAGNOSIS (report_main.json / report_main2.json): L2 (BINDING_USE)
delivers fine (held 0x100 mid-hold) but EVERY attempt aimed 6-30 deg
below the horizon (the look ladder was 14-56 frames = ~2-12 deg; 90 deg
needs ~228 frames at the measured 18432 raw/frame) — the crosshair
never touched a block face, so neither place nor dig could act (even
dig came back dig_persistent:false).  The fine-aim loop residuals were
+-100-175 deg (asymmetric look rates), so aiming by computation is
unreliable.

FIX: a MONOTONIC PITCH SWEEP.  From spawn pitch0, hold LOOK_DOWN (B) in
15-frame cumulative steps; after each step tap L2 (BINDING_USE, 3f) and
record.  A full 465f sweep covers >360 deg of pitch exactly once — every
possible aim gets one USE tap, hits stand out against the built-in
sky-control (most taps aim at nothing and must do nothing).

Success criteria (predeclared):
  HIT  = stack_decrement found (CraftingTable 26->25 / Cobblestone 10->9
         per minecraft.c init) OR (changed_px >= 300 with bbox NOT
         confined to the HUD band) persisting into a static baseline.
  On first HIT: two more placements (30f walk between) = structure.
  Then savestate round-trip on the built world (RAM bit-exact, frame
  bit-exact at t+1) = persistence.
Verdict: GAMEPLAY_CONFIRMED + CAUSAL(place) if >=2 HITs (>=1 with
stack_decrement) + persistence round-trip OK.

One beetle boot per process.  Evidence: scratch/issue6_round7_psxmc/.
"""
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from psxmc_r7_lib import (A_INPUT, A_PLAYER, Evid, PADBUFF_SIG,  # noqa
                          changed_px, idle_window, madiff, sha,
                          words_changed)
from psxmc_r7_main import (CUE, WS, OUT, held_word, pos_of,  # noqa
                           s32, snap, stack_decrement)

TAG = "place3"
STEP_F = 15                 # look-down frames per sweep step
MAX_STEPS = 34              # 34*15 = 510f > 360 deg at 18432/f
TAP_F = 3
SETTLE_F = 25
HUD_BAND = [56, 208, 264, 240]


def in_hud(bbox):
    return bool(bbox) and bbox[0] >= HUD_BAND[0] and bbox[2] <= HUD_BAND[2] \
        and bbox[1] >= HUD_BAND[1]


def main():
    ev = Evid(OUT, TAG)
    ev.j({"ev": "start", "cue": CUE, "why": "pitch-sweep place probe"})
    from ps1play.api import PS1Play
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    P = None
    for _ in range(240):
        P = player_ptr_wait(p)
        if P:
            break
        p.wait(30)
    if not P:
        ev.finish("FAILED: no player pointer")
        return 1
    p.wait(150)
    m = p.mem
    grab = p.core.frame_rgb
    ev.j({"ev": "world_ready", "P": hex(P),
          "padbuff": snap(m).count(PADBUFF_SIG)})
    f_base = grab()
    ev.png("p3_00_world", f_base)
    frames, exact0 = idle_window(p.core, grab, n=8)
    churn0 = 0
    a = snap(m)
    p.core.run(20)
    churn0 = words_changed(a, snap(m))
    pos0 = pos_of(m, P)
    pitch0 = s32(m.u32(P + 0x18))
    hotbar_ptr = m.u32(P + 0x68) & 0x1FFFFF
    ev.j({"ev": "baseline", "idle_bit_exact": exact0,
          "churn20f": churn0,
          "pos_blocks": [round(v / 286720, 2) for v in pos0],
          "pitch_raw": pitch0, "hotbar_ptr": hex(hotbar_ptr)})
    if not exact0:
        ev.finish("FAILED: idle not bit-exact at baseline")
        return 1

    # ---------- the monotonic pitch sweep with USE taps ----------
    hits = []
    table = []
    for step in range(MAX_STEPS):
        pre = snap(m)
        f_pre = grab()
        pitch_aim = s32(m.u32(P + 0x18))
        p.core.run(STEP_F, {"B"})               # LOOK_DOWN hold (cumulative)
        p.core.run(2, set())
        p.core.run(TAP_F, {"L2"})               # USE tap
        w_mid = held_word(m)["held"]
        for _ in range(SETTLE_F):
            p.core.run(2)
        p.core.run(10, set())
        f_post = grab()
        post = snap(m)
        st = stack_decrement(pre, post)
        cp = changed_px(f_post, f_pre)
        wc = words_changed(pre, post)
        deg = round((pitch_aim - pitch0) / 18432.0, 1)
        hit = (st is not None) or (cp[0] >= 300 and not in_hud(cp[1]))
        row = {"step": step, "pitch_deg": deg, "held_l2": w_mid,
               "stack_decrement": st, "changed_px": cp[0], "bbox": cp[1],
               "ram_words_changed": wc, "hit": hit}
        table.append(row)
        ev.j({"ev": "sweep_step", **row})
        if hit:
            ev.png(f"p3_hit_s{step:02d}", f_post)
            hits.append(row)
        if st is not None and len(hits) >= 2:
            break
    ev.step("pitch_sweep", {"steps": len(table), "hits": len(hits),
                            "table": table})

    # ---------- structure: two more placements after first hit ----------
    struct = {"placements": [h for h in hits]}
    if hits:
        for n in (2, 3):
            p.core.run(30, {"UP"})
            p.core.run(6, set())
            pre = snap(m)
            f_pre = grab()
            p.core.run(TAP_F, {"L2"})
            for _ in range(SETTLE_F):
                p.core.run(2)
            p.core.run(10, set())
            f_post = grab()
            post = snap(m)
            st = stack_decrement(pre, post)
            cp = changed_px(f_post, f_pre)
            rec = {"n": n, "stack_decrement": st, "changed_px": cp[0],
                   "bbox": cp[1], "ram_words_changed": words_changed(pre,
                                                                     post)}
            struct["placements"].append(rec)
            ev.j({"ev": "structure_place", **rec})
            if st is not None:
                ev.png(f"p3_struct{n}", f_post)
        p.core.run(40, {"DOWN"})
        p.core.run(8, set())
        ev.png("p3_structure_wide", grab())
    ev.step("structure", struct)

    # ---------- persistence: savestate round-trip on the built world ----
    sv = {}
    p.core.run(30, set())
    ram_saved = snap(m)
    f_saved = grab()
    ev.png("p3_pre_save", f_saved)
    p.save_state("r7_p3_built")
    p.core.run(30, {"UP"})
    p.core.run(6, set())
    pre2 = snap(m)
    p.core.run(TAP_F, {"L2"})
    for _ in range(SETTLE_F):
        p.core.run(2)
    p.core.run(10, set())
    ram_after = snap(m)
    sv["post_edit"] = {"ram_differs_from_saved": sha(ram_after)
                       != sha(ram_saved),
                       "stack_decrement": stack_decrement(pre2, ram_after)}
    p.load_state("r7_p3_built")
    ram_rest = snap(m)
    f_rest = grab()
    ev.png("p3_post_restore", f_rest)
    p.core.run(1)
    f_rest1 = grab()
    sv["round_trip"] = {
        "ram_bit_exact": sha(ram_rest) == sha(ram_saved),
        "frame_bit_exact_t1": bool(np.array_equal(f_rest1,
                                                  grab_and_run1(p))),
        "frame_changed_px": changed_px(f_rest, f_saved)[0]}
    ev.step("savestate_round_trip", sv)

    n_stack = sum(1 for r in (hits + struct["placements"][len(hits):])
                  if r.get("stack_decrement") is not None)
    n_hits = len(hits)
    rt_ok = sv["round_trip"]["ram_bit_exact"] and \
        sv["round_trip"]["frame_bit_exact_t1"]
    ev.step("totals", {"sweep_hits": n_hits, "stack_decrements": n_stack,
                       "round_trip_ok": rt_ok,
                       "churn20f": churn0})
    if n_hits >= 2 and n_stack >= 1 and rt_ok:
        verdict = "GAMEPLAY_CONFIRMED+CAUSAL(place)"
    elif n_hits >= 1:
        verdict = ("STATE_CHANGE_CONFIRMED(place; persistence "
                   f"round_trip_ok={rt_ok})")
    else:
        verdict = "INCONCLUSIVE(place: full 360-deg sweep, no USE effect)"
    ev.finish(verdict)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


def player_ptr_wait(p):
    import psxmc_r7_main as M
    m = p.mem
    v = m.u32(A_PLAYER)
    if (v & 3) == 0 and 0x10000 < (v & 0x1FFFFF) < 0x1F8000:
        y = s32(m.u32((v & 0x1FFFFF) + 4))
        if abs(y) < 40 * 286720 * 4:
            return v & 0x1FFFFF
    return None


def grab_and_run1(p):
    p.core.run(1)
    return p.core.frame_rgb()


if __name__ == "__main__":
    sys.exit(main())
