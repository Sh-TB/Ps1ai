#!/usr/bin/env python3
"""diag_action3.py — from a TRULY live mission state:
1. pad word probes: hold each button alone, read 0x0D494A mid-hold
2. A-diff vs idle diff (equal durations) -> true bombs/hp candidates
3. resilient: refresh the live state after any death"""
import sys, os
sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")
import numpy as np
from ps1play.api import PS1Play
from mission import ensure_mission, responsive, recover

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"

p = PS1Play(GAME)
p.boot()
r = p.enter_gameplay3()
print("enter:", r.get("in_game"), flush=True)
m = ensure_mission(p, tries=6, log=print)
print("gate:", m.get("in_mission"), flush=True)


def refresh():
    ok, _ = responsive(p)
    if not ok:
        recover(p, log=print)
        ok, _ = responsive(p)
    p.save_state("live3")
    return ok


# ---------------- 1) pad word probes ----------------
print("\n=== pad word 0x0D494A bit probes ===", flush=True)
refresh()
for btn in ("RIGHT", "Y", "A", "B", "LEFT"):
    p.load_state("live3")
    p.core.run(20, set())
    idle_w = p.mem.u16(0x0D494A)
    p.core.run(30, {btn})
    held_w = p.mem.u16(0x0D494A)          # still held
    p.core.run(10, set())
    p._advance()
    print(f"  {btn:6s}: idle={idle_w:#06x} held={held_w:#06x} "
          f"diff={held_w & ~idle_w & 0xFFFF:#06x}", flush=True)

# ---------------- 2) A-diff vs idle-diff ----------------
def trial(base, action):
    p.load_state(base)
    p.core.run(8, set())
    s0 = p.mem.snapshot()
    p.core.run(15, action)
    p.core.run(90, set())
    p._advance()
    return s0, p.mem.snapshot()


for round_k in range(2):
    if not refresh():
        print("!! cannot re-enter mission", flush=True)
        break
    i0, i1 = trial("live3", set())
    a0, a1 = trial("live3", {"A"})
    ai0 = i0[:0x1FC000].view("<u2").astype(np.int32)
    ai1 = i1[:0x1FC000].view("<u2").astype(np.int32)
    aa0 = a0[:0x1FC000].view("<u2").astype(np.int32)
    aa1 = a1[:0x1FC000].view("<u2").astype(np.int32)
    d_idle = ai1 - ai0
    d_a = aa1 - aa0
    extra = (d_a != d_idle)
    c16 = np.flatnonzero(extra & (d_a == -1))
    c_any = np.flatnonzero(extra & (d_a != 0))
    print(f"\n=== round {round_k}: u16 exact -1: {len(c16)}, "
          f"any-extra: {len(c_any)} ===", flush=True)
    for w in c16[:15]:
        print(f"  u16@{w*2:#07x}: {aa0[w]} -> {aa1[w]} "
              f"(idle {ai0[w]}->{ai1[w]})", flush=True)
    for w in c_any[:15]:
        print(f"  +u16@{w*2:#07x}: {aa0[w]} -> {aa1[w]} (d={int(d_a[w])})",
              flush=True)
    if len(c16):
        print("FOUND bombs candidates", flush=True)
        break
    # hp candidates: u16 in 90..110 that dropped in the ACTION trial (stab)
    drop_any = np.flatnonzero((d_idle < 0) & (ai0 >= 20) & (ai0 <= 110))
    print(f"hp-ish decayers (idle trial): {len(drop_any)}: "
          f"{[hex(int(w) * 2) for w in drop_any[:10]]}", flush=True)
print("done")
