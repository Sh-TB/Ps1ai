#!/usr/bin/env python3
"""msx_gate_static5.py — locate the module containing 0x800B57FC:
read each module's PS-X EXE header from the raw MODE2/2352 disc image."""
import struct

BIN = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
SECT = 2352
DATA_OFF = 24          # MODE2/2352: 24-byte header (12 sync + 4 head + 8 sub)
# user data area of MODE2 XA form1: bytes 24..24+2048? For simplicity:
# form1 user data at offset 24, 2048 bytes (0x18..0x818)
MODULES = {  # from re_index files table: name -> lba
    "BONUS.BIN": 2866, "ENDING.BIN": 2896, "ENEMY.BIN": 2758,
    "LOADING.BIN": 2910, "MCARD.BIN": 2912, "MISSION.BIN": 2815,
    "RANKING.BIN": 2826, "TITLE.BIN": 2853, "X09.BIN": 23,
}
TARGETS = [0x800B57FC, 0x800BADBC, 0x800BAF1C, 0x800BB9C8, 0x800BBFEC,
           0x800BC34C, 0x800BABCC, 0x800B9F5C, 0x800B9F5C]
DISC = open(BIN, "rb").read()

for name, lba in MODULES.items():
    off = lba * SECT + DATA_OFF
    hdr = DISC[off:off + 2048]
    if not hdr.startswith(b"PS-X EXE"):
        print(f"{name}: no PS-X EXE header ({hdr[:8]!r})")
        continue
    pc0, t_addr, t_size = struct.unpack("<I", hdr[0x10:0x14])[0], \
        struct.unpack("<I", hdr[0x18:0x1C])[0], \
        struct.unpack("<I", hdr[0x1C:0x20])[0]
    span = (t_addr, t_addr + t_size)
    inside = [hex(t) for t in TARGETS if span[0] <= t < span[1]]
    print(f"{name}: pc0={pc0:#x} t_addr={t_addr:#x} t_size={t_size:#x} "
          f"span={hex(span[0])}-{hex(span[1])}"
          + (f"  CONTAINS: {inside}" if inside else ""))
