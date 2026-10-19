#!/usr/bin/env python3
"""diag_input.py — equal-duration action diffing: what does A/B/RIGHT
ACTUALLY change vs idle, from the same savestate? Plus visual PNGs."""
import sys, os
sys.path.insert(0, "/home/z/my-project")
import numpy as np
from ps1play.api import PS1Play

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
OUT = "/tmp/diag_input"
os.makedirs(OUT, exist_ok=True)

p = PS1Play(GAME)
p.boot()
r = p.enter_gameplay3()
print("enter:", r.get("in_game"), flush=True)
p.save_state("ib")


def png(name):
    try:
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).resize((320, 240)).save(
                os.path.join(OUT, name))
    except Exception as e:
        print("png fail", e)


def run_trial(tag, action):
    """8f idle + 15f action + 90f idle — same duration for every trial."""
    p.load_state("ib")
    p.core.run(8, set())
    s0 = p.mem.snapshot()
    p.core.run(15, action)
    p.core.run(90, set())
    s1 = p.mem.snapshot()
    png(f"{tag}.png")
    return s0, s1


s_idle1, s_idle2 = run_trial("idle", set())
sa0, sa1 = run_trial("A", {"A"})
sb0, sb1 = run_trial("B", {"B"})
sr0, sr1 = run_trial("RIGHT", {"RIGHT"})

def cset(a, b):
    return set(np.flatnonzero(a[:0x1FC000] != b[:0x1FC000]).tolist())

only_A = cset(sa0, sa1) - cset(s_idle1, s_idle2)
only_B = cset(sb0, sb1) - cset(s_idle1, s_idle2)
only_R = cset(sr0, sr1) - cset(s_idle1, s_idle2)
print(f"action-unique bytes: A={len(only_A)} B={len(only_B)} "
      f"RIGHT={len(only_R)}", flush=True)

def show(tag, st, n=16):
    print(f"--- {tag}", flush=True)
    for a in sorted(st)[:n]:
        print(f"  {a:#07x}: {st[a]:#04x}->{sa1[a] if tag=='A' else sb1[a] if tag=='B' else sr1[a]:#04x}",
              flush=True)

show("onlyA", only_A)
show("onlyB", only_B)
show("onlyRIGHT", only_R)

# u16 view of the action effects: decrements by 1 = bomb counters
print("--- u16 decrements caused by A:", flush=True)
a0 = sa0[:0x1FC000].view("<u2"); a1 = sa1[:0x1FC000].view("<u2")
i0 = s_idle1[:0x1FC000].view("<u2"); i1 = s_idle2[:0x1FC000].view("<u2")
d = a1.astype(np.int32) - a0.astype(np.int32)
di = i1.astype(np.int32) - i0.astype(np.int32)
extra = np.flatnonzero((d != di) & (d != 0))
for w in extra[:30]:
    print(f"  u16@{w*2:#07x}: {a0[w]} -> {a1[w]} (idle: {i0[w]}->{i1[w]})",
          flush=True)
print("done")
