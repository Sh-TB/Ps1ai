#!/usr/bin/env python3
"""r64_diag_polluted_boot.py — diagnose the second in-process boot.

Reproduces the suite-context failure: an in-process tetrade boot
(like tests/test_plugins_contract.py does) followed by the R64
registry boot, then compares the R63 entry sequence's progress
between a clean FIRST boot and the polluted SECOND boot.
"""
import sys

sys.path.insert(0, "/home/z/my-project/ps1ai")
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
OV = {"beetle_psx_override_bios": "openbios"}

sys.path.insert(0, "/home/z/my-project/ps1ai")
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


def entry_attempt(p, tag):
    """The R63 entry sequence + scan; reports what happened."""
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
    for i in range(30):
        ram = np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8)
        bases = find_bases(ram)
        live = [b for b in bases
                if 1 <= int(ram.view("<i4")[(b + 800) // 4]) <= 7]
        if live:
            print(f"[{tag}] STRUCT FOUND at {hex(live[0])} "
                  f"after {i} rescans")
            return live[0]
        p.core.run(20, set())
    print(f"[{tag}] NO STRUCT (candidates={len(bases)})")
    return None


# ---- 1. the polluter: in-process boot like plugins_contract ---------
print("== polluter boot (plugins_contract style) ==")
p1 = PS1Play(CUE, workspace="/tmp/r64_diag_ws1", var_overrides=OV)
info1 = p1.boot()
print("boot1:", {k: info1[k] for k in ("plugin", "ram_bytes")})
p1.core.run(300, set())
p1.core.run(90, set())

# ---- 2. the R64 registry-style boot in the SAME process -------------
print("== second boot (R64 registry style) ==")
p2 = PS1Play(CUE, workspace="/tmp/r64_diag_ws2", var_overrides=OV)
info2 = p2.boot()
print("boot2:", {k: info2[k] for k in ("plugin", "ram_bytes")})
base = entry_attempt(p2, "second-boot")
if base is None:
    # where is the game? dump diagnostics
    fr = p2.core.frame_rgb()
    from PIL import Image
    Image.fromarray(fr).save(
        "/tmp/r64_diag_second_boot.png")
    print("second-boot frame saved; frame mean:",
          float(np.mean(fr)))
    # retry once from wherever we are
    base = entry_attempt(p2, "second-boot-retry")

# ---- 3. a THIRD boot in the same process for contrast ---------------
print("== third boot ==")
p3 = PS1Play(CUE, workspace="/tmp/r64_diag_ws3", var_overrides=OV)
info3 = p3.boot()
print("boot3:", {k: info3[k] for k in ("plugin", "ram_bytes")})
base3 = entry_attempt(p3, "third-boot")
print("DIAG VERDICT:",
      "second-boot OK" if base else "second-boot BROKEN",
      "| third-boot OK" if base3 else "| third-boot BROKEN")
