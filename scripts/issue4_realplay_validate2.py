#!/usr/bin/env python3
"""issue4_realplay_validate2.py — corrected real-play scans.

v1 lessons:
  * the u32 view bound (<=4000) excluded the 16.16 fixed-point camera
    (real gain ~1.5 px/frame = ~23.6M raw per 240f) -> per-view bounds;
  * the HUD bombs (59) was never value-traced -> strict 59->58->57
    series scan across u8 / u16 / u32 / BCD over two independent
    grenade sequences.
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
BOUNDS = {1: (60, 255), 2: (60, 4000), 4: (80, 60_000_000)}


def _log(*a):
    print("[validate2]", *a, file=sys.stderr, flush=True)


def three_way(p, origin_frames, frames=240):
    legs = {}
    for name, btns in (("idle", set()), ("right", {"RIGHT"}),
                       ("left", {"LEFT"})):
        p.load_state("real0")
        p.core.run(origin_frames, set())
        s0 = p.mem.snapshot()[:ZONE]
        p.core.run(10, set())
        sA = p.mem.snapshot()[:ZONE]
        p.core.run(frames, btns)
        p._advance()
        legs[name] = (s0, sA, p.mem.snapshot()[:ZONE])
    idle = legs["idle"]
    out = {}
    for width in (1, 2, 4):
        view = {1: "<u1", 2: "<u2", 4: "<u4"}[width]
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
    _log(f"origin+{origin_frames}: " +
         " ".join(f"{k}={len(v)}" for k, v in out.items()))
    return out


def camera_series(p, addrs, frames=600, step=40):
    p.load_state("real0")
    series = {hex(a): [] for a in addrs}
    for _ in range(frames // step):
        p.core.run(step, {"RIGHT"})
        for a in addrs:
            series[hex(a)].append(int(p.mem.u32(a)))
    p._advance()
    return series


def bcd(v):
    lo, hi = v & 0xFF, (v >> 8) & 0xFF
    if (lo >> 4) > 9 or (lo & 15) > 9 or (hi >> 4) > 9 or (hi & 15) > 9:
        return None
    return hi * 100 + (lo >> 4) * 10 + (lo & 15)


def bombs_scan(p):
    """Two independent grenade sequences from fresh restores; strict
    -1 per throw, start 55..60, u8/u16/u32/BCD views."""
    seqs = []
    for k in range(2):
        p.load_state("real0")
        p.core.run(6 + 5 * k, set())
        snaps = [p.mem.snapshot()]
        for _ in range(2):
            p.core.run(10, set())
            p.core.run(30, {"A"})
            p.core.run(25, set())
            snaps.append(p.mem.snapshot())
        p._advance()
        seqs.append(snaps)
    results = {}
    for width, view in ((1, None), (2, "<u2"), (4, "<u4")):
        mats = []
        for snaps in seqs:
            if view is None:
                m = np.stack([s[:ZONE].astype(np.int32)
                              for s in snaps])
            else:
                m = np.stack([s[:ZONE].view(view).astype(np.int64)
                              for s in snaps])
            mats.append(m)
        for mi, m in enumerate(mats):
            d1 = m[1] - m[0]
            d2 = m[2] - m[1]
            ok = (d1 == -1) & (d2 == -1) & (m[0] >= 55) & (m[0] <= 60)
            for i in np.flatnonzero(ok):
                key = f"u{width * 8}@{hex(i * width)}"
                results.setdefault(key, []).append(
                    {"seq": mi, "start": int(m[0][i]),
                     "series": [int(x) for x in m[:, i]]})
    # BCD u16: 59 = 0x59 (vectorized validity + value)
    for mi, snaps in enumerate(seqs):
        v0 = snaps[0][:ZONE].view("<u2").astype(np.int64)
        lo = v0 & 0xFF
        hi = (v0 >> 8) & 0xFF
        valid = ((lo >> 4) <= 9) & ((lo & 15) <= 9) & \
                ((hi >> 4) <= 9) & ((hi & 15) <= 9)
        val0 = hi * 100 + (lo >> 4) * 10 + (lo & 15)
        for i in np.flatnonzero(valid & (val0 >= 55) & (val0 <= 60)):
            ok = True
            prev = int(val0[i])
            series = [prev]
            for s in snaps[1:]:
                v = int(s.view("<u2")[i])
                d = bcd(v)
                if d is None or prev - d != 1:
                    ok = False
                    break
                prev = d
                series.append(d)
            if ok:
                key = f"u16bcd@{hex(int(i) * 2)}"
                results.setdefault(key, []).append(
                    {"seq": mi, "start": int(val0[i]),
                     "series": series})
    return results


def main():
    p = boot_to_demo()
    p.core.run(12, {"START"})
    p.core.run(150, set())
    own = owns_pad(p)
    if not own["owns"]:
        raise SystemExit("no input ownership")
    p.core.run(90, {"RIGHT"})
    p.core.run(15, set())
    p._advance()
    p.save_state("real0")
    out = {"schema": "ps1play-realplay-validate2/1",
           "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
           "ownership": own}

    c0 = three_way(p, 0)
    # origin+30 proved fragile in the live opening (enemies interrupt
    # movement legs), so the second experiment is the LONG PLATEAU run
    # + LEFT-boundary check instead of a second origin.
    common = {k: v[:32] for k, v in c0.items() if v}
    out["movement_origin0"] = common
    _log("origin0:", common)
    u32c = common.get("u32", [])
    if u32c:
        out["camera_series"] = camera_series(p, u32c[:6])
        for a, s in out["camera_series"].items():
            fx = [v >> 16 for v in s]
            mono = all(b >= x for x, b in zip(fx, fx[1:]))
            _log(f"camera {a}: px_series={fx[:8]} net={fx[-1]-fx[0]} "
                 f"monotone={mono}")
    out["bombs"] = bombs_scan(p)
    _log("bombs scan:", json.dumps(out["bombs"], indent=1))

    with open(os.path.join(OUTDIR, "realplay_validate2.json"),
              "w") as f:
        json.dump(out, f, indent=1)
    _log("saved realplay_validate2.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
