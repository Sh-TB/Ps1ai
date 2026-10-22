#!/usr/bin/env python3
"""w2_arena_inspect.py — verify WHAT the freshly captured `arena`
savestate actually contains (frame + telemetry + slot table).

The reach rerun finished in 3.2 s wall, which is physically impossible
for a real boot + 18 chunks. Before building probes on this savestate,
look at it.
"""
from __future__ import annotations

import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                       # noqa: E402
from ps1play.telemetry import TelemetryAdapter      # noqa: E402
from mission import idle_churn                      # noqa: E402
from issue4_controller import boot                  # noqa: E402
import msx_gate_probe as gp                         # noqa: E402

EVID = gp.EVID

p, fw = boot()
log = gp.log
log("booted:", fw)

try:
    p.load_state("arena")
    log("loaded `arena`")
except Exception as e:                              # noqa: BLE001
    log("NO arena savestate:", e)
    sys.exit(1)

# --- settle 30 frames (no inputs), then snapshot everything
p.core.run(30, set())

m = p.mem
tel = TelemetryAdapter(p)
t = tel.snapshot()
prog = m.u16(gp.A_PROGRESS)
score = m.u16(gp.A_SCORE)
flags = m.u16(gp.A_FLAGS)
timer = m.u16(gp.A_TIMER16)
ch = idle_churn(p, 30)
log(f"prog={prog} score={score} flags={flags} timer16={timer} churn={ch}")
log("telemetry:", json.dumps(t, default=str)[:400])

# --- full slot table dump (0..40): hp / w78 / w7a / spawn(x@0xA0,4B)
slots = {}
for s in range(40):
    base = gp.TABLE + s * gp.STRIDE
    slots[s] = {
        "hp": m.u16(base + gp.HP_OFF),
        "w78": m.u16(base + 0x78),
        "w7a": m.u16(base + 0x7A),
        "a0_u32": hex(m.u32(base + 0xA0)),
        "a0_lo16": m.u16(base + 0xA0),
        "a4_lo16": m.u16(base + 0xA4),
    }
live = {s: v for s, v in slots.items() if v["hp"] or v["w78"] or v["w7a"]}
log("live slots:", json.dumps(live, indent=0)[:1500])

# --- PNGs for eyeballing
gp.png(p, "w2_arena_loaded.png")
p.core.run(120, set())
gp.png(p, "w2_arena_after120f.png")
m2 = p.mem
log("after 120f idle: prog=%d score=%d churn=%s" %
    (m2.u16(gp.A_PROGRESS), m2.u16(gp.A_SCORE),
     idle_churn(p, 30)))

json.dump({"prog": prog, "score": score, "flags": flags,
           "timer16": timer, "slots": {str(k): v for k, v in slots.items()}},
          open(os.path.join(EVID, "w2_arena_inspect.json"), "w"), indent=1)
log("saved w2_arena_inspect.json")
