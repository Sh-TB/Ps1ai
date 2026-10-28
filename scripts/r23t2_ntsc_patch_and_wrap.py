#!/usr/bin/env python3
"""r23t2_ntsc_patch_and_wrap.py — force-NTSC build of BuzzyBee v1.0 HEAD
EXE + full disc wrap (data + CDDA track 2) + local license sectors.

WHY (disclosed, r21/r22 patch-disclosure policy):
  Boot 1/2 (repo EXE, no audio track): EXE loaded + alive + input state
  machine ran (gameState 0->1->99 anchored) but the display stayed BLACK
  (384x240 frames). Boot 3 (author v1.1 image with its CDDA track): SAME
  black screen, input still live. Static RE: engine/graphics.c compiles
  setScreenMode into PAL-ONLY code (SCREEN_HEIGHT=256 stored
  unconditionally @0x80011C2C, SetVideoMode(1) @0x80011C44). No accepted
  game on this backend has ever forced PAL; suspect = the PAL display
  path (beetle+OpenBIOS). Decisive experiment: force NTSC with TWO
  instructions and see whether the game renders.

  The patch is GAME-SIDE, byte-precise, and disclosed everywhere the
  artifact is referenced. The unpatched EXE (sha256 9b0bfc08...c909a8ba)
  remains the reference artifact.

Patch 1 @VA 0x80011C24 (file off 0x11424):
    addiu $v1,$zero,0x100  (SCREEN_HEIGHT=256, PAL)  -> 0x00F0 (240)
Patch 2 @VA 0x80011C44 (file off 0x11444):
    addiu $a0,$zero,1      (SetVideoMode(1)=PAL)     -> SetVideoMode(0)=NTSC

Output: emu/games_homebrew/patched/buzzybee_ntsc_lic.bin/.cue (LOCAL ONLY).
"""
import hashlib
import os
import struct
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import iso9660_min  # noqa: E402

SRC = "/home/z/my-project/emu/games_homebrew/candidates_r23/BuzzyBee.ps-exe"
SRC_SHA = "9b0bfc089c33d6116f2e67436254a4ced6e26275a7cac83f5f0dda95c909a8ba"
MSX = "/home/z/my-project/emu/game/Metal Slug X (USA).bin"
OUT_DIR = "/home/z/my-project/emu/games_homebrew/patched"
BIN_NAME = "buzzybee_ntsc_lic.bin"
SEC = 2352
USER = 2048
AUDIO_SECONDS = 60


def msf(lba):
    t = lba + 150
    return f"{t // (75 * 60):02d}:{(t // 75) % 60:02d}:{t % 75:02d}"


def patch_exe(data):
    h = hashlib.sha256(data).hexdigest()
    assert h == SRC_SHA, f"EXE sha mismatch: {h}"
    # patch 1: SCREEN_HEIGHT immediate
    off1 = 0x80011C24 - 0x80010000 + 0x800
    old1 = bytes.fromhex("00010324")      # addiu $v1,$zero,0x100 (0x24030100)
    new1 = bytes.fromhex("f0000324")      # addiu $v1,$zero,0x00f0
    assert data[off1:off1 + 4] == old1, \
        f"patch1 site mismatch: {data[off1:off1+4].hex()}"
    # patch 2: SetVideoMode argument
    off2 = 0x80011C44 - 0x80010000 + 0x800
    old2 = bytes.fromhex("01000424")      # addiu $a0,$zero,1
    new2 = bytes.fromhex("00000424")      # addiu $a0,$zero,0
    assert data[off2:off2 + 4] == old2, \
        f"patch2 site mismatch: {data[off2:off2+4].hex()}"
    d = bytearray(data)
    d[off1:off1 + 4] = new1
    d[off2:off2 + 4] = new2
    print(f"patched: SCREEN_HEIGHT 256->240 @0x80011C24, "
          f"SetVideoMode 1->0 @0x80011C44")
    return bytes(d)


def main():
    exe = patch_exe(open(SRC, "rb").read())
    assert exe[:8] == b"PS-X EXE"
    sp = int.from_bytes(exe[0x30:0x34], "little")
    cnf = ("BOOT=cdrom:\\BUZZYBEE.EXE;1\r\n"
           "TCB=4\r\n"
           "EVENT=10\r\n"
           f"STACK={sp:08X}\r\n").encode()
    bin_data, _ = iso9660_min.build_image(
        [("SYSTEM.CNF", cnf), ("BUZZYBEE.EXE", exe)])
    m = len(bin_data) // SEC
    print(f"data track: {m} sectors")

    lic = open(MSX, "rb").read(16 * SEC)
    assert b"Sony Computer Entertainment" in lic, "MSX license not found"
    bin_data = bytearray(bin_data)
    bin_data[:16 * SEC] = lic

    # audio track 2: 2 s pregap + 60 s silence PCM (DsPlay(2) success path)
    pcm = b"\x00" * (44100 * 4 * AUDIO_SECONDS)
    n_pcm = (len(pcm) + SEC - 1) // SEC
    pregap_lba, idx01_lba = m, m + 150
    bin_data += b"\x00" * (150 * SEC)
    bin_data += pcm + b"\x00" * (-len(pcm) % SEC)
    bin_data = bytes(bin_data)
    cue = (f'FILE "{BIN_NAME}" BINARY\n'
           f"  TRACK 01 MODE2/2352\n"
           f"    INDEX 01 00:02:00\n"
           f"  TRACK 02 AUDIO\n"
           f"    INDEX 00 {msf(pregap_lba)}\n"
           f"    INDEX 01 {msf(idx01_lba)}\n")
    os.makedirs(OUT_DIR, exist_ok=True)
    bin_path = os.path.join(OUT_DIR, BIN_NAME)
    with open(bin_path, "wb") as f:
        f.write(bin_data)
    with open(bin_path.replace(".bin", ".cue"), "w") as f:
        f.write(cue)
    print(f"wrote {bin_path}: {len(bin_data)} B ({len(bin_data)//SEC} "
          f"sectors) sha256={hashlib.sha256(bin_data).hexdigest()}")
    print(f"audio track 2 INDEX 01 @ LBA {idx01_lba} = MSF {msf(idx01_lba)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
