#!/usr/bin/env python3
"""Build a jal reverse-call index for the resident EXE text, then resolve the
functions containing the score writes (0x8005C734 cluster + 0x8004F/0x80051
cluster) and list their callers."""
import struct
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

EXE = "/home/z/my-project/work/msx_recomp/SLUS_012.12.full"
EXE_VA = 0x80010000
EXE_HDR = 0x800
exe = open(EXE, "rb").read()
text = exe[EXE_HDR:EXE_HDR + (0x8009C0E8 - EXE_VA)]

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

# 1) collect all jal targets
callers = {}
insns = list(md.disasm(text, EXE_VA))
print(f"disassembled {len(insns)} insns")
for i, insn in enumerate(insns):
    if insn.mnemonic == "jal":
        try:
            tgt = int(insn.op_str, 16)
        except ValueError:
            continue
        callers.setdefault(tgt, []).append(insn.address)

def func_start_of(va, back=400):
    """Walk backwards to a function entry heuristic: addiu sp,sp,-N followed
    by sw ra,(sp) or entry after a jr/epilogue."""
    idx = (va - EXE_VA) // 4
    for j in range(idx, max(0, idx - back), -1):
        ins = insns[j]
        if ins.mnemonic == "addiu" and ins.op_str.startswith("$sp, $sp, -"):
            # check previous is a jr/epilogue or function boundary
            if j > 0 and insns[j - 1].mnemonic in ("jr", "j", "eret"):
                return ins.address
            # common prologue: addiu sp then next sw ra
            if j + 1 < len(insns) and "ra" in insns[j + 1].op_str:
                return ins.address
    return None

for site in (0x8005C734, 0x8004F70C, 0x800500EC, 0x8005029C, 0x80050488, 0x800518B8):
    fs = func_start_of(site)
    print(f"\nscore-use site {site:08X}: func start ~ {fs and f'{fs:08X}'}")
    if fs:
        cl = callers.get(fs, [])
        print(f"  direct jal callers: {[f'{c:08X}' for c in cl]}")

# 2) also: who calls 0x8005C430 (score_add)? scan ALL jal targets landing there
print("\njal targets == 0x8005C430:", [f'{c:08X}' for c in callers.get(0x8005C430, [])])
print("jal targets == 0x8005C4B4:", [f'{c:08X}' for c in callers.get(0x8005C4B4, [])])
print("jal targets == 0x8005C6A0..C760 candidates:",
      {f'{t:08X}': len(c) for t, c in callers.items() if 0x8005C600 <= t <= 0x8005C780})
