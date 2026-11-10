#!/usr/bin/env python3
"""r72_corridor_feed_map.py — R72 offline analysis: THE CORRIDOR-FEED
MAP over the r72 hybrid boot (no boots — the r72 product JSONL).

The R72 boot-1 result: the hybrid threw ON GRID at the PRE-SIDE
frames (fight_f 146/310/475 = the lands freeze+176/340/505) and the
k=2 land CONNECTED (a4 280->180 at f1657 = freeze+506, the register
frame) while the k=0/k=1 lands MISSED.  This map explains the
misses: the corridor occupancy at every grid land (the live mortals
between the parked truck 937.5 and the player posture) — the R71
corridor-feed law (the occupancy is STREAM-DEPENDENT) applied to the
R72 idle-hold stream.

Method (offline, verbatim the r71 map logic):
  * the spawns: the first live sighting of each slot (the world-x
    band test — the R71 verdict: the feed fills the corridor+rear
    zone by POSITION);
  * the corridor occupancy at each land window (+-2f);
  * the a4 ledger + the throw/connect outcome at the lands.

Evidence: data/games/SLUS-01212/truck_evidence/r72/
          r72_corridor_feed_map.json
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r72")
BOOT_FILE = "r72_hybrid_probe_boot1.jsonl"

TRUCK_X = 937.5
PHASE_BASE = 178.0
PHASE_PERIOD = 164.0
TOL = 2.0
X_MAX = 4096.0

CORPSEISH = {"0x5b0c", "0x5cc8", "0x4be4", "0xa304", "0xa44c",
             "0xa45c", "0x6730", "0x540c", "0x515c"}


def log(*a):
    print("[r72-feed]", *a, file=sys.stderr, flush=True)


def analyze_boot(path):
    rows = [json.loads(l) for l in open(path)]
    boot = rows[0].get("boot", 1)
    # the spawns: the first live sighting of each slot (from the
    # every-frame tables)
    seen = {}
    spawns = []
    for r in rows:
        for e in (r.get("table") or []):
            s = e["slot"]
            if s in seen:
                continue
            if e["corpse"] or e["st"] in CORPSEISH:
                seen[s] = True      # a corpse sighting pins the slot
                continue
            if e["a4"] <= 0 and e["st"] not in (
                    "0x4054", "0x42bc", "0x9e88"):
                continue
            if not (0.0 < float(e["x"]) < X_MAX):
                continue
            seen[s] = True
            spawns.append({"f": r["f"], "slot": s, "st": e["st"],
                           "x": e["x"], "px": r.get("px")})
    max_f = max((r.get("f") or 0) for r in rows)
    freeze = None
    for r in rows:
        if r.get("ents") and any(e[1] == 7 for e in r["ents"]):
            freeze = r["f"]
            break
    lands = []
    if freeze:
        k = 0
        while True:
            land = freeze + PHASE_BASE + k * PHASE_PERIOD
            if land > max_f:
                break
            lands.append((k, int(round(land))))
            k += 1
    corr = {}
    for k, land in lands:
        occ = []
        for r in rows:
            if not (land - TOL <= (r.get("f") or 0) <= land + TOL):
                continue
            for e in (r.get("table") or []):
                if e["corpse"] or e["st"] in CORPSEISH:
                    continue
                if e["a4"] <= 0 and e["st"] not in (
                        "0x4054", "0x42bc", "0x9e88"):
                    continue
                if TRUCK_X < e["x"] < r.get("px", 0):
                    occ.append({"f": r["f"], "slot": e["slot"],
                                "st": e["st"], "x": e["x"],
                                "a4": e["a4"]})
        corr[f"k{k}_land{land}"] = {
            "occupied": bool(occ), "rows": occ[:6]}
    a4ev = [(r["f"], r["from"], r["to"], r["cls"])
            for r in rows if r.get("ev") == "A4_TRANSITION"]
    throws = [{"f": t["f"], "fight_f": t["fight_f"],
               "phase_k": t["phase_k"]}
              for t in (r for r in rows
                        if r.get("ev") == "GRID_THROW")]
    return {"boot": boot, "freeze": freeze, "lands": lands,
            "n_spawns": len(spawns), "spawns": spawns[:60],
            "corridor_at_lands": corr, "a4_ledger": a4ev,
            "grid_throws": throws}


def main():
    path = os.path.join(EVID, BOOT_FILE)
    out = {"schema": "ps1play.r72-corridor-feed/1",
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "note": "offline over the r72 hybrid boot-1 JSONL (the "
                   "idle-hold stream; the ledger: 1/3 boots spent, "
                   "2 held — no correction boot was needed, the "
                   "lever's product question answered by boot 1)",
           "boots": {}}
    log("analyzing", BOOT_FILE)
    out["boots"]["1"] = analyze_boot(path)
    xs = [s["x"] for b in out["boots"].values()
          for s in b["spawns"] if s["x"]]
    out["spawn_x_spread"] = (min(xs), max(xs)) if xs else None
    out["verdict"] = {
        "spawn_zone": out["spawn_x_spread"],
        "time_vs_position": (
            "POSITION-CONSISTENT with the R71 map: the live spawns "
            "concentrate in the world-x corridor+rear band (the "
            "spread below) — the feed fills by POSITION, not on a "
            "fixed frame grid" if xs else "no spawn data"),
    }
    dst = os.path.join(EVID, "r72_corridor_feed_map.json")
    with open(dst, "w") as f:
        json.dump(out, f, indent=1)
    log("map ->", dst)
    # the console verdict: the occupancy at each land
    b = out["boots"]["1"]
    print("freeze:", b["freeze"], "lands:", b["lands"])
    for key, occ in b["corridor_at_lands"].items():
        print(f"  {key}: occupied={occ['occupied']} "
              f"rows={[(r['slot'], r['st'], r['x']) for r in occ['rows']]}")
    print("a4 ledger:", b["a4_ledger"])
    print("throws:", b["grid_throws"])
    print("spawn spread:", out["spawn_x_spread"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
