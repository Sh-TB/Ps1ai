#!/usr/bin/env python3
"""run_psxmc_play.py — full-game play session for PSX-Minecraft through
the plugin contract (PSXMCPlayPlugin, contract v1, DualShock opt-in).

Real pad input only, zero memory writes, zero core edits. The sandbox
has no game-over: the run ends at the chunk budget (BUDGET_END) and the
report claims nothing beyond the verified events journaled per chunk
(move bursts with live displacement, turns, jumps, dig campaigns with
breaking-state churn, hotbar changes, health/air telemetry).

Evidence (local-only): emu/games_psx/evidence/psxmc_run_<id>/
"""
import argparse
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

CUE = "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"
WS = "/home/z/my-project/emu/games_psx/ws_psxmc_run"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", type=int, default=200)
    ap.add_argument("--chunk", type=int, default=60)
    args = ap.parse_args()

    run_id = time.strftime("psxmc_%Y%m%d_%H%M%S")
    out = f"/home/z/my-project/emu/games_psx/evidence/{run_id}"
    os.makedirs(out, exist_ok=True)
    trace = open(f"{out}/trace.jsonl", "w")

    def J(ev):
        trace.write(json.dumps(ev, default=str) + "\n")

    def shot(p, name):
        arr = p.core.frame_rgb()
        if arr is not None:
            Image.fromarray(arr).save(f"{out}/{name}.png")

    summary = {"run_id": run_id, "started": time.strftime("%FT%TZ",
                                                          time.gmtime()),
               "chunk_frames": args.chunk, "budget_chunks": args.chunks}
    t0 = time.time()
    p = PS1Play(CUE, workspace=WS)
    info = p.boot()
    summary["boot"] = info
    J({"ev": "boot", "info": info})
    f0 = p.core.frames_run

    feat = {}
    ev_seen = []
    for cidx in range(args.chunks):
        feat = p.plugin.features(p.mem, {}) if p.plugin else {}
        state = p.plugin.infer_state({}, feat) if p.plugin else "generic"
        segs = p.plugin.policy({"chunk": args.chunk,
                                "fc": p.core.frames_run,
                                "feat": feat,
                                "progress":
                                    cidx / max(args.chunks - 1, 1)}
                               ) if p.plugin else []
        for s in segs:
            p.core.run(s["frames"], s["btns"] or set())
        for e in getattr(p.plugin, "events", []):
            J({"ev": e["ev"], "fc": e.get("fc"), "chunk": cidx,
               "data": {k: v for k, v in e.items()
                        if k not in ("ev", "fc")}})
            ev_seen.append(e["ev"])
        p.plugin.events.clear() if hasattr(p.plugin, "events") else None
        row = {"chunk": cidx, "state": state,
               "pos_blocks": feat.get("pos_blocks"),
               "yaw": feat.get("yaw"), "pitch": feat.get("pitch"),
               "on_ground": feat.get("on_ground"),
               "health": feat.get("health"), "air": feat.get("air"),
               "hotbar_hash": feat.get("hotbar_hash"),
               "breaking_nonzero": feat.get("breaking_nonzero"),
               "time_ms": feat.get("time_ms"),
               "P": feat.get("P"), "P_raw": feat.get("P_raw")}
        J(row)
        if cidx % 20 == 0:
            shot(p, f"c{cidx:04d}")
        was_ready = summary.get("_world_seen")
        if feat.get("world_ready"):
            summary["_world_seen"] = True
        elif was_ready:
            summary["world_lost_at_chunk"] = cidx
            summary["world_lost_state"] = {
                "pos_blocks": feat.get("pos_blocks"),
                "on_ground": feat.get("on_ground")}
            J({"ev": "world_lost", "chunk": cidx,
               "state": summary["world_lost_state"]})
            break
        fr = p.core.frames_run
        if cidx > 0 and fr == summary.get("_fr_prev", fr):
            summary["halted_at_chunk"] = cidx
            J({"ev": "game_halted", "chunk": cidx, "frames": fr})
            break
        summary["_fr_prev"] = fr

    trace.close()
    f1 = p.core.frames_run
    shot(p, "end")
    from collections import Counter
    summary["events"] = dict(Counter(ev_seen))
    summary["frames_run"] = f1 - f0
    summary["wall_s"] = round(time.time() - t0, 1)
    summary["emu_fps"] = round((f1 - f0) / max(time.time() - t0, 1), 1)
    summary["finished"] = time.strftime("%FT%TZ", time.gmtime())
    summary["end_state"] = {"pos_blocks": feat.get("pos_blocks"),
                            "health": feat.get("health"),
                            "air": feat.get("air")}
    with open(f"{out}/report.json", "w") as f:
        json.dump(summary, f, indent=1, default=str)
    print(json.dumps(summary, indent=1, default=str)[:1800])
    try:
        p.core.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
