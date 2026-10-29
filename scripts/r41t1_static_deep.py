#!/usr/bin/env python3
"""r41t1_static_deep.py — R41 static deep decode (ZERO boots).

(1) Wider ASCII/word map around the node-list body VA 0x80084dcc to
find the descriptor-table start + entry stride (F6: nodes +0x5C/+0x8).
(2) Full-EXE literal scan: every site that references the section-VM
RAM words (0x800EB588 runner, 0x800EB5C6 gate, 0x800EB5D0 walker,
0x800EB5E8 table, 0x800EB5F8 node-list ptr, 0x80010DB8 script buffer)
via lui/addiu pairs — then classify read/write.
(3) Full disasm of the queue walker 0x80020444 until its final return
branch chain, + the dispatcher handlers 0x800216bc / 0x80021830, so
the node-field semantics come from CODE, not guesswork.
(4) The committed R40 boot-7 report: extract any recorded queue_ram /
progress-word values for the live correlation.

Output: scratch/r41/r41t1_static_deep.json (metadata only).
"""
from __future__ import annotations

import json
import os
import re
import sys

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(_REPO, "scripts"))

EXE = os.path.join(_REPO, "ps1play", "re", "SLUS_012.12")
T_ADDR = 0x80010000
HDR = 0x800
OUT = os.path.join(_REPO, "scratch", "r41")
BODY = 0x80084DCC

TARGETS = {
    "runner": 0x800EB588,
    "gate": 0x800EB5C6,
    "walker_state": 0x800EB5D0,
    "node_table": 0x800EB5E8,
    "node_list_ptr": 0x800EB5F8,
    "script_buf": 0x80010DB8,
}


def off(va):
    return HDR + (va - T_ADDR)


def main():
    os.makedirs(OUT, exist_ok=True)
    exe = open(EXE, "rb").read()
    rep = {"schema": "ps1play.r41t1/1", "boots_used": 0}

    # ---- (1) wider map around the body ------------------------------
    lo, hi = BODY - 0x120, BODY + 0x220
    chunk = exe[off(lo):off(hi)]
    ascii_map = []
    run = []
    for i, b in enumerate(chunk):
        c = chr(b) if 32 <= b < 127 else None
        if c:
            run.append((lo + i, c))
        else:
            if len(run) >= 4:
                ascii_map.append((hex(run[0][0]),
                                  "".join(x for _, x in run)))
            run = []
    if len(run) >= 4:
        ascii_map.append((hex(run[0][0]), "".join(x for _, x in run)))
    rep["ascii_strings_around_body"] = ascii_map

    # u32 map for pointer/stride structure discovery
    words = []
    for i in range(0, len(chunk) - 3, 4):
        words.append((lo + i, int.from_bytes(chunk[i:i + 4], "little")))
    ptrs = [(hex(a), hex(w)) for a, w in words
            if 0x80010000 <= w < 0x80200000]
    rep["ptrs_in_window"] = ptrs[:60]

    # ---- (2) literal-ref scan across the whole text -----------------
    # find lui $rX, 0x800f (opcode 0x3c0X_800f) then nearby addiu with
    # 0xb588/0xb5c6/0xb5d0/0xb5e8/0xb5f8, or lw/sw with those offsets
    hits = {}
    pats = {
        "runner_0xb588": re.compile(rb"[\x88\xb5]"),
    }
    text_lo, text_hi = T_ADDR, T_ADDR + 0x97800
    code = exe[off(text_lo):off(text_hi)]
    n = len(code) // 4
    refmap = {name: [] for name in TARGETS}
    for i in range(n - 1):
        w0 = int.from_bytes(code[i * 4:i * 4 + 4], "little")
        # lui rd, 0x800f  -> (0x3c << 26) | ... imm=0x800f
        if (w0 >> 16) == 0x3c03 and (w0 & 0xFFFF) == 0x800F:
            # $gp-style base in $v1? scan next 8 instrs for addiu/lw/sw
            # with the target offsets
            for j in range(i + 1, min(i + 9, n)):
                w1 = int.from_bytes(code[j * 4:j * 4 + 4], "little")
                imm = w1 & 0xFFFF
                opc = w1 >> 26
                for name, t in TARGETS.items():
                    want = t & 0xFFFF
                    if imm == want and opc in (0x09, 0x23, 0x2B, 0x25,
                                               0x21, 0x24):
                        refmap[name].append({
                            "va": hex(text_lo + i * 4),
                            "pair": [hex(w0), hex(w1)],
                            "second_va": hex(text_lo + j * 4)})
    rep["ram_word_refs"] = {k: v[:12] for k, v in refmap.items()}
    rep["ram_word_ref_counts"] = {k: len(v) for k, v in refmap.items()}

    # ---- (3) walker full disasm -------------------------------------
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)

    def dis_range(va, n_instr):
        o = off(va)
        out = []
        for ins in md.disasm(exe[o:o + 4 * n_instr], va):
            out.append((ins.address, ins.mnemonic, ins.op_str))
        return out

    walker = dis_range(0x80020444, 140)
    rep["walker_disasm"] = [
        {"va": hex(a), "i": f"{m} {o}"} for a, m, o in walker[:140]]
    # branch/jal structure of the walker
    w_jal = [(hex(a), o) for a, m, o in walker if m == "jal"]
    w_ref = [(hex(a), f"{m} {o}") for a, m, o in walker
             if re.search(r"0xb5[0-9a-f]{2}|0x5c\(|0x8\(|0x10db8", o)]
    rep["walker_jals"] = w_jal
    rep["walker_key_refs"] = w_ref

    h1 = dis_range(0x800216BC, 90)
    h2 = dis_range(0x80021830, 90)
    rep["handler1_key_refs"] = [
        (hex(a), f"{m} {o}") for a, m, o in h1
        if re.search(r"0xb5|0x5c|0x8\(|jal|jr", o)]
    rep["handler2_key_refs"] = [
        (hex(a), f"{m} {o}") for a, m, o in h2
        if re.search(r"0xb5|0x5c|0x8\(|jal|jr", o)]

    # dispatcher opcode table region 0x80021128
    disp = dis_range(0x80021128, 64)
    rep["dispatcher_jumps"] = [
        (hex(a), f"{m} {o}") for a, m, o in disp
        if m in ("jr", "jal", "beq", "bne", "slti") ]

    # ---- (4) committed R40 boot reports -----------------------------
    r40p = os.path.join(_REPO, "data/games/SLUS-01212/truck_evidence/r40",
                        "r40_boot_reports.json")
    if os.path.exists(r40p):
        r40 = json.load(open(r40p))
        boots = r40.get("boots") or []
        rep["r40_boots_index"] = []
        for i, b in enumerate(boots):
            if not isinstance(b, dict):
                continue
            run = b.get("run") or {}
            rep["r40_boots_index"].append({
                "i": i,
                "label": b.get("label") or run.get("label"),
                "keys": list(b.keys())[:12],
                "run_keys": list(run.keys())[:14]})
        # dig for queue_ram / progress anywhere in the JSON
        def find_key(obj, key, path=""):
            out = []
            if isinstance(obj, dict):
                for k, v in obj.items():
                    p = f"{path}.{k}"
                    if key in k.lower():
                        out.append((p, v if not isinstance(v, (dict, list))
                                    else f"<{type(v).__name__} len="
                                    f"{len(v)}>"))
                    out += find_key(v, key, p)
            elif isinstance(obj, list):
                for i2, v in enumerate(obj[:40]):
                    out += find_key(v, key, f"{path}[{i2}]")
            return out
        rep["r40_progress_key_hits"] = find_key(r40, "prog")[:12]
        rep["r40_queue_key_hits"] = find_key(r40, "queue")[:12]

    with open(os.path.join(OUT, "r41t1_static_deep.json"), "w") as f:
        json.dump(rep, f, indent=1, default=str)

    # console digest
    print("== strings around body ==")
    for a, s in ascii_map[:26]:
        print(f"  {a}: {s}")
    print("\n== ptrs in window ==")
    for p in ptrs[:24]:
        print("  ", p)
    print("\n== ram word ref counts ==", rep["ram_word_ref_counts"])
    print("\n== walker key refs ==")
    for r in w_ref[:20]:
        print("  ", r)
    print("\n== walker jals ==", w_jal[:12])
    print("\n== r40 boots index ==")
    for b in rep["r40_boots_index"]:
        print("  ", b)
    print("\n== r40 progress/queue hits ==")
    for h in rep["r40_progress_key_hits"][:8]:
        print("   P", h)
    for h in rep["r40_queue_key_hits"][:8]:
        print("   Q", h)
    print(f"\nreport -> {OUT}/r41t1_static_deep.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
