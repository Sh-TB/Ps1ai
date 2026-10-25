#!/usr/bin/env python3
"""walker_writers_scan.py — full-EXE + bank-dump scan for every
store/read of the section-walker words:
  state    0x800EB5F4  (lui 0x800f + off -0x4a0c)
  flags    0x800EB5D0  (off -0x4a30)
  progress 0x800EB5D4  (off -0x4a2c)
  runner   0x800EB588  (off -0x4a78)
  gate u16 0x800EB5C6  (off -0x4a3a)
  latch    0x80022C04 is CODE — skipped.
The walker words are accessed as `lui $rX, 0x800f` + `op off($rX)`
with SIGNED negative offsets, so we match the offset+register pair
directly (no lui tracking needed) and report the owning prologue.

Also scans the live bank dump for the same patterns.
Output: evidence/issue5_session3_static/walker_writers.json
"""
import json
import os
import re
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
EXE = os.path.join(REPO, "ps1play/re/SLUS_012.12")
BANK = os.path.join(REPO, "evidence/issue5_chopper_hunt/bank_044058.bin")
OUT = os.path.join(REPO, "evidence/issue5_session3_static")
EXE_VA, EXE_HDR = 0x80010000, 0x800
BANK_VA = 0x8009C0E8
SCAN_LO, SCAN_HI = 0x80010000, 0x800A7800

OFFS = {-0x4A0C: "state_0x800EB5F4", -0x4A30: "flags_0x800EB5D0",
        -0x4A2C: "progress_0x800EB5D4", -0x4A78: "runner_0x800EB588",
        -0x4A3A: "gate_0x800EB5C6", -0x4A34: "w_0x800EB5CC",
        -0x4A38: "w_0x800EB5C8", -0x4A70: "w_0x800EB590",
        -0x4A6C: "w_0x800EB594", -0x4A68: "scroll_0x800EB598"}

md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True


def va2off(va):
    return EXE_HDR + (va - EXE_VA)


def prologues_of(insns):
    ps = []
    for i, ins in enumerate(insns):
        if ins.mnemonic == "addiu" and "$sp, $sp, -" in ins.op_str:
            nxt = insns[i + 1] if i + 1 < len(insns) else None
            if nxt and nxt.mnemonic in ("sw", "addiu"):
                ps.append(ins.address)
    return ps


def fn_of(ps, va):
    own = None
    for a in ps:
        if a <= va:
            own = a
        else:
            break
    return own


def scan(name, code, base_va):
    insns = list(md.disasm(code, base_va))
    ps = prologues_of(insns)
    hits = {}
    for ins in insns:
        if ins.mnemonic not in ("sw", "sh", "sb", "lw", "lhu", "lbu"):
            continue
        m = re.match(r"\s*(\$\w+), ([-\w]+)\((\$\w+)\)", ins.op_str)
        if not m:
            continue
        try:
            off = int(m.group(2), 16)
        except ValueError:
            continue
        if off in OFFS:
            kind = OFFS[off]
            fn = fn_of(ps, ins.address)
            hits.setdefault(kind, {}).setdefault(fn, []).append(
                {"va": ins.address, "op": f"{ins.mnemonic} {ins.op_str}",
                 "store": ins.mnemonic in ("sw", "sh", "sb")})
    return hits


def main():
    os.makedirs(OUT, exist_ok=True)
    exe = open(EXE, "rb").read()
    report = {}
    print("== EXE scan", hex(SCAN_LO), "..", hex(SCAN_HI))
    report["exe"] = scan("exe", exe[va2off(SCAN_LO):va2off(SCAN_HI)],
                         SCAN_LO)
    for kind, fns in sorted(report["exe"].items()):
        print(f"  {kind}:")
        for fn, uses in sorted(fns.items() or []):
            stores = sum(1 for u in uses if u["store"])
            print(f"    fn {fn:#x} ({len(uses)} refs, {len(uses)-stores} stores)")
    try:
        bank = open(BANK, "rb").read()
        print("== BANK scan", hex(BANK_VA))
        report["bank"] = scan("bank", bank, BANK_VA)
        for kind, fns in sorted(report["bank"].items()):
            print(f"  {kind}:")
            for fn, uses in sorted(fns.items() or []):
                print(f"    fn {fn:#x} ({len(uses)} refs)")
    except FileNotFoundError:
        report["bank"] = {}
        print("bank dump missing")
    with open(os.path.join(OUT, "walker_writers.json"), "w") as f:
        json.dump(report, f, indent=1)
    print("wrote", os.path.join(OUT, "walker_writers.json"))


if __name__ == "__main__":
    main()
