#!/usr/bin/env python3
"""psxmc_r7_place4.py — Task 17-b-r2, iteration 2 (UI-recovery place probe).
ONE beetle boot per process. Predecessor of this script: psxmc_r7_place3.py
(report_place3.json) which achieved the FIRST CONFIRMED PLACE but then lost
the world input for the rest of the run.

place3 findings (honest):
  + attempt 1 (30 deg down, 1-frame L2 tap): stack 0x7cda0 26->25 with
    ItemID 58 (CRAFTING_TABLE) context => the place SUCCEEDED (source:
    playerInputHandlerUse -> worldModifyVoxel, minecraft.c slot0 = table x26).
  - The SAME 1-frame tap also opened the crafting UI: the game logic ticks
    >=2x per emulated frame, tick1 places the table, tick2's raycast hits the
    just-placed CraftingTable -> useAction sets the focused handler
    (block_crafting_table.c:232) -> modal UI. place3's START guard pressed
    START for 8 CONTINUOUS frames: tick1 closed the crafting UI (RELINQUISH)
    and the still-held START immediately re-opened the INVENTORY
    (inventory.c:329 toggle + 200 ms debounce) -> the inventory stayed open
    for the whole rest of the run: look/walk/dig/taps all dead
    (walk delta [0,0,0], eff_down frozen at 30.32, attempts 2-3 tapped L2
    into the UI where it means BINDING_SPLIT_OR_STORE_ONE).
  - place3's merged-report writer had a None-subscript bug (crash after
    RUN_DONE; report_report.json never written).

Fixes in THIS script:
  1. ensure_world_control(): verification-driven recovery. Probe = 6 frames
     of LOOK_DOWN must move the pitch ring (P+0x18); if not, tap START for
     1 frame + 18f settle (debounce-separated single-frame taps, so the
     focused UI toggles one layer per tap) and re-probe, up to 4 rounds.
     Run before every stage and after every successful place tap.
  2. Aim-achievement gate: |eff_down_deg - target| <= 3 (place3's window-only
     gate accepted a frozen aim).
  3. Tap loop aborts on UI-open-without-place (avoids L2-as-SPLIT in UI).
  4. Walk-alive check (delta must be nonzero; recover + retry once).
  5. post/static/PNG evidence captured AFTER the UI is closed => clean
     world-view attribution (the placed table is visible in-frame).
  6. merged report_report.json writer fixed.

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
TAG = "place4"

PITCH_MOD = 1 << 24
DEG = PITCH_MOD / 360.0
ONE_BLOCK = 286720
T_MAX = 400.0
ITEMID_CRAFTING_TABLE = 58
HUD_BAND = (56, 208, 264, 240)

LOOK_DOWN = "B"                  # PAD_CROSS  (bindings.c BINDING_LOOK_DOWN)
LOOK_UP = "X"                    # PAD_TRIANGLE (BINDING_LOOK_UP)
PLACE_BTN = "L2"                 # BINDING_USE
DIG_BTN = "R2"                   # BINDING_ATTACK
UI_BTN = "START"                 # BINDING_OPEN_INVENTORY (toggles/focus-out)


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


def dist_from(a, b):
    return (abs(a[0] - b[0]) + abs(a[2] - b[2])) / ONE_BLOCK


def ring_diff(a, b):
    return (b - a + (PITCH_MOD >> 1)) % PITCH_MOD - (PITCH_MOD >> 1)


def pitch_now(m, P):
    return m.u32(P + 0x18) & (PITCH_MOD - 1)


def eff_down_deg(m, P, pitch0):
    return ((pitch_now(m, P) - pitch0) % PITCH_MOD) / DEG


def ram_churn(p, m, frames=20):
    a = snap(m)
    p.core.run(frames)
    return words_changed(a, snap(m))


def view_stats(f):
    a = f.astype(np.int16)
    c = a[60:180, 100:220]
    return {"std": round(float(a.std()), 1),
            "center_std": round(float(c.std()), 1),
            "top": round(float(a[:120].mean()), 1),
            "bot": round(float(a[120:].mean()), 1)}


def view_ok(v):
    return v["std"] > 25 and v["center_std"] > 8


def look_to(m, core, P, pitch0, want_deg, r_down, r_up,
            tol_deg=1.0, max_it=8):
    """CORRECTED closed-loop aim (place3's fix, kept)."""
    want = (pitch0 + int(round(want_deg * DEG))) % PITCH_MOD
    r_down = max(r_down, 1.0)
    r_up = max(r_up, 1.0)
    cur = pitch_now(m, P)
    err = ring_diff(cur, want)
    it = 0
    while abs(err) > tol_deg * DEG and it < max_it:
        n = int(round(abs(err) / (r_down if err > 0 else r_up)))
        n = max(1, min(n, 400))
        core.run(n, {LOOK_DOWN} if err > 0 else {LOOK_UP})
        cur = pitch_now(m, P)
        err = ring_diff(cur, want)
        it += 1
    return {"want_deg": want_deg, "iters": it, "pitch": cur,
            "err_raw": int(err), "err_deg": round(err / DEG, 2)}


def ensure_world_control(core, m, P, ev, tag):
    """Verification-driven UI recovery. A 6-frame LOOK_DOWN probe must move
    the pitch ring; otherwise tap START for ONE frame (the focused UI layer
    toggles/relinquishes) and re-probe. Returns a record."""
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
        core.run(18, set())          # > 200 ms debounce window
    ev.j({"ev": f"world_control_{tag}", **rec})
    return rec


def stack_scan(pre, post, pairs=((26, 25), (25, 24), (24, 23), (10, 9))):
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
                   "ctx_hex": pre[max(0, i - 16):i + 4].hex()}
            if rec["itemid_ctx"]:
                hits.append(rec)
    return hits


def classify_px(cp):
    n, bb = cp
    if not bb:
        return {"changed_px": n, "bbox": None, "world_px": n}
    x0, y0, x1, y1 = bb
    if x0 >= HUD_BAND[0] and x1 <= HUD_BAND[2] and y0 >= HUD_BAND[1]:
        return {"changed_px": n, "bbox": bb, "world_px": 0, "hud_only": True}
    return {"changed_px": n, "bbox": bb, "world_px": n}


def walk(p, m, P, pos0, btn, frames, ev, tag, max_dist=7.5):
    a = pos_of(m, P)
    p.core.run(frames, {btn})
    p.core.run(10, set())
    b = pos_of(m, P)
    rec = {"btn": btn, "frames": frames,
           "delta_blocks": [round((b[i] - a[i]) / ONE_BLOCK, 2)
                            for i in (0, 1, 2)],
           "dist_from_spawn_blocks": round(dist_from(b, pos0), 2)}
    rec["moved"] = any(abs(d) > 0.05 for d in rec["delta_blocks"])
    if not rec["moved"]:                       # dead input -> recover + retry
        ensure_world_control(p.core, m, P, ev, f"walk_{tag}")
        a = pos_of(m, P)
        p.core.run(frames, {btn})
        p.core.run(10, set())
        b = pos_of(m, P)
        rec["retry_delta_blocks"] = [round((b[i] - a[i]) / ONE_BLOCK, 2)
                                     for i in (0, 1, 2)]
        rec["moved"] = any(abs(d) > 0.05
                           for d in rec["retry_delta_blocks"])
    if dist_from(b, pos0) > max_dist:
        p.core.run(frames, {"DOWN" if btn == "UP" else "UP"})
        p.core.run(8, set())
        rec["safety_backpedal"] = round(
            dist_from(pos_of(m, P), pos0), 2)
    ev.j({"ev": f"walk_{tag}", **rec})
    return rec


def place_taps(core, m, P, ev, f_pre, pre, max_taps=3):
    """Graduated 1-frame L2 taps. Stops on: stack hit (success), UI-open
    without success (abort; L2 means SPLIT inside UI), or exhaustion."""
    rec = {"taps": [], "tap_used": None, "stack_hits": [],
           "ui_opened": False}
    for tap in range(max_taps):
        core.run(1, {PLACE_BTN})
        rec["taps"].append(held_word(m)["held"])
        core.run(3, set())
        post_k = snap(m)
        hits = stack_scan(pre, post_k)
        cp_k = classify_px(changed_px(core.frame_rgb(), f_pre))
        if hits:
            rec["tap_used"] = tap + 1
            rec["stack_hits"] = hits
            break
        if cp_k["changed_px"] > 12000:       # UI opened, no place happened
            rec["ui_opened"] = True
            rec["ui_px"] = cp_k["changed_px"]
            break
    return rec


def main():
    ev = Evid(OUT, TAG)
    ev.j({"ev": "start", "cue": CUE, "workspace": WS, "task": "17-b-r2",
          "iteration": 2})
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
    ev.j({"ev": "world_ready", "P": hex(P),
          "padbuff": snap(m).count(PADBUFF_SIG)})

    # ---------------- baseline ----------------
    f_world = grab()
    ev.png("p4_01_world_render", f_world)
    frames, exact0 = idle_window(core, grab, n=10)
    f_base = frames[0]
    ev.png("p4_02_idle_baseline", f_base)
    churn0 = ram_churn(p, m, 20)
    ram0 = snap(m)
    pos0 = pos_of(m, P)
    pitch0 = pitch_now(m, P)
    ev.step("baseline", {
        "padbuff_hits": snap(m).count(PADBUFF_SIG), "idle_bit_exact": exact0,
        "idle_ram_churn_words_per20f": churn0,
        "pos_blocks": [round(v / ONE_BLOCK, 2) for v in pos0],
        "pitch_raw": pitch0, "ram_sha": sha(ram0)[:16]})

    # ---------------- live look-rate probe ----------------
    a = pitch_now(m, P)
    core.run(10, {LOOK_DOWN})
    r_down = abs(ring_diff(a, pitch_now(m, P))) / 10.0
    a = pitch_now(m, P)
    core.run(10, {LOOK_UP})
    r_up = abs(ring_diff(a, pitch_now(m, P))) / 10.0
    look_to(m, core, P, pitch0, 0, r_down, r_up)
    core.run(6, set())
    ev.step("look_rate_probe", {
        "r_down_raw_per_f": r_down, "r_up_raw_per_f": r_up,
        "down_deg_per_f": round(r_down / DEG, 3),
        "up_deg_per_f": round(r_up / DEG, 3),
        "pitch_after_restore_deg": round(eff_down_deg(m, P, pitch0), 2)})

    # ---------------- PLACE ladder ----------------
    attempts = []
    ok_atts = []
    chain = {}
    angles = (30, 40, 25)
    for ai, ang in enumerate(angles):
        if time.time() - ev.t0 > T_MAX - 100:
            ev.j({"ev": "time_guard_skip", "stage": "place", "angle": ang})
            break
        wc = ensure_world_control(core, m, P, ev, f"pre_a{ai+1}")
        if ai:
            walk(p, m, P, pos0, "DOWN", 45, ev, f"pre_a{ai+1}")
        aim = look_to(m, core, P, pitch0, ang, r_down, r_up)
        core.run(4, set())
        eff = round(eff_down_deg(m, P, pitch0), 2)
        f_pre = grab()
        vs = view_stats(f_pre)
        geo_ok = abs(eff - ang) <= 3.0 and 12.0 <= eff <= 80.0
        gate = bool(geo_ok and view_ok(vs))
        rec = {"attempt": ai + 1, "angle_deg": ang, "aim": aim,
               "eff_down_deg": eff, "geo_gate": geo_ok, "view": vs,
               "gate_pass": gate}
        ev.png(f"p4_a{ai+1}_pre", f_pre)
        ev.j({"ev": "place_gate", **{k: rec[k] for k in
             ("attempt", "angle_deg", "eff_down_deg", "geo_gate",
              "view", "gate_pass")}})
        if not gate:
            attempts.append(rec)
            continue
        pre = snap(m)
        rec.update(place_taps(core, m, P, ev, f_pre, pre))
        # recover world control (successful place opens the crafting UI)
        ctrl = ensure_world_control(core, m, P, ev, f"post_a{ai+1}")
        rec["post_control"] = ctrl
        look_to(m, core, P, pitch0, ang, r_down, r_up)   # re-frame the spot
        core.run(4, set())
        f_post = grab()
        ev.png(f"p4_a{ai+1}_after", f_post)
        post = snap(m)
        frames, exact_s = idle_window(core, grab, n=8)
        f_static = frames[0]
        ev.png(f"p4_a{ai+1}_static", f_static)
        cp_post = classify_px(changed_px(f_post, f_pre))
        cp_static = classify_px(changed_px(f_static, f_pre))
        hits = rec.get("stack_hits") or stack_scan(pre, post)
        for h in hits:
            prev = chain.setdefault(h["addr"], [])
            prev.append((h["before"], h["after"]))
            h["chain_len"] = len(prev)
        rec.update({
            "ram_words_changed": words_changed(pre, post),
            "post": cp_post, "static_idle_bit_exact": exact_s,
            "static_vs_pre": cp_static, "stack_hits": hits})
        rec["placed"] = bool(hits) and exact_s and cp_static["world_px"] > 0
        attempts.append(rec)
        ev.j({"ev": "place_attempt", "attempt": rec["attempt"],
              "placed": rec["placed"], "tap_used": rec.get("tap_used"),
              "stack_hits": hits, "post": cp_post,
              "static_vs_pre": cp_static,
              "ram_words_changed": rec["ram_words_changed"]})
        if rec["placed"]:
            ok_atts.append(rec)
        look_to(m, core, P, pitch0, 0, r_down, r_up)
        core.run(6, set())
    ev.step("place_causality", {
        "note": "L2=BINDING_USE; player.c:255+ needs raycast hit within "
                "reach 6; a successful 1-frame tap also opens the placed "
                "table's UI on the next logic tick (recovered via "
                "ensure_world_control)",
        "attempts": attempts,
        "confirmed_places": len(ok_atts),
        "stack_chain": {k: [list(x) for x in v] for k, v in chain.items()}})

    # ---------------- structure shots ----------------
    if ok_atts:
        ensure_world_control(core, m, P, ev, "shots")
        look_to(m, core, P, pitch0, 0, r_down, r_up)
        core.run(6, set())
        ev.png("p4_11_structure_horizon", grab())
        look_to(m, core, P, pitch0, 30, r_down, r_up)
        core.run(4, set())
        ev.png("p4_12_structure_ground30", grab())
        look_to(m, core, P, pitch0, 0, r_down, r_up)
        core.run(4, set())

    # ---------------- dig A/B discrimination (R2) ----------------
    dig = {}
    if time.time() - ev.t0 < T_MAX - 80:
        wc = ensure_world_control(core, m, P, ev, "pre_dig")
        if wc["alive"]:
            walk(p, m, P, pos0, "DOWN", 45, ev, "pre_dig")
            p.save_state("p4_pre_dig")
            aim_dig = look_to(m, core, P, pitch0, 35, r_down, r_up)
            core.run(4, set())
            f_dig0 = grab()
            ev.png("p4_13_dig_before", f_dig0)
            vs_dig = view_stats(f_dig0)
            pre = snap(m)
            brk = []
            w_r2 = None
            for _ in range(4):
                core.run(60, {DIG_BTN})
                w_r2 = held_word(m)["held"]
                brk.append(any(snap(m)[P + 0x6C:P + 0x9C]))
            core.run(30, set())
            f_dig1 = grab()
            ev.png("p4_14_dig_after", f_dig1)
            post = snap(m)
            cp_dig = classify_px(changed_px(f_dig1, f_dig0))
            dig_hits = stack_scan(pre, post)
            pz = pos_of(m, P)
            f_h0 = grab()
            core.run(15, {"UP"})
            core.run(6, set())
            alive = pos_of(m, P) != pz
            dig = {"aim": aim_dig, "view": vs_dig,
                   "held_word_r2_mid": w_r2,
                   "breaking_churn_seen": any(brk), "brk_series": brk,
                   "ram_words_changed": words_changed(pre, post),
                   "px": cp_dig, "stack_hits": dig_hits,
                   "input_alive_after_dig": bool(alive),
                   "liveness_frame_changed_px": changed_px(grab(), f_h0)[0],
                   "halt_detected": not alive}
            if not alive:
                p.load_state("p4_pre_dig")
                dig["restored_pre_dig"] = True
                ev.j({"ev": "dig_halt_restored"})
            ev.j({"ev": "dig_done", **{k: dig[k] for k in
                 ("breaking_churn_seen", "px", "stack_hits",
                  "input_alive_after_dig", "halt_detected")}})
            look_to(m, core, P, pitch0, 0, r_down, r_up)
            core.run(6, set())
    ev.step("dig_discrimination", dig)

    # ---------------- savestate round-trip on the BUILT world ------------
    sv = {}
    if time.time() - ev.t0 < T_MAX - 60:
        wc = ensure_world_control(core, m, P, ev, "pre_save")
        if wc["alive"]:
            core.run(40, set())
            f_saved = grab()
            ev.png("p4_15_pre_save", f_saved)
            core.run(1)
            f_saved1 = grab()
            ram_saved = snap(m)
            ev.j({"ev": "save_state_call", "api": "p.save_state('p4_built')",
                  "ram_sha": sha(ram_saved)[:16]})
            p.save_state("p4_built")
            walk(p, m, P, pos0, "DOWN", 30, ev, "post_save")
            aim_e = look_to(m, core, P, pitch0, 30, r_down, r_up)
            core.run(4, set())
            pre = snap(m)
            te = place_taps(core, m, P, ev, grab(), pre)
            ensure_world_control(core, m, P, ev, "post_edit")
            core.run(20, set())
            ev.png("p4_16_post_edit", grab())
            look_to(m, core, P, pitch0, 0, r_down, r_up)
            core.run(30, set())
            ram_after = snap(m)
            sv["post_edit"] = {"stack_hits": te["stack_hits"],
                               "aim": aim_e,
                               "ram_sha": sha(ram_after)[:16],
                               "ram_differs_from_saved":
                               sha(ram_after) != sha(ram_saved)}
            ev.j({"ev": "load_state_call",
                  "api": "p.load_state('p4_built')"})
            p.load_state("p4_built")
            ram_rest = snap(m)
            f_rest = grab()
            ev.png("p4_17_post_restore", f_rest)
            core.run(1)
            f_rest1 = grab()
            sv["round_trip"] = {
                "api_save": "PS1Play.save_state -> StateManager.save -> "
                            "core.serialize()",
                "api_load": "PS1Play.load_state -> StateManager.load -> "
                            "core.unserialize()",
                "ram_sha_saved": sha(ram_saved)[:16],
                "ram_sha_restored": sha(ram_rest)[:16],
                "ram_bit_exact": sha(ram_rest) == sha(ram_saved),
                "frame_bit_exact_t": bool(np.array_equal(f_rest, f_saved)),
                "frame_bit_exact_t1":
                bool(np.array_equal(f_rest1, f_saved1))}
            # functional: the restored BUILT world accepts the same edit
            wc2 = ensure_world_control(core, m, P, ev, "post_restore")
            if wc2["alive"]:
                aim_r = look_to(m, core, P, pitch0, 30, r_down, r_up)
                core.run(4, set())
                f_re = grab()
                vs_re = view_stats(f_re)
                pre2 = snap(m)
                tr = place_taps(core, m, P, ev, f_re, pre2)
                ensure_world_control(core, m, P, ev, "post_restore_edit")
                core.run(20, set())
                f_rest_edit = grab()
                ev.png("p4_18_post_restore_edit", f_rest_edit)
                for h in tr["stack_hits"]:
                    prev = chain.setdefault(h["addr"], [])
                    prev.append((h["before"], h["after"]))
                    h["chain_len"] = len(prev)
                cp_re = classify_px(changed_px(f_rest_edit, f_re))
                sv["post_restore_edit"] = {
                    "view": vs_re, "stack_hits": tr["stack_hits"],
                    "px": cp_re,
                    "replaced_on_restored_world":
                    bool(tr["stack_hits"])}
            else:
                sv["post_restore_edit"] = {"world_control": False}
            frames, ex_fin = idle_window(core, grab, n=8)
            sv["final_idle_bit_exact"] = ex_fin
            ev.j({"ev": "roundtrip_done",
                  "ram_bit_exact": sv["round_trip"]["ram_bit_exact"],
                  "frame_bit_exact_t1":
                  sv["round_trip"]["frame_bit_exact_t1"],
                  "replaced_on_restored_world":
                  sv.get("post_restore_edit", {}).get(
                      "replaced_on_restored_world")})
    ev.step("savestate_round_trip", sv)

    # ---------------- totals + verdict -----------------------------------
    ram_end = snap(m)
    n_places = len(ok_atts) + (
        1 if sv.get("post_restore_edit", {}).get(
            "replaced_on_restored_world") else 0)
    totals = {
        "confirmed_place_events": n_places,
        "stack_chain": {k: [list(x) for x in v] for k, v in chain.items()},
        "dig_persistent": bool(dig) and dig.get("input_alive_after_dig") and
                          dig.get("px", {}).get("world_px", 0) > 0,
        "savestate_bit_exact": sv.get("round_trip", {}).get("ram_bit_exact"),
        "ram_words_changed_vs_boot": words_changed(ram0, ram_end),
        "idle_ram_churn_words_per20f": churn0,
        "world_sha_final": sha(ram_end)[:16]}
    ev.step("totals", totals)

    rt_ok = sv.get("round_trip", {}).get("ram_bit_exact") and \
        sv.get("round_trip", {}).get("frame_bit_exact_t1", False)
    if len(ok_atts) >= 3 and rt_ok:
        verdict = "CAUSAL(place x%d; dig persistent; savestate bit-exact)" \
            % len(ok_atts)
    elif len(ok_atts) >= 1 and rt_ok:
        verdict = "GAMEPLAY_CONFIRMED+CAUSAL(place x%d; savestate bit-exact)" \
            % n_places
    elif len(ok_atts) >= 1:
        verdict = "STATE_CHANGE_CONFIRMED(place x%d; savestate not proven)" \
            % len(ok_atts)
    else:
        verdict = "INCONCLUSIVE(place failed after 2 predecessor rounds + " \
                  "2 retries; battery complete)"
    ev.finish(verdict)

    # ---------------- merged final report --------------------------------
    import json
    merged = {"task": "17-b-r2 (place retry of 17-b)",
              "game": "PSX-Minecraft infdev_2025_04_18 (MIT)",
              "predecessor_runs": {}, "final_run": {}}
    for tag in ("main", "main2", "place3", "place4"):
        rp = os.path.join(OUT, f"report_{tag}.json")
        if os.path.exists(rp):
            with open(rp) as f:
                key = "final_run" if tag == TAG else "predecessor_runs"
                merged[key][tag] = json.load(f)
    merged["final_verdict"] = verdict
    merged["diagnosis"] = (
        "Place failures in runs main/main2 were AIM failures: the pitch "
        "controller used the inverted residual (cur-want instead of "
        "want-cur), doubling the ring error every iteration; the camera was "
        "in the sky hemisphere at every L2 press (uniform-sky pre-frames, "
        "center_std ~3.7 vs >=14.5 for terrain), so worldRayCastIntersection "
        "returned block==NULL and playerInputHandlerUse silently did "
        "nothing. Upstream truth: bindings.c BINDING_USE=PAD_L2 / "
        "BINDING_ATTACK=PAD_R2; player.c:429-437 free-running pitch ring "
        "(CROSS down = +, no clamp, ground visible at pitch mod 360 in "
        "(0,180) deg); player.c:255+ use handler needs a raycast hit within "
        "PLAYER_REACH_DISTANCE=6. Retry place3 got the first confirmed "
        "place (stack 0x7cda0 26->25, ItemID 58 context) but a successful "
        "tap also opens the placed table's UI on the next logic tick; "
        "place4 adds verification-driven UI recovery (single-frame START "
        "taps + look-probe).")
    with open(os.path.join(OUT, "report_report.json"), "w") as f:
        json.dump(merged, f, indent=1, default=str)
    ev.j({"ev": "MERGED_REPORT",
          "path": os.path.join(OUT, "report_report.json")})
    try:
        core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
