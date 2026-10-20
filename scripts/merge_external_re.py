#!/usr/bin/env python3
"""merge_external_re.py — Consolidate third-party same-game analysis metadata into the KB
(Issue #5 P1-8/P1-9, deliverable D-2).

Merges metadata-only artifacts from the two Metal-Slug-X-Recomp projects that target the
exact user disc (MD5 37d9e1179a32661800e74858009a4f8b — verified against our disc.json):

  external_audit/msx_tc/analysis/{edges,refs,indirect}.json + widescreen_sites.toml
  external_audit/msx_alexbeavs/ seeds (function list)

Output: data/games/SLUS-01212/psxrecomp_external.json — cross-validation source for our own
re_index.json (disassembler-independent evidence). Metadata ONLY: addresses, sizes, kinds.
No game bytes, no copyrighted asset content, no generated C from the upstream repos.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tomllib
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(_REPO, "data", "games", "SLUS-01212", "psxrecomp_external.json")


def jload(path):
    with open(path, "rb") as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge third-party MSX recomp analysis metadata (facts only).")
    ap.add_argument("--msx-tc", default="/home/z/my-project/external_audit/msx_tc")
    ap.add_argument("--msx-alexbeavs", default="/home/z/my-project/external_audit/msx_alexbeavs")
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    out = {
        "schema": "ps1play-psxrecomp-external/1",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "purpose": "disassembler-independent cross-validation for re_index.json (Issue #5 P1-8)",
        "sources": [],
        "counts": {},
    }
    sections: dict[str, list] = {}

    tc = args.msx_tc
    if os.path.isdir(tc):
        commit = ""
        try:
            commit = os.popen(f"git -C {tc} rev-parse --short HEAD").read().strip()
        except Exception:
            pass
        out["sources"].append({"repo": "TechnicallyComputers/Metal-Slug-X-Recomp", "commit": commit,
                               "scope": "same disc (MD5 37d9e117…); metadata only"})
        for name, key in (("analysis/edges.json", "edges"), ("analysis/refs.json", "refs"),
                          ("analysis/indirect.json", "indirect_sites")):
            p = os.path.join(tc, name)
            if os.path.exists(p):
                d = jload(p)
                rows = d.get("edges") or d.get("refs") or d.get("sites") or []
                for r in rows:
                    r["src"] = "msx_tc"
                sections[key] = rows
        ws = os.path.join(tc, "analysis/widescreen_sites.toml")
        if os.path.exists(ws):
            w = tomllib.load(open(ws, "rb"))
            block = w.get("widescreen") or {}
            # accept both flat ([widescreen] bias_sites=…) and nested ([widescreen.cull]) layouts
            subs = [block] + [v for v in block.values() if isinstance(v, dict)]
            sites = []
            for sub in subs:
                imms = sub.get("screen_w_imms", []) or block.get("screen_w_imms", [])
                sites += [{"kind": "bias_site", "va": v, "src": "msx_tc",
                           "screen_w_imms": sub.get("screen_w_imms", imms),
                           "screen_h_imms": sub.get("screen_h_imms", block.get("screen_h_imms", []))}
                          for v in sub.get("bias_sites", [])]
                sites += [{"kind": "range_site", "va": v, "src": "msx_tc"}
                          for v in sub.get("range_sites", [])]
            sections["widescreen_sites"] = sites

    ab = args.msx_alexbeavs
    if os.path.isdir(ab):
        commit = ""
        try:
            commit = os.popen(f"git -C {ab} rev-parse --short HEAD").read().strip()
        except Exception:
            pass
        out["sources"].append({"repo": "alexbeavs-ps1-ports/metal-slug-x-recomp", "commit": commit,
                               "scope": "same disc (MD5 37d9e117…); seed list only"})
        for cand in ("seeds/ghidra_funcs.txt", "ghidra_funcs.txt"):
            p = os.path.join(ab, cand)
            if os.path.exists(p):
                seeds = []
                for ln in open(p, encoding="utf-8", errors="replace"):
                    ln = ln.strip()
                    if ln.startswith("0x") or ln.startswith("func_"):
                        tok = ln.split()[0].replace("func_", "")
                        try:
                            seeds.append({"va": f"0x{int(tok, 16):08X}", "src": "msx_alexbeavs"})
                        except ValueError:
                            continue
                sections["alexbeavs_seeds"] = seeds
                break

    out["counts"] = {k: len(v) for k, v in sections.items()}
    out.update(sections)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"merge_external_re: {out['counts']} -> {args.out}")
    for s in out["sources"]:
        print("  source:", s["repo"], s.get("commit", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
