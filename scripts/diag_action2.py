#!/usr/bin/env python3
"""diag_action2.py — definitive action-diff from a LIVE mission state:
what EXACTLY changes when A (grenade) is pressed vs an idle trial of the
same duration? u16 and u8 views, exact -1 filter, plus RIGHT trial for
the pad word. This gives the true bombs/hp addresses in OUR revision."""
import sys, os, json
sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")
import numpy as np
from ps1play.api import PS1Play
from mission import ensure_mission

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"

p = PS1Play(GAME)
p.boot()
r = p.enter_gameplay3()
print("enter:", r.get("in_game"), flush=True)
m = ensure_mission(p, tries=6, log=print)
print("gate:", m, flush=True)
p.save_state("live2")

def trial(action):
    """8f idle + 15f action + 90f idle; returns (s0, s1) snapshots."""
    p.load_state("live2")
    p.core.run(8, set())
    s0 = p.mem.snapshot()
    p.core.run(15, action)
    p.core.run(90, set())
    p._advance()
    return s0, p.mem.snapshot()

i0, i1 = trial(set())          # idle control
a0, a1 = trial({"A"})          # grenade
r0, r1 = trial({"RIGHT"})      # movement

ai0 = i0[:0x1FC000].view("<u2").astype(np.int32)
ai1 = i1[:0x1FC000].view("<u2").astype(np.int32)
aa0 = a0[:0x1FC000].view("<u2").astype(np.int32)
aa1 = a1[:0x1FC000].view("<u2").astype(np.int32)

# word changed in A-trial but NOT in idle-trial
d_idle = ai1 - ai0
d_a = aa1 - aa0
extra = (d_a != d_idle)
cands = np.flatnonzero(extra & (d_a == -1))
print(f"\n=== u16 EXACT -1 (A vs idle): {len(cands)} ===", flush=True)
for w in cands[:20]:
    print(f"  u16@{w*2:#07x}: {aa0[w]} -> {aa1[w]}  (idle {ai0[w]}->{ai1[w]})",
          flush=True)

# u8 view -1
b0 = a0[:0x1FC000].astype(np.int32)
b1 = a1[:0x1FC000].astype(np.int32)
bi0 = i0[:0x1FC000].astype(np.int32)
bi1 = i1[:0x1FC000].astype(np.int32)
db = (b1 - b0) - (bi1 - bi0)
c8 = np.flatnonzero((b1 != b0) & (db == -1))
print(f"=== u8 -1 candidates: {len(c8)} ===", flush=True)
for w in c8[:20]:
    print(f"  u8@{w:#07x}: {b0[w]} -> {b1[w]}", flush=True)

# any extra change caused by A (any delta) — top context window
any_extra = np.flatnonzero(extra)
print(f"=== u16 any-extra-change (A vs idle): {len(any_extra)} ===",
      flush=True)
for w in any_extra[:24]:
    print(f"  u16@{w*2:#07x}: {aa0[w]} -> {aa1[w]} (d={int(d_a[w])}, "
          f"idle d={int(d_idle[w])})", flush=True)

# RIGHT: pad + movement counters
ri0 = r0[:0x1FC000].view("<u2").astype(np.int32)
ri1 = r1[:0x1FC000].view("<u2").astype(np.int32)
dr = ri1 - ri0
extra_r = np.flatnonzero((dr != d_idle) & (dr != 0))
print(f"=== RIGHT-extra u16: {len(extra_r)} (pad inc candidates) ===",
      flush=True)
for w in extra_r[:20]:
    print(f"  u16@{w*2:#07x}: {ri0[w]} -> {ri1[w]} (idle {ai0[w]}->{ai1[w]})",
          flush=True)

print("pad word 0x0D494A during RIGHT trial:", hex(p.mem.u16(0x0D494A)),
      flush=True)
print("done")
