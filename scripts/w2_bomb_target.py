#!/usr/bin/env python3
"""w2_bomb_target.py — does the mortar script TRACK the player or is it
a fixed world-x schedule? (determines the crossing strategy)

Protocol from `arena2` (freeze on):
  P1  100f idle            -> baseline spawn X set (expect ~915 band)
  P2  240f hold RIGHT      -> player runs right; record spawns
  P3  300f idle            -> do spawns follow the player's new X?
  P4  240f hold RIGHT again-> second run, second sample

Per frame: all 40 slots' (0x7E,0x78,0x7A,0x8E) to catch spawns; slot0
full words; prog; hp-pair; PNG at boundaries.
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

import msx_gate_probe as gp                     # noqa: E402

EVID = gp.EVID
TABLE, STRIDE = gp.TABLE, gp.STRIDE


def slot_words(m, s):
    base = TABLE + s * STRIDE
    return m.ram[base:base + STRIDE].view("<u2").astype(np.int32).tolist()


def xfix(w):
    return ((int(w[61]) << 16) | int(w[60])) / 65536.0


def main():
    t0 = time.time()
    p, fw = gp.boot()
    m = p.mem
    p.load_state("arena2")
    session = gp.freeze_now(p, "w2_bombtarget")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()

    phases = [("P1_idle", 100, set()),
              ("P2_right", 240, {"RIGHT"}),
              ("P3_idle", 300, set()),
              ("P4_right", 240, {"RIGHT"})]
    events = open(os.path.join(EVID, "w2_bomb_target.jsonl"), "w")
    per_frame = open(os.path.join(EVID, "w2_bomb_target_frames.jsonl"),
                     "w")
    prev = {s: slot_words(m, s) for s in range(40)}
    tracking = {}          # slot -> spawn info
    frame = 0
    for pname, plen, btns in phases:
        gp.png(p, f"w2bt_{pname}_start.png")
        for k in range(plen):
            p.core.set_buttons(set(btns))
            p.core.run_frame()
            session.gs.tick()
            w0 = slot_words(m, 0)
            cur = {}
            for s in range(40):
                w = slot_words(m, s)
                cur[s] = w
                if s == 0:
                    continue
                h, hp = w[63], w[71]
                ph, php = prev[s][63], prev[s][71]
                if php == 0 and hp != 0 and h > 64:
                    tracking[s] = {"spawn_f": frame, "X": xfix(w),
                                   "h0": h, "hp": hp}
                    events.write(json.dumps(
                        {"phase": pname, "f": frame, "slot": s,
                         "X": xfix(w), "h0": h, "hp": hp}) + "\n")
            prev = cur
            per_frame.write(json.dumps({
                "f": frame, "phase": pname,
                "pX": xfix(w0), "p7E": w0[63],
                "prog": m.u16(gp.A_PROGRESS),
                "pair0": m.u16(gp.A_PAIR0)}) + "\n")
            frame += 1
        gp.png(p, f"w2bt_{pname}_end.png")
        gp.log(f"{pname} done at f{frame}: player X={xfix(w0):.1f} "
               f"prog={m.u16(gp.A_PROGRESS)} pair0={m.u16(gp.A_PAIR0)}")
    events.close()
    per_frame.close()
    gp.unfreeze(session, "w2_bombtarget")
    gp.png(p, "w2bt_end.png")
    json.dump({"wall_s": round(time.time() - t0, 1)},
              open(os.path.join(EVID, "w2_bomb_target.json"), "w"))
    gp.log("done")


if __name__ == "__main__":
    main()
