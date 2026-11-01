#!/usr/bin/env python3
"""r64_diag_polluted_boot2.py — the close/shutdown hypothesis.

plugins_contract's in-process tests call p.core.shutdown() (the
`hasattr close -> False` fallback hits `shutdown` in the real test?
No — the test calls p.core.close() only if it exists, else NOTHING).
Hmm: LibretroCore has no close — so the polluter tests LEAK their
core. Reproduce exactly: leak a booted core (no close), then boot the
R64 way, then scan.
"""
import sys

sys.path.insert(0, "/home/z/my-project/ps1ai")
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
OV = {"beetle_psx_override_bios": "openbios"}
from ps1play.api import PS1Play  # noqa: E402


def find_bases(ram, allow_paused=False):
    a4 = ram.view("<i4")
    n = len(a4)
    wins = sliding_window_view(a4, 200)[: n - 590]
    for vmax in (7, 15):
        ok = ((wins >= 0) & (wins <= vmax)).all(axis=1)
        nz = ((wins > 0).sum(axis=1) <= 80)
        cand = np.flatnonzero(ok & nz)
        if not len(cand):
            continue
        c4 = cand * 4
        at = lambda off: a4[(c4 + off) // 4]  # noqa: E731
        t_cur, t_next = at(800), at(896)
        m = (((t_cur >= 1) & (t_cur <= 7)) | (t_cur == -1)) \
            & (t_next >= 1) & (t_next <= 7) \
            & (at(2304) == 0) & (at(2276) == 0) & (at(2312) == 0)
        if not allow_paused:
            m = m & (at(2316) == 0)
        hits = c4[m]
        if len(hits):
            return [int(h) for h in hits]
    return []


def entry_attempt(p, tag, rescan=30):
    p.core.run(900, set())
    p.core.run(60, set())
    p.core.run(120, {"START"})
    p.core.run(240, set())
    p.core.run(12, {"B"})
    p.core.run(60, set())
    p.core.run(4, {"START"})
    p.core.run(280, set())
    p.core.run(4, {"START"})
    p.core.run(120, set())
    bases = []
    for i in range(rescan):
        ram = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8)
        bases = find_bases(ram)
        live = [b for b in bases
                if 1 <= int(ram.view("<i4")[(b + 800) // 4]) <= 7]
        if live:
            print(f"[{tag}] STRUCT at {hex(live[0])} ({i} rescans)")
            return live[0]
        p.core.run(20, set())
    print(f"[{tag}] NO STRUCT (candidates={len(bases)})")
    return None


# exactly what the two plugins tests do: boot, play, LEAK (no close)
print("== polluter 1: boots_through_core (leak, no close) ==")
pA = PS1Play(CUE, workspace="/tmp/r64_diag2_wsA", var_overrides=OV)
pA.boot()
pA.wait(300)
pA.save_state("smoke_origin")
pA.core.run(90, set())
sA = pA.mem.snapshot()
pA.load_state("smoke_origin")
pA.core.run(90, set())
sA2 = pA.mem.snapshot()
print("  replay identical:", bytes(sA) == bytes(sA2))

print("== polluter 2: lic causality (xfail path, leak) ==")
pB = PS1Play(CUE, workspace="/tmp/r64_diag2_wsB", var_overrides=OV)
pB.boot()
pB.core.run(600, set())
pB.save_state("smoke_origin")
pB.core.run(90, set())
sB = pB.mem.snapshot()
pB.load_state("smoke_origin")
pB.core.run(90, {"RIGHT"})
sB2 = pB.mem.snapshot()
print("  divergence cells:",
      int(np.count_nonzero(bytes(sB) != bytes(sB2)) > 0))

print("== victim: the R64 registry boot (3rd in-process core) ==")
pC = PS1Play(CUE, workspace="/tmp/r64_diag2_wsC", var_overrides=OV)
pC.boot()
base = entry_attempt(pC, "victim")
print("VICTIM:", "OK" if base else "BROKEN")
