#!/usr/bin/env python3
"""r31t0_psxmc_ccp_patch.py — Round 31: the disclosed 1-instruction
ChangeClearPAD(0) -> (1) game-side patch for PSX-Minecraft.

MOTIVATION (R30 matrix, all disclosed): the kernel interrupt-driven pad
class InitPAD/StartPAD/ChangeClearPAD(0) lost button delivery after the
5th filesystem rollback (doukutsu + buzzybee probes: zero button bits;
kernel padbuf actively polled with released state). Tetrade, the only
ladder game calling ChangeClearPAD(1), still receives input today, and
its upstream source comment says (1) "Avoids 'VSync: Timeout' caused by
StartPAD()". PSX-Minecraft's source (src/core/input/input.c) calls
ChangeClearPAD(0) - the broken class.

THE PATCH (1 instruction, byte-precise, ELF-symbol located):
  inputInit @0x800104C4 (PSXMC.elf symbol, PSN00bSDK):
    0x800104E0  jal InitPAD      (0x80035634, sym)
    0x800104E8  jal StartPAD     (0x80035640, sym)
    0x800104F0  move $a0, $zero  (0x00002025)  <- argument for:
    0x800104F4  jal ChangeClearPAD (0x80035664, sym)
  patch: move $a0, $zero -> addiu $a0, $zero, 1  (0x24040001)

Output: patched/PSXMC_lic_ccp1.bin/.cue (LOCAL ONLY, from the licensed
image; the unpatched PSXMC_lic.bin remains the reference artifact).
"""
import hashlib
import os
import shutil

GAME_WS = "/home/z/my-project/emu/games_homebrew"
SRC = os.path.join(GAME_WS, "patched", "PSXMC_lic.bin")
DST = os.path.join(GAME_WS, "patched", "PSXMC_lic_ccp1.bin")
PATCH_VA = 0x800104F0
# locate by the surrounding instruction context (elf-verified):
# move $a0,$zero ; jal 0x80035664 (ChangeClearPAD) ; nop
# jal StartPAD ; nop ; move $a0,$zero ; jal ChangeClearPAD   (16 B,
# byte-verified against the ELF at VA 0x800104E8..0x800104F8 and located
# at file offset 0xEAB0 in the raw MODE2/2352 image)
CTX = bytes.fromhex("90d5000c") + bytes.fromhex("00000000") + \
    bytes.fromhex("25200000") + bytes.fromhex("99d5000c")
NEW = bytes.fromhex("01000424")  # addiu $a0, $zero, 1


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    data = bytearray(open(SRC, "rb").read())
    print(f"src: {SRC} {len(data)} bytes sha={sha(bytes(data))[:16]}...")
    hits = [i for i in range(len(data) - len(CTX))
            if bytes(data[i:i + len(CTX)]) == CTX]
    print("context pattern hits:", [hex(h) for h in hits])
    assert len(hits) == 1, f"expected exactly 1 hit, got {len(hits)}"
    off = hits[0] + 8   # the move $a0,$zero inside the 16B context
    assert bytes(data[off:off + 4]) == bytes.fromhex("25200000")
    data[off:off + 4] = NEW
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    open(DST, "wb").write(bytes(data))
    shutil.copyfile(SRC.replace(".bin", ".cue"), DST.replace(".bin", ".cue"))
    # fix the cue's FILE reference
    cue = DST.replace(".bin", ".cue")
    txt = open(cue).read().replace("PSXMC_lic.bin", "PSXMC_lic_ccp1.bin")
    open(cue, "w").write(txt)
    print(f"patched: {DST} sha={sha(bytes(data))[:16]}... "
          f"(file off {hex(off)}, VA {hex(PATCH_VA)} assumed)")
    print("OK")


if __name__ == "__main__":
    main()
