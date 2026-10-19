#!/usr/bin/env python3
"""PS1Play end-to-end demo with Metal Slug X (SLUS-01212).

Phase A  boot-to-gameplay via plugin boot script (RAM observation only)
Phase B  1-run pattern discovery (correlate / echo / monotonic) -> profile
Phase C  policy-driven play with journal + rolling checkpoints
Phase D  fresh session -> load_state -> keep playing (continue anywhere)

Everything the "agent" sees is compact JSON; zero pixels are analyzed.
"""
import json
import os
import shutil
import sys
import time

sys.path.insert(0, "/home/z/my-project")
from ps1play.api import PS1Play  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/download/ps1play_demo"
os.makedirs(OUT, exist_ok=True)
LOG = []


def say(title, obj=None):
    line = f"\n=== {title} ==="
    print(line)
    LOG.append(line)
    if obj is not None:
        s = json.dumps(obj, indent=1, default=str)
        print(s[:2200])
        LOG.append(s)
    return obj


t_all = time.time()

# ---------------- Phase A: boot to gameplay (adaptive) ----------------
p = PS1Play(GAME, journal_path=os.path.join(OUT, "journal.jsonl"))
say("A1 boot", p.boot())
res = p.enter_gameplay()
say("A2 enter_gameplay (adaptive taps + RAM probes)", res)
obs = p.observe()
say("A3 observe (RAM only)", obs)
png = os.path.join(OUT, "gameplay_start.png")
try:
    from PIL import Image
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(png)
        say(f"A3b human-reference frame -> {png}", {"note": "not used by agent"})
except Exception as e:
    print("png skip:", e)

# ---------------- Phase B: learn patterns (1st run) ----------------
say("B1 discover RIGHT (A/B windows)")
d = p.discover("RIGHT")
say("B2 correlate candidates (top)", d["correlate_RIGHT"][:5])
say("B3 input_echo", d.get("input_echo"))
say("B4 monotonic (during shooting)", p.discover_progress(180, buttons="RIGHT+Y"))
say("B5 save profile", p.save_profile())
p.save_state("stage1_start")
say("B6 savestates", p.states.list()[-3:])

# ---------------- Phase C: policy play ----------------
say("C1 play 5400 frames with plugin policy")
res = p.play(5400, chunk=60, checkpoint_every=1800)
say("C2 play result", res)
obs = p.observe()
say("C3 observe after play", obs)
try:
    rows = [json.loads(l) for l in open(os.path.join(OUT, "journal.jsonl"))]
    xs = [r["feat"].get("x") for r in rows if r["feat"].get("x") is not None]
    say("C4 level progress from journal (x tracker)",
        {"x_min": min(xs), "x_max": max(xs), "x_last": xs[-1],
         "active_windows_pct": round(100 * sum(
             1 for r in rows if r["changed"] > 20000) / len(rows))})
except Exception as e:
    print("journal summary skip:", e)
p.save_state("progress_A")
say("C5 report so far", p.report())
p.save_profile()
p.core.shutdown()

# ---------------- Phase D: fresh session, resume, keep playing ----------------
del p
p2 = PS1Play(GAME, journal_path=os.path.join(OUT, "journal2.jsonl"))
say("D1 fresh boot (profile auto-loaded)", p2.boot())
say("D2 load_state progress_A (NO re-boot of game flow!)",
    p2.load_state("progress_A"))
res = p2.play(1500, chunk=60, checkpoint_every=1800)
say("D3 continued play", res)
say("D4 observe", p2.observe())
p2.save_profile()
final = p2.report()
say("D5 FINAL REPORT", final)
p2.core.shutdown()

with open(os.path.join(OUT, "report.json"), "w") as f:
    json.dump(final, f, indent=1, default=str)
shutil.copy(p2.profile_path, os.path.join(OUT, "profile_metal_slug_x.json"))
for src in (os.path.join(OUT, "journal.jsonl"), os.path.join(OUT, "journal2.jsonl")):
    if os.path.exists(src):
        with open(src) as f:
            lines = f.readlines()
        with open(src.replace(".jsonl", "_tail.json"), "w") as f:
            json.dump({"rows": len(lines),
                       "last": [json.loads(x) for x in lines[-6:]]},
                      f, indent=1)
print(f"\nTOTAL wall time: {time.time() - t_all:.1f}s")
print("DEMO DONE")
