#!/usr/bin/env python3
"""r19t7_timeline.py — exact-frame boot census for one old game (r19-t7).

r18 forensic findings this script builds on:
  * oldgames_r18_* booted TWO games in ONE process; the 2nd leg inherited the
    1st leg's core state (r14 lesson: one beetle boot per process), so the
    air_hockey leg of r18_bootfull and the ballistic leg of r18_probe are
    contaminated duplicates of the other game's screens.
  * ballistic's clean (1st) leg: Infogrames screen ~f1200, Mitchell logo
    ~f2400, then pure black from ~f2800 with zero RAM motion (census 0).
  * air_hockey's clean (1st, in r18_probe) leg: OpenBIOS boot-cube animation
    (2-color 640x472 frames) -> never booted the disc (bin is 2448-stride
    while its .cue declares MODE2/2352 -> every sector misread).

This script boots ONE game in a FRESH process and produces the honest census:
  * per-frame luma + frame-to-frame visual delta  -> EXACT transition frames
  * RAM nonzero byte count + RAM motion every --sample-every frames
  * PNG thumbs every --png-every frames + at every visual phase change
  * save-states at each stable visual phase (input battery uses these)
  * early exit when provably frozen (no visual + no RAM motion) after a
    generous floor; default budget 60k frames (~1000 simulated seconds).

Output: <outdir>/timeline_<name>.json + rows_<name>.csv + tl_<name>/*.png
"""
import argparse
import csv
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa: E402

RAMSZ = 2 * 1024 * 1024
D_THR = 40          # visual delta considered a "change"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cue", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--frames", type=int, default=60000)
    ap.add_argument("--sample-every", type=int, default=10)
    ap.add_argument("--png-every", type=int, default=250)
    ap.add_argument("--freeze-frames", type=int, default=6000)
    ap.add_argument("--min-frames", type=int, default=15000)
    ap.add_argument("--outdir", default="/home/z/my-project/scratch/r19t7_oldgames")
    ap.add_argument("--ws", default=None)
    args = ap.parse_args()

    ws = args.ws or f"/home/z/my-project/emu/games_small/play_evidence/r19t7/ws_{args.name}"
    pngdir = os.path.join(args.outdir, f"tl_{args.name}")
    os.makedirs(pngdir, exist_ok=True)

    p = PS1Play(args.cue, workspace=ws)
    info = p.boot()
    print("boot:", json.dumps(info, default=str), flush=True)

    lumas = np.zeros(args.frames + 2, dtype=np.float32)
    deltas = np.zeros(args.frames + 2, dtype=np.int64)
    shapes = {}
    rows_ram = []                       # every sample-every frames
    pngs = []
    t0 = time.time()

    prev_img = None
    prev_ram = None
    freeze_since = None
    last_change_f = 0
    last_ckpt_f = 0
    ckpts = []
    f = 0

    def save_png(fr, img, tag=""):
        name = f"{args.name}_f{fr:06d}{tag}.png"
        Image.fromarray(img).save(os.path.join(pngdir, name))
        pngs.append(name)

    while f < args.frames:
        p.core.run(1, set())
        f += 1
        img = p.core.frame_rgb()
        if img is None:
            lumas[f] = -1
            continue
        lumas[f] = float(img.mean())
        if prev_img is not None and prev_img.shape == img.shape:
            deltas[f] = int(np.abs(img.astype(np.int16) - prev_img.astype(np.int16)).sum())
        else:
            deltas[f] = 1 << 30         # shape switch counts as a hard change
        prev_img = img
        shapes[f] = img.shape
        if deltas[f] > D_THR:
            last_change_f = f

        if f % args.png_every == 0:
            save_png(f, img)

        # stable-stretch live checkpoint (for the r19t7 input battery)
        if (f - last_change_f >= 150 and f - last_ckpt_f >= 300 and f >= 600
                and len(ckpts) < 8):
            cname = f"{args.name}_ck_f{f:06d}"
            try:
                p.save_state(cname)
                ckpts.append({"name": cname, "at_frame": f,
                              "stable_since": last_change_f})
                last_ckpt_f = f
            except Exception as e:                               # noqa
                print("ckpt fail:", repr(e)[:120], flush=True)
                last_ckpt_f = f          # avoid retry spam

        if f % args.sample_every == 0:
            ram = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8)
            nz = int((ram[:RAMSZ] != 0).sum())
            rdiff = int((ram[:RAMSZ] != prev_ram[:RAMSZ]).sum()) if prev_ram is not None else 0
            prev_ram = ram
            rows_ram.append((f, rdiff, nz))
            if deltas[f] == 0 and rdiff == 0:
                if freeze_since is None:
                    freeze_since = f
            else:
                freeze_since = None
            if (freeze_since is not None and f - freeze_since >= args.freeze_frames
                    and f >= args.min_frames):
                print(f"early-exit: provably frozen since f{freeze_since}", flush=True)
                break

    frames_run = f

    # ---- exact phase segmentation from per-frame deltas ----
    changed = deltas[1:frames_run + 1] > D_THR
    bounds = [i + 1 for i in range(frames_run) if changed[i]]
    # collapse bursts: a burst of change frames = one transition event
    events = []
    for b in bounds:
        if not events or b - events[-1][-1] > 25:
            events.append([b])
        else:
            events[-1].append(b)
    exact = [e[0] for e in events]

    phases = []
    edges = [1] + [e[-1] + 1 for e in events] + [frames_run]
    for i in range(len(edges) - 1):
        a, b = edges[i], edges[i + 1]
        if b <= a:
            continue
        seg = lumas[a:b + 1]
        seg = seg[seg >= 0]
        shp = shapes.get(b, shapes.get(a))
        phases.append({"start_f": a, "end_f": b, "frames": b - a + 1,
                       "w": int(shp[1]) if shp else None,
                       "h": int(shp[0]) if shp else None,
                       "luma_mean": round(float(seg.mean()), 2) if len(seg) else None,
                       "n_change_frames": int(changed[a - 1:b].sum())})

    # ---- checkpoints: stable-stretch saves happened live; ensure a final one
    if not ckpts or ckpts[-1].get("at_frame") != frames_run:
        try:
            p.save_state(f"{args.name}_final_f{frames_run}")
            ckpts.append({"name": f"{args.name}_final_f{frames_run}",
                          "at_frame": frames_run})
        except Exception as e:                                       # noqa
            ckpts.append({"error": repr(e)[:160]})

    summary = {
        "game": args.name,
        "cue": args.cue,
        "boot": {k: info[k] for k in ("core", "serial", "plugin")},
        "frames_run": frames_run,
        "wall_s": round(time.time() - t0, 1),
        "early_exit_frozen_since": freeze_since,
        "exact_transition_frames": exact,
        "phases": phases,
        "checkpoints": ckpts,
        "pngs": len(pngs),
        "final_png": pngs[-1] if pngs else None,
    }
    with open(os.path.join(args.outdir, f"timeline_{args.name}.json"), "w") as fp:
        json.dump(summary, fp, indent=1, default=str)
    with open(os.path.join(args.outdir, f"rows_{args.name}.csv"), "w", newline="") as fp:
        w = csv.writer(fp)
        w.writerow(["frame", "luma", "visual_delta", "w", "h", "ram_nonzero", "ram_motion_bytes"])
        ram_map = {r[0]: r for r in rows_ram}
        for i in range(1, frames_run + 1):
            shp = shapes.get(i)
            r = ram_map.get(i) if i % args.sample_every == 0 else None
            w.writerow([i, round(float(lumas[i]), 2) if lumas[i] >= 0 else "",
                        deltas[i] if deltas[i] < (1 << 30) else "SHAPE",
                        shp[1] if shp else "", shp[0] if shp else "",
                        r[2] if r else "", r[1] if r else ""])
    print(json.dumps({k: summary[k] for k in
                      ("game", "frames_run", "wall_s", "exact_transition_frames",
                       "phases", "early_exit_frozen_since")}, indent=1, default=str),
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
