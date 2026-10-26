#!/usr/bin/env python3
"""Find worldGetBlock callers and the IBlock->id deref offset (static)."""
import struct

ELF = "/home/z/my-project/emu/games_homebrew/PSXMC.elf"
raw = open(ELF, "rb").read()
TEXT_VA, TEXT_OFF, TEXT_SZ = 0x80010000, 0x1000, 0x2C59E
WGB = 0x80025C4C                      # worldGetBlock
WJAL = 0x0C000000 | ((WGB >> 2) & 0x3FFFFFF)

callers = []
for i in range(TEXT_SZ // 4):
    w = struct.unpack_from("<I", raw, TEXT_OFF + i * 4)[0]
    if w == WJAL:
        callers.append(TEXT_VA + i * 4)
print("worldGetBlock callers:", [hex(c) for c in callers])

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)

# disassemble each caller + the 24 words after the jal
for c in callers[:6]:
    f = TEXT_OFF + (c - TEXT_VA)
    code = raw[f:f + 0x70]
    print(f"=== caller @ {c:#x} ===")
    for ins in md.disasm(code, c):
        mark = " <-- jal" if ins.address == c else ""
        print(f"  {ins.address:#x}: {ins.mnemonic:9s} {ins.op_str}{mark}")
