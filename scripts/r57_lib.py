#!/usr/bin/env python3
"""r57_lib.py — R57 shared round library.

THE SINGLE-SOURCE-OF-TRUTH passage detector (mission PART 2/5): the r53
band-jump convention on the full-res vision (the tracked gap band jumps
forward >60 px = one pipe passed). Every pipe count, every reward, every
teacher-cutoff decision in R57 goes through PassageCounter.

run_episode(): the R57 episode loop — 1-frame decision cadence (r15
verbatim), FLAP -> B edge semantics, visual game-over detection, no RAM
reads anywhere (assisted audits pass an explicit reader callback).
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


class PassageCounter:
    """Visual passage detector: one event per pipe, strictly increasing.

    fire(bx) -> bool. bx = the tracked gap band center x (full-res
    vision, flappy_gap_target_r15). The band moves LEFT with the pipes;
    when the tracker JUMPS to the next pipe (bx > last + 60) exactly one
    passage has happened. Missing detections (None) are skipped.
    """

    def __init__(self):
        self.last = None
        self.count = 0
        self.events = []          # step indices of fired passages

    def fire(self, bx, step):
        ev = False
        if bx is not None:
            if self.last is not None and bx > self.last + 60:
                self.count += 1
                self.events.append(int(step))
                ev = True
            self.last = float(bx)
        return ev


def gap_band_x(env_vision, fr, bird_y):
    """flappy_gap_target_r15 wrapped: returns the band center x or None."""
    from ps1play.learn.perception import (flappy_green_mask,
                                          flappy_gap_target_r15)
    green = flappy_green_mask(fr)
    _gc, bx = flappy_gap_target_r15(
        green, bird_y if bird_y is not None else -1)
    return bx


def run_episode(env, agent, k, budget, *, passage=None,
                audit_reader=None, on_step=None, tag=""):
    """One R57 episode: restore ready anchor -> k idle -> X press ->
    1-frame control steps. Returns the outcome dict.

    agent: .act(small) -> 'FLAP'/'HOVER' (or the LawOnV7Agent interface).
    passage: a PassageCounter instance (fresh per episode) — the ONLY
      pipe accounting in R57.
    audit_reader: optional assisted callback (assisted modes ONLY —
      teacher collection cross-checks; student rollouts pass None).
    on_step: optional callback(step, small, action) for collectors.
    """
    from ps1play.learn.games import _small_rgb
    from ps1play.learn.perception import flappy_bird_y

    env.start_episode(k)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    if passage is not None:
        passage.last = None
        passage.count = 0
        passage.events = []
    flaps = 0
    t0 = time.time()
    step = 0
    result = "budget"
    for step in range(budget):
        fr = env.frame()
        small = _small_rgb(fr)
        action = agent.act(small)
        if action == "FLAP":
            flaps += 1
        if on_step is not None:
            on_step(step, small, action, fr)
        env.run(1, {"B"} if action == "FLAP" else set())
        by, _n = flappy_bird_y(env.frame())
        if passage is not None:
            passage.fire(gap_band_x(env, env.frame(), by), step)
        if env.game_over(env.frame()):
            result = "death"
            break
    outcome = {
        "tag": tag, "k": int(k), "result": result,
        "pipes": passage.count if passage is not None else -1,
        "passage_events": (list(passage.events)
                           if passage is not None else []),
        "steps": step + 1, "flaps": flaps,
        "wall_s": round(time.time() - t0, 1),
    }
    if audit_reader is not None:
        outcome["audit"] = audit_reader()
    return outcome


def jsave(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
