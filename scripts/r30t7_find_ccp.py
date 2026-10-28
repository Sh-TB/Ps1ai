#!/usr/bin/env python3
"""r30t7_find_ccp.py — locate the ChangeClearPAD(0) call site in the
BuzzyBee EXE (zero boots, static only).

Context: Tetrade (ChangeClearPAD(1)) input works TODAY on this exact
core+host; BuzzyBee/doukutsu (ChangeClearPAD(0)) receive no button bits.
The kernel pad poll is alive (padbuf actively overwritten with released
state) but the interrupt-driven poll never sees our buttons. Tetrade's
source comment: ChangeClearPAD(1) "Avoids VSync: Timeout caused by
StartPAD()" - it changes the kernel's automatic PAD-interrupt clearing.

PsyQ B-function call convention: li $t1, <num>; syscall. The in_init
sequence is: InitPAD(buf1,34,buf2,34); ...; StartPAD(); ChangeClearPAD(0);
The last li $a0/$a1-imm before each syscall identifies the function.
ChangeClearPAD = B(0x4D)? - verified empirically: the B-number whose call
site is immediately preceded by `li $a0, 0` inside in_init.
"""
import struct
import sys

EXE = "/home/z/my-project/emu/games_homebrew/candidates_r23/BuzzyBee.ps-exe"
data = open(EXE, "rb").read()
t_addr = struct.unpack("<I", data[0x10:0x14])[0]
t_size = struct.unpack("<I", data[0x18:0x1C])[0]
print(f"pc0={t_addr:08X} t_size={t_size:X}")
text = data[0x800:0x800 + t_size]

try:
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN
except ImportError:
    sys.exit("capstone missing")

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
md.detail = False

# find all syscall instructions and print a window before each
insns = list(md.disasm(text, t_addr))
print("insns:", len(insns))
sites = []
for idx, ins in enumerate(insns):
    if ins.mnemonic == "syscall":
        lo = max(0, idx - 8)
        win = insns[lo:idx + 1]
        txt = "; ".join(f"{i.mnemonic} {i.op_str}" for i in win)
        sites.append((ins.address, txt))

print("syscall sites:", len(sites))
for a, txt in sites:
    if "t1" in txt or "addiu" in txt or "li" in txt:
        print(f"--- {a:08X}: {txt}")
