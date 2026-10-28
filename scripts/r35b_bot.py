#!/usr/bin/env python3
"""r35b_bot.py — R35-B boot 2 (of 3 max): the BuzzyBee BOT RUN.

Boot fresh (boot 2 pre-run in ledger), restore the boot-1 gs1 checkpoint
(state_r35b_gs1.bin — restores are NOT boots), then run predictive bot
variants until death or a 4000f cap:

  variant A: bot_policy2(engage=150, margin=16, flower_hi=160, hover=95)
  variant B (only if A dies < 1800f): engage=190, margin=20,
             flower_hi=200, hover=130 (earlier engage, wider margins)

Policy (r35b_lib.bot_policy2): predictive wasp dodge (bounce-simulated
y at contact-x entry, committed side with room check), flower seek (bee
center -> flower center), hover fallback. Flap = CROSS tap 2f, only when
bvy > -3000 (slam-down bug guard: post-tap y_vel > -6072 > -6144).

Causal metrics:
  (a) dodge: wasp pass (ex in (-41, engage]) with NO -1500/-1503 edge;
      per-pass min separation logged
  (b) pickup: +997/+991 edge where the flower that jumped to x<=-50 was
      the flower-mode target (mode=="flower") -> caused-by-approach
  (c) survival frames + score vs boot-1 idle baseline (997f / score 1000)
  (d) PNG chain every 200f + event snaps

Outputs: frames_b2_<variant>.jsonl, metrics_r35b_b2.json, PNG shots.
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
import r35b_lib as L  # noqa: E402

OUT = L.OUT
R, log, dump = L.make_logger(OUT, "boot_log_r35b_b2.json", "r35b.b2")
T0 = time.time()

led = L.ledger_use(2, "r35b_bot.py",
                   note="boot 2: bot variants from boot-1 checkpoint "
                        "(restores are not boots)")
log("ledger", count=led["count"], out=OUT, mirror=L.MIRROR_NOTE)

bee = L.Bee("ws_r35b")
av = bee.load_game()
log("boot", core=bee.core.core_name, av=av)

bee.run(900, set())
CKPT = open(L.CKPT_PATH, "rb").read()
bee.unserialize(CKPT)
st = bee.state()
assert st["gs"] == 1, f"checkpoint restore: expected gs1, got {st['gs']}"
log("checkpoint_restored", f=bee.frames_run, score=st["score"],
    hp=st["hp"], ckpt_bytes=len(CKPT))
bee.snap("b2_restored", R)

BASE = json.load(open(os.path.join(OUT, "metrics_r35b_b1.json")))
IDLE = BASE["idle_baseline"]
log("baseline", idle_score=IDLE["score"],
    idle_survival=IDLE["survival_frames"], idle_edges=len(IDLE["edges"]))


def run_variant(label, kw, cap=4000, snap_every=200):
    bee.unserialize(CKPT)
    w, _ = L.jl_writer(OUT, f"frames_b2_{label}.jsonl")
    sticky = {}
    passes, hits, pickups = [], [], []
    in_pass = False
    hit_in_pass = False
    pass_start, pass_min_sep = None, 10 ** 9
    prev_hp = bee.i32(L.HEALTH)
    prev_fl = bee.obs()["fl"]
    f_start = bee.frames_run
    flaps = 0
    next_snap = bee.frames_run + snap_every
    death_f = None
    while bee.frames_run - f_start < cap:
        s = bee.obs()
        flap, target, mode = L.bot_policy2(s, sticky, **kw)
        rec = {"ph": label, "f": bee.frames_run, "mode": mode,
               "tgt": round(target, 1), "side": sticky.get("side"),
               "by": s["by"], "bvy": s["bvy"], "e": s["e"], "fl": s["fl"]}
        f0_it = bee.frames_run
        if flap:
            bee.set_buttons("B")
            for _k in range(2):
                bee.run_frame()
                bee.obj(L.PLAYER)  # keep ram hot
            bee.set_buttons(set())
            bee.run(1, set())
            flaps += 1
        else:
            bee.run(1, set())
        s2 = bee.obs()
        rec["f_end"] = bee.frames_run
        rec.update(by=s2["by"], bvy=s2["bvy"], e=s2["e"], fl=s2["fl"])
        w(rec)
        # ---- wasp pass accounting
        ex, ey = s2["e"][0], s2["e"][1]
        if L.PASS_END_X < ex <= kw["engage"]:
            if not in_pass:
                in_pass, hit_in_pass = True, False
                pass_start, pass_min_sep = bee.frames_run, 10 ** 9
            dx_gap = ex - L.BEE_X2
            dy_gap = abs(s2["by"] - ey)
            pass_min_sep = min(pass_min_sep, max(dx_gap, dy_gap - 13))
        elif in_pass:
            in_pass = False
            passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                           "hit": hit_in_pass, "min_sep": pass_min_sep})
        # ---- health edges
        hp_now = bee.i32(L.HEALTH)
        dh = hp_now - prev_hp
        prev_hp = hp_now
        if dh <= -1000:
            hit_in_pass = True
            hits.append({"f": bee.frames_run, "dh": dh, "by": s2["by"],
                         "bvy": s2["bvy"], "e": s2["e"], "mode": mode,
                         "side": sticky.get("side")})
            log(f"{label}_enemy_edge", **hits[-1])
            bee.snap(f"b2_{label}_hit", R)
        elif dh >= 900:
            picked = [i for i in range(3)
                      if prev_fl[i][0] > 0 and s2["fl"][i][0] <= -49]
            caused = bool(mode == "flower" and picked)
            pickups.append({"f": bee.frames_run, "dh": dh, "by": s2["by"],
                            "fl": s2["fl"], "mode": mode, "tgt": target,
                            "picked_idx": picked, "caused": caused})
            log(f"{label}_flower_edge", **pickups[-1])
            bee.snap(f"b2_{label}_flower", R)
        prev_fl = s2["fl"]
        if in_pass is False and hit_in_pass:
            hit_in_pass = False
        # ---- png chain + death
        if bee.frames_run >= next_snap:
            bee.snap(f"b2_{label}_gameplay", R)
            next_snap += snap_every
        if bee.i32(L.GS) != 1:
            death_f = bee.frames_run
            break
    if in_pass:
        passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                       "hit": hit_in_pass, "min_sep": pass_min_sep})
    st = bee.state()
    m = {
        "variant": label, "kw": kw,
        "survival_frames": (death_f - f_start) if death_f \
            else bee.frames_run - f_start,
        "death": death_f is not None,
        "gs": st["gs"], "score": st["score"], "hp": st["hp"],
        "best": st["best"], "flaps": flaps,
        "passes": len(passes), "dodges": sum(1 for p in passes
                                             if not p["hit"]),
        "enemy_hits": len(hits), "hit_detail": hits,
        "pass_detail": passes,
        "pickups_total": len(pickups),
        "pickups_caused": sum(1 for p in pickups if p["caused"]),
        "pickup_detail": pickups,
        "frames_jsonl": f"frames_b2_{label}.jsonl",
    }
    m["vs_idle"] = {
        "survival_x": round(m["survival_frames"] /
                            max(1, IDLE["survival_frames"] or 1), 2),
        "score_x": round(m["score"] / max(1, IDLE["score"]), 2),
    }
    log(f"{label}_done", **{k: v for k, v in m.items()
                            if k not in ("hit_detail", "pass_detail",
                                         "pickup_detail")})
    if death_f:
        bee.snap(f"b2_{label}_death", R)
        for _ in range(500):
            bee.run(1, set())
            if bee.i32(L.GS) == 0:
                break
        bee.snap(f"b2_{label}_gameover_return", R)
    return m


# ---- variant A ----------------------------------------------------------
mA = run_variant("A", {"engage": 150, "margin": 16, "flower_hi": 160,
                       "hover_y": 95})

results = {"A": mA}
chosen = "A"
if mA["death"] and mA["survival_frames"] < 1800:
    log("variant_B_triggered", reason="A died early",
        a_survival=mA["survival_frames"])
    mB = run_variant("B", {"engage": 190, "margin": 20, "flower_hi": 200,
                           "hover_y": 130})
    results["B"] = mB
    chosen = ("B" if (mB["survival_frames"], mB["score"]) >
              (mA["survival_frames"], mA["score"]) else "A")

metrics = {
    "boot": 2, "checkpoint": L.CKPT_PATH,
    "idle_baseline": {"survival_frames": IDLE["survival_frames"],
                      "score": IDLE["score"],
                      "enemy_edges": len(IDLE["edges"])},
    "variants": results, "chosen": chosen,
    "verdict_inputs": {
        "dodges": results[chosen]["dodges"],
        "enemy_hits": results[chosen]["enemy_hits"],
        "pickups_caused": results[chosen]["pickups_caused"],
        "pickups_total": results[chosen]["pickups_total"],
        "survival_frames": results[chosen]["survival_frames"],
        "score": results[chosen]["score"],
    },
}
json.dump(metrics, open(os.path.join(OUT, "metrics_r35b_b2.json"), "w"),
          indent=1, default=str)
log("b2_verdict", chosen=chosen, **metrics["verdict_inputs"])
dump()
sb = L.sync_back()
if sb:
    log("sync_back", note=sb)
print("[r35b.b2] DONE frames=", bee.frames_run,
      "wall=", round(time.time() - T0, 1), flush=True)
