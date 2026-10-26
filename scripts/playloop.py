#!/usr/bin/env python3
"""playloop.py — Ps1ai reusable game-loop driver (Issue #6 round 6;
generalized in round 7 with a per-game registry + CLI).

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
  python3 scripts/playloop.py --policy tetrade --cycles 2 \
      --steps 4000 --out-dir scratch/issue6_round7_tetrade

Round-7 CLI: --cue/--workspace/--policy override the per-game defaults
(--game keeps its role as the legacy selector and default-provider, so
`--game pong` with no other args behaves exactly as before).  Policies
register in POLICIES (name -> factory(loop, cycles=, out_dir=) ->
policy object with act(step, obs) and terminal(obs)); per-game default
cue/workspace live in GAME_DEFAULTS.
"""
import argparse
import json
import os
import sys
import time
from collections import deque

import numpy as np

REPO = "/home/z/my-project/ps1ai"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

PADBUFF_SIG = b"\x00\x41\xff\xff"

EMU_PATCHED = "/home/z/my-project/emu/games_homebrew/patched"
# Per-game boot targets (license-patched LOCAL images only; the lab
# never commits game bytes).  --cue/--workspace override these.
GAME_DEFAULTS = {
    "pong": {"cue": os.path.join(EMU_PATCHED, "hello_pong_lic.cue"),
             "workspace": "/home/z/my-project/emu/ws_pong_pl"},
    "tetrade": {"cue": os.path.join(EMU_PATCHED, "tetrade_lic.cue"),
                "workspace": "/home/z/my-project/emu/ws_tetrade_r7"},
}


def resolve_targets(game, cue=None, workspace=None):
    """Default cue/workspace for a game, overridden by explicit args.
    Unknown games fall back to the pong defaults (explicit args then
    carry the real targets)."""
    d = GAME_DEFAULTS.get(game) or GAME_DEFAULTS["pong"]
    return cue or d["cue"], workspace or d["workspace"]


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
                 padbuff_poll=40, padbuff_step=30, journal=None,
                 var_overrides=None):
        from ps1play.api import PS1Play
        self.cue = cue
        self.workspace = workspace
        self.settle_frames = settle_frames
        self.padbuff_poll = padbuff_poll
        self.padbuff_step = padbuff_step
        self.var_overrides = var_overrides
        self.p = None
        self.journal = journal or (lambda ev: None)
        self.t0 = None

    # ---- lifecycle ----
    def boot(self):
        from ps1play.api import PS1Play
        self.t0 = time.time()
        self.p = PS1Play(self.cue, workspace=self.workspace,
                         var_overrides=self.var_overrides)
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


# ---------------- tetrade policy slot (round 7) ----------------
class TetradeLoopPolicy:
    """RAM-truth iterative Tetris bot for Tetrade (MIT homebrew).

    Source ground truth (MIT Logan-Campbell/Tetrade, src/main.c @ v1.0,
    clone commit 5155664): TetradeGame = matrix int[20][10] @+0 (800 B);
    tetrimino @+800 (Tetrimino: type +0, shape[4][4] +4, x +68, y +72,
    wasHeld +76, rotState +80); nextTCount +892; nextTetriminos[14]
    +896; holdTerimino +2184; score +2276; singleLine +2280; doubleLine
    +2284; tripleLine +2288; tetrade +2292; moveCooldown +2296; setTime
    +2300; level +2304; ghostY +2308; isGameOver +2312; isGamePaused
    +2316.  MATRIX_WIDTH 10 / MATRIX_HEIGHT 20; gravity BASE_DROP_RATE
    30 f/cell at level 0 (SOFT_DROP_RATE 4); lock delay setTime 80.
    Buttons (beetle/libretro names): B=CROSS (rotate CCW / menu
    confirm), A=CIRCLE (rotate CW / refuse CONTINUE?), UP=hard drop
    (+2/cell), DOWN=soft drop (+1/cell), START=title/pause.
    Scoring: single 200*level, double 500*level, triple 700*level,
    tetra 1000*level — note the *level* factor: singles at level 0
    add 0 points (source lines 406-422).

    Anchors: ps1play/profiles/tetrade_lic.json (live-verified by input
    causality, Issue #8) re-checked against live struct gates each
    boot; fallback = in-process behavioral discovery (LEFT-tap whole-
    RAM u32 diff, struct base = x_addr - 868).  Iterative: ONE action
    segment per act() call; stateless re-plan from live RAM whenever
    the segment queue drains (closed loop, never a blind open-chain).
    Cycle flow: title -> START -> menu -> B -> Marathon -> play
    (tetris_ai greedy) -> natural top-out -> CONTINUE? refused with
    A(CIRCLE) -> title -> next cycle -> fresh counters verified in RAM.
    """

    NAME = "tetrade_loop"
    PROFILE = os.path.join(REPO, "ps1play", "profiles", "tetrade_lic.json")
    # round-7 lesson (dbg PNG timeline): the disc EXE needs ~900 frames
    # before the title accepts input (padbuff fills ~480f but presses
    # before ~900f are LOST) — hence the leading settle + the verified
    # calib gate with up to NAV_RETRIES honest retries.
    NAV = (("", 700), ("START", 120), ("", 90), ("", 120), ("B", 20),
           ("", 20), ("", 500))
    NAV_RETRIES = 3
    # offsets relative to the TetradeGame base (source-derived)
    OFF = {"matrix": 0, "tet_type": 800, "tet_shape": 804, "tet_x": 868,
           "tet_y": 872, "tet_held": 876, "tet_rot": 880, "next_count": 892,
           "score": 2276, "single": 2280, "double": 2284, "triple": 2288,
           "tetra": 2292, "level": 2304, "ghost_y": 2308, "over": 2312,
           "paused": 2316}
    TYPES = (1, 2, 3, 4, 5, 6, 7)

    def __init__(self, loop=None, cycles=1, out_dir=None, target_lines=1,
                 max_pieces=120, max_frames=540000):
        from ps1play.agent import tetris_ai      # pure engine import
        self.ai = tetris_ai
        self.loop = loop
        self.cycles = max(1, int(cycles))
        self.out_dir = out_dir
        self.target_lines = int(target_lines)
        self.max_pieces = int(max_pieces)
        self.max_frames = int(max_frames)
        self.state = "nav"
        self.q = deque((({b} if b else set(), f) for b, f in self.NAV))
        self.base = None
        self.anchor_src = None
        self.cycle = 1
        self.pieces = 0
        self.clears = 0
        self.totals = {"pieces": 0, "clears": 0, "plans": 0}
        self.events = []
        self.frames_done = 0
        self.prev_lines = None
        self.prev_score = None
        self.last_type = None
        self.last_shape = None
        self._taps_issued = 0
        self.rot_stuck = 0
        self.wrap = False
        self.over_calls = 0
        self.refused = False
        self.clear_n = 0
        self.nav_retries = 0

    # ---------- plumbing ----------
    def _j(self, ev):
        self.events.append(ev)
        try:
            if self.loop is not None:
                self.loop.journal(ev)
        except Exception:
            pass

    def _mem(self):
        try:
            return self.loop.p.mem
        except Exception:
            return None

    def _read_state(self, g=None):
        m = self._mem()
        if m is None:
            return None
        g = self.base if g is None else g
        if g is None:
            return None
        s = {k: m.u32(g + v) for k, v in self.OFF.items()}
        s["shape"] = [m.u32(g + self.OFF["tet_shape"] + i * 4)
                      for i in range(16)]
        s["matrix"] = [m.u32(g + i * 4) for i in range(200)]
        return s

    @staticmethod
    def _lines_total(s):
        return (s["single"] + 2 * s["double"] + 3 * s["triple"]
                + 4 * s["tetra"])

    @classmethod
    def _gates_ok(cls, s):
        if s is None:
            return False
        return (max(s["matrix"]) <= 8 and
                (s["tet_type"] in cls.TYPES or s["tet_type"] == -1) and
                0 <= s["tet_x"] <= 10 and 0 <= s["tet_y"] <= 20 and
                s["level"] <= 20 and s["score"] < 10 ** 7 and
                s["over"] == 0 and s["single"] < 10 ** 4 and
                s["double"] < 10 ** 4 and s["triple"] < 10 ** 4 and
                s["tetra"] < 10 ** 4)

    def _anchors_from_profile(self):
        try:
            with open(self.PROFILE) as f:
                prof = json.load(f)
            return int(prof["discovered"]["struct_base"]["addr"])
        except Exception:
            return None

    def _discover(self):
        """Behavioral input-causality fallback (the Issue-8 ladder):
        a LEFT tap decrements exactly one u32 near 0..10 — the piece x;
        struct base = x_addr - 868 (source layout)."""
        m = self._mem()
        core = getattr(self.loop.p, "core", None)
        if m is None or core is None:
            return None
        a = bytes(m.snapshot())
        core.run(2, {"LEFT"})
        core.run(12, set())
        b = bytes(m.snapshot())
        a32 = np.frombuffer(a, dtype="<u4")
        b32 = np.frombuffer(b, dtype="<u4")
        drop = a32.astype(np.int64) - b32.astype(np.int64)
        hits = np.flatnonzero((drop >= 1) & (drop <= 2) & (a32 <= 10))
        for tx in hits:
            g = int(tx) * 4 - self.OFF["tet_x"]
            if g < 0x10000:
                continue
            if self._gates_ok(self._read_state(g)):
                return g
        return None

    def _nav_fail(self, reason):
        """Honest nav retry: press timings can land before the disc EXE
        accepts input (~900f; dbg-PNG lesson) — re-navigate with a longer
        settle, up to NAV_RETRIES, then die loudly."""
        if self.nav_retries < self.NAV_RETRIES:
            self.nav_retries += 1
            self.state = "nav"
            self.q = deque((({b} if b else set(), f)
                            for b, f in (("", 600),) + self.NAV))
            self._j({"ev": "nav_retry", "cycle": self.cycle,
                     "attempt": self.nav_retries, "reason": reason})
            return
        self.state = "dead"
        self._j({"ev": "calib_failed", "cycle": self.cycle,
                 "base": self.base, "reason": reason})

    def _calibrate(self, obs=None):
        """Verify anchors + fresh-cycle counters (first entry AND every
        restart — reset_tetris_game zeroes score/lines/level/matrix).

        Stage A locates the struct base (profile anchor, then the
        behavioral input-causality fallback).  Stage B waits for a LIVE
        piece (type 1..7): at the title/menu no piece ever spawns, so a
        timeout means a nav press was lost — honest nav retry.  Stage C
        checks the fresh-cycle counters."""
        if self.base is None:
            g = self._anchors_from_profile()
            if g is not None and self._gates_ok(self._read_state(g)):
                self.base, self.anchor_src = g, "profile"
        if self.base is None:
            g = self._discover()
            if g is not None:
                self.base, self.anchor_src = g, "input_causality"
        m = self._mem()
        if self.base is None or m is None:
            self._nav_fail("no struct base (profile + discovery both "
                           "failed)")
            return
        # stage B: a live piece must appear within ~900 frames
        typ = None
        for _ in range(90):
            typ = m.u32(self.base + self.OFF["tet_type"])
            if typ in self.TYPES:
                break
            try:
                self.loop.p.core.run(10, set())
            except Exception:
                pass
            self.frames_done += 10
        if typ not in self.TYPES:
            self._nav_fail("no live piece at the anchors — a nav press "
                           "was likely lost (title/menu never left)")
            return
        s = self._read_state()
        if s is None or not self._gates_ok(s):
            self._nav_fail("struct gates failed with a live piece")
            return
        fresh = (s["over"] == 0 and s["paused"] == 0 and s["score"] == 0
                 and s["single"] == 0 and s["double"] == 0
                 and s["triple"] == 0 and s["tetra"] == 0
                 and s["level"] == 0 and max(s["matrix"]) <= 8)
        if not fresh:
            self.state = "dead"
            self._j({"ev": "fresh_cycle_failed", "cycle": self.cycle,
                     "score": s["score"], "single": s["single"],
                     "over": s["over"]})
            return
        self.pieces = 0
        self.clears = 0
        self.clear_n = 0
        self.nav_retries = 0
        self.prev_lines = self._lines_total(s)
        self.prev_score = s["score"]
        self.last_type = None
        self.last_shape = None
        self.rot_stuck = 0
        self.wrap = False
        self.refused = False
        self.state = "play"
        self._j({"ev": ("anchors_verified" if self.cycle == 1 and
                        not self.events else "restart_counters_reset"),
                 "cycle": self.cycle, "base": self.base,
                 "anchor_src": self.anchor_src,
                 "struct": {k: s[k] for k in
                            ("tet_type", "tet_x", "tet_y", "score",
                             "single", "level", "over")}})
        if self.out_dir and obs is not None and obs.frame is not None:
            try:
                tag = "gameplay" if self.cycle == 1 else \
                    f"gameplay_c{self.cycle}_reset"
                obs.png(os.path.join(self.out_dir, f"{tag}.png"))
            except Exception:
                pass

    # ---------- per-piece closed loop ----------
    def _play_step(self, obs):
        s = self._read_state()
        if s is None:
            self.state = "dead"
            return (set(), 10)
        lines = self._lines_total(s)
        if self.prev_lines is not None and lines > self.prev_lines:
            d = lines - self.prev_lines
            self.clears += d
            self.totals["clears"] += d
            self.clear_n += 1
            self._j({"ev": "line_clear", "cycle": self.cycle, "delta": d,
                     "lines_total": lines, "score": s["score"],
                     "single": s["single"], "double": s["double"],
                     "triple": s["triple"], "tetra": s["tetra"],
                     "pieces": self.pieces})
            if self.out_dir and obs.frame is not None:
                try:
                    obs.png(os.path.join(
                        self.out_dir,
                        f"clear_c{self.cycle}_{self.clear_n}.png"))
                except Exception:
                    pass
        self.prev_lines = lines
        if self.prev_score is not None and s["score"] != self.prev_score:
            self._j({"ev": "score_delta", "cycle": self.cycle,
                     "from": self.prev_score, "to": s["score"],
                     "lines_total": lines})
        self.prev_score = s["score"]
        if s["over"]:
            self.state = "over"
            self.over_calls = 0
            self._j({"ev": "game_over", "cycle": self.cycle,
                     "score": s["score"], "lines_total": lines,
                     "pieces": self.pieces, "clears": self.clears})
            if self.out_dir and obs.frame is not None:
                try:
                    obs.png(os.path.join(self.out_dir,
                                         f"gameover_c{self.cycle}.png"))
                except Exception:
                    pass
            return (set(), 10)
        if s["paused"]:
            return (set(), 10)
        typ = s["tet_type"]
        if typ not in self.TYPES:
            if self.last_type in self.TYPES:
                self.pieces += 1
                self.totals["pieces"] += 1
            self.last_type = typ if typ == -1 else None
            if (self.pieces >= self.max_pieces and not self.wrap
                    and self.totals["clears"] >= self.target_lines):
                self.wrap = True
                self._j({"ev": "wrap_up", "cycle": self.cycle,
                         "pieces": self.pieces, "clears": self.clears})
            return (set(), 6)
        if typ != self.last_type:
            if self.last_type is not None:
                self.pieces += 1
                self.totals["pieces"] += 1
            self.last_type = typ
            self.rot_stuck = 0
            self.last_shape = None
        if not self.wrap and self.clears >= self.target_lines:
            self.wrap = True
            self._j({"ev": "wrap_up", "cycle": self.cycle,
                     "pieces": self.pieces, "clears": self.clears})
        x = s["tet_x"]
        if not (0 <= x <= 10) or not (0 <= s["tet_y"] <= 20):
            return (set(), 6)          # mid-lock transient read
        if self.wrap:
            self.q.extend([({"UP"}, 1), (set(), 3)])   # drop in place
            return self.q.popleft()
        shape_key = tuple(s["shape"])
        if self.last_shape is not None:
            if shape_key == self.last_shape and self._taps_issued:
                self.rot_stuck += 1
            elif shape_key != self.last_shape:
                self.rot_stuck = 0
        self.last_shape = shape_key
        grid = [s["matrix"][r * 10:(r + 1) * 10] for r in range(20)]
        shape = [s["shape"][r * 4:(r + 1) * 4] for r in range(4)]
        tet_size = 4 if typ <= 2 else 3
        target = self.ai.choose(grid, shape, tet_size,
                                rot_limit=1 if self.rot_stuck >= 2 else 4)
        self.totals["plans"] += 1
        segs = []
        if target is None:                       # board too full
            segs = [({"UP"}, 1), (set(), 3)]
            self._taps_issued = 0
            self._j({"ev": "plan", "cycle": self.cycle, "type": typ,
                     "x": x, "target": None, "lines": lines})
        else:
            n_rot = 0 if self.rot_stuck >= 2 else target["rot"]
            taps = min(2, n_rot)
            for _ in range(taps):
                segs += [({"A"}, 1), (set(), 2)]   # A = CIRCLE = CW
            self._taps_issued = taps
            if n_rot > taps:                       # finish next re-plan
                self._j({"ev": "plan", "cycle": self.cycle, "type": typ,
                         "x": x, "target": target["x"],
                         "rot_pending": n_rot - taps, "lines": lines})
            else:
                for seg in self.ai.plan_segments(x, target["x"],
                                                 target["x"] == x):
                    segs.append((seg["btns"], seg["frames"]))
                self._j({"ev": "plan", "cycle": self.cycle, "type": typ,
                         "x": x, "target": target["x"], "rot": target["rot"],
                         "drop": target["x"] == x, "lines": lines,
                         "want_clear": target["lines"]})
        if not segs:
            segs = [(set(), 6)]
        self.q.extend(segs)
        return self.q.popleft()

    def _over_step(self, obs):
        s = self._read_state()
        if s is None:
            self.state = "dead"
            return (set(), 10)
        if not self.refused:
            self.over_calls += 1
            if s["over"] and self.over_calls >= 15:   # ~150f destruction
                self.refused = True
                self._j({"ev": "refuse_continue", "cycle": self.cycle,
                         "via": "A(CIRCLE)"})
                self.q.extend([({"A"}, 3), (set(), 90)])
                return self.q.popleft()
            return (set(), 10)
        # refused: back at the title — restart the next cycle
        self.cycle += 1
        if self.cycle > self.cycles:
            self.state = "done"
            self._j({"ev": "loop_done", "cycles": self.cycles,
                     "totals": dict(self.totals)})
            return (set(), 10)
        self.state = "nav"
        self.q = deque((({b} if b else set(), f) for b, f in self.NAV))
        self._j({"ev": "restart", "cycle": self.cycle,
                 "via": "START->menu->B->Marathon",
                 "flow_note": "after the CONTINUE? refuse the game lands "
                              "on the MAIN MENU (menuState persists; "
                              "play_regular_mode never resets it to "
                              "PRESS_START) — the NAV START tap confirms "
                              "the selected Marathon option directly"})
        if self.out_dir and obs.frame is not None:
            try:
                obs.png(os.path.join(self.out_dir,
                                     f"restart_menu_c{self.cycle}.png"))
            except Exception:
                pass
        return self.q.popleft()

    # ---------- Playloop contract ----------
    def act(self, step, obs):
        if self.q:
            seg = self.q.popleft()
            self.frames_done += seg[1]
            return seg
        if self.state == "nav":
            self.state = "calib"
            self.frames_done += 10
            return (set(), 10)
        if self.state == "calib":
            self._calibrate(obs)
            self.frames_done += 10
            return (set(), 10)
        if self.state == "play":
            seg = self._play_step(obs)
            self.frames_done += seg[1]
            return seg
        if self.state == "over":
            seg = self._over_step(obs)
            self.frames_done += seg[1]
            return seg
        self.frames_done += 10
        return (set(), 10)

    def terminal(self, obs):
        if self.state in ("done", "dead"):
            return "stop"
        if self.frames_done > self.max_frames:
            self._j({"ev": "budget_stop", "frames_done": self.frames_done})
            return "stop"
        return None

    def verdict_flags(self):
        flags = {}
        if self.anchor_src is not None and self.totals["pieces"] > 0:
            flags["state_change_confirmed"] = True
        if self.totals["clears"] > 0:
            flags["gameplay_confirmed"] = True
            flags["causal"] = {"lines_cleared": self.totals["clears"],
                               "cycles": self.cycles,
                               "anchor_src": self.anchor_src,
                               "base": self.base}
        return flags


def _make_pong(loop, cycles=2, out_dir=None, **kw):
    return PongLoopPolicy(cycles=cycles)


def _make_tetrade(loop, cycles=1, out_dir=None, **kw):
    return TetradeLoopPolicy(loop=loop, cycles=cycles, out_dir=out_dir,
                             **kw)


POLICIES = {"pong": _make_pong, "tetrade": _make_tetrade}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--game", default="pong",
                    help="legacy selector + default cue/workspace "
                         "provider (pong | tetrade)")
    ap.add_argument("--policy", default=None,
                    help="registered policy name (default: --game); "
                         "one of: " + ", ".join(sorted(POLICIES)))
    ap.add_argument("--cue", default=None,
                    help="cue override (default: per-game default)")
    ap.add_argument("--workspace", default=None,
                    help="workspace override (default: per-game default)")
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--target-lines", type=int, default=1,
                    help="tetrade policy: wrap up after this many "
                         "cleared lines per run (then natural top-out)")
    args = ap.parse_args()
    pol_name = args.policy or args.game
    if pol_name not in POLICIES:
        print("unknown policy", pol_name,
              "(registered:", ", ".join(sorted(POLICIES)), ")")
        return 1
    os.makedirs(args.out_dir, exist_ok=True)
    tag = time.strftime("%H%M%S")
    jf = open(os.path.join(args.out_dir, f"playloop_{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    cue, ws = resolve_targets(args.game, args.cue, args.workspace)
    loop = Playloop(cue, ws, journal=J)
    booted = False
    responded = False
    policy = None
    try:
        b = loop.boot()
        booted = bool(b["booted"])
        responded = b["padbuff_hits"] > 0
        policy = POLICIES[pol_name](loop, cycles=args.cycles,
                                    out_dir=args.out_dir,
                                    target_lines=args.target_lines)
        report = loop.run(policy, args.steps, out_dir=args.out_dir)
    finally:
        loop.close()
    out = {"game": args.game, "policy": pol_name, "cue": cue,
           "workspace": ws, "booted": booted, "padbuff": responded,
           "report": report,
           "policy_events": policy.events if policy is not None else [],
           "verdict": verdict_from(report, booted, responded),
           "started": time.strftime("%FT%TZ", time.gmtime())}
    if policy is not None and hasattr(policy, "verdict_flags"):
        flags = policy.verdict_flags()
        out["verdict_flags"] = flags
        out["verdict"] = verdict_from({**report, **flags}, booted,
                                      responded)
    totals = getattr(policy, "totals", None) or {}
    if totals:
        out["totals"] = dict(totals)
    J({"ev": "RUN_DONE", **out})
    with open(os.path.join(args.out_dir,
                           f"playloop_report_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("verdict:", out["verdict"],
          "game_overs:", getattr(policy, "game_overs", None),
          "clears:", totals.get("clears"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
