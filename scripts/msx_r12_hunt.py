#!/usr/bin/env python3
"""msx_r12_hunt.py -- Round 12 / Task 16-b static mission-word hunt (offline).

Word-steps the canonical SLUS_012.12 text (capstone MIPS32, per-word decode
so data regions do not stop the sweep), tracks lui/addiu/move register
address materialization, and maps every reference to:

  * scene/mission vocabulary strings ("MISSION SELECT", "MISSION 1..6",
    "\\MISSION.BIN;1", "\\LOADING.BIN;1", "STAGE %d", "CONTINUE? %d")
  * the state-machine pointer-table region 0x80010100-0x80010200
    (round-12 discovery: game-mode dispatch tables live with the strings)
  * the known globals band (SECTION_* 0x800EB5D0-0x800EB600,
    world_alive_latch 0x800EB5FC, FLAGS_WORD 0x800EE518)
  * the round-11 kill cluster 0x800E7D98-0x800E7E70

Sites are attributed to owning functions (re_index.json).  Output:
scratch/round12_msx/hunt_report.json (metadata only -- no game bytes).
"""
from __future__ import annotations

import bisect
import json
import os
import struct
from collections import defaultdict

import capstone as cs

REPO = "/home/z/my-project/ps1ai"
GAME = os.path.join(REPO, "data/games/SLUS-01212")
EXE_CANDIDATES = [
    os.path.join(REPO, "scratch/round12_msx/SLUS_012.12.exe"),
    os.path.join(REPO, "ps1play/re/SLUS_012.12"),
]
OUT = os.path.join(REPO, "scratch/round12_msx")

T_ADDR = 0x80010000

STRINGS = {
    0x8001019C: "MISSION SELECT",
    0x800101B8: "MISSION 6", 0x800101C4: "MISSION 5",
    0x800101D0: "MISSION 4", 0x800101DC: "MISSION 3",
    0x800101E8: "MISSION 2", 0x800101F4: "MISSION 1",
    0x80010854: "\\MISSION.BIN;1",
    0x800107F4: "\\LOADING.BIN;1",
    0x80010154: "LOADING...",
    0x800114EC: "STAGE %d",
    0x800115B8: "CONTINUE? %d",
    0x800101AC: "CONTINUE",
    0x80010130: "PRESS START",
    0x80010134: "ptr_table@0x80010134",
}
GLOBALS = {
    0x800EB5D0: "SECTION_FLAGS", 0x800EB5D4: "SECTION_PROGRESS",
    0x800EB5F4: "SECTION_STATE_A", 0x800EB5F6: "SECTION_STATE_B",
    0x800EB5F8: "SECTION_STATE_C", 0x800EB5FC: "world_alive_latch",
    0x800EE518: "FLAGS_WORD", 0x800EB598: "scroll_word",
    0x800C9A98: "entity_base", 0x800CA2E0: "PLAYER_X",
}
KILL_CLUSTER = (0x800E7D98, 0x800E7E70)
# whole section-band window: catch base+disp refs that land anywhere inside
BAND_WINDOWS = [
    (0x800EB5C0, 0x800EB620, "section_band"),
    (0x800EE518, 0x800EE520, "flags_word"),
    (0x800E7D80, 0x800E7E80, "kill_cluster"),
]


def sign16(v):
    return v - 0x10000 if v & 0x8000 else v


def load_exe():
    for p in EXE_CANDIDATES:
        if os.path.exists(p):
            raw = open(p, "rb").read()
            return raw[2048:2048 + 620544], p
    raise SystemExit("no EXE copy found")


def main():
    os.makedirs(OUT, exist_ok=True)
    text, exe_path = load_exe()

    fn = json.load(open(os.path.join(GAME, "re_index.json")))["functions"]
    starts = sorted(int(f["va"], 16) for f in fn)
    fby = {int(f["va"], 16): f for f in fn}

    def owner(va):
        i = bisect.bisect_right(starts, va) - 1
        if i < 0:
            return None
        a = starts[i]
        f = fby[a]
        if va < a + f["size"]:
            return f
        return None

    md = cs.Cs(cs.CS_ARCH_MIPS, cs.CS_MODE_MIPS32)
    md.detail = True

    regs = {}          # reg -> (base_addr, lui_pc)
    site_hits = defaultdict(list)   # target -> [(pc, kind, reg, extra)]
    n_valid = 0

    def note(target, pc, kind, reg, extra=None):
        site_hits[target].append((pc, kind, reg, extra))

    def track(ins, pc):
        m = ins.mnemonic
        ops = ins.operands
        if m == "lui" and len(ops) == 2:
            regs[ops[0].reg] = (ops[1].imm & 0xFFFF, pc)
            return
        if (m in ("addiu", "addi") and len(ops) == 3
                and ops[1].type == cs.CS_OP_REG and ops[1].reg == ops[0].reg):
            r = ops[0].reg
            base = regs.get(r)
            if base is not None:
                addr = (base[0] << 16) + sign16(ops[2].imm & 0xFFFF)
                addr &= 0xFFFFFFFF
                if 0x80000000 <= addr < 0x81000000:
                    note(addr, pc, "lui+addiu", md.reg_name(r),
                         f"hi@{base[1]:#x}")
                regs[r] = (addr >> 16, pc) if addr >> 16 == base[0] else \
                    (None, None)
                if regs[r][0] is None:
                    regs.pop(r)
            return
        if m == "move" and len(ops) == 2:
            src = regs.get(ops[1].reg)
            if src is not None:
                regs[ops[0].reg] = src
            else:
                regs.pop(ops[0].reg, None)
            return
        if (m in ("lw", "sw", "lbu", "sb", "lhu", "sh", "lwl", "lwr",
                  "swl", "swr") and len(ops) == 2
                and ops[1].type == cs.CS_OP_MEM):
            b = ops[1].mem.base
            base = regs.get(b)
            if base is not None:
                addr = (base[0] << 16) + sign16(ops[1].mem.disp & 0xFFFF)
                addr &= 0xFFFFFFFF
                if 0x80000000 <= addr < 0x81000000:
                    w = 1 if m in ("lb", "lbu", "sb") else (
                        2 if m in ("lh", "lhu", "sh") else 4)
                    note(addr, pc, m, md.reg_name(b),
                         f"w{w}{' W' if m.startswith('s') else ''}")
            if ops[0].type == cs.CS_OP_REG and m in ("lw", "lbu", "lhu",
                                                     "lwl", "lwr"):
                pass
            return
        # invalidate rd for other defs
        if ops and ops[0].type == cs.CS_OP_REG and m not in (
                "lw", "lbu", "lhu", "lwl", "lwr", "move", "mflo", "mfhi",
                "mtc0", "lwc2", "lwc1"):
            regs.pop(ops[0].reg, None)

    for i in range(len(text) // 4):
        w = text[i * 4:i * 4 + 4]
        pc = T_ADDR + i * 4
        try:
            ins = next(md.disasm(w, pc))
        except StopIteration:
            continue
        n_valid += 1
        track(ins, pc)

    report = {"schema": "ps1play-r12-hunt/1", "exe": exe_path,
              "t_addr": hex(T_ADDR), "t_size": hex(len(text)),
              "valid_instrs": n_valid, "sites": {}}

    def summarize(target):
        out = []
        for pc, kind, reg, extra in site_hits.get(target, []):
            f = owner(pc)
            out.append({"pc": hex(pc), "kind": kind, "reg": reg,
                        "extra": extra,
                        "func": f["va"] if f else None,
                        "func_name": f["name"] if f else None,
                        "func_size": f["size"] if f else None})
        return out

    for a, name in sorted(STRINGS.items()):
        report["sites"][f"str_{name}"] = {"addr": hex(a), "refs": summarize(a)}
    for a, name in sorted(GLOBALS.items()):
        report["sites"][f"g_{name}"] = {"addr": hex(a), "refs": summarize(a)}
    band = {}
    for lo, hi_a, tag in BAND_WINDOWS:
        d = defaultdict(list)
        for tgt, hits in site_hits.items():
            if lo <= tgt < hi_a:
                d[hex(tgt)] = summarize(tgt)
        band[tag] = dict(sorted(d.items(), key=lambda kv: int(kv[0], 16)))
    report["sites"]["windows"] = band

    json.dump(report, open(os.path.join(OUT, "hunt_report.json"), "w"),
              indent=1)
    print("exe:", exe_path)
    print("valid instrs:", n_valid, "distinct targets:", len(site_hits))
    for key in sorted(report["sites"]):
        v = report["sites"][key]
        refs = v["refs"] if isinstance(v, dict) and "refs" in v else v
        n_r = len(refs) if isinstance(refs, list) else sum(
            len(x) for x in refs.values())
        print(f"{key:34s} refs={n_r}")


if __name__ == "__main__":
    main()
