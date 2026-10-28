#!/usr/bin/env python3
"""r26t4_zenmai_re.py — static disassembly of zenmai's pad_exchange
(file offsets 0xBB60.., VA 0x8001B360..) to READ the actual SIO flow:
per-exchange CTRL writes, the wait predicate, byte counts, result store
address. No boot cost — pure static analysis of the patched r21b EXE.
"""
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
except ImportError:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

EXE = ("/home/z/my-project/emu/games_homebrew/patched/"
       "zenmai-zork-r21b.psexe")
HDR = 0x800
BASE = 0x80010000

data = open(EXE, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True


def dis(file_off, n, label):
    print(f"=== {label} (file {file_off:#x}, VA {BASE + file_off - HDR:#x})")
    code = data[file_off:file_off + n * 4]
    for i in md.disasm(code, BASE + file_off - HDR):
        print(f"  {i.address:08x}: {i.bytes.hex()}  {i.mnemonic} {i.op_str}")


# 1. pad_exchange prologue + full body (generous window)
dis(0xBB40, 120, "pad_exchange region")
# 2. look further: wait loop + result store likely within next 60 insns
dis(0xBD00, 40, "continuation region 1")
# 3. success path beyond 0x8001b4a8 + chord logic + epilogue
dis(0xBCA8, 60, "success path 8001b4a8+")
# 4. caller scan: who calls 8001b360 (jal), and li v0,-1 pattern
import struct
hits = []
for off in range(HDR, len(data) - 4, 4):
    w = data[off:off + 4]
    if w == bytes.fromhex("ffff0224"):          # addiu $v0,$zero,-1
        hits.append(("li v0,-1", off))
print("=== li v0,-1 sites:", [(t, hex(o)) for t, o in hits[:12]])
