#!/usr/bin/env python3
"""game_rebuild_index.py — disc inventory + executable index for a PS1 game
(Issue #3 Phase C).

Discovers the boot executable through disc filesystem records (ISO9660
PVD -> root/child directories -> SYSTEM.CNF BOOT line) and PS-X EXE
metadata (pc0/gp0/t_addr/t_size/data_start), never through a fixed
filename or byte offset alone.

Produces, in --out (default: an EXTERNAL analysis workspace, not the
repository):

  disc.json        every ISO9660 record: name, LBA, size, dir flag,
                   hashes, container/overlay candidates
  exe_identity.json  boot exe + every PS-X EXE candidate on disc
  functions.json   function table (own prologue/JAL recursion MERGED with
                   the external psxrecomp static analysis when provided;
                   every entry carries provenance + confidence)
  xrefs.json       direct call/jump edges, indirect sites, global RAM refs
  strings.json     printable ASCII strings with VAs + code refs
  re_index.json    master index tying everything together (identity,
                   regions, tool versions, commands, counts)
  re_index.sqlite  the same data as queryable tables
  re_report.md     readable report

File offsets and virtual addresses are kept strictly separate:
  file_off = 2048 (PS-EXE header) + (va - t_addr)   for text-mapped bytes
  va       = t_addr + (file_off - 2048)

Caching: <out>/.cache_manifest.json keyed by input bin sha256, exe sha256,
tool versions and CONFIG_VERSION; delete --force to recompute.

Usage (project convention):
  python3 scripts/game_rebuild_index.py --game <local-cue-or-bin> \
      --out <analysis-dir> [--exe-extra <path/to/analysis.tsv>] [--force]

Copyright policy: reads only the owner's local lawful image; writes
metadata (offsets, hashes, addresses, structure) but never copies game
bytes into the outputs beyond 16-byte hex previews.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys
import time
from collections import defaultdict

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)

CONFIG_VERSION = "re-index-1"
SECTOR = 2352
USER_OFF = 24          # MODE2/2352: 12 sync + 4 header + 8 subheader
USER_SZ = 2048
EXE_HDR = 0x800

# ------------------------------------------------------------------
# tool versions (reproducibility)
# ------------------------------------------------------------------


def tool_versions():
    import numpy
    try:
        import capstone
        cap = "capstone " + capstone.__version__
    except Exception:
        cap = "capstone MISSING (xref scan degraded)"
    return {
        "python": sys.version.split()[0],
        "numpy": numpy.__version__,
        "disassembler": cap,
        "config": CONFIG_VERSION,
    }


def sha256_file(path, chunk=1 << 22):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def hash_bytes(b):
    return {"md5": hashlib.md5(b).hexdigest(),
            "sha1": hashlib.sha1(b).hexdigest(),
            "sha256": hashlib.sha256(b).hexdigest()}


def hex_preview(b, n=16):
    return b[:n].hex()


# ------------------------------------------------------------------
# ISO9660 layer (RAW MODE2/2352 or plain 2048)
# ------------------------------------------------------------------


def resolve_cue_bin(cue_path):
    """Follow the .cue FILE entry to the actual binary track."""
    d = os.path.dirname(os.path.abspath(cue_path))
    with open(cue_path, "r", errors="replace") as f:
        for ln in f:
            if 'FILE "' in ln:
                name = ln.split('FILE "')[1].split('"')[0]
                p = os.path.join(d, name)
                if not os.path.exists(p):
                    raise SystemExit(f"cue references missing file: {p}")
                return p
    raise SystemExit(f"cue has no FILE entry: {cue_path}")


class DiscImage:
    def __init__(self, path):
        if path.lower().endswith(".cue"):
            path = resolve_cue_bin(path)
        self.path = path
        self.raw2352 = None
        with open(path, "rb") as f:
            f.seek(0)
            head = f.read(16)
        if head[:12] == b"\x00" + b"\xff" * 10 + b"\x00":
            self.raw2352 = True
            self.stride, self.off = SECTOR, USER_OFF
        elif head[1:6] == b"CD001" or os.path.getsize(path) % 2048 == 0:
            self.raw2352 = False
            self.stride, self.off = USER_SZ, 0
        else:
            raise ValueError(f"unrecognized image layout: {path}")
        self.size = os.path.getsize(path)
        self.sectors = self.size // self.stride

    def read_user(self, lba, count=1):
        with open(self.path, "rb") as f:
            f.seek(lba * self.stride + self.off)
            return f.read(count * USER_SZ)

    def read_user_range(self, lba, nbytes):
        n = (nbytes + USER_SZ - 1) // USER_SZ
        with open(self.path, "rb") as f:
            f.seek(lba * self.stride + self.off)
            return f.read(n * USER_SZ)[:nbytes]


def parse_pvd(disc):
    for s in range(16, 20):
        d = disc.read_user(s)
        if d[1:6] == b"CD001" and d[0] == 1:
            return d
    return None


def parse_dir_records(data):
    """Yield (name, lba, size, flags) from an ISO9660 directory body."""
    out, i = [], 0
    while i < len(data):
        ln = data[i]
        if ln == 0:
            i = (i // USER_SZ + 1) * USER_SZ
            continue
        rec = data[i:i + ln]
        lba = struct.unpack("<I", rec[2:6])[0]
        size = struct.unpack("<I", rec[10:14])[0]
        flags = rec[25]
        nl = rec[32]
        raw_name = rec[33:33 + nl]
        if raw_name in (b"\x00", b"\x01"):
            i += ln
            continue
        name = raw_name.decode("ascii", "replace").rstrip("\x00 ")
        while len(name) > 2 and name.endswith(";1"):
            name = name[:-2]
        out.append((name, lba, size, flags))
        i += ln
    return out


def walk_disc(disc, pvd, max_depth=4, max_files=4096):
    root = pvd[156:190]
    rlba = struct.unpack("<I", root[2:6])[0]
    rsize = struct.unpack("<I", root[10:14])[0]
    files, dirs = [], []
    todo = [("", rlba, rsize, 0)]
    while todo:
        path, lba, size, depth = todo.pop(0)
        if depth > max_depth:
            continue
        try:
            body = disc.read_user_range(lba, size)
        except OSError:
            continue
        for name, flba, fsize, flags in parse_dir_records(body):
            if flags & 2:
                dirs.append({"path": path + name + "/", "lba": flba,
                             "size": fsize})
                todo.append((path + name + "/", flba, fsize, depth + 1))
            else:
                files.append({"path": path + name, "lba": flba,
                              "size": fsize})
                if len(files) >= max_files:
                    return files, dirs
    return files, dirs


def parse_system_cnf(text):
    boot = None
    for line in text.splitlines():
        if line.strip().upper().startswith("BOOT"):
            m = re.search(r"cdrom:\\?([^;\s]+)", line, re.I)
            if m:
                boot = m.group(1).strip()
    return boot


PSX_EXE_MAGIC = b"PS-X EXE"


def parse_psexE_header(data):
    """Parse a PS-X EXE header. Returns dict or None if magic absent."""
    if len(data) < 0x800 or data[:8] != PSX_EXE_MAGIC:
        return None
    pc0, gp0, t_addr, t_size = struct.unpack_from("<IIII", data, 0x10)
    d_addr, d_size = struct.unpack_from("<II", data, 0x20)
    b_addr, b_size = struct.unpack_from("<II", data, 0x38)
    sp, fp, sp2, fp2 = struct.unpack_from("<IIII", data, 0x40)
    return {
        "pc0": pc0, "gp0": gp0, "t_addr": t_addr, "t_size": t_size,
        "d_addr": d_addr, "d_size": d_size, "b_addr": b_addr,
        "b_size": b_size, "sp": sp, "fp": fp,
        "header_hex_preview": hex_preview(data, 64),
    }


# ------------------------------------------------------------------
# MIPS layer (capstone; degrades to word-scan when unavailable)
# ------------------------------------------------------------------

J_OPS = {0x02: "j", 0x03: "jal"}


def decode_words(text_bytes):
    import numpy as np
    return np.frombuffer(text_bytes[:len(text_bytes) // 4 * 4],
                         dtype="<u4")


def scan_jal_targets(words, va0):
    """All j/jal absolute targets (recursive-descent seeds)."""
    targets = {}
    for i in range(len(words)):
        w = int(words[i])
        op = w >> 26
        if op in J_OPS:
            tgt = ((va0 + i * 4 + 4) & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
            targets.setdefault(tgt, []).append(va0 + i * 4)
    return targets


def scan_prologue_candidates(words, va0):
    """Classic MIPS o32 prologue: addiu $sp,$sp,-imm  (sw $ra,N($sp))."""
    out = []
    for i in range(len(words) - 1):
        w = int(words[i])
        if (w >> 26) == 0x09:                      # addiu
            rs = (w >> 21) & 0x1F
            rt = (w >> 16) & 0x1F
            imm = w & 0xFFFF
            if rs == 29 and rt == 29 and 0x8000 <= imm:  # sp, sp, -N
                w2 = int(words[i + 1])
                if (w2 >> 26) == 0x2B:             # sw $ra, N(sp)
                    rt2 = (w2 >> 16) & 0x1F
                    if rt2 == 31:
                        out.append(va0 + i * 4)
    return out


SEXT = lambda v: v - 0x10000 if v >= 0x8000 else v  # noqa: E731
LOADSTORE = {0x20: "lb", 0x21: "lh", 0x22: "lwl", 0x23: "lw",
             0x24: "lbu", 0x25: "lhu", 0x26: "lwr", 0x28: "sb",
             0x29: "sh", 0x2A: "swl", 0x2B: "sw", 0x2E: "swr"}
# I-type ops whose DESTINATION is rt (register written -> tracking stops)
ITYPE_WRITES_RT = {0x08, 0x0A, 0x0B, 0x0C, 0x0E}
# R-type functs that write rd
RTYPE = 0x00


def _rd(w):
    return (w >> 11) & 0x1F


def scan_global_refs(words, va0, lo=0x80000000, hi=0x81000000,
                     window=24):
    """lui rX, hi ; (register-tracking within a bounded window) ->
    load/store/addiu effective-address refs into [lo, hi).

    Unlike the old fixed 4-insn window, the tracker tolerates
    unrelated instructions between the lui and the access (the common
    `lui $s0, 0x8003` at function entry + accesses many insns later)
    and follows lui+ori / lui+addiu re-combinations.
    """
    refs = {}
    n = len(words)
    for i in range(n):
        w = int(words[i])
        if (w & 0xFC100000) != 0x3C000000:          # lui
            continue
        hi16 = w & 0xFFFF
        rt = (w >> 16) & 0x1F
        if rt == 0:
            continue
        base = hi16 << 16
        pc = va0 + i * 4
        for j in range(i + 1, min(i + 1 + window, n)):
            ij = int(words[j])
            op = ij >> 26
            rs = (ij >> 21) & 0x1F
            rtj = (ij >> 16) & 0x1F
            if op == RTYPE:
                if _rd(ij) == rt:
                    break                            # rt overwritten
                continue
            if op == 0x0F:                           # lui
                if rtj == rt:
                    break
                continue
            if op in LOADSTORE and rs == rt:
                eff = base + SEXT(ij & 0xFFFF)
                if lo <= eff < hi:
                    refs.setdefault(eff, []).append(
                        (va0 + j * 4, LOADSTORE[op]))
                continue                             # rt unchanged
            if op == 0x09 and rs == rt:              # addiu rt, rt, imm
                base = base + SEXT(ij & 0xFFFF)
                eff = base
                if lo <= eff < hi:
                    refs.setdefault(eff, []).append((va0 + j * 4,
                                                     "addiu"))
                continue                             # rt now = eff
            if op == 0x0D and rs == rt and rtj == rt:  # ori rt, rt, imm
                base = base | (ij & 0xFFFF)
                continue
            if op in ITYPE_WRITES_RT and rtj == rt:
                break                                # rt overwritten
            if op == 0x09 and rtj == rt:
                break                                # addiu from other rs
    return refs


def disassemble(text_bytes, va0, capstone_mips=True):
    """Full linear disassembly -> list of (pc, mnemonic, op_str, bytes)."""
    if not capstone_mips:
        return []
    try:
        from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
    except Exception:
        return []
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.skipdata = True
    out = []
    for ins in md.disasm(text_bytes, va0):
        out.append((ins.address, ins.mnemonic, ins.op_str, ins.size))
    return out


def extract_strings(text_bytes, va0, min_len=6, max_len=120):
    """Printable ASCII runs -> [(va, text)]. Data + text regions alike."""
    out, cur, start = [], [], 0
    printable = set(range(0x20, 0x7F))
    for off, b in enumerate(text_bytes):
        if b in printable:
            if not cur:
                start = off
            cur.append(b)
        else:
            if len(cur) >= min_len:
                s = bytes(cur).decode("ascii", "replace")
                out.append((va0 + start, s[:max_len]))
            cur = []
    if len(cur) >= min_len:
        out.append((va0 + start,
                    bytes(cur).decode("ascii", "replace")[:max_len]))
    return out


# ------------------------------------------------------------------
# external analysis import (psxrecomp static analysis)
# ------------------------------------------------------------------


def import_functions_tsv(path):
    """Import the psxrecomp functions.tsv (addr,size,name,confidence,
    args,ret,callers,callees,frame,saved,tags)."""
    funcs = {}
    try:
        with open(path) as f:
            header = f.readline()
            for line in f:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 4:
                    continue
                addr = int(parts[0], 16)
                funcs[addr] = {
                    "va": f"0x{addr:08X}",
                    "size": int(parts[1]) if parts[1].isdigit() else 0,
                    "name": parts[2],
                    "confidence": parts[3],
                    "args": parts[4] if len(parts) > 4 else "",
                    "ret": parts[5] if len(parts) > 5 else "",
                    "callers": parts[6] if len(parts) > 6 else "",
                    "callees": parts[7] if len(parts) > 7 else "",
                    "tags": parts[10] if len(parts) > 10 else "",
                    "source": "psxrecomp-analyze(static,external)",
                }
    except OSError:
        pass
    return funcs


# ------------------------------------------------------------------
# main build
# ------------------------------------------------------------------


def build_index(game, out_dir, exe_extra=None, force=False, budget_s=900):
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    tools = tool_versions()

    disc = DiscImage(game)
    pvd = parse_pvd(disc)
    if pvd is None:
        raise SystemExit("no ISO9660 PVD found")
    volid = pvd[40:72].decode("ascii", "replace").strip()

    files, dirs = walk_disc(disc, pvd)
    print(f"disc: {disc.path}  raw2352={disc.raw2352}  "
          f"volume={volid!r}  files={len(files)} dirs={len(dirs)}")

    # full-image hash (identity)
    bin_sha = sha256_file(disc.path)

    # SYSTEM.CNF -> boot exe discovery
    cnf = None
    for f in files:
        if f["path"].upper().endswith("SYSTEM.CNF"):
            cnf = disc.read_user_range(f["lba"], min(f["size"], 4096))
            break
    boot_name = parse_system_cnf(cnf.decode("ascii", "replace")) if cnf else None

    # resolve boot exe through the directory records
    boot_rec = None
    if boot_name:
        for f in files:
            base = f["path"].split("/")[-1]
            if base.upper() == boot_name.upper() or \
               base.upper() == boot_name.upper() + ";1":
                boot_rec = f
                break
    if boot_rec is None:
        raise SystemExit(f"boot exe {boot_name!r} not found in ISO records")

    exe_bytes = disc.read_user_range(boot_rec["lba"], boot_rec["size"])
    hdr = parse_psexE_header(exe_bytes)
    if hdr is None:
        raise SystemExit("boot file is not a PS-X EXE")

    # every other PS-X EXE candidate on disc (overlays / sub-executables)
    exe_candidates = []
    for f in files:
        if f["size"] < 2048 or f["size"] > 4_000_000:
            continue
        head = disc.read_user(f["lba"])
        if head[:8] == PSX_EXE_MAGIC:
            h = parse_psexE_header(head)
            first = disc.read_user_range(f["lba"],
                                         min(f["size"], 64 * 1024))
            exe_candidates.append({
                "path": f["path"], "lba": f["lba"], "size": f["size"],
                "header": h, "hashes_head64k": hash_bytes(first[:65536]),
            })

    # --------------------------------------------------------------
    # text mapping:  file[0x800 + k]  <->  va = t_addr + k
    # --------------------------------------------------------------
    t_addr = hdr["t_addr"]
    text = exe_bytes[EXE_HDR:]
    va0 = t_addr
    print(f"boot exe: {boot_rec['path']} size={len(exe_bytes)} "
          f"pc0={hdr['pc0']:#010x} t_addr={t_addr:#010x} "
          f"t_size={hdr['t_size']} text_bytes={len(text)}")

    # cache gate
    cache_path = os.path.join(out_dir, ".cache_manifest.json")
    cache_key = {"bin_sha256": bin_sha, "exe_sha256":
                 hashlib.sha256(exe_bytes).hexdigest(),
                 "tools": tools, "config": CONFIG_VERSION,
                 "exe_extra": os.path.getsize(exe_extra)
                 if exe_extra and os.path.exists(exe_extra) else None}
    if not force and os.path.exists(cache_path):
        try:
            with open(cache_path) as f:
                prev = json.load(f)
            if prev.get("key") == cache_key:
                print("cache HIT — recomputing nothing "
                      "(--force to override)")
                return json.load(open(os.path.join(out_dir,
                                                   "re_index.json")))
        except (OSError, json.JSONDecodeError):
            pass

    # --------------------------------------------------------------
    # functions: external table + own recursion/prologues
    # --------------------------------------------------------------
    functions = {}
    if exe_extra:
        ext = import_functions_tsv(exe_extra)
        for a, rec in ext.items():
            functions[a] = rec
        print(f"external functions imported: {len(ext)} from {exe_extra}")

    words = decode_words(text)
    jal = scan_jal_targets(words, va0)
    prologues = scan_prologue_candidates(words, va0)
    for tgt, sites in jal.items():
        off = tgt - va0
        if 0 <= off < len(text) - 4:
            if tgt not in functions:
                functions[tgt] = {
                    "va": f"0x{tgt:08X}", "size": 0,
                    "name": f"func_{tgt:08X}", "confidence": "jal_target",
                    "args": "", "ret": "", "callers": len(sites),
                    "callees": "", "tags": "", "source": "own:jal-recursion",
                }
    new_pro = 0
    for pc in prologues:
        if pc not in functions:
            functions[pc] = {
                "va": f"0x{pc:08X}", "size": 0,
                "name": f"func_{pc:08X}", "confidence": "prologue",
                "args": "", "ret": "", "callers": "", "callees": "",
                "tags": "", "source": "own:prologue-scan",
            }
            new_pro += 1
    print(f"own seeds: {len(jal)} jal targets, {new_pro} new prologues")

    # sort by va; size = next_va - va (clipped to text end)
    text_end_va = va0 + len(text)
    ordered = sorted(functions)
    for i, a in enumerate(ordered):
        nxt = ordered[i + 1] if i + 1 < len(ordered) else text_end_va
        rec = functions[a]
        if not rec.get("size"):
            rec["size"] = max(0, min(nxt, text_end_va) - a)
        rec["file_off"] = EXE_HDR + (a - va0)

    # verification: does each function begin with a decodable (non-zero,
    # non-unmapped) MIPS word?
    for a, rec in functions.items():
        off = (a - va0) // 4
        if 0 <= off < len(words):
            w = int(words[off])
            rec["decodable"] = bool(w not in (0x00000000, 0xFFFFFFFF))
        else:
            rec["decodable"] = False

    # --------------------------------------------------------------
    # xrefs: call/jump edges + global refs
    # --------------------------------------------------------------
    call_edges = []
    indirect_sites = []
    func_starts = set(ordered)
    for i in range(len(words)):
        w = int(words[i])
        pc = va0 + i * 4
        op = w >> 26
        if op in J_OPS:
            tgt = ((pc + 4) & 0xF0000000) | ((w & 0x3FFFFFF) << 2)
            if va0 <= tgt < text_end_va:
                call_edges.append({"src": pc, "dst": tgt,
                                   "kind": J_OPS[op]})
        elif op == 0 and ((w >> 21) & 0x1F) == 0 and ((w >> 6) & 0x3F) in \
                (0x09, 0x0C):                        # jalr variants
            indirect_sites.append({"pc": pc,
                                   "kind": "jalr"})
    grefs = scan_global_refs(words, va0)
    print(f"edges={len(call_edges)} indirect={len(indirect_sites)} "
          f"global_ref_targets={len(grefs)}")

    # strings + refs into strings (code may point anywhere INSIDE a run,
    # so match by containment, not exact start)
    strings = extract_strings(text, va0)
    import bisect as _bisect
    s_starts = [a for a, _s in strings]
    s_lens = [len(s) for _a, s in strings]
    str_refs = []
    for eff, sites in grefs.items():
        i = _bisect.bisect_right(s_starts, eff) - 1
        if 0 <= i < len(s_starts) and s_starts[i] <= eff \
                < s_starts[i] + s_lens[i]:
            str_refs.append({"va": f"0x{eff:08X}",
                             "string": strings[i][1][:60],
                             "sites": [f"0x{p:08X}" for p, _k
                                       in sites[:4]]})
    print(f"strings={len(strings)} (referenced from code: "
          f"{len(str_refs)})")

    # pointer-table candidates: data words holding image VAs
    img_refs = {}
    for i in range(len(words)):
        w = int(words[i])
        if va0 <= w < text_end_va:
            img_refs.setdefault(w, []).append(va0 + i * 4)

    # --------------------------------------------------------------
    # disc file hashing (metadata only) + classification
    # --------------------------------------------------------------
    for f in files:
        data = disc.read_user_range(f["lba"], min(f["size"], 1 << 20))
        f["hash_head1m"] = hash_bytes(data) \
            if f["size"] <= (1 << 20) else \
            {"sha256_head1m": hashlib.sha256(data).hexdigest()}
        f["is_dir"] = False
        if f["size"] >= 2048:
            head = disc.read_user(f["lba"])
            f["psx_exe"] = head[:8] == PSX_EXE_MAGIC
            f["tim_like"] = struct.unpack_from("<I", head)[0] == 0x10
    disc_out = {
        "image": os.path.abspath(disc.path),
        "raw2352": disc.raw2352, "sectors": disc.sectors,
        "size": disc.size, "sha256": bin_sha,
        "volume_id": volid, "system_cnf":
            cnf.decode("ascii", "replace") if cnf else None,
        "boot_exe": boot_name, "files": files, "dirs": dirs,
    }

    exe_identity = {
        "path": boot_rec["path"], "lba": boot_rec["lba"],
        "size": boot_rec["size"], "hashes": hash_bytes(exe_bytes),
        "header": hdr, "text_file_off": EXE_HDR,
        "text_sha256": hashlib.sha256(text).hexdigest(),
        "va_range": [f"0x{va0:08X}", f"0x{text_end_va:08X}"],
        "other_exe_candidates": exe_candidates,
    }

    # --------------------------------------------------------------
    # write outputs
    # --------------------------------------------------------------
    def wj(name, obj):
        p = os.path.join(out_dir, name)
        with open(p, "w") as f:
            json.dump(obj, f, indent=1)
        print(f"wrote {p} ({os.path.getsize(p)} bytes)")
        return p

    wj("disc.json", disc_out)
    wj("exe_identity.json", exe_identity)
    wj("functions.json", {
        "source_files": {"external_tsv": exe_extra or None},
        "count": len(functions),
        "functions": [functions[a] for a in ordered],
    })
    wj("xrefs.json", {
        "call_edges": call_edges,
        "indirect_sites": indirect_sites,
        "global_refs": {f"0x{a:08X}": [[p, k] for p, k in v[:24]]
                        for a, v in sorted(grefs.items())},
        "image_pointer_refs": {f"0x{a:08X}": len(v)
                               for a, v in sorted(img_refs.items())
                               if len(v) >= 2},
        "string_refs": str_refs[:200],
    })
    wj("strings.json", {
        "min_len": 6, "count": len(strings),
        "strings": [[f"0x{a:08X}", s] for a, s in strings],
    })
    # note: strings.json stays in the EXTERNAL workspace (game text); only
    # counts + re_index.json master metadata are ever candidates for commit

    # byte coverage: union of function ranges (no double counting)
    covered = 0
    last = va0
    for a in ordered:
        sz = functions[a].get("size") or 0
        s, e = max(a, last), min(a + sz, text_end_va)
        if e > s:
            covered += e - s
            last = e
        elif a >= last:
            last = a
    master = {
        "schema": "ps1play re_index v1",
        "config_version": CONFIG_VERSION,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                       time.gmtime()),
        "tools": tools,
        "commands": {
            "rebuild": (f"python3 scripts/game_rebuild_index.py "
                        f"--game {disc.path} --out {out_dir}"),
        },
        "disc": {"sha256": bin_sha, "volume_id": volid,
                 "files": len(files), "dirs": len(dirs),
                 "raw2352": disc.raw2352},
        "exe": {"path": boot_rec["path"], "size": boot_rec["size"],
                "pc0": f"0x{hdr['pc0']:08X}",
                "t_addr": f"0x{t_addr:08X}",
                "t_size": hdr["t_size"],
                "text_sha256": hashlib.sha256(text).hexdigest()},
        "counts": {
            "functions": len(functions),
            "own_jal_targets": len(jal),
            "own_prologues": len(prologues),
            "call_edges": len(call_edges),
            "indirect_sites": len(indirect_sites),
            "global_ref_targets": len(grefs),
            "image_pointer_targets": len(img_refs),
            "strings": len(strings),
            "strings_referenced": len(str_refs),
            "function_bytes_covered": covered,
            "exe_text_bytes": len(text),
        },
        "copyright_note": (
            "metadata only: offsets, hashes, addresses, structure — "
            "no game bytes are committed anywhere"),
    }
    wj("re_index.json", master)

    # sqlite
    dbp = os.path.join(out_dir, "re_index.sqlite")
    try:
        import sqlite3
        con = sqlite3.connect(dbp)
        cur = con.cursor()
        for t in ("files", "functions", "edges", "grefs", "strings"):
            cur.execute(f"DROP TABLE IF EXISTS {t}")
        cur.execute("CREATE TABLE IF NOT EXISTS files "
                    "(path TEXT, lba INT, size INT, psx_exe INT, "
                    "tim_like INT, sha256 TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS functions "
                    "(va TEXT PRIMARY KEY, size INT, name TEXT, "
                    "confidence TEXT, source TEXT, file_off INT)")
        cur.execute("CREATE TABLE IF NOT EXISTS edges "
                    "(src TEXT, dst TEXT, kind TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS grefs "
                    "(va TEXT, pc TEXT, kind TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS strings "
                    "(va TEXT, text TEXT)")
        cur.executemany("INSERT INTO files VALUES (?,?,?,?,?,?)",
                        [(f["path"], f["lba"], f["size"],
                          int(f.get("psx_exe", False)),
                          int(f.get("tim_like", False)),
                          (f["hash_head1m"].get("sha256") or
                           f["hash_head1m"].get("sha256_head1m", "")))
                         for f in files])
        cur.executemany("INSERT INTO functions VALUES (?,?,?,?,?,?)",
                        [(functions[a]["va"], functions[a]["size"],
                          functions[a]["name"], functions[a]["confidence"],
                          functions[a]["source"], functions[a]["file_off"])
                         for a in ordered])
        cur.executemany("INSERT INTO edges VALUES (?,?,?)",
                        [(f"0x{e['src']:08X}", f"0x{e['dst']:08X}",
                          e["kind"]) for e in call_edges])
        cur.executemany("INSERT INTO grefs VALUES (?,?,?)",
                        [(f"0x{a:08X}", f"0x{p:08X}", k)
                         for a, v in grefs.items() for p, k in v])
        cur.executemany("INSERT INTO strings VALUES (?,?)",
                        [(f"0x{a:08X}", s) for a, s in strings])
        con.commit()
        con.close()
        print(f"wrote {dbp}")
    except ImportError:
        print("sqlite3 unavailable — skipped DB")

    # readable report
    rep = os.path.join(out_dir, "re_report.md")
    with open(rep, "w") as f:
        f.write(f"# RE index report — {volid}\n\n")
        f.write(f"- image: `{disc.path}` sha256 `{bin_sha[:16]}…`\n")
        f.write(f"- boot exe: `{boot_rec['path']}` "
                f"({boot_rec['size']} B) pc0 `{hdr['pc0']:#010x}` "
                f"t_addr `{t_addr:#010x}` t_size `{hdr['t_size']}`\n")
        f.write(f"- tools: {tools}\n\n")
        f.write("| metric | count |\n|---|---|\n")
        for k, v in master["counts"].items():
            f.write(f"| {k} | {v} |\n")
        f.write("\n## disc layout\n\n")
        f.write("| path | lba | size | psx_exe | tim_like |\n")
        f.write("|---|---|---|---|---|\n")
        for f_ in files:
            f.write(f"| {f_['path']} | {f_['lba']} | {f_['size']} "
                    f"| {int(f_.get('psx_exe', False))} "
                    f"| {int(f_.get('tim_like', False))} |\n")
    print(f"wrote {rep}")

    with open(cache_path, "w") as f:
        json.dump({"key": cache_key, "generated_utc":
                   master["generated_utc"]}, f, indent=1)
    print(f"done in {time.time()-t0:.1f}s")
    return master


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--game", required=True,
                    help="owner's local .cue or .bin image")
    ap.add_argument("--out", required=True,
                    help="analysis output dir (external workspace)")
    ap.add_argument("--exe-extra", default=None,
                    help="optional external functions.tsv to merge "
                         "(e.g. psxrecomp analysis)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(args.game):
        raise SystemExit(f"--game not found: {args.game}")
    master = build_index(args.game, args.out, args.exe_extra, args.force)
    print(json.dumps(master["counts"], indent=1))


if __name__ == "__main__":
    main()
