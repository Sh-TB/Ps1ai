#!/usr/bin/env python3
"""psxmc_r11_place8.py (v5) — Round 11 / Segment 6: DIG-DOWN bootstrap +
engine-sensed breaking + shaft refill placement.

Why v2-v4 failed (instrument map, all evidence on disk):
  v2/v3: forward servo aims adopted junk/stale diff candidates — the
         fresh world is FLATLAND (spawn [0,9.62,0] on stone y=7), the
         engine raycast over a flat plain hits NOTHING within reach 6,
         so player->breaking.block stayed NULL and no cell ever
         changed.  Hotbar was EMPTY the whole time, so even a perfect
         aim could not place (player.c playerInputHandlerUse: item
         NULL -> steps 2-4 -> no-op).
  v4:    continuous R2 hold was CORRECT (release resets progress,
         player.c:402 reset_trigger) — 1,440 f hold on [0,7,1] still
         mined nothing because the crosshair was in the air.

v5 design (ground truth: player.c + breaking_state.c/h + ELF disasm):
  - BreakingState @ player+0x6C: ticks_so_far +0x74 (+= 0x1000/tick),
    position (3x s32) +0x78/7C/80, block ptr +0x88 (NULL=not breaking)
    — verified against updateBreakingState @0x80013c9c (addiu s3,a0,0x6c;
    ticks += ONE @0x80013d3c; block @0x88 via lw v1,0x88(a0)).
  - Stone hardness 6144, hand (no ideal tool) => /100 => ~152-682 ticks
    to break => a 1,440 f hold is enough IF the crosshair is on the
    block.  The breaking window tells us the truth every frame.

Chain: boot -> settle -> WorldReader -> surface -> DIG-DOWN x2 (aim
straight down at the own-column cell, hold R2 CONTINUOUSLY, poll
breaking window + world id; the engine target is READ, not assumed)
-> hotbar check (pickup expected) -> negative control (horizon + L2)
-> PLACE: aim straight down (crosshair = top face of the block under
the shaft bottom; normal face => placement cell = shaft bottom) ->
L2 -> verify shaft-bottom cell id 0 -> non-zero + stack decrement +
PNG diff -> second cycle: mine the placed cell back, place again.
Verdict: PLACE_CONFIRMED x N / FAILED_<stage>.  Evidence:
scratch/round11_psxmc/place8/. ONE beetle boot; no RAM writes.
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

import psxmc_r11_lib as R11                          # noqa: E402
import psxmc_r10_lib as L                            # noqa: E402
from psxmc_r10_oracle import (                       # noqa: E402
    CUE, player_ptr, pos_of, pitch_now, ensure_world_control,
    aim_ring_exact)
from psxmc_r7_lib import Evid                        # noqa: E402

WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r11p"
OUT = os.path.join(_REPO, "scratch", "round11_psxmc", "place8")
TAG = "place8"
PLACE_BTN = "L2"
ATTACK_BTN = "R2"


def find_hotbar_item(m, P, search=0x60):
    """Prefer the UI whose SELECTED slot holds a real item (sane id,
    stack > 0).  The v12 generic scan stopped at the first UI (empty
    slot 0) and missed the spawn-kit cobblestone at P+0x64 slot 0
    (item_id 4, stack 92 — itemsurvey evidence)."""
    best = None
    for off in range(0x40, 0x40 + search, 4):
        H = L.phys(m.u32(P + off))
        if not L.is_heap(H):
            continue
        # v14: the active gate (H+8 in {0,1}) rejected the UI after the
        # fall into the dig shaft — relax it (record the value, decide
        # on the item chain alone)
        active = m.u8(H + 8)
        # v15: the sel byte (H+100) read 12 for the cobblestone UI —
        # outside 0..8, so the gate killed the only real item chain.
        # Drop it; scan slots 0..12 and let the physical verifiers
        # (stack decrement / y-rise / PNG) decide the semantics.
        sel = m.u8(H + 100)
        for s in range(13):
            d = L.phys(m.u32(H + 28 + 8 * s))
            item = d
            if L.is_heap(d):
                r = L.phys(m.u32(d))
                if L.is_heap(r):
                    item = r
            if not L.is_heap(item):
                continue
            iid = m.u32(item)
            stack = m.u8(item + 12)
            if iid in (0, None) or iid > 64 or not stack:
                continue
            cand = {"hotbar_off": off, "hotbar": H,
                    "active": bool(active), "selected": sel, "slot": s,
                    "item": item, "item_id": iid, "stack": stack,
                    "stack_addr": item + 12}
            if best is None or cand["stack"] > best["stack"]:
                best = cand
    return best


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    ev = Evid(OUT, TAG)
    ev.jpath = os.path.join(OUT, "r11_place8_v5.jsonl")
    ev.j({"ev": "start", "cue": CUE, "task": "17-b place8 v5: dig-down "
          "bootstrap + engine-sensed breaking + shaft refill"})

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
    ensure_world_control(core, m, P, ev, "place8")

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

    def breaking_now():
        return R11.breaking_current(m, P)

    pos0 = settle()
    ev.j({"ev": "settled", "P": hex(P),
          "pos_blocks": [round(v / L.ONE_BLOCK, 3) for v in pos0]})

    wr = L.WorldReader(m)
    wr_info = None
    for _ in range(5):
        try:
            wr_info = wr.discover()
            break
        except Exception as e:                        # noqa: BLE001
            ev.j({"ev": "world_retry", "err": str(e)[:120]})
            core.run(30, set())
    if wr_info is None:
        ev.finish("FAILED: WorldReader discovery failed")
        return 2
    ev.j({"ev": "world", **wr_info})

    fbx = int(np.floor(pos_of(m, P)[0] / L.ONE_BLOCK))
    fbz = int(np.floor(pos_of(m, P)[2] / L.ONE_BLOCK))

    # ---------------- negative control (horizon + L2) -----------------
    st_pre = (L.find_hotbar(m, P) or {}).get("stack")
    aim_ring_exact(core, m, P, pitch_now(m, P), 0.0)
    core.run(6, {PLACE_BTN})
    core.run(45, set())
    st_post = (L.find_hotbar(m, P) or {}).get("stack")
    ev.j({"ev": "NEGATIVE_CONTROL", "stack": [st_pre, st_post]})

    def engine_aim_sweep(want_cell, span=8):
        """Sweep the LOOK ring (15-deg steps) across +/-span frames and
        read the ENGINE's breaking.position at each reachable ring.

        Returns (ok, ring_offset, map).  The v6 servo showed pitch
        nudges land BETWEEN rings (aim settles, ray jumps beyond
        reach); the sweep enumerates the actual reachable set."""
        import psxmc_r10_place7 as _P7
        step, _r2 = R11.measure_ring_step(core, lambda: pitch_now(m, P))
        # go to the top of the sweep range
        core.run(span, {"X"})                # LOOK_UP span frames
        ring_map = []
        for k in range(-span, span + 1):
            core.run(2, set())
            bw = None
            for _h in range(5):
                core.run(12, {ATTACK_BTN})
                bw = breaking_now()
                if bw["live"]:
                    break
            ring_map.append({"k": k, "live": bw["live"],
                             "hit": bw["hit"]})
            if k < 2 * span:
                core.run(1, {"B"})           # LOOK_DOWN one step
        core.run(2, set())
        ev.j({"ev": "ring_sweep", "want": list(want_cell),
              "step_deg": round(step / L.DEG, 2), "map": ring_map})
        # choose the ring whose engine cell == want (nearest first)
        best = None
        for e in ring_map:
            if not e["live"]:
                continue
            d = sum(abs(a - b) for a, b in zip(e["hit"], want_cell))
            if best is None or d < best[0]:
                best = (d, e["k"], e["hit"])
        if best is None:
            return False, None, ring_map
        d, k_best, hit = best
        # walk back to k_best: from current position (k=+span side after
        # the loop we are at +span... the loop ended having pressed
        # LOOK_DOWN 2*span times total, so we are back near k=+span end;
        # move (span - k_best) LOOK_UP frames to reach k_best
        back = span - k_best
        if back > 0:
            core.run(back, {"X"})
        elif back < 0:
            core.run(-back, {"B"})
        core.run(2, set())
        bw = None
        for _h in range(5):
            core.run(12, {ATTACK_BTN})
            bw = breaking_now()
            if bw["live"]:
                break
        ok = bool(bw and bw["live"]
                  and tuple(bw["hit"]) == tuple(want_cell))
        ev.j({"ev": "engine_aim_locked" if ok else "engine_aim_off",
              "want": list(want_cell), "k": k_best,
              "dist": d, "hit": bw["hit"] if bw else None})
        return ok, k_best, ring_map

    # ---------------- v8: embrace the engine -------------------------
    # v5 proved: aim_ring_exact(90 deg) + continuous R2 -> the engine
    # breaks [0,7,-1] (one cell behind the nominal column) with ticks
    # growing.  So DIG WHATEVER THE ENGINE POINTS AT:
    #   1. read T = breaking.position at the vertical ring
    #   2. continuous R2 until wid(T) == 0 (never release: progress
    #      resets on release, player.c:402)
    #   3. walk forward into the hole (facing == ray tilt), fall, pick
    #      up the dropped item -> hotbar non-null
    #   4. place: straight-down ray in the hole hits the floor top
    #      face; normal +y => placement cell = the refilled cell
    #   5. second cycle: mine the refilled cell, place again
    digs, verified = [], []
    pos = settle()
    bx = int(np.floor(pos[0] / L.ONE_BLOCK))
    bz = int(np.floor(pos[2] / L.ONE_BLOCK))
    surf_y, surf_id = R11.top_nonair(wr, bx, bz)
    aim_ring_exact(core, m, P, pitch_now(m, P), 90.0)
    core.run(2, set())
    T = None
    for _h in range(5):
        core.run(30, {ATTACK_BTN})
        bw = breaking_now()
        if bw["live"]:
            T = tuple(bw["hit"])
            break
    ev.j({"ev": "engine_vertical_target", "T": list(T) if T else None,
          "nominal": [bx, surf_y, bz]})
    if T is not None:
        # continuous hold; stop the MOMENT the engine's target moves
        # off T (that = the ray passed through a broken T) or wid flips
        mined, holds = False, []
        for _i in range(24):
            core.run(60, {ATTACK_BTN})
            bw = breaking_now()
            holds.append({"f": core.frames_run, "hit": bw["hit"],
                          "tsf": bw["ticks"]["so_far"]})
            if bw["live"] and tuple(bw["hit"]) != T:
                mined = True        # engine target moved off T
                break
            if _i % 4 == 3:
                wr = L.WorldReader(m)
                wr.discover()
                if wr.block_id(*T) in (0, None):
                    mined = True
                    break
        ev.j({"ev": "MINE_HOLD", "target": list(T), "mined": mined,
              "holds_head": holds[:2], "holds_tail": holds[-2:]})
        core.run(30, set())
        # walk INTO the hole (1 cell backward — 15 f, not 26)
        core.run(15, {"DOWN"})
        core.run(150, set())                     # fall + pickup settle
        pos = settle()
        bx2 = int(np.floor(pos[0] / L.ONE_BLOCK))
        bz2 = int(np.floor(pos[2] / L.ONE_BLOCK))
        digs.append({"target": list(T), "mined": mined,
                     "stood_at": [bx2, bz2],
                     "breaking_seen": True})
        ev.j({"ev": "DIG_DONE", **digs[-1]})
        ev.png("place8_dig0.png", grab())
    else:
        ev.j({"ev": "no_engine_target"})

    hb = find_hotbar_item(m, P)
    # raw chain dump for the survey-reproduced UI at P+0x64
    dump = {}
    for off in (0x5C, 0x60, 0x64, 0x68):
        Hraw = m.u32(P + off)
        H = L.phys(Hraw)
        e = {"Hraw": hex(Hraw), "heap": L.is_heap(H)}
        if L.is_heap(H):
            e["active"] = m.u8(H + 8)
            e["sel"] = m.u8(H + 100)
            d = L.phys(m.u32(H + 28))
            e["d"] = hex(d) if d else "0"
            if L.is_heap(d):
                r = L.phys(m.u32(d))
                it = r if L.is_heap(r) else d
                e["item_id"] = m.u32(it)
                e["stack"] = m.u8(it + 12)
        dump[hex(off)] = e
    ev.j({"ev": "hotbar_after_digs", "hotbar": hb, "raw": dump})
    if hb is None or not hb.get("stack"):
        # place is a no-op with an empty hotbar (player.c use handler)
        rep = {"verdict": "FAILED_HOTBAR_EMPTY", "digs": digs,
               "note": "player.c use handler: item NULL -> no-op; "
                       "mining did not yield a pickup",
               "wall_s": round(time.time() - t0, 1)}
        json.dump(rep, open(os.path.join(OUT, "report.json"), "w"),
                  indent=1, default=str)
        ev.finish(rep["verdict"])
        return 4

    # ---------------- PLACE: shaft-bottom refill ----------------------
    # v16: the post-remesh WorldReader cannot re-read the mined cell
    # (v10/v15 evidence), but the ENGINE already confirmed the break —
    # the refill target IS T (the mined cell); the player stands in it.
    verified = []
    if T is None:
        ev.j({"ev": "no_engine_target_place"})
        T = None
    for cycle in range(2) if T is not None else range(0):
        target = T
        ev.j({"ev": "place_target", "cycle": cycle, "target": target,
              "source": "engine-confirmed mined cell"})
        ev.j({"ev": "place_target", "cycle": cycle, "target": target})
        okg, _gt = __import__("psxmc_r10_place7").stable_gate(core, m)
        ev.j({"ev": "place_gate", "stable": okg})
        # aim-sense: the ray down must hit the FLOOR (target.y - 1)
        bw_pre = None
        for _i in range(6):
            core.run(10, {ATTACK_BTN})
            bw_pre = breaking_now()
            if bw_pre["live"]:
                break
        sense_ok = bool(bw_pre and bw_pre["live"]
                        and bw_pre["hit"][0] == target[0]
                        and bw_pre["hit"][2] == target[2]
                        and bw_pre["hit"][1] == target[1] - 1)
        ev.j({"ev": "aim_sense", "cycle": cycle,
              "engine_target": bw_pre["hit"] if bw_pre else None,
              "live": bw_pre["live"] if bw_pre else False,
              "sense_ok": sense_ok})
        st_pre = (find_hotbar_item(m, P) or {}).get("stack")
        y_pre = pos_of(m, P)[1]
        fr_pre = grab()
        ev.png(f"place8_c{cycle}_pre", fr_pre)
        core.run(6, {PLACE_BTN})
        core.run(45, set())
        st_post = (find_hotbar_item(m, P) or {}).get("stack")
        fr_post = grab()
        ev.png(f"place8_c{cycle}_post", fr_post)
        y_post = pos_of(m, P)[1]
        stack_delta = ((st_post - st_pre)
                       if (st_pre is not None and st_post is not None)
                       else None)
        wid_post = wr.block_id(*target)
        png_changed = (fr_pre.tobytes() != fr_post.tobytes())
        y_rise = round(y_post - y_pre, 3)      # pushed up by the block
        signals = {"stack_drop": stack_delta is not None
                   and stack_delta < 0,
                   "png": png_changed,
                   "y_rise": y_rise > L.ONE_BLOCK * 0.5}
        # v17 grading: a placement must show a PHYSICAL consumption
        # signal — the stack decrements or the player is pushed up.
        # wid_post is unreliable post-remesh (reads stale ids) and
        # png alone fires on the breaking overlay; the v16 run's
        # "PLACE_CONFIRMED x1" was downgraded on exactly this basis
        # (stack 92->92, y_rise 0 — the use-handler's item-NULL
        # no-op: the cobblestone sits in the INVENTORY UI, not the
        # hotbar).
        ok = bool(signals["stack_drop"] or signals["y_rise"])
        rec = {"cycle": cycle, "target": target, "wid_post": wid_post,
               "stack": [st_pre, st_post], "stack_delta": stack_delta,
               "png_changed": png_changed, "y_rise": y_rise,
               "signals": signals,
               "verdict": "VERIFIED" if ok else "NOT_VERIFIED"}
        verified.append(rec) if ok else None
        ev.j({"ev": "PLACE_ATTEMPT", **rec})
        if cycle == 0 and ok:
            # mine the placed block back out for a second cycle
            aim_ring_exact(core, m, P, pitch_now(m, P), 90.0)
            core.run(4, set())
            for _i in range(24):
                core.run(60, {ATTACK_BTN})
                if _i % 4 == 3:
                    wr = L.WorldReader(m)
                    wr.discover()
                if wr.block_id(*target) in (0, None):
                    break
            core.run(120, set())
            ev.j({"ev": "remine_done", "target": target,
                  "wid": wr.block_id(*target)})

    verdict = (f"PLACE_CONFIRMED x{len(verified)}" if verified
               else "FAILED_PLACE_REJECTED")
    rep = {"verdict": verdict, "digs": digs, "verified": verified,
           "hotbar_final": hb,
           "instrument": "engine-sensed: BreakingState @ player+0x6C "
                         "(ticks +0x74, pos +0x78 i32x3, block +0x88) "
                         "per updateBreakingState @0x80013c9c",
           "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(OUT, "report.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)
    ev.j({"ev": "final", "verdict": verdict})
    ev.finish(verdict)
    print("VERDICT:", verdict)
    return 0 if verified else 4


if __name__ == "__main__":
    sys.exit(main())
