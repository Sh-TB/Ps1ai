#!/usr/bin/env python3
"""msx_rain_slot_trace.py — live bomb-slot signature at the checkpoint
encounter (the 10-pattern ladder's faller census recorded 0 fallers
while the deaths are blast kills -> the w2 RainLogger signature
(hp!=0, 0x7E dropping 1..20/f) does NOT match this phase's bombs).

Protocol: load chopper_ckpt, replicate pattern 1 (walk RIGHT to the
corridor then stand), and every frame from f150 dump ALL slots with
xw != 0 whose 0x7E height < 140 (airborne/low) -> (X, h, hp, w7a).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np                                      # noqa: E402

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from issue4_controller import boot                      # noqa: E402
import msx_helicopter_ladder as hl                      # noqa: E402


def main():
    p, fw = boot()
    m = p.mem
    p.load_state(hl.CKPT)
    for _ in range(2):
        p.core.run_frame()
    out = open(os.path.join(hl.EVID, "rain_slot_trace.jsonl"), "w")
    prev = {}
    for i in range(290):
        px = hl.px_of(m)
        btns = {"RIGHT"} if px < 950.0 else set()
        p.core.set_buttons(btns)
        p.core.run_frame()
        tv = hl._table_words(m)
        for s in range(1, 40):
            xw = (int(tv[s, 61]) << 16) | int(tv[s, 60])
            h = int(tv[s, 63])
            hp = int(tv[s, 71])
            w7a = int(tv[s, 62])
            key = s
            ph = prev.get(key, {}).get("h")
            prev[key] = {"h": h, "hp": hp}
            if not xw:
                continue
            xpx = xw / 65536.0
            if h < 140 and (hp or ph is not None and ph != h):
                dh = (ph - h) if ph is not None else None
                out.write(json.dumps({
                    "f": i, "slot": s, "x": round(xpx, 1), "h": h,
                    "dh": dh, "hp": hp, "w7a": w7a,
                    "px": round(px, 1)}) + "\n")
        if hl.flags_of(m) != 0xFF or int(m.u16(hl.A_PAIR0)) == 0:
            out.write(json.dumps({"f": i, "END": True,
                                  "px": round(px, 1)}) + "\n")
            break
    out.close()
    print("done -> rain_slot_trace.jsonl")


if __name__ == "__main__":
    sys.exit(main())
