#!/usr/bin/env python3
"""r20-t4 RUN 4 (final, short): finish the 3P retire from r20t4_retire state
(3P at 1 heart after run-3 hit). Charged-throw loop; event = heart-band
collapse; PNG evidence + slot trace. Retire verified by VLM afterwards."""
import json, os, sys, time
import numpy as np
from PIL import Image
sys.path.insert(0, "/home/z/my-project/ps1ai")
from ps1play.api import PS1Play

OUT = "/home/z/my-project/scratch/r20t4_poypoy/run4_finish"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
CORE = "/home/z/my-project/emu/cores/mednafen_psx_libretro.so"
OV = {b"beetle_psx_override_bios": b"openbios"}
SLOTS = [0x9F780, 0x9F7EA, 0x9F7B0, 0x9F778]
HARRY = (1322744, 1322752)
os.makedirs(OUT, exist_ok=True)
R = {"started": time.strftime("%Y-%m-%dT%H:%M:%SZ")}
p = PS1Play(CUE, core=CORE, workspace=WS, var_overrides=OV)
R["boot"] = {k: p.boot().get(k) for k in ("core", "serial")}
p.load_state("r20t4_retire")
p.core.run(10)
Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/resume.png")
R["hearts"] = []; R["events"] = []; R["slot_trace"] = []
hist = []; base = None; B_burst = 0; throw_n = 0
for step in range(2400 // 30):
    btn = "B" if B_burst > 0 else None
    if B_burst > 0:
        B_burst -= 30
        if B_burst == 0: throw_n += 1
    p.core.run(30, btn)
    fc = p.core.frames_run
    g = np.asarray(Image.fromarray(p.core.frame_rgb()).convert("L")
                   .resize((512, 240)), np.float32)
    band = [float((g[78:94, 20+i*120:120+i*120] > 110).mean()) for i in range(4)]
    R["hearts"].append([fc] + [round(b, 3) for b in band])
    R["slot_trace"].append([fc] + [int(p.mem.u16(a)) for a in SLOTS]
                           + [int(p.mem.u16(HARRY[0])), int(p.mem.u16(HARRY[1]))])
    hist.append(band)
    if base is None and len(hist) >= 6:
        base = [max(0.05, float(np.mean([h[i] for h in hist[:6]]))) for i in range(4)]
        R["baseline"] = [round(b, 3) for b in base]
    if fc % 120 < 30:
        Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/f{fc:05d}.png")
    if base:
        for i in range(4):
            if hist[-1][i] < 0.45*base[i] and hist[-2][i] < 0.45*base[i]:
                R["events"].append({"frame": fc, "band": i,
                                    "w": hist[-1][i], "throw_n": throw_n})
                Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/event_f{fc:05d}.png")
                for _ in range(4):
                    p.core.run(30)
                    Image.fromarray(p.core.frame_rgb()).save(
                        f"{OUT}/post_{fc:05d}_{p.core.frames_run:05d}.png")
                base = None; hist = []   # re-learn after event
                break
    if not (B_burst > 0) and step % 5 == 2:
        B_burst = 90
R["throws"] = throw_n; R["n_events"] = len(R["events"])
R["final_frame"] = p.core.frames_run
Image.fromarray(p.core.frame_rgb()).save(f"{OUT}/end.png")
p.save_state("r20t4_end")
R["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
json.dump(R, open(f"{OUT}/run4.json", "w"), indent=1)
print(json.dumps({k: R.get(k) for k in ("boot","baseline","throws","n_events",
      "events","final_frame")}, indent=1)[:2000])
