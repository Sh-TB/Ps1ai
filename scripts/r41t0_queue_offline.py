#!/usr/bin/env python3
"""r41t0_queue_offline.py — R41 static-first analysis (ZERO boots).

Step 1: re-read the committed R40 boot-5/6/7 queue_ram sweeps
(0x800EB580..0x800EB670) and lay out the section-VM words:
runner id s16 @0x800EB588, gate u16 @0x800EB5C6, walker
state/flags @0x800EB5D0, node table @0x800EB5E8, node-list
POINTER @0x800EB5F8 (R40: points at 0x80084dcc), progress word
(the 0x80000000 -> 0xFFFFFFFF accumulator, F1 release flips to
0xFFF38B4A).

Step 2: decode the node-list BODY statically from the canonical EXE
(sha256 1508b532..., 622,592 B; t_addr 0x80010000, 0x800-byte
header): the body lives in the EXE image at VA 0x80084dcc, so the
pending-node structure can be understood BEFORE any boot.

Step 3: disassemble the queue walker 0x80020444 and the dispatcher
handler entries (0x80021128 dispatcher, 0x800216bc/0x80021830)
with capstone to decode the node fields (+0x5C/+0x8 per F6) and
the request-opcode vocabulary (13 opcodes, 30-byte script buffer
@0x80010DB8).

Outputs: scratch/r41/r41t0_static_report.json (metadata only, no
game bytes) + console summary.
"""
from __future__ import annotations

import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, os.path.join(_REPO, "scripts"))

EXE = os.path.join(_REPO, "ps1play", "re", "SLUS_012.12")
T_ADDR = 0x80010000
HDR = 0x800
QUEUE_LO = 0x800EB580
QUEUE_HI = 0x800EB670
OUT = os.path.join(_REPO, "scratch", "r41")

RUNNER = 0x800EB588
GATE = 0x800EB5C6
WALKER_STATE = 0x800EB5D0        # u16 state, u16 flags (the [0xB,0x1])
NODE_TABLE = 0x800EB5E8
NODE_LIST_PTR = 0x800EB5F8


def va_to_off(va):
    return HDR + (va - T_ADDR)


def u16(b, off):
    return int.from_bytes(b[off:off + 2], "little")


def u32(b, off):
    return int.from_bytes(b[off:off + 4], "little")


def main():
    os.makedirs(OUT, exist_ok=True)
    report = {"schema": "ps1play.r41t0/1", "boots_used": 0}

    # ---- step 1: the committed boot-7 sweep --------------------------
    r40 = json.load(open(os.path.join(
        _REPO, "data/games/SLUS-01212/truck_evidence/r40/"
        "r40_boot_reports.json")))
    print("r40 report keys:", list(r40.keys()))
    boots = r40.get("boots") or []
    for i, b in enumerate(boots):
        if not isinstance(b, dict):
            continue
        label = b.get("label") or b.get("script") or f"boot{i+1}"
        runs = b.get("run") or b
        qrs = []
        for ev_name in ("CHOPPER_RESOLVED", "FULL_TABLE"):
            # search jsonl paths instead
            break
        print(f"- {label}: keys={list(b.keys())[:10]}")
    report["r40_layout"] = "see jsonl below"

    # the jsonl traces hold the FULL_TABLE/CHOPPER_RESOLVED events, but
    # scratch/ was wiped by the rollback; the committed boot reports
    # carry the summarized runs. Fall back: decode ONLY the static side
    # (the body bytes) + the walker disasm, and take the R40-recorded
    # words (pointer 0x80084dcc, walker [0xB,0x1], progress flip) as
    # given by the commit message + capsule.

    # ---- step 2: the node-list body, statically ----------------------
    exe = open(EXE, "rb").read()
    assert len(exe) == 622592, f"unexpected EXE size {len(exe)}"
    import hashlib
    sha = hashlib.sha256(exe).hexdigest()
    assert sha.startswith("1508b532"), f"unexpected EXE sha {sha[:8]}"
    report["exe_sha256"] = sha

    body_va = 0x80084DCC
    off = va_to_off(body_va)
    # read a generous window (the list is node-chain based; 0x400 words
    # covers ~10 node-strides of 0x5C + slack)
    win = exe[off:off + 0x400]
    words32 = [u32(win, i) for i in range(0, 0x200, 4)]
    words16 = [u16(win, i) for i in range(0, 0x200, 2)]
    report["body_va"] = hex(body_va)
    report["body_u32_first128"] = [hex(w) for w in words32[:128]]
    report["body_u16_first256"] = [hex(w) for w in words16[:256]]

    # heuristics: pointers inside the body (values in KUSEG text/data)
    ptrs = [(hex(0x80084DCC + i), hex(w))
            for i, w in enumerate(words32) if 0x80010000 <= w < 0x80200000]
    report["body_internal_ptrs"] = ptrs[:40]
    # small-int structure markers (opcodes 0x01..0x0D vocabulary per F6)
    op_like = [(hex(0x80084DCC + i), hex(w))
               for i, w in enumerate(words16) if 1 <= w <= 0x0D]
    report["body_opcode_like_u16"] = op_like[:40]

    # ---- step 3: the walker + dispatcher disasm ----------------------
    from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)

    def dis(va, n=64, back=0):
        o = va_to_off(va) - back * 4
        code = exe[o:o + 4 * n]
        return [(f"{va - back*4 + i*4:08x}", ins.mnemonic, ins.op_str)
                for i, ins in enumerate(md.disasm(code, va - back * 4))]

    def reads_writes(insns):
        out = []
        for a, m, ops in insns:
            if "0x5c(" in ops or "0x5c," in ops or ", 0x5c" in ops:
                out.append((a, m, ops))
            if "0x8(" in ops:
                out.append((a, m, ops))
            if "0x80010db8" in ops or "0x10db8" in ops:
                out.append((a, m, ops))
        return out

    walker = dis(0x80020444, 96)
    report["walker_80020444_first96"] = [
        {"va": a, "m": m, "op": o} for a, m, o in walker]
    report["walker_node_field_refs"] = reads_writes(walker)

    disp = dis(0x80021128, 48)
    report["dispatcher_80021128_first48"] = [
        {"va": a, "m": m, "op": o} for a, m, o in disp]

    h1 = dis(0x800216BC, 40)
    h2 = dis(0x80021830, 40)
    report["handler_800216bc_first40"] = [
        {"va": a, "m": m, "op": o} for a, m, o in h1]
    report["handler_80021830_first40"] = [
        {"va": a, "m": m, "op": o} for a, m, o in h2]

    # the script buffer @0x80010DB8: F6 says ASCII tokens in the FILE,
    # runtime-rebuilt pointers in RAM — decode the file bytes
    sb = exe[va_to_off(0x80010DB8):va_to_off(0x80010DB8) + 0x80]
    report["script_buffer_file_bytes_hex"] = sb.hex()
    printable = "".join(chr(b) if 32 <= b < 127 else "." for b in sb)
    report["script_buffer_file_ascii"] = printable

    with open(os.path.join(OUT, "r41t0_static_report.json"), "w") as f:
        json.dump(report, f, indent=1)

    # console digest
    print("\n== body u32[0:32] ==")
    for i in range(0, 32, 4):
        print(f"  +{i:#06x}: " + " ".join(
            f"{w:08x}" for w in words32[i:i + 4]))
    print("\n== body internal ptrs ==", len(ptrs))
    for p in ptrs[:20]:
        print("  ", p)
    print("\n== walker node-field refs ==")
    for r in report["walker_node_field_refs"][:24]:
        print("  ", r)
    print("\n== script buffer ascii ==")
    print("  ", printable[:96])
    print(f"\nreport -> {OUT}/r41t0_static_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
