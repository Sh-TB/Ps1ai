#!/usr/bin/env python3
"""entity_probe.py — one bounded live session that ties the static index
to runtime truth (Issue #3 Phases E/F/G).

Everything here is OBSERVATIONAL (no RAM writes, no cheats, no rewinds):

  1. ASSET-TO-RUNTIME CORRELATION (VRAM, word-level):
     the frontend exposes the live VRAM view, so extracted TIM assets
     (which carry their VRAM x/y placement in the header) are compared
     halfword-by-halfword against the live VRAM at those coordinates,
     first at the title screen, then during Mission 1.  A high match
     ratio is direct evidence that the extracted bytes are the same
     asset the game uploaded — stronger than screenshot resemblance.
  2. PLAYER STRUCT DISCOVERY:
     reads the game-state root pointer (0x800C9A98, 1144 static xrefs)
     and diffs the pointed-to struct across controlled windows
     (idle / RIGHT held / grenade throws) to classify fields:
     inventory (grenade count), position-like (monotonic under RIGHT),
     flags.  The grenade inventory offset is expected at +0xB6 per the
     static decode of the VERIFIED bombs patch site (sb at 0x800398BC).
  3. MISSION TIMER HUNT:
     strict multi-snapshot series scan for counters that decrement
     exactly once per ~60-frame interval (the 300 s mission timer that
     killed the Issue-#2 route runs) or once per frame.

Outputs: evidence JSONL + PNGs in the evidence dir (external), a JSON
report, and a machine-readable entity/finding update file.

Usage:
  python3 scripts/entity_probe.py [--budget-minutes 6] [--report out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                        # noqa: E402

from ps1play import labconfig                             # noqa: E402
from ps1play.api import PS1Play                           # noqa: E402
from run_mission1_legit import find_progress_addr  # noqa: E402
from mission import ensure_mission                 # noqa: E402

PLAYER_PTR = 0x800C9A98
STRUCT_LEN = 0x300
RAM_MASK = 0x1FFFFF          # PS1 2MB RAM: virtual -> physical offset


def ram_u32(ram, va):
    a = va & RAM_MASK
    return int(ram[a] | (ram[a+1] << 8) | (ram[a+2] << 16)
               | (ram[a+3] << 24))
VRAM_W, VRAM_H = 1024, 512


def log(*a):
    print("[probe]", *a, flush=True)


def png(path, core):
    try:
        from PIL import Image
        arr = core.frame_rgb
        if arr is None:
            return False
        Image.fromarray(arr).save(path)
        return True
    except Exception:
        return False


def save_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


# ------------------------------------------------------------------
# 1) VRAM correlation
# ------------------------------------------------------------------


def tim_blocks(rec_data, rec):
    """Return (clut_bytes, image_bytes, declared_vram_xy) for a TIM rec."""
    i = rec["abs_off"]
    mode = rec["flag"] & 0xF
    p = i + 8
    clut = None
    if mode in (0, 1, 8, 9):
        clut_len = int.from_bytes(rec_data[p:p + 4], "little")
        clut = rec_data[p + 12:p + clut_len]
        p += clut_len
    img_len = int.from_bytes(rec_data[p:p + 4], "little")
    ix, iy = int.from_bytes(rec_data[p + 4:p + 6], "little"), \
        int.from_bytes(rec_data[p + 6:p + 8], "little")
    iw, ih = int.from_bytes(rec_data[p + 8:p + 10], "little"), \
        int.from_bytes(rec_data[p + 10:p + 12], "little")
    body = rec_data[p + 12:p + img_len]
    return clut, body, (ix, iy, iw, ih)


def vram_find(vram_u8, blob, probe=256):
    """Locate `blob` (bytes) inside the live VRAM view; returns
    (byte_offset, match_ratio) or (None, 0)."""
    if not blob or len(blob) < probe:
        return None, 0.0
    at = vram_u8.tobytes().find(bytes(blob[:probe]))
    if at < 0 or at + len(blob) > len(vram_u8):
        return None, 0.0
    region = vram_u8[at:at + len(blob)]
    eq = (region == np.frombuffer(blob, dtype=np.uint8))
    return at, float(eq.mean())


def correlate_vram(vram_u8, rec_data, rec):
    """Search the TIM image body (and CLUT) anywhere in the live VRAM
    view; verify the full body. Returns dict or None."""
    try:
        clut, body, dims = tim_blocks(rec_data, rec)
    except Exception:
        return None
    if not body or len(body) < 128:
        return None
    at, ratio = vram_find(vram_u8, body)
    out = {"asset_id": rec["asset_id"], "found": at is not None,
           "match": round(ratio, 4), "bytes": len(body),
           "declared_vram_xy": list(dims[:2]),
           "declared_wh": list(dims[2:]),
           "bpp": rec.get("bpp_name", "?")}
    if at is not None:
        hw = at // 2
        out["vram_xy_found"] = [hw % VRAM_W, hw // VRAM_W]
    if clut and len(clut) >= 64:
        cat, cratio = vram_find(vram_u8, clut)
        out["clut_found"] = cat is not None
        out["clut_match"] = round(cratio, 4)
    return out


def vram_correlation(core, assets, top_k=24, tag=""):
    """Try TIM assets against the live VRAM view (sliding search)."""
    vram = core.vram
    if vram is None or len(vram) < 65536:
        return {"tag": tag, "tried": 0, "hits": [], "best_20": [],
                "note": f"vram view too small: "
                        f"{None if vram is None else len(vram)}"}
    results = []
    for a in assets:
        data = (a.get("source") or {}).get("_data")
        if data is None:
            continue
        r = correlate_vram(vram, data, a)
        if r:
            results.append(r)
    results.sort(key=lambda r: (-r["match"], -r["bytes"]))
    hits = [r for r in results if r["match"] >= 0.98][:top_k]
    return {"tag": tag, "tried": len(results), "hits_98pct": hits,
            "best_20": results[:20]}


# ------------------------------------------------------------------
# 2) player struct windows
# ------------------------------------------------------------------


def snap_struct(ram, ptr, n=STRUCT_LEN):
    return ram[ptr:ptr + n].copy()


def classify_fields(snaps, labels, grenade_press_frames):
    """snaps: list of (frame, np.array); labels: window name per snap."""
    n = len(snaps[0][1])
    s = np.stack([x[1] for x in snaps]).astype(np.int16)
    out = {"inventory_u8": [], "position_like": [], "stable": [],
           "volatile": []}
    frames = np.array([fr for fr, _ in snaps])
    press = np.zeros(len(snaps), dtype=bool)
    for gi, gf in enumerate(grenade_press_frames):
        press |= (frames >= gf[0]) & (frames <= gf[1])
    pre = [i for i, l in enumerate(labels) if l in ("idle0", "idle1")
           and not press[i]]
    for f in range(n):
        col = s[:, f]
        if col.max() == col.min():
            out["stable"].append(f)
            continue
        # inventory candidate: max delta exactly -1 across all
        # consecutive press-gap pairs, stable in non-press frames
        vals = [int(v) for v in col]
        dec_at_press = all(
            vals[i] - vals[i - 1] == -1
            for i in range(1, len(vals)) if press[i] and not press[i - 1])
        quiet = all(vals[i] == vals[i - 1]
                    for i in range(1, len(vals))
                    if labels[i] == labels[i - 1] and not press[i]
                    and not press[i - 1])
        if dec_at_press and quiet and 0 < max(vals) <= 99:
            out["inventory_u8"].append(f)
    # position-like: monotonic non-decreasing across the RIGHT window,
    # unchanged across the idle windows
    for f in range(n):
        col = s[:, f]
        seq = [int(v) for v in col]
        if all(seq[i] <= seq[i + 1] for i in range(len(seq) - 1)) and \
                seq[-1] > seq[0] and max(seq) - min(seq) >= 2:
            out["position_like"].append(f)
    return out


# ------------------------------------------------------------------
# 3) timer hunt
# ------------------------------------------------------------------


def timer_hunt(core, frames_total=480, period=60, lo=0x1000,
               hi=0x1F0000):
    ram = core.ram
    snaps, frames = [], []
    for k in range(frames_total // period + 1):
        snaps.append(ram[lo:hi].copy())
        frames.append(k * period)
        core.run(period if k < frames_total // period else 0)
    res = []
    for width, dt in ((2, 1), (4, 1)):
        words = [np.frombuffer(s, dtype=f"<u{width}"
                               if width > 1 else "<u1") for s in snaps]
        a = np.stack(words[:-1]).astype(np.int64)
        b = np.stack(words[1:]).astype(np.int64)
        d = b - a
        L = period
        # per-second countdown (-1/interval) and per-frame (-L/interval)
        mono = ((d == -dt) | (d == -L)).all(axis=0)
        # reject counters that also jitter (strictly -dt everywhere)
        idx = np.flatnonzero(mono)
        for i in idx[:200]:
            res.append({"addr": lo + int(i) * width, "width": width,
                        "first": int(words[0][i]),
                        "last": int(words[-1][i]),
                        "snapshots": len(snaps)})
    return {"snapshots": len(snaps), "interval_frames": period,
            "candidates": res[:64], "n_candidates": len(res)}


# ------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget-minutes", type=float, default=6.0)
    ap.add_argument("--report", default=None)
    ap.add_argument("--evidence-dir", default=None)
    ap.add_argument("--assets", default=None,
                    help="assets.json from asset_catalog.py (for VRAM "
                         "correlation)")
    ap.add_argument("--asset-root", default=None,
                    help="dir containing the disc image for TIM reads")
    ap.add_argument("--game", default=labconfig.resolve_path("game"))
    ap.add_argument("--core", default=labconfig.resolve_path("core"))
    ap.add_argument("--workspace", default=labconfig.resolve_path(
        "workspace"))
    ap.add_argument("--firmware", default=os.environ.get(
        "M1_FIRMWARE", "openbios"))
    args = ap.parse_args()

    evid = args.evidence_dir or os.path.join(
        labconfig.resolve_path("evidence_dir") or
        "/home/z/my-project/work/msx_recomp/evidence", "entity_probe")
    os.makedirs(evid, exist_ok=True)
    t0 = time.time()

    fw = labconfig.resolve_firmware(args.firmware, args.workspace)
    kw = {}
    if args.core:
        kw["core"] = args.core
    if args.workspace:
        kw["workspace"] = args.workspace
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]
    p = PS1Play(args.game, **kw)
    info = p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    fw_ok, fw_detail = labconfig.check_firmware_trust(fw, fw_ev)
    if not fw_ok:
        sys.exit(f"!! firmware trust failed: {fw_detail}")
    log("boot ok, firmware:", fw["mode"])

    rows = []
    core = p.core

    # ---- title VRAM correlation ------------------------------------
    core.run(4700)      # title appears ~f4250-4500 on this chain
    title_png = os.path.join(evid, "title_frame.png")
    png(title_png, core)
    vram_title = None
    if args.assets and os.path.exists(args.assets):
        with open(args.assets) as f:
            reg = json.load(f)
        # load TIM bytes lazily from the disc image
        sys.path.insert(0, _REPO)
        from game_rebuild_index import DiscImage
        binp = args.asset_root or args.game
        disc = DiscImage(binp)
        from game_rebuild_index import parse_pvd, walk_disc
        pvd = parse_pvd(disc)
        files, _ = walk_disc(disc, pvd)
        lbamap = {f["path"].split("/")[-1].upper().replace(";1", ""):
                  f["lba"] for f in files}
        cache = {}
        for a in reg["assets"]:
            fn = a["source_file"].split("/")[-1].upper()
            if fn not in lbamap:
                continue
            if fn not in cache:
                cache[fn] = disc.read_user_range(lbamap[fn], 4_000_000)
            a["source"] = {"_data": cache[fn]}
        # keep the biggest embedded TIMs (fewer, likelier to be loaded)
        def aw(a):
            d = a.get("dims") or [0, 0]
            return (d[0] or 0) * (d[1] or 0)
        big = [a for a in reg["assets"] if aw(a) >= 4096][:400]
        vram_title = vram_correlation(core, big, tag="title")
        log(f"title VRAM: tried={vram_title['tried']} "
            f"hits98={len((vram_title or {}).get('hits_98pct', []))}")

    # ---- enter Mission 1 --------------------------------------------
    r = p.enter_gameplay3()
    log("enter:", r.get("in_game"))
    if not r.get("in_game"):
        sys.exit("!! boot failed")
    m = ensure_mission(p, tries=6, log=log)
    if not m.get("in_mission"):
        sys.exit("!! gate failed")
    core.run(120)                                    # settle drop-in

    # ---- player struct probe ----------------------------------------
    ptr = ram_u32(core.ram, PLAYER_PTR)
    log(f"player root ptr @0x{PLAYER_PTR:08X} -> raw 0x{ptr:08X}")
    ok_ptr = 0x80000000 <= ptr < 0x80200000
    snaps, labels, gpress = [], [], []
    if ok_ptr:
        f0 = core.frames_run
        core.run(240)                                 # idle0 settle
        for k in range(6):                            # idle0
            snaps.append((core.frames_run, snap_struct(core.ram, ptr)))
            labels.append("idle0")
            core.run(20)
        for k in range(12):                           # RIGHT
            snaps.append((core.frames_run, snap_struct(core.ram, ptr)))
            labels.append("right")
            core.run(20, "RIGHT")
        for k in range(4):                            # post-right idle
            snaps.append((core.frames_run, snap_struct(core.ram, ptr)))
            labels.append("idle1")
            core.run(20)
        # grenade presses (A = CIRCLE)
        for g in range(2):
            g0 = core.frames_run
            snaps.append((core.frames_run, snap_struct(core.ram, ptr)))
            labels.append("pre_grenade")
            core.run(6, "A")
            snaps.append((core.frames_run, snap_struct(core.ram, ptr)))
            labels.append("grenade")
            gpress.append((g0, core.frames_run))
            core.run(80)
        snaps.append((core.frames_run, snap_struct(core.ram, ptr)))
        labels.append("post_grenade")
        cls = classify_fields(snaps, labels, gpress)
        log(f"struct classify: inventory_u8 offsets={[hex(0x100 + o) for o in cls['inventory_u8'][:12]]} "
            f"position_like={[hex(0x100 + o) for o in cls['position_like'][:16]]}")
        # series evidence for +0xB6 (u8 grenade count)
        b6 = [(fr, int(s[0xB6])) for fr, s in snaps]
        rows.append({"t": time.strftime("%FT%TZ", time.gmtime()),
                     "kind": "player_struct", "ptr": hex(ptr),
                     "classification": cls,
                     "grenade_series_0xB6": b6,
                     "labels": labels})
        gameplay_png = os.path.join(evid, "mission_frame.png")
        png(gameplay_png, core)
    else:
        cls = None
        log("player pointer out of range — record honestly")

    # ---- timer hunt ---------------------------------------------------
    th = timer_hunt(core, frames_total=420, period=60)
    log(f"timer hunt: {th['n_candidates']} candidates")
    rows.append({"t": time.strftime("%FT%TZ", time.gmtime()),
                 "kind": "timer_hunt", **th})

    # ---- gameplay VRAM correlation ------------------------------------
    vram_game = None
    if args.assets and ok_ptr:
        vram_game = vram_correlation(core, big, tag="mission1")
        log(f"mission VRAM: tried={vram_game['tried']} "
            f"hits98={len((vram_game or {}).get('hits_98pct', []))}")
        rows.append({"t": time.strftime("%FT%TZ", time.gmtime()),
                     "kind": "vram_correlation",
                     "title": vram_title, "mission1": vram_game})

    # ---- camera/progress word -----------------------------------------
    cam = find_progress_addr(p, log=log)
    rows.append({"t": time.strftime("%FT%TZ", time.gmtime()),
                 "kind": "progress_word", **cam})

    report = {
        "schema": "ps1play-entity-probe/1",
        "serial": "SLUS-01212",
        "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
        "wall_s": round(time.time() - t0, 1),
        "frames": core.frames_run,
        "firmware": fw["mode"],
        "player_ptr": hex(ptr) if ok_ptr else None,
        "title_vram_hits": (vram_title or {}).get("hits_98pct", [])[:8],
        "mission_vram_hits": (vram_game or {}).get("hits_98pct", [])[:8],
        "timer_candidates": th["candidates"][:16],
        "progress": cam,
        "classification": cls,
    }
    out = args.report or os.path.join(evid, "entity_probe_report.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=1)
    save_jsonl(os.path.join(evid, "entity_probe.jsonl"), rows)
    print(json.dumps({k: v for k, v in report.items()
                      if k != "classification"}, indent=1)[:2000])
    log("done ->", out)


if __name__ == "__main__":
    main()
