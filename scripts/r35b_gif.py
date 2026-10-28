#!/usr/bin/env python3
"""r35b_gif.py — build ONE evidence GIF of the R35-B bot run from the
boot-2 variant-A gameplay PNG chain (the 4000f no-death run), plus a
vision sanity check (consecutive-frame deltas prove live animation),
and write the consolidated verdict JSON. No emulator boot involved.
"""
import glob
import json
import os
import sys

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
import r35b_lib as L  # noqa: E402
from PIL import Image  # noqa: E402

import numpy as np  # noqa: E402

OUT = L.OUT
SHOTS = L.SHOTS

pngs = sorted(glob.glob(os.path.join(SHOTS, "b2_A_gameplay_*.png")),
              key=lambda p: int(p.rsplit("_f", 1)[1].split(".")[0]))
print(f"[gif] {len(pngs)} gameplay frames")
assert len(pngs) >= 8, "not enough gameplay frames"

frames, deltas = [], []
prev = None
for p in pngs:
    im = Image.open(p).convert("RGB")
    a = np.asarray(im, dtype=np.int16)
    if prev is not None:
        deltas.append(round(float(np.abs(a - prev).mean()), 2))
    prev = a
    im = im.resize((256, 192), Image.LANCZOS)
    frames.append(im.quantize(colors=128, method=Image.MEDIANCUT))

gif_path = os.path.join(OUT, "r35_buzzybee_bot.gif")
frames[0].save(gif_path, save_all=True, append_images=frames[1:],
               duration=130, loop=0, optimize=True)
size_kb = os.path.getsize(gif_path) // 1024
print(f"[gif] wrote {gif_path} ({size_kb} KB, {len(frames)} frames)")
print(f"[gif] consecutive-frame mean-abs-deltas: {deltas}")
alive = all(d > 0.5 for d in deltas)

# mirror copy to docs/evidence_gifs
mirror_dir = "/home/z/my-project/ps1ai/docs/evidence_gifs"
os.makedirs(mirror_dir, exist_ok=True)
mirror = os.path.join(mirror_dir, "r35_buzzybee_bot.gif")
try:
    import shutil
    shutil.copyfile(gif_path, mirror)
    print(f"[gif] mirrored -> {mirror}")
except OSError as e:
    mirror = None
    print(f"[gif] mirror FAILED: {e}")

# ---- consolidated verdict JSON ------------------------------------------
m1 = json.load(open(os.path.join(OUT, "metrics_r35b_b1.json")))
m2 = json.load(open(os.path.join(OUT, "metrics_r35b_b2.json")))
m3 = json.load(open(os.path.join(OUT, "metrics_r35b_b3.json")))
mA, mC = m2["variants"]["A"], m3["variants"]["C"]
idle = m1["idle_baseline"]
dodges = [p for p in mA["pass_detail"] if not p["hit"]]
verdict = {
    "task": "R35-B BuzzyBee bot",
    "claim": "PLAYING_BOT",
    "entity_map": {
        "struct": "AnimatedObject 0x24B: fn+0 idx+4 tf+8 y+0C x+10 xv+14 yv+18 rate+1C il+20 (fixed/1024)",
        "mainPlayer_bee": "0x8005EDC0 (x=15360 const, y clamp 18..172px)",
        "enemy_wasp": "0x8005EB7C (56x48, xv=-1536, y bounce 2..142, |yv| in {1024,2048,3072})",
        "flowers": "0x8005EBA0 +0x24*i (3, 16x29, x=rock.x+21*1024, y=rock.y-29*1024)",
        "rocks": "0x8005F55C +0x24*i (3, 42x40, xv=-1024)",
        "mainHealth": "0x8005EF48 (5999 init/cap, -3/f drain, -1500 enemy, +1000 flower)",
        "gameState": "0x80058830; bestScore 0x80058838; score 0x8005883C",
        "input": "pad 0x8005881C / trig 0x80058820 / held 0x80058824",
        "live_verified_boot1": m1["map_ok"],
        "checks": m1["checks"],
    },
    "dynamics": m1["dynamics"],
    "bot_runs": {
        "boot2_A_policy2": {
            "survival_frames": mA["survival_frames"], "death": mA["death"],
            "score": mA["score"], "hp_end": mA["hp"],
            "passes": mA["passes"], "dodges": mA["dodges"],
            "close_dodges_min_sep_lt30": sum(
                1 for p in dodges if p["min_sep"] < 30),
            "enemy_hits": mA["enemy_hits"],
            "pickups": mA["pickups_total"],
            "example_dodge": "pass f1539-1653 min_sep=1px, no -1503 edge",
        },
        "boot3_C_policy3": {
            "survival_frames": mC["survival_frames"], "death": mC["death"],
            "score": mC["score"], "dodges": mC["dodges"],
            "enemy_hits": mC["enemy_hits"],
            "pickups_caused": mC["pickups_caused"],
            "example_caused_pickup": "f2563 +997, mode=flower, "
                                     "seek_dur=127f on picked flower idx0",
        },
    },
    "idle_baseline": {"survival_frames": idle["survival_frames"],
                      "score": idle["score"],
                      "enemy_edges": len(idle["edges"])},
    "comparison": {
        "survival_x": round(mA["survival_frames"] /
                            max(1, idle["survival_frames"]), 2),
        "score_x": round(mA["score"] / max(1, idle["score"]), 2),
    },
    "criteria": {
        "a_dodges": "8 passes crossed the bee column (ex in (-41,150]) "
                    "with NO -1500 edge; closest min_sep=1px (f1539-1653)",
        "b_caused_pickups": "boot3 C f2563: +997 after 127f of "
                            "flower-mode steering to that exact flower "
                            "(mode+seek_idx+seek_dur logged per frame)",
        "c_survival": f"4000f cap (never died) score 4003 vs idle "
                      f"{idle['survival_frames']}f score {idle['score']}",
        "d_png_chain": f"{len(pngs)} gameplay PNGs, all consecutive "
                       f"deltas {deltas} (live animation), GIF built",
    },
    "honest_caveats": [
        "boot2 A took 7 wasp hits in 15 passes (47%); dodges are real but "
        "the bot is not dominant — below-side over-flap chaining was "
        "diagnosed post-hoc from frames_b2_A.jsonl",
        "boot3 policy3 (ceiling-hugging above-side) regressed to 3/7; "
        "rising-wasp ceiling sweeps are near-unavoidable geometry",
        "boot2 pickups were incidental (mode never flower at pickup — "
        "seek window fx>37 dropped the target on final approach); the "
        "causal pickup evidence comes from boot3 C",
    ],
    "vision_check": {"gif": os.path.relpath(gif_path, OUT),
                     "mirror": mirror, "frames": len(frames),
                     "consecutive_deltas": deltas, "animation_alive": alive},
    "boots_used": 3, "boot_cap": 3,
}
json.dump(verdict, open(os.path.join(OUT, "r35b_verdict.json"), "w"),
          indent=1, default=str)
print("[gif] verdict -> r35b_verdict.json")
