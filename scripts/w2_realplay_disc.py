#!/usr/bin/env python3
"""w2_realplay_disc.py — WHERE does real play become the attract demo?

Protocol (no freeze, no savestates — pure observation):
  phase A  boot() -> 6 chunks of CONTINUOUS RIGHT+Y: per chunk record
           prog, demo-band white, pad mirror 0x0D4948, hp0, PNG
           (real play must show prog rising + mirror ~0x0020 while held)
  phase B  3 chunks of IDLE: real play -> mirror 0x0000 (documented);
           demo -> mirror shows the ATTRACT SCRIPT's inputs (nonzero,
           changing) and the demo band lights up
  phase C  6 chunks RIGHT+Y again: does real play resume?
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_gate_probe as gp                     # noqa: E402
from ps1play.telemetry import TelemetryAdapter  # noqa: E402

EVID = gp.EVID
A_PROGRESS, A_FLAGS = gp.A_PROGRESS, gp.A_FLAGS
MIRROR = 0x0D4948


def band_white(p):
    rgb = p.core.frame_rgb()
    if rgb is None:
        return -1.0
    a = np.asarray(Image.fromarray(rgb).convert("RGB"),
                   dtype=np.int32)[6:30, 200:318]
    return float(((a[:, :, 0] > 200) & (a[:, :, 1] > 200) &
                  (a[:, :, 2] > 200)).mean())


def sample(p, tag, btns):
    m = p.mem
    tel = TelemetryAdapter(p)
    row = {
        "phase": tag,
        "prog": m.u16(A_PROGRESS),
        "mirror": hex(m.u16(MIRROR)),
        "mirror_raw": m.u16(MIRROR),
        "hp0": m.u16(gp.TABLE + gp.HP_OFF),
        "flags": m.u16(A_FLAGS),
        "band": round(band_white(p), 4),
        "hud_score": tel.read_score(),
    }
    gp.png(p, f"w2rd_{tag}.png")
    gp.log(f"[{tag}] prog={row['prog']} mirror={row['mirror']} "
           f"hp0={row['hp0']} band={row['band']} score={row['hud_score']}")
    return row


def main():
    p, fw = gp.boot()
    rows = []
    # ---- phase A: 6 chunks RIGHT+Y (real play advances) ----
    for k in range(6):
        for _ in range(60):
            p.core.set_buttons({"RIGHT", "Y"})
            p.core.run_frame()
        rows.append(sample(p, f"A{k}", {"RIGHT", "Y"}))
    # ---- phase B: 3 chunks IDLE ----
    for k in range(3):
        p.core.run(60, set())
        rows.append(sample(p, f"B{k}", set()))
    # ---- phase C: 6 chunks RIGHT+Y again ----
    for k in range(6):
        for _ in range(60):
            p.core.set_buttons({"RIGHT", "Y"})
            p.core.run_frame()
        rows.append(sample(p, f"C{k}", {"RIGHT", "Y"}))

    json.dump(rows, open(os.path.join(EVID, "w2_realplay_disc.json"),
                         "w"), indent=1)
    gp.log("saved w2_realplay_disc.json")


if __name__ == "__main__":
    main()
