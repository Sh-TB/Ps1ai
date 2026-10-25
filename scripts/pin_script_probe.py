#!/usr/bin/env python3
"""pin_script_probe.py — the live side of the D7 release correlation.

Static findings this probe tests (scripts/pin_release_disasm.py):
  * the section-script dispatcher fn 0x80021128 consumes a 30-byte
    script template copied from 0x80010DB8 onto its stack; the opcode
    byte = template[cursor] with valid opcodes 0x01..0x0D;
  * the runner id (s16, -1 = inactive) lives at 0x800EB588;
  * a u16 gate at 0x800EB5C6 (== 9 triggers a special arm);
  * the ticker fn 0x80022500 supplies the cursor (a1).

So at the D7 pin the CURRENT script bytes + cursor = the exact pending
release condition.  This probe polls, every 15f from `pin_ckpt`:
  * the script buffer 0x80010DB8..0x80010DF0 (as bytes),
  * cursor candidates: u32/u16 around 0x80022C00..0x80022C20 and
    0x800EB580..0x800EB5F8,
  * the walker words (state/flags/progress) and the scroll struct.

READ-ONLY.  Usage: python3 scripts/pin_script_probe.py
"""
import json
import os
import sys
import time
import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from ps1play import labconfig
from issue4_controller import boot
import ps1play.agent.combat as combat

EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_chopper_hunt")

SCRIPT_LO, SCRIPT_HI = 0x80010DB0, 0x80010DF0
CURSOR_CANDS = [0x80022BF0 + 4 * k for k in range(12)] + \
               [0x80022C04, 0x80022C08, 0x80022C0C]
WALKER_WORDS = [0x800EB588, 0x800EB58C, 0x800EB590, 0x800EB5C0,
                0x800EB5C4, 0x800EB5C6, 0x800EB5C8, 0x800EB5D0,
                0x800EB5D4, 0x800EB5F4]


def main():
    os.makedirs(EVID, exist_ok=True)
    tag = time.strftime("%H%M%S")
    out = os.path.join(EVID, f"pin_script_{tag}.jsonl")
    p, fw = boot()
    m = p.mem
    p.load_state("pin_ckpt")

    def word(va):
        return int.from_bytes(m.ram[va - 0x80000000:va - 0x80000000 + 4]
                              .tobytes(), "little")

    with open(out, "w") as jf:
        for k in range(80):
            rec = {"k": k, "f": p.core.frames_run,
                   "px": round(int(m.u32(0x0CA2E0)) / 65536.0, 1),
                   "script_bytes": m.ram[
                       SCRIPT_LO - 0x80000000:
                       SCRIPT_HI - 0x80000000].tobytes().hex(),
                   "cursor_cands": {hex(va): word(va)
                                    for va in CURSOR_CANDS},
                   "walker": {hex(va): word(va)
                              for va in WALKER_WORDS},
                   "sec": (int(m.u16(combat.SECTION_STATE)),
                           int(m.u16(combat.SECTION_FLAGS))),
                   "score": int(m.u32(0x0EE318))}
            jf.write(json.dumps(rec, default=str) + "\n")
            jf.flush()
            if k % 8 == 0:
                print(f"k{k:02d} px={rec['px']:7.1f} "
                      f"sec={rec['sec']} "
                      f"runner={rec['walker']['0x800eb588']:#x} "
                      f"script={rec['script_bytes'][:40]}",
                      file=sys.stderr, flush=True)
            p.core.run(15, set())
    print("wrote", out, file=sys.stderr)


if __name__ == "__main__":
    main()
