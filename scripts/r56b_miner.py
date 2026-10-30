#!/usr/bin/env python3
"""r56b_miner.py (v2) — R56 offline lab (ZERO boots): the REAL-ANCHORED
step-level surgical mining (the r55-declared open lever).

ARCHITECTURE (the r55 lessons applied strictly):
  * "The lab only PROPOSES; the emulator boot disposes" — the sim is
    used ONLY for LOCAL physics lookaheads (pure step_physics + the
    recorded schedule's geometry, horizons <= 180 steps, local drift
    ~1px/18f => ~10px), NEVER for full-flight perception rollouts.
  * Every training label's FEATURES come from REAL recorded frames
    (the teacher's tv8 traces / the student's real lives) through the
    EXACT Brain._vector mirror (observer + finder + tracker + the
    policy's own history) — bit-identical to deployment, zero
    synthetic-frame artifacts.
  * The corrective labels are SURGICAL: one label per 15-step window,
    cap 12/life, only where (a) the recorded action's local lookahead
    DIES and (b) the opposite action's lookahead SURVIVES with margin
    — never a whole-tail relabel (the r55 honest negative).

MINING SOURCES:
  1. the teacher's tv8 traces (8 lives, this round's boots 1-2);
  2. (round 2, after the eval boot) the student's REAL lives — the
     same miner runs unchanged on student npz files (frames + the
     student's own actions) — the on-policy drift-basin coverage the
     r55 BC never had.

  THE EXCEED LEVER: on the teacher's own death windows (k30 @4398,
  k45 @3620 — both measured this round) the latest single flip of the
  teacher's action whose local lookahead survives — the student learns
  to fly through a window that kills the teacher.

PHYSICS GATE (local, the fit_pads standard): every recorded death's
fatal state (last valid beak + the local one-step rollout) must
COLLIDE under the r55k pads (TOP=10/BOT=11/GROUND=204) against the
death frame's geometry; every budget-alive life's last valid beak must
be collision-free. Plus the mirror gate: the feature recomputation's
observer readings must equal the recorded obs_y (the same code path).

SPLIT DISCIPLINE (unchanged): mining lives = the TRAIN family only
(k=6/30/60/12/45/120); k90 = val (metrics only, no labels); k210 =
held-out test (NEVER labeled).

Outputs: scratch/r56/mined_r1.npz + r56b_calibration.json.
"""
import json
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn import visual_only as VO                  # noqa: E402
from ps1play.learn.teacher import FlappyTeacher              # noqa: E402
import r55k_sim_lab as SL                                    # noqa: E402

SCR = os.path.join(REPO, "scratch", "r56")
LEARN = os.path.join(REPO, "data", "learn")

CLASSES = ["HOVER", "FLAP"]
TRAIN_K = [6, 30, 60, 12, 45, 120]
VAL_K = [90]
TEST_K = [210]
ALL_K = TRAIN_K + VAL_K + TEST_K

PADS_R55K = (10.0, 11.0, 204.0)     # TOP, BOT, GROUND (r55k fitted)
LAW_FB, LAW_EB = 14.0, 26.0         # the m1 law (the r55k sweep winner)
H_LOOK = 90                          # risky-step lookahead horizon
H_WALK = 150                         # walk-back horizon
MARGIN_MIN = 2.0                     # px the corrective branch must keep
DEDUPE_WIN = 15                      # one label per window per life
CAP_PER_LIFE = 12
RECORDED_DEATHS = {30: 4398, 45: 3620}   # the r56a measured results


# --------------------------------------------------------------- corpus
def load_life(k):
    z = np.load(os.path.join(SCR, f"tv8_k{k:03d}.npz"))
    return _pack(k, z["frames"], [str(a) for a in z["action"]],
                 z["obs_y"].astype(float), z["beak_y"].astype(float),
                 z["since_trust"].astype(int),
                 z["trk_gc"].astype(float))


def _pack(k, frames, acts, obs_y, beak, since_trust, trk_gc):
    n = len(acts)
    i0 = 0
    for i in range(n - 1):
        if (beak[i] > 0 and beak[i + 1] > 0
                and (beak[i + 1] - beak[i]) == 2.0):
            i0 = i
            break
    geom = [SL.geometry(frames[i],
                        by_hint=(beak[i] if beak[i] > 0 else None))
            for i in range(n)]
    return {"k": k, "frames": frames, "acts": acts, "obs_y": obs_y,
            "beak": beak, "since_trust": since_trust,
            "trk_gc": trk_gc, "n": n, "i0": i0, "geom": geom}


def load_student_life(path, k):
    """A REAL student life (frames + the student's OWN actions) from
    the eval boot — the on-policy mining source (round 2)."""
    z = np.load(path)
    acts = z["actions"] if "actions" in z else z["action"]
    obs_y = z["obs_y"] if "obs_y" in z else np.full(
        len(acts), -1.0)
    beak = z["beak_y"] if "beak_y" in z else np.full(
        len(acts), -1.0)
    st = z["since_trust"] if "since_trust" in z else np.zeros(
        len(acts), dtype=int)
    return _pack(k, z["frames"], [str(a) for a in acts],
                 obs_y.astype(float), beak.astype(float),
                 st.astype(int),
                 z["trk_gc"].astype(float) if "trk_gc" in z
                 else np.full(len(acts), -1.0))


# ------------------------------------------------- the feature mirror
def mirror_vectors(life):
    """The EXACT Brain._vector/act mirror (r55_train's
    episode_vectors + the observer/tracker state per step)."""
    obs = VO.BirdObserverV7()
    gtr = VO.GapTrackerV7()
    X, states = [], []
    since_flap, flap_run = 99, 0
    last_gc, since_gap = -1.0, 40
    prev_action = None
    for i in range(life["n"]):
        cur = life["frames"][i]
        by_obs, vy_obs = obs.step(cur, prev_action)
        gc_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(cur,
                                                     by_hint=by_obs)
        gc_obs = gtr.step((gc_raw, g0, g1, dx + 160.0))
        x = VO.features_flappy_v7(cur, by_obs, vy_obs,
                                  since_flap=since_flap,
                                  last_gc=last_gc,
                                  since_gap=since_gap,
                                  flap_run=flap_run,
                                  gc_obs=gc_obs)
        X.append(x)
        run = min(flap_run + 1, 9) if prev_action == "FLAP" else 0
        # the observer's own fused state = the net's belief at step i
        # (the vy the NEXT step's decision will see)
        states.append((float(by_obs), float(vy_obs), int(run)))
        a = life["acts"][i]
        prev_action = a
        if a == "FLAP":
            since_flap = 0
            flap_run = min(flap_run + 1, 9)
        else:
            since_flap = min(since_flap + 1, 99)
            flap_run = 0
        if gc_obs is not None:
            last_gc = float(gc_obs)
            since_gap = 0
        else:
            since_gap = min(since_gap + 1, 40)
    return X, states


# ---------------------------------------------------- physics toolkit
def gc_true(geom_i):
    band = SL.current_band(geom_i)
    if band is None or not band[2]:
        return None
    g0, g1 = band[2][0]
    return (g0 + g1) / 2.0


def lookahead(life, i, y, vy, run, first_action, horizon=H_LOOK):
    """LOCAL closed-loop survive check from the belief state: the
    first_action at step i, then the LAW on the recorded schedule's
    geometry (the r55k-proven local-rollout route). Returns (survived,
    min_margin, death_offset)."""
    t = FlappyTeacher(flap_below=LAW_FB, emergency_below=LAW_EB)
    t.reset_history()
    y2, vy2, run2 = y, vy, run
    min_margin = 999.0
    n = life["n"]
    for off in range(horizon):
        j = i + off
        if j + 1 >= n:
            return True, min_margin, None          # schedule exhausted
        a = first_action if off == 0 else t.act(
            y2, vy2, gc_true(life["geom"][j]))
        y2, vy2, run2 = SL.step_physics(y2, vy2, run2, a)
        band = SL.current_band(life["geom"][j + 1])
        d = SL.dead(y2, band)
        if band is not None and band[2]:
            g0b, g1b = band[2][0]
            min_margin = min(min_margin, y2 + SL.BOT_PAD - g0b,
                             g1b - (y2 + SL.BOT_PAD))
        if d:
            return False, min_margin, off
    return True, min_margin, None


def physics_gate(life):
    """LOCAL death-reproduction gate (the r55k fit_pads standard):
    each recorded death's fatal state must collide; the alive lives'
    last valid beak must be collision-free."""
    rec = RECORDED_DEATHS.get(life["k"])
    beak = life["beak"]
    acts = life["acts"]
    if rec is None:
        # the last valid beak must be collision-free
        for i in range(life["n"] - 1, -1, -1):
            if beak[i] > 0:
                band = SL.current_band(life["geom"][i])
                d = SL.dead(float(beak[i]), band)
                return {"ok": d is None,
                        "last_valid_y": float(beak[i]),
                        "dead": d}
        return {"ok": False, "last_valid_y": None}
    # death life: the local reconstruction must collide at/near rec
    i = min(rec - 1, life["n"] - 1)
    dys = [float(beak[j] - beak[j - 1])
           for j in range(max(1, i - 3), i + 1)
           if beak[j] > 0 and beak[j - 1] > 0]
    vy0 = float(np.median(dys)) if dys else 0.0
    y_f, vy_f, run_f = float(beak[i]), vy0, 0
    for j in range(i, life["n"]):
        y_f, vy_f, run_f = SL.step_physics(y_f, vy_f, run_f, acts[j])
    band = SL.current_band(life["geom"][life["n"] - 1])
    d = SL.dead(y_f, band)
    return {"ok": d is not None, "fatal_y": round(y_f, 1), "dead": d,
            "recorded_step": rec}


# --------------------------------------------------------------- mining
def risky_mask(life):
    n = life["n"]
    out = np.zeros(n, dtype=bool)
    for i in range(life["i0"], n):
        for j in range(i, min(n, i + H_LOOK)):
            for bd in life["geom"][j]:
                if bd[1] * 4 > 130 and bd[0] * 4 < 196:
                    out[i] = True
                    break
            if out[i]:
                break
    return out


def mine_life(life, X, states, cap=CAP_PER_LIFE):
    """Surgical mining on a RECORDED life (the labels' features = the
    real frames' mirror vectors)."""
    acts = life["acts"]
    n = life["n"]
    labels = []
    risky = risky_mask(life)
    windows = []
    for t in range(life["i0"], n):
        if not risky[t]:
            continue
        a = acts[t]
        alt = "FLAP" if a == "HOVER" else "HOVER"
        st = states[t]
        # the belief state's y/vy + the flap-run the physics needs
        run_t = min((1 if t > 0 and acts[t - 1] == "FLAP" else 0) + 1,
                    9) if a == "FLAP" else 0
        y_t = st[0] if st[0] >= 0 else None
        if y_t is None:
            continue
        vy_t = st[1]
        ok_a, _mg_a, _d_a = lookahead(life, t, y_t, vy_t, run_t,
                                      first_action=a)
        ok_b, mg_b, _d_b = lookahead(life, t, y_t, vy_t, run_t,
                                     first_action=alt)
        if (not ok_a) and ok_b and mg_b >= MARGIN_MIN:
            w0 = t // DEDUPE_WIN
            if w0 in windows or len(labels) >= cap:
                continue
            windows.append(w0)
            labels.append({"step": t, "label": alt, "kind": "lookahead",
                           "margin": round(float(mg_b), 1),
                           "x": X[t].tolist()})
    return labels


def walkback_mining(life, X, states):
    """The LATEST single flip of the RECORDED action that survives the
    recorded death (the local lookahead from the belief state)."""
    rec = RECORDED_DEATHS.get(life["k"])
    if rec is None:
        return None
    beak = life["beak"]
    latest = None
    safest = None
    for t in range(rec - 1, max(life["i0"], rec - 400), -1):
        if beak[t] <= 0:
            continue
        flip = "FLAP" if life["acts"][t] == "HOVER" else "HOVER"
        st = states[t]
        if st[0] < 0:
            continue
        run_t = 1 if (t > 0 and life["acts"][t - 1] == "FLAP") else 0
        ok, mg, _d = lookahead(life, t, st[0], st[1], run_t,
                               first_action=flip, horizon=H_WALK)
        if not (ok and mg >= MARGIN_MIN):
            continue
        if latest is None:
            latest = (t, flip, mg)      # the LAST surviving flip =
                                        # the minimal intervention
        if safest is None or mg > safest[2]:
            safest = (t, flip, mg)      # the max-margin flip =
                                        # the safest line through the
                                        # death window (the label the
                                        # student can actually ride)
    out = []
    if latest:
        t, flip, mg = latest
        out.append({"step": t, "label": flip, "kind": "walkback_latest",
                    "margin": round(float(mg), 1), "x": X[t].tolist()})
    if safest and (latest is None or safest[0] != latest[0]):
        t, flip, mg = safest
        out.append({"step": t, "label": flip, "kind": "walkback_safe",
                    "margin": round(float(mg), 1), "x": X[t].tolist()})
    return out[0] if len(out) == 1 else (out if out else None)


# ----------------------------------------------------------------- main
def main():
    SL.TOP_PAD, SL.BOT_PAD = PADS_R55K[0], PADS_R55K[1]
    SL.GROUND_Y = PADS_R55K[2]
    lives = {k: load_life(k) for k in ALL_K}
    cal = {"pads": PADS_R55K, "lives": {}}

    # 1) the local physics gate
    for k, life in lives.items():
        g = physics_gate(life)
        cal["lives"][f"k{k}"] = {"gate": g}
        print(f"k{k} physics gate: {g}", flush=True)

    # 2) the mirror gate: the recomputed observer must equal the
    #    recorded obs_y (the same code path — an identity check)
    for k, life in lives.items():
        X, states = mirror_vectors(life)
        life["X"], life["states"] = X, states
        errs = [abs(states[i][0] - life["obs_y"][i])
                for i in range(life["n"])
                if life["obs_y"][i] > 0 and states[i][0] >= 0]
        me = float(np.mean(errs)) if errs else -1.0
        cal["lives"][f"k{k}"]["mirror_mean_err"] = round(me, 4)
        print(f"k{k} mirror mean|err|={me:.4f}px", flush=True)

    # 3) the law re-flight sanity (the r55k simulate route — reported,
    #    not gated: the lab PROPOSES, the boot DISPOSES)
    for k, life in lives.items():
        t = FlappyTeacher(flap_below=LAW_FB, emergency_below=LAW_EB)
        t.reset_history()
        gtr = VO.GapTrackerV7()
        y = float(life["beak"][life["i0"]])
        vy, run = 2.0, 0
        n = life["n"]
        i = life["i0"]
        d_i = None
        while i < n:
            gc_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(
                life["frames"][i], by_hint=y)
            gc = gtr.step((gc_raw, g0, g1, dx + 160.0))
            a = t.act(y, vy, gc)
            y, vy, run = SL.step_physics(y, vy, run, a)
            band = SL.current_band(
                life["geom"][min(i + 1, n - 1)])
            if SL.dead(y, band):
                d_i = i
                break
            i += 1
        rec = RECORDED_DEATHS.get(k)
        cal["lives"][f"k{k}"]["law_refly_death"] = d_i
        print(f"k{k} law re-flight death: {d_i} (recorded {rec})",
              flush=True)

    # 4) surgical mining on the TRAIN family only
    all_labels = []
    for k in TRAIN_K:
        life = lives[k]
        wbs = walkback_mining(life, life["X"], life["states"])
        wbs = wbs if isinstance(wbs, list) else             ([wbs] if wbs else [])
        for wb in wbs:
            wb["life"] = k
            all_labels.append(wb)
        print(f"k{k}: walkback labels={len(wbs)} "
              f"({[w['kind'] for w in wbs]})", flush=True)

    X = np.asarray([lb["x"] for lb in all_labels], dtype=np.float32)
    y = np.asarray([CLASSES.index(lb["label"]) for lb in all_labels],
                   dtype=np.int64)
    np.savez_compressed(
        os.path.join(SCR, "mined_r1.npz"), X=X, y=y,
        life=np.asarray([lb["life"] for lb in all_labels]),
        step=np.asarray([lb["step"] for lb in all_labels]),
        kind=np.asarray([lb["kind"] for lb in all_labels]),
        margin=np.asarray([lb["margin"] for lb in all_labels]))
    cal["mined"] = {"n": int(len(y)),
                    "by_kind": {kk: int(sum(1 for lb in all_labels
                                            if lb["kind"] == kk))
                                for kk in {lb["kind"]
                                           for lb in all_labels}},
                    "flap_frac": round(float((y == 1).mean()), 3)}
    with open(os.path.join(SCR, "r56b_calibration.json"), "w") as f:
        json.dump(cal, f, indent=2)
    print(f"== mined {len(y)} surgical labels -> mined_r1.npz",
          flush=True)


if __name__ == "__main__":
    main()
