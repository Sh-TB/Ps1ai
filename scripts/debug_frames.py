#!/usr/bin/env python3
"""Debug: exact frames issued by MSX boot_script vs frames_run counter."""
import sys
sys.path.insert(0, "/home/z/my-project")
from ps1play.api import PS1Play  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
p = PS1Play(GAME)
p.boot()
steps = p.plugin.boot_script()
total = 0
for st in steps:
    if st["op"] == "wait":
        total += st["frames"]
    elif st["op"] == "tap":
        total += st.get("frames", 15) + st.get("every", 285)
    elif st["op"] == "hold":
        total += st["frames"]
print("steps:", len(steps), "expected frames:", total)
taps = [s for s in steps if s["op"] == "tap"]
print("taps:", len(taps), "waits:", len([s for s in steps if s['op'] == 'wait']))
p.core.run(100)
print("after 100:", p.core.frames_run, p.core.frame_count)
p.core.run(300)
print("after +300:", p.core.frames_run, p.core.frame_count)
res = p.run_steps(steps)
print("after boot_script:", p.core.frames_run, p.core.frame_count, res)
p.core.shutdown()
