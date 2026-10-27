#!/usr/bin/env python3
"""poypoy_r18_calib2.py — Round 18: tap-based same-schedule entity localization.

calib v1 failed for a measured reason: hold-probes with different frame
schedules diverge (control_vs_base 51,231 — the match is dynamic: 3 AI
players, timer, camera). v2 uses the tetrade single-tap protocol with an
EXACT same-schedule control:

    restore ckpt -> 30f idle -> [2f tap | 2f idle] -> 35f settle -> snap

  ctrl  = restore, 30f, 2f idle, 35f          (identical timeline)
  tapX  = restore, 30f, 2f X-btn, 35f
Any byte differing between ctrl and a rerun-of-ctrl is ambient churn; a
byte differing between tapLEFT and ctrl is causally downstream of LEFT.
x-candidate: i16 slot with dL<0<dR and |dL|,|dR| small (a few frames of
walk speed ~ 1-3 px/frame * subpixels). y likewise with UP/DOWN.

Outputs: JSON with per-slot deltas; PNGs per probe. No gameplay claims.
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


def run_probe(p, tap):
    p.load_state(MATCH)
    p.core.run(30, set())
    p.core.run(2, tap)
    p.core.run(35, set())
    return ram(p)


def i16(a, off):
    return int(np.frombuffer(a[off:off + 2].tobytes(), dtype="<i2")[0])


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime()),
           "protocol": "restore->30 idle->2 tap->35 settle (same schedule all runs)"}

    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    ctrl = run_probe(p, set())
    snap(p, "c2_ctrl.png")
    ctrl2 = run_probe(p, set())          # ambient churn reference
    out["ambient_ctrl_vs_ctrl2"] = int((ctrl[:RAMSZ] != ctrl2[:RAMSZ]).sum())

    taps = {}
    for name, btn in (("left", {"LEFT"}), ("right", {"RIGHT"}),
                      ("up", {"UP"}), ("down", {"DOWN"})):
        taps[name] = run_probe(p, btn)
        snap(p, f"c2_{name}.png")

    out["diffs"] = {n: int((taps[n][:RAMSZ] != ctrl[:RAMSZ]).sum())
                    for n in taps}

    # candidate scan on bytes changed by taps but NOT by ambient churn
    amb = (ctrl[:RAMSZ] != ctrl2[:RAMSZ])
    dL = (taps["left"][:RAMSZ] != ctrl[:RAMSZ]) & ~amb
    dR = (taps["right"][:RAMSZ] != ctrl[:RAMSZ]) & ~amb
    dU = (taps["up"][:RAMSZ] != ctrl[:RAMSZ]) & ~amb
    dD = (taps["down"][:RAMSZ] != ctrl[:RAMSZ]) & ~amb
    out["tap_only_bytes"] = {k: int(v.sum()) for k, v in
                             (("L", dL), ("R", dR), ("U", dU), ("D", dD))}

    xs, ys = [], []
    for off in np.flatnonzero(dL | dR):
        off = int(off - (off % 2))
        vC, vL, vR = i16(ctrl, off), i16(taps["left"], off), i16(taps["right"], off)
        d, dl, dr = vC, vL - vC, vR - vC
        if dl < 0 < dr and -4096 < dl < 0 and 0 < dr < 4096:
            xs.append((off, dl, dr))
    for off in np.flatnonzero(dU | dD):
        off = int(off - (off % 2))
        vC, vU, vD = i16(ctrl, off), i16(taps["up"], off), i16(taps["down"], off)
        du, dd = vU - vC, vD - vC
        if du < 0 < dd and -4096 < du < 0 and 0 < dd < 4096:
            ys.append((off, du, dd))
    xs.sort(key=lambda t: abs(t[1]) + abs(t[2]))
    ys.sort(key=lambda t: abs(t[1]) + abs(t[2]))
    out["x_cands"] = xs[:40]
    out["y_cands"] = ys[:40]

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "r18_calib2.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: out[k] for k in
                      ("ambient_ctrl_vs_ctrl2", "diffs", "tap_only_bytes")},
                     indent=1))
    print("x:", xs[:16])
    print("y:", ys[:16])
    return 0


if __name__ == "__main__":
    sys.exit(main())
