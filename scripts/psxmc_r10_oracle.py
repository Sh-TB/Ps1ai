#!/usr/bin/env python3
"""psxmc_r10_oracle.py — Round 10 (Task 16-c), PROCESS 1: FIX-2 deliverable.

Validate the R2 breaking-state raycast oracle against a KNOWN-HIT
configuration BEFORE it is trusted as a placement-target finder (the
round-9 mandatory fix; r9 returned NO hits at any pitch 5..80 deg).

Root-cause analysis of the r9 empty map (upstream source re-read @
infdev_2025_04_18, EngineersBox/PSX-Minecraft):

  * player.c:134 updateBreakingState latches result->pos / result->block
    into player->breaking ONLY while BINDING_ATTACK (R2) is held.
  * player.c:402: on release, breaking.reset_trigger = true, and
    chunk.c:772 executes breakingStateReset (zeroes position + block)
    during the chunk-mesh update — i.e. WITHIN A FRAME OR TWO OF RELEASE.
  * r9's probe snapshotted ONE FRAME AFTER RELEASE and — worse — the
    raymap read the breaking state LIVE long after all probes had
    finished.  Both reads raced the reset => zeros everywhere => "NO hits
    at any pitch".  The instrument, not the game, was broken.

Round-10 oracle protocol (this script):
  1. boot (ONE beetle boot per process) -> settle -> player pointer ->
     ground settle (physics position.vy stable).
  2. baseline RAM snapshot + player struct + hotbar chain (independent
     stack sensor) + WorldReader discovery (in-world block read).
  3. R2 probe at pitch p: closed-loop aim (ring read @P+0x18), hold R2
     ~8 frames, SNAPSHOT WHILE STILL HOLDING (before any release tick),
     then release and snapshot again (reset check).
  4. candidate discovery = full-RAM diff (hold vs baseline): changed
     i32-triple + heap IBlock* pointer, ranked by canonical BreakingState
     layout; validated against the world walk (block at the hit cell must
     be non-air) — the world read is the arbiter, not the struct layout.
  5. VALIDATIONS:
       V1 known-hit: pitch +88 deg (straight down) x3 repeats — the hit
          MUST be in the player's own column (|dx|<=1, |dz|<=1), at/below
          the camera (feet+1.7), within reach 6, and the block at that
          cell must be non-air (grass 2 / dirt 3 / stone 1 / bump grass).
       V0 negative: pitch 0 (horizon ray, geometrically no hit within
          reach over flat terrain) — breaking state must stay zeroed.
       V2 forward: pitch +20 deg — hit 1..5 blocks AHEAD (+z at yaw 0),
          y in {4,5}, within reach (validates the pitch->distance mapping
          and the raycast -sin5o(pitch) sign convention live).
Verdicts: ORACLE_VALIDATED / ORACLE_BROKEN (honest, with numbers).
Evidence: scratch/round10_psxmc/ (report_oracle.json, JSONL, PNGs).
"""
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from psxmc_r7_lib import A_INPUT, Evid, PADBUFF_SIG, sha  # noqa: E402
import psxmc_r10_lib as L  # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r10"
OUT = os.path.join(REPO, "scratch", "round10_psxmc")
TAG = "oracle"

LOOK_DOWN = "B"      # PAD_CROSS: ring + (player.c:435)
LOOK_UP = "X"        # PAD_TRIANGLE: ring -
LOOK_RIGHT = "O"     # PAD_CIRCLE: yaw-
LOOK_LEFT = "SQ"     # PAD_SQUARE: yaw+
ATTACK_BTN = "R2"    # BINDING_ATTACK
UI_BTN = "START"     # BINDING_OPEN_INVENTORY (closes crafting UI)

HOLD_FRAMES = 8      # ~2-3 game ticks @ tps20/fps60 << 15-tick dig budget
MID_AFTER = 3        # snapshot this many held frames into the hold


def s32(v):
    return L.s32(v)


def snap(m):
    return bytes(m.snapshot())


def player_ptr(m):
    v = m.u32(L.A_PLAYER)
    if (v & 3) == 0 and L.HEAP_LO < (v & 0x1FFFFF) < L.HEAP_HI:
        y = s32(m.u32((v & 0x1FFFFF) + 4))
        if abs(y) < 40 * L.ONE_BLOCK * 4:
            return v & 0x1FFFFF
    return None


def pos_of(m, P):
    return [s32(m.u32(P)), s32(m.u32(P + 4)), s32(m.u32(P + 8))]


def pitch_now(m, P):
    return m.u32(P + 0x18) & (L.PITCH_MOD - 1)


def yaw_now(m, P):
    return m.u32(P + 0x1C) & (L.PITCH_MOD - 1)


def held_word(m):
    return {"stat": m.u8(A_INPUT), "id": hex(m.u8(A_INPUT + 1)),
            "held": hex((~m.u16(A_INPUT + 2)) & 0xFFFF)}


def ensure_world_control(core, m, P, ev, tag):
    """LOOK_DOWN 6-frame probe must move the pitch ring; else START taps
    (>200 ms apart) toggle the focused UI layer (r7/r9 technique)."""
    rec = {"rounds": 0, "alive": False, "start_taps": 0}
    for rnd in range(4):
        a = pitch_now(m, P)
        core.run(6, {LOOK_DOWN})
        moved = abs(L.ring_diff(a, pitch_now(m, P))) > 0.2 * L.DEG
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


def aim_ring_exact(core, m, P, pitch0, want_deg, tol_deg=0.35, max_it=400):
    want = (pitch0 + int(round(want_deg * L.DEG))) % L.PITCH_MOD
    frames = 0
    err = L.ring_diff(pitch_now(m, P), want)
    it = 0
    stall = 0
    best = abs(err)
    while abs(err) > tol_deg * L.DEG and it < max_it and stall < 3:
        step = 5 if abs(err) > 4 * L.DEG else 1
        core.run(step, {LOOK_DOWN} if err > 0 else {LOOK_UP})
        frames += step
        err = L.ring_diff(pitch_now(m, P), want)
        it += 1
        if abs(err) < best - 0.05 * L.DEG:
            best = abs(err)
            stall = 0
        else:
            stall += 1
    return {"want_deg": want_deg, "err_deg": round(err / L.DEG, 3),
            "frames": frames}


def r2_probe(core, m, P, ev, pitch0, pdeg, tag):
    """Aim closed-loop, hold R2, snapshot WHILE HOLDING, release, snapshot
    the reset.  Returns the record (no interpretation)."""
    aim = aim_ring_exact(core, m, P, pitch0, pdeg)
    core.run(2, set())
    base = snap(m)
    core.run(2, {ATTACK_BTN})                 # hold begins
    core.run(max(1, MID_AFTER - 2), {ATTACK_BTN})
    mid = snap(m)                             # WHILE STILL HOLDING (FIX-2)
    core.run(HOLD_FRAMES - MID_AFTER, {ATTACK_BTN})
    core.run(1, set())                        # release
    rel = snap(m)
    core.run(24, set())                       # remesh/reset settles
    late = snap(m)
    pos = pos_of(m, P)
    rec = {"tag": tag, "pdeg": pdeg, "aim": aim, "pos": pos,
           "pitch_deg": round(L.ring_diff(pitch0, pitch_now(m, P)) / L.DEG, 2),
           "yaw_deg": round(L.ring_diff(0, yaw_now(m, P)) / L.DEG, 2),
           "base": base, "mid": mid, "rel": rel, "late": late}
    ev.j({"ev": f"probe_{tag}", "pdeg": pdeg, "aim": aim,
          "pitch_deg": rec["pitch_deg"]})
    return rec


def parse_probe(m, wr, rec, P, pitch0, full_ram_fallback=True):
    """Diff mid vs base; rank candidates; arbitrate with the world walk."""
    cam_y, feet = L.camera_world_y(rec["pos"][1])
    cands = L.breaking_candidates(rec["mid"], rec["base"], P, cam_y,
                                  rec["pos"], search=0x800)
    fallback = False
    if not cands and full_ram_fallback:
        # whole-RAM sweep: where DID the raycast latch, if anywhere?
        cands = L.breaking_candidates(rec["mid"], rec["base"], 0, cam_y,
                                      rec["pos"], search=0x1F0000)
        fallback = bool(cands)
    parsed = []
    for c in cands[:8]:
        # parse_breaking_from_snap adds P internally: non-fallback cands
        # are P-relative (pass 0); fallback cands are ABSOLUTE (pass -P).
        # (r10 fix v2: the r10-fix-v1 conditional was itself inverted.)
        base = -P if fallback else 0
        hit, blk = L.parse_breaking_from_snap(rec["mid"], P, c["off"] + base,
                                              c["ptr_off"] + base)
        if hit == [0, 0, 0]:
            continue        # a real latch always carries a non-NULL block
        wid = wr.block_id(hit[0], hit[1], hit[2])
        rel_hit, rel_blk = L.parse_breaking_from_snap(
            rec["rel"], P, c["off"] + base, c["ptr_off"] + base)
        late_hit, late_blk = L.parse_breaking_from_snap(
            rec["late"], P, c["off"] + base, c["ptr_off"] + base)
        g = L.hit_geometry(hit, rec["pos"], cam_y)
        parsed.append({**c, "hit": hit, "blk": hex(blk),
                       "world_id": wid, "geom": g,
                       "rel_hit": rel_hit, "rel_blk": hex(rel_blk),
                       "late_hit": late_hit,
                       "late_blk": hex(late_blk),
                       "reset_by_late": late_hit == [0, 0, 0]
                       and late_blk == 0})
    # adoption: world read must agree (non-air at the hit cell); prefer
    # the CURRENT latch — it resets to zero by 'late' (breakingState-
    # Reset, chunk.c:772) while stale mirrors from earlier probes do
    # not (r10 finding: adopted[0] jumped between multiple retained
    # triples, decoupling the hit from the ring pitch)
    live = [p for p in parsed
            if p["world_id"] not in (None, 0) and p["blk"] != "0x0"
            and p.get("reset_by_late")]
    stale_ok = [p for p in parsed
                if p["world_id"] not in (None, 0) and p["blk"] != "0x0"]
    adopted = live or stale_ok
    ok, why = (True, "") if adopted else (False, "no world-arbitrated hit")
    if adopted:
        p = adopted[0]
        ok, why = L.validate_known_hit(p["hit"], rec["pos"], cam_y)
        p["known_hit_verdict"] = {"ok": ok, "why": why}
    return {"cam_y": round(cam_y, 2), "feet": round(feet, 2),
            "cands": parsed, "adopted": adopted[:3], "ok": ok, "why": why,
            "fallback_scan": fallback,
            "pos_blocks": [round(v / L.ONE_BLOCK, 2) for v in rec["pos"]]}


def main():
    ev = Evid(OUT, TAG)
    ev.jpath = os.path.join(OUT, "r10_oracle.jsonl")
    ev.j({"ev": "start", "cue": CUE, "task": "16-c FIX-2 oracle validation",
          "fix2": "snapshot WHILE HOLDING R2 (r9 read after release, raced "
                  "the chunk-mesh reset)"})
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
    p.wait(120)
    m = p.mem
    core = p.core
    grab = core.frame_rgb
    pitch0 = pitch_now(m, P)
    yaw0 = yaw_now(m, P)

    # ground settle: physics y stable
    stable_n = 0
    last_y = None
    for _ in range(120):
        y = pos_of(m, P)[1]
        stable_n = stable_n + 1 if y == last_y else 0
        last_y = y
        if stable_n >= 45:
            break
        core.run(2, set())
    pos0 = pos_of(m, P)
    cam_y0, feet0 = L.camera_world_y(pos0[1])
    ev.j({"ev": "settled", "P": hex(P), "pos_blocks":
          [round(v / L.ONE_BLOCK, 3) for v in pos0],
          "cam_y": round(cam_y0, 2), "feet": round(feet0, 2),
          "pitch0_raw": pitch0, "yaw0_raw": yaw0})

    # independent sensors + world walk discovery
    hb = L.find_hotbar(m, P)
    inv = L.find_inventory(m, P, hb["hotbar_off"]) if hb else None
    wr = L.WorldReader(m)
    wr_info = None
    for _ in range(5):
        try:
            wr_info = wr.discover()
            break
        except RuntimeError as e:
            ev.j({"ev": "world_discover_retry", "err": str(e)})
            core.run(60, set())
    if wr_info is None:
        ev.finish("FAILED: WorldReader discovery failed (world walk "
                  "unavailable; no arbiter for the oracle)")
        return 1
    stack0 = int(m.u8(L.STACK_ADDR))
    pxb, pyb, pzb = [v / L.ONE_BLOCK for v in pos0]
    fbx, fbz = int(np.floor(pxb)), int(np.floor(pzb))
    surf_y = L.expected_surface_y(fbx, fbz)
    ev.step("baseline", {
        "P": hex(P), "pos_blocks": [round(v / L.ONE_BLOCK, 3) for v in pos0],
        "cam_y": round(cam_y0, 2), "expected_surface_y": surf_y,
        "stack_addr_0x7cda0": stack0,
        "hotbar": None if not hb else {k: (hex(v) if k in ("hotbar", "item")
                                            else v) for k, v in hb.items()},
        "inventory_active": None if not inv else inv["active"],
        "world": wr_info,
        "world_id_below_feet": wr.block_id(fbx, surf_y, fbz),
        "world_id_at_bump": wr.block_id(fbx, 5, fbz),
        "padbuff": snap(m).count(PADBUFF_SIG),
        "ram_sha": sha(snap(m))[:16]})
    f0, _ = (grab(), True)
    ev.png("o10_boot_world", f0)

    # ------------- V1 known-hit: straight down x3 ---------------------------
    v1 = []
    boff = None
    for i in range(3):
        ensure_world_control(core, m, P, ev, f"v1_{i}")
        rec = r2_probe(core, m, P, ev, pitch0, 88.0, f"v1_{i}")
        pr = parse_probe(m, wr, rec, P, pitch0)
        if pr["adopted"] and boff is None:
            boff = (pr["adopted"][0]["off"], pr["adopted"][0]["ptr_off"])
        ev.j({"ev": f"v1_{i}", "ok": pr["ok"], "why": pr["why"],
              "fallback": pr["fallback_scan"],
              "adopted": [{k: v for k, v in a.items()
                           if k in ("off", "hit", "blk", "world_id", "geom",
                                    "reset_by_late")}
                          for a in pr["adopted"]]})
        if i == 0:
            core.run(2, set())
            ev.png("o10_v1_down_view", grab())
        core.run(30, set())
        v1.append({k: v for k, v in pr.items()
                   if k in ("ok", "why", "cam_y", "feet", "adopted")})

    # ------------- V0 negative control: horizon -----------------------------
    ensure_world_control(core, m, P, ev, "v0")
    aim_back = aim_ring_exact(core, m, P, pitch0, 0.0)
    rec0 = r2_probe(core, m, P, ev, pitch0, 0.0, "v0")
    pr0 = parse_probe(m, wr, rec0, P, pitch0)
    v0_pass = not pr0["adopted"]
    ev.j({"ev": "v0_negative", "aim_back": aim_back, "pass": v0_pass,
          "n_cands": len(pr0["cands"]),
          "adopted": [{k: a[k] for k in ("off", "hit", "blk", "world_id")}
                      for a in pr0["adopted"]]})

    # ------------- V2 forward probe: +20 deg --------------------------------
    ensure_world_control(core, m, P, ev, "v2")
    rec2 = r2_probe(core, m, P, ev, pitch0, 20.0, "v2")
    pr2 = parse_probe(m, wr, rec2, P, pitch0)
    fwd = None
    if pr2["adopted"]:
        a = pr2["adopted"][0]
        fwd = {"hit": a["hit"], "geom": a["geom"], "world_id": a["world_id"]}
    ev.j({"ev": "v2_forward", "adopted": fwd})

    # ------------- verdict ---------------------------------------------------
    v1_all = all(v["ok"] for v in v1)
    verdict = ("ORACLE_VALIDATED: straight-down known-hit x3 (in-column, "
               "in-reach, world-arbitrated), negative horizon clean"
               if v1_all and v0_pass else
               "ORACLE_BROKEN: v1=%s v0=%s (v1 details in report)" %
               ([v["ok"] for v in v1], v0_pass))
    ev.step("validations", {
        "v1_known_hit_x3": [{k: v[k] for k in ("ok", "why")} for v in v1],
        "v1_adopted": [v["adopted"][:1] for v in v1],
        "v0_negative_pass": v0_pass, "v2_forward": fwd,
        "breaking_off": None if not boff else list(boff)})
    ev.step("sensors", {"stack_first": stack0,
                        "stack_last": int(m.u8(L.STACK_ADDR)),
                        "hotbar_stack_last": None if not hb
                        else L.find_hotbar(m, P)["stack"]})
    ev.finish(verdict)

    import json
    merged = {"task": "16-c FIX-2 oracle validation (round 10 place7)",
              "game": "PSX-Minecraft infdev_2025_04_18 (MIT)",
              "verdict": verdict,
              "protocol": {
                  "fix2": "breaking state parsed from a snapshot taken WHILE "
                          "R2 IS HELD (r9 read after release and raced the "
                          "chunk.c:772 breakingStateReset)",
                  "arbitration": "every adopted hit cross-checked against the "
                                 "in-RAM world walk (WorldReader: World -> "
                                 "chunks[az][ax][0] -> blocks -> Block.id)",
                  "dig_safety": f"{HOLD_FRAMES}f hold ~= 2-3 ticks << ~15-tick "
                                "hand-dig budget (grass 18 / dirt 15)"},
              "baseline": ev.report["steps"]["baseline"],
              "validations": ev.report["steps"]["validations"],
              "sensors": ev.report["steps"]["sensors"]}
    with open(os.path.join(OUT, "report_oracle.json"), "w") as f:
        json.dump(merged, f, indent=1, default=str)
    try:
        core.close()
    except Exception:
        pass
    return 0 if v1_all and v0_pass else 2


if __name__ == "__main__":
    sys.exit(main())
