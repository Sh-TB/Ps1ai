#!/usr/bin/env python3
"""playloop.py — Ps1ai reusable game-loop driver (Issue #6 round 6).

The per-round probe scripts (tetrade/nortis/psxmc/pong causality) all
re-implemented the same skeleton: boot -> settle -> act loop with
per-frame observation -> terminal detection -> restart/next-cycle ->
structured report.  This module factors that skeleton out ONCE, with:

  - subprocess-safe one-boot-per-process (the lab's hard rule: the
    tool boots exactly once per invocation and exits),
  - pluggable policies (per-game steering logic),
  - honest-verdict fields (BOOTED / INPUT_RESPONSIVE /
    STATE_CHANGE_CONFIRMED / GAMEPLAY_CONFIRMED / CAUSAL /
    INCONCLUSIVE / FAILED),
  - JSONL journal + report.json outputs.

Usage:
  python3 scripts/playloop.py --game pong --steps 400 \
      --out-dir scratch/issue6_round6_pong_tools

Policies register in POLICIES (name -> callable(playloop) -> policy
object with act(step, obs) and terminal(obs)).
"""
import argparse
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

PADBUFF_SIG = b"\x00\x41\xff\xff"


def madiff(a, b):
    if a is None or b is None:
        return None
    if a.shape != b.shape:
        return None
    return float(np.abs(a.astype(np.int16) - b.astype(np.int16)).mean())


class Observation:
    """Per-step observation bundle handed to policies."""

    def __init__(self, step, frame, prev_frame, padbuff_hits, state_raw):
        self.step = step
        self.frame = frame
        self.prev_frame = prev_frame
        self.madiff = madiff(prev_frame, frame)
        self.padbuff_hits = padbuff_hits
        self.state_raw = state_raw

    def png(self, path):
        if self.frame is None:
            return None
        from PIL import Image
        Image.fromarray(self.frame).save(path)
        return path


class Playloop:
    """ONE boot per process.  Composes ps1play's real APIs."""

    def __init__(self, cue, workspace, settle_frames=420,
                 padbuff_poll=40, padbuff_step=30, journal=None):
        from ps1play.api import PS1Play
        self.cue = cue
        self.workspace = workspace
        self.settle_frames = settle_frames
        self.padbuff_poll = padbuff_poll
        self.padbuff_step = padbuff_step
        self.p = None
        self.journal = journal or (lambda ev: None)
        self.t0 = None

    # ---- lifecycle ----
    def boot(self):
        from ps1play.api import PS1Play
        self.t0 = time.time()
        self.p = PS1Play(self.cue, workspace=self.workspace)
        self.p.boot()
        self.p.wait(self.settle_frames)
        hits = 0
        for _ in range(self.padbuff_poll):
            snap = bytes(self.p.mem.snapshot())
            hits = snap.count(PADBUFF_SIG)
            if hits > 0:
                break
            self.p.wait(self.padbuff_step)
        self.journal({"ev": "boot", "padbuff_hits": hits,
                     "wall_s": round(time.time() - self.t0, 1)})
        return {"booted": True, "padbuff_hits": hits}

    def observe(self, step):
        frame = self.p.core.frame_rgb()
        prev = getattr(self, "_prev_frame", None)
        snap = bytes(self.p.mem.snapshot())
        obs = Observation(step, frame, prev, snap.count(PADBUFF_SIG),
                          None)
        self._prev_frame = frame
        return obs

    def act(self, buttons, frames):
        self.p.core.run(frames, set(buttons))

    # ---- the loop ----
    def run(self, policy, max_steps, png_every=50, out_dir=None):
        steps = []
        verdict_evts = []
        for step in range(max_steps):
            obs = self.observe(step)
            if out_dir is not None and step % png_every == 0:
                obs.png(os.path.join(out_dir, f"pl_{step:04d}.png"))
            cmd = policy.act(step, obs)
            if cmd:
                buttons, frames = cmd
                self.journal({"ev": "act", "step": step,
                              "buttons": sorted(buttons),
                              "frames": frames,
                              "madiff": obs.madiff})
                self.act(buttons, frames)
            steps.append({"step": step, "madiff": obs.madiff,
                          "acted": bool(cmd)})
            term = policy.terminal(obs)
            if term:
                verdict_evts.append({"step": step, "kind": term})
                self.journal({"ev": "terminal", "step": step,
                              "kind": term})
                if term == "stop":
                    break
        report = {"steps": len(steps), "terminals": verdict_evts,
                  "policy": getattr(policy, "NAME", policy.__class__
                                    .__name__),
                  "wall_s": round(time.time() - self.t0, 1)}
        self.journal({"ev": "run_done", **report})
        return report

    def close(self):
        try:
            self.p.core.close()
        except Exception:
            pass


def verdict_from(report, booted, responded):
    """Honest-verdict composition (vocabulary of the lab)."""
    if not booted:
        return "FAILED"
    if not responded:
        return "INCONCLUSIVE"
    if report.get("gameplay_confirmed"):
        return "GAMEPLAY_CONFIRMED"
    if report.get("state_change_confirmed"):
        return "STATE_CHANGE_CONFIRMED"
    return "BOOTED"


# ---------------- pong policy (round-6 dogfood) ----------------
class PongLoopPolicy:
    """hello_pong: PLAYING -> steer left paddle (UP/DOWN bang-bang on
    the ball row vs paddle row from PNG blobs) -> natural GAME_OVER
    (madiff burst then static screen) -> X (=libretro B) restart ->
    second cycle.  Ground truth: PSX CROSS = libretro B; in-play
    libretro X = pause (never used)."""

    NAME = "pong_loop"

    def __init__(self, cycles=2):
        self.cycles = cycles
        self.cycle = 1
        self.game_overs = 0
        self.static_run = 0
        self._burst = False
        self.last_madiff = None
        self.events = []

    def _ball_and_paddle(self, frame):
        """Brightest-blob ball row + left-paddle row (column ~8-24)."""
        if frame is None:
            return None, None
        g = frame.mean(axis=2)
        ys, xs = np.nonzero(g > 150)
        if len(xs) < 4:
            return None, None
        # left strip = the paddle column band
        left = xs < (g.shape[1] * 0.12)
        prow = float(np.median(ys[left])) if left.any() else None
        # ball = bright pixels OUTSIDE both paddle bands
        band = (xs > g.shape[1] * 0.12) & (xs < g.shape[1] * 0.88)
        brow = float(np.median(ys[band])) if band.any() else None
        return brow, prow

    def act(self, step, obs):
        # game-over detection: madiff burst (scene change) followed by
        # consecutive static frames (game-over screen is static)
        m = obs.madiff
        if m is not None:
            if m > 3.0:
                self._burst = True
                self.static_run = 0
            elif self._burst and m < 0.05:
                self.static_run += 1
            if self.static_run >= 2:
                self.game_overs += 1
                self.events.append({"step": step, "ev": "game_over",
                                    "n": self.game_overs})
                self.static_run = 0
                self._burst = False
                if self.game_overs < self.cycles:
                    self.events.append({"step": step,
                                        "ev": "restart",
                                        "via": "X(libretro B)"})
                    return ({"B"}, 4)      # X = CROSS = libretro B
                return None                # done
        brow, prow = self._ball_and_paddle(obs.frame)
        if brow is None or prow is None:
            return (set(), 6)
        d = brow - prow
        if abs(d) < 10:
            return (set(), 4)
        return ({"UP"} if d < 0 else {"DOWN"}, 4)

    def terminal(self, obs):
        if self.game_overs >= self.cycles:
            return "stop"
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="pong")
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cycles", type=int, default=2)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    tag = time.strftime("%H%M%S")
    jf = open(os.path.join(args.out_dir, f"playloop_{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    if args.game != "pong":
        print("unknown game", args.game)
        return 1
    cue = "/home/z/my-project/emu/games_homebrew/patched/" \
          "hello_pong_lic.cue"
    ws = "/home/z/my-project/emu/ws_pong_pl"
    loop = Playloop(cue, ws, journal=J)
    booted = False
    responded = False
    try:
        b = loop.boot()
        booted = bool(b["booted"])
        responded = b["padbuff_hits"] > 0
        policy = PongLoopPolicy(cycles=args.cycles)
        report = loop.run(policy, args.steps, out_dir=args.out_dir)
    finally:
        loop.close()
    out = {"game": args.game, "booted": booted, "padbuff": responded,
           "report": report, "policy_events": policy.events,
           "verdict": verdict_from(report, booted, responded),
           "started": time.strftime("%FT%TZ", time.gmtime())}
    J({"ev": "RUN_DONE", **out})
    with open(os.path.join(args.out_dir,
                           f"playloop_report_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("verdict:", out["verdict"], "game_overs:",
          policy.game_overs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
