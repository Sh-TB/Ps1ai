#!/usr/bin/env python3
"""Dump the shared death-state handler 0x800151DC (retarget target of 17
overlay funcs) and the 4-caller function 0x8005C6D4 near a score write."""
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
import struct

EXE = "/home/z/my-project/work/msx_recomp/SLUS_012.12.full"
EXE_VA = 0x80010000
EXE_HDR = 0x800
exe = open(EXE, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

def dump(va0, va1, title):
    code = exe[EXE_HDR + (va0 - EXE_VA):EXE_HDR + (va1 - EXE_VA)]
    print(f"===== {title}: {va0:08X}..{va1:08X} =====")
    for insn in md.disasm(code, va0):
        print(f"  {insn.address:08X}: {insn.mnemonic:8s} {insn.op_str}")
    print()

# 1) shared death state handler
dump(0x800151DC, 0x80015300, "state_0x800151DC head")

# 2) 0x8005C6D4 and who jal's it
dump(0x8005C6D4, 0x8005C780, "func_8005C6D4")
text = exe[EXE_HDR:EXE_HDR + (0x8009C0E8 - EXE_VA)]
for off in range(0, len(text) - 3, 4):
    w = struct.unpack_from("<I", text, off)[0]
    if w >> 26 == 0x0C and ((w & 0x3FFFFFF) << 2) == (0x8005C6D4 & 0x0FFFFFFC):
        print(f"jal -> 0x8005C6D4 at {EXE_VA + off:08X}")
