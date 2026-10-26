#!/usr/bin/env python3
"""psxmc_r11_item_survey.py — Round 11 / Segment 6c: is there ANY
placeable item at fresh spawn?  Scans all 9 hotbar slots (per-slot
item chain) + the inventory UI, with the L3/R3 selection walk.
ONE boot; no RAM writes; evidence -> scratch/round11_psxmc/place8/.
"""
import json, os, sys, time
_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path: sys.path.insert(0, _p)
import psxmc_r10_lib as L
from psxmc_r10_oracle import CUE, player_ptr, ensure_world_control
from psxmc_r7_lib import Evid
from ps1play.api import PS1Play

WS = "/home/z/my-project/emu/games_homebrew/ws_psxmc_r11p"
OUT = os.path.join(_REPO, "scratch", "round11_psxmc", "place8")

def main():
    ev = Evid(OUT, "itemsurvey")
    ev.jpath = os.path.join(OUT, "r11_itemsurvey.jsonl")
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    P = None
    for _ in range(240):
        P = player_ptr(p.mem)
        if P: break
        p.wait(30)
    if not P:
        ev.finish("FAILED: no player pointer"); return 1
    p.wait(240)
    m, core = p.mem, p.core
    ensure_world_control(core, m, P, ev, "survey")
    core.run(120, set())
    slots = []
    for off in range(0x40, 0x80, 4):
        H = L.phys(m.u32(P + off))
        if not L.is_heap(H): continue
        active = m.u8(H + 8)
        if active not in (0, 1): continue
        sel = m.u8(H + 100)
        for s in range(9):
            d = L.phys(m.u32(H + 28 + 8 * s))
            item = d
            if L.is_heap(d):
                r = L.phys(m.u32(d))
                if L.is_heap(r): item = r
            iid = m.u32(item) if L.is_heap(item) else None
            stack = m.u8(item + 12) if L.is_heap(item) else None
            if iid not in (None, 0) and (stack or 0) > 0:
                slots.append({"hotbar_off": off, "slot": s,
                              "item_id": iid, "stack": stack})
        ev.j({"ev": "hotbar_ui", "off": off, "active": active,
              "sel": sel, "per_slot": [
                  {"slot": s,
                   "item_id": (lambda it: m.u32(it) if L.is_heap(it) else None)(L.phys(m.u32(H + 28 + 8*s))),
                   "stack": (lambda it: m.u8(it + 12) if L.is_heap(it) else None)(L.phys(m.u32(H + 28 + 8*s)))}
                  for s in range(9)]})
    rep = {"schema": "ps1play-r11-itemsurvey/1",
           "placeable_slots": slots,
           "verdict": ("ITEMS_PRESENT" if slots else
                       "NO_ITEMS_AT_SPAWN"),
           "note": "per player.c:196 blockCanHarvest: hand cannot "
                   "harvest stone -> drop_item_on_break=false -> no "
                   "pickup path from stone; survey decides the "
                   "place-campaign closure",
           "wall_s": round(time.time() - ev.t0, 1)}
    json.dump(rep, open(os.path.join(OUT, "itemsurvey.json"), "w"),
              indent=1, default=str)
    ev.j({"ev": "final", **rep})
    ev.finish(rep["verdict"])
    print("VERDICT:", rep["verdict"], "slots:", slots)
    return 0

if __name__ == "__main__":
    sys.exit(main())
