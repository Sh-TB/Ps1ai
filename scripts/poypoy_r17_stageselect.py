#!/usr/bin/env python3
"""poypoy_r17_stageselect.py — Round 17: enter a REAL match via STAGE SELECT.

r17_realmatch finding: START-exit from practice aborts to the boot logo, so
the real match must be entered at the STAGE SELECT screen (menu23's m23_b0:
3 arena thumbnails + red PRACTICE label; our B-confirm picked PRACTICE).

Phase A (cursor map): from m23_b0.ckpt, UP/UP/UP/DOWN/DOWN strip, PNG each
  rung -> identifies how the cursor cycles.
Phase B (confirm): reload m23_b0, UP x2 (colosseum candidate), B-confirm,
  long observation ladder, direction census -> REAL_MATCH iff directions
  register and the frame leaves the menus. Checkpoints saved per rung.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_r17_stageselect"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/tmp/my-project/emu/games_psx/ws_poypoy_menu22"
B0 = "/tmp/my-project/emu/games_psx/ws_poypoy_menu22/m23_b0.ckpt"  # STAGE SELECT


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def census(p, ckpt):
    snaps = {}
    for name, btns in (("none", set()), ("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(ckpt)
        p.core.run(120, set())
        p.core.run(90, btns)
        snaps[name] = ram(p)
    p.load_state(ckpt)
    p.core.run(120, set())
    p.core.run(90, set())
    n2 = ram(p)
    det = int((n2 != snaps["none"]).sum())
    out = {
        "det_none": det,
        "left_vs_right": int((snaps["left"] != snaps["right"]).sum()),
        "left_vs_none": int((snaps["left"] != n2).sum()),
    }
    out["verdict"] = ("REAL_MATCH" if out["left_vs_right"] > max(500, 5 * out["det_none"])
                      else "not_yet")
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # ---- Phase A: cursor map from STAGE SELECT ----
    p.load_state(B0)
    p.core.run(120, set())
    snap(p, "ss_restore.png")
    strip = []
    for i, (lbl, btn) in enumerate([("up1", {"UP"}), ("up2", {"UP"}),
                                    ("up3", {"UP"}), ("down1", {"DOWN"}),
                                    ("down2", {"DOWN"})]):
        p.core.run(20, set())
        p.core.run(30, btn)
        p.core.run(150, set())
        snap(p, f"ss_{lbl}.png")
        ck = os.path.join(WS, f"r17_ss_{lbl}.ckpt")
        p.save_state(ck)
        strip.append(lbl)
    out["strip"] = strip

    # ---- Phase B: confirm after UP x2 (colosseum candidate) ----
    p.load_state(B0)
    p.core.run(120, set())
    for _ in range(2):
        p.core.run(20, set())
        p.core.run(30, {"UP"})
        p.core.run(120, set())
    snap(p, "ss_before_confirm.png")
    p.core.run(60, {"B"})
    p.core.run(1200, set())            # match intro / loading
    snap(p, "match_1200.png")
    ck_m1 = os.path.join(WS, "r17_match_1200.ckpt")
    p.save_state(ck_m1)

    p.core.run(1200, set())
    snap(p, "match_2400.png")
    ck_m2 = os.path.join(WS, "r17_match_2400.ckpt")
    p.save_state(ck_m2)

    p.core.run(2400, set())
    snap(p, "match_4800.png")
    ck_m3 = os.path.join(WS, "r17_match_4800.ckpt")
    p.save_state(ck_m3)

    out["census_m1"] = census(p, ck_m1)
    out["census_m2"] = census(p, ck_m2)
    out["census_m3"] = census(p, ck_m3)

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "r17_stageselect.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: out[k] for k in ("census_m1", "census_m2", "census_m3")},
                     indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
