#!/usr/bin/env python3
"""r55_mine.py — FAILURE MINING (offline, zero boots): the counter-
factual relabels at the teacher's own death states.

The mission bar: the student must MEET OR EXCEED its teacher. Pure
BC+DAgger converges TO the teacher (the labels ARE the teacher's
actions) — the student can never out-live the teacher's own failures.
The lever: at the teacher's DEATH states, mine the COUNTERFACTUALLY
SURVIVING action (the sim: flip the law's action at step t, re-fly the
window with the calibrated physics+collision model) and teach THAT to
the student with high weight. Wherever the mined label differs from
the teacher's, the student's decision is strictly better-informed than
the teacher's — the mechanism by which the student exceeds the teacher.

Inputs: the teacher traces saved by r55_eval (teacher_v7_k*.npz, the
deaths only — the budget-alive lives hold no mining signal).
Output: mine_<stem>.npz (frames, teacher_actions = the CORRECTED
labels for the mined window, actions = the teacher's original) for
r55_train --dagger-eps.
"""
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import r55k_sim_lab as L                                     # noqa: E402
from ps1play.learn import visual_only as VO                  # noqa: E402

SCR = os.path.join(REPO, "scratch", "r55")
WINDOW = 60          # the mining window before the recorded death
HORIZON = 150        # the survival requirement after the flip


def sim_fly(geom, acts, i0, y0, vy0, run0, flip_at=None,
            flip_to=None, n=None):
    """Re-fly the recorded action list through the sim; returns
    (death_step or None, margin_min). One action can be flipped."""
    y, vy, run = y0, vy0, run0
    last_bx = None
    margin = 999.0
    n = len(acts) if n is None else n
    for i in range(i0, min(i0 + n, len(geom) - 1)):
        a = acts[i]
        if flip_at is not None and i == flip_at:
            a = flip_to
        band = L.current_band(geom[i + 1])
        # pipe-count bookkeeping is irrelevant here
        y, vy, run = L.step_physics(y, vy, run, a)
        d = L.dead(y, band)
        if band is not None and band[2]:
            g0b, g1b = band[2][0]
            margin = min(margin, abs(y + L.BOT_PAD - g0b),
                         abs(g1b - (y + L.BOT_PAD)))
        if d:
            return i + 1, margin
    return None, margin


def mine_life(stem, flip_pref="HOVER"):
    z = np.load(os.path.join(SCR, f"{stem}.npz"))
    fr = z["frames"]
    acts = [str(a) for a in z["actions"]]
    n = len(fr)
    # the truth channel = the v7 observer itself (the same mission-
    # legal small-frame pathway; measured |obs-beak| med 1.4 / max ~8px
    # on every corpus trace) — the mining needs NO RAM, NO full-res
    obs = VO.BirdObserverV7()
    by = np.zeros(n)
    prev = None
    for i in range(n):
        y_o, _vy = obs.step(fr[i], prev)
        prev = acts[i]
        by[i] = y_o if y_o > 0 else -1.0
    geom = [L.geometry(fr[i], by_hint=(float(by[i]) if by[i] > 0
                                       else None))
            for i in range(n)]
    # the sim's start state: the last valid truth before the window
    i0 = max(0, n - WINDOW)
    if by is None:
        print(f"{stem}: no truth channel — skip")
        return None
    j = i0
    while j > 0 and (by[j] <= 0 or by[j - 1] <= 0):
        j -= 1
    y0 = float(by[j])
    dys0 = [float(by[k] - by[k - 1]) for k in
            range(max(1, j - 3), j + 1) if by[k] > 0 and by[k - 1] > 0]
    vy0 = float(np.median(dys0)) if dys0 else 0.0
    # sanity: the recorded actions must reproduce the death
    dstep, m = sim_fly(geom, acts, j, y0, vy0, 0, n=n)
    rec_death = n - 1
    print(f"{stem}: sim replay death={dstep} (recorded {rec_death}) "
          f"margin={m:.1f}")
    if dstep is None or abs(dstep - rec_death) > 8:
        print(f"  -> sim does not reproduce the death; skip")
        return None
    # mine: flip each action in the window, keep the flips whose
    # re-flight SURVIVES the window + horizon
    mined = []
    for t in range(i0, n - 1):
        if acts[t] == flip_pref:
            continue
        alt = flip_pref
        d2, m2 = sim_fly(geom, acts, j, y0, vy0, 0, flip_at=t,
                         flip_to=alt, n=n - j + HORIZON
                         if n - j + HORIZON <= len(geom) - j
                         else len(geom) - j)
        if d2 is None:
            mined.append((t, alt, m2))
    if not mined:
        print("  -> no surviving flip found (the death is not a "
              "single-action fault)")
        return None
    # build the corrected-label episode: the WINDOW's frames with the
    # teacher's actions EXCEPT the mined steps -> the flipped action;
    # the episode starts at j (the last anchored state)
    t_acts = list(acts)
    for t, alt, _m in mined:
        t_acts[t] = alt
    out = os.path.join(SCR, f"mine_{stem}.npz")
    np.savez_compressed(
        out,
        frames=fr[j:n],
        actions=np.asarray(acts[j:n]),
        teacher_actions=np.asarray(t_acts[j:n]))
    print(f"  -> mined {len(mined)} flips at "
          f"{[t - j for t, _a, _m in mined]} (window-relative); "
          f"saved {out}")
    return out


def mine_recovery(stem, sim_lab):
    """Recovery-sequence mining: the single-action flips fail when the
    bird arrives at the death zone too fast — the correction needs a
    SEQUENCE with a LONGER runway. Candidate recovery laws: the flap
    threshold grid x the HOVER BIAS (the law's gap target shifted UP
    by 0/4/8/12px — the recorded deaths all sink into the BOTTOM rim:
    the oscillation bottom = trigger+sprite sits ~9px from the bottom
    rim and ~23px from the top, so the upward bias is the principled
    safety direction). The sim is the survival oracle."""
    z = np.load(os.path.join(SCR, f"{stem}.npz"))
    fr = z["frames"]
    acts = [str(a) for a in z["actions"]]
    n = len(fr)
    obs = VO.BirdObserverV7()
    by = np.zeros(n)
    prev = None
    for i in range(n):
        y_o, _vy = obs.step(fr[i], prev)
        prev = acts[i]
        by[i] = y_o if y_o > 0 else -1.0
    geom = [sim_lab.geometry(fr[i],
                             by_hint=(float(by[i]) if by[i] > 0
                                      else None))
            for i in range(n)]
    rec_death = n - 1
    candidates = []
    for bias in (0, 4, 8, 12):
        for fb, eb in ((14, 26), (12, 26), (12, 24), (10, 24)):
            candidates.append((fb, eb, bias))
    for back in (0, 20, 40, 80, 140, 200, 260, 320):
        j = max(0, n - WINDOW - back)
        while j > 0 and (by[j] <= 0 or by[j - 1] <= 0):
            j -= 1
        y0 = float(by[j])
        dys0 = [float(by[k] - by[k - 1]) for k in
                range(max(1, j - 3), j + 1)
                if by[k] > 0 and by[k - 1] > 0]
        vy0 = float(np.median(dys0)) if dys0 else 0.0
        # sanity: the teacher's own actions die here
        d0, _m = sim_fly(geom, acts, j, y0, vy0, 0, n=n)
        if d0 is None:
            continue          # the teacher survives from this anchor
        for fb, eb, bias in candidates:
            from ps1play.learn.teacher import FlappyTeacher
            t = FlappyTeacher(flap_below=fb, emergency_below=eb)
            t.reset_history()
            rec_acts = []
            o2 = VO.BirdObserverV7()
            g2 = VO.GapTrackerV7()
            p2 = None
            for i in range(j, n):
                o_by, o_vy = o2.step(fr[i], p2)
                gc_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(
                    fr[i], by_hint=o_by)
                gc = g2.step((gc_raw, g0, g1, dx + 160.0))
                if gc is not None:
                    gc = gc - bias
                a = t.act(o_by if o_by >= 0 else None, o_vy, gc)
                rec_acts.append(a)
                p2 = a
            hybrid = list(acts)
            hybrid[j:n] = rec_acts
            d2, m2 = sim_fly(geom, hybrid, j, y0, vy0, 0, n=n)
            if d2 is None:
                out = os.path.join(SCR, f"mine_{stem}.npz")
                np.savez_compressed(
                    out,
                    frames=fr[j:n],
                    actions=np.asarray(acts[j:n]),
                    teacher_actions=np.asarray(hybrid[j:n]))
                print(f"{stem}: teacher dies at sim {d0} "
                      f"(recorded {rec_death}); RECOVERY fb={fb:g} "
                      f"eb={eb:g} bias={bias:g} from anchor -{n - j} "
                      f"survives (margin {m2:.1f}); saved {out}")
                return out
    print(f"{stem}: no recovery variant survives the window")
    return None


def main():
    mode = "single"
    args = []
    for a in sys.argv[1:]:
        if a == "--recovery":
            mode = "recovery"
        else:
            args.append(a)
    stems = args or ["teacher_v7_k30"]
    import r55k_sim_lab as L
    L.TOP_PAD, L.BOT_PAD, L.GROUND_Y = 10.0, 11.0, 204.0
    for stem in stems:
        if mode == "recovery":
            mine_recovery(stem, L)
        else:
            mine_life(stem)


if __name__ == "__main__":
    main()
