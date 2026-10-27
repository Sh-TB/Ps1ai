#!/usr/bin/env python3
"""r19t2_static_scan.py — offline EXE scan for the mission-global & load flow.

Finds (pure static, no emulator):
  1. lui/addiu pairs referencing key data VAs (menu objects 0x800D4A48,
     label ptr 0x800D4A68, cursors 0x800D4A70/71, mode word 0x800D4210,
     mission var 0x800DAB3C, CD-table base 0x800841C4, menu ptr array
     0x80083518..0x8008355C).
  2. candidate mission->CD-row maps (bytes/u16/u32 runs of 0,1,5,7,8,12).
  3. 16B CD-table rows decoded (field3 = byte size per row, MEASURED check).
VA rule: VA = 0x80010000 + (off - 0x800).
"""
import json
import struct
import sys

EXE = "/home/z/my-project/emu/msx_extract_r18/SLUS_012.12"
data = open(EXE, "rb").read()


def off2va(off):
    return 0x80010000 + (off - 0x800)


def va2off(va):
    return va - 0x80010000 + 0x800


targets = {
    0x800D4A48: "menu_objects", 0x800D4A68: "label_ptr",
    0x800D4A70: "msel_cursor", 0x800D4A71: "menu_cursor",
    0x800D4210: "mode_word", 0x800DAB3C: "mission_var?",
    0x800841C4: "cd_table_row0", 0x80083518: "menu_ptr_array",
    0x80083538: "menu_ptr_m1", 0x800100C4: "str_mission1",
    0x80010E58: "mission_row_map",
}

# --- 1. lui/addiu pair scan (opcode 0x0F = lui, 0x09 = addiu) ---
hits = {}
for i in range(0, len(data) - 8, 4):
    w = struct.unpack_from("<I", data, i)[0]
    if (w & 0xFC000000) != 0x3C000000:
        continue
    hi = w & 0xFFFF
    if hi not in (0x8008, 0x800D, 0x8001, 0x800A):
        continue
    rt = (w >> 16) & 0x1F
    for j in range(1, 4):
        if i + 4 * j + 4 > len(data):
            break
        w2 = struct.unpack_from("<I", data, i + 4 * j)[0]
        if (w2 >> 26) == 0x09:                      # addiu
            rs = (w2 >> 21) & 0x1F
            imm = w2 & 0xFFFF
            if rs == rt and imm < 0x8000:
                va = (hi << 16) | imm
                if va in targets:
                    hits.setdefault(targets[va], []).append(
                        {"lui_va": hex(off2va(i)), "addiu_va": hex(off2va(i + 4 * j))})

# --- 2. mission->row map candidates: u8/u16/u32 runs (0,1,5,7,8,12) ---
maps = []
pats = {
    "u8": bytes([0, 1, 5, 7, 8, 12]),
    "u16": struct.pack("<6H", 0, 1, 5, 7, 8, 12),
    "u32": struct.pack("<6I", 0, 1, 5, 7, 8, 12),
}
for kind, pat in pats.items():
    start = 0
    while True:
        k = data.find(pat, start)
        if k < 0:
            break
        maps.append({"kind": kind, "off": hex(k), "va": hex(off2va(k))})
        start = k + 1

# --- 3. decode first 16 CD rows ---
rows = []
for r in range(16):
    o = va2off(0x800841C4) + 16 * r
    pva, dva, f3, f4 = struct.unpack_from("<IIII", data, o)
    so = va2off(pva) if 0x80010000 <= pva < 0x80020000 else None
    path = data[so:so + 24].split(b"\x00")[0].decode("ascii", "replace") if so else "?"
    rows.append({"i": r, "path": path, "dest": hex(dva), "f3": hex(f3),
                 "size": f4})

out = {"refs": hits, "row_maps": maps[:40], "rows16": rows}
json.dump(out, open("/home/z/my-project/ps1ai/scratch/r19t2_msx/static_scan.json", "w"), indent=1)
for k, v in hits.items():
    print(k, len(v), [h["lui_va"] for h in v[:14]])
print("row-map candidates:", len(maps))
for m in maps[:12]:
    print(" ", m)
print("rows16 f3/size:")
for r in rows:
    print(" ", r["i"], r["path"], r["dest"], r["f3"], r["size"])
