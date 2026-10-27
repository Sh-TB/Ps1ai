#!/usr/bin/env python3
"""poypoy_r18_calib3.py — Round 18: strong holds + i32 scan + vision anchor.

calib2 established: emulation is deterministic (ambient 0), 2f taps move
i16 slots by only ±1-2 (fixed-point subpixels; pixel part likely the high
half of an i32). v3:
  - same-schedule protocol: restore -> 30 idle -> [hold 30 | idle 30] -> snap
  - scan BOTH i16 and i32 deltas for LEFT/RIGHT (x) and UP/DOWN (y)
  - vision anchor: blue-suit centroid (HARRY) per probe frame
  - button taps B/A/X (cross/circle/square) with 60f settle, PNG + diff
No gameplay claims — measured candidates only.
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


def run_hold(p, hold):
    p.load_state(MATCH)
    p.core.run(30, set())
    p.core.run(30, hold)
    return ram(p)


def i16(a, off):
    return int(np.frombuffer(a[off:off + 2].tobytes(), dtype="<i2")[0])


def i32(a, off):
    return int(np.frombuffer(a[off:off + 4].tobytes(), dtype="<i4")[0])


def blue_centroid(png):
    a = np.asarray(png, dtype=np.int16)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    m = (b > 120) & (b > r + 40) & (b > g + 30) & (r < 110)
    ys, xs = np.nonzero(m)
    if len(xs) < 20:
        return None, int(m.sum())
    return (float(xs.mean()), float(ys.mean())), int(m.sum())


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime())}

    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    idle = run_hold(p, set())
    img = snap(p, "c3_idle.png")
    out["idle_blue"] = blue_centroid(img)

    holds = {}
    for name, btn in (("left", {"LEFT"}), ("right", {"RIGHT"}),
                      ("up", {"UP"}), ("down", {"DOWN"})):
        holds[name] = run_hold(p, btn)
        img = snap(p, f"c3_{name}.png")
        out[f"blue_{name}"] = blue_centroid(img)
        out[f"bytes_{name}"] = int((holds[name][:RAMSZ] != idle[:RAMSZ]).sum())

    # x-candidates via i32 on even offsets and i16 scan
    dL = (holds["left"][:RAMSZ] != idle[:RAMSZ])
    dR = (holds["right"][:RAMSZ] != idle[:RAMSZ])
    both = dL & dR
    xs32, xs16 = [], []
    for off in np.flatnonzero(both):
        o4 = int(off - (off % 4))
        d32l = i32(holds["left"], o4) - i32(idle, o4)
        d32r = i32(holds["right"], o4) - i32(idle, o4)
        if d32l < 0 < d32r and -200000 < d32l and d32r < 200000:
            xs32.append((o4, d32l, d32r))
        o2 = int(off - (off % 2))
        d16l = i16(holds["left"], o2) - i16(idle, o2)
        d16r = i16(holds["right"], o2) - i16(idle, o2)
        if d16l < 0 < d16r and -5000 < d16l and d16r < 5000 and abs(d16l) + abs(d16r) > 6:
            xs16.append((o2, d16l, d16r))
    xs32.sort(key=lambda t: abs(t[1]) + abs(t[2]))
    xs16.sort(key=lambda t: abs(t[1]) + abs(t[2]))

    dU = (holds["up"][:RAMSZ] != idle[:RAMSZ])
    dD = (holds["down"][:RAMSZ] != idle[:RAMSZ])
    bothY = dU & dD
    ys32, ys16 = [], []
    for off in np.flatnonzero(bothY):
        o4 = int(off - (off % 4))
        d32u = i32(holds["up"], o4) - i32(idle, o4)
        d32d = i32(holds["down"], o4) - i32(idle, o4)
        if d32u < 0 < d32d and -200000 < d32u and d32d < 200000:
            ys32.append((o4, d32u, d32d))
        o2 = int(off - (off % 2))
        d16u = i16(holds["up"], o2) - i16(idle, o2)
        d16d = i16(holds["down"], o2) - i16(idle, o2)
        if d16u < 0 < d16d and -5000 < d16u and d16d < 5000 and abs(d16u) + abs(d16d) > 6:
            ys16.append((o2, d16u, d16d))
    ys32.sort(key=lambda t: abs(t[1]) + abs(t[2]))
    ys16.sort(key=lambda t: abs(t[1]) + abs(t[2]))

    out["x32"] = xs32[:30]
    out["x16"] = xs16[:20]
    out["y32"] = ys32[:30]
    out["y16"] = ys16[:20]

    # button taps with same schedule (2f tap, 60f settle)
    taps = {}
    for name, btn in (("cross", {"B"}), ("circle", {"A"}), ("square", {"X"})):
        p.load_state(MATCH)
        p.core.run(30, set())
        p.core.run(2, btn)
        p.core.run(60, set())
        st = ram(p)
        img = snap(p, f"c3_tap_{name}.png")
        taps[name] = int((st[:RAMSZ] != idle[:RAMSZ]).sum())
        out[f"blue_tap_{name}"] = blue_centroid(img)
    out["tap_bytes"] = taps

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "r18_calib3.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: out[k] for k in
                      ("idle_blue", "blue_left", "blue_right", "blue_up",
                       "blue_down", "bytes_left", "bytes_right", "tap_bytes")},
                     indent=1))
    print("x32:", xs32[:12])
    print("y32:", ys32[:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
