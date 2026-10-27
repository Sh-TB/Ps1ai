#!/usr/bin/env python3
"""poypoy_r17_realmatch.py — Round 17: START exits PRACTICE into the REAL MATCH.

Round-16 verified ladder (checkpoints in ws_poypoy_menu22): title --START-->
MODE SELECT --B--> PLAYER SET UP --B--> PLAYER ENTRY --B--> GLOVE SET UP
--B x4--> PRACTICE arena (m23_last.ckpt; census REAL_MATCH left_vs_right
54,357 / det_none 0). The arena banner says "PRESS THE START BUTTON TO EXIT
PRACTICE". This probe: from m23_last.ckpt, press START, then a long
observation ladder, PNGs at every rung, a direction census at each stable
state, and checkpoints of the first distinct post-practice states so the
closed-loop agent can start from the real match.

Honest verdicts only:
  REAL_MATCH_ENTERED = a post-practice state where directions register
  (left_vs_right >> det_none) AND the frame differs from practice.
  Otherwise we record what actually happened with PNG evidence.
"""
import json
import os
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.api import PS1Play                                   # noqa

EVID = "/home/z/my-project/emu/games_psx/evidence/poypoy_r17_realmatch"
CUE = "/tmp/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
if not os.path.exists(CUE):
    CUE = "/home/z/my-project/emu/games_psx/poy_poy/Poy Poy (USA).cue"
WS = "/tmp/my-project/emu/games_psx/ws_poypoy_menu22"  # round-16 ladder workspace
PRACTICE = "/tmp/my-project/emu/games_psx/ws_poypoy_menu22/m23_last.ckpt"
_mangled = os.path.join(WS, "states", "_" + PRACTICE.lstrip("/").replace("/", "_") + ".state")
assert os.path.exists(_mangled), f"practice checkpoint missing: {_mangled}"


def snap(p, name):
    img = p.core.frame_rgb()
    if img is not None:
        Image.fromarray(img).save(os.path.join(EVID, name))
    return img


def ram(p):
    return np.frombuffer(bytes(p.mem.snapshot()), dtype=np.uint8).copy()


def census(p, ckpt):
    """LEFT/RIGHT/none census from a checkpoint (round-16 protocol)."""
    out = {}
    snaps = {}
    for name, btns in (("none", set()), ("left", {"LEFT"}), ("right", {"RIGHT"})):
        p.load_state(ckpt)
        p.core.run(120, set())
        p.core.run(90, btns)
        snaps[name] = ram(p)
        p.load_state(ckpt)
        p.core.run(120, set())
        p.core.run(90, set())
    n2 = ram(p)
    det = int((n2 != snaps["none"]).sum())
    out = {
        "det_none": det,
        "left_vs_right": int((snaps["left"] != snaps["right"]).sum()),
        "left_vs_none": int((snaps["left"] != n2).sum()),
        "right_vs_none": int((snaps["right"] != n2).sum()),
    }
    out["verdict"] = ("REAL_MATCH" if out["left_vs_right"] > max(500, 5 * out["det_none"])
                      else "not_yet")
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    out = {"started": time.strftime("%FT%TZ", time.gmtime()),
           "practice_ckpt": PRACTICE}
    p = PS1Play(CUE, workspace=WS)
    p.boot()
    p.wait(120)

    # 0. sanity: restore practice, confirm we are in the arena
    p.load_state(PRACTICE)
    p.core.run(120, set())
    snap(p, "r17_practice_restore.png")

    # 1. START press -> exit practice
    p.core.run(10, set())
    p.core.run(90, {"START"})          # the banner asks for START
    p.core.run(900, set())             # long settle: transition / VS screen / intro
    snap(p, "r17_after_start_900.png")
    ck_a = os.path.join(WS, "r17_a_afterstart.ckpt")
    p.save_state(ck_a)

    p.core.run(900, set())
    snap(p, "r17_after_start_1800.png")
    ck_b = os.path.join(WS, "r17_b_1800.ckpt")
    p.save_state(ck_b)

    # 2. census at each candidate state
    out["census_a"] = census(p, ck_a)
    snap(p, "r17_census_a.png")
    out["census_b"] = census(p, ck_b)
    snap(p, "r17_census_b.png")

    # 3. if still practice/transition, wait more from ck_b
    p.load_state(ck_b)
    p.core.run(2400, set())
    snap(p, "r17_b_plus_2400.png")
    ck_c = os.path.join(WS, "r17_c_4200.ckpt")
    p.save_state(ck_c)
    out["census_c"] = census(p, ck_c)
    snap(p, "r17_census_c.png")

    # 4. X (throw) + circle (jump) causality probe at the best real-match state
    best = max((("a", out["census_a"]), ("b", out["census_b"]), ("c", out["census_c"])),
               key=lambda kv: kv[1]["left_vs_right"])
    ck_best = {"a": ck_a, "b": ck_b, "c": ck_c}[best[0]]
    out["best_state"] = best[0]
    probes = {}
    for name, btns in (("X", {"B"}), ("circle", {"A"}), ("square", {"X"})):
        p.load_state(ck_best)
        p.core.run(60, set())
        p.core.run(30, btns)
        p.core.run(150, set())
        probes[name] = ram(p)
        p.load_state(ck_best)
        p.core.run(60, set())
        p.core.run(180, set())
    base = ram(p)
    out["button_probes"] = {k: int((v != base).sum()) for k, v in probes.items()}

    out["finished"] = time.strftime("%FT%TZ", time.gmtime())
    with open(os.path.join(EVID, "r17_realmatch.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print(json.dumps({k: out[k] for k in ("census_a", "census_b", "census_c",
                                          "best_state", "button_probes")}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
