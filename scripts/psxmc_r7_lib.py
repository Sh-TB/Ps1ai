#!/usr/bin/env python3
"""psxmc_r7_lib.py — shared helpers for Task 17-b (PSX-Minecraft round 7:
world-modification + persistence causality).

Conventions follow the lab: madiff = mean abs frame diff (float),
changed_px = count of pixels differing in any channel + bbox,
one beetle boot per process, honest verdict vocabulary.
"""
import hashlib
import json
import os
import time

import numpy as np

A_PLAYER = 0x3C608          # map symbol `player` (live-verified r3)
A_WORLD = 0x3C61C           # map symbol `world`
A_TIME = 0x3C5A0
A_INPUT = 0x3C73C           # game Input global (pad_buffer[2][34] first)
PADBUFF_SIG = b"\x00\x41\xff\xff"   # beetle pad buffer id bytes (0xBB120/0xBB142)
ONE_BLOCK = 286720          # source ONE*BLOCK_SIZE (spawn y 2867200 = 10 blocks)

# upstream ground truth (src/core/input/bindings.c @ infdev_2025_04_18):
#   BINDING_USE = PAD_L2 / BINDING_ATTACK = PAD_R2
#   BINDING_PREVIOUS = PAD_L3 / BINDING_NEXT = PAD_R3   (hotbar selector)
#   BINDING_OPEN_INVENTORY = PAD_START
#   LOOK: UP=TRIANGLE DOWN=CROSS LEFT=SQUARE RIGHT=CIRCLE


def madiff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return None
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


def changed_px(a, b):
    """(count, [x0,y0,x1,y1]) of pixels differing in any channel."""
    if a is None or b is None or a.shape != b.shape:
        return None, None
    d = np.any(a.astype(np.int16) != b.astype(np.int16), axis=2)
    n = int(d.sum())
    if n == 0:
        return 0, None
    ys, xs = np.nonzero(d)
    return n, [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def sha(b):
    return hashlib.sha256(b).hexdigest()


def words_changed(s0, s1):
    return int(np.count_nonzero(
        np.frombuffer(s0, "<u4") != np.frombuffer(s1, "<u4")))


class Evid:
    """JSONL journal + PNG sink + report accumulator (one run)."""

    def __init__(self, out_dir, tag):
        self.dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.tag = tag
        self.jpath = os.path.join(out_dir, f"r7_{tag}.jsonl")
        self.report = {"started": time.strftime("%FT%TZ", time.gmtime()),
                       "steps": {}}
        self.t0 = time.time()
        self.png_count = 0

    def wall(self):
        return round(time.time() - self.t0, 1)

    def j(self, ev):
        ev = {"t": self.wall(), **ev}
        with open(self.jpath, "a") as f:
            f.write(json.dumps(ev, default=str) + "\n")
        print(f"[{self.wall():7.1f}s] {json.dumps(ev, default=str)[:220]}",
              flush=True)

    def png(self, name, frame):
        if frame is None:
            return None
        from PIL import Image
        p = os.path.join(self.dir, f"{name}.png")
        Image.fromarray(frame).save(p)
        self.png_count += 1
        return p

    def step(self, name, data):
        self.report["steps"][name] = data
        self.j({"ev": "step_done", "step": name})

    def finish(self, verdict):
        self.report["verdict"] = verdict
        self.report["finished"] = time.strftime("%FT%TZ", time.gmtime())
        self.report["wall_s"] = self.wall()
        self.report["png_count"] = self.png_count
        rp = os.path.join(self.dir, f"report_{self.tag}.json")
        with open(rp, "w") as f:
            json.dump(self.report, f, indent=1, default=str)
        self.j({"ev": "RUN_DONE", "verdict": verdict, "report": rp})
        return rp


def idle_window(core, grab, n=8):
    """Sample n consecutive rendered frames (1 emu frame apart);
    return list of frames + bit-exact bool."""
    core.run(1)
    frames = [grab()]
    exact = True
    for _ in range(n - 1):
        core.run(1)
        f = grab()
        exact = exact and np.array_equal(frames[-1], f)
        frames.append(f)
    return frames, bool(exact)
