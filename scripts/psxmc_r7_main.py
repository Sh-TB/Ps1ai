#!/usr/bin/env python3
"""psxmc_r7_main.py — Task 17-b: PSX-Minecraft (infdev_2025_04_18, MIT)
world-modification + persistence causality, ONE beetle boot per process.

Stages:
  0 boot+settle            4 hotbar select causality (L3/R3) + START control
  1 baseline (idle bit-exact, padbuff)   5 build structure (>=3 blocks)
  2 look calibration + look-loop control 6 dig A/B discrimination (R2, bounded)
  3 PLACE causality (L2, upstream BINDING_USE)  7 savestate round-trip

Ground truth quoted from upstream src/core/input/bindings.c @ tag
infdev_2025_04_18:
  WEAK PadButton BINDING_ATTACK = PAD_R2;
  WEAK PadButton BINDING_USE = PAD_L2;
  WEAK PadButton BINDING_PREVIOUS = PAD_L3;
  WEAK PadButton BINDING_NEXT = PAD_R3;
  WEAK PadButton BINDING_OPEN_INVENTORY = PAD_START;
and src/game/entity/player.c playerInputHandlerWorldInteraction():
  if (isPressed(pad, BINDING_ATTACK)) breaking = playerInputHandlerAttack(ctx);
  else if (isPressed(pad, BINDING_USE)) playerInputHandlerUse(ctx);
and src/game/minecraft.c init: hotbar slot0 = CraftingTable x26 (selected),
slot1 = Cobblestone x10 (inventoryFindFreeSlot is hotbar-first).

Evidence: /home/z/my-project/ps1ai/scratch/issue6_round7_psxmc/
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
TAG = "main"

ONE = 4096
FIXED_SHIFT = 12
PITCH_MOD = ONE << FIXED_SHIFT          # positiveModulo full range (2^24)
LOOK_LADDER = [14, 20, 28, 40, 56]      # look-down hold frames per attempt
STACK_DECLS = ((26, 25), (25, 24), (10, 9), (9, 8))
HUD_BAND = [56, 208, 264, 240]          # hotbar strip (hotbar.h: x 64..256,
#                               y = SCREEN_YRES-22-1 = 217..240; padded)


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
    st = m.u8(A_INPUT)
    pid = m.u8(A_INPUT + 1)
    w = m.u16(A_INPUT + 2)
    return {"stat": st, "id": hex(pid), "held": hex((~w) & 0xFFFF)}


def ram_churn(p, frames=20):
    a = snap(p.mem)
    p.core.run(frames)
    b = snap(p.mem)
    return words_changed(a, b)


def pos_of(m, P):
    return [s32(m.u32(P)), s32(m.u32(P + 4)), s32(m.u32(P + 8))]


def dist_from(a, b):
    return (abs(a[0] - b[0]) + abs(a[2] - b[2])) / 286720.0


def pitch_diff(a, b):
    """shortest signed modular distance b-a on the pitch ring."""
    return (b - a + (PITCH_MOD >> 1)) % PITCH_MOD - (PITCH_MOD >> 1)


def stack_decrement(pre, post):
    a4 = np.frombuffer(pre, "<u4")
    b4 = np.frombuffer(post, "<u4")
    for j in np.nonzero(a4 != b4)[0]:
        pair16 = (int(a4[j] & 0xFFFF), int(b4[j] & 0xFFFF))
        if pair16 in STACK_DECLS:
            return {"addr": hex(int(j) * 4), "before": pair16[0],
                    "after": pair16[1], "width": "u16"}
        pair32 = (int(a4[j]), int(b4[j]))
        if pair32 in STACK_DECLS:
            return {"addr": hex(int(j) * 4), "before": pair32[0],
                    "after": pair32[1], "width": "u32"}
    return None


def look_restore(p, m, P, pitch0, rate, LOOK_DOWN, LOOK_UP, cap=400):
    d = pitch_diff(pitch0, s32(m.u32(P + 0x18)))    # current - spawn
    n = int(round(-d / rate)) if rate else 0
    n = max(-cap, min(cap, n))
    if n > 0:
        p.core.run(n, {LOOK_UP})
    elif n < 0:
        p.core.run(-n, {LOOK_DOWN})
    p.core.run(8, set())
    return s32(m.u32(P + 0x18))


def guarded_walk(p, m, P, pos0, frames, btn="UP", max_dist=3.5):
    """walk `frames` with btn, backpedal if farther than max_dist blocks."""
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
        c = pos_of(m, P)
        out["backpedal"] = {"frames": frames,
                            "dist_after": round(dist_from(c, pos0), 2)}
    return out


def main():
    ev = Evid(OUT, TAG)
    ev.j({"ev": "start", "cue": CUE, "workspace": WS})
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
    grab = p.core.frame_rgb
    ev.j({"ev": "world_ready", "P": hex(P),
          "padbuff": snap(m).count(PADBUFF_SIG)})

    # ---------------- stage 1: baseline ----------------
    f_world = grab()
    ev.png("01_world_render", f_world)
    frames, exact0 = idle_window(p.core, grab, n=10)
    f_base = frames[0]
    ev.png("02_idle_baseline", f_base)
    churn0 = ram_churn(p, 20)
    ram0 = snap(m)
    pos0 = pos_of(m, P)
    pitch0 = s32(m.u32(P + 0x18))
    yaw0 = s32(m.u32(P + 0x1C))
    hotbar_ptr = m.u32(P + 0x68) & 0x1FFFFF
    ev.step("baseline", {
        "world_render": True, "padbuff_hits": snap(m).count(PADBUFF_SIG),
        "idle_bit_exact": exact0,
        "idle_ram_churn_words_per20f": churn0,
        "pos_blocks": [round(v / 286720, 2) for v in pos0],
        "pitch_raw": pitch0, "yaw_raw": yaw0,
        "hotbar_ptr": hex(hotbar_ptr), "ram_sha": sha(ram0)[:16]})

    # ------------- stage 2: look-button matrix + pitch calibration ------
    # Only LOOK buttons here: USE/ATTACK are level-triggered every frame
    # (player.c:389-397) so L2/R2 words are recorded at their use sites.
    matrix = {}
    for name in ("X", "TR", "B", "Y", "O"):
        p.core.run(8, {name})
        matrix[name] = held_word(m)["held"]
        p.core.run(6, set())
    pitch = {}
    for name in ("X", "B", "TR"):
        a = s32(m.u32(P + 0x18))
        p.core.run(20, {name})
        pitch[name] = {"d20f": pitch_diff(a, s32(m.u32(P + 0x18)))}
        p.core.run(8, set())
    cands = {k: v["d20f"] for k, v in pitch.items() if v["d20f"] != 0}
    LOOK_DOWN = max(cands, key=lambda k: cands[k]) if cands else "B"
    up_c = {k: v for k, v in cands.items() if k != LOOK_DOWN}
    LOOK_UP = max(up_c, key=lambda k: up_c[k]) if up_c else "X"
    rate = pitch[LOOK_DOWN]["d20f"] / 20.0
    p_after = look_restore(p, m, P, pitch0, rate, LOOK_DOWN, LOOK_UP)
    frames, exact_loop = idle_window(p.core, grab, n=8)
    loop_cp = changed_px(frames[0], f_base)
    ev.step("input_matrix", {
        "held_words": matrix, "pitch_d20f": pitch,
        "look_down_btn": LOOK_DOWN, "look_up_btn": LOOK_UP,
        "pitch_raw_per_frame": rate, "pitch_after_restore": p_after})
    ev.step("look_loop_control", {
        "idle_bit_exact_after_look": exact_loop,
        "vs_boot_baseline": {"madiff": madiff(frames[0], f_base),
                             "changed_px": loop_cp[0], "bbox": loop_cp[1]}})

    # ---------------- stage 3: PLACE causality (L2 = BINDING_USE) -------
    hbwin = snap(m)[hotbar_ptr:hotbar_ptr + 0x40]
    ev.j({"ev": "hotbar_window", "hex": hbwin.hex()})
    place = {"attempts": [], "note": "hotbar slot0=CraftingTable x26 "
             "selected at spawn (minecraft.c:155-159)"}
    ok = None
    f_pre = None
    for i, k in enumerate(LOOK_LADDER):
        p.core.run(k, {LOOK_DOWN})
        p.core.run(4, set())
        pitch_aim = s32(m.u32(P + 0x18))
        f_pre = grab()
        ev.png(f"03_place{i+1}_pre", f_pre)
        pre = snap(m)
        w_pre = held_word(m)
        p.core.run(1, {"L2"})                       # 1-frame USE tap
        burst = []
        for _ in range(10):
            p.core.run(2)
            burst.append(madiff(f_pre, grab()))
        p.core.run(20, set())
        f_post = grab()
        ev.png(f"04_place{i+1}_after", f_post)
        post = snap(m)
        wc = words_changed(pre, post)
        st = stack_decrement(pre, post)
        cp = changed_px(f_post, f_pre)
        att = {"attempt": i + 1, "lookdown_frames": k,
               "pitch_raw": pitch_aim, "held_word_l2": w_pre["held"],
               "burst_madiff_max": round(max(burst), 3),
               "burst_madiff_series": [round(b, 3) for b in burst],
               "ram_words_changed": wc, "stack_decrement": st,
               "changed_px": cp[0], "bbox": cp[1]}
        place["attempts"].append(att)
        ev.j({"ev": "place_attempt", **att})
        if st is not None and wc > churn0 * 3:
            ok = att
            break
        look_restore(p, m, P, pitch0, rate, LOOK_DOWN, LOOK_UP)
    if ok:
        frames, exact_after = idle_window(p.core, grab, n=8)
        after_cp = changed_px(frames[0], f_pre)
        place["after_static"] = {
            "idle_bit_exact": exact_after,
            "vs_pre_place": {"madiff": madiff(frames[0], f_pre),
                             "changed_px": after_cp[0], "bbox": after_cp[1]}}
        ev.png("05_place_after_static", frames[0])
        look_restore(p, m, P, pitch0, rate, LOOK_DOWN, LOOK_UP)
    ev.step("place_causality", place)

    # ---------------- stage 4: hotbar select (L3/R3) + START control ----
    hot = {}
    f_hb = grab()
    sel0 = snap(m)[hotbar_ptr:hotbar_ptr + 0x20]
    p.core.run(2, {"R3"})
    w_r3 = held_word(m)
    p.core.run(16, set())                    # debounce 200ms ~ 12f
    f_next = grab()
    ev.png("06_hotbar_next", f_next)
    sel1 = snap(m)[hotbar_ptr:hotbar_ptr + 0x20]
    sel_addr = next((hex(hotbar_ptr + off) for off in range(0x20)
                     if sel0[off] == 0 and sel1[off] == 1), None)
    cp_next = changed_px(f_next, f_hb)
    p.core.run(2, {"L3"})
    p.core.run(16, set())
    f_prev = grab()
    ev.png("07_hotbar_prev", f_prev)
    sel2 = snap(m)[hotbar_ptr:hotbar_ptr + 0x20]
    sel_addr2 = next((hex(hotbar_ptr + off) for off in range(0x20)
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
    # START inventory open/close control (proven round-4; reused as control)
    p.core.run(8, {"START"})
    p.core.run(24, set())
    f_inv = grab()
    ev.png("08_inventory_open", f_inv)
    cp_inv = changed_px(f_inv, f_prev)
    p.core.run(8, {"START"})
    p.core.run(24, set())
    f_closed = grab()
    cp_closed = changed_px(f_closed, f_inv)
    hot["start_inventory"] = {"open": {"changed_px": cp_inv[0],
                                       "bbox": cp_inv[1]},
                              "closed_again": {"changed_px": cp_closed[0]}}
    ev.step("hotbar_inventory", hot)

    # ---------------- stage 5: build structure (>=3 blocks) -------------
    struct = {"placements": []}
    if ok:
        struct["placements"].append({"n": 1, **{k: ok[k] for k in
                                   ("lookdown_frames", "stack_decrement",
                                    "ram_words_changed", "changed_px")}})
        for n in (2, 3):
            w = guarded_walk(p, m, P, pos0, 30, "UP")
            p.core.run(ok["lookdown_frames"], {LOOK_DOWN})
            p.core.run(4, set())
            f_pre = grab()
            ev.png(f"09_struct{n}_pre", f_pre)
            pre = snap(m)
            p.core.run(1, {"L2"})
            for _ in range(10):
                p.core.run(2)
            p.core.run(20, set())
            f_post = grab()
            ev.png(f"10_struct{n}_after", f_post)
            post = snap(m)
            st = stack_decrement(pre, post)
            cp = changed_px(f_post, f_pre)
            rec = {"n": n, "walk": w, "ram_words_changed": words_changed(pre, post),
                   "stack_decrement": st, "changed_px": cp[0], "bbox": cp[1]}
            struct["placements"].append(rec)
            ev.j({"ev": "structure_place", **rec})
            look_restore(p, m, P, pitch0, rate, LOOK_DOWN, LOOK_UP)
        # wide shot: step back toward spawn and frame the structure
        p.core.run(50, {"DOWN"})
        p.core.run(10, set())
        if dist_from(pos_of(m, P), pos0) > 3.5:
            p.core.run(30, {"UP"})
            p.core.run(6, set())
        f_wide = grab()
        ev.png("11_structure_wide", f_wide)
        struct["wide_png"] = "11_structure_wide.png"
    ev.step("structure", struct)

    # ---------------- stage 6: dig A/B discrimination (R2, bounded) -----
    dig = {}
    p.save_state("r7_pre_dig")
    dig["savestate_pre_dig"] = "r7_pre_dig"
    p.core.run((ok["lookdown_frames"] + 10) if ok else 30, {LOOK_DOWN})
    p.core.run(4, set())
    f_dig0 = grab()
    ev.png("12_dig_before", f_dig0)
    pre = snap(m)
    brk_series = []
    w_r2 = None
    for _ in range(4):                        # bounded 240f hold
        p.core.run(60, {"R2"})
        w_r2 = held_word(m)["held"]
        brk_series.append(any(snap(m)[P + 0x6C:P + 0x9C]))
    p.core.run(30, set())
    f_dig1 = grab()
    ev.png("13_dig_after", f_dig1)
    post = snap(m)
    cp_dig = changed_px(f_dig1, f_dig0)
    frames, exact_dig = idle_window(p.core, grab, n=6)
    dig.update({"held_word_r2": w_r2, "breaking_churn_seen": any(brk_series),
                "brk_series": brk_series,
                "ram_words_changed": words_changed(pre, post),
                "changed_px": cp_dig[0], "bbox": cp_dig[1],
                "after_idle_bit_exact": exact_dig})
    # halt detection = input-dead probe (idle static is NORMAL, so test
    # whether a held movement still moves the player): hold UP 15f ->
    # pos must change; a halted game leaves pos and frame frozen.
    pz_h = pos_of(m, P)
    f_h0 = grab()
    p.core.run(15, {"UP"})
    p.core.run(6, set())
    pos_moved = pos_of(m, P) != pz_h
    dig["input_alive_after_dig"] = bool(pos_moved)
    dig["liveness_frame_changed_px"] = changed_px(grab(), f_h0)[0]
    if not pos_moved:
        p.load_state("r7_pre_dig")
        dig["halt_detected"] = True
        dig["restored_pre_dig"] = True
        ev.j({"ev": "dig_halt_restored"})
    else:
        dig["halt_detected"] = False
    look_restore(p, m, P, pitch0, rate, LOOK_DOWN, LOOK_UP)
    ev.step("dig_discrimination", dig)

    # ---------------- stage 7: savestate round-trip (persistence) -------
    sv = {}
    p.core.run(60, set())
    f_saved = grab()
    ev.png("14_pre_save", f_saved)
    p.core.run(1)
    f_saved1 = grab()                         # frame at t+1 (post-restore ref)
    ram_saved = snap(m)
    ev.j({"ev": "save_state_call", "api": "p.save_state('r7_built')",
          "ram_sha": sha(ram_saved)[:16]})
    p.save_state("r7_built")
    # MORE world edits after the save (place #4)
    w7 = guarded_walk(p, m, P, pos0, 30, "UP")
    p.core.run(ok["lookdown_frames"] if ok else 20, {LOOK_DOWN})
    p.core.run(4, set())
    pre = snap(m)
    p.core.run(1, {"L2"})
    for _ in range(10):
        p.core.run(2)
    p.core.run(20, set())
    post = snap(m)
    f_edit = grab()
    ev.png("15_post_edit", f_edit)
    edits = [{"ram_words_changed": words_changed(pre, post),
              "stack_decrement": stack_decrement(pre, post),
              "walk": w7,
              "vs_saved_frame_changed_px": changed_px(f_edit, f_saved)[0]}]
    look_restore(p, m, P, pitch0, rate, LOOK_DOWN, LOOK_UP)
    p.core.run(50, set())
    ram_after_edits = snap(m)
    sv["post_edit"] = {"edits": edits,
                       "ram_sha": sha(ram_after_edits)[:16],
                       "ram_differs_from_saved": sha(ram_after_edits)
                       != sha(ram_saved)}
    ev.j({"ev": "load_state_call", "api": "p.load_state('r7_built')"})
    p.load_state("r7_built")
    ram_rest = snap(m)
    f_rest = grab()
    ev.png("16_post_restore", f_rest)
    p.core.run(1)
    f_rest1 = grab()
    sv["round_trip"] = {
        "api_save": "PS1Play.save_state -> StateManager.save -> core.serialize()",
        "api_load": "PS1Play.load_state -> StateManager.load -> core.unserialize()",
        "ram_sha_saved": sha(ram_saved)[:16],
        "ram_sha_restored": sha(ram_rest)[:16],
        "ram_bit_exact": sha(ram_rest) == sha(ram_saved),
        "frame_madiff": madiff(f_rest, f_saved),
        "frame_changed_px": changed_px(f_rest, f_saved)[0],
        "frame_bit_exact_t": bool(np.array_equal(f_rest, f_saved)),
        "frame_bit_exact_t1": bool(np.array_equal(f_rest1, f_saved1))}
    # functional: the restored world accepts the same edit again (pre-save
    # world had no block there), proving the BUILT state came back
    p.core.run(ok["lookdown_frames"] if ok else 20, {LOOK_DOWN})
    p.core.run(4, set())
    pre2 = snap(m)
    p.core.run(1, {"L2"})
    for _ in range(10):
        p.core.run(2)
    p.core.run(20, set())
    post2 = snap(m)
    f_rest_edit = grab()
    ev.png("17_post_restore_edit", f_rest_edit)
    sv["post_restore_edit"] = {"ram_words_changed": words_changed(pre2, post2),
                               "stack_decrement": stack_decrement(pre2, post2)}
    frames, exact_final = idle_window(p.core, grab, n=8)
    sv["final_idle_bit_exact"] = exact_final
    ev.step("savestate_round_trip", sv)

    # ---------------- totals --------------------------------------------
    ram_end = snap(m)
    totals = {
        "ram_words_changed_vs_boot": words_changed(ram0, ram_end),
        "idle_ram_churn_words_per20f": churn0,
        "persistent_place_events": len(struct["placements"]) +
        (0 if sv["post_restore_edit"]["stack_decrement"] is None else 1),
        "sum_changed_px_persistent_events": sum(
            r.get("changed_px") or 0 for r in struct["placements"]),
        "dig_persistent": (not dig["halt_detected"]) and
                          dig["ram_words_changed"] > churn0 * 3,
        "world_sha_final": sha(ram_end)[:16]}
    ev.step("totals", totals)

    rt_ok = sv["round_trip"]["ram_bit_exact"] and \
        (sv["round_trip"]["frame_bit_exact_t"] or
         sv["round_trip"]["frame_bit_exact_t1"])
    if ok and rt_ok:
        verdict = "GAMEPLAY_CONFIRMED+CAUSAL"
    elif ok:
        verdict = "STATE_CHANGE_CONFIRMED"
    elif sv["round_trip"]["ram_bit_exact"]:
        verdict = "INCONCLUSIVE(place failed; persistence machinery OK)"
    else:
        verdict = "INCONCLUSIVE"
    ev.finish(verdict)
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
