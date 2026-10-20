#!/usr/bin/env python3
"""live_crosscheck.py — bounded live session that closes the loop between
the static index and runtime state (Issue #3 Phase F/G validation).

Checks (all observational, no writes, no cheats):
  1. grenade inventory: PerceptionGuard strict-series anchor -> live
     counter address C this boot; compare with the static struct
     hypothesis [0x800C9A98] + 0xB6  (root pointer slot from static RE)
  2. root pointer lifetime: sample [0x800C9A98] at mission entry, after
     the drop-in, and after grenade presses
  3. VRAM view semantics: save the exposed VRAM window as a PNG and run
     the TIM sliding search over ALL extracted assets

Evidence: entity_probe.jsonl-style rows + PNGs in the evidence dir.
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
from ps1play.agent.perception import PerceptionGuard      # noqa: E402
from mission import ensure_mission                        # noqa: E402

PLAYER_PTR = 0x800C9A98
RAM_MASK = 0x1FFFFF


def log(*a):
    print("[xcheck]", *a, flush=True)


def ram_u32(core, va):
    a = va & RAM_MASK
    r = core.ram
    return int(r[a] | (r[a + 1] << 8) | (r[a + 2] << 16) | (r[a + 3] << 24))


def vram_png(core, path):
    from PIL import Image
    v = core.vram
    if v is None:
        return False
    hw = np.frombuffer(v[:len(v) // 2 * 2].tobytes(), dtype="<u2")
    w = 1024
    h = max(1, len(hw) // w)
    rgb = np.zeros((h, w, 3), dtype=np.uint8)
    r5 = (hw & 0x1F).astype(np.uint8) << 3
    g5 = ((hw >> 5) & 0x1F).astype(np.uint8) << 3
    b5 = ((hw >> 10) & 0x1F).astype(np.uint8) << 3
    rgb[:, :, 0] = r5.reshape(h, w)
    rgb[:, :, 1] = g5.reshape(h, w)
    rgb[:, :, 2] = b5.reshape(h, w)
    Image.fromarray(rgb).save(path)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--assets", default="/home/z/my-project/work/"
                                        "msx_recomp/assets/assets.json")
    ap.add_argument("--evidence-dir", default=None)
    ap.add_argument("--game", default=labconfig.resolve_path("game"))
    ap.add_argument("--core", default=labconfig.resolve_path("core"))
    ap.add_argument("--workspace", default=labconfig.resolve_path(
        "workspace"))
    ap.add_argument("--firmware", default=os.environ.get(
        "M1_FIRMWARE", "openbios"))
    args = ap.parse_args()

    evid = args.evidence_dir or "/home/z/my-project/work/msx_recomp/" \
                                "evidence/crosscheck"
    os.makedirs(evid, exist_ok=True)
    fw = labconfig.resolve_firmware(args.firmware, args.workspace)
    kw = {}
    if args.core:
        kw["core"] = args.core
    if args.workspace:
        kw["workspace"] = args.workspace
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]
    p = PS1Play(args.game, **kw)
    p.boot()
    fw_ev = labconfig.firmware_log_evidence(
        getattr(p.core, "log_history", []))
    ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
    if not ok:
        sys.exit(f"!! firmware trust failed: {detail}")
    core = p.core
    rows = []

    # ---- VRAM at the title (before gameplay) -----------------------
    core.run(4700)
    vram_png(core, os.path.join(evid, "vram_title.png"))
    hit_title = try_assets(core, args.assets)
    rows.append({"kind": "vram_title", "hits": hit_title[:12],
                 "n_hits": len(hit_title)})
    log(f"title VRAM asset hits: {len(hit_title)}")
    for h in hit_title[:6]:
        log("   ", h)

    r = p.enter_gameplay3()
    log("enter:", r.get("in_game"))
    m = ensure_mission(p, tries=6, log=log)
    if not m.get("in_mission"):
        sys.exit("!! gate failed")

    # ---- root pointer lifetime --------------------------------------
    ptr_series = []
    for tag, extra in (("entry", 0), ("settled", 200), ("run10s", 600)):
        core.run(extra)
        ptr_series.append({"tag": tag, "frame": core.frames_run,
                           "ptr": f"0x{ram_u32(core, PLAYER_PTR):08X}"})
    log("root ptr series:", ptr_series)

    # ---- grenade anchor (strict series) ------------------------------
    guard = PerceptionGuard(p)
    anch = guard.anchor(log=log)
    caddr = (guard.addrs or {}).get("bombs")
    log("bombs anchor:", anch.get("ok"), hex(caddr) if caddr else None)
    ptr_now = ram_u32(core, PLAYER_PTR)
    rel = None
    if caddr and ptr_now:
        rel = caddr - (ptr_now & RAM_MASK)
    rows.append({
        "kind": "grenade_struct_crosscheck",
        "root_slot_ptr": f"0x{ptr_now:08X}",
        "live_counter": hex(caddr) if caddr else None,
        "counter_minus_0xB6": hex(rel) if rel is not None else None,
        "struct_hypothesis_confirmed":
            rel == 0xB6 if rel is not None else False,
        "ptr_series": ptr_series,
    })
    log(f"crosscheck: ptr=0x{ptr_now:08X} counter={hex(caddr) if caddr else '?'} "
        f"counter-0xB6={hex(rel) if rel is not None else '?'} "
        f"confirmed={rel == 0xB6 if rel is not None else False}")

    # grenade series on the live counter (validate again in-session)
    if caddr:
        ser = []
        for i in range(3):
            ser.append((core.frames_run, int(core.ram[caddr])))
            core.run(10, "A")
            ser.append((core.frames_run, int(core.ram[caddr])))
            core.run(70)
        rows.append({"kind": "grenade_series_live", "addr": hex(caddr),
                     "series": ser})
        log("live grenade series:", ser)

    # ---- mission VRAM -------------------------------------------------
    vram_png(core, os.path.join(evid, "vram_mission.png"))
    hit_mission = try_assets(core, args.assets)
    rows.append({"kind": "vram_mission", "hits": hit_mission[:12],
                 "n_hits": len(hit_mission)})
    log(f"mission VRAM asset hits: {len(hit_mission)}")
    for h in hit_mission[:6]:
        log("   ", h)

    with open(os.path.join(evid, "crosscheck.jsonl"), "w") as f:
        for r2 in rows:
            f.write(json.dumps(r2) + "\n")
    log("done ->", evid)


def try_assets(core, assets_path, min_probe=64):
    """Sliding search of every extracted TIM body in the VRAM window."""
    v = core.vram
    if v is None:
        return []
    sys.path.insert(0, _REPO)
    with open(assets_path) as f:
        reg = json.load(f)
    from game_rebuild_index import DiscImage, parse_pvd, walk_disc
    disc = DiscImage(labconfig.resolve_path("game"))
    pvd = parse_pvd(disc)
    files, _ = walk_disc(disc, pvd)
    lbamap = {f["path"].split("/")[-1].upper().replace(";1", ""):
              f["lba"] for f in files}
    cache = {}
    hits = []
    vbytes = v.tobytes()
    for a in reg["assets"]:
        fn = a["source_file"].split("/")[-1].upper()
        if fn not in lbamap:
            continue
        if fn not in cache:
            cache[fn] = disc.read_user_range(lbamap[fn], 4_000_000)
        data = cache[fn]
        i = a["abs_off"]
        flag = a["flag"]
        mode = flag & 0xF
        q = i + 8
        try:
            if mode in (0, 1, 8, 9):
                clut_len = int.from_bytes(data[q:q + 4], "little")
                q += clut_len
            img_len = int.from_bytes(data[q:q + 4], "little")
            body = data[q + 12:q + img_len]
        except Exception:
            continue
        if len(body) < min_probe:
            continue
        probe = body[:256]
        at = vbytes.find(bytes(probe))
        if at < 0 or at + len(body) > len(vbytes):
            continue
        region = v[at:at + len(body)]
        eq = float((region == np.frombuffer(
            body, dtype=np.uint8)).mean())
        if eq >= 0.98:
            hits.append({"asset_id": a["asset_id"], "match": round(eq, 4),
                         "bytes": len(body), "at": at})
    hits.sort(key=lambda h: (-h["bytes"], -h["match"]))
    return hits


if __name__ == "__main__":
    main()
