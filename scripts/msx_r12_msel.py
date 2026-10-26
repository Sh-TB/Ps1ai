#!/usr/bin/env python3
"""msx_r12_msel.py — Round 12 (Task 16-b) MSX mission-select hunt.

hunt2 found the string table: "MISSION SELECT" @ 0x8001019c, per-mission
sequencer files \\ANG\\M1\\MISS01.BIN .. M4\\MISS16.BIN.  The hunt's ref
pass missed lui/ori pairs, so this script scans the EXE manually for
%hi(0x8001)+%lo(...) references to the MISSION SELECT string and its
neighbours, disassembles the referencing function, and maps:

  A. who builds the MISSION SELECT screen,
  B. which RAM word gates entry / per-mission selectability,
  C. the store sites = the unlock lever for the live probe.

Static only (no emulator).  Output: hunt3_report.json.
"""
import json
import os
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

REPO = "/home/z/my-project/ps1ai"
EXE = os.path.join(REPO, "scratch", "round12_msx", "SLUS_012.12.exe")
OUT = os.path.join(REPO, "scratch", "round12_msx", "hunt3_report.json")

STR = {
    "MISSION_SELECT": 0x8001019C,
    "CONTINUE": 0x800101AC,
    "MISSION_6": 0x800101B8,
    "MISSION_3": 0x800101DC,
    "MISSION_1": 0x800101F4,
    "LOADING_BIN": 0x800107F4,
    "MISSION_BIN": 0x80010854,
}

TEXT_VA = 0x80010000          # PS-EXE: taddr runs 0x80010000.. (header 0x800)
TEXT_OFF = 0x800              # file offset of text start


def main():
    blob = open(EXE, "rb").read()
    n = len(blob)
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    md.detail = False

    # ---- pass 1: find lui 0x8001 + addiu/ori %lo(str) pairs -----------
    # lui rt, 0x8001  = 0x3C0x8001 ; addiu rt, rt, lo / ori rt, rt, lo
    refs = {k: [] for k in STR}
    for i in range(TEXT_OFF, n - 8, 4):
        w = int.from_bytes(blob[i:i + 4], "little")
        if (w & 0xFFFF0000) != 0x3C010000 + (0x8001 << 0) and \
                (w >> 16) != 0x3C01:
            # general: any lui with %hi 0x8001 -> opcode 0x0F (lui), rs=0
            pass
        op = w >> 26
        if op != 0x0F:                     # lui
            continue
        hi = w & 0xFFFF
        if hi != 0x8001:
            continue
        rt = (w >> 16) & 0x1F
        # next 1-3 instrs: addiu rt2, rt, lo or ori rt2, rt, lo
        for j in (1, 2, 3):
            w2 = int.from_bytes(blob[i + 4 * j:i + 4 * j + 4], "little")
            if w2 == 0:
                break
            op2 = w2 >> 26
            rs = (w2 >> 21) & 0x1F
            rt2 = (w2 >> 16) & 0x1F
            lo = w2 & 0xFFFF
            if op2 in (0x09, 0x0D) and rs == rt:      # addiu/ori
                va = 0x80010000 + (i - TEXT_OFF) + (lo << 16 if False else 0)
                # %hi/%lo pair: address = (hi<<16) + signext(lo) when hi
                # accounts for carry; for 0x8001xxxx strings lo is the
                # low 16 bits directly if hi matches.
                addr = (hi << 16) + (lo if lo < 0x8000 else lo - 0x10000)
                for k, sa in STR.items():
                    if addr == sa:
                        refs[k].append({
                            "pc": hex(0x80010000 + (i - TEXT_OFF)),
                            "lo_op": "addiu" if op2 == 0x09 else "ori",
                            "slot": j,
                        })

    # ---- pass 2: disassemble around each MISSION_SELECT ref ----------
    out = {"schema": "ps1play-r12-hunt3/1", "string_refs": refs}
    dis = {}
    for k in ("MISSION_SELECT", "CONTINUE", "MISSION_1", "MISSION_3"):
        for r in refs[k][:4]:
            pc = int(r["pc"], 16)
            off = pc - 0x80010000 + TEXT_OFF
            start = max(TEXT_OFF, off - 0x180)
            end = min(n, off + 0x180)
            lines = []
            for ins in md.disasm(blob[start:end], 0x80010000 + start
                                 - TEXT_OFF):
                mark = " <<<" if ins.address == pc else ""
                lines.append(f"{ins.address:08x}: {ins.mnemonic} "
                             f"{ins.op_str}{mark}")
            dis[f"{k}@{r['pc']}"] = lines
    out["disasm"] = dis

    # ---- pass 3: locate the mission-index read near MISSxx table -----
    # \ANG\M1\MISS01.BIN @ 0x80010b84: refs via pairs too
    json.dump(out, open(OUT, "w"), indent=1)
    print("refs:", {k: len(v) for k, v in refs.items()})
    for k in ("MISSION_SELECT", "CONTINUE"):
        for r in refs[k][:3]:
            print(k, r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
