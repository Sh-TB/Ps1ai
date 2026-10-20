#!/usr/bin/env python3
"""gkb_query.py — Game Knowledge Base query helper (Issue #3 Phase H).

One CLI over the committed registries (data/games/<serial>/*.json) and,
when configured, the EXTERNAL workspace index (functions/xrefs/strings/
assets produced by game_rebuild_index.py / asset_catalog.py).

Queries:
  --grenade-logic        confirmed grenade logic + live anchor contract
  --projectile-candidates  candidate projectile/fire functions (status-aware)
  --asset-by-hash H      find an asset by image sha1 prefix (16 hex)
  --map-after N          map segments/landmarks beyond camera N
  --unverified           everything not VERIFIED (honesty worklist)
  --function-at VA       containing function + callers/callees
  --refs VA              code sites referencing a global address
  --string HINT          strings containing HINT (+ code refs)
  --timer                verified timer facts
  --stats                counts across all sources

Status policy: answers NEVER merge statuses. VERIFIED facts are
reported as such; everything else keeps OBSERVED/TESTED/HEURISTIC/
UNKNOWN/BLOCKED/PENDING with its evidence pointer.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(_REPO, "data", "games", "SLUS-01212")

WORKSPACE_CANDIDATES = [
    os.environ.get("MSX_RE_INDEX", ""),
    "/home/z/my-project/work/msx_recomp/index",
]


def load(path):
    p = os.path.join(DATA, path)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return None


def load_workspace():
    for d in WORKSPACE_CANDIDATES:
        if d and os.path.isdir(d):
            out = {}
            for name in ("re_index.json", "functions.json", "xrefs.json",
                         "strings.json"):
                p = os.path.join(d, name)
                if os.path.exists(p):
                    with open(p) as f:
                        out[name.split(".")[0]] = json.load(f)
            return out
    return {}


def assets_workspace():
    for d in ("/home/z/my-project/work/msx_recomp/assets",):
        p = os.path.join(d, "assets.json")
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    return None


def overlay_index():
    """Overlay index: workspace full index first, committed summary
    fallback. Both are module-tagged; regions never mix."""
    for d in WORKSPACE_CANDIDATES:
        p = os.path.join(d, "overlay_index.json")
        if os.path.exists(p):
            with open(p) as f:
                return json.load(f), "workspace"
    p = os.path.join(DATA, "overlay_index.json")
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f), "committed"
    return None, None


def _va(x):
    try:
        return int(x, 0)
    except (TypeError, ValueError):
        return None


def query_overlay(args):
    ov, src = overlay_index()
    if ov is None:
        print("overlay index not found (run scripts/overlay_index.py)")
        return
    print(f"== overlay index [{src}] config={ov.get('config_version')}")
    for name, m in sorted(ov["modules"].items()):
        if m.get("status") != "INDEXED":
            print(f"{name}: {m.get('status')}")
            continue
        mp = m["mapping"]
        print(f"{name}: {m['code_region_file_off'][0]}.."
              f"{m['code_region_file_off'][1]} -> "
              f"{mp['va_range'][0]}..{mp['va_range'][1]} "
              f"[{mp['rule']}] {m['counts']}")
    want = _va(args.overlay_function_at)
    if want is not None:
        for name, m in sorted(ov["modules"].items()):
            for f in m.get("functions") or []:
                if _va(f["va"]) <= want < _va(f["va"]) + f["size"]:
                    print(f"  {name} {f['va']} +{f['size']:#x} "
                          f"{f['name']} [{f['confidence']}] "
                          f"({','.join(f['evidence'])})")
    want = _va(args.overlay_refs)
    if want is not None:
        rad = args.radius
        for name, m in sorted(ov["modules"].items()):
            hits = [g for g in m.get("grefs") or []
                    if abs(_va(g["va"]) - want) <= rad]
            for g in hits[:24]:
                print(f"  {name} gref {g['va']} @ pc {g['pc']} "
                      f"{g['kind']} [{g['region']}]")
            callees = sorted({e["dst"] for e in m.get("edges") or []
                              if e["src"] and want <= int(e["src"], 16)
                              < want + 0x200})
            if callees:
                print(f"  {name} callees near: {callees[:10]}")


def status_of(e):
    return e.get("status") or e.get("confidence") or "UNKNOWN"


def print_ev(e, indent="  "):
    for ev in (e.get("evidence") or [])[:4]:
        print(f"{indent}- evidence: {ev}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--serial", default="SLUS-01212")
    g = ap.add_argument_group("queries")
    g.add_argument("--grenade-logic", action="store_true")
    g.add_argument("--projectile-candidates", action="store_true")
    g.add_argument("--asset-by-hash", default=None)
    g.add_argument("--map-after", type=int, default=None)
    g.add_argument("--unverified", action="store_true")
    g.add_argument("--function-at", default=None)
    g.add_argument("--refs", default=None)
    g.add_argument("--refs-near", default=None)
    g.add_argument("--radius", type=lambda x: int(x, 0), default=0x100)
    g.add_argument("--string", default=None)
    g.add_argument("--timer", action="store_true")
    g.add_argument("--overlay-function-at", default=None,
                   help="which overlay function contains this VA")
    g.add_argument("--overlay-refs", default=None,
                   help="overlay grefs/callees near this VA")
    g.add_argument("--overlay-stats", action="store_true")
    g.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    ent = load("entities.json") or {}
    mp = load("mission1_map.json") or {}
    ch = load("cheats.json") or {}
    ws = load_workspace()
    areg = assets_workspace()

    if args.overlay_stats or args.overlay_function_at or args.overlay_refs:
        query_overlay(args)
        if not (args.grenade_logic or args.projectile_candidates
                or args.map_after or args.unverified or args.function_at
                or args.refs or args.refs_near or args.string
                or args.timer or args.stats):
            return
        print()

    if args.grenade_logic:
        gi = ((ent.get("player") or {}).get("grenade_inventory") or {})
        gs = ((ent.get("player") or {}).get("grenade_store_instruction")
              or {})
        cb = (ch.get("cheats") or {}).get("bombs") or {}
        print("== grenade logic (status-separated) ==")
        print(f"[{status_of(gi)}] live inventory: "
              f"{gi.get('kind')} at {gi.get('runtime_addr_this_boot')} "
              f"(boot-dynamic; locate via PerceptionGuard strict series)")
        print_ev(gi)
        print(f"[{status_of(gs)}] exe store: {gs.get('instruction')} "
              f"@ {gs.get('va')} in {gs.get('containing_function')}")
        print(f"[{cb.get('status')}] registry cheat 'bombs': "
              f"{cb.get('codes')} — {cb.get('mechanism')}")
        print_ev(cb)
        return

    if args.projectile_candidates:
        print("== projectile/fire function candidates ==")
        # status-aware: only functions near verified weapon/fire sites,
        # marked as candidates (never 'enemy AI' by proximity alone)
        ammo = (ch.get("cheats") or {}).get("ammo") or {}
        print(f"[{ammo.get('status')}] published ammo site decode: "
              f"{(ent.get('player') or {}).get('published_cheat_sites_decode', {}).get('sites', {}).get('8002DCE6 2400 (ammo)')}")
        fns = (ws.get("functions") or {}).get("functions") or []
        near = [f for f in fns
                if f["va"].upper().startswith("0x8002DC") or
                f["va"].upper().startswith("0x800173")]
        for f in near[:6]:
            print(f"  [candidate/{f.get('confidence')}] {f['va']} "
                  f"size={f.get('size')} {f.get('name')}")
        print("  NOTE: no projectile update function is confirmed yet "
              "(see entities.json unresolved)")
        return

    if args.asset_by_hash:
        if not areg:
            print("assets registry not found (external workspace)")
            return
        h = args.asset_by_hash.lower()
        for a in areg.get("assets", []):
            if (a.get("image_sha1_16") or "").startswith(h):
                print(json.dumps(a, indent=1))
                return
        print("no asset with that hash prefix")
        return

    if args.map_after is not None:
        segs = [s for s in mp.get("segments", [])
                if (s.get("camera_range") or [0, 0])[0] > args.map_after
                or args.map_after < (s.get("camera_range") or [0, 0])[1]]
        for s in segs:
            print(f"[{s.get('status')}] {s['id']} {s.get('name')} "
                  f"camera={s.get('camera_range')}")
        for l in mp.get("landmarks", []):
            c = l.get("camera")
            if c is None or c > args.map_after:
                print(f"  [{l.get('status')}] {l['id']} {l['name']} "
                      f"@ camera {c}")
        return

    if args.unverified:
        print("== worklist: every fact NOT VERIFIED ==")
        def walk(node, path):
            if isinstance(node, dict):
                st = node.get("status")
                if st and st != "VERIFIED":
                    print(f"[{st}] {path}")
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")
        walk(ent, "entities")
        walk(mp, "mission1_map")
        walk(ch, "cheats")
        return

    if args.timer:
        t = ent.get("mission_timer") or {}
        print(json.dumps(t, indent=1))
        return

    if args.stats:
        fns = (ws.get("functions") or {}).get("functions") or []
        xr = ws.get("xrefs") or {}
        counts = {
            "entities_top_level": len(ent),
            "map_segments": len(mp.get("segments", [])),
            "map_landmarks": len(mp.get("landmarks", [])),
            "cheats_registered": len(ch.get("cheats", {})),
            "functions_indexed": len(fns),
            "call_edges": len(xr.get("call_edges", [])),
            "global_ref_targets": len(xr.get("global_refs", {})),
            "strings": (ws.get("strings") or {}).get("count"),
            "assets_extracted": ((areg or {}).get("counts") or {})
                .get("tim_assets"),
        }
        print(json.dumps(counts, indent=1))
        return

    if args.function_at or args.refs or args.refs_near or args.string:
        sys.path.insert(0, os.path.join(_REPO, "scripts"))
        import re_lookup
        idx_dir = None
        for d in WORKSPACE_CANDIDATES:
            if d and os.path.isdir(d):
                idx_dir = d
                break
        if not idx_dir:
            print("external index not found — run "
                  "scripts/game_rebuild_index.py first")
            return
        exe = os.path.join(os.path.dirname(idx_dir), "SLUS_012.12.full")
        argv = ["--index", idx_dir]
        if args.function_at:
            argv += ["--function-at", args.function_at]
        if args.refs:
            argv += ["--refs", args.refs]
        if args.refs_near:
            argv += ["--refs-near", args.refs_near,
                     "--radius", str(args.radius)]
        if args.string:
            argv += ["--string", args.string]
        if os.path.exists(exe):
            argv += ["--exe", exe]
        re_lookup.main(argv)
        return

    ap.print_help()


if __name__ == "__main__":
    main()
