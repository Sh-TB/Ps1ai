#!/usr/bin/env python3
"""real_menu_mission1_probe.py — from the real main menu into Mission 1.

Continues the observed chain:
  disc boot (OpenBIOS override) -> game title "NOW LOADING!" -> main
  menu (ARCADE MISSION / COMBAT SCHOOL / TIME ATTACK / OPTION) after
  START taps (real_title_advance_probe).

This probe drives: menu -> ARCADE MISSION -> difficulty select ->
(default) -> mission 1 start, snapshotting every 60 frames and sampling
static-RE-known RAM signals (read-only). Inputs only — no RAM writes,
no cheats, no state editing.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)

from ps1play.api import PS1Play  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
WORKSPACE = "/home/z/my-project/ps1-test/emu"
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_mission1_start"
os.makedirs(OUT, exist_ok=True)

# static RE (docs/source_of_truth.md): read-only observation only
SCORE_ADDR = 0x0EE318
POW_ADDR = 0x087A78
MISSION_ADDR = 0x0D4213

SCRIPT = [
    # (start_frame, end_frame, buttons, note)
    (0,     1200, None,     "BIOS cube + game boot"),
    (1200,  2400, "START",  "tap START 12/150 until main menu"),
    (2400,  2800, "START",  "select ARCADE MISSION"),
    (2800,  3200, "START",  "accept difficulty"),
    (3200,  5400, None,     "observe mission 1 intro / gameplay"),
]
SNAP_EVERY = 60


def diff_metric(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        b = np.asarray(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def held(f):
    """Return button spec held at frame f according to SCRIPT (taps:
    hold 12 frames out of every 150 during tap windows)."""
    for s, e, btn, _ in SCRIPT:
        if s <= f < e:
            if btn is None:
                return ""
            return btn if (f - s) % 150 < 12 else ""
    return ""


def main():
    p = PS1Play(GAME, core=CORE, workspace=WORKSPACE,
                var_overrides={b"beetle_psx_override_bios": b"openbios"},
                verbose=False)
    info = p.boot()
    print("boot:", json.dumps(info, default=str))

    prev = None
    timeline = []
    ram_samples = []
    t0 = time.time()
    for f in range(1, 5400 + 1):
        p.core.set_buttons(held(f))
        p.core.run_frame()
        if f % 300 == 0 and p.mem is not None:
            try:
                ram = p.core.ram
                def rd(addr, n=4):
                    return int.from_bytes(ram[addr:addr + n], "little")
                ram_samples.append({
                    "frame": f,
                    "score@0x0EE318": rd(SCORE_ADDR),
                    "pow@0x087A78": rd(POW_ADDR),
                    "mission@0x0D4213": rd(MISSION_ADDR, 1),
                })
            except Exception as e:                          # noqa: BLE001
                ram_samples.append({"frame": f, "err": str(e)})
        if f % SNAP_EVERY == 0:
            rgb = p.core.frame_rgb()
            if rgb is not None:
                arr = np.asarray(rgb)
                Image.fromarray(arr).save(
                    os.path.join(OUT, f"f{f:05d}.png"))
                m = diff_metric(arr, prev)
                timeline.append({"frame": f, "diff": m,
                                 "shape": list(arr.shape)})
                prev = arr
    elapsed = time.time() - t0

    events = [t for t in timeline if t["diff"] is not None and t["diff"] > 3.0]
    report = {"elapsed_s": round(elapsed, 1), "big_changes": events,
              "ram_samples": ram_samples, "timeline": timeline}
    with open(os.path.join(OUT, "report.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    print("big_changes:", [(e["frame"], round(e["diff"], 1)) for e in events])
    print("ram:", json.dumps(ram_samples[-6:], indent=1))
    print("report:", os.path.join(OUT, "report.json"))


if __name__ == "__main__":
    main()
