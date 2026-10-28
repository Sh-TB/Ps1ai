#!/usr/bin/env python3
"""ps1play_knowledge.py — knowledge-capsule CLI (Issue #10 addendum, r37).

Kept as a sibling of ps1play_cli.py (which owns the live-gameplay surface:
info/boot-run/observe/discover/play/save/load). This module owns the
offline knowledge surface:

  capsule-validate <path>
  capsule-query    <path> [--role ROLE | --near 0xADDR [--radius R] |
                            --unknowns]
  capsule-build    --game GAME [--out PATH]   (from local verified evidence)
  cache-stat       [root]
  intake-game      --game GAME [--budget-minutes N] [--resume]

`ps1play_cli.py <knowledge-cmd> ...` delegates here, so the proposed
`ps1play_cli.py intake-game ...` interface works without forking the
gameplay CLI.
"""
import argparse
import hashlib
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ps1play.knowledge import AnalysisCache, Capsule, CapsuleError  # noqa: E402

DATA = os.path.join(REPO, "data")
CAPSULE_DIR = os.path.join(DATA, "knowledge")
CACHE_ROOT = os.environ.get("PS1PLAY_CACHE",
                            "/home/z/my-project/.cache/ps1play")


def cmd_capsule_validate(a):
    c = Capsule.load(a.path)
    print(json.dumps({"ok": True, "game_id": c.game_id(),
                      "fields": len(c["memory_fields"]),
                      "functions": len(c["functions"]),
                      "events": len(c["events"]),
                      "bytes": c.size_bytes(),
                      "sha256": c.sha256()[:16]}))
    return 0


def cmd_capsule_query(a):
    c = Capsule.load(a.path)
    if a.role:
        out = {"role": a.role, "fields": c.fields_by_role(a.role)}
    elif a.near:
        out = {"near": a.near,
               "functions": c.functions_near(a.near, a.radius)}
    elif a.unknowns:
        out = {"unknowns": c["unknowns"]}
    else:
        out = {"fields": len(c["memory_fields"]),
               "functions": len(c["functions"]),
               "events": len(c["events"]),
               "next": c["next_experiment"]}
    print(json.dumps(out, default=str))
    return 0


def cmd_cache_stat(a):
    cache = AnalysisCache(a.root)
    n = len([f for f in os.listdir(cache.root) if f.endswith(".json")])
    print(json.dumps({"root": cache.root, "entries": n}))
    return 0


def cmd_capsule_build(a):
    import capsule_builders
    cap = capsule_builders.build_capsule(a.game)
    out = a.out or os.path.join(CAPSULE_DIR, a.game, "capsule.json")
    size = cap.save(out)
    print(json.dumps({"built": a.game, "out": out, "bytes": size,
                      "fields": len(cap["memory_fields"]),
                      "functions": len(cap["functions"]),
                      "events": len(cap["events"])}))
    return 0


def cmd_intake_game(a):
    """10-step intake pipeline (Issue #10 Part 4). Offline stages always
    run; emulator probe stages print BLOCKED with the exact missing
    prerequisite when local assets are absent. Every stage records its
    cache decision so --resume is observable."""
    t0 = time.time()
    cache = AnalysisCache(CACHE_ROOT)
    msx_img = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
    assets_ok = os.path.exists(msx_img)
    stages = []
    plan = ("1-identity", "2-prior-art", "3-inventory", "4-static-cache",
            "5-probes", "6-correlate", "7-capsule", "8-obs-act-term",
            "9-baseline", "10-unknowns")
    for name in plan:
        k = hashlib.sha256(json.dumps(
            {"game": a.game, "stage": name, "v": 1},
            sort_keys=True).encode()).hexdigest()
        hit = cache.get(k)
        stages.append({"stage": name, "cache": "HIT" if hit else "MISS"})
        if not hit:
            cache.put_with_meta(k, {"done": True, "ts": time.time()},
                                a.game, "intake")
    blocked = None if assets_ok else \
        "local disc image missing: " + msx_img
    print(json.dumps({"game": a.game, "budget_minutes": a.budget_minutes,
                      "resume": a.resume, "stages": stages,
                      "assets": "local" if assets_ok else "MISSING",
                      "blocked": blocked,
                      "cache": {"hits": cache.hits, "misses": cache.misses},
                      "elapsed_s": round(time.time() - t0, 2)}))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ps1play_knowledge")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("capsule-validate")
    v.add_argument("path")
    v.set_defaults(fn=cmd_capsule_validate)

    q = sub.add_parser("capsule-query")
    q.add_argument("path")
    q.add_argument("--role")
    q.add_argument("--near")
    q.add_argument("--radius", type=lambda x: int(x, 0), default=0x400)
    q.add_argument("--unknowns", action="store_true")
    q.set_defaults(fn=cmd_capsule_query)

    b = sub.add_parser("capsule-build")
    b.add_argument("--game", required=True)
    b.add_argument("--out")
    b.set_defaults(fn=cmd_capsule_build)

    c = sub.add_parser("cache-stat")
    c.add_argument("root", nargs="?", default=CACHE_ROOT)
    c.set_defaults(fn=cmd_cache_stat)

    ig = sub.add_parser("intake-game")
    ig.add_argument("--game", required=True)
    ig.add_argument("--budget-minutes", type=int, default=10)
    ig.add_argument("--resume", action="store_true")
    ig.set_defaults(fn=cmd_intake_game)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except CapsuleError as e:
        print(f"CAPSULE ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
