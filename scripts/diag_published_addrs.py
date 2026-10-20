#!/usr/bin/env python3
"""diag_published_addrs.py — do the PUBLISHED gamehacking.org DATA
addresses hold the real counters in this boot?

Background: the live '-1 per grenade x2' anchor at 0xCAF9C turned out to
be an impostor (animation/scratch word — series jumps 4->84->74). That
invalidates the derived 'cluster delta' concept. This diagnostic tests
the PUBLISHED static addresses directly with a strict multi-event
series (3 separated grenade presses + long idle):

  bombs  0x0398B4   lives 0x0475A8   hp    0x032764
  timer  0x0295F8   ammo  0x02DCD8   weapon 0x02D92C

A REAL inventory counter: bounded, exactly -1 per separated throw,
constant between throws, idle-stable over hundreds of frames.
Prints per-address series summary + verdicts. Read-only.
"""
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from mission import ensure_mission                         # noqa: E402

PUB = {"bombs": 0x0398B4, "ammo": 0x02DCD8, "hp": 0x032764,
       "lives": 0x0475A8, "timer": 0x0295F8, "weapon": 0x02D92C}


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
    log("boot:", p.boot())
    r = p.enter_gameplay3()
    if not r.get("in_game"):
        sys.exit("!! boot failed")
    m = ensure_mission(p, tries=6, log=log)
    if not m.get("in_mission"):
        sys.exit("!! gate failed")
    p.save_state("pbase")

    # --- series: idle 60f, then 3 separated grenade presses ----------
    def series(addr):
        p.load_state("pbase")
        p.core.run(60, set())
        out = [("idle", p.mem.u16(addr))]
        for ev in range(3):
            p.core.set_buttons({"A"})
            for _ in range(15):
                p.core.run_frame()
            p.core.set_buttons(set())
            p.core.run(100, set())
            p._advance()
            out.append((f"after_press_{ev}", p.mem.u16(addr)))
        return out

    results = {}
    for role, addr in PUB.items():
        s = series(addr)
        vals = [v for _, v in s]
        results[role] = s
        log(f"{role:7s} @{addr:#x}: {s}")

    # verdicts
    b = [v for _, v in results["bombs"]]
    bombs_like = (all(0 <= v <= 60 for v in b)
                  and b[1] == b[0] - 1 and b[2] == b[1] - 1
                  and b[3] == b[2] - 1)
    h = [v for _, v in results["hp"]]
    print("\nVERDICTS")
    print(f"  bombs_published_series={b} -> bombs_like={bombs_like}")
    print(f"  hp series={h}")
    for role in ("ammo", "lives", "timer", "weapon"):
        print(f"  {role} series={[v for _, v in results[role]]}")


if __name__ == "__main__":
    main()
