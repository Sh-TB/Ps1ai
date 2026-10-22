#!/usr/bin/env python3
"""w2_reach2.py — corrected arena-isolation run (Issue #5 focused
follow-up, session-local probe).

Why this exists: the committed msx_gate_probe.stage_reach fired its
capture on the SECOND frozen-progress streak, which this boot turned
out to be an ATTRACT-DEMO frame (PRESS START overlay visible in the
saved PNG). The first frozen streak (prog=139 x 5 chunks, c8..c12) was
the real camera-gate lock but was skipped by `chunk > 12`.

Fixes here:
  1. capture the FIRST frozen streak >= 4 chunks (chunk > 6), and keep
     capturing later candidates as arena2/arena3 (never overwrite a
     good one with a worse one)
  2. REAL-PLAY gate at capture: the demo PRESS-START overlay sits in
     the top-right band; blink is ~30f on / 30f off -> require the
     band to be white-free across a 120f rolling max
  3. per-chunk PNG only at capture; full history JSONL for post-hoc
     analysis (the c0-c5 oscillation needs explanation either way)

EXPLORATION DISCLOSURE: hp_pair freeze (0xCA2F6/0xCA2FE) active from
the cb0 anchor; continues accepted via the disclosed v1 rescue.
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

from ps1play import labconfig                       # noqa: E402
from mission import idle_churn                      # noqa: E402
import msx_gate_probe as gp                         # noqa: E402

EVID = gp.EVID
A_PROGRESS = gp.A_PROGRESS
A_TIMER16 = gp.A_TIMER16
A_FLAGS = gp.A_FLAGS


def demo_band_white(p, samples=4, every=30):
    """Max white-pixel fraction in the top-right PRESS-START band over
    ~samples*every frames (blink-aware). Demo overlay: text is bright
    white; real play keeps this band dark."""
    mx = 0.0
    for i in range(samples):
        rgb = p.core.frame_rgb()
        if rgb is not None:
            a = np.asarray(Image.fromarray(rgb).convert("RGB"),
                           dtype=np.int32)[6:30, 200:318]
            white = float(((a[:, :, 0] > 200) & (a[:, :, 1] > 200) &
                           (a[:, :, 2] > 200)).mean())
            mx = max(mx, white)
        p.core.run(every, set())
    return mx


def main(max_chunks=400):
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    m.u16(A_PROGRESS)
    g = __import__("mission").ensure_mission(p, tries=4, log=gp.log,
                                             want_hp_cands=False)
    gp.log("mission gate:", g.get("in_mission"))
    p.save_state("cb0")
    session = gp.freeze_now(p, "w2_reach2")
    gp.log(f"freeze cb0: pair=({p.mem.u16(gp.A_PAIR0)},"
           f"{p.mem.u16(gp.A_PAIR1)})")

    hist = []
    captures = []
    max_ever = 0
    prog_streak = 0
    phase = 0
    for chunk in range(max_chunks):
        # 60-frame advance cadence (pit_run pattern: RIGHT + hop + fire)
        for f in range(60):
            btns = gp.advance_schedule(f)
            phase = gp._arm_frame(p, session, btns, phase)
        prog = m.u16(A_PROGRESS)
        hp0 = m.u16(gp.TABLE + gp.HP_OFF)
        flags = m.u16(A_FLAGS)
        churn = idle_churn(p, 30)
        max_ever = max(max_ever, prog)
        prog_streak = prog_streak + 1 if hist and \
            prog == hist[-1]["prog"] else 1
        row = {"chunk": chunk, "prog": prog, "hp0": hp0,
               "flags": flags, "churn": churn, "streak": prog_streak,
               "timer": m.u16(A_TIMER16)}
        hist.append(row)
        gp.log(f"c{chunk} prog={prog} hp0={hp0} churn={churn} "
               f"streak={prog_streak} maxE={max_ever} timer={row['timer']}")

        # ---- capture rule: FIRST frozen streak, real play only ----
        if (prog_streak >= 4 and max_ever >= 120 and hp0 > 50 and
                len(captures) < 3):
            dw = demo_band_white(p)
            name = "arena" if not captures else f"arena{len(captures) + 1}"
            p.save_state(name)
            gp.png(p, f"{name}_capture.png")
            captures.append({"state": name, "chunk": chunk, "prog": prog,
                             "hp0": hp0, "max_ever": max_ever,
                             "demo_band_white": round(dw, 4),
                             "real_play": dw < 0.02})
            gp.log(f"CAPTURE {name}: prog={prog} demo_band={dw:.4f} "
                   f"real_play={dw < 0.02}")
            if len(captures) >= 2 and all(c["real_play"]
                                          for c in captures):
                break
        # ---- silent-death / continue rescue (flags is unreliable) --
        if churn < 250:
            p.core.run(10, {"START"})
            p.core.run(70, set())
            for _ in range(70):
                p.core.run_frame()
                session.gs.tick()
            gp.log(f"c{chunk} rescue tap (churn={churn})")

    gp.unfreeze(session, "w2_reach2")
    out = {"fw": fw, "captures": captures,
           "hist": hist,
           "disclosure": "EXPLORATION: hp_pair freeze from cb0; "
                         "continue rescue taps on low churn",
           "wall_s": round(time.time() - t0, 1)}
    json.dump(out, open(os.path.join(EVID, "w2_reach2.json"), "w"),
              indent=1)
    gp.log("done:", bool(captures), "captures:", len(captures),
           "wall:", out["wall_s"], "s")
    return bool(captures)


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
