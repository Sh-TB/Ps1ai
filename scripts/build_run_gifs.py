#!/usr/bin/env python3
"""build_run_gifs.py — assemble section + highlight GIFs from a
gif_run_capture frames directory (f%07d.jpg, stride-captured).

Outputs (outdir/gifs/):
  part1_start.gif   first W captured frames (run start / intro / village)
  part2_mid.gif     middle W captured frames
  part3_final.gif   last W captured frames (best progress)
  highlights.gif    windows around recorded events (kills, grenades,
                    deaths, restarts, stalls) merged in time order

All GIFs play at --fps (default 6 = real-time for stride 10 @60fps).
Palette is generated per GIF (palettegen stat_mode=diff) then applied.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile


def sh(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr[-600:]}")
    return r


def build_gif(frame_paths, out_path, fps, tmp):
    if len(frame_paths) < 4:
        print(f"  skip {out_path} (too few frames)")
        return None
    seq = os.path.join(tmp, "seq")
    shutil.rmtree(seq, ignore_errors=True)
    os.makedirs(seq)
    for i, src in enumerate(frame_paths):
        os.link(src, os.path.join(seq, f"s{i:06d}.jpg"))
    pal = os.path.join(tmp, "pal.png")
    sh(["ffmpeg", "-y", "-framerate", str(fps), "-i",
        os.path.join(seq, "s%06d.jpg"), "-vf",
        "palettegen=max_colors=200", pal])
    sh(["ffmpeg", "-y", "-framerate", str(fps), "-i",
        os.path.join(seq, "s%06d.jpg"), "-i", pal, "-lavfi",
        "paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle",
        "-loop", "0", out_path])
    shutil.rmtree(seq, ignore_errors=True)
    return out_path


def event_windows(hl_path, stride, half_game_frames=150,
                  kinds=None, max_total=1000):
    """Read highlights.jsonl -> merged ordered windows of captured
    frame numbers (g values)."""
    if not os.path.exists(hl_path):
        return []
    wins = []
    for line in open(hl_path):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if kinds and e.get("kind") not in kinds:
            continue
        g = e.get("gframe")
        if g is None:
            continue
        lo = max(0, (g - half_game_frames) // stride * stride)
        hi = g + half_game_frames
        wins.append((lo, hi, e.get("kind"), e.get("delta")))
    wins.sort()
    merged = []
    for lo, hi, kind, delta in wins:
        if merged and lo <= merged[-1][1]:
            m = merged[-1]
            merged[-1] = (m[0], max(m[1], hi),
                          f"{m[2]}+{kind}" if m[2] != kind else kind,
                          m[3])
        else:
            merged.append((lo, hi, kind, delta))
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True,
                    help="gif_run_capture output dir (has frames/)")
    ap.add_argument("--fps", type=int, default=6)
    ap.add_argument("--part-frames", type=int, default=900,
                    help="captured frames per section GIF")
    ap.add_argument("--stride", type=int, default=10)
    ap.add_argument("--max-hl", type=int, default=950)
    args = ap.parse_args()
    fdir = os.path.join(args.run_dir, "frames")
    gdir = os.path.join(args.run_dir, "gifs")
    os.makedirs(gdir, exist_ok=True)
    gs = sorted(int(os.path.basename(p)[1:8]) for p in
                glob.glob(os.path.join(fdir, "f*.jpg")))
    if not gs:
        sys.exit("no frames found")
    print(f"frames: {len(gs)}  range g{gs[0]}..g{gs[-1]}")
    gset = set(gs)
    out = {}
    tmp = tempfile.mkdtemp(prefix="gifbuild_")
    try:
        # ---- section GIFs ----
        w = args.part_frames
        sections = {
            "part1_start": gs[:w],
            "part2_mid": gs[len(gs) // 2 - w // 2: len(gs) // 2 + w // 2],
            "part3_final": gs[-w:],
        }
        for name, sel in sections.items():
            paths = [os.path.join(fdir, f"f{g:07d}.jpg") for g in sel
                     if g in gset]
            p = build_gif(paths, os.path.join(gdir, f"{name}.gif"),
                          args.fps, tmp)
            if p:
                out[name] = {"frames": len(sel),
                             "g_range": [sel[0], sel[-1]]}
            # size guard
            sz = os.path.getsize(p) // (1024 * 1024) if p else 0
            print(f"  {name}: {len(sel)} frames, {sz} MB")
        # ---- highlights GIF ----
        wins = event_windows(os.path.join(args.run_dir,
                                          "highlights.jsonl"),
                             args.stride)
        print(f"highlight windows: {len(wins)}")
        sel, total = [], 0
        for lo, hi, kind, delta in wins:
            g_l = [g for g in gs if lo <= g <= hi]
            if total + len(g_l) > args.max_hl:
                continue
            sel.extend(g_l)
            total += len(g_l)
            print(f"  win {kind} g{lo}..g{hi} (+{len(g_l)})")
        if sel:
            paths = [os.path.join(fdir, f"f{g:07d}.jpg") for g in sel]
            p = build_gif(paths, os.path.join(gdir, "highlights.gif"),
                          args.fps, tmp)
            sz = os.path.getsize(p) // (1024 * 1024) if p else 0
            print(f"  highlights: {len(sel)} frames, {sz} MB")
            out["highlights"] = {"frames": len(sel),
                                 "windows": [(w[2], w[0], w[1])
                                             for w in wins]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    with open(os.path.join(gdir, "gifs_manifest.json"), "w") as f:
        json.dump({"fps": args.fps, "stride": args.stride,
                   "gifs": out}, f, indent=1)
    print("manifest:", os.path.join(gdir, "gifs_manifest.json"))


if __name__ == "__main__":
    main()
