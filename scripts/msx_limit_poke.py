#!/usr/bin/env python3
"""msx_limit_poke.py — the decisive D7 experiment: poke the pin-limit
candidate u16 @ 0x8008DBF8 (== 1164) from the clamp0 savestate (taken
AT pin arrival, px 1163, this session) and test whether the player
walks past the village-section boundary.

Arms (each from a fresh load of clamp0, RIGHT held, 18 chunks):
  arm S (specificity)  : u16 @ 0x8008DBF8 := 2000   (the candidate)
  arm N (neighbour)    : u16 @ 0x8008DBFC := 2000   (control poke)
  arm 0 (no poke)      : no write                   (control)
All writes are DISCLOSED EXPLORATION probes (never part of agent play);
the observation itself is read-only. Report px max per arm + JSONL.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

from PIL import Image                                 # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                         # noqa: E402
from ps1play.agent.cheatprof import CheatSession, CHEAT_ASSISTED  # noqa
from ps1play.agent.gameshark import GSCode            # noqa: E402
from msx_gate_probe import PAIR, log                  # noqa: E402
from issue4_controller import boot                    # noqa: E402

EVID = os.path.join(
    labconfig.resolve_path("evidence_dir"), "clamp_globals")
CKPT = "clamp0"
LIMIT_ADDR = 0x8008DBF8


def px_of(m):
    return int(m.u32(0x0CA2E0)) >> 16


def arm_run(p, m, poke_addr, tag, chunks=18):
    """One arm: load clamp0, optional disclosed poke, walk RIGHT."""
    p.load_state(CKPT)
    for _ in range(10):
        p.core.run(1, set())
    px0 = px_of(m)
    session = None
    if poke_addr is not None:
        cur = int(m.u16(poke_addr & 0x1FFFFF))
        session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
        code = GSCode(f"8{poke_addr & 0x7FFFFFF:07X} 07D0")
        session.enable(f"limit_poke_{tag}", [code])
        log(f"[{tag}] DISCLOSED EXPLORATION poke: u16@{poke_addr:#x} "
            f"was {cur} -> 2000")
    jf = open(os.path.join(EVID, f"poke_{tag}.jsonl"), "w")
    max_px = px0
    t0 = time.time()
    for c in range(chunks):
        for _k in range(6):
            p.core.run(10, {"RIGHT"})
        px = px_of(m)
        max_px = max(max_px, px)
        jf.write(json.dumps(
            {"f": int(p.core.frames_run), "px": px,
             "hp0": int(m.u16(PAIR[0]))}) + "\n")
        if px_of(m) <= 1:                      # died -> stop
            log(f"[{tag}] death at chunk {c}")
            break
    jf.close()
    if session is not None:
        session.disable(f"limit_poke_{tag}")
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, f"poke_{tag}.png"))
    log(f"[{tag}] RESULT px0={px0} max_px={max_px} "
        f"chunks={chunks} wall={time.time()-t0:.0f}s")
    return {"tag": tag, "poke": hex(poke_addr) if poke_addr else None,
            "px0": px0, "max_px": max_px}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=18)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    p, fwmode = boot()
    m = p.mem
    out = {"schema": "ps1play-limit-poke/1", "fw": fwmode,
           "arms": []}
    for poke, tag in [(LIMIT_ADDR, "S_limit"),
                      (0x8008DBFC, "N_neighbour"),
                      (None, "0_nopoke")]:
        out["arms"].append(arm_run(p, m, poke, tag, args.chunks))
    with open(os.path.join(EVID, "report_limit_poke.json"), "w") as f:
        json.dump(out, f, indent=1)
    log("report written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
