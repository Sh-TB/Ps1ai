#!/usr/bin/env python3
"""msx_r12_hunt2.py -- Round 12 / Task 16-b runtime-image tracker (offline).

Reconstructs the runtime instruction image from the external psxrecomp
shards (read-only, metadata-level extraction of instruction-word comments),
then runs a full-width register tracker (lui/addiu any-rd/move/load-store
incl. unaligned lwl/lwr/swl/swr) over every function and reports every
materialized address in the bands of interest:

  * CD file-path string vocab (\\ST0x\\..., \\ANG\\...\\MISSxx.BIN;1,
    \\MISSION.BIN;1, \\ENEMY.BIN;1, \\LOADING.BIN;1, ...)
  * the file-request struct (filename buffer 0x800EB5CE and neighbours)
  * the section band 0x800EB5C0-0x800EB620 / FLAGS_WORD / kill cluster
  * the debug "MISSION SELECT" menu strings + descriptor tables

Output: scratch/round12_msx/hunt2_report.json (metadata only).
"""
from __future__ import annotations

import bisect
import json
import os
import pickle
import struct
from collections import defaultdict

import capstone as cs

REPO = "/home/z/my-project/ps1ai"
OUT = os.path.join(REPO, "scratch/round12_msx")
RUNTIME_PKL = os.path.join(OUT, "msxtc_runtime.pkl")

T_LO, T_HI = 0x80010000, 0x81000000

STRINGS = {
    0x8001019C: "MISSION SELECT", 0x800101B8: "MISSION 6",
    0x800101DC: "MISSION 3", 0x800101F4: "MISSION 1",
    0x80010854: "\\MISSION.BIN;1", 0x800107F4: "\\LOADING.BIN;1",
    0x80010154: "LOADING...", 0x800114EC: "STAGE %d",
    0x800115B8: "CONTINUE? %d", 0x800101AC: "CONTINUE",
    # per-mission map files (MSX = ST01..ST06)
    0x8001074C: "\\ST01\\VAB01.BIN;1", 0x80010760: "\\ST01\\SEQ01.BIN;1",
    0x80010D90: "\\ST06\\_3\\ST06C.BIN;1",
    0x80010DD8: "\\ST06\\ST06.BIN;1",
    0x80010DEC: "\\ST05\\_3\\ST05C.BIN;1",
    # arrange-mode mission files ANG/M1..M4/MISS01..20
    0x80010B84: "\\ANG\\M1\\MISS01.BIN;1",
    0x80010B0C: "\\ANG\\M2\\MISS06.BIN;1",
    0x80010A94: "\\ANG\\M3\\MISS11.BIN;1",
    0x800108EC: "\\ANG\\M4\\MISS16.BIN;1",
    0x80010878: "\\ANG\\MISSMN.BIN;1",
    0x80010864: "\\ANG\\CSCHOOL.BIN;1",
    0x80010D80: "\\ENEMY.BIN;1",
    0x80010CDC: "\\STD\\STD00.BIN;1", 0x80010CC8: "\\STD\\STD01.BIN;1",
    0x800107E4: "\\STD\\GO00.BIN;1", 0x80010834: "\\TITLE.BIN;1",
    0x800102C0: "\\STD\\_VHIECLE.BIN;1",
}
GLOBALS = {
    0x800EB5CE: "filename_buffer",
    0x800EB5D0: "SECTION_FLAGS", 0x800EB5D2: "sect_byte_D2",
    0x800EB5D4: "SECTION_PROGRESS", 0x800EB5D8: "sect_word_D8",
    0x800EB5F4: "SECTION_STATE_A", 0x800EB5F8: "SECTION_STATE_C",
    0x800EB5FC: "world_alive_latch", 0x800EE518: "FLAGS_WORD",
    0x800C9A98: "entity_base", 0x800CA2E0: "PLAYER_X",
    0x80093E48: "ctx_ptr_80093E48",
    0x80095F40: "menu_desc_table", 0x80095800: "file_desc_table_2",
}
WINDOWS = [
    (0x800EB5C0, 0x800EB620, "section_band"),
    (0x800E7D80, 0x800E7E80, "kill_cluster"),
    (0x800EE510, 0x800EE528, "flags_word"),
    (0x80095400, 0x80096100, "descriptor_tables"),
    (0x80093E00, 0x80093F00, "ctx_ptr_region"),
]


def sign16(v):
    return v - 0x10000 if v & 0x8000 else v


def main():
    os.makedirs(OUT, exist_ok=True)
    d = pickle.load(open(RUNTIME_PKL, "rb"))
    words, func_of = d["words"], d["func_of"]
    fstarts = sorted(func_of)
    fby = {int(f["va"], 16): f for f in
           json.load(open(os.path.join(
               REPO, "data/games/SLUS-01212/re_index.json")))["functions"]}

    def fname(pc):
        i = bisect.bisect_right(fstarts, pc) - 1
        if i >= 0:
            a = fstarts[i]
            if pc < a + func_of[a]:
                return f"func_{a:08x}"
        f = fby.get(pc)
        return f["name"] if f else "??"

    md = cs.Cs(cs.CS_ARCH_MIPS, cs.CS_MODE_MIPS32)
    md.detail = True
    hits = defaultdict(list)   # addr -> [(pc, kind, detail)]

    for fva in fstarts:
        size = func_of[fva]
        regs = {}   # reg -> base address (materialized) or None

        def note(addr, pc, kind, extra):
            hits[addr].append((pc, kind, extra))

        for off in range(0, size, 4):
            pc = fva + off
            w = words.get(pc)
            if w is None:
                continue
            ins = next(md.disasm(struct.pack("<I", w), pc), None)
            if ins is None:
                continue
            m, ops = ins.mnemonic, ins.operands
            if m == "lui" and len(ops) == 2:
                regs[ops[0].reg] = (ops[1].imm & 0xFFFF) << 16
                continue
            if m in ("addiu", "addi") and len(ops) == 3:
                rs, rt = ops[1].reg, ops[0].reg
                base = regs.get(rs)
                if base is not None:
                    addr = (base + sign16(ops[2].imm & 0xFFFF)) & 0xFFFFFFFF
                    if T_LO <= addr < T_HI:
                        note(addr, pc, "addr", m)
                    regs[rt] = addr if 0x80000000 <= addr < 0x81000000 else \
                        None
                else:
                    regs.pop(rt, None)
                continue
            if m == "move" and len(ops) == 2:
                src = regs.get(ops[1].reg)
                if src is not None:
                    regs[ops[0].reg] = src
                else:
                    regs.pop(ops[0].reg, None)
                continue
            if (m in ("lw", "sw", "lbu", "sb", "lhu", "sh", "lwl", "lwr",
                      "swl", "swr") and len(ops) == 2
                    and ops[1].type == cs.CS_OP_MEM):
                base = regs.get(ops[1].mem.base)
                if base is not None:
                    addr = (base + sign16(ops[1].mem.disp & 0xFFFF)) \
                        & 0xFFFFFFFF
                    if T_LO <= addr < T_HI:
                        w_d = "W" if m.startswith("s") else "R"
                        note(addr, pc, m, w_d)
            if ops and ops[0].type == cs.CS_OP_REG and m not in (
                    "lw", "lbu", "lhu", "lwl", "lwr", "move", "mflo", "mfhi"):
                regs.pop(ops[0].reg, None)

    def summarize(addr):
        out = []
        for pc, kind, extra in hits.get(addr, []):
            out.append({"pc": hex(pc), "kind": kind, "extra": extra,
                        "func": fname(pc)})
        return out

    report = {"schema": "ps1play-r12-hunt2/1",
              "runtime_words": len(words), "functions": len(fstarts),
              "sites": {}}
    for a, name in sorted(STRINGS.items()):
        report["sites"][f"str_{name}"] = {"addr": hex(a),
                                          "refs": summarize(a)}
    for a, name in sorted(GLOBALS.items()):
        report["sites"][f"g_{name}"] = {"addr": hex(a),
                                        "refs": summarize(a)}
    for lo, hi, tag in WINDOWS:
        band = {}
        for tgt in sorted(hits):
            if lo <= tgt < hi:
                band[hex(tgt)] = summarize(tgt)
        report["sites"][tag] = band

    json.dump(report, open(os.path.join(OUT, "hunt2_report.json"), "w"),
              indent=1)
    print("functions traced:", len(fstarts), "addrs hit:", len(hits))
    for key in sorted(report["sites"]):
        v = report["sites"][key]
        if isinstance(v, dict) and "refs" in v:
            print(f"{key:36s} refs={len(v['refs'])}")
        else:
            print(f"{key:36s} sub={len(v)}")


if __name__ == "__main__":
    main()
