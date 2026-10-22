#!/usr/bin/env python3
"""w2_disasm_live.py — dump 0x80012814..+0x700 from LIVE RAM (lock and
arena2) and disassemble: the scroll governor + clamp logic. Also dump
the camera globals: 0xCA2E0(u32), 0xD4938, 0xD4970, 0xD4974, 0xD4A1C.
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
GLOBAL_ADDR = [0x0CA2E0, 0x0D4938, 0x0D4970, 0x0D4974, 0x0D4A1C,
               0x0D4948, 0x0D494A]


def main():
    p, fw = gp.boot()
    m = p.mem
    out = {}
    for tag, state in (("lock", "lock"), ("arena2", "arena2")):
        p.load_state(state)
        session = gp.freeze_now(p, f"w2dl_{tag}")
        for _ in range(2):
            p.core.run_frame()
            session.gs.tick()
        cam = {hex(a): int.from_bytes(m.ram[a:a + 4].tobytes(), "little")
               for a in GLOBAL_ADDR}
        gp.log(f"[{tag}] camera globals: " + json.dumps(cam))
        code = bytes(m.ram[0x12814:0x12814 + 0x700])
        md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32)
        lines = [f"{i.address:#x}: {i.mnemonic} {i.op_str}"
                 for i in md.disasm(code, 0x80012814)]
        out[tag] = {"cam": cam, "disasm": lines}
        gp.unfreeze(session, f"w2dl_{tag}")
    json.dump(out, open(os.path.join(EVID, "w2_disasm_live.json"), "w"),
              indent=1)
    # print the interesting part: branches/cmps around 0x4A1C
    for tag in out:
        gp.log(f"===== {tag} disasm (first 80):")
        for l in out[tag]["disasm"][:80]:
            gp.log("  ", l)


if __name__ == "__main__":
    main()
