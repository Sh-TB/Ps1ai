#!/usr/bin/env python3
"""r22t1R_rxen_patch.py — PREPARE (do NOT boot) the 2-instruction RXEN patch.

Status: **PREPARED, NOT BOOTED.** The evidence.md patch gate was "apply ONLY
if boot 1 shows the predicted dead input"; boot 1 REFUTED that prediction
(pad_buff[0]=41 5A FF FF, held=0, title stable) — see evidence.md §1. Boot 2
therefore runs the license-only image and this artifact is kept for the
record only. Rationale (frontio.c ~805-820): the TXEN trigger route admits
the ReceivePending branch, so the dummy read + TX write already produce
aligned, correct RX latching; adding RXEN would additionally start
receive-only transfers at every JOY_DATA read, misaligned to the wire byte
stream (risk of garbage pad data in beetle 0.9.44.1).

Patch (byte-for-byte same size, in-place inside the license-patched image):
  exe_off 0x2474: 03 10 42 34 -> 07 10 42 34  (ori $v0,$v0,0x1003->0x1007)
  exe_off 0x22BC: 13 10 63 34 -> 17 10 63 34  (ori $v1,$v1,0x1013->0x1017)
EXE payload starts at LBA 24, user data at sector*2352+24, 2048 B/sector.
Performs NO emulator boot (boot cap unaffected).
"""
import os
import shutil

SEC = 2352
GAME_WS = "/home/z/my-project/emu/games_homebrew"
SRC = os.path.join(GAME_WS, "patched", "mspsx_lic.bin")
DST = os.path.join(GAME_WS, "patched", "mspsx_lic_rxen.bin")
PATCHES = [(0x2474, bytes.fromhex("03104234"), bytes.fromhex("07104234")),
           (0x22BC, bytes.fromhex("13106334"), bytes.fromhex("17106334"))]


def disc_off(exe_off):
    return (24 + exe_off // 2048) * SEC + 24 + exe_off % 2048


def main():
    shutil.copyfile(SRC, DST)
    with open(DST, "r+b") as f:
        for exe_off, old, new in PATCHES:
            f.seek(disc_off(exe_off))
            got = f.read(4)
            assert got == old, f"exe_off 0x{exe_off:X}: got {got.hex()}, " \
                               f"expected {old.hex()}"
            f.seek(disc_off(exe_off))
            f.write(new)
    with open(DST, "rb") as f:
        for exe_off, old, new in PATCHES:
            f.seek(disc_off(exe_off))
            got = f.read(4)
            assert got == new, f"verify failed at 0x{exe_off:X}"
            print(f"exe_off 0x{exe_off:X} disc_off 0x{disc_off(exe_off):X}: "
                  f"{old.hex()} -> {got.hex()} OK")
    assert os.path.getsize(DST) == os.path.getsize(SRC), "size changed!"
    cue = DST.replace(".bin", ".cue")
    with open(cue, "w") as f:
        f.write('FILE "mspsx_lic_rxen.bin" BINARY\n'
                '  TRACK 01 MODE2/2352\n'
                '    INDEX 01 00:00:00\n'
                '  TRACK 02 AUDIO\n'
                '    INDEX 00 00:15:43\n'
                '    INDEX 01 00:17:43\n'
                '  TRACK 03 AUDIO\n'
                '    INDEX 00 01:57:19\n'
                '    INDEX 01 01:59:19\n'
                '  TRACK 04 AUDIO\n'
                '    INDEX 00 03:47:40\n'
                '    INDEX 01 03:49:40\n'
                '  TRACK 05 AUDIO\n'
                '    INDEX 00 06:33:41\n'
                '    INDEX 01 06:35:41\n')
    print(f"PREPARED {DST} (+cue), size unchanged, NOT booted "
          f"(gate closed by boot-1 refutation)")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
