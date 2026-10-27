#!/usr/bin/env python3
"""r21-t2 autogaz: cheap static RE on the boot EXE (no emulator).
EXE: scratch/r20t2_autogaz/autogaz_exe2.bin ("PS-X EXE", 706560 B,
t_addr 0x80010000, pc0 0x80018c6c). Goals (from the upstream source
egemenkus0/autogaz ps1/main.c, cloned read-only to /tmp/ag_src):
  - find the PadRead(0) call site and the button masks used (0x4000/0x2000)
  - disassemble libpad's PadRead to learn buffer address + word order +
    whether buttons are returned active-low (raw) or inverted (active-high)
  - find Timer()'s 476 (0x1DC) compare -> state/timerVal variables
Output: JSON + printed disasm to scratch/r21t2_autogaz/re_scan.json.
"""
import json
import os
import struct

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN

REPO = "/home/z/my-project/ps1ai"
EXE = os.path.join(REPO, "scratch", "r20t2_autogaz", "autogaz_exe2.bin")
OUT = os.path.join(REPO, "scratch", "r21t2_autogaz")
os.makedirs(OUT, exist_ok=True)

data = open(EXE, "rb").read()
assert data[:8] == b"PS-X EXE"
t_addr = 0x80010000
# text starts after the 0x800-byte header
TEXT_OFF = 0x800
text = data[TEXT_OFF:]
BASE = t_addr  # VA of text[0]

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 + CS_MODE_LITTLE_ENDIAN)
md.skipdata = True


def disasm(va, n=48, back=0):
    off = va - BASE
    chunk = text[max(0, off - back * 4):off + n * 4]
    start_va = BASE + max(0, off - back * 4)
    out = []
    for ins in md.disasm(chunk, start_va):
        out.append(f"0x{ins.address:08x}: {ins.mnemonic}\t{ins.op_str}")
        if len(out) >= n + back:
            break
    return "\n".join(out)


# ---- scan for ANDI imm 0x4000 / 0x2000 (button masks) ----
words = struct.unpack(f"<{len(text)//4}I", text[:len(text) // 4 * 4])
andi_hits = {0x4000: [], 0x2000: [], 0x1DC: [], 0x0800: [], 0x0100: []}
for i, w in enumerate(words):
    op = w >> 26
    imm = w & 0xFFFF
    if op == 0x0C and imm in andi_hits:          # ANDI
        andi_hits[imm].append(BASE + i * 4)
    if op in (0x09, 0x0A) and imm == 0x1DC:      # ADDIU/SLTI 476
        andi_hits[0x1DC].append(BASE + i * 4)

res = {"andi_0x4000": [hex(x) for x in andi_hits[0x4000]],
       "andi_0x2000": [hex(x) for x in andi_hits[0x2000]],
       "imm476": [hex(x) for x in andi_hits[0x1DC]],
       "disasm": {}}

print("ANDI 0x4000 hits:", [hex(x) for x in andi_hits[0x4000]])
print("ANDI 0x2000 hits:", [hex(x) for x in andi_hits[0x2000]])
print("imm 476 (ADDIU/SLTI) hits:", [hex(x) for x in andi_hits[0x1DC]])

# disassemble windows around each hit
for imm, label in ((0x4000, "cross"), (0x2000, "circle"), (0x1DC, "timer476")):
    for va in andi_hits[imm][:6]:
        key = f"{label}@{va:08x}"
        res["disasm"][key] = disasm(va, 26, back=12)
        print("=" * 70)
        print(key)
        print(res["disasm"][key])

with open(os.path.join(OUT, "re_scan.json"), "w") as f:
    json.dump(res, f, indent=1)
print("saved re_scan.json")
