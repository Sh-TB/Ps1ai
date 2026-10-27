#!/usr/bin/env python3
"""r21t3_zenmai_patch.py — 8-byte SIO patch for zenmai (r21t3).

ROOT CAUSE (r20 INPUT_UNPROVEN -> r21 diagnosis):
  zenmai's pad_exchange() (native/plat_ps1.c, v1.5.0 == HEAD) polls the pad
  by bit-banging SIO registers with NO dummy JOY_DATA read before its first
  TX byte. The beetle/mednafen core (mednafen/psx/frontio.c) only arms the
  receiver via ReceivePending, which is set EXCLUSIVELY by a JOY_DATA READ
  (FrontIO_Read case 0x0). A TX-only start never sets ReceivePending, so
  ReceiveInProgress stays false, ReceiveBufferAvail (JOY_STAT bit1) never
  asserts, and zenmai's 2000-iteration wait for STAT&2 times out on byte 0
  -> pad_exchange returns n=0 -> pad_read() = -1 forever. Matches r20:
  zero RAM deltas, no menu response, backend healthy (Tetrade padbuff OK).

FIX (host-visible, game-side, 8 bytes):
  In pad_exchange prologue (VA 0x8001B364..0x8001B37C):
    0x8001B370  addiu $v1,$zero,0x0D   ->  lw $v1,0x1040($v0)   (dummy READ)
    0x8001B374  sh $v1,0x1048($v0)     ->  nop                  (load-delay gap)
  - The dummy read arms ReceivePending before the first TX write; after that
    zenmai's own read-per-byte keeps re-arming it (piggybacks on the TX
    trigger inside FrontIO_CheckStartStopPending).
  - Dropping JOY_MODE=0x000D is timing-neutral for this core:
    ClockDivider = MAX(0x20, Baudrate << ScaleShift[Mode&3]); 0x000D&3==1 ->
    ScaleShift 0, Mode 0 -> ScaleShift 0. Baudrate 0x88 unchanged.
  - JOY_CTRL stays 0x1003 (no RXEN): with RXEN unset the core cannot start
    a receive-only transfer at the CTRL write, so the armed ReceivePending
    cleanly piggybacks on the first TX byte.

Builds the patched PS-EXE and a minimal CD image (iso9660_min + MSX license
sectors, local-only, same route as r20t3_zenmai_wrap.py).
"""
import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import iso9660_min  # noqa: E402

SRC = "/home/z/my-project/emu/games_homebrew/zenmai-zork.psexe"
MSX = os.environ.get("M1_RETAIL_BIN",
                     "/home/z/my-project/emu/game/Metal Slug X (USA).bin")
OUT_DIR = "/home/z/my-project/emu/games_homebrew/patched"
EXE_NAME = "ZENMAI.EXE"

BASE = 0x80010000
HDR = 0x800

# patch site
VA = 0x8001B370
OLD = bytes.fromhex("0d000324" "481043a4")   # addiu $v1,0xD ; sh $v1,0x1048($v0)
NEW = bytes.fromhex("4010438c" "00000000")   # lw $v1,0x1040($v0) ; nop


def main():
    exe = bytearray(open(SRC, "rb").read())
    assert exe[:8] == b"PS-X EXE"
    import struct
    taddr, = struct.unpack_from("<I", exe, 0x18)
    off = HDR + (VA - taddr)
    cur = bytes(exe[off:off + 8])
    print(f"patch site VA {VA:#x} file {off:#x}: {cur.hex()}")
    assert cur == OLD, f"unexpected bytes at patch site: {cur.hex()}"
    exe[off:off + 8] = NEW
    exe = bytes(exe)
    print(f"patched: {NEW.hex()}  (dummy JOY_DATA read arms ReceivePending)")

    exe_path = os.path.join(OUT_DIR, "zenmai-zork-r21.psexe")
    with open(exe_path, "wb") as f:
        f.write(exe)
    print(f"wrote {exe_path} sha256={hashlib.sha256(exe).hexdigest()}")

    cnf = (f"BOOT = cdrom:\\{EXE_NAME};1\n"
           "TCB = 4\n"
           "EVENT = 10\n"
           "STACK = 801FFF00\n").encode()
    bin_data, cue = iso9660_min.build_image(
        [("SYSTEM.CNF", cnf), (EXE_NAME, exe)])
    lic = open(MSX, "rb").read(16 * 2352)
    assert b"Sony Computer Entertainment" in lic, "MSX license not found"
    bin_data = bytearray(bin_data)
    bin_data[:16 * 2352] = lic
    bin_data = bytes(bin_data)
    bin_path = os.path.join(OUT_DIR, "zenmai_lic_r21.bin")
    with open(bin_path, "wb") as f:
        f.write(bin_data)
    with open(os.path.join(OUT_DIR, "zenmai_lic_r21.cue"), "w") as f:
        f.write(cue.replace('"image.bin"', '"zenmai_lic_r21.bin"'))
    print(f"wrote {bin_path}: {len(bin_data)} bytes "
          f"sha256={hashlib.sha256(bin_data).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
