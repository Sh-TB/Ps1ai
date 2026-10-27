#!/usr/bin/env python3
"""r19t7_inputscan.py — frame-by-frame input battery at an exact frame (r19-t7).

The honest TITLE_REACHED test for the old games:
  1. fresh process, boot, run with NO input to --at (the exact frame to test),
     PNG + checkpoint.
  2. control: hold NO buttons, frame-by-frame `--hold` frames, record
     per-frame RAM motion (ambient) + visual delta.
  3. battery: for each button (START CROSS TRIANGLE CIRCLE SQUARE SELECT
     UP DOWN LEFT RIGHT): restore checkpoint, hold the button, frame-by-frame,
     record per-frame RAM motion + visual delta. FIRST frame where RAM motion
     exceeds the ambient threshold = first input-response frame. PNG at the
     response frame and at window end.
  4. --mash mode: fresh boot, cycle (START, CROSS, TRIANGLE, START, ...) every
     30 frames from f300 to --at, then keep watching to --watch. Phase events
     (visual-transition bursts) are compared against the no-input baseline
     events from timeline_<name>.json -> proves/disproves logo-skip and any
     input-driven path change.

Prints a JSON verdict; writes inputscan_<name>_<at>.json + PNGs.
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
from ps1play.api import PS1Play                                   # noqa: E402

RAMSZ = 2 * 1024 * 1024
D_THR = 40
BUTTONS = ["START", "B", "X", "A", "Y", "SELECT", "UP", "DOWN", "LEFT", "RIGHT"]


def ram_motion(p, prev):
    r = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8)
    d = int((r[:RAMSZ] != prev[:RAMSZ]).sum()) if prev is not None else 0
    return r, d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cue", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--at", type=int, default=3400, help="frame to test at")
    ap.add_argument("--hold", type=int, default=240)
    ap.add_argument("--mash", action="store_true")
    ap.add_argument("--watch", type=int, default=12000,
                    help="mash mode: watch until this frame")
    ap.add_argument("--outdir", default="/home/z/my-project/scratch/r19t7_oldgames")
    ap.add_argument("--ws", default=None)
    ap.add_argument("--buttons", default=",".join(BUTTONS))
    args = ap.parse_args()

    ws = args.ws or f"/home/z/my-project/emu/games_small/play_evidence/r19t7/ws_{args.name}"
    pngdir = os.path.join(args.outdir, f"in_{args.name}")
    os.makedirs(pngdir, exist_ok=True)
    btns = [b.strip().upper() for b in args.buttons.split(",") if b.strip()]
    tag = "mash" if args.mash else f"f{args.at}"
    out = {"game": args.name, "mode": "mash" if args.mash else "battery",
           "at": args.at, "hold": args.hold, "buttons": btns, "started": time.strftime("%FT%TZ", time.gmtime())}

    def png(p, fr, label):
        img = p.core.frame_rgb()
        if img is not None:
            Image.fromarray(img).save(os.path.join(pngdir, f"{args.name}_{label}_f{fr:06d}.png"))
        return img

    p = PS1Play(args.cue, workspace=ws)
    info = p.boot()
    out["boot"] = {k: info[k] for k in ("core", "serial", "plugin")}

    if args.mash:
        # ---- mash mode: cyclic pulses from f300, watch phases ----
        events = []
        last_change = 0
        cur_burst = None
        prev_img = None
        cycle = [b for b in ("START", "B", "X", "A", "Y", "START", "B", "SELECT")]
        f = 0
        rows = []
        while f < args.watch:
            held = set() if f < 300 or (f // 30) % 3 == 2 else {cycle[(f // 30) % len(cycle)]}
            p.core.run(1, held)
            f += 1
            img = p.core.frame_rgb()
            if img is None:
                continue
            d = int(np.abs(img.astype(np.int16) - prev_img.astype(np.int16)).sum()) \
                if prev_img is not None and prev_img.shape == img.shape else 1 << 30
            prev_img = img
            if d > D_THR:
                if cur_burst is None:
                    cur_burst = [f, f]
                else:
                    cur_burst[1] = f
                last_change = f
            elif cur_burst and f - cur_burst[1] > 25:
                events.append({"first_f": cur_burst[0], "last_f": cur_burst[1]})
                cur_burst = None
            if f % 500 == 0:
                rows.append((f, float(img.mean())))
                png(p, f, "mash")
        if cur_burst:
            events.append({"first_f": cur_burst[0], "last_f": cur_burst[1]})
        out["mash_events"] = events
        base = os.path.join(args.outdir, f"timeline_{args.name}.json")
        if os.path.exists(base):
            bl = json.load(open(base)).get("exact_transition_frames", [])
            out["baseline_events"] = bl
            out["events_delta_vs_baseline"] = {"new": [e["first_f"] for e in events
                                                       if not any(abs(e["first_f"] - b) < 120 for b in bl)],
                                               "missing": [b for b in bl
                                                           if not any(abs(e["first_f"] - b) < 120 for e in events)]}
        out["frozen_tail"] = last_change and (args.watch - last_change)
        out["luma_500s"] = rows
    else:
        # ---- battery mode ----
        # run to --at with no input
        f = 0
        prev_img = None
        while f < args.at:
            p.core.run(1, set())
            f += 1
            img = p.core.frame_rgb()
            if img is not None:
                prev_img = img
        png(p, args.at, "base")
        ck = f"{args.name}_batt_{args.at}"
        p.save_state(ck)
        base_ram = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()
        out["base_png"] = f"{args.name}_base_f{args.at:06d}.png"

        # control window
        ctrl, prev = [], base_ram
        vis = []
        for i in range(args.hold):
            p.core.run(1, set())
            prev, d = ram_motion(p, prev)
            ctrl.append(d)
            img = p.core.frame_rgb()
            if img is not None and prev_img is not None and prev_img.shape == img.shape:
                vis.append(int(np.abs(img.astype(np.int16) - prev_img.astype(np.int16)).sum()))
                prev_img = img
        amb_max = max(ctrl) if ctrl else 0
        thr = max(16, 3 * amb_max)
        out["control"] = {"ram_motion_head": ctrl[:24], "ambient_max": amb_max,
                          "threshold": thr, "visual_changed_frames": int(sum(1 for v in vis if v > D_THR))}

        ctrl_visual = out["control"]["visual_changed_frames"]
        results = {}
        for b in btns:
            p.load_state(ck)
            prev = base_ram
            first = None
            peak = 0
            vchange = 0
            head = []
            prev_img = None
            for i in range(1, args.hold + 1):
                p.core.run(1, {b})
                prev, d = ram_motion(p, prev)
                peak = max(peak, d)
                if len(head) < 12:
                    head.append(d)
                if first is None and d > thr:
                    first = i
                    png(p, args.at + i, f"resp_{b}")
                img = p.core.frame_rgb()
                if img is not None and prev_img is not None and prev_img.shape == img.shape:
                    if int(np.abs(img.astype(np.int16) - prev_img.astype(np.int16)).sum()) > D_THR:
                        vchange += 1
                    prev_img = img
            png(p, args.at + args.hold, f"end_{b}")
            results[b] = {"first_response_frame": first, "peak_motion": peak,
                          "ram_motion_head": head,
                          "visual_changed_frames": vchange,
                          "responds": bool(first is not None or
                                           vchange > 2 * ctrl_visual + 4)}
        out["results"] = results
        out["responsive_buttons"] = sorted(k for k, v in results.items() if v["responds"])
        firsts = [results[k]["first_response_frame"] for k in results
                  if results[k]["first_response_frame"]]
        out["verdict"] = ("INPUT_RESPONSE_AT_FRAME_+%d" % min(firsts) if firsts
                          else ("VISUAL_ONLY_RESPONSE" if out["responsive_buttons"]
                                else "ALL_INERT"))

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    path = os.path.join(args.outdir, f"inputscan_{args.name}_{tag}.json")
    with open(path, "w") as fp:
        json.dump(out, fp, indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
