#!/usr/bin/env python3
"""issue5_context_check.py — REAL PLAY vs ATTRACT DEMO discriminator.

Evidence conflict to resolve (inv10, 2026-10-22):
  * boot gate passed with input-ownership contrast (idle churn 32 vs
    RIGHT churn 4672 bytes) — looks like real play;
  * but the run never advanced (no scroll, telemetry score frozen at
    140 while the HUD shows 2700), the scene loops on the village
    helicopter, and PRESS START flashes.

The demo plays Mission 1 with its own scripted inputs, so idle
windows are the discriminator:
  REAL PLAY: idle -> pad mirror 0, RAM churn collapses, no scroll.
  DEMO:      idle -> the script keeps pressing buttons (mirror lights
             bits on its own), the world keeps scrolling (churn stays
             high, frame content keeps shifting horizontally).
Three idle/active windows are measured back-to-back so a scripted
calm stretch cannot fake ownership.
"""
from __future__ import annotations

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from mission import ensure_mission                        # noqa: E402
from issue4_controller import boot                        # noqa: E402


def _log(*a):
    print("[ctxchk]", *a, file=sys.stderr, flush=True)


def window(p, buttons, frames=120):
    """Measure pad mirror, RAM churn, frame churn, score over a window."""
    s0 = p.mem.snapshot()
    m0 = int(p.mem.u16(0x0D4948))
    f0 = p.core.frame_rgb()
    sc0 = int(p.mem.u32(0x0EE318))
    p.core.run(frames, set(buttons) if buttons else None)
    m1 = int(p.mem.u16(0x0D4948))
    ram_churn = int(np.count_nonzero(s0 != p.mem.snapshot()))
    f1 = p.core.frame_rgb()
    fr_diff = float(np.abs(f0.astype(np.int16) -
                           f1.astype(np.int16)).mean()) \
        if (f0 is not None and f1 is not None) else None
    sc1 = int(p.mem.u32(0x0EE318))
    # self-play: mirror bits DURING an idle window we did not cause
    return {"buttons": sorted(buttons), "mirror_start": hex(m0),
            "mirror_end": hex(m1), "ram_churn": ram_churn,
            "frame_diff": fr_diff, "score": (sc0, sc1)}


def main():
    p, fwmode = boot()
    g = ensure_mission(p, tries=3, log=_log, want_hp_cands=False)
    _log("gate:", g.get("in_mission"))
    results = []
    seq = [(set(), "idle-1"), ({"RIGHT"}, "right"),
           (set(), "idle-2"), ({"RIGHT"}, "right-2"),
           (set(), "idle-3")]
    for btns, name in seq:
        r = window(p, btns)
        r["window"] = name
        results.append(r)
        _log(f"{name:8s} mirror {r['mirror_start']}->{r['mirror_end']} "
             f"ram_churn={r['ram_churn']} "
             f"frame_diff={r['frame_diff']} score={r['score']}")
    # verdict: real play iff every idle window shows mirror==0 AND
    # the RIGHT windows produce far more churn than idle windows
    idle_mirror_selfplay = any(
        int(r["mirror_end"], 16) != 0
        for r in results if r["window"].startswith("idle"))
    idle_churns = [r["ram_churn"] for r in results
                   if r["window"].startswith("idle")]
    right_churns = [r["ram_churn"] for r in results
                    if r["window"] == "right"]
    contrast = (min(right_churns) if right_churns else 0) > \
        (max(idle_churns) * 5 + 500)
    verdict = "REAL_PLAY" if (not idle_mirror_selfplay and contrast) \
        else "DEMO_OR_SCRIPTED"
    out = {"schema": "ps1play-context-check/1",
           "firmware_mode": fwmode, "verdict": verdict,
           "idle_selfplay_bits": idle_mirror_selfplay,
           "input_contrast": contrast, "windows": results}
    print(verdict)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
