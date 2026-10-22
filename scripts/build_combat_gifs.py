#!/usr/bin/env python3
"""build_combat_gifs.py — deliverable GIF set for the combat-policy
work (user gameplay feedback, Issue #5 session 3).

Windows (global emulator frames; combat_6 segments are frame-seeded so
numbers are continuous across the three evidence dirs):
  B1 route_at_wall    baseline RoutePolicy at the section clamp:
                      holds RIGHT into the wall, never turns back
  C1 combat_advance   combat policy opening: run-through + forward
                      fire bursts + point-blank kills
  C2 combat_clamp_clear  the derived stage-end reached -> DEFENSIVE
                      rear-clear: face LEFT, fire into the pursuit
                      pack (jeep/grenadier), UP-fire at the chopper/
                      rain zone, hops + grenades
  C3 combat_clamp_late   later clamp phase from segment 2 (escalated
                      rounds, continues disclosed)
Output: $EV/gif2_combat_final/*.gif (local; mirrors are uploaded
separately; only the repo-copied set is committed to docs/).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
from build_run_gifs import build_gif                   # noqa: E402

EV = "/home/z/my-project/work/msx_recomp/evidence"
DIRS = {
    "route_base": os.path.join(EV, "gif2_route_base", "frames"),
    "route_base_r2": os.path.join(EV, "gif2_route_base_r2", "frames"),
    "combat_6": os.path.join(EV, "gif2_combat_6", "frames"),
    "combat_6_r2": os.path.join(EV, "gif2_combat_6_r2", "frames"),
    "combat_6_r3": os.path.join(EV, "gif2_combat_6_r3", "frames"),
}
OUT = os.path.join(EV, "gif2_combat_final")
REPO_OUT = "/home/z/my-project/ps1ai/docs/gif_evidence"

WINDOWS = [
    ("B1_route_at_wall", [("route_base", 15100, 15800),
                           ("route_base_r2", 17300, 17600)]),
    ("C1_combat_advance", [("combat_6", 12350, 12900)]),
    ("C2_combat_clamp_clear", [("combat_6", 13100, 13900)]),
    ("C3_combat_clamp_late", [("combat_6_r2", 18600, 19400)]),
]


def frange(spec, lo, hi):
    fs = os.listdir(spec)
    gset = {int(f[1:8]) for f in fs
            if f.startswith("f") and f.endswith(".jpg")}
    sel = [g for g in sorted(gset) if lo <= g <= hi]
    return [os.path.join(spec, f"f{g:07d}.jpg") for g in sel]


def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="cgif_")
    made = {}
    try:
        for name, parts in WINDOWS:
            paths = []
            for d, lo, hi in parts:
                paths += frange(DIRS[d], lo, hi)
            out = os.path.join(OUT, f"{name}.gif")
            r = build_gif(paths, out, 6, tmp)
            if r:
                made[name] = {"path": r, "frames": len(paths),
                              "size_mb": round(
                                  os.path.getsize(r) / 1e6, 2)}
                print("made", name, made[name])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        import json
        json.dump({"schema": "ps1play-gifset/1", "set": "combat_v6",
                   "windows": WINDOWS, "made": made}, f, indent=1)
    # copy into the repo evidence dir (committed like last session)
    os.makedirs(REPO_OUT, exist_ok=True)
    for name in made:
        shutil.copy2(os.path.join(OUT, f"{name}.gif"),
                     os.path.join(REPO_OUT, f"{name}.gif"))
    print("repo copies in", REPO_OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
