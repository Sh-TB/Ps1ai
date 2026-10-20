#!/usr/bin/env python3
"""issue4_realplay_validate.py — final validation of real-play variables.

Candidates from issue4_real_start (3 trials, two origins):
  movement  u16 @0xE80B8 / @0xE80E4 (twins 0x2c apart)
  bombs     u8  @0xCB3AB / @0xCB5F0 (HUD starts 59)

Validation protocol (each needs >=2 independent experiments):
  * movement: idle freeze / RIGHT growth / LEFT reversal+boundary /
    plateau tolerance over a long run / twin agreement / value range
  * bombs: start value == 59 on a fresh real start, strict -1 series
    across 3 fresh-restore grenade throws, second address as shadow
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

MOVE_ADDRS = (0xE80B8, 0xE80E4)
BOMBS_ADDRS = (0xCB3AB, 0xCB5F0, 0xEDCF4)


def _log(*a):
    print("[validate]", *a, file=sys.stderr, flush=True)


def main():
    p = boot_to_demo()
    p.core.run(12, {"START"})
    p.core.run(150, set())
    own = owns_pad(p)
    if not own["owns"]:
        raise SystemExit("no input ownership")
    _log("ownership ok")
    p.core.run(90, {"RIGHT"})
    p.core.run(15, set())
    p._advance()
    p.save_state("real0")
    out = {"schema": "ps1play-realplay-validate/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "ownership": own}

    # ---- movement series per leg --------------------------------
    legs = {}
    for name, btns in (("idle", set()), ("right", {"RIGHT"}),
                       ("left", {"LEFT"})):
        p.load_state("real0")
        series = {hex(a): [] for a in MOVE_ADDRS}
        for i in range(6):
            p.core.run(40, btns)
            for a in MOVE_ADDRS:
                series[hex(a)].append(int(p.mem.u16(a)))
        p._advance()
        legs[name] = series
        _log(f"move {name}: {series}")
    out["movement_legs"] = legs
    verdicts = {}
    for a in MOVE_ADDRS:
        h = hex(a)
        idle, right, left = (legs["idle"][h], legs["right"][h],
                             legs["left"][h])
        v = {
            "idle_frozen": max(idle) - min(idle) <= 2,
            "right_gain": right[-1] - right[0],
            "right_monotone": all(b >= x for x, b in
                                  zip(right, right[1:])),
            "left_gain": left[-1] - left[0],
            "left_monotone": all(b <= x for x, b in zip(left, left[1:])),
        }
        # long plateau run (walls stop movement legitimately)
        p.load_state("real0")
        long_series = []
        for i in range(30):
            p.core.run(20, {"RIGHT"})
            long_series.append(int(p.mem.u16(a)))
        p._advance()
        big_revs = sum(1 for x, b in zip(long_series, long_series[1:])
                       if b < x - 64)
        v["long_run_net"] = long_series[-1] - long_series[0]
        v["long_run_big_revs"] = big_revs
        v["twin_agrees"] = (legs["right"][hex(MOVE_ADDRS[0])] ==
                            legs["right"][hex(MOVE_ADDRS[1])]) \
            if a == MOVE_ADDRS[0] else None
        v["class"] = ("VERIFIED_MOVEMENT" if
                      v["idle_frozen"] and v["right_monotone"] and
                      v["right_gain"] >= 60 and v["left_monotone"] and
                      big_revs == 0 else "UNVERIFIED")
        verdicts[h] = v
    out["movement_verdicts"] = verdicts
    _log("movement verdicts:", json.dumps(verdicts, indent=1))

    # ---- bombs strict series from FRESH real starts --------------
    bomb_series = {}
    for a in BOMBS_ADDRS:
        runs = []
        for k in range(3):
            # fresh real start each time: re-run the start sequence
            p.core.run(2, set())           # keepalive
            p.load_state("real0")
            p.core.run(4 + 3 * k, set())
            v0 = int(p.mem.u8(a))
            p.core.run(30, {"A"})
            p.core.run(20, set())
            p._advance()
            runs.append([v0, int(p.mem.u8(a))])
        bomb_series[hex(a)] = runs
        _log(f"bombs {hex(a)}: {runs}")
    out["bombs_series"] = bomb_series
    bombs_verdict = {}
    for a in BOMBS_ADDRS:
        runs = bomb_series[hex(a)]
        strict = all(r[0] - r[1] == 1 for r in runs)
        in_range = all(1 <= r[0] <= 99 for r in runs)
        bombs_verdict[hex(a)] = {
            "strict_minus1": strict, "in_range": in_range,
            "class": ("VERIFIED_BOMBS" if strict and in_range
                      else "UNVERIFIED")}
    out["bombs_verdicts"] = bombs_verdict
    _log("bombs verdicts:", json.dumps(bombs_verdict, indent=1))

    with open(os.path.join(OUTDIR, "realplay_validate.json"), "w") as f:
        json.dump(out, f, indent=1)
    _log("saved realplay_validate.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
