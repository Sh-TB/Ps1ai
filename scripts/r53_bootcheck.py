#!/usr/bin/env python3
"""r53_bootcheck.py — verify both learning games boot after the asset
rebuild, classify the reached state, and save ANCHOR savestates for the
learning foundation (restore-based episode resets -> no boot per episode).

hello_pong: boot via the r12 lib route (license-patched bin), settle to a
fresh 0-0 game, save anchor `pong_anchor`.
FlappyBirdPSX: boot the release ISO (route 1), X-press through GET READY,
save anchors `flappy_ready` (pre-first-flap) + `flappy_flying`.

Evidence -> scratch/r53learn/bootcheck.jsonl
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                              # noqa: E402
from ps1play.api import PS1Play                            # noqa: E402
from hellopong_r12_lib import (                            # noqa: E402
    boot_hellopong, classify, make_jrn, save_png)

OUT = os.path.join(REPO, "scratch", "r53learn")
WS_PONG = "/home/z/my-project/emu/games_homebrew/ws_r53learn_pong"
WS_FLAP = "/home/z/my-project/emu/games_homebrew/ws_r53learn_flappy"
CUE_FLAP = "/home/z/my-project/emu/games_homebrew/flappybird.cue"
OPENBIOS_SRC = os.path.join(REPO, "third_party", "openbios", "openbios.bin")


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.join(OUT, "pong"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "flappy"), exist_ok=True)
    jr = make_jrn(OUT, "[bootcheck]")
    report = {}

    # ---------------- hello_pong ----------------
    t0 = time.time()
    p, _boot_info = boot_hellopong(WS_PONG, jr)
    p.core.run(600, set())          # settle well into the fresh game
    fr = p.core.frame_rgb()
    save_png(os.path.join(OUT, "pong"), fr, "settled.png")
    cls, facts = classify(fr, None)
    blob = p.core.serialize()
    anchor = os.path.join(OUT, "pong_anchor.bin")
    with open(anchor, "wb") as f:
        f.write(blob)
    report["pong"] = {
        "classify": cls, "facts": {k: v for k, v in facts.items()
                                   if isinstance(v, (int, float, str))},
        "anchor_bytes": len(blob), "anchor": anchor,
        "wall_s": round(time.time() - t0, 1)}
    jr({"ev": "pong_anchor_saved", "bytes": len(blob), "cls": cls})
    p.core.shutdown()

    # ---------------- FlappyBirdPSX ----------------
    t0 = time.time()
    os.makedirs(os.path.join(WS_FLAP, "system"), exist_ok=True)
    import shutil
    shutil.copyfile(OPENBIOS_SRC,
                    os.path.join(WS_FLAP, "system", "openbios.bin"))
    fw = labconfig.resolve_firmware("openbios", workspace=WS_FLAP)
    q = PS1Play(CUE_FLAP, workspace=WS_FLAP,
                var_overrides=fw["override_vars"])
    boot_info = q.boot()
    jr({"ev": "flappy_boot", "core": boot_info})
    q.core.run(900, set())          # reach GET READY
    fr = q.core.frame_rgb()
    save_png(os.path.join(OUT, "flappy"), fr, "getready.png")
    g = fr.mean(axis=2)
    report["flappy"] = {"getready_mean": round(float(g.mean()), 2)}
    # X press seeds RNG + first flap (the r15 route)
    q.core.run(3, {"X"})
    q.core.run(3, set())
    q.core.run(120, set())
    fr = q.core.frame_rgb()
    save_png(os.path.join(OUT, "flappy"), fr, "flying.png")
    blob = q.core.serialize()
    anchor = os.path.join(OUT, "flappy_flying.bin")
    with open(anchor, "wb") as f:
        f.write(blob)
    report["flappy"].update({"flying_mean": round(float(fr.mean()), 2),
                             "anchor_bytes": len(blob), "anchor": anchor,
                             "wall_s": round(time.time() - t0, 1)})
    # restore check: unserialize the same blob, run 30 frames, capture
    q.core.unserialize(blob)
    q.core.run(30, set())
    fr2 = q.core.frame_rgb()
    save_png(os.path.join(OUT, "flappy"), fr2, "restored_plus30.png")
    jr({"ev": "flappy_anchor_saved", "bytes": len(blob)})
    q.core.shutdown()

    with open(os.path.join(OUT, "bootcheck_report.json"), "w") as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
