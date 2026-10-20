#!/usr/bin/env python3
"""real_menu_timeout_test.py — is the mode-menu -> arcade-attract
transition an IDLE TIMEOUT (input-independent)?

E1: no input at all after boot; watch menu lifetime.
E2: one START tap at f2450 (menu stable); does the transition shift?
E3: periodic START taps; does the timer keep resetting?

If E1 transitions at ~f2800 like the CROSS runs did, the CROSS never
selected anything — the menu times out into the attract replay.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)

from ps1play.api import PS1Play  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
WORKSPACE = "/home/z/my-project/ps1-test/emu"
OUT = "/home/z/my-project/ps1-test/emu/autolab/real_menu_timeout"
os.makedirs(OUT, exist_ok=True)

END = 4000
SNAP_EVERY = 12

EXPS = {
    "E1_noinput": lambda f: "",
    "E2_start2450": lambda f: "START" if 2450 <= f < 2468 else "",
    "E3_start_loop": lambda f: "START" if (2400 <= f and
                                           (f - 2400) % 200 < 14) else "",
}


def small_diff(a, b):
    if a is None or b is None:
        return 999.0
    if a.shape != b.shape:
        b = np.asarray(Image.fromarray(b).resize((a.shape[1], a.shape[0])))
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def run_exp(p, name, btnfn):
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    snaps = []
    prev = None
    for f in range(1, END + 1):
        p.core.set_buttons(btnfn(f))
        p.core.run_frame()
        if f % SNAP_EVERY == 0:
            rgb = p.core.frame_rgb()
            if rgb is None:
                continue
            arr = np.asarray(rgb)
            Image.fromarray(arr).save(os.path.join(d, f"f{f:05d}.png"))
            ds = small_diff(arr, prev)
            snaps.append({"frame": f, "diff": round(ds, 2) if ds < 998 else None,
                          "mean": round(float(arr.mean()), 1)})
            prev = arr
    runs = []
    cur = None
    for s in snaps:
        same = cur is not None and s["diff"] is not None and s["diff"] < 1.5
        if same:
            cur["end"] = s["frame"]
        else:
            if cur:
                runs.append(cur)
            cur = {"start": s["frame"], "end": s["frame"], "mean": s["mean"]}
    if cur:
        runs.append(cur)
    print(f"== {name} ==")
    for r in runs:
        if r["end"] - r["start"] >= 36:
            print(f"  {r['start']:5d}-{r['end']:5d} mean={r['mean']:6.1f}")
    with open(os.path.join(d, "runs.json"), "w") as fh:
        json.dump(runs, fh, indent=1)


def main():
    for name, fn in EXPS.items():
        p = PS1Play(GAME, core=CORE, workspace=WORKSPACE,
                    var_overrides={b"beetle_psx_override_bios": b"openbios"},
                    verbose=False)
        p.boot()
        run_exp(p, name, fn)
        p.core.shutdown()


if __name__ == "__main__":
    main()
