#!/usr/bin/env python3
"""msx_vertical_probe.py — Issue #9 §9-B: vertical targeting experiment.

Question: does the agent's UP+Y aimed fire actually connect with an
elevated target (the chopper)? Prior evidence is contradictory: Y fire
did NOT change the armored truck (h=64, ground contact — Y-immune
armor), but the chopper (h >> 64) has never been a verified target.

Design (from chopper_ckpt): when any entity slot shows an AIRBORNE
signature (h >= 200 — far above ground contact 64) within ±150 px, hold
UP+Y for a bounded 3-chunk burst and record that slot's hp across the
burst. Verified hit signal = hp decrease of the SAME slot (score is
per-life, hp is the entity word) — the mission's hit-evidence rule.
Control: the same fire pattern with no airborne slot (no-target arm)
must NOT produce phantom hits.
"""
from __future__ import annotations

import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.agent.combat import scan_entities            # noqa: E402
from msx_helicopter_ladder import (                       # noqa: E402
    CKPT, EVID, A_FLAGS, A_PAIR0, flags_of, log, png, px_of)
from issue4_controller import boot                        # noqa: E402

AIR_H = 200          # airborne class (chopper/canon >> ground contact 64)
AIR_DX = 150.0
BURST_CHUNKS = 3


def run(mode, chunks, tag):
    p, fwmode = boot()
    m = p.mem
    p.load_state(CKPT)
    for _ in range(2):
        p.core.run_frame()
    out_dir = os.path.join(EVID, tag)
    os.makedirs(out_dir, exist_ok=True)
    f0 = p.core.frames_run
    t0 = time.time()
    hp0 = int(m.u16(A_PAIR0))
    target_hp_track = {}
    fired_chunks = 0
    last_px = None
    for c in range(chunks):
        px = px_of(m)
        hp = int(m.u16(A_PAIR0))
        if flags_of(m) != 0xFF or hp <= 0:
            log(f"  [{mode}] died/halted c{c} px {px:.1f}")
            png(p, os.path.join(out_dir, f"end_c{c}.png"))
            break
        scan = scan_entities(m, px=px)
        air = [e for e in scan if e["h"] >= AIR_H and abs(e["dx_px"]) <= AIR_DX]
        advanced = 0.0 if last_px is None else (px - last_px)
        last_px = px
        for e in air:
            target_hp_track.setdefault(e["slot"], []).append(
                {"chunk": c, "hp": e["hp"], "h": e["h"],
                 "dx": round(e["dx_px"], 1)})

        if mode == "upfire" and air:
            # hold UP+Y (aim up + fire) — 3-chunk bounded burst
            fired_chunks += 1
            for s in (["UP", "Y"], ["UP", "Y"], ["UP", "Y"], []):
                p.core.run(15, set(s))
        elif mode == "upfire":
            p.core.run(60, set())                    # no target: idle
        else:
            p.core.run(60, set())                    # control: pure idle
    # final census
    result = {"mode": mode, "chunks": chunks, "fired_chunks": fired_chunks,
              "frames_used": p.core.frames_run - f0,
              "wall_s": round(time.time() - t0, 1),
              "hp_delta": int(m.u16(A_PAIR0)) - hp0,
              "air_targets": {str(k): v for k, v in target_hp_track.items()}}
    import json
    with open(os.path.join(out_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=1)
    log(f"[{mode}] done fired={fired_chunks} targets="
        f"{ {k: (v[0]['hp'], v[-1]['hp']) for k, v in target_hp_track.items()} }")
    return result


def main():
    log("== §9-B vertical targeting: upfire arm ==")
    r1 = run("upfire", 40, "vertical_upfire")
    log("== §9-B vertical targeting: idle control arm ==")
    r2 = run("idle", 40, "vertical_idle")
    # verdict: any SAME-slot hp decrease across the burst = verified hit
    hits = {}
    for slot, tl in r1["air_targets"].items():
        drops = [tl[i + 1]["hp"] - tl[i]["hp"] for i in range(len(tl) - 1)
                 if tl[i + 1]["hp"] < tl[i]["hp"]]
        if drops:
            hits[slot] = drops
    log("VERDICT hits:", hits if hits else
        "no same-slot hp decrease observed under UP+Y fire")
    log("control air targets:", {k: (v[0]['hp'], v[-1]['hp'])
                                 for k, v in r2["air_targets"].items()})


if __name__ == "__main__":
    main()
