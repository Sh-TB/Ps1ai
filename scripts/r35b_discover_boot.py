#!/usr/bin/env python3
"""r35b_discover_boot.py — R35-B boot 1 (of 3 max): BuzzyBee entity-map
live verification + dynamics probe + policy rehearsal + idle baseline +
savestate checkpoint for boot-2 bot variants.

Entity map is SOURCE-derived (prior dead attempt read github.com/NDR008/
BuzzyBee main.c + BuzzyBee.map — see r35b_lib.py header). This boot
VERIFIES it live against the patched NTSC build and measures dynamics.

Phases (event-driven; frame ceilings are honesty bounds):
  A boot -> settle 900f -> title gs0 -> START -> gs1 -> score>=3 ->
    CHECKPOINT core.serialize() -> scratch/r35b/state_r35b_gs1.bin
  V struct checks: p.x==15360 p.xv==0 e.xv==-1536 r0.xv==-1024
    f0==r0+(21,-29)*1024 hp in [5900,5999] anim img_list anchors
  D dynamics (restore): 40f free fall; tap; 30f; tap; 30f; tap; 30f
    -> gravity/f, flap y_vel delta, slam-bug guard window
  R policy rehearsal (restore, 900f): full bot policy from r35b_lib,
    JSONL per iteration, wasp passes classified dodge/hit, flower
    pickups with mode evidence, event snaps
  I idle baseline (restore, <=2300f): no input until gs5; death frame,
    score, best; then auto-return-to-title watch (<=600f)
Final: metrics_r35b_b1.json; restore checkpoint; sync-back if mirrored.

Boot ledger: fresh r35b ledger, boot 1 of max 3, appended PRE-RUN.
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
import r35b_lib as L  # noqa: E402

OUT = L.OUT
R, log, dump = L.make_logger(
    OUT, "boot_log_r35b_b1.json", "r35b.b1")
T0 = time.time()

# ---- boot ledger PRE-RUN ------------------------------------------------
led = L.ledger_use(1, "r35b_discover_boot.py",
                   note="boot 1: entity map verify + dynamics + rehearsal "
                        "+ idle baseline + checkpoint")
log("ledger", count=led["count"], out=OUT, mirror=L.MIRROR_NOTE)

bee = L.Bee("ws_r35b")
av = bee.load_game()
log("boot", core=bee.core.core_name, av=av,
    ram_mb=round(len(bee.ram) / 1e6, 1))


def flog(rec_f, ev, **kw):
    log(ev, f=rec_f, **kw)


# ---- A: settle -> title -> START -> checkpoint --------------------------
bee.run(900, set())
st = bee.state(full=True)
log("A_title", gs=st["gs"], score=st["score"], best=st["best"])
bee.snap("b1_A_title", R)
assert st["gs"] == 0, f"expected title gs0, got {st['gs']}"

bee.set_buttons("START")
for _ in range(40):
    bee.run_frame()
bee.set_buttons(set())
gs1 = None
for _ in range(200):
    bee.run(1, set())
    if bee.i32(L.GS) == 1:
        gs1 = bee.frames_run
        break
st = bee.state()
log("A_run1_started", f=bee.frames_run, gs1_frame=gs1, gs=st["gs"],
    hp=st["hp"])
assert st["gs"] == 1, f"expected gs1 after START, got {st['gs']}"
bee.snap("b1_A_run1", R)

sc = -1
for _ in range(300):
    bee.run(1, set())
    sc = bee.i32(L.SCORE)
    if sc >= 3:
        break
st = bee.state()
log("A_pre_checkpoint", f=bee.frames_run, score=sc, hp=st["hp"])
CKPT = bee.serialize()
open(L.CKPT_PATH, "wb").write(CKPT)
log("A_checkpoint_saved", bytes=len(CKPT), score=sc, hp=st["hp"],
    f_abs=bee.frames_run, path=L.CKPT_PATH)
bee.snap("b1_A_checkpoint", R)

# ---- V: entity-map verification -----------------------------------------
bee.unserialize(CKPT)
bee.run(2, set())
st = bee.state(full=True)
C = {
    "player_x_const_15360": st["p"]["x"] == 15 * L.FACTOR,
    "player_xv_zero": st["p"]["xv"] == 0,
    "enemy_xv_minus1536": st["e"]["xv"] == -1536,
    "rock0_xv_minus1024": st["r0"]["xv"] == -1024,
    "rock1_xv_minus1024": st["r1"]["xv"] == -1024,
    "rock2_xv_minus1024": st["r2"]["xv"] == -1024,
    "flower0_follows_rock0": (st["f0"]["x"] - st["r0"]["x"]
                              == 21 * L.FACTOR and
                              st["f0"]["y"] - st["r0"]["y"]
                              == -29 * L.FACTOR),
    "flower1_follows_rock1": (st["f1"]["x"] - st["r1"]["x"]
                              == 21 * L.FACTOR and
                              st["f1"]["y"] - st["r1"]["y"]
                              == -29 * L.FACTOR),
    "flower2_follows_rock2": (st["f2"]["x"] - st["r2"]["x"]
                              == 21 * L.FACTOR and
                              st["f2"]["y"] - st["r2"]["y"]
                              == -29 * L.FACTOR),
    "health_near_init_5999": 5900 <= st["hp"] <= 5999,
    "il_player_mainPlayerL": st["p"]["il"] == L.IL_PLAYER,
    "il_enemy_enemiesL": st["e"]["il"] == L.IL_ENEMY,
    "gs_is_1": st["gs"] == 1,
}
log("V_checks", f=bee.frames_run, **C,
    p={k: st["p"][k] for k in ("x", "y", "xv", "yv", "il")},
    e={k: st["e"][k] for k in ("x", "y", "xv", "yv", "il")},
    r0={k: st["r0"][k] for k in ("x", "y", "xv", "yv", "il")},
    f0={k: st["f0"][k] for k in ("x", "y", "xv", "yv", "il")},
    hp=st["hp"], score=st["score"])
MAP_OK = bool(all(C.values()))
log("V_map_ok", map_ok=MAP_OK,
    failed=[k for k, v in C.items() if not v])

# ---- D: dynamics probe ---------------------------------------------------
bee.unserialize(CKPT)
wD, _ = L.jl_writer(OUT, "frames_b1_dyn.jsonl")
wD({"ph": "D", "f": bee.frames_run, **bee.obs()})
grav_samples, tap_deltas = [], []
bvy_min = 0
bee.run(2, set())
v0, y0 = bee.obj(L.PLAYER)["yv"], bee.obj(L.PLAYER)["y"]
bee.run(10, set())
v1, y1 = bee.obj(L.PLAYER)["yv"], bee.obj(L.PLAYER)["y"]
grav_samples.append((v1 - v0) / 10)
wD({"ph": "D", "f": bee.frames_run, "by": L.px(y1), "bvy": v1})
# tap response: record y_vel across a 2f hold
for t_i in range(3):
    pre = bee.obj(L.PLAYER)["yv"]
    bee.set_buttons("B")
    for k in range(2):
        bee.run_frame()
        post = bee.obj(L.PLAYER)["yv"]
        bvy_min = min(bvy_min, post)
        wD({"ph": "D", "f": bee.frames_run, "by": L.px(bee.obj(L.PLAYER)["y"]),
            "bvy": post, "tap": t_i})
    bee.set_buttons(set())
    tap_deltas.append(post - pre)
    bee.run(28, set())
    wD({"ph": "D", "f": bee.frames_run, **bee.obs()})
GRAV = round(sum(grav_samples) / len(grav_samples))
FLAP_D = tap_deltas[0]
log("D_dynamics", gravity_per_f=GRAV, flap_yv_delta=tap_deltas,
    bvy_floor_seen=bvy_min)
bee.snap("b1_D_after_taps", R)

# ---- R: policy rehearsal (restore, 900f) ---------------------------------
bee.unserialize(CKPT)
wR, _ = L.jl_writer(OUT, "frames_b1_rehearsal.jsonl")
sticky = {}
passes, pickups, hits = [], [], []
in_pass, hit_in_pass, pass_start, pass_min_dx = False, False, None, 999
prev_hp = bee.i32(L.HEALTH)
f0_abs = bee.frames_run
flaps = 0
for it in range(900):
    s = bee.obs()
    flap, target, mode = L.bot_policy(s, sticky)
    rec = {"ph": "R", "f": bee.frames_run, "mode": mode, "tgt": target,
           "by": s["by"], "bvy": s["bvy"], "e": s["e"], "fl": s["fl"]}
    if flap:
        bee.set_buttons("B")
        for _k in range(2):
            bee.run_frame()
            rec2 = dict(rec, f=bee.frames_run, tap=1)
            rec2["by"] = L.px(bee.obj(L.PLAYER)["y"])
            rec2["bvy"] = bee.obj(L.PLAYER)["yv"]
            wR(rec2)
        bee.set_buttons(set())
        bee.run(1, set())
        flaps += 1
        rec["f_end"] = bee.frames_run
    else:
        bee.run(1, set())
        rec["f_end"] = bee.frames_run
    s2 = bee.obs()
    rec.update(by=s2["by"], bvy=s2["bvy"], e=s2["e"], fl=s2["fl"])
    wR(rec)
    ex, ey = s2["e"][0], s2["e"][1]
    if L.PASS_END_X < ex <= L.ENGAGE_X:
        if not in_pass:
            in_pass, hit_in_pass = True, False
            pass_start, pass_min_dx = bee.frames_run, 999
        pass_min_dx = min(pass_min_dx, max(ex - L.BEE_X2, ey - (s2["by"] + L.BEE_H)))
    elif in_pass:
        in_pass = False
        passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                       "hit": hit_in_pass, "min_dx": pass_min_dx})
    hp_now = bee.i32(L.HEALTH)
    dh = hp_now - prev_hp
    prev_hp = hp_now
    if dh <= -1000:
        hit_in_pass = True
        hits.append({"f": bee.frames_run, "dh": dh, "by": s2["by"],
                     "bvy": s2["bvy"], "e": s2["e"], "mode": mode,
                     "side": sticky.get("side")})
        log("R_enemy_edge", **hits[-1])
        bee.snap("b1_R_hit", R)
    elif dh >= 900:
        pickups.append({"f": bee.frames_run, "dh": dh, "by": s2["by"],
                        "fl": s2["fl"], "mode": mode, "tgt": target})
        log("R_flower_edge", **pickups[-1])
        bee.snap("b1_R_flower", R)
    if bee.i32(L.GS) != 1:
        break
if in_pass:
    passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                   "hit": hit_in_pass, "min_dx": pass_min_dx})
dodges = [p for p in passes if not p["hit"]]
st = bee.state()
log("R_done", f=bee.frames_run, frames=bee.frames_run - f0_abs,
    flaps=flaps, passes=len(passes), dodges=len(dodges), hits=len(hits),
    pickups=len(pickups), gs=st["gs"], score=st["score"], hp=st["hp"])
dodged_passes = len(dodges)
hit_count = len(hits)
pick_count = len(pickups)
rehearsal_score_end = st["score"]
rehearsal_frames = bee.frames_run - f0_abs

# ---- I: idle baseline (restore, <=2300f) ---------------------------------
bee.unserialize(CKPT)
wI, _ = L.jl_writer(OUT, "frames_b1_idle.jsonl")
prev_hp = bee.i32(L.HEALTH)
f0_abs = bee.frames_run
edges = []
death_f = None
for i in range(2300):
    bee.run(1, set())
    hp_now = bee.i32(L.HEALTH)
    dh = hp_now - prev_hp
    prev_hp = hp_now
    if i % 15 == 0 or abs(dh) > 100:
        s = bee.obs()
        wI({"ph": "I", "f": bee.frames_run, "by": s["by"], "bvy": s["bvy"],
            "hp": hp_now, "score": bee.i32(L.SCORE), "e": s["e"]})
    if dh <= -1000 or dh >= 900:
        s = bee.obs()
        edges.append({"f": bee.frames_run, "dh": dh, "by": s["by"],
                      "e": s["e"]})
        log("I_health_edge", **edges[-1])
    if bee.i32(L.GS) == 5:
        death_f = bee.frames_run
        break
st = bee.state()
IDLE = {"death_f": death_f, "survival_frames": (death_f - f0_abs) if death_f
        else None, "score": st["score"], "best": st["best"],
        "hp": st["hp"], "edges": edges, "gs": st["gs"]}
log("I_idle_end", **{k: v for k, v in IDLE.items() if k != "edges"},
    n_edges=len(edges))
bee.snap("b1_I_end", R)

ret_f = None
if st["gs"] == 5:
    for _ in range(600):
        bee.run(1, set())
        if bee.i32(L.GS) == 0:
            ret_f = bee.frames_run
            break
    log("I_auto_return", f=bee.frames_run, ret_f=ret_f,
        gs=bee.i32(L.GS), best=bee.i32(L.BEST))
    bee.snap("b1_I_title", R)

# ---- metrics -------------------------------------------------------------
metrics = {
    "map_ok": MAP_OK,
    "checks": C,
    "dynamics": {"gravity_per_f": GRAV, "flap_yv_delta": tap_deltas},
    "idle_baseline": IDLE,
    "rehearsal": {"frames": rehearsal_frames, "flaps": flaps,
                  "passes": len(passes), "dodges": dodged_passes,
                  "enemy_hits": hit_count, "flower_pickups": pick_count,
                  "score_end": rehearsal_score_end,
                  "pass_detail": passes},
    "checkpoint": L.CKPT_PATH,
}
json.dump(metrics, open(os.path.join(OUT, "metrics_r35b_b1.json"), "w"),
          indent=1, default=str)
log("b1_verdict", map_ok=MAP_OK,
    idle_score=IDLE["score"], idle_survival=IDLE["survival_frames"],
    rehearsal_dodges=dodged_passes, rehearsal_hits=hit_count,
    rehearsal_pickups=pick_count)
dump()
sb = L.sync_back()
if sb:
    log("sync_back", note=sb)
print("[r35b.b1] DONE frames=", bee.frames_run,
      "wall=", round(time.time() - T0, 1), flush=True)
