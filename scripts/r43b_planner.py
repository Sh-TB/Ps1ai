#!/usr/bin/env python3
"""r43b_planner.py — R43 (buzzybee, the 40% track): the CONTACT-TIME
TRAJECTORY GUARANTEE planner A/B.

The buzzybee capsule lever, executed: "a contact-time trajectory
guarantee reaches dominance (0 hits/1500f) — at engage time, simulate
(bee gravity/tap physics x wasp bounce-y) forward to ex=32 and choose
the exit (side + tap schedule) that keeps the bee out of the PREDICTED
band for the whole ex in [-36,32] window; re-plan on vy-flip or a
failed guarantee (bail = maximize distance from the band center)."

Arm B = bot_policy5: at every engage-window frame the planner
forward-simulates candidate hold-controllers (side x quantized target)
under the calibrated physics (bee: impulse -3072 -> move -> gravity
+256/f, clamp [18,172], slam guard bvy > -3000; wasp: predict_wasp_y
bounce model) and accepts the FIRST controller whose whole simulated
trajectory stays outside the predicted 56px band with a 12px guarantee
margin for every frame until the wasp passes (ex <= -36, cap 200f).
No guaranteed candidate -> the recorded bail: maximize the distance
from the band center.  Re-planning is implicit (every frame replans
from fresh state); the vy-flip therefore costs nothing extra.

Secondary (the capsule): the pickup attribution window is widened —
caused = flower-mode seek >= 20f OR a dodge-mode frame whose last
flower-seek started <= 60f ago (the R42-B zero-caused-pickups lesson).
Tertiary: per-hit timing metric (f_since_pass_start).

Arm A = the recorded bot-A recipe: bot_policy2(engage=150, margin=16,
flower_hi=160, hover_y=95), 1500f — the same protocol as R42-B.

Boot ledger: cap 1 (disclosed pre-run).  The R42-B gs1 checkpoint did
NOT survive (scratch/r42b absent — same scratch-cleanup class as
before), so boot 1 rebuilds it (settle 900f -> START -> gs1 ->
serialize), disclosed.  Restores are NOT boots (r35 precedent).
Dominance oracle: B enemy_hits == 0 (primary); B dodges == passes and
score/pickups not worse than A (secondary).
Outputs: scratch/r43b/{boot_log_r43b.json, frames_a.jsonl,
frames_b.jsonl, metrics_r43b.json, shots/}.
"""
import json
import os
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(REPO, "scripts"))
import r35b_lib as L  # noqa: E402

# ---- retarget the lib to the R43b scratch dir (before any use) --------
L.OUT = os.path.join(REPO, "scratch", "r43b")
L.SHOTS = os.path.join(L.OUT, "shots")
L.BOOTS = os.path.join(L.OUT, "boots_used.json")
L.CKPT_PATH = os.path.join(L.OUT, "state_r43b_gs1.bin")
os.makedirs(L.SHOTS, exist_ok=True)

T0 = time.time()


def _setup():
    """Ledger + logger setup (called from main; import-safe for the
    offline planner tests)."""
    R, log, dump = L.make_logger(L.OUT, "boot_log_r43b.json", "r43b")
    if not os.path.exists(L.BOOTS):
        json.dump({"cap": 1, "count": 0, "log": [],
                   "note": "R43b fresh ledger; cap 1 disclosed pre-run; "
                           "the R42-B gs1 checkpoint did not survive "
                           "(scratch/r42b absent) -> boot 1 rebuilds it "
                           "(settle->START->gs1->serialize), disclosed; "
                           "restores are not boots"},
                  open(L.BOOTS, "w"), indent=1)
    led_pre = json.load(open(L.BOOTS))
    nxt = int(led_pre.get("count", 0)) + 1
    led = L.ledger_use(nxt, "r43b_planner.py",
                       note="boot: fresh boot -> gs1 checkpoint rebuild "
                            "(the R42-B checkpoint is absent; disclosed; "
                            "entry 1 was the disclosed filed-but-"
                            "boot-failed filing — disc absent, rebuilt "
                            "internet-first sha-verified)")
    log("ledger", count=led["count"], cap=led["cap"], out=L.OUT,
        mirror=L.MIRROR_NOTE)
    return R, log, dump, led

CAP_F = 1500
SEEK_MIN_F = 20
PICKUP_WINDOW_F = 60          # the widened attribution window
GM = 12                       # the guarantee margin (px)
SIM_CAP = 200                 # forward-sim horizon cap (frames)
TGT_STEP = 8                  # candidate-target quantization (px)

# ---- the calibrated bee physics (main.c, r35b header) ------------------
# impulse -3072 on the tap frame; move; gravity +256/f; clamp [18,172];
# slam bug: never tap at pre-tap y_vel <= -3000.


def sim_bee_hold(by, bvy, side, target, horizon):
    """Forward-simulate the bee under the hold-controller (tap iff the
    side rule fires and bvy > -3000).  Returns the trajectory list.
    Physics (main.c, calibrated): impulse -3072 on the tap frame, then
    move (v/1024 px), then gravity +256/f; clamp [Y_MIN, Y_MAX].
    NOTE: the discrete loop climbs ~1.3-2.5 px MORE than the recorded
    rise_px calibration over one tap - absorbed by GM=12 plus the
    per-frame closed-loop replanning (each frame re-plans from fresh
    state, so model error does not accumulate)."""
    y, v = float(by), int(bvy)
    traj = []
    for _ in range(horizon):
        if side == "above":
            flap = y > target + 4 and v > -3000
        else:
            # below: there is NO downward impulse - any tap would rise
            # the bee back INTO the band, so the below hold is pure
            # free-fall (the residual rise already inside v included).
            flap = False
        if flap:
            v -= 3072
        y += v / 1024.0
        v += 256
        if y < L.Y_MIN:
            y, v = L.Y_MIN, max(v, 0)
        elif y > L.Y_MAX:
            y, v = L.Y_MAX, min(v, 0)
        traj.append(y)
    return traj


def danger_window(ex, horizon):
    """The contact frames: the wasp closes at 1.5 px/f; contact is
    possible only while ex(t) in [-36, 32] (the lever's window).
    Returns (t_enter, t_exit) as 1-based frame indices into the sim
    trajectory, or None when the window is already over."""
    t_enter = max(1, int((ex - 32.0) / 1.5) + 1)
    t_exit = min(horizon, int((ex + 36.0) / 1.5) + 1)
    if t_enter > t_exit:
        return None
    return t_enter, t_exit


def guaranteed(traj, ey, evy, win, side):
    """True iff every DANGER-window frame keeps the bee outside the
    predicted band with the GM margin.  Frames outside the window are
    not checked (the wasp is horizontally out of reach there)."""
    for t in range(win[0] - 1, win[1]):
        y = traj[t]
        wy = L.predict_wasp_y(ey, evy, t + 1)
        top, bot = wy - 13, wy + 43
        if side == "above":
            if y > top - GM:
                return False
        else:
            if y < bot + GM:
                return False
    return True


def plan_exit(by, bvy, ey, evy, ex, engage, margin):
    """The contact-time planner: enumerate (side, target) candidates,
    simulate to the window end, check the DANGER window only, return
    (flap_now, target, side, planned).  flap_now comes from the first
    frame of the winning hold-controller."""
    horizon = max(2, min(SIM_CAP, int((ex + 36.0) / 1.5) + 2))
    win = danger_window(ex, horizon)
    center = ey + 15.0
    if win is None:            # window over: wasp past, anything goes
        side = "above" if by < center else "below"
        return False, float(by), side, True
    cands = []
    # full-range candidate enumeration (step 8) on both sides; the
    # guarantee filter does the work, early-exit sims keep it cheap
    for tgt in range(L.Y_MIN + 4, L.Y_MAX - 3, TGT_STEP):
        cands.append(("above", tgt))
        cands.append(("below", tgt))
    # prefer the side the bee is already on (fewer crossings)
    cands.sort(key=lambda c: (0 if (c[0] == "above") == (by < center)
                              else 1, abs(c[1] - by)))
    for side, tgt in cands:
        traj = sim_bee_hold(by, bvy, side, tgt, horizon)
        if guaranteed(traj, ey, evy, win, side):
            flap = traj_control_now(by, bvy, side, tgt)
            return flap, float(tgt), side, True
    # ---- bail: maximize the distance from the band center ----------
    side = "above" if by < center else "below"
    if side == "above":
        tgt = max(L.Y_MIN + 4, L.Y_MIN + 10)
    else:
        tgt = min(L.Y_MAX - 4, L.Y_MAX - 10)
    flap = traj_control_now(by, bvy, side, tgt)
    return flap, float(tgt), side, False


def traj_control_now(by, bvy, side, target):
    if side == "above":
        return by > target + 4 and bvy > -3000
    return False          # below: never tap (any tap rises into the band)


def bot_policy5(s, sticky, engage=200, margin=16, flower_hi=170,
                hover_y=95):
    """The contact-time guarantee planner (see module docstring)."""
    by, bvy = s["by"], s["bvy"]
    ex, ey, evy = s["e"][0], s["e"][1], s["e"][2]
    if L.PASS_END_X < ex <= engage:
        flap, target, side, planned = plan_exit(by, bvy, ey, evy, ex,
                                                engage, margin)
        prev_side = sticky.get("side")
        flipped = (sticky.get("vy") is not None
                   and (sticky["vy"] < 0) != (evy < 0))
        sticky["vy"] = evy
        sticky["side"] = side
        sticky["planned"] = planned
        sticky["flip"] = bool(flipped or
                              (prev_side is not None
                               and prev_side != side))
        return flap, target, "dodge"
    sticky["side"] = None
    sticky["vy"] = None
    sticky["planned"] = None
    sticky["flip"] = False
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
    replans = 0
    bails = 0
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
               "planned": sticky.get("planned"),
               "flip": sticky.get("flip"),
               "by": s["by"], "bvy": s["bvy"], "e": s["e"], "fl": s["fl"]}
        if mode == "dodge":
            replans += 1
            bails += 0 if sticky.get("planned") else 1
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
                         "side": sticky.get("side"),
                         "planned": sticky.get("planned"),
                         "f_since_pass_start": (bee.frames_run
                                                - pass_start)
                         if pass_start is not None else None})
            log(f"{label}_enemy_edge", **hits[-1])
            if n_hit_snap < 2:
                bee.snap(f"r43b_{label}_hit", R)
                n_hit_snap += 1
        elif dh >= 900:
            picked = [i for i in range(3)
                      if prev_fl[i][0] > 0 and s2["fl"][i][0] <= -49]
            seek_dur = (bee.frames_run - seek["since"]) \
                if (seek["idx"] is not None and mode == "flower" and
                    picked and seek["idx"] in picked and
                    seek["since"] is not None) else 0
            # SECONDARY: the widened attribution window
            recent_seek = (seek["since"] is not None
                           and bee.frames_run - seek["since"]
                           <= PICKUP_WINDOW_F)
            caused = bool((mode == "flower" and picked
                           and seek_dur >= SEEK_MIN_F)
                          or (picked and recent_seek))
            pickups.append({"f": bee.frames_run, "dh": dh,
                            "picked_idx": picked, "seek_dur": seek_dur,
                            "caused": caused, "mode": mode,
                            "recent_seek": bool(recent_seek)})
            log(f"{label}_flower_edge", **pickups[-1])
            if n_fl_snap < 2:
                bee.snap(f"r43b_{label}_flower", R)
                n_fl_snap += 1
        prev_fl = s2["fl"]
        if bee.frames_run >= next_snap:
            bee.snap(f"r43b_{label}_gameplay", R)
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
        "planner_replans": replans, "planner_bails": bails,
        "frames_jsonl": f"frames_{label}.jsonl",
    }
    log(f"{label}_done", **{k: v for k, v in m.items()
                            if not k.endswith("_detail")})
    dump()
    return m


def main():
    R, log, dump, led = _setup()
    bee = L.Bee("ws_r43b")
    av = bee.load_game()
    log("boot", core=bee.core.core_name, av=av)

    # ---- boot 1: rebuild the gs1 checkpoint (settle -> START -> gs1) --
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
    bee.snap("r43b_checkpoint", R)

    # ---- Arm A: the recorded bot-A baseline ---------------------------
    mA = run_arm(bee, "A", L.bot_policy2,
                 {"engage": 150, "margin": 16, "flower_hi": 160,
                  "hover_y": 95}, CKPT, log, R, dump)
    # ---- Arm B: the contact-time guarantee planner --------------------
    mB = run_arm(bee, "B", bot_policy5,
                 {"engage": 200, "margin": 16, "flower_hi": 170,
                  "hover_y": 95}, CKPT, log, R, dump)

    dominant = (mB["enemy_hits"] == 0
                and mB["dodges"] == mB["passes"]
                and mB["score"] >= mA["score"]
                and mB["pickups_caused"] >= mA["pickups_caused"])
    metrics = {
        "schema": "ps1play.r43b-evidence/1",
        "round": "R43 (buzzybee, the 40% track)",
        "boot_ledger": led,
        "checkpoint": L.CKPT_PATH,
        "ckpt_rebuild_disclosed": True,
        "cap_frames": CAP_F,
        "guarantee_margin_px": GM,
        "pickup_window_f": PICKUP_WINDOW_F,
        "arm_A": mA,
        "arm_B": mB,
        "dominance_oracle": {
            "v5_hits_zero": mB["enemy_hits"] == 0,
            "v5_no_hit_pass": mB["dodges"] == mB["passes"],
            "v5_score_ge_A": mB["score"] >= mA["score"],
            "v5_pickups_ge_A": mB["pickups_caused"] >= mA["pickups_caused"],
            "DOMINANT": bool(dominant),
        },
        "wall_s": round(time.time() - T0, 1),
    }
    json.dump(metrics, open(os.path.join(L.OUT, "metrics_r43b.json"), "w"),
              indent=1, default=str)
    log("r43b_verdict", dominant=bool(dominant),
        A_hits=mA["enemy_hits"], B_hits=mB["enemy_hits"],
        A_score=mA["score"], B_score=mB["score"],
        A_passes=mA["passes"], B_passes=mB["passes"],
        A_caused=mA["pickups_caused"], B_caused=mB["pickups_caused"],
        B_replans=mB["planner_replans"], B_bails=mB["planner_bails"])
    dump()
    sb = L.sync_back()
    if sb:
        log("sync_back", note=sb)
    print("[r43b] DONE frames=", bee.frames_run,
          "wall=", round(time.time() - T0, 1), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
