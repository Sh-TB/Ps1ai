#!/usr/bin/env python3
"""issue4_realplay_validate4.py — final scans: tile-digit bombs + camera.

v3 lessons:
  * the HUD bombs digits are stored as TILE indices ('9' -> 0x59),
    outside the 0x30..0x3B window that was scanned -> accept 0x50..0x59;
  * scans need a NO-PRESS control leg to separate button effects from
    pure timing decrements;
  * camera: sample u32 series over a LONG rightward run from deep0
    instead of the blocked 3-way.
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

from issue4_real_start import (                           # noqa: E402
    boot_to_demo, owns_pad, OUTDIR, SCORE_OFF)

ZONE = 0x1FC000


def _log(*a):
    print("[v4]", *a, file=sys.stderr, flush=True)


def digit_scan(p, with_press=True, presses=2):
    """From fresh deep0 restores: optional grenade presses; find u8
    series 0x50..0x59 dropping -1 per press (tile-encoded ones digit
    of the bombs HUD).  A control leg (with_press=False) must find
    NOTHING for the same protocol."""
    from ps1play.core.inputmap import parse_buttons
    btns = parse_buttons("A") if with_press else set()
    seqs = []
    for k in range(presses):
        p.load_state("deep0")
        p.core.run(6 + 5 * k, set())
        snaps = [p.mem.snapshot()]
        for _ in range(presses - k if with_press else 0):
            p.core.run(10, set())
            p.core.run(30, btns)
            p.core.run(25, set())
            snaps.append(p.mem.snapshot())
        p._advance()
        seqs.append(snaps)
    # normalize: every seq must have presses+1 snapshots; pad by repeat
    found = {}
    for mi, snaps in enumerate(seqs):
        if len(snaps) < 2:
            continue
        a0 = snaps[0][:ZONE].astype(np.int32)
        a1 = snaps[-1][:ZONE].astype(np.int32)
        d = a1 - a0
        n_throw = len(snaps) - 1
        ok = (d == -n_throw) & (a0 >= 0x50) & (a0 <= 0x59)
        for i in np.flatnonzero(ok):
            key = hex(int(i))
            found.setdefault(key, []).append(
                {"seq": mi, "start": int(a0[i]),
                 "after": int(a1[i])})
    return found


def camera_long_run(p, frames=960, step=40):
    p.load_state("deep0")
    words = {}
    for i in range(frames // step):
        p.core.run(step, {"RIGHT"})
        s = p.mem.snapshot()[:ZONE]
        if i == 0:
            base = s
        if i in (1, 3, 6, 9, 11, 14, 17, 20, 23):
            words[i] = s
    p._advance()
    out = {}
    b32 = base.view("<u4").astype(np.int64)
    for i, s in words.items():
        d = s.view("<u4").astype(np.int64) - b32
        idx = np.flatnonzero((d > 2_000_000) & (d < 400_000_000))
        out[i] = [hex(int(x) * 4) for x in idx[:40]]
    # intersect: addresses present in EVERY sampled frame with growing
    sets = None
    for i, lst in out.items():
        st = set(lst)
        sets = st if sets is None else sets & st
    return {"per_frame_counts": {i: len(v) for i, v in out.items()},
            "persistent": sorted(sets or [])[:32]}


def main():
    p = boot_to_demo()
    p.core.run(12, {"START"})
    p.core.run(150, set())
    own = owns_pad(p)
    if not own["owns"]:
        raise SystemExit("no input ownership")
    p.core.run(400, {"RIGHT"})
    p.core.run(15, set())
    p._advance()
    p.save_state("deep0")
    out = {"schema": "ps1play-realplay-validate4/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime())}

    out["press_scan"] = digit_scan(p, with_press=True)
    out["control_scan"] = digit_scan(p, with_press=False)
    press_addrs = set(out["press_scan"])
    ctrl_addrs = set(out["control_scan"])
    out["bombs_digit_addrs"] = sorted(press_addrs - ctrl_addrs)
    _log("press:", {k: v[:2] for k, v in
                    list(out["press_scan"].items())[:8]})
    _log("control:", list(out["control_scan"].items())[:6])
    _log("bombs digits:", out["bombs_digit_addrs"])

    cam = camera_long_run(p)
    out["camera"] = cam
    _log("camera persistent:", cam["persistent"])

    with open(os.path.join(OUTDIR, "realplay_validate4.json"),
              "w") as f:
        json.dump(out, f, indent=1)
    _log("saved realplay_validate4.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
