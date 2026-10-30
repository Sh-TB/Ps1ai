#!/usr/bin/env python3
"""r55k_sim_lab.py — the OFFLINE flappy simulator lab (zero boots).

Physical basis (all measured, r15 + r55):
  * pipes scroll LEFT on a fixed schedule — independent of the bird —
    so the recorded frames of a life carry the full pipe geometry for
    ANY candidate action sequence;
  * bird dynamics: vy = -8 on the 2nd pulse frame, vy = min(vy+1, 2),
    y += vy (the r55a silver integrator, verified against vision);
  * death = the bird box crossing the current pipe's rims (or the
    ground), calibrated on the corpus's RECORDED deaths.

What it validates / sweeps:
  1. REPLAY check: feeding the RECORDED actions must reproduce each
     recorded death at its recorded step (+-2) — the physics+collision
     model is then trusted;
  2. CANDIDATE sweep: the r15 law driven by the v3.2 finder + tracker
     (by_hint = the SIMULATED bird) with law-parameter grid — virtual
     pipes / death step per corpus life, zero boots.

The lab only PROPOSES; the emulator boot disposes (m1 re-run).
"""
import itertools
import json
import math
import os
import sys

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn import visual_only as VO                    # noqa: E402
from ps1play.learn.teacher import FlappyTeacher                # noqa: E402

OUT = os.path.join(REPO, "scratch", "r55")
SY, SX = VO.SY, VO.SX                                          # 4, 4

# the corpus: (npz, kind) — law-on-v7 traces (beak_y truth) and the
# r55a sf-teacher lives (silver_y truth)
CORPUS = [
    ("tv7g_k6", "trace"), ("tv7g_k60", "trace"),
    ("tv7g_k90", "trace"), ("tv7h_k6", "trace"),
    ("tv7h_k60", "trace"), ("life_k006", "life"),
    ("life_k030", "life"), ("life_k060", "life"),
    ("life_k090", "life"), ("life_k210", "life"),
]
BIRD_X0, BIRD_X1 = 130.0, 196.0     # the r15 bird window (full-res)
GROUND_Y = 216.0                    # the beige ground strip


def _pipe_mask(cur):
    r = cur[:, :, 0].astype(int)
    g = cur[:, :, 1].astype(int)
    b = cur[:, :, 2].astype(int)
    return (g > r + 8) & (b < g - 40)


def decontaminate_runs(runs, by_hint):
    """The constant-gap rule (the finder v3's, shared logic): a free
    run longer than ~82px has one side bird-extended; the side NEARER
    the bird row is the dirty one — pin the gap on the OPPOSITE edge
    (top+35 / bottom-35) and report the corrected 70px gap."""
    out = []
    for g0, g1 in runs:
        if g1 - g0 > 82.0 and by_hint is not None and by_hint > 0:
            mid = (g0 + g1) / 2.0
            if by_hint > mid:
                out.append((g0, g0 + 70.0))      # pin the top edge
            else:
                out.append((g1 - 70.0, g1))      # pin the bottom edge
        else:
            out.append((g0, g1))
    return out


def geometry(cur, by_hint=None):
    """All pipe bands + their DECONTAMINATED free runs (full-res px).
    Returns [(bx0, bx1, [(g0, g1), ...]), ...] — bx in small cols."""
    green = _pipe_mask(cur)
    colsum = green[5:41, :].sum(axis=0)
    cs = np.maximum(np.maximum(colsum[:-2], colsum[1:-1]), colsum[2:])
    colsum = np.concatenate([[colsum[0]], cs, [colsum[-1]]])
    bands, start = [], None
    for x in range(20, 80):
        if colsum[x] > 10:
            if start is None:
                start = x
        else:
            if start is not None and x - start >= 2:
                bands.append((start, x))
            start = None
    if start is not None and 80 - start >= 2:
        bands.append((start, 80))
    out = []
    for bx0, bx1 in bands:
        frac = green[5:46, bx0:bx1].mean(axis=1)
        pipe = frac >= 0.5
        free = np.nonzero(~pipe)[0]
        runs = []
        if len(free):
            for rp in np.split(free, np.nonzero(np.diff(free) > 1)[0]
                               + 1):
                if len(rp) >= 8:
                    runs.append(((rp[0] + 5) * SY, (rp[-1] + 5) * SY))
        runs = decontaminate_runs(runs, by_hint)
        out.append((bx0, bx1, runs))
    return out


def current_band(geom):
    """The band at/over the bird (the r15 semantics: right edge past
    the bird's window start)."""
    for bx0, bx1, runs in geom:
        if bx1 * SX > BIRD_X0:
            return bx0, bx1, runs
    return None


def step_physics(y, vy, run, action):
    """One control step of the MEASURED dynamics (r55k, median of 183
    impulse events in the corpus truth):
      * impulse -8 on the 2nd consecutive FLAP step;
      * the rise arc decelerates at exactly +1 px/f^2 (integer steps,
        no plateaus);
      * the fall accelerates at +0.125 px/f^2 with the screen dy
        ROUNDED (the 8-frame plateaus at 0/+1/+2/+3 the r54k fit
        misread as a terminal +2);
      * no fall cap (the measured tail reaches +4/+5)."""
    run = min(run + 1, 9) if action == "FLAP" else 0
    if run == 2:
        vy = -8.0
    elif vy < 0:
        vy = min(vy + 1.0, 0.0)
    else:
        vy = vy + 0.125
    # HALF-UP rounding (the game's convention); Python's round() is
    # banker's and shifts every plateau boundary by a frame
    dy = math.floor(vy + 0.5) if vy > 0 else vy
    y = y + dy
    return y, vy, run


def dead(y, band_geom):
    """Collision test: bird box vs the current band's rims/ground.
    The pads are the calibrated sprite half-extents around the beak
    centroid (TOP_PAD above, BOT_PAD below)."""
    if y + BOT_PAD >= GROUND_Y:
        return "ground"
    if band_geom is None:
        return None
    bx0, bx1, runs = band_geom
    if bx1 * SX <= BIRD_X0 or bx0 * SX >= BIRD_X1:
        return None
    if not runs:
        return None
    g0, g1 = runs[0]
    if y - TOP_PAD <= g0:
        return "top"
    if y + BOT_PAD >= g1:
        return "bottom"
    return None


# --- corpus load: frames, truth y per step, recorded actions, death ---
def load_corpus():
    corpus = []
    for name, kind in CORPUS:
        z = np.load(os.path.join(OUT, f"{name}.npz"))
        fr = z["frames"]
        if kind == "trace":
            truth = z["beak_y"].astype(float)
        else:
            # vision_y = the full-res vision truth; silver_y coasts
            # (drifts) during occlusion and is NOT used here
            truth = z["vision_y"].astype(float)
        acts = list(z["action"] if kind == "trace" else z["actions"])
        n = len(fr)
        # start the sim where the bird is in a clean terminal fall:
        # truth valid, dy = +2 (the initial-condition mismatch otherwise
        # poisons the replay — the traces open mid-impulse-arc)
        i0 = 0
        for i in range(n - 1):
            if truth[i] > 0 and truth[i + 1] > 0 \
                    and (truth[i + 1] - truth[i]) == 2.0:
                i0 = i
                break
        corpus.append({"name": name, "frames": fr, "truth": truth,
                       "acts": acts, "i0": i0, "died": n,
                       "geom": [geometry(fr[i],
                                         by_hint=(truth[i]
                                                  if truth[i] > 0
                                                  else None))
                                for i in range(n)]})
    return corpus


def fit_v0(life, acts=None):
    """Fit the initial internal fall velocity v0 against the life's own
    truth (the recorded dy is the ROUNDED screen velocity — the
    internal v0 is only known to +-0.5). Returns the v0 minimizing the
    mean |sim-truth| over the life's replay."""
    best, best_err = None, 1e9
    base = life["truth"][life["i0"] + 1] - life["truth"][life["i0"]]
    for dv in np.arange(-0.45, 0.46, 0.05):
        v0 = float(base) + float(dv)
        y = float(life["truth"][life["i0"]])
        vy, run = v0, 0
        err, n = 0.0, 0
        for i in range(life["i0"], life["died"] - 1):
            y, vy, run = step_physics(y, vy, run, life["acts"][i])
            t = life["truth"][i + 1]
            if t > 0:
                err += abs(y - t)
                n += 1
        if n and err / n < best_err:
            best_err, best = err / n, v0
    return best, best_err


def fit_pads(corpus, only_names=None):
    """LOCAL geometric calibration (no sim dynamics — the open-loop
    replay drifts ~1px/18f from the +-1-frame plateau-boundary
    quantization, which would poison a full-trajectory fit).

    only_names: restrict the calibration events (the r55a sf-teacher
    lives die in abnormal states — the bird clamped at the screen top
    by the broken v1 perception — and would poison the pads; the
    law-on-v7 trace deaths are the honest calibration class).
    For each recorded death: the fatal y = the last valid truth y plus
    ONE model step (the impulse or the fall dy at that step — local,
    zero accumulation), tested against the geometry of the death
    frame. The pads = the smallest (top, bot, ground) where ALL deaths
    collide."""
    events = []
    for life in corpus:
        if only_names is not None and life["name"] not in only_names:
            continue
        n = life["died"]
        tr = life["truth"]
        # the last valid truth + the local one-step dy
        y_last = None
        for i in range(n - 1, life["i0"], -1):
            if tr[i] > 0:
                y_last = (i, float(tr[i]))
                break
        if y_last is None:
            continue
        i, yv = y_last
        # reconstruct the FATAL state: roll the model forward from the
        # last valid truth through the remaining (vision-lost) frames
        # with the recorded actions — a short local rollout, zero
        # accumulated drift; the initial vy = the local fall speed
        dys0 = [float(tr[j] - tr[j - 1]) for j in
                range(max(life["i0"] + 1, i - 3), i + 1)
                if tr[j] > 0 and tr[j - 1] > 0]
        vy0 = float(np.median(dys0)) if dys0 else 0.0
        y_f, vy_f, run_f = yv, vy0, 0
        for j in range(i, n):
            y_f, vy_f, run_f = step_physics(y_f, vy_f, run_f,
                                            life["acts"][j])
        y_fatal = y_f
        band = current_band(life["geom"][n - 1])
        events.append({"life": life["name"], "y": y_fatal, "band": band,
                       "step": i})
    ev_desc = [(e["life"], e["step"], round(e["y"], 1)) for e in events]
    print("death events:", ev_desc)
    best = None
    for ground in (204.0, 208.0, 212.0, 216.0):
        for top in np.arange(4.0, 22.1, 1.0):
            for bot in np.arange(4.0, 26.1, 1.0):
                ok = True
                for e in events:
                    y = e["y"]
                    hit = False
                    if y + bot >= ground:
                        hit = True
                    b = e["band"]
                    if b is not None and b[2]:
                        g0, g1 = b[2][0]
                        # the band must overlap the bird's columns
                        if b[1] * SX > BIRD_X0 and b[0] * SX < BIRD_X1:
                            if y - top <= g0 or y + bot >= g1:
                                hit = True
                    if not hit:
                        ok = False
                        break
                if ok:
                    best = (float(top), float(bot), ground)
                    break
            if best:
                break
        if best:
            break
    return best


def simulate(life, law_fn, use_truth=True):
    """Re-fly one corpus life with law_fn(y, vy, gc_tracked) -> action.
    gc comes from the v3.2 finder + GapTrackerV7 on the recorded
    frames (by_hint = the SIMULATED bird). Returns (pipes, death_step
    or None, min_bottom_margin)."""
    obs_gap = VO.GapTrackerV7()
    v0, _e = fit_v0(life)
    y = float(life["truth"][life["i0"]])
    vy, run = v0, 0
    pipes = 0
    last_bx = None
    min_margin = 999.0
    n = life["died"]
    for i in range(life["i0"], n):
        geom = life["geom"][i]
        gc_raw, dx, g0, g1, _by = VO._flappy_gap_raw2(
            life["frames"][i], by_hint=y)
        gc = obs_gap.step((gc_raw, g0, g1, dx + 160.0))
        a = law_fn(y, vy, gc)
        # the decision a is applied over i -> i+1; the resulting state
        # lives in frame i+1 (its geometry, its band, its pipes)
        y, vy, run = step_physics(y, vy, run, a)
        nxt = life["geom"][i + 1] if i + 1 < n else None
        band = current_band(nxt) if nxt is not None else None
        d = dead(y, band)
        if band is not None:
            bx = (band[0] + band[1]) / 2.0
            if last_bx is not None and bx > last_bx + 15:
                pipes += 1
            last_bx = bx
        if band is not None and band[2]:
            g0b, g1b = band[2][0]
            min_margin = min(min_margin, y + BOT_PAD - g0b,
                             g1b - (y + BOT_PAD))
        if d:
            return pipes, i + 1, min_margin, d
    return pipes, None, min_margin, None


def main():
    global TOP_PAD, BOT_PAD
    corpus = load_corpus()
    print(f"corpus lives: {[c['name'] for c in corpus]}")
    trace_names = {c["name"] for c in corpus
                   if c["name"].startswith("tv7")}
    pads = fit_pads(corpus, only_names=trace_names)
    if pads is None:
        print("PAD FIT FAILED — the physics/collision model does not "
              "reproduce the recorded deaths; report and stop")
        return
    TOP_PAD, BOT_PAD = pads[0], pads[1]
    print(f"calibrated pads: TOP={TOP_PAD} BOT={BOT_PAD} GROUND={pads[2]}")

    # --- candidate sweep: the r15 law on the v3.2 perception ---
    results = {}
    for fb, eb in itertools.product([12.0, 14.0, 16.0], [24.0, 26.0,
                                                         28.0]):
        rows = []
        for life in corpus:
            t = FlappyTeacher(flap_below=fb, emergency_below=eb)
            t.reset_history()

            def law_fn(y, vy, gc, _t=t):
                return _t.act(y, vy, gc)
            pipes, dstep, margin, dcause = simulate(life, law_fn)
            rows.append({"life": life["name"],
                         "pipes": pipes,
                         "death": dstep,
                         "cause": dcause,
                         "min_margin": round(margin, 1)})
        results[f"fb{fb:g}_eb{eb:g}"] = rows
        alive = sum(1 for r in rows if r["death"] is None)
        tot = sum(r["pipes"] for r in rows)
        print(f"law fb={fb:g} eb={eb:g}: alive {alive}/{len(rows)}, "
              f"total pipes {tot}")
    with open(os.path.join(OUT, "r55k_sim_sweep.json"), "w") as f:
        json.dump({"pads": pads, "sweep": results}, f, indent=2)
    print("== saved r55k_sim_sweep.json")


if __name__ == "__main__":
    main()
