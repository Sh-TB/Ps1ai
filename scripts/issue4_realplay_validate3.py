#!/usr/bin/env python3
"""issue4_realplay_validate3.py — button-role disambiguation + HUD-digit
scan + deep-anchor camera scan.

Open questions from validate2:
  * does CIRCLE (libretro A) actually throw grenades, or is it
    TRIANGLE (libretro X)?  The HUD bombs value never moved with A.
  * HUD numbers may be stored as ASCII digit bytes ('9'=0x39), so the
    scan accepts 0x30..0x39 values, not only 55..60.
  * the camera never scrolled inside the spawn corridor; scan from a
    DEEP anchor (400f of running) where scrolling is guaranteed.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from PIL import Image                                     # noqa: E402
from issue4_real_start import (                           # noqa: E402
    boot_to_demo, owns_pad, OUTDIR, SCORE_OFF)

ZONE = 0x1FC000
BOUNDS = {1: (60, 255), 2: (60, 4000), 4: (80, 60_000_000)}


def _log(*a):
    print("[v3]", *a, file=sys.stderr, flush=True)


def grenade_scan(p, btn_name, presses=2):
    """From fresh deep0 restores: press the button, scan for u8 series
    dropping -1 per press with start in 0x30..0x3B (ASCII digits or
    small counters) or 50..60 (plain)."""
    from ps1play.core.inputmap import parse_buttons
    btns = parse_buttons(btn_name)
    seqs = []
    for k in range(presses):
        p.load_state("deep0")
        p.core.run(6 + 5 * k, set())
        snaps = [p.mem.snapshot()]
        for _ in range(1):
            p.core.run(10, set())
            p.core.run(30, btns)
            p.core.run(25, set())
            snaps.append(p.mem.snapshot())
        p._advance()
        seqs.append(snaps)
    found = {}
    for mi, snaps in enumerate(seqs):
        a0 = snaps[0][:ZONE].astype(np.int32)
        a1 = snaps[1][:ZONE].astype(np.int32)
        d = a1 - a0
        ok = (d == -1) & (((a0 >= 0x30) & (a0 <= 0x3B)) |
                          ((a0 >= 50) & (a0 <= 60)))
        for i in np.flatnonzero(ok):
            key = hex(int(i))
            found.setdefault(key, []).append(
                {"seq": mi, "start": int(a0[i]), "after": int(a1[i])})
    return found


def deep_three_way(p, frames=480):
    legs = {}
    for name, btns in (("idle", set()), ("right", {"RIGHT"}),
                       ("left", {"LEFT"})):
        p.load_state("deep0")
        s0 = p.mem.snapshot()[:ZONE]
        p.core.run(10, set())
        sA = p.mem.snapshot()[:ZONE]
        p.core.run(frames, btns)
        p._advance()
        legs[name] = (s0, sA, p.mem.snapshot()[:ZONE])
    idle = legs["idle"]
    out = {}
    for width in (2, 4):
        view = {2: "<u2", 4: "<u4"}[width]
        dr = legs["right"][2].view(view).astype(np.int64) - \
            legs["right"][0].view(view).astype(np.int64)
        dl = legs["left"][2].view(view).astype(np.int64) - \
            legs["left"][0].view(view).astype(np.int64)
        di = idle[2].view(view).astype(np.int64) - \
            idle[0].view(view).astype(np.int64)
        diA = idle[1].view(view).astype(np.int64) - \
            idle[0].view(view).astype(np.int64)
        lo, hi = BOUNDS[width]
        cand = np.flatnonzero(
            (dr >= lo) & (dr <= hi) & (dl <= -lo) & (dl >= -hi) &
            (np.abs(di) <= 6) & (np.abs(diA) <= 2) &
            (np.abs(dr + dl) <= np.maximum(60, 0.15 * np.abs(dr))))
        out[f"u{width * 8}"] = sorted(int(c) * width for c in cand)
    _log("deep 3-way:", {k: len(v) for k, v in out.items()})
    return out


def main():
    p = boot_to_demo()
    p.core.run(12, {"START"})
    p.core.run(150, set())
    own = owns_pad(p)
    if not own["owns"]:
        raise SystemExit("no input ownership")
    _log("ownership ok")
    # deep anchor: run right 400f so the camera is definitely scrolling
    p.core.run(400, {"RIGHT"})
    p.core.run(15, set())
    p._advance()
    p.save_state("deep0")
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(OUTDIR, "deep0.png"))
    out = {"schema": "ps1play-realplay-validate3/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime())}

    # ---- button roles: A (Circle) vs X (Triangle) ----
    for btn, label in (("A", "circle"), ("X", "triangle")):
        res = grenade_scan(p, btn)
        out[f"grenade_scan_{label}"] = res
        _log(f"grenade scan {label}: {len(res)} addrs " +
             str(list(res.items())[:6]))

    # ---- camera from deep anchor ----
    tw = deep_three_way(p)
    out["deep_3way"] = {k: [hex(a) for a in v[:24]]
                        for k, v in tw.items()}
    u32c = tw.get("u32", [])
    if u32c:
        series = {}
        p.load_state("deep0")
        for a in u32c[:8]:
            series[hex(a)] = []
        for _ in range(12):
            p.core.run(40, {"RIGHT"})
            for a in u32c[:8]:
                series[hex(a)].append(int(p.mem.u32(a)))
        p._advance()
        out["deep_camera_series"] = series
        for a, s in series.items():
            fx = [v >> 16 for v in s]
            mono = all(b >= x for x, b in zip(fx, fx[1:]))
            _log(f"cand {a}: px={fx[:6]} net={fx[-1] - fx[0]} "
                 f"mono={mono}")

    with open(os.path.join(OUTDIR, "realplay_validate3.json"),
              "w") as f:
        json.dump(out, f, indent=1)
    _log("saved realplay_validate3.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
