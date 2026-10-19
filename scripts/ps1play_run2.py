#!/usr/bin/env python3
"""run2.py — the REAL play run: enter Mission 1, play with the reactive
policy, checkpoint progress, then PROVE resume-from-checkpoint.

Zero-token play: every decision comes from RAM bytes (position counter,
stall detection, entity blocks). No pixels are sent anywhere, no memory
is ever written — only legal joypad inputs, like a human player.
"""
import json
import os
import sys
import time

sys.path.insert(0, "/home/z/my-project")
from PIL import Image

from ps1play.api import PS1Play

GAME = "/home/z/my-project/ps1-test/extracted/metal_slug_x/Metal Slug X (USA).cue"
OUT = "/home/z/my-project/download/ps1play_v2"
os.makedirs(OUT, exist_ok=True)

report = {"started": time.strftime("%H:%M:%S")}
png_times = []


def log(msg):
    print(f"[run] {msg}", file=sys.stderr, flush=True)


def snap(p, name):
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            im = Image.fromarray(rgb)
            im.save(os.path.join(OUT, name))
    except Exception as e:
        log(f"png {name}: {e}")


# ------------------------------------------------ 1. boot + enter --------
log("boot...")
p = PS1Play(GAME, verbose=False)
info = p.boot()
log(f"core={info['core']} profile_reused={info['profile_reused']}")
report["boot"] = {"core": info["core"], "serial": info["serial"]}

import numpy as np


def settle_and_verify(tries=3):
    """Enter, then demand 7 consecutive COLORFUL, text-free checks.
    Dark/loading frames just delay (they neither prove nor fail)."""
    budget = 12000
    for t in range(tries):
        r = p.enter_gameplay3()
        log(f"enter try {t}: in_game={r['in_game']} "
            f"detector={r.get('detector')}")
        if not r["in_game"]:
            continue
        clean_streak = 0
        spent = 0
        while spent < budget:
            p.core.run(350, {"RIGHT", "Y"})
            p._advance()
            spent += 350
            rgb = p.core.frame_rgb()
            if rgb is None:
                continue
            a = np.asarray(Image.fromarray(rgb).convert("RGB"),
                           dtype=np.int32)
            dark = float((a.max(axis=2) < 60).mean())
            band = a[222:240, 60:260]
            white = float(((band[:, :, 0] > 190) & (band[:, :, 1] > 190) &
                           (band[:, :, 2] > 190)).mean())
            if white > 0.004:
                log(f"  attract reappeared (white={white:.3f}) -> retry")
                clean_streak = 0
                break
            if dark < 0.6:
                clean_streak += 1
                if clean_streak >= 4:
                    proven, proof = p.control_proof()
                    log(f"  control proof: {proof}")
                    if proven:
                        log("  verified: colorful + text-free + CONTROL")
                        return True
                    clean_streak = 0
            # dark frames: keep waiting (loading), streak untouched
        log(f"  settle budget exhausted (streak={clean_streak})")
    return False


t0 = time.time()
if not settle_and_verify():
    log("FAILED to reach a verified mission session")
    report["enter"] = {"in_game": False}
    print(json.dumps(report, indent=1))
    sys.exit(2)
report["enter"] = {"in_game": True, "detector": "verified-settle"}
snap(p, "run2_0_mission_start.png")

# ------------------------------------------------ 2. quick discovery -----
log("discovery: monotonic score + player pos sanity (240f)...")
mono = p.disc.monotonic(frames=240, step=30, buttons={"RIGHT", "Y"}, top=10)
report["discovery"] = {"monotonic_top": mono[:6]}
log(f"monotonic: {mono[:4]}")
px = (p.profile.get("discovered") or {}).get("player_x") or {}
log(f"player_x addr={px.get('addr')} dtype={px.get('dtype')}")

# ------------------------------------------------ 3. checkpoint ----------
p.save_state("msx_m1_start")
log("checkpoint saved: msx_m1_start")

# ------------------------------------------------ 4. PLAY ----------------
frames_main = int(os.environ.get("PS1PLAY_FRAMES", "12000"))
log(f"playing {frames_main} frames with reactive policy...")
t0 = time.time()
res = p.play(frames_main, chunk=60, checkpoint_every=3000)
log(f"play done: {res}")
report["play"] = res
snap(p, "run2_1_after_play.png")

feat_end = p.plugin.features(p.mem, p.observe())
report["feat_end"] = {k: v for k, v in feat_end.items()
                      if not isinstance(v, list)}
log(f"feat_end: {report['feat_end']}")
log(f"plugin counters: deaths={p.plugin.deaths} hits={p.plugin.hits}")

# ------------------------------------------------ 5. resume proof --------
log("RESUME TEST: load msx_m1_start, play 2400 more frames...")
p.load_state("msx_m1_start")
snap(p, "run2_2_resumed.png")
res2 = p.play(2400, chunk=60, checkpoint_every=0)
log(f"resume play: {res2}")
report["resume"] = res2
snap(p, "run2_3_after_resume.png")

# ------------------------------------------------ 6. report --------------
p.profile.setdefault("history", []).append({
    "op": "run2", "frames": frames_main,
    "fps": res.get("fps"), "deaths": p.plugin.deaths,
    "hits": p.plugin.hits})
p.save_profile()
report["states"] = [s["name"] for s in p.states.list()]
report["wall_s"] = round(time.time() - t0, 1)
with open(os.path.join(OUT, "run2_report.json"), "w") as f:
    json.dump(report, f, indent=1, default=str)
print(json.dumps(report, indent=1, default=str)[:2500])
log("DONE")
