#!/usr/bin/env python3
"""probe0_addresses.py — Instrument 0 for the combat-policy work
(user gameplay feedback, Issue #5 focused follow-up session 3).

GOAL (verify-before-use, RAM-first):
  From the mission-start savestate, determine the GROUND TRUTH of:
    P1  which word is the PLAYER world X (walks at 4..60 u/10f while
        RIGHT held, keeps growing past the camera at a section clamp)
    P2  which word is the CAMERA scroll (follows the player, clamps
        earlier at section ends)
    P3  enemy geometry: which entity-table slots light up with live
        enemies, in front AND behind, while walking / standing / walking
        back — the raw material for the facing/rear-engage policy.
    P4  what is BEHIND the player at mission start (spawn geometry).

Protocol (all READ-ONLY; no RAM writes, no cheats):
  A  resume issue5_m1_start, verify active play (flags 0xFF / hp>0)
  B  400f walk RIGHT  (sample every 10f: camera u32 @0xCA2E0, all 40
     slots' X u32 @+0x78 + HP u16 @+0x8E, score, hp_pair)
  C  150f stand still  (who still moves? -> live enemies)
  D  150f walk LEFT    (rear ground truth: what does turning back see)
  E  dump JSON + PNGs; print the mover/enemy table verdict.

Output: $EVID/probe0/probe0_addresses.json (+ PNGs).
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                          # noqa: E402
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from mission import ensure_mission                     # noqa: E402
from issue4_controller import boot                     # noqa: E402

EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "probe0")
TABLE = 0x0CA268
STRIDE = 0x14C
SLOTS = 40
CAMERA = 0x0CA2E0          # == TABLE+0x78 (slot0 X) — verify behaviour
HP_PAIR = (0xCA2F6, 0xCA2FE)
FLAGS = 0x0EE518
N_SLOTS_X = range(SLOTS)


def _log(*a):
    print("[probe0]", *a, file=sys.stderr, flush=True)


def snap_row(p, tel):
    m = p.mem
    row = {
        "frame": p.core.frames_run,
        "camera_px": int(m.u32(CAMERA)) / 65536.0,
        "score": tel.snapshot(buttons=[], frame=p.core.frames_run)["score"],
        "hp_pair": [int(m.u16(HP_PAIR[0])), int(m.u16(HP_PAIR[1]))],
        "flags": hex(int(m.u32(FLAGS))),
        "slots": {},
    }
    for s in N_SLOTS_X:
        base = TABLE + s * STRIDE
        xw = int(m.u32(base + 0x78))
        hp = int(m.u16(base + 0x8E))
        if xw or hp:
            row["slots"][s] = {"x_px": xw / 65536.0, "hp": hp}
    return row


def classify(rows):
    """P1/P2/P3 verdicts from the sampled series."""
    verdict = {"movers": {}, "camera_note": None, "player_note": None}
    # per-phase mover analysis
    phases = [("B_right", rows["B_right"]), ("C_stand", rows["C_stand"]),
              ("D_left", rows["D_left"])]
    for name, rs in phases:
        movers = {}
        for s in range(SLOTS):
            xs = [r["slots"].get(s, {}).get("x_px") for r in rs]
            xs = [x for x in xs if x is not None]
            if len(xs) >= 3:
                delta = xs[-1] - xs[0]
                if abs(delta) > 2.0:
                    movers[s] = {"delta": round(delta, 2),
                                 "first": round(xs[0], 1),
                                 "last": round(xs[-1], 1)}
        verdict["movers"][name] = movers
    cam = [r["camera_px"] for r in rows["B_right"]]
    verdict["camera_note"] = {
        "B_start": round(cam[0], 1), "B_end": round(cam[-1], 1),
        "B_delta": round(cam[-1] - cam[0], 2)}
    return verdict


def main():
    os.makedirs(EVID, exist_ok=True)
    p, fw = boot()
    tel = TelemetryAdapter(p)
    p.load_state("issue5_m1_start")
    for _ in range(30):
        p.core.run(1, set())
    s0 = snap_row(p, tel)
    _log(f"resumed: flags={s0['flags']} score={s0['score']} "
         f"hp={s0['hp_pair']} camera={s0['camera_px']:.1f}")
    rows = {"A_resume": [s0], "B_right": [], "C_stand": [], "D_left": []}
    pngs = []

    def seg(name, frames, btns, phase_rows):
        t0 = time.time()
        for i in range(frames):
            p.core.run(1, btns)
            if i % 10 == 0:
                phase_rows.append(snap_row(p, tel))
            if i % 200 == 0:
                f = os.path.join(EVID, f"{name}_f{i:04d}.png")
                from PIL import Image
                Image.fromarray(p.core.frame_rgb()).save(f)
                pngs.append(os.path.basename(f))
        _log(f"{name}: {frames}f in {time.time()-t0:.0f}s "
             f"score={phase_rows[-1]['score']} "
             f"cam={phase_rows[-1]['camera_px']:.1f} "
             f"hp={phase_rows[-1]['hp_pair']}")

    seg("B_right", 400, {"RIGHT"}, rows["B_right"])
    seg("C_stand", 150, set(), rows["C_stand"])
    seg("D_left", 150, {"LEFT"}, rows["D_left"])

    verdict = classify(rows)
    out = {"schema": "ps1play-probe0/1", "generated": time.strftime(
        "%FT%TZ", time.gmtime()), "verdict": verdict, "rows": rows,
        "pngs": pngs}
    path = os.path.join(EVID, "probe0_addresses.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=0)
    _log("WROTE", path)
    print(json.dumps(verdict, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
