#!/usr/bin/env python3
"""msx_pin_matrix.py — the tight D7 pin experiment (three arms from the
SAME clamp0 savestate, per-frame traces, death-episode accounting,
SUSTAINED-traversal metric):

  P (pure)     : load clamp0 -> hold RIGHT 20 chunks. Baseline: is the
                 pin stable with no interference?
  R (respawn)  : load clamp0 -> keep holding RIGHT until the FIRST
                 death episode completes + respawn settles (cap 60
                 chunks) -> then hold RIGHT 20 chunks. Does a
                 death+respawn cycle change the traversal ceiling?
  L (leftwalk) : load clamp0 -> walk LEFT to px ~1100 (stop BEFORE the
                 truck at ~1126) -> walk RIGHT 20 chunks. Does the
                 left walk alone change anything?

Traversal verdict per arm: SUSTAINED >= 5 consecutive samples at
px >= 1180 (single-frame death-launch spikes do NOT count), plus the
max SUSTAINED px. All runs keep the disclosed hp-freeze EXPLORATION
assist (it demonstrably does NOT block truck one-shots - damage lands
after the freeze write within the frame); deaths are real game deaths.
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
from issue4_controller import boot                    # noqa: E402
import msx_gate_probe as gp                           # noqa: E402

EVID = os.path.join(
    labconfig.resolve_path("evidence_dir"), "pin_matrix")
PAIR = (0xCA2F6, 0xCA2FE)


def log(*a):
    print("[pinmatrix]", *a, flush=True)


def px_of(m):
    return int(m.u32(0x0CA2E0)) >> 16


def png(p, tag, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(EVID, f"{tag}_{name}"))


def is_alive(m):
    return int(m.u16(PAIR[0])) > 0 and px_of(m) > 1.0


def walk_frames(p, m, tag, n_chunks, btns, tracef, phase):
    """Run n_chunks of 60f holding btns; per-10f rows; stop 3 chunks
    after a death episode starts; return episode info."""
    deaths = 0
    dead_prev = True          # force 'alive' edge detection
    ep_start = None
    max_px = px_of(m)
    rows = []
    for c in range(n_chunks):
        for _k in range(6):
            p.core.run(10, btns)
            alive = is_alive(m)
            px = px_of(m)
            max_px = max(max_px, px) if alive else max_px
            rows.append({"f": int(p.core.frames_run), "px": px,
                         "hp": int(m.u16(PAIR[0])), "alive": alive,
                         "ph": phase})
            if not alive and not dead_prev:
                deaths += 1
                ep_start = int(p.core.frames_run)
                log(f"[{tag}] death #{deaths} at f={ep_start} "
                    f"px={px}")
            dead_prev = alive
        tracef.write(json.dumps({"chunk": c, "phase": phase,
                                 "deaths": deaths,
                                 "px": rows[-1]["px"]}) + "\n")
        if deaths >= 1 and phase == "die":
            # give 6 more chunks for the respawn to settle, then stop
            if ep_start and p.core.frames_run - ep_start > 360:
                break
    return {"deaths": deaths, "max_px": max_px, "rows": rows}


def sustained(rows, min_px=1180.0, need=5):
    """Longest run of consecutive alive samples at px>=min_px."""
    best = cur = 0
    best_px = 0.0
    for r in rows:
        if r["alive"] and r["px"] >= min_px:
            cur += 1
            if cur == 1:
                pass
            if cur > best:
                best = cur
            best_px = max(best_px, r["px"])
        else:
            cur = 0
    return best, best_px


def load_ckpt(p, m):
    p.load_state("clamp0")
    for _ in range(10):
        p.core.run(1, set())
    return px_of(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=20)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    p, fwmode = boot()
    m = p.mem
    out = {"schema": "ps1play-pin-matrix/1", "fw": fwmode,
           "arms": []}
    for tag in ("P_pure", "R_respawn", "L_leftwalk"):
        p0 = load_ckpt(p, m)
        session = gp.freeze_now(p, f"pin_{tag}")
        tracef = open(os.path.join(EVID, f"trace_{tag}.jsonl"), "w")
        pre = walk_frames(p, m, tag, 4, {"RIGHT"}, tracef, "verify")
        log(f"[{tag}] verify: max_px={pre['max_px']} "
            f"deaths={pre['deaths']} (expect pin 1163, 0 deaths)")
        if tag == "P_pure":
            res = walk_frames(p, m, tag, args.chunks, {"RIGHT"},
                              tracef, "pure")
        elif tag == "R_respawn":
            d = walk_frames(p, m, tag, 60, {"RIGHT"}, tracef, "die")
            log(f"[{tag}] die phase: deaths={d['deaths']} "
                f"max_px={d['max_px']}")
            res = walk_frames(p, m, tag, args.chunks, {"RIGHT"},
                              tracef, "after")
        else:                                  # L_leftwalk
            # walk LEFT until px <= 1100 (stop before the truck ~1126)
            for _ in range(600):
                if px_of(m) <= 1100 or px_of(m) < 1:
                    break
                p.core.run(1, {"LEFT"})
            lx = px_of(m)
            log(f"[{tag}] walked left to px={lx}")
            res = walk_frames(p, m, tag, args.chunks, {"RIGHT"},
                              tracef, "after")
        tracef.close()
        sus, sus_px = sustained(res["rows"])
        rep = {"tag": tag, "verify": pre, "result_deaths":
               res["deaths"], "max_px_any": res["max_px"],
               "sustained_chunks": sus, "sustained_max_px": sus_px,
               "traversed": sus >= 5}
        png(p, tag, "end.png")
        gp.unfreeze(session, f"pin_{tag}")
        out["arms"].append(rep)
        log(f"[{tag}] RESULT deaths={res['deaths']} "
            f"max_any={res['max_px']} sustained>=1180: {sus} chunks "
            f"(max {sus_px}) -> traversed={rep['traversed']}")
    with open(os.path.join(EVID, "report.json"), "w") as f:
        json.dump(out, f, indent=1)
    for a in out["arms"]:
        log(f"SUMMARY {a['tag']}: traversed={a['traversed']} "
            f"sustained={a['sustained_chunks']} "
            f"max_sustained_px={a['sustained_max_px']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
