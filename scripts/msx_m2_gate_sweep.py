#!/usr/bin/env python3
"""msx_m2_gate_sweep.py — Issue #5 session 10 / round 7 (task 17-a-r3):
deterministic M1->M2 gate resolver by TIMING SWEEP.

The 17-a-r2 evidence (m2t7 vs m2t8 vs rg2) shows the post-banner
CONTINUE? countdown accepts ONE START tap into M2 at some FRAME OFFSETS
and re-enters the input-live M1 endzone at others (frame-timing
sensitive, bit-deterministic otherwise).  Instead of guessing one
offset per boot, this run:

  1. boots (firmware openbios+start_taps auto-enters M1),
  2. rides M1 with the proven run_once(control=False) to the
     MISSION_BANNER (c=107 in m2t7/m2t8),
  3. waits for the countdown signature (px 0.0, sec (11,1), flags 255,
     score>0) and saves the savestate "m2_gate" AT THE FIRST SIGHTING,
  4. sweeps the tap offset: for K = 0,24,...: restore "m2_gate", run K
     quiet frames, tap START (12f), poll <=900f and classify:
       m2_spawn  (score 0, px 60-90, php 70-80, gren 10, flags 255)
           -> 90f stability proof -> save_state("m2_train") + RAM npz
           + RIGHT input-ownership probe  -> SUCCESS
       endzone / countdown-persists / dark -> next K
  5. reports the full K->outcome table (honest, incl. all negatives).

One boot per process (savestate restore is not a re-boot).  Evidence:
scratch/issue6_round7_msx/.
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

from ps1play import labconfig                       # noqa: E402,F401
from issue4_controller import boot                  # noqa: E402
from e2e_policy_trial import snap, px_of, sha_file, DISC, run_once  # noqa: E402
from lives_banner_variant import raw_slots          # noqa: E402
from msx_ramhunt_util import png, jlog              # noqa: E402

EVID = "/home/z/my-project/ps1ai/scratch/issue6_round7_msx"
EXPECT = {"px": (60.0, 90.0), "php": (70, 80), "gren": 10, "score": 0}
K_STEP = 24
K_MAX = 960
POLL_F = 900
POLL_STEP = 30
STABILITY_F = 90
SWEEP_WALL_S = 540.0
COUNTDOWN_WAIT_F = 4200


def log(*a):
    print("[sweep]", *a, file=sys.stderr, flush=True)


def classify(m):
    s = snap(m)
    if s["px"] == 0.0 and s["php"] == 0:
        if s["sec"] == (11, 1) and s["flags"] == 255 and s["score"] > 0:
            return "countdown", s
        return "dark", s
    if s["flags"] != 0xFF:
        return "dark", s
    if s["sec"][0] == 0xC and 10.0 <= s["px"] <= 60.0:
        return "banner", s
    if (s["score"] == 0 and EXPECT["px"][0] <= s["px"] <= EXPECT["px"][1]
            and EXPECT["php"][0] <= s["php"] <= EXPECT["php"][1]
            and s["gren"] == EXPECT["gren"]):
        return "m2_spawn", s
    if s["px"] > 800.0:
        return "endzone", s
    return "world", s


def try_anchor(p, m, J, tag):
    """m2_spawn signature -> stability proof -> save m2_train + npz +
    input-ownership probe.  Returns the spawn snap or None."""
    kind, s = classify(m)
    if kind != "m2_spawn":
        return None
    p.core.run(STABILITY_F, set())
    kind2, s2 = classify(m)
    if kind2 != "m2_spawn":
        J({"ev": "SPAWN_UNSTABLE", "first": s, "after": s2})
        return None
    J({"ev": "M2_SPAWN_VERIFIED", **s2, "slots": raw_slots(m)})
    png(p, "m2_spawn", tag)
    p.save_state("m2_train")
    np.savez_compressed(os.path.join(EVID, f"{tag}_m2spawn_ram.npz"),
                        ram=m.ram.copy())
    px0 = px_of(m)
    p.core.run(90, {"RIGHT"})
    moved = round(px_of(m) - px0, 1)
    J({"ev": "ANCHOR_SAVED", "state": "m2_train", **s2,
       "right_probe_moved": moved})
    png(p, "anchor_right", tag)
    log(f"ANCHOR SAVED px={s2['px']} php={s2['php']} moved={moved}")
    return s2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"gs{args.run}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jlog(jf, ev)

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    s0 = snap(m)
    J({"ev": "boot", "run": args.run, "firmware": fw, **s0})
    log(f"booted ({fw}) px={s0['px']} php={s0['php']}")

    # ---- ride M1 to the banner (proven c=107 path) ----
    banner = None
    for attempt in range(2):
        rec = run_once(p, m, J, tag, 200, control=False)
        J({"ev": "E2E", "attempt": attempt, **rec})
        log(f"run_once#{attempt}: {rec['outcome']} c={rec['end_chunk']}")
        if rec["outcome"] == "MISSION_BANNER":
            banner = rec
            break
    if banner is None:
        out = {"verdict": "FAILED", "why": "M1 banner not reached in 2 "
               "run_once attempts", "boot": s0}
        with open(os.path.join(EVID, f"report_{tag}.json"), "w") as fh:
            json.dump(out, fh, indent=1, default=str)
        J({"ev": "RUN_DONE", **out})
        jf.close()
        return 0

    # ---- wait for the countdown signature; snapshot "m2_gate" ----
    gate_f = None
    f = 0
    while f < COUNTDOWN_WAIT_F:
        kind, s = classify(m)
        if kind == "m2_spawn":
            sp = try_anchor(p, m, J, tag)
            finish(p, m, J, tag, t0, s0, {"spontaneous_spawn": bool(sp)},
                   sp is not None, None)
            jf.close()
            return 0
        if kind == "countdown":
            gate_f = f
            break
        p.core.run(30, set())
        f += 30
    if gate_f is None:
        out = {"verdict": "INCONCLUSIVE",
               "why": "countdown signature never appeared after banner",
               "banner": banner}
        with open(os.path.join(EVID, f"report_{tag}.json"), "w") as fh:
            json.dump(out, fh, indent=1, default=str)
        J({"ev": "RUN_DONE", **out})
        jf.close()
        return 0
    p.save_state("m2_gate")
    np.savez_compressed(os.path.join(EVID, f"{tag}_gatestart.npz"),
                        ram=m.ram.copy())
    J({"ev": "GATE_SAVED", "state": "m2_gate", "f_after_banner": gate_f,
       **snap(m)})
    log(f"gate saved at f={gate_f} after banner")

    # ---- arm 1: QUIET self-resolve.  Session-6 record (m2_train_advance
    # docstring): the M1->M2 ladder tally->countdown->loading->score
    # reset->spawn is INPUT-FREE and self-resolves; input inside it
    # re-arms the end machinery.  The 41/41-endzone sweep result (gs1)
    # confirms: every tap lands in the endzone.  So FIRST just watch,
    # quietly, past the whole loading window. ----
    table = []
    saved = False
    spawn = None
    quiet_f = 0
    while quiet_f < 5400:
        kind, s = classify(m)
        if kind == "m2_spawn":
            sp = try_anchor(p, m, J, tag)
            if sp:
                saved, spawn = True, sp
                break
        p.core.run(30, set())
        quiet_f += 30
    J({"ev": "QUIET_WATCH", "f": quiet_f, "saved": saved,
       "final_kind": classify(m)[0]})
    log(f"quiet watch f={quiet_f} saved={saved}")

    # ---- arm 2: the K sweep (only if quiet failed) ----
    for K in range(0, K_MAX + 1, K_STEP):
        if time.time() - t0 > SWEEP_WALL_S:
            J({"ev": "SWEEP_WALL", "K": K})
            break
        p.load_state("m2_gate")
        p.core.run(K, set())
        p.core.run(12, {"START"})
        outcome = None
        poll = 0
        while poll < POLL_F:
            kind, s = classify(m)
            if kind == "m2_spawn":
                outcome = "m2_spawn"
                break
            if kind == "endzone":
                outcome = "endzone"
                break
            poll += POLL_STEP
            p.core.run(POLL_STEP, set())
        if outcome is None:
            kind, s = classify(m)
            outcome = f"no_take({kind})"
        row = {"K": K, "outcome": outcome}
        if outcome == "m2_spawn":
            row["snap"] = s
            png(p, f"hit_K{K:03d}", tag)
            sp = try_anchor(p, m, J, tag)
            if sp:
                saved, spawn = True, sp
                row["anchor_saved"] = True
                table.append(row)
                break
            row["anchor_saved"] = False
        table.append(row)
        J({"ev": "K_RESULT", **row})
        log(f"K={K:3d} -> {outcome}")
    finish(p, m, J, tag, t0, s0,
           {"sweep": table, "gate_f": gate_f}, saved, spawn)
    jf.close()
    return 0


def finish(p, m, J, tag, t0, s0, extra, saved, spawn):
    out = {"verdict": "ANCHOR_SAVED" if saved else "INCONCLUSIVE",
           "boot": s0, "anchor_saved": saved, "spawn": spawn,
           "wall_total_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run,
           "game_sha256": sha_file(DISC), **extra}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    J({"ev": "RUN_DONE", "verdict": out["verdict"],
       "anchor_saved": saved, "wall_total_s": out["wall_total_s"]})
    log(f"DONE verdict={out['verdict']} saved={saved}")


if __name__ == "__main__":
    sys.exit(main())
