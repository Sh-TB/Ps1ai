#!/usr/bin/env python3
"""scan_bombs_strict.py — find the REAL grenade-inventory word with a
strict multi-event series scan (Issue #2: every address must survive a
controlled in-game event before it is marked VERIFIED).

The trap this fixes: the previous live anchor (0xCAF9C) decremented -1
on two grenade presses but is actually an animation/scratch impostor
(series jumps 4->84->74). A real inventory counter satisfies ALL of:

  * exactly -1 per separated grenade press (4 presses)
  * constant during the idle gaps between presses
  * bounded 0..60 everywhere
  * idle-stable for 300 frames before the first press

Stage 1: numpy u16 sweep over the low 2MB across 9 boundary snapshots.
Stage 2: independent re-run of the same series for every survivor.
Output: candidate list + verdicts JSON (read-only, no RAM writes).
"""
import json
import os
import sys
import time

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np                                         # noqa: E402

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from mission import ensure_mission                         # noqa: E402

ZONE = 0x1FC000
OUT = os.path.join(labconfig.resolve_path("evidence_dir")
                   or os.path.join(_REPO, "evidence_local"),
                   f"bombs_scan_{time.strftime('%Y%m%d_%H%M%S')}.json")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def run_series(p):
    """4 separated grenade presses, NO long idle (the mission-1 opening
    is lethal to idlers); returns boundary u16/u8 snapshots."""
    snaps = []

    def snap():
        snaps.append(p.mem.ram[:ZONE].copy())

    p.core.run(45, set())           # brief settle only
    snap()                          # 0 settle
    p.core.run(30, set())
    snap()                          # 1 pre-press
    for ev in range(4):
        p.core.set_buttons({"A"})
        for _ in range(30):         # hold A across the throw anim
            p.core.run_frame()
        p.core.set_buttons(set())
        p.core.run(60, set())       # gap (explosion lands)
        snap()                      # after gap ev -> 2,4,6,8
    p._advance()
    return snaps


def analyze(snaps, width):
    """width=2: u16 words; width=1: u8 bytes."""
    if width == 2:
        a = [s.view("<u2").astype(np.int32) for s in snaps]
        off = 0
    else:
        a = [s.view(np.uint8).astype(np.int32) for s in snaps]
        off = 1
    idle_stable = a[1] == a[0]
    seq = [a[1], a[2], a[3], a[4], a[5]]   # pre-press, after each gap
    dec = np.ones(a[0].shape, bool)
    for k in range(4):
        dec &= (seq[k + 1] - seq[k]) == -1
    bounded = np.ones(a[0].shape, bool)
    for arr in seq:
        bounded &= (arr >= 0) & (arr <= 60)
    return np.flatnonzero(idle_stable & dec & bounded), off


def main():
    game = labconfig.resolve_path("game")
    core = labconfig.resolve_path("core")
    workspace = labconfig.resolve_path("workspace")
    fw = labconfig.resolve_firmware(
        os.environ.get("M1_FIRMWARE", "auto"), workspace)
    kw = {}
    if core:
        kw["core"] = core
    if workspace:
        kw["workspace"] = workspace
    if fw["override_vars"]:
        kw["var_overrides"] = fw["override_vars"]
    p = PS1Play(game, **kw)
    log("boot:", p.boot())
    r = p.enter_gameplay3()
    if not r.get("in_game"):
        sys.exit("!! boot failed")
    m = ensure_mission(p, tries=6, log=log)
    if not m.get("in_mission"):
        sys.exit("!! gate failed")
    p.save_state("sb")

    t0 = time.time()
    snaps = run_series(p)
    # death guard: an unresponsive window means no throw happened
    from mission import responsive
    ok, gate = responsive(p)
    log(f"post-series responsive={ok} gate={gate}")
    c16, _ = analyze(snaps, 2)
    c8, _ = analyze(snaps, 1)
    log(f"stage1: u16 cands={len(c16)} "
        f"{[hex(int(w) * 2) for w in c16[:12]]} | "
        f"u8 cands={len(c8)} "
        f"{[hex(int(w)) for w in c8[:12]]} "
        f"wall={time.time() - t0:.1f}s")

    # stage 2: independent re-run per candidate (u16 first, then u8)
    survivors = []
    for w in c16.tolist():
        addr = int(w) * 2
        p.load_state("sb")
        s2 = run_series(p)
        a = [s.view("<u2").astype(np.int32) for s in s2]
        vals = [int(a[1][w]), int(a[2][w]), int(a[3][w]),
                int(a[4][w]), int(a[5][w])]
        ok2 = all(vals[k + 1] - vals[k] == -1 for k in range(4))
        log(f"  u16 cand {addr:#x}: series {vals} -> "
            f"{'CONFIRM' if ok2 else 'reject'}")
        if ok2:
            survivors.append({"addr": hex(addr), "dtype": "u16",
                              "series": vals})
    for b in c8.tolist():
        addr = int(b)
        p.load_state("sb")
        s2 = run_series(p)
        a = [s.view(np.uint8).astype(np.int32) for s in s2]
        vals = [int(a[1][b]), int(a[2][b]), int(a[3][b]),
                int(a[4][b]), int(a[5][b])]
        ok2 = all(vals[k + 1] - vals[k] == -1 for k in range(4))
        log(f"  u8  cand {addr:#x}: series {vals} -> "
            f"{'CONFIRM' if ok2 else 'reject'}")
        if ok2:
            survivors.append({"addr": hex(addr), "dtype": "u8",
                              "series": vals})
    p.load_state("sb")

    out = {"zone": ZONE,
           "post_series_responsive": bool(ok),
           "stage1_u16": [hex(int(w) * 2) for w in c16.tolist()],
           "stage1_u8": [hex(int(w)) for w in c8.tolist()],
           "survivors": survivors,
           "note": "strict 4-press series (-1 each, bounded, "
                   "idle-stable); read-only scan",
           "wall_s": round(time.time() - t0, 1)}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    log("saved ->", OUT)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
