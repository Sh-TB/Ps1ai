#!/usr/bin/env python3
"""poypoy_r18_calib.py — Round 18: in-match input causality + entity localization.

Round-17 left a REAL_MATCH checkpoint (r17_match_1200.ckpt: UPx2+B from
STAGE SELECT, census left_vs_right 47,573 / det_none 0). Before a closed-loop
agent can play, we need ground truth for what each button does IN the match
and where the players live in RAM — measured, not assumed.

Protocol (tetrade/flappy playbook, applied mid-match):
  restore ckpt -> settle -> base rerun control
  per button: fresh restore -> settle -> hold/tap -> whole-RAM diff + PNG
Direction candidates: i16 slots whose value moves LEFT<BASE<RIGHT (x-axis) or
UP<BASE<DOWN (y-axis) — the movement signature. Button probes record raw
diff sizes + PNG evidence for manual reading (grab vs throw vs jump).

Honest output: JSON with candidate addresses; no claims about gameplay yet.
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

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_r18_calib"
CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/home/z/my-project/emu/games_psx/ws_poypoy_menu22"
MATCH = os.path.join(WS, "r18_match.ckpt")
RAMSZ = 2 * 1024 * 1024


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def i16(a, off):
    return int(np.frombuffer(a[off:off + 2].tobytes(), dtype="<i2")[0]) if off + 2 <= len(a) else 0


def restore_settle(p):
    p.load_state(MATCH)
    p.core.run(150, set())
    return ram(p)


def diff_bytes(a, b):
    return np.flatnonzero(a[:RAMSZ] != b[:RAMSZ])


def direction_candidates(base, held_l, held_r, held_u, held_d):
    """i16 slots moving left<base<right (x) or up<base<down (y)."""
    out = {"x": [], "y": []}
    db = diff_bytes(base, held_l)
    if len(db) == 0:
        return out
    cand = np.unique(db - (db % 2))          # align to even offsets
    for off in cand[:200000]:
        v0, vl, vr = i16(base, off), i16(held_l, off), i16(held_r, off)
        if vl < v0 < vr and vr - vl > 8:
            out["x"].append((int(off), vl, v0, vr))
        v0, vu, vd = i16(base, off), i16(held_u, off), i16(held_d, off)
        if vu < v0 < vd and vd - vu > 8:
            out["y"].append((int(off), vu, v0, vd))
    out["x"].sort(key=lambda t: -(t[3] - t[1]))
    out["y"].sort(key=lambda t: -(t[3] - t[1]))
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime()),
           "match_ckpt": MATCH}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    base = restore_settle(p)
    snap(p, "cal_base.png")
    out["base_frame"] = "cal_base.png"

    # ---- direction holds (45f each after a 30f idle ramp) ----
    holds = {}
    for name, btn in (("left", {"LEFT"}), ("right", {"RIGHT"}),
                      ("up", {"UP"}), ("down", {"DOWN"})):
        p.load_state(MATCH)
        p.core.run(30, set())
        p.core.run(45, btn)
        holds[name] = ram(p)
        snap(p, f"cal_{name}.png")
    p.load_state(MATCH)
    p.core.run(75, set())
    ctrl = ram(p)
    out["control_vs_base"] = int((ctrl[:RAMSZ] != base[:RAMSZ]).sum())
    for n in holds:
        out[f"diff_{n}"] = int((holds[n][:RAMSZ] != base[:RAMSZ]).sum())

    out["candidates"] = direction_candidates(base, holds["left"], holds["right"],
                                             holds["up"], holds["down"])
    out["n_x_cand"] = len(out["candidates"]["x"])
    out["n_y_cand"] = len(out["candidates"]["y"])

    # ---- button taps (each from fresh restore) ----
    probes = {}
    for name, btn, hold in (("cross", {"B"}, 10), ("circle", {"A"}, 10),
                            ("square", {"X"}, 10), ("start", {"START"}, 10)):
        p.load_state(MATCH)
        p.core.run(30, set())
        p.core.run(hold, btn)
        p.core.run(90, set())
        st = ram(p)
        snap(p, f"cal_tap_{name}.png")
        probes[name] = int((st[:RAMSZ] != base[:RAMSZ]).sum())
    out["tap_diffs"] = probes

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "r18_calib.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: out[k] for k in
                      ("control_vs_base", "diff_left", "diff_right", "diff_up",
                       "diff_down", "n_x_cand", "n_y_cand", "tap_diffs")},
                     indent=1))
    print("top x:", out["candidates"]["x"][:12])
    print("top y:", out["candidates"]["y"][:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
