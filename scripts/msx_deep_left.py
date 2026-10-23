#!/usr/bin/env python3
"""msx_deep_left.py — Arm D: does a SURVIVED deep-left traverse (past
the truck, into the 660-880 lob zone) change the RIGHT traversal
ceiling? The messy mosque-gate arms both did a deep-left walk (lob
spot / grenade pile); the clean L arm stopped at 1100 and stayed
pinned. This isolates the deep-left variable with the truck-hop gait
(LEFT held, B hop when stuck - the walk_to_window gait that
successfully reached the window in the gif_story sessions).

From clamp0: verify pin -> deep-left to 700-780 (hop the truck) ->
walk RIGHT 20 chunks -> sustained-traversal verdict.
"""
from __future__ import annotations

import json
import os
import sys

from PIL import Image                                 # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                         # noqa: E402
from issue4_controller import boot                    # noqa: E402
import msx_gate_probe as gp                           # noqa: E402
from msx_pin_matrix import (px_of, is_alive, sustained, png, PAIR, log)


def main():
    os.makedirs(
        "/home/z/my-project/work/msx_recomp/evidence/pin_matrix",
        exist_ok=True)
    EVID = os.path.join(
        labconfig.resolve_path("evidence_dir"), "pin_matrix")
    p, fwmode = boot()
    m = p.mem
    p.load_state("clamp0")
    for _ in range(10):
        p.core.run(1, set())
    session = gp.freeze_now(p, "pin_D_deep")
    log(f"loaded clamp0 px={px_of(m):.0f}")

    # 1) verify pin
    for _c in range(4):
        p.core.run(60, {"RIGHT"})
    log(f"verify pin: px={px_of(m):.0f}")

    # 2) deep-left with truck hop (walk_to_window gait)
    stuck = 0
    reached = False
    for i in range(3600):
        x = px_of(m)
        if not is_alive(m):
            log(f"DIED during deep-left at f={p.core.frames_run} "
                f"px={x:.0f}")
            break
        if 700.0 <= x <= 780.0:
            reached = True
            log(f"reached deep-left target px={x:.0f} at i={i}")
            break
        btns = {"LEFT", "Y"}
        if stuck > 40:
            btns.add("B")
        p.core.run(1, btns)
        nx = px_of(m)
        stuck = stuck + 1 if abs(nx - x) < 0.3 else 0
    dx = px_of(m)
    log(f"deep-left end: reached={reached} px={dx:.0f} "
        f"gren={int(m.u8(0x0EDCF4))}")

    # 3) walk RIGHT 20 chunks with per-10f rows
    rows = []
    deaths = 0
    alive_prev = True
    max_px = 0.0
    for c in range(20):
        for _k in range(6):
            p.core.run(10, {"RIGHT"})
            alive = is_alive(m)
            px = px_of(m)
            if alive:
                max_px = max(max_px, px)
            rows.append({"f": int(p.core.frames_run), "px": px,
                         "hp": int(m.u16(PAIR[0])), "alive": alive})
            if not alive and alive_prev:
                deaths += 1
                log(f"death #{deaths} f={p.core.frames_run} px={px}")
            alive_prev = alive
    sus, sus_px = sustained(rows)
    rep = {"tag": "D_deep", "deep_left_reached": reached,
           "deep_left_px": dx, "deaths": deaths,
           "max_px_any": max_px, "sustained_chunks": sus,
           "sustained_max_px": sus_px, "traversed": sus >= 5}
    png(p, "D_deep", "end.png")
    gp.unfreeze(session, "pin_D_deep")
    with open(os.path.join(EVID, "report_D.json"), "w") as f:
        json.dump(rep, f, indent=1)
    with open(os.path.join(EVID, "rows_D.json"), "w") as f:
        json.dump(rows, f)
    log(f"RESULT reached={reached} deaths={deaths} "
        f"max_any={max_px} sustained={sus} (max {sus_px}) "
        f"traversed={rep['traversed']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
