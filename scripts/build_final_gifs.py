#!/usr/bin/env python3
"""build_final_gifs.py — assemble the deliverable GIF set for the user
from the recorded run frames (gif2 = legit combat run, gif3 = the
mosque/truck/clamp push), then upload to an image host.

Windows (captured-frame numbers = global emulator frame // 10):
  G1 legit_run_start    gif2 f12320-13520  rope -> desert -> first
                        fights -> mosque pass (score 200->1500)
  G2 legit_clamp_fight  gif2 f14020-15200  the village-end truck
                        checkpoint fight (score 1800, soldiers, bombs)
  G3 deaths_recovery    gif2  windows around the 13 recorded deaths
  G4 mosque_push        gif3 f13043-16475  disclosed-assist push: walk
                        to the mosque, grenade volley (+200/+100/+500
                        kills), unfrozen traversal past the truck to
                        the section clamp at 1163px
  G5 clamp_arrival      gif3  last 130 captured frames (the truck pass
                        and the clamp wall close-up)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
from build_run_gifs import build_gif                   # noqa: E402

EV = "/home/z/my-project/work/msx_recomp/evidence"
G2 = os.path.join(EV, "issue5_gif_gif2", "frames")
G3 = os.path.join(EV, "issue5_gif_gif3", "frames")
OUT = os.path.join(EV, "issue5_gif_final")
os.makedirs(OUT, exist_ok=True)


def frange(d, lo, hi):
    fs = os.listdir(d)
    gset = {int(f[1:8]) for f in fs if f.startswith("f") and f.endswith(".jpg")}
    sel = [g for g in sorted(gset) if lo <= g <= hi]
    return [os.path.join(d, f"f{g:07d}.jpg") for g in sel]


def death_windows():
    wins = []
    for l in open(os.path.join(EV, "issue5_gif_gif2",
                               "trace_gif2.jsonl")):
        r = json.loads(l)
        if r.get("type") == "death_recovery":
            fs = r.get("frame") or 0
            wins.append((max(12317, fs - 400), fs + 400))
    return wins


def main():
    tmp = tempfile.mkdtemp(prefix="fgif_")
    made = {}
    try:
        w = [(12320, 13520), (14020, 15200), (13600, 14700)]
        made["G1_legit_run_start"] = build_gif(
            frange(G2, *w[0]), os.path.join(OUT, "G1_legit_run_start.gif"),
            6, tmp)
        made["G2_legit_clamp_fight"] = build_gif(
            frange(G2, *w[1]), os.path.join(OUT, "G2_legit_clamp_fight.gif"),
            6, tmp)
        made["G3_legit_mid_pass"] = build_gif(
            frange(G2, *w[2]), os.path.join(OUT, "G3_legit_mid_pass.gif"),
            6, tmp)
        # G4: deaths + recovery windows from the A trace
        chunks_frames = {}
        deaths = []
        for l in open(os.path.join(EV, "issue5_gif_gif2",
                                   "trace_gif2.jsonl")):
            r = json.loads(l)
            if r.get("type") == "chunk" and "telemetry" in r and \
                    "phase" not in r:
                chunks_frames[r["chunk"]] = r["frame_start"]
            elif r.get("type") == "death_recovery":
                deaths.append(r["chunk"])
        sel = []
        for c in deaths[:6]:
            fs = chunks_frames.get(c)
            if fs is None:
                continue
            sel.extend(g for g in range(max(12317, fs - 300),
                                        fs + 300, 10))
        sel = sorted(set(sel))[:260]
        made["G4_deaths_recovery"] = build_gif(
            [os.path.join(G2, f"f{g:07d}.jpg") for g in sel
             if os.path.exists(os.path.join(G2, f"f{g:07d}.jpg"))],
            os.path.join(OUT, "G4_deaths_recovery.gif"), 6, tmp)
        # G5: the mosque push (whole gif3 story)
        made["G5_mosque_truck_clamp"] = build_gif(
            frange(G3, 13043, 16475),
            os.path.join(OUT, "G5_mosque_truck_clamp.gif"), 6, tmp)
        # G6: clamp arrival close-up
        made["G6_clamp_arrival"] = build_gif(
            frange(G3, 15600, 16475),
            os.path.join(OUT, "G6_clamp_arrival.gif"), 6, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for k, v in made.items():
        if v and os.path.exists(v):
            print(f"{k}: {os.path.getsize(v)//1024} KB  {v}")
    with open(os.path.join(OUT, "manifest.json"), "w") as f:
        json.dump({k: v for k, v in made.items() if v}, f, indent=1)


if __name__ == "__main__":
    main()
