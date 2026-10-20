#!/usr/bin/env python3
"""re_lookup.py — query/lookup helper over the RE index (Issue #3 Phase F/H).

Loads the workspace index produced by game_rebuild_index.py and answers
targeted questions WITHOUT any GUI disassembler:

  --function-at VA    containing function + record
  --disasm VA [N]     disassembly window around VA (annotated)
  --callers VA        who calls/jumps to the containing function
  --callees VA        what the containing function calls
  --refs VA           code sites referencing global address VA
  --refs-near VA R    refs within +/- R of VA (bucketed view)
  --string HINT       find strings containing HINT + referencing sites
  --annotate OUT      write annotated .asm files for a list of VAs

Examples:
  python3 scripts/re_lookup.py --index <dir> --function-at 0x800398BC
  python3 scripts/re_lookup.py --index <dir> --disasm 0x800398BC --after 0x40
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import struct
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)


def load_index(index_dir):
    data = {}
    for name in ("re_index.json", "functions.json", "xrefs.json"):
        p = os.path.join(index_dir, name)
        if os.path.exists(p):
            with open(p) as f:
                data[name.split(".")[0]] = json.load(f)
    return data


def load_text(index_dir, exe_path=None):
    """text bytes mapped at va0 (from exe_identity + the game image)."""
    p = os.path.join(index_dir, "exe_identity.json")
    if not os.path.exists(p):
        return None, None
    with open(p) as f:
        ident = json.load(f)
    va0 = int(ident["header"]["t_addr"])
    text = None
    if exe_path and os.path.exists(exe_path):
        with open(exe_path, "rb") as f:
            raw = f.read()
        if raw[:8] == b"PS-X EXE" and len(raw) >= ident["header"]["t_size"]:
            text = raw[0x800:0x800 + ident["header"]["t_size"]]
    return text, va0


def function_at(functions, va):
    vas = [int(f["va"], 16) for f in functions]
    order = sorted(range(len(vas)), key=lambda i: vas[i])
    svas = [vas[i] for i in order]
    i = bisect.bisect_right(svas, va) - 1
    if i < 0:
        return None
    f = functions[order[i]]
    a = int(f["va"], 16)
    if a <= va < a + max(f.get("size") or 0, 4):
        return f
    return None


def edges_for(xrefs, va, fn=None):
    """Callers/callees of a function; when a function record is given,
    edges are matched by RANGE (src/dst anywhere inside the body)."""
    if fn:
        a = int(fn["va"], 16)
        b = a + max(fn.get("size") or 0, 4)
        callers = [e for e in xrefs.get("call_edges", [])
                   if a <= e["dst"] < b]
        callees = [e for e in xrefs.get("call_edges", [])
                   if a <= e["src"] < b]
        return callers, callees
    callers = [e for e in xrefs.get("call_edges", [])
               if e["dst"] == va]
    callees = [e for e in xrefs.get("call_edges", [])
               if e["src"] == va]
    return callers, callees


def refs_for(grefs, va, radius=0):
    va = int(va, 16) if isinstance(va, str) else va
    out = {}
    for k, v in grefs.items():
        a = int(k, 16)
        if abs(a - va) <= radius:
            out[k] = v
    return out


def disasm_window(text, va0, va, before=0x30, after=0x30):
    if text is None:
        return []
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.skipdata = True
    off = va - va0
    lo = max(0, off - before)
    code = text[lo:off + after]
    return [(i.address, i.mnemonic, i.op_str)
            for i in md.disasm(code, va0 + lo)]


def find_strings(strings, hint, limit=20):
    out = []
    for va, s in strings.get("strings", []):
        if hint.lower() in s.lower():
            out.append((va, s))
            if len(out) >= limit:
                break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--index", required=True)
    ap.add_argument("--exe", default=None,
                    help="PS-X EXE file (owner's local copy) for --disasm")
    ap.add_argument("--function-at", dest="function_at", default=None)
    ap.add_argument("--disasm", default=None)
    ap.add_argument("--before", type=lambda x: int(x, 0), default=0x30)
    ap.add_argument("--after", type=lambda x: int(x, 0), default=0x30)
    ap.add_argument("--callers", default=None)
    ap.add_argument("--callees", default=None)
    ap.add_argument("--refs", default=None)
    ap.add_argument("--refs-near", default=None)
    ap.add_argument("--radius", type=lambda x: int(x, 0), default=0x100)
    ap.add_argument("--string", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    idx = load_index(args.index)
    functions = idx.get("functions", {}).get("functions", [])
    xrefs = idx.get("xrefs", {})
    grefs = xrefs.get("global_refs", {})
    strings = idx.get("strings", {})
    text, va0 = load_text(args.index, args.exe)

    if args.function_at:
        va = int(args.function_at, 0)
        f = function_at(functions, va)
        callers, callees = edges_for(xrefs, va, f) if f else ([], [])
        out = {"containing": f,
               "callers": sorted({c["src"] for c in callers}),
               "callees": sorted({c["dst"] for c in callees})}
        print(json.dumps(out, indent=1) if args.json else
              (f"{f}\ncallers: {sorted({c['src'] for c in callers})[:12]}\n"
               f"callees: {sorted({c['dst'] for c in callees})[:12]}"))
    if args.disasm:
        va = int(args.disasm, 0)
        for a, m, o in disasm_window(text, va0, va, args.before,
                                     args.after):
            print(f"{a:08X}: {m:8s} {o}")
    if args.callers:
        va = int(args.callers, 0)
        f = function_at(functions, va)
        callers, _ = edges_for(xrefs, va, f)
        print(json.dumps({"function": f["va"] if f else f"0x{va:08X}",
                          "callers": sorted({c["src"] for c in callers})},
                         indent=1))
    if args.callees:
        va = int(args.callees, 0)
        f = function_at(functions, va)
        _, callees = edges_for(xrefs, va, f)
        print(json.dumps({"function": f["va"] if f else f"0x{va:08X}",
                          "callees": sorted({c["dst"] for c in callees})},
                         indent=1))
    if args.refs:
        va = int(args.refs, 0)
        hits = refs_for(grefs, va, 0)
        print(json.dumps({k: v[:8] for k, v in hits.items()}, indent=1))
    if args.refs_near:
        va = int(args.refs_near, 0)
        hits = refs_for(grefs, va, args.radius)
        print(json.dumps({k: v[:6] for k, v in
                          sorted(hits.items(), key=lambda kv: int(kv[0],
                                                                 16))[:40]},
                         indent=1))
    if args.string:
        hits = find_strings(strings, args.string)
        for va, s in hits:
            print(f"{va}: {s!r}")


if __name__ == "__main__":
    main()
