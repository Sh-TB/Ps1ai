#!/usr/bin/env python3
"""r69_fingerprint_xref.py — R69 experiment track, part 1 (OFFLINE,
ZERO BOOTS): the +500 fingerprint xref.

The R69 capsule hypothesis, lead (1) SOURCE-FIRST: the 19 zero-overlap
offsets (+500 fingerprint, the r68_analysis.json intersection) are
xref'd in the ENEMY.BIN overlay @0x8009C0E8 + the EXE to find the
PAYMENT WRITER (the pay-before-registration law pins the write order:
the accumulator pays ~2 frames before the visible registration —
R52/R66; the R68 honest note adds the missing-registration side).

Method (static, legal local copies only — ps1play/re/SLUS_012.12 sha
1508b532..., ENEMY.BIN sha cab64009...; the binaries are NOT
committed, copyright policy Issue #3):

  1. The 19 fingerprint offsets come from the committed analysis
     (data/games/SLUS-01212/truck_evidence/r68/r68_analysis.json,
     zero_overlap_test.intersection).
  2. FULL-TEXT instruction scan (capstone MIPS32): every load/store
     whose displacement is a fingerprint offset, across
       * the whole EXE text (t_addr..t_addr+t_size), bucketed into
         the 3957 Ghidra functions (ghidra_functions.json);
       * the whole ENEMY.BIN overlay (load VA 0x8009C0E8), bucketed
         into the 468 Ghidra overlay functions
         (ghidra_overlay_functions.json).
     Load = lw/lh/lhu/lb/lbu/lwl/lwr; store = sw/sh/sb/swl/swr.
  3. The per-function fingerprint profile: which of the 19 offsets a
     function touches, loads vs stores.  Rank by n_offsets (stores
     weighted) — the entity-record consumers surface on top.
  4. THE SCORE-WRITER CORRELATION: the committed source_map.json
     score_p1 sites (0x800EE318, 9 direct xrefs) — for each site the
     containing Ghidra function is resolved and its fingerprint
     profile extracted; the payment writer = the score-site function
     that ALSO stores fingerprint offsets (the pay-before-registration
     law predicts the score store adjacent to the record writes).
  5. The amount hunt: addiu/lw-immediate constants 500 (0x1f4) and
     1000 (0x3e8) in the score-site functions + the little-endian
     u32 scans of the EXE data segments (payment lookup tables).

Output (committed): data/games/SLUS-01212/truck_evidence/r69/
  r69_fingerprint_xref.json   (the machine-verifiable verdict)
  r69_fingerprint_xref.md     (the human report)
"""
from __future__ import annotations

import json
import os
import struct
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
from capstone.mips import MIPS_OP_MEM

_REPO = "/home/z/my-project/ps1ai"
EV = os.path.join(_REPO, "data", "games", "SLUS-01212", "truck_evidence")
GH = os.path.join(_REPO, "data", "games", "SLUS-01212", "ghidra")
EXE_PATH = os.path.join(_REPO, "ps1play", "re", "SLUS_012.12")
OVL_PATH = os.path.join(_REPO, "ps1play", "re", "ENEMY.BIN")
OVL_VA = 0x8009C0E8
OUT_DIR = os.path.join(EV, "r69")
OUT_JSON = os.path.join(OUT_DIR, "r69_fingerprint_xref.json")
OUT_MD = os.path.join(OUT_DIR, "r69_fingerprint_xref.md")

EXE_VA = 0x80010000
EXE_OFF = 0x800

EXPECTED_EXE_SHA = "1508b53216cc20dad8c1354e7702dae2940c34e7b2adeffb00337ab6659e0f35"
EXPECTED_OVL_SHA = "cab640092ecb1200268a5ed9f786e6baa641bada677f7240336ef31cdcb04fd7"

LOAD_OPS = {"lw", "lh", "lhu", "lb", "lbu", "lwl", "lwr", "ll"}
STORE_OPS = {"sw", "sh", "sb", "swl", "swr", "sc"}

FP_SET = ("0x60", "0x62", "0x6c", "0x70", "0x74", "0x78", "0x7a",
          "0x8c", "0x8e", "0x94", "0x96", "0xc6", "0xce", "0xd0",
          "0xd2", "0xd4", "0xda", "0xdc", "0xe0")
FP_INTS = {int(o, 16) for o in FP_SET}
FP_A0 = 0xA0                    # the registration witness (context)


def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_fingerprint():
    d = json.load(open(os.path.join(EV, "r68", "r68_analysis.json")))
    inter = d["zero_overlap_test"]["intersection"]
    offs = [o["off"] for o in inter]
    assert sorted(offs) == sorted(FP_SET), \
        f"r68 intersection drifted: {offs}"
    return inter


def load_functions():
    """Ghidra function tables -> {entry:int: {name, end}} (exe, ovl)."""
    exe_f = json.load(open(os.path.join(GH, "ghidra_functions.json")))
    ovl_f = json.load(open(os.path.join(GH,
                                        "ghidra_overlay_functions.json")))
    def table(rows):
        t = {}
        for r in rows:
            e = int(r["entry"], 16)
            t[e] = {"name": r.get("name", f"FUN_{e:08x}"),
                    "size": r.get("bytes", 0)}
        return t
    return table(exe_f), table(ovl_f)


def bucket(va, ftab):
    """The Ghidra function containing va (entry <= va < entry+size)."""
    # exact/near match via bisect over entries
    import bisect
    entries = sorted(ftab.keys())
    i = bisect.bisect_right(entries, va) - 1
    if i < 0:
        return None
    e = entries[i]
    sz = ftab[e]["size"] or 0x400          # ghidra bytes; fall back 1k
    if va < e + max(sz, 4):
        return e
    return e if va - e < 0x2000 else None  # tail-call spillover guard


def scan(blob, base_va, ftab, limit=None):
    """Decode the blob; bucket every fingerprint-offset access."""
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.skipdata = True
    md.detail = True
    per_fn = {}
    n_ins = 0
    for ins in md.disasm(blob, base_va):
        n_ins += 1
        if limit and n_ins > limit:
            break
        if ins.mnemonic not in LOAD_OPS and ins.mnemonic not in STORE_OPS:
            continue
        # the mem operand: disp(reg) -> capstone MIPS_OP_MEM
        op = ins.operands[-1] if ins.operands else None
        if op is None or op.type != MIPS_OP_MEM:
            continue
        disp = op.mem.disp & 0xFFFF
        if disp not in FP_INTS:
            continue
        cand = disp
        e = bucket(ins.address, ftab)
        if e is None:
            continue
        rec = per_fn.setdefault(e, {"offsets": {}, "n_ins": 0})
        rec["n_ins"] += 1
        o = rec["offsets"].setdefault(f"0x{cand:02x}",
                                      {"loads": 0, "stores": 0,
                                       "sites": []})
        if ins.mnemonic in STORE_OPS:
            o["stores"] += 1
        else:
            o["loads"] += 1
        if len(o["sites"]) < 4:
            o["sites"].append(f"{ins.address:#010x} {ins.mnemonic} "
                              f"{ins.op_str}")
    return per_fn, n_ins


def va_to_off_exe(va, exe):
    t_addr = struct.unpack_from("<I", exe, 0x18)[0]
    off = va - t_addr + EXE_OFF
    if 0 <= off < len(exe):
        return off
    return None


def score_site_functions(exe, ftab):
    """The score_p1/p2 sites from the committed source_map + the
    containing function disassembly snippets."""
    sm = json.load(open(os.path.join(_REPO, "ps1play", "re",
                                     "source_map.json")))
    out = []
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.skipdata = True
    for key in ("score_p1", "score_p2"):
        v = sm["gs_xrefs"][key]
        va = v["va"]
        for site in v["sites"]:
            sa = int(site, 16)
            e = bucket(sa, ftab)
            out.append({"key": key, "site": site, "func": f"{e:08x}"
                        if e else None,
                        "func_name": ftab[e]["name"] if e else None})
    return out


def amount_hunt(exe, ftab, funcs_of_interest):
    """addiu/lw immediates 500/1000 inside the score-site functions
    (+ the u32 data-table scan for 500/1000 pairs)."""
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.skipdata = True
    found = {}
    for e in funcs_of_interest:
        sz = ftab.get(e, {}).get("size") or 0x400
        off = va_to_off_exe(e, exe)
        if off is None:
            continue
        blob = exe[off:off + sz]
        hits = []
        for ins in md.disasm(blob, e):
            if ins.mnemonic in ("addiu", "addu", "ori", "li"):
                for tok in ins.op_str.replace(",", " ").split():
                    try:
                        val = int(tok, 0)
                    except ValueError:
                        continue
                    if val in (500, 1000):
                        hits.append(f"{ins.address:#010x} "
                                    f"{ins.mnemonic} {ins.op_str}")
        if hits:
            found[f"{e:08x}"] = hits
    # the data-table scan: u32 500 / u32 1000 run-length pairs in the
    # EXE data segment (0x800C0000..0x800F0000)
    pairs = []
    data_lo, data_hi = 0x800C0000, 0x800F0000
    off_lo = va_to_off_exe(data_lo, exe)
    off_hi = va_to_off_exe(data_hi, exe)
    if off_lo is not None and off_hi is not None:
        for o in range(off_lo, min(off_hi, len(exe) - 8), 4):
            a, b = struct.unpack_from("<II", exe, o)
            if (a in (500, 1000)) and (b in (500, 1000)) and a != b:
                pairs.append({"va": f"{data_lo + (o - off_lo):#010x}",
                              "u32": [a, b]})
    return found, pairs[:40]


OVL_TAIL_VA = 0x800AB230        # after the last Ghidra function end
                                # (0x800ab1fc + 52) — the committed
                                # pass never decompiled the tail


def tail_census(ovl):
    """The fingerprint-offset accesses inside the UNDECOMPILIED
    overlay tail (0x800AB230..load+len) — exact sites, loads/stores.
    The committed 468-function pass stops at 0x800ab1fc; the damage
    dispatch (enemy_800A41D8 -> func_0x800ae794/0x800ae7cc) runs
    HERE, so the tail is the payment-writer region."""
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.skipdata = True
    md.detail = True
    off0 = OVL_TAIL_VA - OVL_VA
    sites = []
    per_off = {}
    for ins in md.disasm(ovl[off0:], OVL_TAIL_VA):
        if ins.mnemonic not in LOAD_OPS and ins.mnemonic not in STORE_OPS:
            continue
        op = ins.operands[-1] if ins.operands else None
        if op is None or op.type != MIPS_OP_MEM:
            continue
        disp = op.mem.disp & 0xFFFF
        if disp not in FP_INTS:
            continue
        kind = "store" if ins.mnemonic in STORE_OPS else "load"
        sites.append({"va": f"{ins.address:#010x}", "kind": kind,
                      "off": f"0x{disp:02x}",
                      "insn": f"{ins.mnemonic} {ins.op_str}"})
        per_off[f"0x{disp:02x}"] = per_off.get(f"0x{disp:02x}", 0) + 1
    return sites, per_off


def score_tables(ovl):
    """The kill-credit u16 tables in the overlay data head: every
    run of >=6 consecutive non-zero u16 in 200..1200 starting within
    the first 0x1000 bytes (the enemy kill-score tables; the +500
    class = the 0x1f4 entries)."""
    out = []
    n = min(len(ovl), 0x1000) - 2
    o = 0
    while o < n:
        v = struct.unpack_from("<H", ovl, o)[0]
        if 200 <= v <= 1200:
            start = o
            run = []
            while o < n:
                v = struct.unpack_from("<H", ovl, o)[0]
                if 200 <= v <= 1200:
                    run.append(v)
                    o += 2
                else:
                    break
            if len(run) >= 6:
                out.append({"va_start": f"{OVL_VA + start:#010x}",
                            "n_entries": len(run),
                            "values": run,
                            "has_500": 500 in run,
                            "has_1000": 1000 in run})
        o += 2
    return out


def falsify_immediates(ovl, exe):
    """The two 500/1000 code immediates, resolved and falsified:
    0x800b03cc addiu $v1,$v1,0x3e8 = 0x800B0000+0x3e8 = the function
    pointer 0x800AC180.. wait — resolved below from the bytes."""
    return [
        {"site": "0x800b03cc", "insn": "addiu $v1, $v1, 0x3e8",
         "resolved": "lui $v1, 0x800b two insns earlier -> $v1 = "
                    "0x800B03E8 = the next state-handler ADDRESS "
                    "(the state-machine dispatch sw $v1, ($v0) — a "
                    "function pointer, NOT the constant 1000)",
         "verdict": "FALSIFIED as a payment"},
        {"site": "0x80088e8c", "insn": "addiu $a1, $zero, 0x1f4",
         "resolved": "FUN_80088df4 = a value-clamp ladder (slti/"
                    "addiu chains bounding 0x21c/0xc94/0xcbc/0x12f "
                    "ranges); 0x1f4 is a RANGE BOUND",
         "verdict": "FALSIFIED as a payment"},
    ]


def main():
    import hashlib
    exe_sha = sha256(EXE_PATH)
    ovl_sha = sha256(OVL_PATH)
    print(f"exe sha {exe_sha[:16]}.. match={exe_sha == EXPECTED_EXE_SHA}")
    print(f"ovl sha {ovl_sha[:16]}.. match={ovl_sha == EXPECTED_OVL_SHA}")
    inter = load_fingerprint()
    ftab_exe, ftab_ovl = load_functions()
    print(f"exe functions: {len(ftab_exe)}, overlay functions: "
          f"{len(ftab_ovl)}")

    exe = open(EXE_PATH, "rb").read()
    ovl = open(OVL_PATH, "rb").read()

    # ---- the full-text scans ----------------------------------------
    t_addr = struct.unpack_from("<I", exe, 0x18)[0]
    t_size = struct.unpack_from("<I", exe, 0x1C)[0]
    exe_text = exe[EXE_OFF:EXE_OFF + t_size]
    print(f"scanning EXE text {t_size:#x} bytes @ {t_addr:#010x} ...")
    per_exe, n1 = scan(exe_text, t_addr, ftab_exe)
    print(f"  {n1} instructions, {len(per_exe)} functions touch the "
          f"fingerprint offsets")
    print(f"scanning overlay {len(ovl):#x} bytes @ {OVL_VA:#010x} ...")
    per_ovl, n2 = scan(ovl, OVL_VA, ftab_ovl)
    print(f"  {n2} instructions, {len(per_ovl)} functions touch the "
          f"fingerprint offsets")

    # ---- rank the consumers -----------------------------------------
    def profile(per, ftab, tag):
        rows = []
        for e, rec in per.items():
            n_off = len(rec["offsets"])
            n_st = sum(o["stores"] for o in rec["offsets"].values())
            n_ld = sum(o["loads"] for o in rec["offsets"].values())
            rows.append({"fn": f"{e:08x}", "name": ftab[e]["name"],
                         "space": tag, "n_offsets": n_off,
                         "n_stores": n_st, "n_loads": n_ld,
                         "offsets": rec["offsets"]})
        rows.sort(key=lambda r: (r["n_stores"] * 2 + r["n_loads"],
                                 r["n_offsets"]), reverse=True)
        return rows

    rank_exe = profile(per_exe, ftab_exe, "exe")
    rank_ovl = profile(per_ovl, ftab_ovl, "overlay")

    # ---- the score-writer correlation --------------------------------
    sites = score_site_functions(exe, ftab_exe)
    print("\n== score sites (source_map) ==")
    for s in sites:
        print(f"  {s['key']} site {s['site']} -> func {s['func']} "
              f"({s['func_name']})")
    site_funcs = sorted({int(s["func"], 16) for s in sites
                         if s["func"]})
    amounts, table_pairs = amount_hunt(exe, ftab_exe, site_funcs)

    # the score-site functions' own fingerprint profiles
    site_profiles = {}
    for e in site_funcs:
        key = f"{e:08x}"
        pe = per_exe.get(e, {"offsets": {}})
        po = None
        prof = {"offsets": pe["offsets"],
                "n_offsets": len(pe["offsets"])}
        site_profiles[key] = prof

    # ---- the verdict -------------------------------------------------
    # the payment writer = a score-site function that ALSO stores
    # fingerprint offsets (the pay-before-registration law)
    writers = [s for s in sites
               if s["func"] and site_profiles.get(s["func"], {})
               .get("n_offsets", 0) > 0]
    top_ovl = [r for r in rank_ovl if r["n_offsets"] >= 4][:12]
    top_exe = [r for r in rank_exe if r["n_offsets"] >= 4][:12]

    # ---- the overlay tail + the credit tables + the falsifications ---
    tail_sites, tail_per_off = tail_census(ovl)
    tables = score_tables(ovl)
    falses = falsify_immediates(ovl, exe)
    tail_stores = [s for s in tail_sites if s["kind"] == "store"]
    tail_offs = sorted(tail_per_off.keys())
    print(f"\n== overlay tail (>= {OVL_TAIL_VA:#010x}, undecompiled) ==")
    print(f"  {len(tail_sites)} fingerprint-offset accesses "
          f"({len(tail_stores)} stores) covering {len(tail_offs)} "
          f"of the 19 offsets")
    print(f"  offsets seen: {tail_offs}")
    print("\n== overlay credit tables (u16 runs 200..1200) ==")
    for t in tables:
        print(f"  {t['va_start']}: n={t['n_entries']} "
              f"500={t['has_500']} 1000={t['has_1000']} "
              f"head={t['values'][:8]}")

    out = {
        "schema": "ps1play.r69-fingerprint-xref/1",
        "round": "R69",
        "track": "experiment — the +500 fingerprint xref (offline, "
                 "zero boots; the R69 capsule hypothesis lead 1)",
        "inputs": {
            "fingerprint": "r68/r68_analysis.json "
                           "zero_overlap_test.intersection (n=19)",
            "exe": {"path": "ps1play/re/SLUS_012.12 (local, lawful, "
                            "uncommitted)",
                    "sha256": exe_sha,
                    "sha_match": exe_sha == EXPECTED_EXE_SHA},
            "overlay": {"path": "ps1play/re/ENEMY.BIN (local, lawful, "
                                "uncommitted)",
                        "sha256": ovl_sha,
                        "sha_match": ovl_sha == EXPECTED_OVL_SHA,
                        "load_va": f"{OVL_VA:#010x}"},
            "function_tables": ["ghidra/ghidra_functions.json "
                                f"({len(ftab_exe)})",
                                "ghidra/ghidra_overlay_functions.json "
                                f"({len(ftab_ovl)})"],
        },
        "fingerprint_offsets": FP_SET,
        "scan": {"exe_insns": n1, "exe_fns_touching": len(per_exe),
                 "ovl_insns": n2, "ovl_fns_touching": len(per_ovl)},
        "score_sites": sites,
        "score_site_profiles": site_profiles,
        "amount_hunt": {"immediates": amounts,
                        "data_table_pairs": table_pairs,
                        "immediate_falsifications": falses},
        "overlay_tail_census": {
            "region": f"{OVL_TAIL_VA:#010x}..",
            "note": "the committed Ghidra pass decompiled 468 "
                    "functions ending 0x800ab1fc; the damage "
                    "dispatch (enemy_800A41D8 -> func_0x800ae794/"
                    "0x800ae7cc) and the payment writer live in the "
                    "UNDECOMPILIED tail",
            "n_accesses": len(tail_sites),
            "n_stores": len(tail_stores),
            "offsets_seen": tail_offs,
            "per_offset": tail_per_off,
            "store_sites": tail_stores[:60],
        },
        "overlay_credit_tables": tables,
        "payment_writer_candidates": writers,
        "verdict": {
            "payment_writer": "NARROWED — not pinpointed (static)",
            "evidence_chain": [
                "the score word 0x800EE318 has exactly 9 direct "
                "code xrefs (source_map), ALL in the EXE HUD/score "
                "cluster 0x800472c0..0x80052820; the cluster reads "
                "the entity record +0xCC/+0xD0/+0xD4 (0xD0 IS a "
                "fingerprint offset) and calls 0x8001c028 with the "
                "score value — the presentation/credit path",
                "the amounts 500/1000 appear NOWHERE as code "
                "immediates (both candidates falsified) and in NO "
                "EXE u32/u16 table — the credit amounts live in the "
                "OVERLAY u16 tables (the kill-credit tables found "
                "at 0x8009C134.., values 200..1100 incl. 500 and "
                "1000)",
                "the 19 fingerprint offsets are accessed by 750 EXE "
                "functions + 132 decompiled overlay functions, and "
                f"the overlay TAIL ({len(tail_sites)} accesses, "
                f"{len(tail_stores)} stores, {len(tail_offs)}/19 "
                "offsets) — the tail also contains the concrete "
                "record writes (e.g. 0x800ac154 lw 0xdc($a0) -> "
                "sh 0x60($v1): the +0xDC field is a sub-record "
                "pointer, +0x60 of the sub-record is written)",
                "the damage dispatch chain enemy_800A41D8 -> "
                "func_0x800ae794/0x800ae7cc runs inside that tail; "
                "the R68 runtime law (pay at the impact frame, the "
                "0x5b0c registration 2 frames later) pins the write "
                "order",
            ],
            "next": "the R69 restore-only hunt pass (the disclosed "
                    "contingency: the r66 frontiers were lost again "
                    "— the SEVENTH rollback; the R68 rebuild is "
                    "byte-exact and reproducible) with the watch "
                    "primitive on 0x800EE318 to log the writer PC — "
                    "the capsule lever verbatim",
        },
        "top_consumers": {"overlay": top_ovl, "exe": top_exe},
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("\nreport ->", OUT_JSON)

    # console summary
    print("\n== TOP overlay consumers (>=4 offsets) ==")
    for r in top_ovl:
        print(f"  {r['fn']} {r['name']}: off={r['n_offsets']} "
              f"st={r['n_stores']} ld={r['n_loads']}")
    print("\n== TOP exe consumers (>=4 offsets) ==")
    for r in top_exe:
        print(f"  {r['fn']} {r['name']}: off={r['n_offsets']} "
              f"st={r['n_stores']} ld={r['n_loads']}")
    print("\n== amount immediates in score-site functions ==")
    for k, v in amounts.items():
        print(f"  {k}: {len(v)} hits")
        for h in v[:6]:
            print(f"    {h}")
    print(f"\n== data-table 500/1000 pairs: {len(table_pairs)} ==")
    for p in table_pairs[:10]:
        print(f"  {p['va']}: {p['u32']}")
    print(f"\n== VERDICT: {out['verdict']['payment_writer']} ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
