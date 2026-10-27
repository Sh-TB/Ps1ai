#!/usr/bin/env python3
"""r21t6 static RE for Poy Poy (SLUS_004.86): xref-scan address constants.

Goals (task r21t6 item 2, no emulator):
  1. Find readers/writers of the r20 live-position cluster region
     (RAM 0x8009F778/780/7B0/7EA) in the main EXE — settle whether the
     code references 0x8009F7xx (main-image tail) or 0x8019F7xx (the r20
     hint / possible overlay space).
  2. Find xrefs to the r19 per-fighter screen-position slots
     (1P 0x80142EF8, 2P 0x8013247C, 3P 0x801E12EC, 4P 0x80083114,
     camera 0x800A09CC) and map nearby struct offsets — leads for the
     per-fighter heart/HP counter array.

Method: linear constant tracker over little-endian MIPS I words.
  lui  rt, hi            -> regs[rt] = hi<<16 (provisional)
  addiu/ori rt, rs, imm  -> if rs known: regs[rt] = regs[rs] + s16(imm)
  lw/sw/lbu/lhu/sb/sh/lh with base rs known -> record ea = regs[rs]+s16(off)
Window-less full pass; branches ignored (approximation, disclosed).
Outputs JSON + printed buckets for the regions of interest.
"""
import json
import struct
import sys

EXE = "/home/z/my-project/ps1ai/scratch/r21t6_poypoy/SLUS_004.86.exe"
OUT = "/home/z/my-project/ps1ai/scratch/r21t6_poypoy/re_scan.json"
T_ADDR = 0x80010000

LOADS = {0x20: "lb", 0x21: "lh", 0x23: "lw", 0x24: "lbu", 0x25: "lhu"}
STORES = {0x28: "sb", 0x29: "sh", 0x2B: "sw"}


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def main():
    d = open(EXE, "rb").read()
    body = d[0x800:]                      # skip PS-EXE header
    n = len(body) // 4
    words = struct.unpack(f"<{n}I", body[:n * 4])

    regs = {}                             # reg -> constant value (provisional)
    xrefs = []                            # {ea, pc, kind, op}
    for i, w in enumerate(words):
        pc = T_ADDR + i * 4
        op = w >> 26
        rs = (w >> 21) & 31
        rt = (w >> 16) & 31
        imm = w & 0xFFFF
        if op == 0x0F:                    # lui rt, imm
            regs[rt] = (imm << 16) & 0xFFFFFFFF
        elif op == 0x09:                  # addiu rt, rs, imm
            if rs == rt:
                if rs in regs:
                    regs[rs] = (regs[rs] + s16(imm)) & 0xFFFFFFFF
            elif rs in regs:
                regs[rt] = (regs[rs] + s16(imm)) & 0xFFFFFFFF
            else:
                regs.pop(rt, None)
        elif op == 0x0D:                  # ori rt, rs, imm
            if rs == rt:
                if rs in regs:
                    regs[rs] = regs[rs] | imm
            elif rs in regs:
                regs[rt] = regs[rs] | imm
            else:
                regs.pop(rt, None)
        elif op in LOADS or op in STORES:
            if rs in regs:
                ea = (regs[rs] + s16(imm)) & 0xFFFFFFFF
                kind = "R" if op in LOADS else "W"
                xrefs.append({"ea": ea, "pc": pc, "op": LOADS.get(op, STORES.get(op)),
                              "kind": kind})
            # loads define rt; stores read rt — conservative: keep unknown
        elif op == 0x00 and (w & 0x3F) in (0x21, 0x23, 0x25, 0x20, 0x22, 0x24, 0x2A, 0x2B):
            regs.pop(rt, None)            # ALU writes rt -> invalidate

    json.dump({"n_xrefs": len(xrefs), "xrefs": xrefs}, open(OUT, "w"))

    def bucket(lo, hi, tag):
        hits = [x for x in xrefs if lo <= x["ea"] < hi]
        print(f"--- {tag} [{hex(lo)}..{hex(hi)}): {len(hits)} xrefs")
        for x in hits[:40]:
            print(f"    {x['op']} {hex(x['ea'])}  @pc {hex(x['pc'])} ({x['kind']})")
        return hits

    b1 = bucket(0x8009F700, 0x8009FA00, "r20 cluster as 0x8009F7xx")
    b2 = bucket(0x8019F700, 0x801A0200, "r20-hint region 0x8019F7xx/801A0xxx")
    b3 = bucket(0x80142E80, 0x80142F60, "1P slot 0x142EF8 +-0x40")
    b4 = bucket(0x80132400, 0x80132500, "2P slot 0x13247C +-0x40")
    b5 = bucket(0x801E1280, 0x801E1380, "3P slot 0x1E12EC +-0x40")
    b6 = bucket(0x800830C0, 0x80083180, "4P slot 0x083114 +-0x40")
    b7 = bucket(0x800A0980, 0x800A0A20, "camera 0x0A09CC +-0x20")
    # whole-image histogram of referenced pages (0x400 granularity), top 40
    from collections import Counter
    pages = Counter((x["ea"] >> 10) for x in xrefs)
    print("--- top pages (0x400) referenced via base+imm")
    for pg, c in pages.most_common(40):
        print(f"    {pg*0x400:08X} x{c}")
    json.dump({tag: [x for x in hits] for tag, hits in
               [("b1", b1), ("b2", b2), ("b3", b3), ("b4", b4),
                ("b5", b5), ("b6", b6), ("b7", b7)]},
              open(OUT.replace(".json", "_buckets.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
