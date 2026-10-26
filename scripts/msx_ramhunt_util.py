#!/usr/bin/env python3
"""msx_ramhunt_util.py — Issue #5 session 10 / Issue #6 round 7: shared
RAM flip-tracking kit for the M2->M3 gate probes (task 17-a).

The recorded next lever (session 9) was the ATTRACT-FLAG RAM HUNT around
the post-crash NOW LOADING window: diff consecutive RAM snapshots and
rank bytes that flip exactly at the attract-hijack onset and stay
flipped.  This module provides:

  FlipTracker  per-byte change bookkeeping over a snapshot sequence
               (first_change frame, last_change frame, change count,
               value at phase start, value at phase end) — O(changes)
               per sample over the live 2 MB RAM numpy view.

  K            known-address observation vocabulary (sessions 3-9):
               px, php, score, gren, flags u32, section state/flags,
               walker progress + frame visual-churn (madiff).

  helpers      png, jsonl J(), boot_guard, sampling-gap schedules.

Nothing here writes RAM (observe-only); the force-test script uses the
GameShark engine for its pokes and records every write.
"""
import json
import os
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"

# ---- the known telemetry vocabulary (all VERIFIED in sessions 3-9) ----
A_FLAGS = 0x0EE518     # u32: 0xFF active play, 0x1 menu/game-over,
                       #      0x0 transient during loading (evidence.jsonl)
A_SCORE = 0x0EE318     # u32 per-life score
A_GREN = 0x0EDCF4      # u8  grenade inventory (VERIFIED series 10,9,8..)
A_PX = 0x0CA2E0        # u32 16.16 player screen-x
A_PHP = 0x0CA2F6       # u16 player HP
A_SEC_ST = 0x0EB5F4    # u16 section/state id
A_SEC_FL = 0x0EB5D0    # u16 section flags
A_PROG = 0x0EB5D4      # u16 walker progress accumulator

KNOWN = (("flags32", A_FLAGS, "u32"), ("score", A_SCORE, "u32"),
         ("gren", A_GREN, "u8"), ("px", A_PX, "u32"),
         ("php", A_PHP, "u16"), ("sec_st", A_SEC_ST, "u16"),
         ("sec_fl", A_SEC_FL, "u16"), ("prog", A_PROG, "u16"))


def read_known(m):
    """One known-vocabulary observation + visual churn vs caller's prev
    frame.  Returns (rec, rgb) — rgb for the caller's next madiff."""
    rec = {}
    for name, addr, kind in KNOWN:
        rec[name] = getattr(m, kind)(addr)
    return rec


def madiff(rgb_prev, rgb_now):
    """Mean absolute per-pixel frame difference (playloop's static
    detector vocabulary).  None-safe."""
    if rgb_prev is None or rgb_now is None:
        return None
    return round(float(np.abs(rgb_prev.astype(np.int16)
                              - rgb_now.astype(np.int16)).mean()), 3)


class FlipTracker:
    """Per-byte change bookkeeping over a sequence of RAM snapshots.

    step(f, ram): diff against the previous snapshot, update first/last
    change frame + count.  val0 stays the PHASE-START value; final is
    the latest snapshot.  save() writes everything for the offline
    ranker (msx_m2_candidates.py).
    """

    def __init__(self, ram):
        self.n = len(ram)
        self.prev = ram.copy()
        self.val0 = ram.copy()
        self.first_f = np.full(self.n, -1, dtype=np.int32)
        self.last_f = np.full(self.n, -1, dtype=np.int32)
        self.count = np.zeros(self.n, dtype=np.int32)

    def step(self, f, ram):
        ch = np.flatnonzero(self.prev != ram)
        if ch.size:
            self.count[ch] += 1
            new = self.first_f[ch] < 0
            self.first_f[ch[new]] = f
            self.last_f[ch] = f
        self.prev = ram.copy()

    def save(self, path, meta):
        np.savez_compressed(path, val0=self.val0, first_f=self.first_f,
                            last_f=self.last_f, count=self.count,
                            final=self.prev,
                            meta=np.array(json.dumps(meta, default=str)))
        return {"path": path, "bytes": int(self.n),
                "changed_total": int((self.count > 0).sum())}


def sampling_gap(f, base=30, dense_spans=(), dense_until=-1, dense_gap=3):
    """Frames to run before the next sample.  Dense (2-5f) inside the
    declared spans and until dense_until (adaptive onset window)."""
    for lo, hi in dense_spans:
        if lo <= f < hi:
            return dense_gap
    if 0 <= dense_until >= 0 and f < dense_until:
        return dense_gap
    return base


def png(p, name, tag, evid=None):
    evid = evid or "/home/z/my-project/ps1ai/scratch/issue6_round7_msx"
    try:
        rgb = p.core.frame_rgb()
        if rgb is not None:
            from PIL import Image
            Image.fromarray(rgb).save(os.path.join(evid, f"{tag}_{name}.png"))
    except Exception as e:                                  # noqa: BLE001
        print("[hunt] png failed:", repr(e)[:120], flush=True)


def jlog(jf, ev):
    jf.write(json.dumps(ev, default=str) + "\n")
    jf.flush()


def wall_out(t0, limit_s):
    return (time.time() - t0) > limit_s
