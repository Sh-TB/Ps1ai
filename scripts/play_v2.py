#!/usr/bin/env python3
"""play_v2.py — the REAL play session: boot (proven trajectory timeline),
then play Mission 1 with the plugin policy driven by the verified
RAM telemetry (hp/bombs/lives/timer). Checkpoints + evidence PNGs."""
import json
import os
import sys
import time

sys.path.insert(0, "/home/z/my-project")
from ps1play.api import PS1Play

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
EVID = "/home/z/my-project/download/ps1play_v2"
OUT = "/home/z/my-project/ps1-test/emu/states/play_v2_report.json"
os.makedirs(EVID, exist_ok=True)

report = {"started": time.strftime("%Y-%m-%d %H:%M:%S")}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def png(p, name):
    try:
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).resize((320, 240)).save(
                os.path.join(EVID, name))
    except Exception as e:                                  # noqa: BLE001
        log("png fail:", e)


p = PS1Play(GAME, verbose=False)
info = p.boot()
log("boot:", info)
r = p.enter_gameplay3()
log("enter:", {k: v for k, v in r.items() if k != "proof"})
report["boot"] = info
report["enter"] = {k: v for k, v in r.items() if k != "proof"}
if not r.get("in_game"):
    sys.exit("!! boot failed")

# per-boot semantic recalibration (RAM layout shifts between boots!)
sys.path.insert(0, "/home/z/my-project/scripts")
from calibrate import calibrate
cal = calibrate(p)
log("calibration:", json.dumps(cal))
report["calibration"] = cal

png(p, "play_00_mission_start.png")
p.save_state("mission1_start")
log("state saved: mission1_start")

# ---------------- the play loop with live telemetry ----------------
from collections import defaultdict

evc = defaultdict(int)
tel = []                       # telemetry samples every 20 chunks
CH, NC = 60, 340               # 340*60 = 20400 frames ~= 5.7 game-minutes
stall, last_x = 0, None
t0 = time.time()
for i in range(NC):
    obs = p.observer.observe(p.t)
    feat = p.plugin.features(p.mem, obs)
    for e in feat.get("events", ()):
        evc[e] += 1
    watched = feat.get("x")
    if watched is not None and last_x is not None:
        stall = stall + CH if watched == last_x else 0
    last_x = watched
    ctx = {"t": p.t, "chunk": CH, "stall": stall, "feat": feat, "obs": obs}
    done = 0
    for s_ in (p.plugin.policy(ctx) or []):
        k = min(s_["frames"], CH - done)
        if k > 0:
            p.core.run(k, s_["btns"])
            done += k
    if done < CH:
        p.core.run(CH - done)
    p._advance()
    if ctx.get("stall_reset"):
        stall = 0
    if i % 20 == 19:
        tel.append({"t": p.t, "feat": {k: v for k, v in feat.items()
                                       if k != "events"}})
        png(p, f"play_{(i // 20) + 1:02d}_mid.png")
    if i in (170, 335):
        name = "mission1_half" if i == 170 else "mission1_latest"
        p.save_state(name)
        log("checkpoint:", name, "at t =", p.t)

wall = time.time() - t0
report["play"] = {"frames": NC * CH, "wall_s": round(wall, 1),
                  "fps": round(NC * CH / wall, 1)}
report["events"] = dict(evc)
report["telemetry"] = tel
report["states"] = [s["name"] for s in p.states.list()]
png(p, "play_99_end.png")

# quick resume proof: reload the half checkpoint and keep playing
p.load_state("mission1_half")
obs = p.observer.observe(p.t)
feat = p.plugin.features(p.mem, obs)
report["resume_proof"] = {"loaded": "mission1_half", "feat": feat}
p.core.run(600, {"RIGHT", "Y"})
p._advance()
png(p, "play_98_resumed.png")

report["finished"] = time.strftime("%H:%M:%S")
json.dump(report, open(OUT, "w"), indent=1)
p.save_profile()
log("report ->", OUT)
print(json.dumps({"enter": report["enter"], "play": report["play"],
                  "events": report["events"],
                  "states": report["states"]}, indent=1))
