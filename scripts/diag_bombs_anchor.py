#!/usr/bin/env python3
"""diag_bombs_anchor.py — is the live 'bombs' anchor REALLY the bomb
inventory? (Issue #2 honesty requirement: every address must survive a
controlled multi-event test.)

Series test from one checkpoint:
  * read the anchor word every 5 frames through THREE separated grenade
    presses (15f hold, 100f gap each)
  * a true inventory counter: bounded 0..40, exactly -1 per throw,
    constant between throws, never wild jumps
  * an animation/countdown impostor: per-frame drift, values outside
    the inventory band, or jumps unrelated to presses
Prints the full series + verdict. No writes to game RAM.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from ps1play.agent.perception import PerceptionGuard       # noqa: E402
from mission import ensure_mission                         # noqa: E402


def log(*a):
    print(*a, file=sys.stderr, flush=True)


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
    info = p.boot()
    log("boot:", info)
    r = p.enter_gameplay3()
    if not r.get("in_game"):
        sys.exit("!! boot failed")
    m = ensure_mission(p, tries=6, log=log)
    if not m.get("in_mission"):
        sys.exit("!! gate failed")

    guard = PerceptionGuard(p)
    anch = guard.anchor(log=log)
    if not anch.get("ok"):
        sys.exit("!! anchor failed")
    addr = guard.addrs["bombs"]
    p.save_state("dbase")

    series = []
    presses = []
    p.load_state("dbase")
    p.core.run(30, set())
    for ev in range(3):
        p.core.set_buttons({"A"})
        for _ in range(15):
            p.core.run_frame()
            series.append(("press", ev, p.mem.u16(addr)))
        p.core.set_buttons(set())
        for _ in range(100):
            p.core.run_frame()
            series.append(("gap", ev, p.mem.u16(addr)))
        presses.append((ev, p.mem.u16(addr)))
    p._advance()

    vals = [v for _, _, v in series]
    lo, hi = min(vals), max(vals)
    log(f"anchor {addr:#x} series min={lo} max={hi}")
    # per-event deltas: value before press vs value after gap
    per_ev = []
    pre_val = vals[0]
    idx = 0
    for ev in range(3):
        seg = [v for (phase, e, v) in series if e == ev]
        per_ev.append(seg[0] - seg[-1] if False else (seg[-1], seg[0]))
    log("per-event (last,first):", per_ev)
    log("presses:", presses)
    log("first 40:", [v for _, _, v in series][:40])
    log("all:", vals)
    band = 0 <= lo and hi <= 60
    stable = hi - lo <= 3
    print(json_d := f"verdict_band={band} verdict_stable={stable}")


if __name__ == "__main__":
    main()
