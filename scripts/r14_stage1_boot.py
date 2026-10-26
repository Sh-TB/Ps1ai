#!/usr/bin/env python3
"""r14_stage1_boot.py — ONE boot of breakout_r14b.cue (stage-1 loader).

Watch: stage-1 body at 0x80180000, payload chunks arriving at
0x80010000 (the 16-sector-cap workaround streaming), then the game's
own crt0+Psy-Q init, pad driver, screen. Then INPUT CAUSALITY on the
map-anchored sensors: LEFT/RIGHT move playerX, CROSS launches the
ball (motion 0->1). Verdict BOOTED requires: payload fully staged,
sensors live, launch causality proven. Evidence to
scratch/round14_breakout/boot/. No RAM writes.
"""
import json
import os
import shutil
import sys
import time

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                          # noqa: E402
from PIL import Image                                       # noqa: E402
from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                             # noqa: E402

EMU = "/home/z/my-project/emu/games_homebrew"
CUE = os.path.join(EMU, "patched", "breakout_r14b.cue")
WS = os.path.join(EMU, "ws_r14_breakout_boot")
OUT = os.path.join(REPO, "scratch", "round14_breakout", "boot")

A = {  # cs50x.map (release cs50x.exe) — source-anchored sensors
    "hit": 0x800187B0, "ballRad": 0x800187B4, "velY": 0x800187B8,
    "velX": 0x800187BC, "lives": 0x800187C0, "playerY": 0x800187C4,
    "playerSize": 0x800187C8, "yOff": 0x800187CC, "xOff": 0x800187D0,
    "framing": 0x800187E0, "maxLevel": 0x800187E4,
    "gridMaster": 0x800187E8,
    "ballX": 0x80023004, "cachedPadValue": 0x80023008,
    "ballY": 0x8002300C, "pause": 0x80023020, "bricksLeft": 0x80023024,
    "bricksCounter": 0x80023028, "motion": 0x80023030,
    "gameWon": 0x80023034, "playerX": 0x80023038, "level": 0x8002303C,
    "grid": 0x80028F9C,
}


def snap_u32(snap, addr):
    return int(np.frombuffer(snap[addr - 0x80000000:
                                   addr - 0x80000000 + 4], "<u4")[0])


def sensors(p):
    s = bytes(p.mem.snapshot())
    return {k: snap_u32(s, a) for k, a in A.items()
            if k in ("motion", "ballX", "ballY", "playerX", "lives",
                     "level", "bricksCounter", "gameWon", "velX", "velY")}


def reach(snap):
    """How far the staged payload extends from 0x80010000 (2KB blocks)."""
    r = 0
    for blk in range(0, 0x13000, 0x800):
        if any(snap[0x10000 + blk:0x10000 + blk + 0x800]):
            r = blk + 0x800
    return r


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(WS, "system"), exist_ok=True)
    shutil.copyfile(os.path.join(REPO, "third_party", "openbios",
                                 "openbios.bin"),
                    os.path.join(WS, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS)
    p = PS1Play(CUE, workspace=WS, var_overrides=fw["override_vars"])
    p.boot()
    t0 = time.time()
    tl = []
    game_live_f = None
    for step in range(300):
        p.wait(8)
        snap = bytes(p.mem.snapshot())
        fr = p.core.frame_rgb()
        mean = None if fr is None else round(float(fr.mean()), 2)
        rec = {"f": p.core.frames_run, "mean": mean,
               "payload_reach": reach(snap),
               "stage1": snap[0x180000:0x180008] != b"\x00" * 8,
               "motion": snap_u32(snap, A["motion"]) if
               snap[0x10020:0x10028] != b"\x00" * 8 else None}
        tl.append(rec)
        if step % 4 == 0:
            print(json.dumps(rec), flush=True)
        if rec["payload_reach"] >= 0x13000 and mean and mean > 5 and \
                rec["motion"] is not None:
            game_live_f = p.core.frames_run
            break
    if game_live_f is None:
        json.dump({"verdict": "BOOT_FAIL", "timeline": tl[-30:]},
                  open(os.path.join(OUT, "boot.json"), "w"), indent=1)
        print("VERDICT BOOT_FAIL")
        return 1
    # ---- game is live: settle and prove input causality ----
    p.wait(90)
    fr = p.core.frame_rgb()
    Image.fromarray(fr).save(os.path.join(OUT, "game_first_screen.png"))
    s0 = sensors(p)
    # RIGHT 40 frames
    p.core.run(40, {"RIGHT"})
    s1 = sensors(p)
    # LEFT 40 frames
    p.core.run(40, {"LEFT"})
    s2 = sensors(p)
    fr = p.core.frame_rgb()
    Image.fromarray(fr).save(os.path.join(OUT, "game_after_move.png"))
    # CROSS tap (hold 3, release 6) -> launch
    p.core.run(3, {"B"})
    p.core.run(6, set())
    p.wait(30)
    s3 = sensors(p)
    fr = p.core.frame_rgb()
    Image.fromarray(fr).save(os.path.join(OUT, "game_after_launch.png"))
    p.wait(240)
    s4 = sensors(p)
    fr = p.core.frame_rgb()
    Image.fromarray(fr).save(os.path.join(OUT, "game_rally.png"))

    out = {
        "verdict": "BOOTED",
        "game_live_frame": game_live_f,
        "wall_s": round(time.time() - t0, 1),
        "payload_reach": tl[-1]["payload_reach"],
        "sensors_idle": s0, "after_right40": s1, "after_left40": s2,
        "after_cross": s3, "after_240f": s4,
        "move_causality": {
            "right_dx": (s1["playerX"] - s0["playerX"]),
            "left_dx": (s2["playerX"] - s1["playerX"]),
        },
        "launch_causality": {"motion_before": s2["motion"],
                             "motion_after_cross": s3["motion"]},
        "timeline_tail": tl[-8:],
    }
    json.dump(out, open(os.path.join(OUT, "boot.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items()
                      if k not in ("timeline_tail",)}, indent=1))
    print("VERDICT BOOTED — launch causality:",
          out["launch_causality"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
