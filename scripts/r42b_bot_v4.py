#!/usr/bin/env python3
"""r42b_bot_v4.py — R42-B (buzzybee, the 40% track): policy-v4 dominance A/B.

The buzzybee capsule lever, executed: "policy-v4 (arc-checked below-side
taps + fx>0 flower window) reaches dominance (0 hits/1500f)" — A/B
bot-v4 vs bot-A on a gs1 savestate checkpoint.

Boot ledger: cap 1 (disclosed pre-run). Boot 1 REBUILDS the gs1
checkpoint (settle 900f -> START -> gs1 -> serialize) because the r35b
savestate did not survive the sandbox scratch cleanup — disclosed here
and in the ledger. Restores are NOT boots (r35 precedent).

Arm A (baseline = the recorded bot-A): bot_policy2(engage=150,
margin=16, flower_hi=160, hover=95) — the r35 boot-2 variant-A recipe,
1500f cap.
Arm B (v4): bot_policy4 — bot_policy3 with ONE targeted fix + earlier
commitment: the below-side corrective flap's arc-check uses the
PREDICTED band bottom over the tap rise window (max ey+43 over the next
14f via the bounce sim, +4 extra clearance) instead of the current-frame
band bottom (the v3 hits were below-side over-flaps chaining into a
DESCENDING wasp's band); engage=200, margin=16. Everything else
(above-side preference, inside-band emergency, vy-flip re-choose, fx>0
flower window, slam-bug guard bvy > -3000) is bot_policy3 verbatim.

Dominance oracle: v4 enemy_hits == 0 across 1500f (primary); secondary:
v4 dodges == passes, score/pickups not worse than A.
Outputs: scratch/r42b/{boot_log_r42b.json, frames_a.jsonl,
frames_b.jsonl, metrics_r42b.json, shots/}.
"""
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
import r35b_lib as L  # noqa: E402

# ---- retarget the lib to the R42-B scratch dir (before any use) --------
L.OUT = os.path.join(REPO, "scratch", "r42b")
L.SHOTS = os.path.join(L.OUT, "shots")
L.BOOTS = os.path.join(L.OUT, "boots_used.json")
L.CKPT_PATH = os.path.join(L.OUT, "state_r42b_gs1.bin")
os.makedirs(L.SHOTS, exist_ok=True)

T0 = time.time()
R, log, dump = L.make_logger(L.OUT, "boot_log_r42b.json", "r42b")

# ---- ledger: cap 1, disclosed pre-run -----------------------------------
if not os.path.exists(L.BOOTS):
    json.dump({"cap": 1, "count": 0, "log": [],
               "note": "R42-B fresh ledger; cap 1 disclosed pre-run; "
                       "boot 1 rebuilds the gs1 checkpoint (the r35b "
                       "savestate was not preserved across the sandbox "
                       "scratch cleanup); restores are not boots"},
              open(L.BOOTS, "w"), indent=1)
led = L.ledger_use(1, "r42b_bot_v4.py",
                   note="boot 1: fresh boot -> gs1 checkpoint rebuild "
                        "(disclosed replacement for the lost r35b ckpt)")
log("ledger", count=led["count"], cap=led["cap"], out=L.OUT,
    mirror=L.MIRROR_NOTE)

CAP_F = 1500
SEEK_MIN_F = 20


# ---- v4 policy -----------------------------------------------------------
def bot_policy4(s, sticky, engage=200, margin=16, flower_hi=170,
                hover_y=95, tap_window=14):
    """bot_policy3 + the predictive tap-window arc-check (see module
    docstring). Same contract: returns (flap, target, mode)."""
    by, bvy = s["by"], s["bvy"]
    ex, ey, evy = s["e"][0], s["e"][1], s["e"][2]
    if L.PASS_END_X < ex <= engage:
        t_c = max(0, int((ex - 32) / 1.5))
        ey_c = L.predict_wasp_y(ey, evy, t_c)
        band_top, band_bot = ey - 13, ey + 43          # current band
        tgt_a = ey_c - 13 - margin
        tgt_b = ey_c + 43 + margin
        room_a, room_b = tgt_a - L.Y_MIN, L.Y_MAX - tgt_b
        cur = sticky.get("side")
        inside = (band_top + 2) <= by <= (band_bot - 2)
        flipped = sticky.get("vy") is not None and \
            (sticky["vy"] < 0) != (evy < 0)
        sticky["vy"] = evy
        if inside:
            cur = "above" if by < ey + 15 else "below"
        elif cur is None or flipped:
            if room_a >= 10 and by <= tgt_b - 6:
                cur = "above"
            elif room_b >= 10 and by >= tgt_b - 4:
                cur = "below"
            elif room_a >= 10:
                cur = "above"
            elif room_b >= 10:
                cur = "below"
            else:
                cur = "above" if by < ey_c else "below"
        sticky["side"] = cur
        if cur == "above":
            target = max(L.Y_MIN + 2, min(L.Y_MAX - 2, tgt_a))
            flap = by > target + 4 and bvy > -3000
        else:
            target = max(L.Y_MIN + 2, min(L.Y_MAX - 2, tgt_b))
            # v4 FIX: arc-check against the PREDICTED band bottom over
            # the whole tap rise window (the wasp may descend INTO the
            # rising bee), plus +4 extra clearance
            bot_max = max(L.predict_wasp_y(ey, evy, t) + 43
                          for t in range(0, tap_window + 1))
            flap = (by > target + 12 and bvy > -3000 and
                    by - L.rise_px(bvy) > bot_max + 12)
        return flap, target, "dodge"
    sticky["side"] = None
    sticky["vy"] = None
    best = None
    for i, (fx, fy) in enumerate(s["fl"]):
        if 0 < fx <= flower_hi and (best is None or fx < best[1]):
            best = (i, fx, fy)
    if best:
        target = max(L.Y_MIN + 2, min(L.Y_MAX - 2, best[2] + 5))
        return (by > target + 4 and bvy > -3000), target, "flower"
    return (by > hover_y and bvy > -3000), hover_y, "hover"


def seek_target_idx(s, kw):
    best = None
    for i, (fx, fy) in enumerate(s["fl"]):
        if 0 < fx <= kw["flower_hi"] and (best is None or fx < best[1]):
            best = (i, fx)
    return best[0] if best else None


def run_arm(bee, label, policy, kw, ckpt, log, R, dump):
    bee.unserialize(ckpt)
    w, fh = L.jl_writer(L.OUT, f"frames_{label}.jsonl")
    sticky = {}
    passes, hits, pickups = [], [], []
    seek = {"idx": None, "since": None}
    n_fl_snap = n_hit_snap = 0
    in_pass, hit_in_pass = False, False
    pass_start, pass_min_sep = None, 10 ** 9
    prev_hp = bee.i32(L.HEALTH)
    prev_fl = bee.obs()["fl"]
    f_start = bee.frames_run
    flaps = 0
    death_f = None
    next_snap = bee.frames_run + 300
    while bee.frames_run - f_start < CAP_F:
        s = bee.obs()
        flap, target, mode = policy(s, sticky, **kw)
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
                               max(ex - L.BEE_X2,
                                   abs(s2["by"] - ey) - 13))
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
            if n_hit_snap < 2:
                bee.snap(f"r42b_{label}_hit", R)
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
            pickups.append({"f": bee.frames_run, "dh": dh,
                            "picked_idx": picked, "seek_dur": seek_dur,
                            "caused": caused, "mode": mode})
            log(f"{label}_flower_edge", **pickups[-1])
            if n_fl_snap < 2:
                bee.snap(f"r42b_{label}_flower", R)
                n_fl_snap += 1
        prev_fl = s2["fl"]
        if bee.frames_run >= next_snap:
            bee.snap(f"r42b_{label}_gameplay", R)
            next_snap += 300
        if bee.i32(L.GS) != 1:
            death_f = bee.frames_run
            break
    fh.close()
    if in_pass:
        passes.append({"start_f": pass_start, "end_f": bee.frames_run,
                       "hit": hit_in_pass, "min_sep": pass_min_sep})
    st = bee.state()
    close = [p for p in passes if not p["hit"] and p["min_sep"] < 30]
    m = {
        "arm": label, "kw": kw,
        "survival_frames": (death_f - f_start) if death_f \
            else bee.frames_run - f_start,
        "death": death_f is not None, "gs": st["gs"], "score": st["score"],
        "hp": st["hp"], "flaps": flaps,
        "passes": len(passes),
        "dodges": sum(1 for p in passes if not p["hit"]),
        "close_dodges": len(close), "pass_detail": passes,
        "enemy_hits": len(hits), "hit_detail": hits,
        "pickups_total": len(pickups),
        "pickups_caused": sum(1 for p in pickups if p["caused"]),
        "pickup_detail": pickups,
        "frames_jsonl": f"frames_{label}.jsonl",
    }
    log(f"{label}_done", **{k: v for k, v in m.items()
                            if not k.endswith("_detail")})
    dump()
    return m


def main():
    bee = L.Bee("ws_r42b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)

    # ---- boot 1: rebuild the gs1 checkpoint (settle -> START -> gs1) ----
    bee.run(900, set())
    st = bee.state()
    log("settled", f=bee.frames_run, gs=st["gs"], score=st["score"])
    if st["gs"] == 0:
        bee.set_buttons("START")
        bee.run_frame()
        bee.set_buttons(set())
        for _ in range(60):
            bee.run(1, set())
            if bee.i32(L.GS) == 1:
                break
    st = bee.state()
    assert st["gs"] == 1, f"expected gs1 after START, got {st['gs']}"
    bee.run(10, set())
    CKPT = bee.serialize()
    open(L.CKPT_PATH, "wb").write(CKPT)
    st = bee.state()
    log("checkpoint_saved", bytes=len(CKPT), score=st["score"],
        hp=st["hp"], f_abs=bee.frames_run, path=L.CKPT_PATH)
    bee.snap("r42b_checkpoint", R)

    # ---- Arm A: the recorded bot-A baseline ------------------------------
    mA = run_arm(bee, "A", L.bot_policy2,
                 {"engage": 150, "margin": 16, "flower_hi": 160,
                  "hover_y": 95}, CKPT, log, R, dump)
    # ---- Arm B: policy-v4 -------------------------------------------------
    mB = run_arm(bee, "B", bot_policy4,
                 {"engage": 200, "margin": 16, "flower_hi": 170,
                  "hover_y": 95}, CKPT, log, R, dump)

    dominant = (mB["enemy_hits"] == 0
                and mB["dodges"] == mB["passes"]
                and mB["score"] >= mA["score"]
                and mB["pickups_caused"] >= mA["pickups_caused"])
    metrics = {
        "schema": "ps1play.r42b-evidence/1",
        "round": "R42-B (buzzybee, the 40% track)",
        "boot_ledger": led,
        "checkpoint": L.CKPT_PATH,
        "ckpt_rebuild_disclosed": True,
        "cap_frames": CAP_F,
        "arm_A": mA,
        "arm_B": mB,
        "dominance_oracle": {
            "v4_hits_zero": mB["enemy_hits"] == 0,
            "v4_no_hit_pass": mB["dodges"] == mB["passes"],
            "v4_score_ge_A": mB["score"] >= mA["score"],
            "v4_pickups_ge_A": mB["pickups_caused"] >= mA["pickups_caused"],
            "DOMINANT": bool(dominant),
        },
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r42b.json"), "w"),
              indent=1, default=str)
    log("r42b_verdict", dominant=bool(dominant),
        A_hits=mA["enemy_hits"], B_hits=mB["enemy_hits"],
        A_score=mA["score"], B_score=mB["score"],
        A_passes=mA["passes"], B_passes=mB["passes"],
        A_caused=mA["pickups_caused"], B_caused=mB["pickups_caused"])
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r42b] DONE frames=", bee.frames_run,
          "wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
