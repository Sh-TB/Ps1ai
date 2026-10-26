#!/usr/bin/env python3
"""msx_r11_section_write.py — Round 11 / Segment 2b: the gate probe.

Segment 2 (progress_watch v2) found the NATURAL kill-aligned
transitions at the px-2212 arena, reproduced twice, each holding >=5
polls (~300 f):

  SECTION_FLAGS      0x0EB5D0 : 1 -> 67   (near armored-trio kills)
  world_alive_latch  0x0EB5FC : 255 -> 0  (same events)

Question: is that state SUFFICIENT for the camera gate to release?
Round 8 held SECTION_FLAGS=9 (a guessed value) — no release.  This run
holds the OBSERVED post-squadron-fell values WITHOUT killing, then
walk-probes:

  control   : no writes, 300 f walk probe (baseline; CAMERA HELD 0/8
              in rounds 9-10)
  arm FLAGS : hold 0x0EB5D0 = 67 (u8)          -> walk probe
  arm LATCH : hold 0x0EB5FC = 0 (u8)           -> walk probe
  arm BOTH  : hold both                        -> walk probe

Every write is DISCLOSED CHEAT_ASSISTED_EXPLORATION (GS constant codes,
opt_in=True); each arm disables its codes and VERIFIES the restore.
Watched globals logged every 60 f.  Verdict per arm: GATE_OPENS
(px advance >= 100 beyond control AND/OR px past the pin) / HELD.
Evidence: scratch/round11_msx/section_write/. ONE beetle boot.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_r10_timergate as tg                          # noqa: E402
tg.OUTDIR = "/home/z/my-project/ps1ai/scratch/round11_msx/section_write"
from msx_r10_timergate import (                         # noqa: E402
    A_SCORE, PLAYER_HP, alive, px_of, png)
from msx_r11_mission_select import gs_codes, read_word  # noqa: E402
from ps1play.agent.cheatprof import (                   # noqa: E402
    CheatSession, CHEAT_ASSISTED)
from issue4_controller import boot                      # noqa: E402
from mission import ensure_mission                      # noqa: E402

OUTDIR = tg.OUTDIR
STATE = "wr9_arena"
PIN_PX = 2212.0
FLAGS_ADDR = 0x0EB5D0        # SECTION_FLAGS (u8 cell; u16 view 1->67)
LATCH_ADDR = 0x0EB5FC        # world-alive latch (u8 cell; 255->0)
WATCHED = {"world_alive_latch": LATCH_ADDR, "SECTION_STATE": 0x0EB5F4,
           "SECTION_FLAGS": FLAGS_ADDR, "SECTION_PROGRESS": 0x0EB5D4}
FLAGS_WORD = 0x0EE518


def log(*a):
    print("[r11-sw]", *a, file=sys.stderr, flush=True)


def watched_values(m):
    d = {k: int(m.u8(a)) for k, a in WATCHED.items()}
    d["FLAGS_WORD"] = int(m.u32(FLAGS_WORD))
    return d


def walk_probe(p, m, J, tag, frames=300):
    """Hold RIGHT for `frames`, return px trajectory + advance."""
    px0 = px_of(m)
    traj = [round(px0, 1)]
    for _ in range(frames // 30):
        p.core.run(30, {"RIGHT"})
        traj.append(round(px_of(m), 1))
    px1 = px_of(m)
    out = {"px0": round(px0, 1), "px1": round(px1, 1),
           "advance": round(px1 - px0, 1), "alive": bool(alive(m)),
           "past_pin": px1 > PIN_PX + 20.0}
    J({"ev": f"walk_{tag}", **out, "traj_last5": traj[-5:]})
    png(p, f"sw_{tag}_end.png")
    return out


def sample_window(p, m, J, tag, frames=180):
    for _ in range(frames // 60):
        p.core.run(60, set())
        J({"ev": f"obs_{tag}", "px": round(px_of(m), 1),
           "php": int(m.u16(PLAYER_HP)),
           "score": int(m.u32(A_SCORE)), **watched_values(m)})


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()
    trace_path = os.path.join(OUTDIR, "trace.jsonl")
    trace = open(trace_path, "a")

    def J(ev):
        ev["t"] = round(time.time() - t0, 1)
        trace.write(json.dumps(ev, default=str) + "\n")
        trace.flush()

    p, fw = boot()
    m = p.mem
    g = ensure_mission(p, tries=6, log=log, want_hp_cands=False)
    J({"ev": "boot", "fw": fw, "in_mission": bool(g.get("in_mission"))})
    if not g.get("in_mission"):
        json.dump({"verdict": "GATE_FAILED"},
                  open(os.path.join(OUTDIR, "report.json"), "w"), indent=1)
        return 2
    p.load_state(STATE)
    J({"ev": "state_loaded", "px": round(px_of(m), 1),
       "score": int(m.u32(A_SCORE)), **watched_values(m)})
    png(p, "sw_loaded.png")

    # ---- control arm (no writes) ----
    sample_window(p, m, J, "control_pre")
    ctl = walk_probe(p, m, J, "control")
    if not ctl["alive"]:
        p.load_state(STATE)
        J({"ev": "restore", "disclosed": True})
        ctl = walk_probe(p, m, J, "control_retry")

    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    arms = [
        ("flags67", [(FLAGS_ADDR, 67, "u8")]),
        ("latch0", [(LATCH_ADDR, 0, "u8")]),
        ("both", [(FLAGS_ADDR, 67, "u8"), (LATCH_ADDR, 0, "u8")]),
    ]
    results = {}
    try:
        for name, writes in arms:
            if not alive(m):
                p.load_state(STATE)
                J({"ev": "restore", "arm": name, "disclosed": True})
            codes = []
            for addr, val, enc in writes:
                pre = read_word(m, addr, enc)
                codes += gs_codes(addr, val, enc)
                J({"ev": "WRITE_ARMED", "arm": name, "addr": hex(addr),
                   "value": val, "enc": enc, "pre": pre,
                   "disclosed": True,
                   "mode": "CHEAT_ASSISTED_EXPLORATION"})
            session.enable(f"sw_{name}", codes)
            pres = {hex(addr): read_word(m, addr, enc)
                    for addr, val, enc in writes}
            sample_window(p, m, J, name, frames=120)
            res = walk_probe(p, m, J, name)
            session.disable(f"sw_{name}")
            restores = {}
            for addr, val, enc in writes:
                after = read_word(m, addr, enc)
                pre = pres[hex(addr)]
                restores[hex(addr)] = {
                    "pre": pre, "held": val, "after": after,
                    # honest: restored == back to the PRE value (the
                    # engine may itself write a third value after
                    # disable; that is recorded, not hidden)
                    "restore_ok": after == pre,
                    "engine_moved": after not in (pre, val)}
            J({"ev": "WRITE_RESTORED", "arm": name,
               "disclosed": True, **restores})
            res["restores"] = restores
            res["held_state"] = watched_values(m)
            results[name] = res
            p.core.run(120, set())
    finally:
        session.disable_all()
        J({"ev": "session_end", "word_final": watched_values(m)})

    ctl_adv = ctl["advance"]
    for name, r in results.items():
        r["verdict"] = ("GATE_OPENS" if (r["advance"] - ctl_adv >= 100.0
                                         or r["past_pin"]) else "HELD")
    verdict = ("GATE_OPENS:" + ",".join(n for n, r in results.items()
                                        if r["verdict"] == "GATE_OPENS")
               if any(r["verdict"] == "GATE_OPENS"
                      for r in results.values()) else "ALL_HELD")
    rep = {"schema": "ps1play-r11-section-write/1", "verdict": verdict,
           "control": ctl, "arms": results,
           "disclosed": "all writes CHEAT_ASSISTED_EXPLORATION, "
                        "GS constant codes, disabled + restore verified "
                        "per arm; savestate restores are disclosed retries",
           "wall_s": round(time.time() - t0, 1)}
    json.dump(rep, open(os.path.join(OUTDIR, "report.json"), "w"),
              indent=1)
    J({"ev": "final", "verdict": verdict})
    log("done:", verdict)
    return 0


if __name__ == "__main__":
    sys.exit(main())
