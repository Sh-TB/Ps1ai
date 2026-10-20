#!/usr/bin/env python3
"""real_b_spam_advance.py — auto-advance the real menu chain with
periodic circle (B) presses, then observe where the game lands.

Empirical button map (OBSERVED):
  Agetec "PRESS 1P OR 2P START" -> START enters the mode menu
  mode menu: UP/DOWN move the pixel-verified highlight; B(circle)
  opens the "OK? YES" dialog; another B confirms YES
  -> SOLDIER SELECT (P1 MARCO highlighted)

B-spam from menu entry should walk: OK? -> YES -> soldier select ->
confirm MARCO -> (difficulty?) -> mission 1. Snapshots every 6 frames,
read-only RAM sampling at the static-RE addresses.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)

from ps1play.api import PS1Play  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
WORKSPACE = "/home/z/my-project/ps1-test/emu"
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_b_spam"
os.makedirs(OUT, exist_ok=True)

SCORE_ADDR = 0x0EE318
POW_ADDR = 0x087A78
MISSION_ADDR = 0x0D4213

END = 11000
SNAP_EVERY = 6


def buttons_at(f):
    if 2450 <= f < 2468:
        return "START"                    # Agetec -> mode menu
    if 2700 <= f <= 9500 and (f - 2700) % 100 < 14:
        return "B"                        # circle spam: confirm chains
    return ""


def small_diff(a, b):
    if a is None or b is None:
        return 999.0
    if a.shape != b.shape:
        b = np.asarray(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def main():
    p = PS1Play(GAME, core=CORE, workspace=WORKSPACE,
                var_overrides={b"beetle_psx_override_bios": b"openbios"},
                verbose=False)
    info = p.boot()
    print("boot:", json.dumps(info, default=str), flush=True)

    snaps = []
    ram = []
    prev = None
    for f in range(1, END + 1):
        p.core.set_buttons(buttons_at(f))
        p.core.run_frame()
        if f % 300 == 0:
            try:
                r = p.core.ram
                rd = lambda a, n=4: int.from_bytes(r[a:a + n], "little")
                ram.append({"frame": f, "score": rd(SCORE_ADDR),
                            "pow": rd(POW_ADDR),
                            "mission": rd(MISSION_ADDR, 1)})
            except Exception as e:                          # noqa: BLE001
                ram.append({"frame": f, "err": str(e)})
        if f % SNAP_EVERY == 0:
            rgb = p.core.frame_rgb()
            if rgb is None:
                continue
            arr = np.asarray(rgb)
            Image.fromarray(arr).save(os.path.join(OUT, f"f{f:05d}.png"))
            d = small_diff(arr, prev)
            snaps.append({"frame": f, "diff": round(d, 2) if d < 998 else None,
                          "mean": round(float(arr.mean()), 1)})
            prev = arr
    runs = []
    cur = None
    for s in snaps:
        same = cur is not None and s["diff"] is not None and s["diff"] < 1.5
        if same:
            cur["end"] = s["frame"]
        else:
            if cur:
                runs.append(cur)
            cur = {"start": s["frame"], "end": s["frame"], "mean": s["mean"]}
    if cur:
        runs.append(cur)
    for r in runs:
        if r["end"] - r["start"] >= 24:
            print(f"  {r['start']:5d}-{r['end']:5d} mean={r['mean']:6.1f}")
    with open(os.path.join(OUT, "runs.json"), "w") as fh:
        json.dump({"snaps": snaps, "runs": runs, "ram": ram}, fh, indent=1)
    print("ram tail:", json.dumps(ram[-3:]))
    print("done")


if __name__ == "__main__":
    main()
