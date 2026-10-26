#!/usr/bin/env python3
"""psxmc_r7_place2.py — Task 17-b round-7, run 2 (corrected place ladder).

Run-1 (report_main.json) honest negatives + fixes applied here:
  1. held_word was sampled BEFORE the L2 tap -> now sampled mid-hold.
  2. pitch restore used an averaged single rate (measured B 18432 vs X
     21504 raw/f) leaving a ~9 deg residual, and the look-down ladder was
     only 5.5-22 deg deep (raycast landed beyond the 6-block reach or
     wrapped) -> now CLOSED-LOOP aim/restore on the live pitch counter
     (P+0x18) with per-direction rates from a same-spot quantum probe.
  3. hotbar selected_slot scan window was 0x20 (struct starts with inline
     strings "hotbar", "/tmp/.../hotbar.c") -> now scans 0x80.
  4. dig aim now closed-loop at 35 deg below horizon.

One beetle boot per process. Evidence: scratch/issue6_round7_psxmc/
"""
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from psxmc_r7_lib import (A_INPUT, A_PLAYER, Evid, PADBUFF_SIG,  # noqa
                          changed_px, idle_window, madiff, sha, words_changed)

CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r7"
OUT = os.path.join(REPO, "scratch", "issue6_round7_psxmc")
TAG = "main2"

PITCH_MOD = 1 << 24
STACK_DECLS = ((26, 25), (25, 24), (10, 9), (9, 8), (24, 23))
HUD_BAND = [56, 208, 264, 240]
DEG = PITCH_MOD // 360


def s32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def snap(m):
    return bytes(m.snapshot())


def player_ptr(m):
    v = m.u32(A_PLAYER)
    if (v & 3) == 0 and 0x10000 < (v & 0x1FFFFF) < 0x1F8000:
        y = s32(m.u32((v & 0x1FFFFF) + 4))
        if abs(y) < 40 * 286720 * 4:
            return v & 0x1FFFFF
    return None


def held_word(m):
    return {"stat": m.u8(A_INPUT), "id": hex(m.u8(A_INPUT + 1)),
            "held": hex((~m.u16(A_INPUT + 2)) & 0xFFFF)}


def ram_churn(p, frames=20):
    a = snap(p.mem)
    p.core.run(frames)
    return words_changed(a, snap(p.mem))


def pos_of(m, P):
    return [s32(m.u32(P)), s32(m.u32(P + 4)), s32(m.u32(P + 8))]


def dist_from(a, b):
    return (abs(a[0] - b[0]) + abs(a[2] - b[2])) / 286720.0


def pitch_diff(a, b):
    return (b - a + (PITCH_MOD >> 1)) % PITCH_MOD - (PITCH_MOD >> 1)


def stack_decrement(pre, post):
    a4 = np.frombuffer(pre, "<u4")
    b4 = np.frombuffer(post, "<u4")
    for j in np.nonzero(a4 != b4)[0]:
        for sh in (0, 16):
            pair = (int((a4[j] >> sh) & 0xFFFF), int((b4[j] >> sh) & 0xFFFF))
            if pair in STACK_DECLS:
                return {"addr": hex(int(j) * 4 + sh // 8),
                        "before": pair[0], "after": pair[1], "width": "u16"}
        pair = (int(a4[j]), int(b4[j]))
        if pair in STACK_DECLS:
            return {"addr": hex(int(j) * 4), "before": pair[0],
                    "after": pair[1], "width": "u32"}
    return None


def look_adjust(m, core, P, pitch0, target_raw, r_down, r_up,
                tol=DEG // 4, max_it=6):
    """CLOSED-LOOP look on the live pitch counter (P+0x18).
    B increases pitch (LOOK_DOWN, player.c:434), X decreases (LOOK_UP).
    Returns landing record incl. residual to the exact target.
    Frame-bounded: per-iteration |n| <= 200, total extra frames <= 1200."""
    want = (pitch0 + target_raw) % PITCH_MOD
    coarse = 0
    if target_raw:
        n = int(round(target_raw / max(r_down, 1.0)))
        n = max(0, min(n, 900))
        if n:
            core.run(n, {"B"})
            coarse = n
    cur = s32(m.u32(P + 0x18))
    res = pitch_diff(want, cur)
    it = 0
    spent = 0
    last = None
    while abs(res) > tol and it < max_it and spent < 1200:
        n = int(round(res / (r_down if res > 0 else max(r_up, 1.0))))
        if n == 0:
            n = 1 if res > 0 else -1
        n = max(-200, min(200, n))
        core.run(abs(n), {"B" if n > 0 else "X"})
        spent += abs(n)
        cur = s32(m.u32(P + 0x18))
        res = pitch_diff(want, cur)
        if last is not None and abs(res) >= abs(last):
            it += 1                      # oscillation guard
        else:
            last = res
        it += 1
    return {"coarse_frames": coarse, "fine_iters": it, "pitch": cur,
            "residual_raw": int(res), "exact": res == 0,
            "residual_deg": round(res / DEG, 3)}


def guarded_walk(p, m, P, pos0, frames, btn="UP", max_dist=3.5):
    a = pos_of(m, P)
    p.core.run(frames, {btn})
    p.core.run(8, set())
    b = pos_of(m, P)
    d = dist_from(b, pos0)
    out = {"btn": btn, "frames": frames,
           "delta_blocks": [round((b[i] - a[i]) / 286720.0, 2)
                            for i in (0, 1, 2)],
           "dist_from_spawn_blocks": round(d, 2)}
    if d > max_dist and btn == "UP":
        p.core.run(frames, {"DOWN"})
        p.core.run(8, set())
        out["backpedal"] = {"dist_after":
                            round(dist_from(pos_of(m, P), pos0), 2)}
    return out


def try_place(p, m, core, P, ev, pitch0, angle_deg, r_down, r_up, hold=2):
    """Aim angle_deg below horizon (closed loop), tap L2 (BINDING_USE)."""
    aim = look_adjust(m, core, P, pitch0, angle_deg * DEG, r_down, r_up)
    core.run(4, set())
    f_pre = core.frame_rgb()
    ev.png(f"v2_place_a{angle_deg}_pre", f_pre)
    pre = snap(m)
    core.run(1, {"L2"})
    w_mid = held_word(m)
    core.run(max(0, hold - 1), {"L2"})
    w_mid2 = held_word(m)
    burst = []
    for _ in range(10):
        core.run(2)
        burst.append(madiff(f_pre, core.frame_rgb()))
    core.run(20, set())
    f_post = core.frame_rgb()
    ev.png(f"v2_place_a{angle_deg}_after", f_post)
    post = snap(m)
    cp = changed_px(f_post, f_pre)
    rec = {"angle_deg": angle_deg, "aim": aim, "hold_frames": hold,
           "held_word_l2_mid": w_mid["held"],
           "held_word_l2_mid2": w_mid2["held"],
           "burst_madiff_max": round(max(burst), 3),
           "ram_words_changed": words_changed(pre, post),
           "stack_decrement": stack_decrement(pre, post),
           "changed_px": cp[0], "bbox": cp[1]}
    if cp[0] > 5000 and cp[1] and 40 < cp[1][1] < 200:
        rec["ui_open_suspected"] = True
        core.run(8, {"START"})
        core.run(24, set())
        rec["ui_closed_changed_px"] = changed_px(core.frame_rgb(), f_post)[0]
        ev.j({"ev": "ui_open_closed", "angle_deg": angle_deg})
    rec["restore"] = look_adjust(m, core, P, pitch0, 0, r_down, r_up,
                                 tol=0, max_it=6)
    core.run(6, set())
    return rec


def main():
    ev = Evid(OUT, TAG)
    ev.j({"ev": "start", "cue": CUE, "workspace": WS, "run": 2})
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
    p.wait(150)
    m = p.mem
    core = p.core
    grab = core.frame_rgb
    ev.j({"ev": "world_ready", "P": hex(P),
          "padbuff": snap(m).count(PADBUFF_SIG)})

    # ---------------- baseline ----------------
    f_world = grab()
    ev.png("v2_01_world_render", f_world)
    frames, exact0 = idle_window(core, grab, n=10)
    f_base = frames[0]
    ev.png("v2_02_idle_baseline", f_base)
    churn0 = ram_churn(p, 20)
    ram0 = snap(m)
    pos0 = pos_of(m, P)
    pitch0 = s32(m.u32(P + 0x18))
    hotbar_ptr = m.u32(P + 0x68) & 0x1FFFFF
    ev.step("baseline", {
        "padbuff_hits": snap(m).count(PADBUFF_SIG), "idle_bit_exact": exact0,
        "idle_ram_churn_words_per20f": churn0,
        "pos_blocks": [round(v / 286720, 2) for v in pos0],
        "pitch_raw": pitch0, "hotbar_ptr": hex(hotbar_ptr),
        "ram_sha": sha(ram0)[:16]})

    # -------- same-spot quantum probe + look-loop control ----------------
    core.run(100, {"B"})                      # ~44 deg down, away from wrap
    a = s32(m.u32(P + 0x18))
    core.run(10, {"B"})
    q_down = pitch_diff(a, s32(m.u32(P + 0x18)))
    a = s32(m.u32(P + 0x18))
    core.run(10, {"X"})
    q_up = pitch_diff(a, s32(m.u32(P + 0x18)))
    r_down = q_down / 10.0
    r_up = -q_up / 10.0
    q = {"down_d10f": q_down, "up_d10f": q_up,
         "r_down_raw_per_f": r_down, "r_up_raw_per_f": r_up,
         "symmetric": q_down == -q_up}
    ev.step("pitch_quantum", q)
    # exact return to horizon, then the round-4 look-loop control
    r0 = look_adjust(m, core, P, pitch0, 0, r_down, r_up, tol=0, max_it=8)
    core.run(6, set())
    frames, exact_loop = idle_window(core, grab, n=8)
    loop_cp = changed_px(frames[0], f_base)
    ev.step("look_loop_control", {
        "exact_restore": r0, "idle_bit_exact": exact_loop,
        "vs_boot_baseline": {"madiff": madiff(frames[0], f_base),
                             "changed_px": loop_cp[0], "bbox": loop_cp[1]}})

    # ---------------- PLACE ladder (L2 = BINDING_USE) --------------------
    place = {"attempts": []}
    ok = None
    for ang, hold in ((20, 2), (30, 2), (40, 2), (50, 2),
                      (25, 5), (35, 5), (45, 5)):
        rec = try_place(p, m, core, P, ev, pitch0, ang, r_down, r_up,
                        hold=hold)
        place["attempts"].append(rec)
        ev.j({"ev": "place_attempt", **rec})
        if rec["stack_decrement"] and \
                rec["ram_words_changed"] > churn0 * 3:
            ok = rec
            break
    if ok:
        place["after_static"] = {
            "note": "persistent-change proof = stack_decrement + "
                    "ram_words_changed + changed_px vs pre (run-1 style "
                    "after-window self-consistency below)",
            "idle_bit_exact": None}
        core.run(ok["aim"]["coarse_frames"], {"B"})
        core.run(4, set())
        f_chk = grab()
        frames, ex_a = idle_window(core, grab, n=8)
        place["after_static"]["idle_bit_exact"] = ex_a
        place["after_static"]["self_madiff"] = madiff(frames[0], f_chk)
        ev.png("v2_05_place_after_static", frames[0])
        look_adjust(m, core, P, pitch0, 0, r_down, r_up, tol=0, max_it=8)
        core.run(6, set())
    ev.step("place_causality", place)

    # ---------------- hotbar select (L3/R3) + START control --------------
    hot = {}
    f_hb = grab()
    sel0 = snap(m)[hotbar_ptr:hotbar_ptr + 0x80]
    core.run(2, {"R3"})
    w_r3 = held_word(m)
    core.run(16, set())
    f_next = grab()
    ev.png("v2_06_hotbar_next", f_next)
    sel1 = snap(m)[hotbar_ptr:hotbar_ptr + 0x80]
    sel_addr = next((hex(hotbar_ptr + off) for off in range(0x80)
                     if sel0[off] == 0 and sel1[off] == 1), None)
    cp_next = changed_px(f_next, f_hb)
    core.run(2, {"L3"})
    core.run(16, set())
    f_prev = grab()
    ev.png("v2_07_hotbar_prev", f_prev)
    sel2 = snap(m)[hotbar_ptr:hotbar_ptr + 0x80]
    sel_addr2 = next((hex(hotbar_ptr + off) for off in range(0x80)
                      if sel2[off] == 0 and sel1[off] == 1), None)
    cp_prev = changed_px(f_prev, f_next)
    hot["next"] = {"held_word_r3": w_r3["held"], "selected_byte": sel_addr,
                   "changed_px": cp_next[0], "bbox": cp_next[1],
                   "bbox_in_hud_band": bool(cp_next[1]) and
                   cp_next[1][0] >= HUD_BAND[0] and
                   cp_next[1][2] <= HUD_BAND[2] and
                   cp_next[1][1] >= HUD_BAND[1]}
    hot["prev"] = {"selected_byte": sel_addr2,
                   "changed_px": cp_prev[0], "bbox": cp_prev[1]}
    core.run(8, {"START"})
    core.run(24, set())
    f_inv = grab()
    ev.png("v2_08_inventory_open", f_inv)
    cp_inv = changed_px(f_inv, f_prev)
    core.run(8, {"START"})
    core.run(24, set())
    f_closed = grab()
    hot["start_inventory"] = {
        "open": {"changed_px": cp_inv[0], "bbox": cp_inv[1]},
        "closed_again": {"changed_px": changed_px(f_closed, f_inv)[0]}}
    ev.step("hotbar_inventory", hot)

    # ---------------- structure: places #2 and #3 ------------------------
    struct = {"placements": []}
    if ok:
        struct["placements"].append(
            {"n": 1, "angle_deg": ok["angle_deg"],
             "stack_decrement": ok["stack_decrement"],
             "ram_words_changed": ok["ram_words_changed"],
             "changed_px": ok["changed_px"]})
        for n in (2, 3):
            w = guarded_walk(p, m, P, pos0, 30, "UP")
            rec = try_place(p, m, core, P, ev, pitch0, ok["angle_deg"],
                            r_down, r_up)
            rec.update({"n": n, "walk": w})
            struct["placements"].append(rec)
            ev.j({"ev": "structure_place", **rec})
        core.run(50, {"DOWN"})
        core.run(10, set())
        if dist_from(pos_of(m, P), pos0) > 3.5:
            core.run(40, {"UP"})
            core.run(6, set())
        ev.png("v2_11_structure_wide", grab())
    ev.step("structure", struct)

    # ---------------- dig A/B discrimination (R2, bounded) ---------------
    dig = {}
    p.save_state("v2_pre_dig")
    aim_dig = look_adjust(m, core, P, pitch0, 35 * DEG, r_down, r_up)
    core.run(4, set())
    f_dig0 = grab()
    ev.png("v2_12_dig_before", f_dig0)
    pre = snap(m)
    brk = []
    w_r2 = None
    for _ in range(4):
        core.run(60, {"R2"})
        w_r2 = held_word(m)["held"]
        brk.append(any(snap(m)[P + 0x6C:P + 0x9C]))
    core.run(30, set())
    f_dig1 = grab()
    ev.png("v2_13_dig_after", f_dig1)
    post = snap(m)
    cp_dig = changed_px(f_dig1, f_dig0)
    dig.update({"aim": aim_dig, "held_word_r2_mid": w_r2,
                "breaking_churn_seen": any(brk), "brk_series": brk,
                "ram_words_changed": words_changed(pre, post),
                "changed_px": cp_dig[0], "bbox": cp_dig[1]})
    pz_h = pos_of(m, P)
    f_h0 = grab()
    core.run(15, {"UP"})
    core.run(6, set())
    dig["input_alive_after_dig"] = pos_of(m, P) != pz_h
    dig["liveness_frame_changed_px"] = changed_px(grab(), f_h0)[0]
    dig["halt_detected"] = not dig["input_alive_after_dig"]
    if dig["halt_detected"]:
        p.load_state("v2_pre_dig")
        dig["restored_pre_dig"] = True
        ev.j({"ev": "dig_halt_restored"})
    look_adjust(m, core, P, pitch0, 0, r_down, r_up, tol=0, max_it=8)
    ev.step("dig_discrimination", dig)

    # ---------------- savestate round-trip on the BUILT world ------------
    sv = {}
    core.run(60, set())
    f_saved = grab()
    ev.png("v2_14_pre_save", f_saved)
    core.run(1)
    f_saved1 = grab()
    ram_saved = snap(m)
    ev.j({"ev": "save_state_call", "api": "p.save_state('v2_built')",
          "ram_sha": sha(ram_saved)[:16]})
    p.save_state("v2_built")
    # MORE edits: one place (L2) and one bounded dig (R2)
    w7 = guarded_walk(p, m, P, pos0, 30, "UP")
    aim7 = look_adjust(m, core, P, pitch0, ok["angle_deg"] * DEG,
                       r_down, r_up) if ok else {"coarse_frames": 0}
    core.run(4, set())
    pre = snap(m)
    core.run(2, {"L2"})
    for _ in range(10):
        core.run(2)
    core.run(20, set())
    post = snap(m)
    ev.png("v2_15_post_edit_place", grab())
    e1 = {"kind": "place", "ram_words_changed": words_changed(pre, post),
          "stack_decrement": stack_decrement(pre, post), "walk": w7,
          "aim": aim7}
    pre = snap(m)
    for _ in range(2):
        core.run(60, {"R2"})
    core.run(30, set())
    post = snap(m)
    e2 = {"kind": "dig", "ram_words_changed": words_changed(pre, post)}
    look_adjust(m, core, P, pitch0, 0, r_down, r_up, tol=0, max_it=8)
    core.run(40, set())
    ram_after = snap(m)
    sv["post_edit"] = {"edits": [e1, e2],
                       "ram_sha": sha(ram_after)[:16],
                       "ram_differs_from_saved":
                       sha(ram_after) != sha(ram_saved)}
    ev.j({"ev": "load_state_call", "api": "p.load_state('v2_built')"})
    p.load_state("v2_built")
    ram_rest = snap(m)
    f_rest = grab()
    ev.png("v2_16_post_restore", f_rest)
    core.run(1)
    f_rest1 = grab()
    sv["round_trip"] = {
        "api_save": "PS1Play.save_state -> StateManager.save -> core.serialize()",
        "api_load": "PS1Play.load_state -> StateManager.load -> core.unserialize()",
        "ram_sha_saved": sha(ram_saved)[:16],
        "ram_sha_restored": sha(ram_rest)[:16],
        "ram_bit_exact": sha(ram_rest) == sha(ram_saved),
        "frame_madiff_immediate": madiff(f_rest, f_saved),
        "frame_bit_exact_t": bool(np.array_equal(f_rest, f_saved)),
        "frame_bit_exact_t1": bool(np.array_equal(f_rest1, f_saved1))}
    # functional re-edit: the restored built world accepts the same place
    aim8 = look_adjust(m, core, P, pitch0, ok["angle_deg"] * DEG,
                       r_down, r_up) if ok else {"coarse_frames": 0}
    core.run(4, set())
    pre2 = snap(m)
    core.run(2, {"L2"})
    for _ in range(10):
        core.run(2)
    core.run(20, set())
    post2 = snap(m)
    ev.png("v2_17_post_restore_edit", grab())
    sv["post_restore_edit"] = {
        "aim": aim8, "ram_words_changed": words_changed(pre2, post2),
        "stack_decrement": stack_decrement(pre2, post2)}
    frames, ex_fin = idle_window(core, grab, n=8)
    sv["final_idle_bit_exact"] = ex_fin
    ev.step("savestate_round_trip", sv)

    # ---------------- totals ---------------------------------------------
    ram_end = snap(m)
    n_places = sum(1 for r in struct["placements"]
                   if r.get("stack_decrement"))
    totals = {
        "persistent_place_events": n_places,
        "sum_changed_px_persistent_events": sum(
            r.get("changed_px") or 0 for r in struct["placements"]),
        "dig_persistent": (not dig["halt_detected"]) and
                          dig["ram_words_changed"] > churn0 * 3 and
                          (dig["changed_px"] or 0) > 0,
        "ram_words_changed_vs_boot": words_changed(ram0, ram_end),
        "idle_ram_churn_words_per20f": churn0,
        "world_sha_final": sha(ram_end)[:16]}
    ev.step("totals", totals)

    rt_ok = sv["round_trip"]["ram_bit_exact"] and \
        sv["round_trip"]["frame_bit_exact_t1"]
    if n_places >= 3 and rt_ok:
        verdict = "GAMEPLAY_CONFIRMED+CAUSAL"
    elif n_places >= 1 and rt_ok:
        verdict = "GAMEPLAY_CONFIRMED+CAUSAL(min structure <3)"
    elif n_places >= 1:
        verdict = "STATE_CHANGE_CONFIRMED"
    else:
        verdict = "INCONCLUSIVE"
    ev.finish(verdict)
    try:
        core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
