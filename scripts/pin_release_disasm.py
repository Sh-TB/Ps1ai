#!/usr/bin/env python3
"""pin_release_disasm.py — Phase 4 (Issue #5 D7 release), session-3.

The named smallest static experiment (session-2 §5 / worklog):
"table-disassemble the 0x80022500 ticker (embedded jump table at
0x80022600+) and correlate its next-state production with the live
trace at the 0x80023308 store."

Deliverables here (all from the canonical committed EXE):
  A. fn 0x80021128 — the 13-opcode section-script dispatcher:
     jump table 0x80010E14 decoded, every handler's flag effects
     (ori 0x42 / ori 0x12 sites), and WHERE the opcode byte is read
     from (the dynamic probe address for the live correlation).
  B. fn 0x80022500 — the ticker: embedded jump-table decode, every
     handler disassembled, all writes to walker state/flags/progress
     + the 0x80022c04 advance latch + calls into 0x80021128/0x800230e0.
  C. The pointer table at 0x80010DB8 (the ROOT-chain path table).
  D. m2c C output for both functions (work/m2c, re-cloned).

Output: evidence/issue5_session3_static/pin_release_static.json
        + .asm/.m2c.c per function.  Read-only.
"""
import json
import os
import subprocess
import sys
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
EXE = os.path.join(REPO, "ps1play/re/SLUS_012.12")
EXE_VA = 0x80010000
EXE_HDR = 0x800
M2C = "/home/z/my-project/ps1ai/work/m2c/m2c.py"
OUT = os.path.join(REPO, "evidence/issue5_session3_static")
STATE, FLAGS, PROG = 0x0EB5F4, 0x0EB5D0, 0x0EB5D4
LATCH = 0x80022C04
ADV_STORE = 0x80023308
SCAN_LO, SCAN_HI = 0x80021000, 0x80024000

exe = open(EXE, "rb").read()
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
md.skipdata = True


def va2off(va):
    return EXE_HDR + (va - EXE_VA)


def u32(va):
    o = va2off(va)
    return int.from_bytes(exe[o:o + 4], "little")


# ---- prologue map (fn boundaries) ----------------------------------
insns = list(md.disasm(exe[va2off(SCAN_LO):va2off(SCAN_HI)], SCAN_LO))
prologues = []
for i, ins in enumerate(insns):
    if ins.mnemonic == "addiu" and "$sp, $sp, -" in ins.op_str:
        nxt = insns[i + 1] if i + 1 < len(insns) else None
        if nxt and nxt.mnemonic in ("sw", "addiu") and \
                ("$ra" in nxt.op_str or "$sp" in nxt.op_str):
            prologues.append(ins.address)


def fn_end(start):
    for a in prologues:
        if a > start:
            return a
    return SCAN_HI


def disasm_fn(lo, hi):
    return list(md.disasm(exe[va2off(lo):va2off(hi)], lo))


def dump_asm(body, path):
    branch_targets = set()
    for ins in body:
        if ins.mnemonic in ("beq", "bne", "blez", "bgtz", "bltz",
                            "bgez", "beqz", "bnez", "b", "jal", "jr"):
            try:
                t = int(ins.op_str.split(", ")[-1], 16)
                if body[0].address <= t < body[-1].address + 4:
                    branch_targets.add(t)
            except (ValueError, IndexError):
                pass
    lines = [".set noat", ".set noreorder", ".text", "",
             f".global FUN_{body[0].address:08x}",
             f"FUN_{body[0].address:08x}:"]
    for ins in body:
        if ins.address in branch_targets:
            lines.append(f".L{ins.address:08x}:")
        op = ins.op_str
        if ins.mnemonic in ("beq", "bne", "blez", "bgtz", "bltz",
                            "bgez", "beqz", "bnez", "b"):
            parts = op.split(", ")
            try:
                t = int(parts[-1], 16)
                if body[0].address <= t < body[-1].address + 4:
                    parts[-1] = f".L{t:08x}"
                    op = ", ".join(parts)
            except (ValueError, IndexError):
                pass
        lines.append(f"  {ins.mnemonic} {op}")
    open(path, "w").write("\n".join(lines) + "\n")


def run_m2c(fn_addr, body, tag):
    ap = os.path.join(OUT, f"{tag}_{fn_addr:08x}.asm")
    dump_asm(body, ap)
    r = subprocess.run([sys.executable, M2C, ap, "-f",
                        f"FUN_{fn_addr:08x}"],
                       capture_output=True, text=True, timeout=240,
                       cwd=os.path.dirname(M2C))
    cp = os.path.join(OUT, f"{tag}_{fn_addr:08x}.m2c.c")
    if r.returncode == 0 and r.stdout.strip():
        open(cp, "w").write(r.stdout)
        return {"m2c": "OK", "c": cp}
    return {"m2c": "FAIL", "err": r.stderr[:300], "c": None}


def interesting(body):
    """Categorise the instructions that matter for the release.
    Resolves lui+off($reg) pairs to absolute VAs (capstone renders
    the walker words as negative offsets off a 0x800fxxxx base)."""
    out = {"state_writes": [], "flag_writes": [], "prog_writes": [],
           "latch_refs": [], "adv_store_refs": [], "jal": [],
           "computed_jumps": [], "ori_42": [], "ori_12": [],
           "lbu_sources": [], "walker_reads": []}
    lui_val = {}          # reg -> hi half for lui 0x800f style bases
    KNOWN = {STATE: "state", FLAGS: "flags", PROG: "progress",
             LATCH: "latch", ADV_STORE: "adv_store"}
    for ins in body:
        op = ins.op_str
        mn = ins.mnemonic
        if mn == "lui":
            parts = op.replace("$", "").split(", ")
            if len(parts) == 2:
                try:
                    lui_val[parts[0]] = int(parts[1], 16) << 16
                except ValueError:
                    pass
            continue
        # resolve mem operands "mnemonic $rX, off($rY)"
        tgt = None
        if mn in ("sw", "sh", "sb", "lw", "lhu", "lbu"):
            try:
                off_s = op.split(", ")[1]
                off_s, base = off_s.split("(")
                off = int(off_s, 16) & 0xFFFFFFFF
                if off >= 0x80000000:
                    off -= 0x100000000
                base = base.rstrip(")").replace("$", "")
                if base in lui_val:
                    tgt = (lui_val[base] + off) & 0xFFFFFFFF
            except (IndexError, ValueError):
                tgt = None
        if tgt in KNOWN:
            key = {STATE: "state", FLAGS: "flags", PROG: "progress",
                   LATCH: "latch", ADV_STORE: "adv_store"}[tgt]
            key = {"state": "state_writes", "flags": "flag_writes",
                   "progress": "prog_writes", "latch": "latch_refs",
                   "adv_store": "adv_store_refs"}[key]
            if mn in ("sw", "sh", "sb"):
                out[key].append([ins.address, op])
            else:
                out["walker_reads"].append([ins.address, mn, op])
        if mn == "ori" and op.endswith("0x42"):
            out["ori_42"].append([ins.address, op])
        elif mn == "ori" and op.endswith("0x12"):
            out["ori_12"].append([ins.address, op])
        elif mn == "jal":
            out["jal"].append([ins.address, op])
        elif mn == "jr" and "$ra" not in op:
            out["computed_jumps"].append([ins.address, op])
        elif mn == "lbu":
            out["lbu_sources"].append([ins.address, op])
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    report = {}

    # ---- A. the dispatcher fn 0x80021128 ---------------------------
    d_lo, d_hi = 0x80021128, fn_end(0x80021128)
    d_body = disasm_fn(d_lo, d_hi)
    report["dispatcher"] = {
        "range": [d_lo, d_hi], "n_insns": len(d_body),
        "effects": interesting(d_body),
    }
    report["dispatcher"]["m2c"] = run_m2c(d_lo, d_body,
                                          "dispatcher")["m2c"]

    # jump table 0x80010E14: read until targets leave the fn range
    jt = []
    for k in range(32):
        t = u32(0x80010E14 + 4 * k)
        jt.append({"k": k, "target": t,
                   "in_fn": d_lo <= t < d_hi})
        if not (d_lo <= t < d_hi) and k >= 12:
            break
    report["dispatcher"]["jump_table_0x80010E14"] = jt

    # ---- B. the ticker fn 0x80022500 -------------------------------
    t_lo, t_hi = 0x80022500, fn_end(0x80022500)
    t_body = disasm_fn(t_lo, t_hi)
    report["ticker"] = {
        "range": [t_lo, t_hi], "n_insns": len(t_body),
        "effects": interesting(t_body),
    }
    report["ticker"]["m2c"] = run_m2c(t_lo, t_body, "ticker")["m2c"]

    # embedded jump table: scan 0x80022600.. for u32 targets inside
    # the ticker body
    tj = []
    for k in range(64):
        va = 0x80022600 + 4 * k
        t = u32(va)
        if t_lo <= t < t_hi:
            tj.append({"va": va, "target": t})
    report["ticker"]["embedded_jump_table_hits"] = tj

    # ---- C. pointer table 0x80010DB8 --------------------------------
    ptrs = [{"va": 0x80010DB8 + 4 * k, "val": u32(0x80010DB8 + 4 * k)}
            for k in range((0x80010E14 - 0x80010DB8) // 4 + 8)]
    report["path_table_0x80010DB8"] = ptrs

    # ---- D. the advance fn 0x800230e0 (context refresh) -------------
    a_lo, a_hi = 0x800230e0, fn_end(0x800230e0)
    a_body = disasm_fn(a_lo, a_hi)
    report["advance_fn"] = {
        "range": [a_lo, a_hi], "n_insns": len(a_body),
        "effects": interesting(a_body),
    }
    report["advance_fn"]["m2c"] = run_m2c(a_lo, a_body,
                                          "advance")["m2c"]

    with open(os.path.join(OUT, "pin_release_static.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: (v if k == "path_table_0x80010DB8" else
                          {kk: vv for kk, vv in v.items()
                           if kk != "effects"})
                      for k, v in report.items()
                      if k != "path_table_0x80010DB8"},
                     indent=1, default=str)[:2000])
    print("\n== dispatcher effects ==")
    print(json.dumps(report["dispatcher"]["effects"], indent=1,
                     default=str))
    print("\n== ticker effects ==")
    print(json.dumps(report["ticker"]["effects"], indent=1,
                     default=str))
    print("\n== advance effects ==")
    print(json.dumps(report["advance_fn"]["effects"], indent=1,
                     default=str))
    print("\nwrote", os.path.join(OUT, "pin_release_static.json"))


if __name__ == "__main__":
    main()
