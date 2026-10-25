#!/usr/bin/env python3
"""session3_static_chopper.py — session-3 static batch (Phase 2 reuse).

Questions from the session-2 report §5 (smallest next experiments):
  Q1  Which overlay/EXE functions reference the chopper state words
      0xaa94 / 0xabdc (its two alternating states) — i.e. the chopper
      handler and any code that reads/writes it?
  Q2  Which functions reference the wreck states 0xa304 / 0xa44c and is
      there ANY path out of 0xa44c (despawn / section-cleanup)?
  Q3  Which functions reference the truck states 0x9e88 (parked) and the
      kill-adjacent states, to cross-check the known handlers?

Output: JSON to evidence/issue5_session3_static/static_chopper.json
(stdout summary too).  Read-only analysis of committed Ghidra corpora.
"""
import json
import os
import re
import sys

REPO = "/home/z/my-project/ps1ai"
GH = os.path.join(REPO, "data/games/SLUS-01212/ghidra")
OUT = os.path.join(REPO, "evidence/issue5_session3_static")
os.makedirs(OUT, exist_ok=True)

CORPORA = {
    "overlay": os.path.join(GH, "overlay_decompiled.json"),
    "exe": os.path.join(GH, "exe_decompiled_targeted.json"),
}

TARGETS = {
    "chopper_a": "0xaa94",
    "chopper_b": "0xabdc",
    "wreck_dead": "0xa44c",
    "wreck_live": "0xa304",
    "truck_parked": "0x9e88",
    "faller_bomb": "0xb4e4",
    "soldier_4054": "0x4054",
}


def load_corpus(path):
    if not os.path.exists(path):
        print("[warn] missing corpus:", path)
        return {}
    with open(path) as f:
        raw = json.load(f)
    # normalize: {addr: {"c": text, "name": ...}}
    return raw


def find_refs(text, target):
    """Match the target as a standalone hex immediate (e.g. 0xaa94)."""
    if not text:
        return False
    return re.search(r"(?<![0-9a-fA-F])" + target + r"(?![0-9a-fA-F])",
                     text) is not None


def main():
    results = {}
    for corpus, path in CORPORA.items():
        data = load_corpus(path)
        per_target = {t: [] for t in TARGETS}
        for addr, fn in data.items():
            c = fn.get("c") or ""
            name = fn.get("name") or addr
            for t, const in TARGETS.items():
                if find_refs(c, const):
                    per_target[t].append(
                        {"addr": addr, "name": name, "bytes": fn.get("bytes")})
        results[corpus] = {
            "n_funcs": len(data),
            "refs": {t: v for t, v in per_target.items()},
        }
        print(f"[{corpus}] {len(data)} funcs")
        for t, v in per_target.items():
            addrs = [x["addr"] for x in v]
            print(f"  {t} ({TARGETS[t]}): {addrs}")

    # Q2 deep-dive: any reference to 0xa44c in overlay functions — dump
    # the C bodies so we can see whether a despawn path exists.
    q2_dump = {}
    ov = load_corpus(CORPORA["overlay"])
    for addr, fn in ov.items():
        c = fn.get("c") or ""
        if find_refs(c, "0xa44c") or find_refs(c, "0xa304"):
            q2_dump[addr] = c[:2500]
    results["wreck_bodies"] = q2_dump

    out = os.path.join(OUT, "static_chopper.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
