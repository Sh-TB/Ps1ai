#!/usr/bin/env python3
"""Decompile the section walker FUN_80021898 (EXE text) with the proven
m2c pipeline: capstone word-wise GNU-as emitter -> m2c -> readable C.

The walker owns: state 0x0EB5F4, flags 0x0EB5D0, progress 0x0EB5D4 —
the D7 clamp lives here. Reading its branch conditions answers Phase 4.

Output: work/msx_recomp/evidence/issue5_truck/walker_80021898.{asm,m2c.c}
"""
import json, os, struct, subprocess, sys
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
EXE = "/home/z/my-project/work/msx_recomp/SLUS_012.12.full"
EXE_VA = 0x80010000
EXE_HDR = 0x800
OUT = "/home/z/my-project/work/msx_recomp/evidence/issue5_truck"
M2C = "/home/z/my-project/work/m2c/m2c.py"

os.makedirs(OUT, exist_ok=True)
exe = open(EXE, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True

FN = 0x80021898

def va2off(va):
    return EXE_HDR + (va - EXE_VA)

# ---- 1. find function start: walk back to the prologue pattern ----
start = None
insns = list(md.disasm(exe[va2off(FN) - 0x400:va2off(FN) + 0x40],
                       FN - 0x400))
for i, ins in enumerate(insns):
    if ins.address >= FN:
        break
    if ins.mnemonic == "addiu" and "$sp, $sp, -" in ins.op_str:
        nxt = insns[i + 1] if i + 1 < len(insns) else None
        if nxt and nxt.mnemonic in ("sw", "addiu") and \
                ("$ra" in nxt.op_str or "$sp" in nxt.op_str):
            start = ins.address
if start is None:
    start = FN
print("function start:", hex(start))

# ---- 2. find end: first epilogue (jr ra after lw ra) followed by a new
#         prologue, or scan until the next function's prologue ----
insns2 = list(md.disasm(exe[va2off(start):va2off(start) + 0x2000], start))
end = None
depth_ret = False
for i, ins in enumerate(insns2):
    if ins.mnemonic == "jr" and "$ra" in ins.op_str:
        # check the delay slot + next few for a new prologue
        end = ins.address + 8
        for j in range(i + 1, min(i + 6, len(insns2))):
            if insns2[j].mnemonic == "addiu" and "$sp, $sp, -" in insns2[j].op_str:
                end = insns2[j].address
                break
        break
if end is None:
    end = start + 0x800
print("function end (exclusive):", hex(end), "size:", end - start)

# ---- 3. collect referenced addresses for extern labels ----
refs = set()
for ins in insns2:
    if ins.address >= end:
        break
    if ins.mnemonic in ("jal", "j"):
        try:
            refs.add(int(ins.op_str, 16))
        except ValueError:
            pass

# ---- 4. emit GNU-as with m2c conventions ----
lines = [".set noat", ".set noreorder", ".text", ""]
lines.append(f".global FUN_{start:08x}")
lines.append(f"FUN_{start:08x}:")
body = list(md.disasm(exe[va2off(start):va2off(end)], start))
# label in-body branch targets .L..., externs X_...
branch_targets = set()
for ins in body:
    if ins.mnemonic in ("beq", "bne", "blez", "bgtz", "bltz", "bgez",
                        "beqz", "bnez", "b"):
        try:
            t = int(ins.op_str.split(", ")[-1], 16)
            if start <= t < end:
                branch_targets.add(t)
        except (ValueError, IndexError):
            pass
for ins in body:
    lbl = f".L{ins.address:08x}" if ins.address in branch_targets else ""
    if lbl:
        lines.append(lbl + ":")
    op = ins.op_str
    if ins.mnemonic in ("jal", "j") and "0x" in op:
        try:
            t = int(op.split()[-1], 16)
            if not (start <= t < end):
                op = op.replace(f"{t:#x}", f"X_{t:08x}")
                if t not in refs:
                    pass
        except (ValueError, IndexError):
            pass
    # m2c: numeric branch targets -> .L labels
    if ins.mnemonic in ("beq", "bne", "blez", "bgtz", "bltz", "bgez",
                        "beqz", "bnez", "b"):
        parts = op.split(", ")
        try:
            t = int(parts[-1], 16)
            if start <= t < end:
                parts[-1] = f".L{t:08x}"
                op = ", ".join(parts)
        except (ValueError, IndexError):
            pass
    lines.append(f"  {ins.mnemonic} {op}")
asm_path = os.path.join(OUT, f"walker_{start:08x}.asm")
open(asm_path, "w").write("\n".join(lines) + "\n")
print("asm ->", asm_path, f"({len(body)} insns)")

# ---- 5. run m2c ----
r = subprocess.run([sys.executable, M2C, asm_path, "-f",
                    f"FUN_{start:08x}"], capture_output=True, text=True,
                   timeout=120, cwd=os.path.dirname(M2C))
cpath = os.path.join(OUT, f"walker_{start:08x}.m2c.c")
if r.returncode == 0:
    open(cpath, "w").write(r.stdout)
    print("m2c OK ->", cpath)
else:
    print("m2c FAIL rc=", r.returncode)
    print(r.stderr[:2000])
    print(r.stdout[:800])
