#!/usr/bin/env python3
"""r51_gate_dryrun.py — OFFLINE gate dry-run against the boot-2 census.
No boot: replays pick_target decisions on the REAL census rows the
starved boots recorded, so boot 3 fires only if the gate provably
admits taps."""
import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(_REPO, "scripts"))
sys.path.insert(0, _REPO)

import r51t1_wound_hunt as R51  # noqa: E402  (module import only)

evs = [json.loads(l) for l in open(
    os.path.join(_REPO, "data/games/SLUS-01212/truck_evidence/r51",
                 "r51_boot2.jsonl"))]
cens = [e for e in evs if e.get("ev") == "CENSUS_FULL"]
ok = True
for c in cens:
    px = c["px"]
    ents = c["entities"]
    conn = R51.pick_target(ents, set(), px, "CONNECT")
    kill = R51.pick_target(ents, set(), px, "KILL")
    pierce = R51.pick_target(ents, set(), px, "PIERCE")
    print(f"{c['frontier']} px={px}: CONNECT->",
          None if conn is None else (conn["slot"], hex(conn["st"]),
                                     round(conn["x_px"], 1)),
          " KILL->", None if kill is None else (kill["slot"],
                                                hex(kill["st"])),
          " PIERCE->", None if pierce is None else (pierce["slot"],
                                                    hex(pierce["st"])))
    if conn is None and kill is None:
        ok = False
        print("  !! gate would starve again on this census")
print("GATE_DRYRUN:", "PASS (taps will flow)" if ok else "FAIL")
sys.exit(0 if ok else 1)
