#!/usr/bin/env python3
"""msx_gate_scriptscan.py — locate the TOWN ARENA's script-state pointer.

Static facts (msx_gate_static*.py): ENEMY.BIN's encounter state machine
keeps its ROOT object pointer at *(0x800C9A98) and installs handlers in
the 0x800B0000+ module — but that slot reads 0xA0 (uninitialized) in the
town arena, so the arena is driven by a DIFFERENT controller object.

This probe diffs pointer-like words (values in the code/handler ranges)
across the arena timeline to find the live controller fields:
  snapshot A: 60f after load (freeze on)
  snapshot B: after 1800f of the upy_left (dodge+anti-air) cadence
  diff: words whose VALUE changed within [0x80010000, 0x80100000)
Report: address, valueA, valueB, region tag. Saved to script_scan.json.
"""
from __future__ import annotations

import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from issue4_controller import boot                        # noqa: E402
from mission import ensure_mission                        # noqa: E402

EVID = os.path.join(labconfig.resolve_path("evidence_dir"),
                    "issue5_gate_probe")

SCAN_LO, SCAN_HI = 0x0C0000, 0x0E0000      # RAM window (entity/system)
PTR_LO, PTR_HI = 0x80010000, 0x80100000    # pointer value range


def ptr_scan(p):
    m = p.mem
    out = {}
    for a in range(SCAN_LO, SCAN_HI, 4):
        v = m.u32(a)
        if PTR_LO <= v < PTR_HI:
            out[a] = v
    return out


def main():
    p, fw = boot()
    g = ensure_mission(p, tries=4, log=print, want_hp_cands=False)
    p.load_state("arena_pristine")
    # freeze via the same proven pattern
    from msx_gate_probe import freeze_now, _arm_frame
    session = freeze_now(p, "scriptscan")
    for _ in range(2):
        p.core.run_frame()
        session.gs.tick()
    for _ in range(60):                        # dismount prelude
        phase = _arm_frame(p, session, {"LEFT"}, 0)
    A = ptr_scan(p)
    phase = 60
    for f in range(1800):                      # dodge + anti-air
        btns = {"LEFT", "UP", "Y"} if (f % 80) < 40 else set()
        phase = _arm_frame(p, session, btns, phase)
    B = ptr_scan(p)
    diffs = []
    for a in sorted(set(A) | set(B)):
        va, vb = A.get(a, 0), B.get(a, 0)
        if va != vb:
            region = ("EXE" if va < 0x800A7800 or vb < 0x800A7800
                      else "OVL" if va < 0x800B0000 or vb < 0x800B0000
                      else "HANDLER")
            diffs.append({"addr": f"0x{a:06X}", "A": f"0x{va:08X}",
                          "B": f"0x{vb:08X}", "region": region})
    print(f"pointer-like words: A={len(A)} B={len(B)} changed={len(diffs)}")
    for d in diffs[:80]:
        print(f"  {d['addr']}: {d['A']} -> {d['B']} [{d['region']}]")
    json.dump({"A_count": len(A), "B_count": len(B), "diffs": diffs},
              open(os.path.join(EVID, "script_scan.json"), "w"), indent=1)
    print("saved -> script_scan.json")


if __name__ == "__main__":
    main()
