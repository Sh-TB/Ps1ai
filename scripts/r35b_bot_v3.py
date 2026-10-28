#!/usr/bin/env python3
"""r35b_bot_v3.py — R35-B boot 3 (of 3 max): FINAL bot run.

Boot fresh (boot 3 pre-run in ledger), restore boot-1 gs1 checkpoint
(restores are NOT boots), run bot_policy3 variants until death or 4000f:

  variant C: engage=170, margin=14, flower_hi=170, hover=95
  variant D (only if C has <5 close dodges or <2 causal pickups):
             engage=200, margin=18, flower_hi=200, hover=110

policy3 (r35b_lib) fixes measured from boot-2 forensics:
  - above-side preferred; below-side taps arc-checked (no more chaining
    the bee up into the wasp contact band)
  - emergency nearest-exit when inside the band; vy-flip re-choose
  - flower window fx>0 (boot-2's fx>37 dropped targets on final approach)

Causal metrics:
  (a) dodge = wasp pass (ex in (-41, engage]) with NO -1503 edge;
      close dodge = min_sep < 30px
  (b) caused pickup = +997 edge, mode=="flower", picked flower was the
      seek target with seek duration >= 20f
  (c) survival frames + score vs idle baseline (997f / score 1000)
  (d) PNG chain every 300f (event snaps capped at 2 each)
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
import r35b_lib as L  # noqa: E402

OUT = L.OUT
R, log, dump = L.make_logger(OUT, "boot_log_r35b_b3.json", "r35b.b3")
T0 = time.time()

led = L.ledger_use(3, "r35b_bot_v3.py",
                   note="boot 3 (final): policy3 bot variants from boot-1 "
                        "checkpoint; restores are not boots")
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
    hp=st["hp"])
bee.snap("b3_restored", R)

BASE = json.load(open(os.path.join(OUT, "metrics_r35b_b1.json")))
IDLE = BASE["idle_baseline"]

SEEK_MIN_F = 20


def seek_target_idx(s, kw):
    best = None
    for i, (fx, fy) in enumerate(s["fl"]):
        if 0 < fx <= kw["flower_hi"] and (best is None or fx < best[1]):
            best = (i, fx)
    return best[0] if best else None


def run_variant(label, kw, cap=4000, snap_every=300, max_event_snaps=2):
    bee.unserialize(CKPT)
    w, _ = L.jl_writer(OUT, f"frames_b3_{label}.jsonl")
    sticky = {}
    passes, hits, pickups = [], [], []
    seek = {"idx": None, "since": None}
    n_flower_snap = n_hit_snap = 0
    in_pass = hit_in_pass = False
    pass_start, pass_min_sep = None, 10 ** 9
    prev_hp = bee.i32(L.HEALTH)
    prev_fl = bee.obs()["fl"]
    f_start = bee.frames_run
    flaps = 0
    next_snap = bee.frames_run + snap_every
    death_f = None
    while bee.frames_run - f_start < cap:
        s = bee.obs()
        flap, target, mode = L.bot_policy3(s, sticky, **kw)
        # seek bookkeeping for causal pickup attribution
        if mode == "flower":
            idx = seek_target_idx(s, kw)
            if seek["idx"] != idx:
                seek["idx"], seek["since"] = idx, bee.frames_run
        else:
            seek["idx"], seek["since"] = None, None
        rec = {"ph": label, "f": bee.frames_run, "mode": mode,
               "tgt": round(target, 1), "side": sticky.get("side"),
               "by": s["by"], "bvy": s["bvy"], "e": s["e"], "fl": s["fl"]}
        if flap:
            bee.set_buttons("B")
            for _k in range(2):
                bee.run_frame()
            bee.set_buttons(set())
            bee.run(1, set())
            flaps += 1
        else:
            bee.run(1, set())
        s2 = bee.obs()
        rec["f_end"] = bee.frames_run
        rec.update(by=s2["by"], bvy=s2["bvy"], e=s2["e"], fl=s2["fl"])
        w(rec)
        ex, ey = s2["e"][0], s2["e"][1]
        if L.PASS_END_X < ex <= kw["engage"]:
            if not in_pass:
                in_pass, hit_in_pass = True, False
                pass_start, pass_min_sep = bee.frames_run, 10 ** 9
            pass_min_sep = min(pass_min_sep,
                               max(ex - L.BEE_X2, abs(s2["by"] - ey) - 13))
        elif in_pass:
            in_pass = False
            passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                           "hit": hit_in_pass, "min_sep": pass_min_sep})
        hp_now = bee.i32(L.HEALTH)
        dh = hp_now - prev_hp
        prev_hp = hp_now
        if dh <= -1000:
            hit_in_pass = True
            hits.append({"f": bee.frames_run, "dh": dh, "by": s2["by"],
                         "bvy": s2["bvy"], "e": s2["e"], "mode": mode,
                         "side": sticky.get("side")})
            log(f"{label}_enemy_edge", **hits[-1])
            if n_hit_snap < max_event_snaps:
                bee.snap(f"b3_{label}_hit", R)
                n_hit_snap += 1
        elif dh >= 900:
            picked = [i for i in range(3)
                      if prev_fl[i][0] > 0 and s2["fl"][i][0] <= -49]
            seek_dur = (bee.frames_run - seek["since"]) \
                if (seek["idx"] is not None and mode == "flower" and
                    picked and seek["idx"] in picked and
                    seek["since"] is not None) else 0
            caused = bool(mode == "flower" and picked and
                          seek_dur >= SEEK_MIN_F)
            pickups.append({"f": bee.frames_run, "dh": dh, "by": s2["by"],
                            "fl": s2["fl"], "mode": mode, "tgt": target,
                            "picked_idx": picked, "seek_idx": seek["idx"],
                            "seek_dur": seek_dur, "caused": caused})
            log(f"{label}_flower_edge", **pickups[-1])
            if n_flower_snap < max_event_snaps:
                bee.snap(f"b3_{label}_flower", R)
                n_flower_snap += 1
        prev_fl = s2["fl"]
        if bee.frames_run >= next_snap:
            bee.snap(f"b3_{label}_gameplay", R)
            next_snap += snap_every
        if bee.i32(L.GS) != 1:
            death_f = bee.frames_run
            break
    if in_pass:
        passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                       "hit": hit_in_pass, "min_sep": pass_min_sep})
    st = bee.state()
    close = [p for p in passes if not p["hit"] and p["min_sep"] < 30]
    m = {
        "variant": label, "kw": kw,
        "survival_frames": (death_f - f_start) if death_f \
            else bee.frames_run - f_start,
        "death": death_f is not None, "gs": st["gs"], "score": st["score"],
        "hp": st["hp"], "best": st["best"], "flaps": flaps,
        "passes": len(passes), "dodges": sum(1 for p in passes
                                             if not p["hit"]),
        "close_dodges": len(close), "pass_detail": passes,
        "enemy_hits": len(hits), "hit_detail": hits,
        "pickups_total": len(pickups),
        "pickups_caused": sum(1 for p in pickups if p["caused"]),
        "pickup_detail": pickups,
        "frames_jsonl": f"frames_b3_{label}.jsonl",
        "vs_idle": {
            "survival_x": round((death_f - f_start if death_f else
                                 bee.frames_run - f_start) /
                                max(1, IDLE["survival_frames"] or 1), 2),
            "score_x": round(st["score"] / max(1, IDLE["score"]), 2)},
    }
    log(f"{label}_done", **{k: v for k, v in m.items()
                            if not k.endswith("_detail")})
    if death_f:
        bee.snap(f"b3_{label}_death", R)
        for _ in range(500):
            bee.run(1, set())
            if bee.i32(L.GS) == 0:
                break
        bee.snap(f"b3_{label}_gameover_return", R)
    return m


mC = run_variant("C", {"engage": 170, "margin": 14, "flower_hi": 170,
                       "hover_y": 95})
results = {"C": mC}
chosen = "C"
if mC["close_dodges"] < 5 or mC["pickups_caused"] < 2:
    log("variant_D_triggered", c_close=mC["close_dodges"],
        c_caused=mC["pickups_caused"])
    mD = run_variant("D", {"engage": 200, "margin": 18, "flower_hi": 200,
                           "hover_y": 110})
    results["D"] = mD
    chosen = ("D" if (mD["close_dodges"], mD["pickups_caused"],
                      mD["score"]) > (mC["close_dodges"],
                                      mC["pickups_caused"], mC["score"])
              else "C")

metrics = {
    "boot": 3, "checkpoint": L.CKPT_PATH, "policy": "bot_policy3",
    "idle_baseline": {"survival_frames": IDLE["survival_frames"],
                      "score": IDLE["score"],
                      "enemy_edges": len(IDLE["edges"])},
    "variants": results, "chosen": chosen,
    "verdict_inputs": {
        "dodges": results[chosen]["dodges"],
        "close_dodges": results[chosen]["close_dodges"],
        "enemy_hits": results[chosen]["enemy_hits"],
        "pickups_caused": results[chosen]["pickups_caused"],
        "pickups_total": results[chosen]["pickups_total"],
        "survival_frames": results[chosen]["survival_frames"],
        "score": results[chosen]["score"],
        "death": results[chosen]["death"],
    },
}
json.dump(metrics, open(os.path.join(OUT, "metrics_r35b_b3.json"), "w"),
          indent=1, default=str)
log("b3_verdict", chosen=chosen, **metrics["verdict_inputs"])
dump()
sb = L.sync_back()
if sb:
    log("sync_back", note=sb)
print("[r35b.b3] DONE frames=", bee.frames_run,
      "wall=", round(time.time() - T0, 1), flush=True)
