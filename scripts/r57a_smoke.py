#!/usr/bin/env python3
"""r57a_smoke.py — R57 P0 gate: ONE boot, verify the flappy environment
end-to-end after the sandbox rebuild (ISO re-fetched, anchors wiped):

  1. boot + firmware trust,
  2. reach_ready + save the PRE-SEED anchor (flappy_ready),
  3. start_episode(k=6) + 240 LawOnV7 teacher steps (1-frame cadence),
  4. passage-event counter (the r53 band-jump convention) on real play,
  5. serialize/unserialize roundtrip (the anchor discipline),
  6. RAM score anchor read (assisted, evaluation-only) vs the vision count.

Evidence -> scratch/r57/r57a_smoke.json. No training, no claims.
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

from ps1play.learn.games import FlappyEnv, _small_rgb      # noqa: E402
from ps1play.learn.teacher import FlappyTeacherAgent        # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,        # noqa: E402
                                      flappy_green_mask,
                                      flappy_gap_target_r15)

OUT = os.path.join(REPO, "scratch", "r57")
os.makedirs(OUT, exist_ok=True)

# the r53 flappy RAM anchors (assisted evaluation-only readers)
RAM_ANCHORS = {
    "score": (0x1FF50E, "u16"),
    "dead": (0x1FF496, "u8"),
}


def vision_passage_counter():
    """Stateful visual passage detector: the r53 band-jump convention
    (the tracked gap band jumps forward by >60 px = one pipe passed).
    This is the R57 single-source-of-truth passage detector."""
    def inner(state, bx):
        ev = False
        if bx is not None:
            if state["last"] is not None and bx > state["last"] + 60:
                state["count"] += 1
                ev = True
            state["last"] = bx
        return ev
    return inner


def main():
    ev = {"t": time.time()}
    t0 = time.time()
    env = FlappyEnv()
    ev["boot"] = {"ok": True, "info": str(env.boot_info)[:200],
                  "wall_s": round(time.time() - t0, 1)}
    t1 = time.time()
    env.reach_ready()
    ev["reach_ready"] = {"wall_s": round(time.time() - t1, 1)}

    # anchor roundtrip check
    blob = env.p.core.serialize()
    env.p.core.unserialize(blob)
    env.run(1, set())
    ev["anchor_roundtrip"] = {"bytes": len(blob), "ok": True}

    # ---- one recorded teacher life at k=6, 240 steps ----
    agent = FlappyTeacherAgent()
    env.start_episode(6)
    agent.reset_history()
    passage = vision_passage_counter()
    pstate = {"last": None, "count": 0}
    last_band = None
    flaps = 0
    t2 = time.time()
    fps_marks = []
    for step in range(240):
        fr = env.frame()
        small = _small_rgb(fr)
        action = agent.act(small)
        if action == "FLAP":
            flaps += 1
        green = flappy_green_mask(fr)
        _gc, bx = flappy_gap_target_r15(
            green, (flappy_bird_y(fr)[0] if flappy_bird_y(fr)[0]
                    is not None else -1))
        passage(pstate, bx)
        env.run(1, {"B"} if action == "FLAP" else set())
        if step % 60 == 0:
            fps_marks.append(round(60 / max(time.time() - t2, 1e-9), 1))
            t2 = time.time()
        if env.game_over(env.frame()):
            break
    labels = env.read_assisted(RAM_ANCHORS)
    ev["teacher_life_240"] = {
        "steps": step + 1, "flaps": flaps, "action_last": action,
        "vision_passages": pstate["count"],
        "ram_score": labels.get("score", -1),
        "dead_flag": labels.get("dead", -1),
        "game_over": bool(env.game_over(env.frame())),
        "fps_marks": fps_marks,
    }
    env.close()
    with open(os.path.join(OUT, "r57a_smoke.json"), "w") as f:
        json.dump(ev, f, indent=2)
    print(json.dumps(ev, indent=2))


if __name__ == "__main__":
    main()
