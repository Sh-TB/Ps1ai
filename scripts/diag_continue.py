#!/usr/bin/env python3
"""diag_continue.py — get to the continue screen, then try every button
and WATCH (PNG each step) what actually happens."""
import sys, os
sys.path.insert(0, "/home/z/my-project")
sys.path.insert(0, "/home/z/my-project/scripts")
from ps1play.api import PS1Play
from mission import ensure_mission, responsive, png

OUT = "/tmp/continue_dbg"
os.makedirs(OUT, exist_ok=True)

p = PS1Play(GAME_CUE := "/home/z/my-project/ps1-test/emu/games/"
                        "Metal Slug X (USA).cue")
p.boot()
r = p.enter_gameplay3()
print("enter:", r.get("in_game"), flush=True)

# force our way to a dead state quickly: stand still in the mission
# (gate recovery will land us on continue if dead)
m = ensure_mission(p, tries=3, log=print)
print("gate:", m.get("in_mission"), flush=True)
if m.get("in_mission"):
    # die on purpose: stand still for a long time (enemies kill us)
    for k in range(6):
        p.core.run(600, set())
        p._advance()
    ok, (i1, rr) = responsive(p)
    print("after standing still: responsive =", ok, (i1, rr), flush=True)
    png(p, f"{OUT}/after_stand.png")

# now try buttons on the (presumed) continue screen
png(p, f"{OUT}/00_state.png")
seq = [
    ("START_tap", [{"START"}, 15]),
    ("wait30", [set(), 30]),
    ("png", None),
    ("START_hold60", [{"START"}, 60]),
    ("wait200", [set(), 200]),
    ("png", None),
    ("A_tap", [{"A"}, 15]),
    ("wait200", [set(), 200]),
    ("png", None),
    ("B_tap", [{"B"}, 15]),
    ("wait200", [set(), 200]),
    ("png", None),
    ("STARTx2", [{"START"}, 15]),
    ("wait120", [set(), 120]),
    ("START2", [{"START"}, 15]),
    ("wait500", [set(), 500]),
    ("png", None),
]
n = 0
for step in seq:
    if step[0] == "png":
        n += 1
        png(p, f"{OUT}/{n:02d}_step.png")
        ok, (i1, rr) = responsive(p)
        print(f"step{n}: responsive={ok} idle={i1} run={rr}", flush=True)
    else:
        p.core.run(step[1][1], step[1][0])
        p._advance()
print("done")
