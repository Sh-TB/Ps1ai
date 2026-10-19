#!/usr/bin/env python3
"""diag_grenade.py — what RAM word REALLY changes when A (grenade) is
pressed? Full-RAM diff from an identical savestate, twice, plus jump
diff for coords. Decisive empirical answer, zero guessing."""
import sys, os, json, time
sys.path.insert(0, "/home/z/my-project")
import numpy as np
from ps1play.api import PS1Play

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"

p = PS1Play(GAME)
p.boot()
r = p.enter_gameplay3()
print("enter:", r.get("in_game"), flush=True)

def diffset(base_state, frames_before=8, action=None, frames_after=90, topn=30):
    p.load_state(base_state)
    p.core.run(frames_before, set())
    s0 = p.mem.snapshot()
    if action:
        p.core.run(15, action)
    p.core.run(frames_after, set())
    s1 = p.mem.snapshot()
    d = np.flatnonzero(s0[:0x1FC000] != s1[:0x1FC000])
    out = []
    for a in d[:topn * 6]:
        out.append((a, s0[a], s1[a]))
    return out, len(d)

p.save_state("gbase")
# settle so ambient churn passes, then capture A-diff twice
p.core.run(240, {"RIGHT", "Y"})
p._advance()
p.save_state("gbase2")

for trial, act in ((1, {"A"}), (2, {"A"}), (3, set()), (4, {"B"})):
    ch, n = diffset("gbase2", action=act)
    print(f"--- trial {trial} action={act} total_changed_bytes={n}", flush=True)
    # group into runs and show u16 interpretations
    a = 0
    shown = 0
    while a < len(ch) and shown < 14:
        addr, v0, v1 = ch[a]
        print(f"  byte {addr:#07x}: {v0:#04x}->{v1:#04x} | "
              f"u16@{addr & ~1:#07x}: "
              f"{p.mem.u16(addr & ~1):#06x}", flush=True)
        a += 1
        shown += 1

# dump a window around the two interesting zones for manual reading
for zone in (0xEED80, 0x0398A0):
    print(f"=== window {zone:#07x} ===")
    print(p.mem.hexdump(zone, 64))
print("done")
