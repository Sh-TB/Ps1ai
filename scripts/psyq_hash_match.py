#!/usr/bin/env python3
"""psyq_hash_match.py — Identify Psy-Q library functions inside SLUS_012.12 (Issue #5, P1-9).

Port of the relocation-tolerant hashing recipe from PS1Recomp/ps1-recomp
(external_audit/ps1recomp/tools/extract_psyq_signatures.py, MIT-style reuse of
the *algorithm* only — no game content, no PsyQ binaries are redistributed):

  hash_masked = sha256( little-endian words with immediates zeroed )[:16]
  hash_full   = sha256( raw function body )[:16]
  match_mode  = "full" if size <= 24 else "masked"   (BIOS A0/B0/C0 wrappers)

Inputs:
  --exe         PS-X EXE (2048-byte header + text). Defaults to the canonical
                owner-local copy; falls back to the workspace .full copy.
  --functions   functions.json from the game_rebuild_index workspace index.
  --signatures  psyq_signatures.toml (kept OUT of the repo on purpose; it is
                third-party GPL-3 repo data derived from PsyQ libs).
  --out         psyq_labels.json (fact-only: va, size, name, library, hash).

Evidence fields on every record: source, match_mode, hash, candidates.
Never commit the signatures file or the EXE itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import tomllib
from datetime import datetime, timezone

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_EXE_CANDIDATES = [
    os.path.join(_REPO, "ps1play", "re", "SLUS_012.12"),
    "/home/z/my-project/work/msx_recomp/SLUS_012.12.full",
]
DEFAULT_FUNCTIONS = "/home/z/my-project/work/msx_recomp/index/functions.json"
DEFAULT_SIGNATURES = "/home/z/my-project/external_audit/ps1recomp/ps1Analyzer/data/psyq_signatures.toml"
DEFAULT_OUT = os.path.join(_REPO, "data", "games", "SLUS-01212", "psyq_labels.json")

FULL_MATCH_SIZE_LIMIT = 24

_BRANCH_OPS = {0x01, 0x04, 0x05, 0x06, 0x07, 0x14, 0x15, 0x16, 0x17}
_IMM_ALU_OPS = {0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F}


def mask_immediates(word: int) -> int:
    """Zero immediate fields in a 32-bit MIPS instruction (relocation-tolerant).

    Conservative: COP0/1/2/3 kept exact (GTE encodings carry no relocatable imm).
    """
    op = (word >> 26) & 0x3F
    if op == 0x00:
        return word
    if op in (0x02, 0x03):            # J / JAL: 26-bit target
        return word & 0xFC000000
    if op in _BRANCH_OPS:             # branches: low 16 offset
        return word & 0xFFFF0000
    if op in _IMM_ALU_OPS:            # ADDI..LUI
        return word & 0xFFFF0000
    if op >= 0x20:                    # loads/stores incl. LWC2/SWC2
        return word & 0xFFFF0000
    return word


def load_exe(path: str) -> tuple[int, int, bytes]:
    """Return (t_addr, t_size, text_bytes) from a PS-X EXE."""
    raw = open(path, "rb").read()
    if raw[0:8] != b"PS-X EXE":
        raise SystemExit(f"not a PS-X EXE: {path}")
    t_addr, t_size = struct.unpack_from("<II", raw, 0x18)
    text = raw[0x800:0x800 + t_size]
    if len(text) != t_size:
        raise SystemExit(f"text truncated in {path}: {len(text)} != {t_size}")
    return t_addr, t_size, text


def func_body(text: bytes, t_addr: int, va: int, size: int) -> bytes | None:
    off = va - t_addr
    if off < 0 or size <= 0 or off + size > len(text):
        return None
    return text[off:off + size]


def hashes_for(body: bytes) -> tuple[str, str]:
    masked = bytearray()
    for off in range(0, len(body) - len(body) % 4, 4):
        w = struct.unpack_from("<I", body, off)[0]
        masked += struct.pack("<I", mask_immediates(w))
    return (
        hashlib.sha256(bytes(masked)).hexdigest()[:16],
        hashlib.sha256(body).hexdigest()[:16],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Match Psy-Q signatures against the game EXE (Issue #5 P1-9).")
    ap.add_argument("--exe", default=None)
    ap.add_argument("--functions", default=DEFAULT_FUNCTIONS)
    ap.add_argument("--signatures", default=DEFAULT_SIGNATURES)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    exe = args.exe
    if not exe:
        exe = next((c for c in DEFAULT_EXE_CANDIDATES if os.path.exists(c)), None)
        if not exe:
            raise SystemExit("no EXE found; pass --exe (owner-local PS-X EXE)")
    exe_sha = hashlib.sha256(open(exe, "rb").read()).hexdigest()

    t_addr, t_size, text = load_exe(exe)
    funcs = json.load(open(args.functions))["functions"]
    sigs = tomllib.load(open(args.signatures, "rb"))["signature"]

    by_full: dict[str, list[dict]] = {}
    by_masked: dict[str, list[dict]] = {}
    for s in sigs:
        by_full.setdefault(s.get("hash_full", ""), []).append(s)
        by_masked.setdefault(s.get("hash_masked", ""), []).append(s)

    labels, stats = [], {"matched": 0, "ambiguous": 0, "skipped": 0}
    lib_counts: dict[str, int] = {}
    for f in funcs:
        va = int(f["va"], 16)
        size = int(f.get("size") or 0)
        body = func_body(text, t_addr, va, size)
        if body is None or len(body) < 4:
            stats["skipped"] += 1
            continue
        h_masked, h_full = hashes_for(body)
        mode = "full" if size <= FULL_MATCH_SIZE_LIMIT else "masked"
        cands = (by_full if mode == "full" else by_masked).get(h_full if mode == "full" else h_masked, [])
        if not cands:
            continue
        names = sorted({c["name"] for c in cands})
        libraries = sorted({c.get("library", "") for c in cands if c.get("library")})
        rec = {
            "va": f"0x{va:08X}",
            "size": size,
            "name": names[0] if len(names) == 1 else f"ambiguous:{'|'.join(names[:4])}",
            "library": libraries[0] if len(libraries) == 1 else "",
            "match_mode": mode,
            "hash": h_full if mode == "full" else h_masked,
            "candidates": names[:8],
            "confidence": "matched" if len(names) == 1 else f"ambiguous({len(names)})",
            "source": "ps1recomp@ab4f0e0 psyq_signatures.toml (hash-identification, no content)",
        }
        labels.append(rec)
        if len(names) == 1:
            stats["matched"] += 1
            lib_counts[rec["library"] or "?"] = lib_counts.get(rec["library"] or "?", 0) + 1
        else:
            stats["ambiguous"] += 1

    out = {
        "schema": "ps1play-psyq-labels/1",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "exe_sha256": exe_sha,
        "t_addr": f"0x{t_addr:08X}",
        "t_size": t_size,
        "signatures_total": len(sigs),
        "functions_scanned": len(funcs),
        "stats": stats,
        "library_counts": lib_counts,
        "labels": labels,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out, "w"), indent=1)
    print(f"psyq_hash_match: {stats['matched']} matched, {stats['ambiguous']} ambiguous, "
          f"{stats['skipped']} skipped -> {args.out}")
    print("libraries:", dict(sorted(lib_counts.items(), key=lambda kv: -kv[1])[:10]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
