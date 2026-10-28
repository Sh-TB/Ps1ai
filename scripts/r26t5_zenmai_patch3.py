#!/usr/bin/env python3
"""r26t5_zenmai_patch3.py — build the delay-loop-free zenmai disc.

ROOT CAUSE (static RE, r26t4, no boot cost): zenmai's pad_exchange has
a 60-iteration (~360-cycle) delay loop between its per-byte RX read and
the next TX write (VA 0x8001B4B4..0x8001B4EC, 15 instruction slots).
On beetle/mednafen the RX read RE-ARMS and RESTARTS a receive transfer,
and ReceiveInProgress clocks the pad WITHOUT transmit (frontio.c clocks
all four ports unconditionally) — so during the delay gap the pad gets
~2.6 extra clock edges and its byte alignment corrupts: rx[1] reads
0x43-class garbage instead of the 0x41 pad ID, the game's adaptive
length logic mis-sizes the exchange, and the button bytes never land in
the right slots -> input dead (matches boots 1-2: zero RAM response).

FIX (game-side, disclosed, patch #3): NOP the 15 delay slots so the
read->TX sequence is back-to-back. The resulting flow is then
byte-equivalent to scripts/make_padtest_hw.py's core-verified protocol
(CTRL=0 -> CTRL=TXEN|DTR|RXEN -> sync read -> TX/wait/read per byte),
which was PROVEN against this exact core build in r21.

Build: zenmai-zork-r21b.psexe (patches 1+2) + NOP region -> 
zenmai-zork-r26.psexe -> iso9660_min wrap + MSX license sectors ->
zenmai_lic_r26.bin/.cue (local-only, never committed).
"""
import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import iso9660_min  # noqa: E402

OUT_DIR = "/home/z/my-project/emu/games_homebrew/patched"
SRC = os.path.join(OUT_DIR, "zenmai-zork-r21b.psexe")
DST_EXE = os.path.join(OUT_DIR, "zenmai-zork-r26.psexe")
MSX = os.environ.get("M1_RETAIL_BIN",
                     "/home/z/my-project/emu/game/Metal Slug X (USA).bin")

REGION_VA = 0x8001B4B4
REGION_END_VA = 0x8001B4F0          # exclusive
HDR = 0x800
BASE = 0x80010000
NOP = bytes.fromhex("00000000")


def main():
    exe = bytearray(open(SRC, "rb").read())
    off = HDR + (REGION_VA - BASE)
    end = HDR + (REGION_END_VA - BASE)
    cur = bytes(exe[off:end])
    print(f"region {REGION_VA:#x}..{REGION_END_VA:#x} "
          f"(file {off:#x}..{end:#x}): {len(cur)} bytes")
    print("first 16:", cur[:16].hex(), "last 16:", cur[-16:].hex())
    # expected: sw/lw/slti/beqz sequence per the disassembly
    assert cur[:4] == bytes.fromhex("0000a9af"), cur[:4].hex()  # sw t1,(sp)
    assert cur[4:8] == bytes.fromhex("0000a38f"), cur[4:8].hex()  # lw v1,(sp)
    assert cur[12:16] == bytes.fromhex("3c006328"), cur[12:16].hex()  # slti
    exe[off:end] = NOP * ((end - off) // 4)
    exe = bytes(exe)
    with open(DST_EXE, "wb") as f:
        f.write(exe)
    print(f"wrote {DST_EXE} sha256={hashlib.sha256(exe).hexdigest()}")

    cnf = (b"BOOT = cdrom:\\ZENMAI.EXE;1\nTCB = 4\nEVENT = 10\n"
           b"STACK = 801FFF00\n")
    bin_data, cue = iso9660_min.build_image(
        [("SYSTEM.CNF", cnf), ("ZENMAI.EXE", exe)])
    lic = open(MSX, "rb").read(16 * 2352)
    assert b"Sony Computer Entertainment" in lic
    bin_data = bytearray(bin_data)
    bin_data[:16 * 2352] = lic
    bin_data = bytes(bin_data)
    bin_path = os.path.join(OUT_DIR, "zenmai_lic_r26.bin")
    with open(bin_path, "wb") as f:
        f.write(bin_data)
    with open(os.path.join(OUT_DIR, "zenmai_lic_r26.cue"), "w") as f:
        f.write(cue.replace('"image.bin"', '"zenmai_lic_r26.bin"'))
    print(f"wrote {bin_path}: {len(bin_data)} bytes "
          f"sha256={hashlib.sha256(bin_data).hexdigest()}")


if __name__ == "__main__":
    main()
