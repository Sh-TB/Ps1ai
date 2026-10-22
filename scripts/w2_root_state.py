#!/usr/bin/env python3
"""w2_root_state.py — read the encounter state machine LIVE:
  ROOTP = u32(0x800C9A98)   (pointer slot)
  ROOT  = *ROOTP            (the object)
  handler = u32(ROOT+0)     (the current state handler!)
  + ROOT fields 0x2c/0x7a/0x7e/0x80/0xe4
at states: lock / arena2 — then disassemble the current handler head.
"""
from __future__ import annotations

import json
import os
import sys

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import msx_gate_probe as gp                     # noqa: E402

EVID = gp.EVID
ROOTP = 0x0C9A98


def probe(m, tag):
    ram = m.ram
    rootp = int.from_bytes(ram[ROOTP:ROOTP + 4], "little")
    info = {"ROOTP": hex(rootp)}
    if 0x80010000 <= rootp < 0x80200000:
        off = rootp - 0x80000000
        h = int.from_bytes(ram[off:off + 4], "little")
        info["handler"] = hex(h)
        for name, o in (("f2c", 0x2C), ("f7a", 0x7A), ("f7e", 0x7E),
                        ("f80", 0x80), ("e4", 0xE4), ("f0_2", 0x04),
                        ("f0_3", 0x08)):
            info[name] = hex(int.from_bytes(ram[off + o:off + o + 4],
                                            "little"))
        info["_root_off"] = hex(off)
    else:
        # maybe the slot itself IS the object (handle/index based)
        info["raw_words"] = [hex(int.from_bytes(ram[ROOTP + i * 4:
                                                ROOTP + i * 4 + 4],
                                                "little"))
                             for i in range(6)]
    gp.log(f"[{tag}] {json.dumps(info)}")
    return info


def disasm_handler(m, h, n=48):
    ram = m.ram
    off = h - 0x80000000
    md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
    ins = md.disasm(bytes(ram[off:off + n * 4]), h)
    return [f"{i.address:#x}: {i.mnemonic} {i.op_str}" for i in ins]


def main():
    p, fw = gp.boot()
    m = p.mem
    out = {}
    for tag, state in (("lock", "lock"), ("arena2", "arena2")):
        p.load_state(state)
        session = gp.freeze_now(p, f"w2rs_{tag}")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        info = probe(m, tag)
        out[tag] = info
        h = int(info.get("handler", "0"), 16)
        if h:
            lines = disasm_handler(m, h)
            out[tag + "_disasm"] = lines
            gp.log(f"--- handler {hex(h)} @ {tag}:")
            for l in lines[:36]:
                gp.log("   ", l)
        gp.unfreeze(session, f"w2rs_{tag}")
    json.dump(out, open(os.path.join(EVID, "w2_root_state.json"), "w"),
              indent=1)
    gp.log("saved w2_root_state.json")


if __name__ == "__main__":
    main()
