#!/usr/bin/env python3
"""state_writer_decompile.py — Phase 4 (Issue #5 D7 release): m2c the
EXE function containing 0x80023308 (the section advance at
`progress < threshold` — the documented decisive static step after the
clamp survived the truck kill + zone sweep).

Also maps the whole state-writer cluster 0x80022000-0x80023800: every
`sw` to the walker state 0x0EB5F4 / flags 0x0EB5D0 / progress
0x0EB5D4, with the owning function and the branch condition text.

Usage: python3 scripts/state_writer_decompile.py
"""
import os, subprocess, sys
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
EXE = "/home/z/my-project/work/msx_recomp/SLUS_012.12.full"
EXE_VA = 0x80010000
EXE_HDR = 0x800
M2C = "/home/z/my-project/work/m2c/m2c.py"
OUT = "/home/z/my-project/work/msx_recomp/evidence/issue5_truck"
STATE, FLAGS, PROG = 0x0EB5F4, 0x0EB5D0, 0x0EB5D4
SCAN_LO, SCAN_HI = 0x80021000, 0x80023C00
TARGET = 0x80023308

exe = open(EXE, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True


def va2off(va):
    return EXE_HDR + (va - EXE_VA)


# ---- 1. prologue map over the cluster ------------------------------
insns = list(md.disasm(exe[va2off(SCAN_LO):va2off(SCAN_HI)], SCAN_LO))
prologues = []
for i, ins in enumerate(insns):
    if ins.mnemonic == "addiu" and "$sp, $sp, -" in ins.op_str:
        nxt = insns[i + 1] if i + 1 < len(insns) else None
        if nxt and nxt.mnemonic in ("sw", "addiu") and \
                ("$ra" in nxt.op_str or "$sp" in nxt.op_str):
            prologues.append(ins.address)
print("prologues:", [hex(a) for a in prologues])


def fn_of(va):
    own = None
    for a in prologues:
        if a <= va:
            own = a
        else:
            break
    return own


def fn_end(start):
    for a in prologues:
        if a > start:
            return a
    return SCAN_HI


# ---- 2. writer census: which functions write state/flags/progress --
writers = {STATE: {}, FLAGS: {}, PROG: {}}
cur = None
for ins in insns:
    if ins.address in prologues:
        cur = ins.address
    if ins.mnemonic in ("sw", "sh") and cur is not None:
        for name, addr in (("STATE", STATE), ("FLAGS", FLAGS),
                           ("PROG", PROG)):
            if f"{addr:#x}" in ins.op_str or f"{addr}" in ins.op_str:
                writers[addr].setdefault(cur, []).append(
                    (ins.address, ins.mnemonic, ins.op_str))
for addr, label in ((STATE, "state 0x0EB5F4"), (FLAGS, "flags 0x0EB5D0"),
                    (PROG, "progress 0x0EB5D4")):
    print(f"--- writers of {label} ---")
    for fn, uses in sorted(writers[addr].items()):
        print(f"  fn {fn:#x}: {len(uses)} writes  e.g. {uses[0]}")

# ---- 3. m2c the function containing TARGET (and its neighbours) ----
tgt_fn = fn_of(TARGET)
print("function containing 0x80023308:", hex(tgt_fn) if tgt_fn else None)
os.makedirs(OUT, exist_ok=True)

targets = [tgt_fn] if tgt_fn else []
# also decompile the nearest writer of the walker state
st_fns = sorted(writers[STATE].keys())
for f in st_fns:
    if f not in targets:
        targets.append(f)
if not targets:
    targets = [0x80022000]

for fn in targets[:4]:
    end = fn_end(fn)
    body = list(md.disasm(exe[va2off(fn):va2off(end)], fn))
    branch_targets = set()
    for ins in body:
        if ins.mnemonic in ("beq", "bne", "blez", "bgtz", "bltz",
                            "bgez", "beqz", "bnez", "b"):
            try:
                t = int(ins.op_str.split(", ")[-1], 16)
                if fn <= t < end:
                    branch_targets.add(t)
            except (ValueError, IndexError):
                pass
    lines = [".set noat", ".set noreorder", ".text", "",
             f".global FUN_{fn:08x}", f"FUN_{fn:08x}:"]
    for ins in body:
        lbl = f".L{ins.address:08x}" if ins.address in branch_targets \
            else ""
        if lbl:
            lines.append(lbl + ":")
        op = ins.op_str
        if ins.mnemonic in ("beq", "bne", "blez", "bgtz", "bltz",
                            "bgez", "beqz", "bnez", "b"):
            parts = op.split(", ")
            try:
                t = int(parts[-1], 16)
                if fn <= t < end:
                    parts[-1] = f".L{t:08x}"
                    op = ", ".join(parts)
            except (ValueError, IndexError):
                pass
        lines.append(f"  {ins.mnemonic} {op}")
    ap = os.path.join(OUT, f"sw_{fn:08x}.asm")
    open(ap, "w").write("\n".join(lines) + "\n")
    r = subprocess.run(
        [sys.executable, M2C, ap, "-f", f"FUN_{fn:08x}"],
        capture_output=True, text=True, timeout=180,
        cwd=os.path.dirname(M2C))
    cp = os.path.join(OUT, f"sw_{fn:08x}.m2c.c")
    if r.returncode == 0:
        open(cp, "w").write(r.stdout)
        print(f"m2c OK {fn:#x} ({len(body)} insns) -> {cp}")
    else:
        print(f"m2c FAIL {fn:#x} rc={r.returncode}:",
              r.stderr[:400])

# ---- 4. raw disasm of the region around TARGET ---------------------
lo, hi = TARGET - 0x80, TARGET + 0xC0
print(f"--- disasm {lo:#x}..{hi:#x} (around 0x80023308) ---")
for ins in md.disasm(exe[va2off(lo):va2off(hi)], lo):
    mark = " <== 0x80023308" if ins.address == TARGET else ""
    print(f"  {ins.address:08x}: {ins.mnemonic:8s} {ins.op_str}{mark}")
