#!/usr/bin/env python3
"""smallgames_sweep.py — one fresh boot + input-causality probe per
small local game (<30 MB), one PROCESS per game (H5 rule: a second
in-process boot returns stale state).

Games swept (owner directive: "test the small games we have"):
  tetrade   — homebrew MIT (license-patched local image)
  psxmc     — PSX-Minecraft infdev, MIT (license-patched local image)
  nortis    — homebrew, no license (license-patched local image; stays
              BLOCKED for distribution, played locally only)
  poy_poy   — retail USA disc (owner-supplied download source)
  trap_gunner — retail USA disc (owner-supplied download source)

Evidence: /home/z/my-project/emu/games_psx/evidence/sweep_<gid>/
Local only — disc images are never committed.
"""
import json
import os
import subprocess
import sys
import time

EVID = "/home/z/my-project/emu/games_psx/evidence"
GAMES = [
    ("tetrade", "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"),
    ("psxmc", "/home/z/my-project/emu/games_homebrew/patched/PSXMC_lic.cue"),
    ("nortis", "/home/z/my-project/emu/games_homebrew/patched/nortis_lic.cue"),
    ("poy_poy", "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"),
    ("trap_gunner",
     "/home/z/my-project/emu/games_psx/trap_gunner/Trap Gunner (USA).cue"),
]


def main():
    only = sys.argv[1:] or [g for g, _ in GAMES]
    summary = {}
    for gid, cue in GAMES:
        if gid not in only:
            continue
        if not os.path.exists(cue):
            summary[gid] = {"verdict": "MISSING_CUE", "cue": cue}
            continue
        t0 = time.time()
        r = subprocess.run(
            [sys.executable,
             "/home/z/my-project/ps1ai/scripts/boot_test_psx_smallgames.py",
             gid, cue],
            capture_output=True, text=True, timeout=420)
        rep = os.path.join(EVID, f"{gid}_boot", "report.json")
        out = {}
        if os.path.exists(rep):
            with open(rep) as f:
                out = json.load(f)
        out["sweep_wall_s"] = round(time.time() - t0, 1)
        out["rc"] = r.returncode
        summary[gid] = out
        print(f"[sweep] {gid}: {out.get('verdict')} "
              f"({out.get('sweep_wall_s')}s)")
    os.makedirs(EVID, exist_ok=True)
    with open(os.path.join(EVID, "sweep_summary.json"), "w") as f:
        json.dump(summary, f, indent=1, default=str)
    print(json.dumps({k: v.get("verdict") for k, v in summary.items()},
                     indent=1))


if __name__ == "__main__":
    main()
