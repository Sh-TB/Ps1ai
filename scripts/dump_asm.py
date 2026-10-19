#!/usr/bin/env python3
"""dump_asm.py — disassemble the functions that touch the verified
globals (input pad, score, hit-slots) -> the game's actual source for
'what is an entity / who reads the pad / who adds score'."""
import os
import sys
from collections import defaultdict

import numpy as np
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

EXE = "/home/z/my-project/ps1play/re/SLUS_012.12"
OUT = "/home/z/my-project/ps1play/re"
T_ADDR = 0x80010000

text = open(EXE, "rb").read()[2048:]
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True


def dump(start_va, length, title, path):
    lo = start_va - T_ADDR
    code = text[lo:lo + length]
    lines = [f"; {title}  (start {start_va:#010x}, {length} bytes)"]
    for ins in md.disasm(code, start_va):
        lines.append(f"{ins.address:08X}: {ins.mnemonic:<8s} {ins.op_str}")
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print(f"wrote {path} ({len(lines)} lines)")
    return lines


def func_start(va, max_back=0x400):
    """Walk back to the likely function start: after a jr $ra + nop."""
    w = np.frombuffer(text, "<u4")
    i = (va - T_ADDR) // 4
    for k in range(i, max(0, i - max_back // 4), -1):
        if int(w[k]) == 0x03E00008:        # jr $ra
            return T_ADDR + (k + 1) * 4    # delay slot + start
    return va - 0x80


SITES = {
    "pad_reader":  0x80015714,
    "score_add":   0x8004732c,
    "hit_slot":    0x80042060,
    "pow_add":     0x80047a1c,
    "score_p2":    0x80052654,
}
for name, site in SITES.items():
    fs = func_start(site)
    dump(fs, 0x300, f"{name} (xref site {site:#x}, func start {fs:#x})",
         os.path.join(OUT, f"asm_{name}.asm"))
print("done")
