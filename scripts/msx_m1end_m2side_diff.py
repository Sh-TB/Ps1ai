#!/usr/bin/env python3
"""msx_m1end_m2side_diff.py — Issue #5 session 11 / Issue #6 round 8
(task 8-a): the surgical M1-end vs M2-side loading diff.

The round-8 recorded lever.  One fresh one-boot process; ALL contexts
entered via savestate restore (never a second boot).  Four RAM-diff
windows over the live 2MB SYSTEM_RAM, sampled every 30f with the
FlipTracker per-byte bookkeeping (first/last change frame, count,
phase-start value val0, final value):

  A  restore m2_train  (the regenerated anchor: stable M2 gameplay,
     px 76.4 / php 76 / score 0 / gren 10): 300f quiet then 900f
     RIGHT-hold — the M2 LIVE baseline + the anchor's input-aliveness
     proof.  This window's churn set is EXCLUDED from mission-flag
     candidates (mission flags must be stable in live M2 play).
  B  restore m1_end    (the CONTINUE? countdown gate: px 0.0, sec
     (11,1), flags 255, score 3300): 4800f NO-INPUT — the M1-end
     quiet path (countdown expiry -> loading -> whatever it becomes).
  C  restore m1_end again: the bounded signature-gated START-accept
     ladder (tap ONLY while the countdown signature persists, 12f
     tap, 600f poll, <=4 taps, STOP on endzone/dark/banner/spawn —
     the m2t1/m2t8 lesson) then the same-length quiet watch — the
     M2-side loading path attempt.
  D  restore issue5_m1_start (M1 gameplay start, px 26): 300f quiet +
     900f RIGHT-hold — the M1 LIVE baseline (same core version
     0.9.44.1 df2b53b verified on both state metas).

Candidates (diff-of-diffs): bytes that TRANSITION during the
M2-reaching loading windows (B/C) to a value that matches the A
(M2-live) steady state, never churn in A, and differ from D's M1
value — ranked by B/C agreement, small-u32 patterns (0x0 -> 0x1/2/3
mission-index shapes), and proximity to the known scene globals.

No RAM writes here (observe-only); the write-probe is a separate
script.  Evidence: scratch/issue6_round8_msx/.
"""
import argparse
import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig                       # noqa: E402
from issue4_controller import boot                  # noqa: E402
from e2e_policy_trial import snap, px_of, sha_file, DISC  # noqa: E402
from msx_ramhunt_util import FlipTracker, KNOWN     # noqa: E402

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round8_msx"
P = None                     # the one-boot PS1Play handle (set in main)
TAG = None
A_QUIET_F = 300
A_RIDE_F = 900
B_F = 4800
C_F = 4800
D_QUIET_F = 300
D_RIDE_F = 900
SAMPLE_GAP = 30
TAP_F = 12
POLL_F = 600
MAX_TAPS = 4
M2_PX = (0.0, 100.0)
M1_START_STATE = "issue5_m1_start"

# known scene globals (msx_ramhunt_util.KNOWN) + structural regions
KNOWN_ADDRS = [a for _, a, _ in KNOWN]
OVERLAY_ENEMY = (0x9C0E8, 0x9C0E8 + 115400)   # ENEMY.BIN verbatim @VA 0x8009C0E8


def log(*a):
    print("[diff]", *a, file=sys.stderr, flush=True)


def png(name):
    try:
        rgb = P.core.frame_rgb()
        if rgb is not None:
            from PIL import Image
            Image.fromarray(rgb).save(
                os.path.join(SCRATCH, f"{TAG}_{name}.png"))
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])


def classify(m):
    """Signature classification from VERIFIED telemetry only."""
    s = snap(m)
    if s["px"] == 0.0 and s["php"] == 0:
        if s["sec"] == (11, 1) and s["flags"] == 255 and s["score"] > 0:
            return "countdown", s
        return "scene_dark", s
    if s["flags"] != 0xFF:
        return "scene_dark", s
    if s["sec"][0] == 0xC and 10.0 <= s["px"] <= 60.0:
        return "banner", s
    if s["score"] == 0 and M2_PX[0] < s["px"] < M2_PX[1] and s["php"] > 0:
        return "m2_spawn", s
    if s["px"] > 800.0:
        return "endzone", s
    return "world", s


def sample_window(p, m, trk, frames, ride=False, label="W", png_at=()):
    """Step `frames` in SAMPLE_GAP chunks, sampling RAM + classification.
    ride=True holds RIGHT the whole window.  Returns the event list."""
    evs = []
    f = 0
    png(f"{label}_f0")
    while f < frames:
        buttons = {"RIGHT"} if ride else set()
        p.core.run(min(SAMPLE_GAP, frames - f), buttons)
        f += SAMPLE_GAP
        trk.step(f, m.ram)
        cls, s = classify(m)
        known = {name: int(getattr(m, kind)(a)) for name, a, kind in KNOWN}
        evs.append({"f": f, "cls": cls, **s, **known})
        if f in png_at:
            png(f"{label}_f{f}")
    cls, s = classify(m)
    png(f"{label}_end")
    log(f"{label}: end cls={cls} px={s['px']} score={s['score']} "
        f"php={s['php']} sec={s['sec']}")
    return evs


def summarize(evs, label):
    """Class-run-length timeline of a window."""
    out, cur, start, n = [], None, 0, 0
    for e in evs:
        if e["cls"] != cur:
            if cur is not None:
                out.append({"cls": cur, "f0": start, "f1": e["f"], "n": n})
            cur, start, n = e["cls"], e["f"], 1
        else:
            n += 1
    if cur is not None:
        out.append({"cls": cur, "f0": start, "f1": evs[-1]["f"], "n": n})
    log(f"{label} timeline: " + "; ".join(
        f"{r['cls']} f{r['f0']}-{r['f1']}({r['n']})" for r in out))
    return out


def window_E(p, m, trk, max_f=7200, post_spawn_f=600):
    """The m2t9-PROVEN ride-along ladder: restore m1_end, then mirror
    train_phase semantics — ride RIGHT only while a world reads alive
    (flags 0xFF, px != 0), quiet through scene_dark/countdown/banner.
    In the anchor run this exact discipline walked the ladder
    endzone -> banner -> dark -> countdown -> winter world -> M2 SPAWN
    (i46..i101).  Stops post_spawn_f after the first m2_spawn."""
    evs = []
    f, spawn_f, trap_logged = 0, None, False
    png("E_m1end_restore")
    while f < max_f:
        cls, s = classify(m)
        if cls == "m2_spawn" and spawn_f is None:
            spawn_f = f
            png(f"E_m2_spawn_f{f}")
            log(f"E M2 SPAWN at f={f} px={s['px']} php={s['php']} "
                f"score={s['score']}")
        if spawn_f is not None and f - spawn_f >= post_spawn_f:
            break
        ride = (cls in ("world", "endzone") and s["flags"] == 0xFF
                and s["px"] != 0.0)
        p.core.run(SAMPLE_GAP, {"RIGHT"} if ride else set())
        f += SAMPLE_GAP
        trk.step(f, m.ram)
        known = {name: int(getattr(m, kind)(a))
                 for name, a, kind in KNOWN}
        evs.append({"f": f, "cls": cls, "ride": ride, **s, **known})
        if cls == "endzone" and not trap_logged:
            trap_logged = True
            log(f"E endzone at f={f} px={s['px']}")
        if f % 1200 == 0:
            png(f"E_f{f}")
    png("E_end")
    return evs, spawn_f


def main():
    global TAG, P
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("--windows", type=str, default="A,B,C,D",
                    help="comma list of windows to run this invocation")
    args = ap.parse_args()
    want = [w.strip().upper() for w in args.windows.split(",")]
    os.makedirs(SCRATCH, exist_ok=True)
    TAG = f"diff{args.run}_{time.strftime('%H%M%S')}"
    t0 = time.time()

    p, fw = boot()
    P = p
    m = p.mem
    log(f"booted ({fw})")

    windows = {}
    trackers, events = {}, {}
    d_done = False

    # ---------------- window A: M2-live baseline (anchor) ----------------
    if "A" in want:
        p.load_state("m2_train")
        s0 = snap(m)
        png("A_anchor_restore")
        log(f"A restore m2_train: px={s0['px']} php={s0['php']} "
            f"score={s0['score']} gren={s0['gren']}")
        trk_a = FlipTracker(m.ram)
        evs_a = sample_window(p, m, trk_a, A_QUIET_F, ride=False,
                              label="Aq", png_at=(A_QUIET_F,))
        px0 = px_of(m)
        evs_a += sample_window(p, m, trk_a, A_RIDE_F, ride=True,
                               label="Ar", png_at=(A_RIDE_F // 2,))
        moved = round(px_of(m) - px0, 1)
        log(f"A anchor RIGHT-ride moved {moved}px (input aliveness)")
        trackers["A"], events["A"] = trk_a, evs_a
        windows["A"] = {"label": "A_m2_live", "state": "m2_train",
                        "restore": s0, "moved_px_ride": moved,
                        "timeline": summarize(evs_a, "A")}

    # ---------------- window B: m1_end quiet path ----------------
    if "B" in want:
        p.load_state("m1_end")
        s0 = snap(m)
        png("B_m1end_restore")
        log(f"B restore m1_end: px={s0['px']} score={s0['score']} "
            f"sec={s0['sec']} flags={s0['flags']}")
        trk_b = FlipTracker(m.ram)
        evs_b = sample_window(p, m, trk_b, B_F, ride=False, label="B",
                              png_at=(1200, 2400, 3600, 4800))
        trackers["B"], events["B"] = trk_b, evs_b
        windows["B"] = {"label": "B_m1end_quiet", "state": "m1_end",
                        "restore": s0, "timeline": summarize(evs_b, "B")}

    # ---------------- window C: m1_end accept ladder ----------------
    if "C" in want:
        p.load_state("m1_end")
        s0 = snap(m)
        png("C_m1end_restore")
        log(f"C restore m1_end: px={s0['px']} score={s0['score']}")
        trk_c = FlipTracker(m.ram)
        evs_c = []
        taps, trap, accepted, f = 0, False, False, 0
        cls, s = classify(m)
        while f < C_F:
            if (cls == "countdown" and taps < MAX_TAPS and not trap
                    and (not evs_c or evs_c[-1].get("cls") != "TAP"
                         or f - evs_c[-1].get("f", -10**9) >= POLL_F)):
                p.core.run(TAP_F, {"START"})
                f += TAP_F
                taps += 1
                evs_c.append({"f": f, "cls": "TAP", "tap": taps})
                png(f"C_tap{taps}")
                log(f"C tap {taps} at f={f}")
                cls, s = classify(m)
                continue
            p.core.run(SAMPLE_GAP, set())
            f += SAMPLE_GAP
            trk_c.step(f, m.ram)
            cls, s = classify(m)
            known = {name: int(getattr(m, kind)(a))
                     for name, a, kind in KNOWN}
            evs_c.append({"f": f, "cls": cls, **s, **known})
            if cls == "endzone" and taps:
                trap = True                    # m2t1/m2t8: stop tapping
                log(f"C ENDZONE TRAP at f={f} px={s['px']}")
            if cls == "m2_spawn" and not accepted:
                accepted = True
                png(f"C_m2_spawn_f{f}")
                log(f"C M2 SPAWN at f={f} px={s['px']} php={s['php']}")
            if f % 1200 == 0:
                png(f"C_f{f}")
        trackers["C"], events["C"] = trk_c, evs_c
        windows["C"] = {"label": "C_m1end_accept", "state": "m1_end",
                        "restore": s0, "taps": taps, "endzone_trap": trap,
                        "m2_spawn_seen": accepted,
                        "timeline": summarize(evs_c, "C")}

    # ---------------- window D: M1-live baseline ----------------
    if "D" in want:
        try:
            p.load_state(M1_START_STATE)
            s0 = snap(m)
            png("D_m1start_restore")
            log(f"D restore {M1_START_STATE}: px={s0['px']} php={s0['php']} "
                f"score={s0['score']}")
            trk_d = FlipTracker(m.ram)
            evs_d = sample_window(p, m, trk_d, D_QUIET_F, ride=False,
                                  label="Dq", png_at=(D_QUIET_F,))
            evs_d += sample_window(p, m, trk_d, D_RIDE_F, ride=True,
                                   label="Dr", png_at=(D_RIDE_F // 2,))
            trackers["D"], events["D"] = trk_d, evs_d
            windows["D"] = {"label": "D_m1_live", "state": M1_START_STATE,
                            "restore": s0,
                            "timeline": summarize(evs_d, "D")}
            d_done = True
        except Exception as e:                              # noqa: BLE001
            log("window D skipped:", repr(e)[:160])
            windows["D"] = {"label": "D_m1_live",
                            "skipped": repr(e)[:160]}

    # ---------------- window E: m1_end ride-along (the m2t9 ladder) --
    if "E" in want:
        p.load_state("m1_end")
        s0 = snap(m)
        log(f"E restore m1_end: px={s0['px']} score={s0['score']}")
        trk_e = FlipTracker(m.ram)
        evs_e, spawn_f = window_E(p, m, trk_e)
        trackers["E"], events["E"] = trk_e, evs_e
        windows["E"] = {"label": "E_m1end_ride", "state": "m1_end",
                        "restore": s0, "m2_spawn_f": spawn_f,
                        "timeline": summarize(evs_e, "E")}

    # ---------------- persist trackers + reports ----------------
    for key, trk in trackers.items():
        path = os.path.join(SCRATCH, f"{TAG}_trk{key}.npz")
        info = trk.save(path, {"window": key})
        log(f"tracker {key}: {info['changed_total']} bytes changed -> "
            f"{os.path.basename(path)}")
        windows[key]["changed_bytes"] = info["changed_total"]
        windows[key]["npz"] = path

    with open(os.path.join(SCRATCH, f"{TAG}_events.json"), "w") as fh:
        json.dump(events, fh, default=str)
    report = {"tag": TAG, "firmware": fw, "windows": windows,
              "wall_total_s": round(time.time() - t0, 1),
              "frames": p.core.frames_run,
              "game_sha256": sha_file(DISC)}
    with open(os.path.join(SCRATCH, f"report_{TAG}.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    log(f"RUN {TAG} done wall={report['wall_total_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
