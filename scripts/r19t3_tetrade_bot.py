#!/usr/bin/env python3
"""r19t3_tetrade_bot.py — Round 19 train T3: a REAL closed-loop Tetris
bot for Tetrade (MIT homebrew), upgraded from the r7 input-causality
bot (scripts/playloop.py TetradeLoopPolicy) to one that plays WELL.

Honest deltas vs r7:
  1. No early wrap-up: r7 defaulted to target_lines=1 and then
     deliberately top-out'd; this bot plays every cycle until a natural
     game over or the wall budget (then savestates for the next run).
  2. BFS-reachable planning: from the LIVE (shape, x, y) the planner
     breadth-first searches (rotation, x, y) space with the game's own
     move semantics (CW rotation without kicks, per-cell slides, fall),
     so targets are always physically reachable (late-game safety the
     r7 drop-from-top search lacked).
  3. 2-ply lookahead: placement value = immediate Dellacherie-style
     score (tetris_ai.evaluate, W_LINES for clears) + GAMMA x the best
     follow-up placement of the NEXT piece read live from the
     nextTetriminos[0] struct (base+896, source layout) — gated, and
     skipped honestly when the read fails sanity.
  4. Landing verification (the verdict evidence): the planned target
     (rotation taps, target x) is journaled per piece; at lock the
     ACTUAL landing is measured two ways — last live (x, shape) minos
     before the lock, and (for no-clear drops) the exact board-matrix
     diff — and compared to the planned columns within +-1.
  5. Multi-run continuation: ONE boot per process (lab rule), but a
     mid-game beetle savestate + a resume_state.json ledger carries a
     run past the wall limit into the next run (--mode resume).

Pinned RAM ground truth (r7, re-verified each boot by struct gates):
  struct base 0x1FECA0; matrix 20x10 @+0; tetrimino @+800 (type +0,
  shape[4][4] +4, x +68, y +72); nextTCount +892, nextTetriminos +896;
  score +2276; single/double/triple/tetra +2280..2292; level +2304;
  isGameOver +2312; isGamePaused +2316.  BASE_DROP_RATE 30 f/cell.
  Controls: A=CIRCLE rotate CW, B=CROSS rotate CCW / menu confirm,
  UP=hard drop (+2/cell), START title/menu.

Nav ladder (r7-proven): title --START--> menu --B(CROSS)--> Marathon.
CONTINUE? after game over is refused with A(CIRCLE) -> menu -> next
cycle (menuState persists; r7 flow note).

Usage:
  python3 scripts/r19t3_tetrade_bot.py --mode new    --wall 280 \
      --out-dir scratch/r19t3_tetrade/run1
  python3 scripts/r19t3_tetrade_bot.py --mode resume --wall 280 \
      --out-dir scratch/r19t3_tetrade/run2
"""
import argparse
import json
import os
import sys
import time
from collections import deque

import numpy as np                                       # noqa: F401

REPO = "/home/z/my-project/ps1ai"
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from scripts.playloop import Playloop                    # noqa: E402
from ps1play.agent import tetris_ai as ai                # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/TETRADE_lic.cue"
WS = "/home/z/my-project/emu/ws_tetrade_r19t3"
STATE_NAME = "r19t3_cont"
RESUME_JSON = os.path.join(REPO, "scratch", "r19t3_tetrade",
                           "resume_state.json")

# r7-pinned + profile-verified struct base (0x1FECA0)
BASE = 0x1FECA0
OFF = {"matrix": 0, "tet_type": 800, "tet_shape": 804, "tet_x": 868,
       "tet_y": 872, "tet_held": 876, "tet_rot": 880,
       "next_count": 892, "next0_type": 896, "next0_shape": 900,
       "hold_type": 2184, "score": 2276, "single": 2280,
       "double": 2284, "triple": 2288, "tetra": 2292,
       "level": 2304, "over": 2312, "paused": 2316}
TYPES = (1, 2, 3, 4, 5, 6, 7)
HEIGHT, WIDTH = 20, 10
GAMMA = 0.35          # next-piece lookahead weight
DEAD_NEXT = -60000    # value of boards that give the next piece no fit

# r7 NAV ladder: title needs ~900f before input; START -> menu ->
# B(CROSS) -> Marathon.
NAV = (("", 700), ("START", 120), ("", 90), ("", 120), ("B", 20),
       ("", 20), ("", 500))


# ------------------------------------------------------------------
# pure helpers (offline-testable)
# ------------------------------------------------------------------
def collides(grid, cells, x, y):
    for r, c in cells:
        cc = x + c
        rr = y + r
        if cc < 0 or cc >= WIDTH or rr >= HEIGHT:
            return True
        if rr >= 0 and grid[rr][cc]:
            return True
    return False


def drop_from(grid, cells, x, y0):
    """Landing y when hard-dropped from (x, y0)."""
    y = y0
    while not collides(grid, cells, x, y + 1):
        y += 1
    return y


def bfs_reach(grid, shape, size, x0, y0):
    """All reachable (rot_taps_from_live, x) with min/max y.

    Moves: LEFT/RIGHT 1 cell, DOWN 1 cell (gravity can always be
    waited for), ROT-CW only when the rotated shape fits in place
    (Tetrade has no wall kicks — r7 lesson).  Returns
    {(rot % 4, x): [min_y, max_y]}."""
    seen = {(0, x0, y0)}
    reach = {}
    frontier = deque([(0, x0, y0, [row[:] for row in shape])])
    while frontier:
        rot, x, y, sh = frontier.popleft()
        cells = ai.minos_of(sh)
        key = (rot % 4, x)
        if key not in reach:
            reach[key] = [y, y]
        else:
            reach[key][0] = min(reach[key][0], y)
            reach[key][1] = max(reach[key][1], y)
        for dx in (-1, 1):
            nx = x + dx
            if not collides(grid, cells, nx, y) and \
                    (rot % 4, nx, y) not in seen:
                seen.add((rot % 4, nx, y))
                frontier.append((rot, nx, y, sh))
        if not collides(grid, cells, x, y + 1) and \
                (rot % 4, x, y + 1) not in seen:
            seen.add((rot % 4, x, y + 1))
            frontier.append((rot, x, y + 1, sh))
        sh2 = ai.rotate_cw(sh, size)
        if not collides(grid, ai.minos_of(sh2), x, y) and \
                ((rot + 1) % 4, x, y) not in seen:
            seen.add(((rot + 1) % 4, x, y))
            frontier.append((rot + 1, x, y, sh2))
    return reach


def canonical_rot(shape, size, rot):
    """Smallest tap-count producing the same shape (O/I symmetry)."""
    sh = ai.shape_after(shape, size, rot)
    for kk in range(rot + 1):
        if ai.shape_after(shape, size, kk) == sh:
            return kk
    return rot


def place_and_clear(grid, cells, x, y):
    g2 = [row[:] for row in grid]
    for r, c in cells:
        g2[y + r][x + c] = 1
    n = ai._clear_lines(g2)
    return g2, n


def board_value(g2, cleared):
    return ai.W_LINES[cleared] + ai.evaluate(g2)["score"]


def plan_2ply(grid, shape, size, x0, y0, next_shape, next_size):
    """Best reachable placement with next-piece lookahead.

    Returns dict(rot, x, y_land, cells, lines, value) or None when
    nothing is reachable/placable (board too full — honest top-out)."""
    reach = bfs_reach(grid, shape, size, x0, y0)
    cands = {}
    for (rot, x), (ymin, ymax) in reach.items():
        sh = ai.shape_after(shape, size, rot)
        cells = ai.minos_of(sh)
        if not cells:
            continue
        rot_c = canonical_rot(shape, size, rot)
        for y in {ymin, ymax}:
            if collides(grid, cells, x, y):
                continue
            yl = drop_from(grid, cells, x, y)
            g2, n = place_and_clear(grid, cells, x, yl)
            v = board_value(g2, n)
            cur = cands.get((rot_c, x))
            if cur is None or v > cur["v1"]:
                cands[(rot_c, x)] = {"rot": rot_c, "x": x, "y_land": yl,
                                     "cells": cells, "lines": n, "v1": v}
    if not cands:
        return None
    best, best_v = None, None
    for cand in cands.values():
        v = cand["v1"]
        if next_shape is not None:
            g2, _ = place_and_clear(grid, cand["cells"], cand["x"],
                                    cand["y_land"])
            nxt = ai.choose(g2, next_shape, next_size)
            v += GAMMA * (DEAD_NEXT if nxt is None else
                          nxt["eval"]["score"] + ai.W_LINES[nxt["lines"]])
        if best_v is None or v > best_v:
            best, best_v = cand, v
    best["value"] = best_v
    return best


def plan_1ply_reachable(grid, shape, size, x0, y0):
    """Fast re-plan: best REACHABLE placement, immediate value only."""
    reach = bfs_reach(grid, shape, size, x0, y0)
    best, best_v = None, None
    for (rot, x), (ymin, ymax) in reach.items():
        sh = ai.shape_after(shape, size, rot)
        cells = ai.minos_of(sh)
        if not cells:
            continue
        rot_c = canonical_rot(shape, size, rot)
        for y in {ymin, ymax}:
            if collides(grid, cells, x, y):
                continue
            yl = drop_from(grid, cells, x, y)
            g2, n = place_and_clear(grid, cells, x, yl)
            v = board_value(g2, n)
            cur_key = (rot_c, x)
            if best_v is None or v > best_v:
                best = {"rot": rot_c, "x": x, "y_land": yl, "cells": cells,
                        "lines": n, "value": v}
                best_v = v
    return best


def shape_cols(cells, x):
    return sorted({x + c for _, c in cells})


def cols_within(actual, planned, tol=1):
    """True when every actual column is within +-tol of the planned
    column set."""
    if not actual or not planned:
        return False
    return all(min(abs(a - p) for p in planned) <= tol for a in actual)


# ------------------------------------------------------------------
# the bot
# ------------------------------------------------------------------
class R19T3Bot:
    NAME = "r19t3_tetrade"

    def __init__(self, loop, out_dir, mode="new", wall_s=280.0,
                 target_clears=24, gif_ring=450, journal=print,
                 max_steps=100000):
        self.loop = loop
        self.out_dir = out_dir
        self.mode = mode
        self.wall_s = float(wall_s)
        self.target_clears = int(target_clears)
        self.max_steps = max_steps
        self.journal = journal
        self.state = "nav"
        self.q = deque((({b} if b else set(), f) for b, f in NAV))
        if mode == "resume":
            # A savestate resumes MID-GAME: never replay the title nav
            # ladder — the START tap would PAUSE the live game and
            # nothing in this bot unpauses it (review fix).  Calibrate
            # directly against the restored RAM instead.
            self.q.clear()
            self.state = "calib"
        self.t_start = time.time()
        self.play_start = None
        self.cycle = 1
        self.pieces = 0
        self.pieces_cycle = 0
        self.clears = 0
        self.clears_cycle = 0
        self.clear_n = 0
        self.score_max = 0
        self.events = []
        self.frames_done = 0
        self.paused_saved = False
        self.status = None
        # per-piece bookkeeping
        self.spawn_grid = None
        self.spawn_shape = None
        self.spawn_type = None
        self.lines_at_spawn = None
        self.target = None
        self.awaiting_lock = False
        self.last_live = None
        self.over_calls = 0
        self.refused = False
        self.nav_retries = 0
        # rotation verification
        self._prev_k = None
        self._last_rot_issued = False
        self.rot_stuck = 0
        # lines bookkeeping
        self._prev_lines = None
        # decision-accuracy ledger
        self.decisions = []
        self._last_y = 0
        # gif capture
        self.ring = deque(maxlen=int(gif_ring))
        self.seg_n = 0
        self.seg_dir = os.path.join(out_dir, "gifsegs")
        os.makedirs(self.seg_dir, exist_ok=True)
        self.cycles_hist = []
        # hard wall stop = play budget + nav/boot margin
        self.wall_hard = self.wall_s + 150

    # ---------- resume ledger ----------
    def seed_from_resume(self, path=RESUME_JSON):
        try:
            with open(path) as f:
                d = json.load(f)
        except Exception:
            return None
        self.cycle = d.get("cycle", 1)
        self.pieces = d.get("pieces", 0)
        self.pieces_cycle = d.get("pieces_cycle", 0)
        self.clears = d.get("clears", 0)
        self.clears_cycle = d.get("clears_cycle", 0)
        self.clear_n = d.get("clear_n", 0)
        self.score_max = d.get("score_max", 0)
        self.seg_n = d.get("seg_n", 0)
        self.cycles_hist = d.get("cycles_hist", [])
        self.decisions = [{"ok": bool(ok)} for ok in
                          d.get("decisions_ok", [])]
        if self.clears >= self.target_clears:
            self._target_hit_logged = True
        self._j({"ev": "resume_seeded", **{k: d.get(k) for k in
                                           ("cycle", "pieces", "clears",
                                            "clears_cycle", "score_max")}})
        return d

    def _write_resume(self, s):
        d = {"cycle": self.cycle, "pieces": self.pieces,
             "pieces_cycle": self.pieces_cycle, "clears": self.clears,
             "clears_cycle": self.clears_cycle, "clear_n": self.clear_n,
             "score_max": self.score_max, "seg_n": self.seg_n,
             "cycles_hist": self.cycles_hist,
             "decisions_ok": [bool(x["ok"]) for x in self.decisions],
             "score": s["score"], "lines_total": self._lines_total(s),
             "level": s["level"], "ts": time.time()}
        try:
            with open(RESUME_JSON, "w") as f:
                json.dump(d, f, indent=1)
        except Exception as e:
            self._j({"ev": "resume_write_failed", "err": repr(e)})
        return d

    # ---------- plumbing ----------
    def _j(self, ev):
        ev = dict(ev, t=round(time.time() - self.t_start, 1))
        self.events.append(ev)
        try:
            self.journal(ev)
        except Exception:
            pass

    def _png(self, name):
        try:
            fr = self.loop.p.core.frame_rgb()
            if fr is None:
                return
            from PIL import Image
            Image.fromarray(fr).save(os.path.join(self.out_dir, name))
        except Exception:
            pass

    def _read_state(self):
        m = self.loop.p.mem
        g = BASE
        s = {k: m.u32(g + v) for k, v in OFF.items()}
        s["shape"] = [m.u32(g + OFF["tet_shape"] + i * 4) for i in range(16)]
        s["matrix"] = [m.u32(g + i * 4) for i in range(200)]
        s["next_shape"] = [m.u32(g + OFF["next0_shape"] + i * 4)
                           for i in range(16)]
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
                (s["tet_type"] in TYPES or s["tet_type"] == -1) and
                0 <= s["tet_x"] <= 10 and 0 <= s["tet_y"] <= 20 and
                s["level"] <= 20 and s["score"] < 10 ** 7 and
                s["over"] == 0 and max(s["single"], s["double"],
                                       s["triple"], s["tetra"]) < 10 ** 4)

    @staticmethod
    def _shape_sane(shape):
        return (len(shape) == 16 and all(v in (0, 1) for v in shape)
                and sum(shape) == 4)

    def _grid(self, s):
        return [s["matrix"][r * WIDTH:(r + 1) * WIDTH] for r in range(HEIGHT)]

    def _next_placement_shape(self, s):
        """(shape4x4, size) for the queued next piece, or (None, 0)."""
        if s["next0_type"] not in TYPES:
            return None, 0
        if not self._shape_sane(s["next_shape"]):
            return None, 0
        size = 4 if s["next0_type"] <= 2 else 3
        sh = [s["next_shape"][r * 4:(r + 1) * 4] for r in range(4)]
        if size == 3 and sum(sh[3]):
            return None, 0          # 3x3 piece must not use row 3
        return sh, size

    # ---------- calibration ----------
    def _calibrate(self, obs):
        m = self.loop.p.mem
        s = self._read_state()
        if s is None or not self._gates_ok(s):
            self._nav_fail("struct gates failed at base")
            return
        typ = s["tet_type"]
        for _ in range(90):
            if typ in TYPES:
                break
            try:
                self.loop.p.core.run(10, set())
                self.frames_done += 10
            except Exception:
                pass
            typ = m.u32(BASE + OFF["tet_type"])
        if typ not in TYPES:
            self._nav_fail("no live piece within ~900f — nav press lost")
            return
        s = self._read_state()
        if not self._gates_ok(s):
            self._nav_fail("struct gates failed with a live piece")
            return
        if self.mode == "new":
            # cycle 1 of a fresh boot must see a pristine struct; from
            # cycle 2 on the NAV START tap re-selects Marathon from the
            # persisted menu (r7 flow note), so the game already played
            # ~750 unattended frames before calibration and the matrix
            # legitimately holds a few landed pieces (run1 lesson).
            first_boot = not self.cycles_hist
            fresh = (s["score"] == 0 and s["single"] == 0
                     and s["double"] == 0 and s["triple"] == 0
                     and s["tetra"] == 0 and s["level"] == 0
                     and s["paused"] == 0 and
                     (max(s["matrix"]) == 0 if first_boot else True))
            if not fresh:
                self.status = "not_fresh_start"
                self.state = "dead"
                self._j({"ev": "fresh_cycle_failed", "cycle": self.cycle,
                         "score": s["score"], "single": s["single"]})
                return
        self.state = "play"
        self.play_start = self.play_start or time.time()
        self.awaiting_lock = False
        self.target = None
        self.last_live = None
        self.rot_stuck = 0
        self._last_y = s["tet_y"]
        self._prev_k = None
        self._prev_lines = self._lines_total(s)
        self._j({"ev": ("anchors_verified" if not self.cycles_hist
                        else "cycle_ready"),
                 "mode": self.mode, "cycle": self.cycle,
                 "fresh_check": self.mode == "new",
                 "struct": {k: s[k] for k in
                            ("tet_type", "tet_x", "tet_y", "score",
                             "single", "level", "over")}})
        tag = "gameplay" if not self.cycles_hist else \
            f"gameplay_c{self.cycle}"
        self._png(tag + ".png")

    def _nav_fail(self, reason):
        if self.nav_retries < 3:
            self.nav_retries += 1
            self.state = "nav"
            self.q = deque((({b} if b else set(), f)
                            for b, f in (("", 600),) + NAV))
            self._j({"ev": "nav_retry", "cycle": self.cycle,
                     "attempt": self.nav_retries, "reason": reason})
            return
        self.status = "nav_failed"
        self.state = "dead"
        self._j({"ev": "nav_failed_final", "reason": reason})

    # ---------- planning ----------
    def _new_piece(self, s):
        """Full 2-ply plan for a freshly spawned piece."""
        self.spawn_grid = self._grid(s)
        self.spawn_shape = [s["shape"][r * 4:(r + 1) * 4] for r in range(4)]
        self.spawn_type = s["tet_type"]
        self.lines_at_spawn = self._lines_total(s)
        self.rot_stuck = 0
        self._prev_k = 0
        self._last_rot_issued = False
        size = 4 if self.spawn_type <= 2 else 3
        nsh, nsize = self._next_placement_shape(s)
        tgt = None
        try:
            tgt = plan_2ply(self.spawn_grid, self.spawn_shape, size,
                            s["tet_x"], s["tet_y"], nsh, nsize)
        except Exception as e:                       # never crash the run
            self._j({"ev": "plan_error", "err": repr(e)})
        if tgt is None:
            self._j({"ev": "plan", "cycle": self.cycle, "piece": self.pieces,
                     "type": self.spawn_type, "target": None,
                     "note": "no reachable placement — hard drop in place",
                     "lookahead": "next" if nsh is not None else "1ply"})
            self.target = None
            self.awaiting_lock = True
            self.q.append((set(), 4))
            return ({"UP"}, 1)
        self.target = tgt
        self.awaiting_lock = False
        self._last_y = s["tet_y"]
        self._j({"ev": "plan", "cycle": self.cycle, "piece": self.pieces,
                 "type": self.spawn_type, "x": s["tet_x"], "y": s["tet_y"],
                 "target": {"rot": tgt["rot"], "x": tgt["x"],
                            "y_land": tgt["y_land"], "lines": tgt["lines"]},
                 "value": round(tgt["value"], 1),
                 "cols": shape_cols(tgt["cells"], tgt["x"]),
                 "lookahead": "next" if nsh is not None else "1ply_only"})
        return (set(), 4)

    def _steer(self, s):
        """One closed-loop steering chunk toward self.target."""
        grid = self._grid(s)
        shape = [s["shape"][r * 4:(r + 1) * 4] for r in range(4)]
        size = 4 if s["tet_type"] <= 2 else 3
        # rotation bookkeeping: which tap-index is the live shape?
        k = None
        for kk in range(4):
            if ai.shape_after(self.spawn_shape, size, kk) == shape:
                k = kk
                break
        if self._last_rot_issued:
            if k is not None and k == self._prev_k:
                self.rot_stuck += 1
            elif k is not None:
                self.rot_stuck = 0
        self._last_rot_issued = False
        if k is not None:
            self._prev_k = k
        if k is None:
            # shape drifted off-model (should not happen) — re-plan
            self.target = plan_1ply_reachable(grid, shape, size,
                                              s["tet_x"], s["tet_y"])
            self.rot_stuck = 0
            self._j({"ev": "replan", "why": "shape_off_model",
                     "piece": self.pieces})
            if self.target is None:
                self.target = None
                self.awaiting_lock = True
                self.q.append((set(), 4))
                return ({"UP"}, 1)
            return (set(), 3)
        tgt = self.target
        rot_need = (tgt["rot"] - k) % 4
        if rot_need and self.rot_stuck < 3:
            self._last_rot_issued = True
            self.q.append((set(), 2))    # release
            return ({"A"}, 1)            # one CW tap per chunk, verified
        if rot_need and self.rot_stuck >= 3:
            # rotation physically blocked (wall) — accept orientation,
            # re-target with the current shape (r7 fallback, upgraded)
            alt = plan_1ply_reachable(grid, shape, size,
                                      s["tet_x"], s["tet_y"])
            self._j({"ev": "replan", "why": "rot_blocked",
                     "piece": self.pieces,
                     "new_x": alt["x"] if alt else None})
            if alt is None:
                self.target = None
                self.awaiting_lock = True
                self.q.append((set(), 4))
                return ({"UP"}, 1)
            self.target = alt
            return (set(), 2)
        # rotation done — reachability re-check for the target x
        reach = bfs_reach(grid, shape, size, s["tet_x"], s["tet_y"])
        if all(rx != tgt["x"] for _, rx in reach):
            alt = plan_1ply_reachable(grid, shape, size,
                                      s["tet_x"], s["tet_y"])
            self._j({"ev": "replan", "why": "target_unreachable",
                     "piece": self.pieces, "old_x": tgt["x"],
                     "new_x": alt["x"] if alt else None})
            if alt is None:
                self.target = None
                self.awaiting_lock = True
                self.q.append((set(), 4))
                return ({"UP"}, 1)
            self.target = alt
            tgt = alt
        # horizontal steering
        dx = tgt["x"] - s["tet_x"]
        if dx:
            btn = "RIGHT" if dx > 0 else "LEFT"
            self.q.append((set(), 2))    # release
            return ({btn}, 2)            # per-cell tap, verify next chunk
        # aligned: hard drop
        self.awaiting_lock = True
        self.q.append((set(), 4))
        return ({"UP"}, 1)

    # ---------- play loop ----------
    def _play_step(self, obs):
        s = self._read_state()
        if s is None:
            self.status = "mem_fail"
            self.state = "dead"
            return (set(), 10)
        # ---- wall budget (honest pause for the next run) ----
        wall = time.time() - self.t_start
        if wall > self.wall_s:
            return self._pause_for_next_run(s, "wall_budget")
        # ---- line clears ----
        lines = self._lines_total(s)
        if self._prev_lines is not None and lines > self._prev_lines:
            d = lines - self._prev_lines
            self.clears += d
            self.clears_cycle += d
            self.clear_n += 1
            self._j({"ev": "line_clear", "cycle": self.cycle,
                     "delta": d, "lines_total": lines,
                     "score": s["score"], "single": s["single"],
                     "double": s["double"], "triple": s["triple"],
                     "tetra": s["tetra"], "pieces": self.pieces,
                     "clears_cycle": self.clears_cycle})
            self._png(f"clear_c{self.cycle}_{self.clear_n}.png")
            self._flush_ring()
        self._prev_lines = lines
        if s["score"] > self.score_max:
            self.score_max = s["score"]
        # ---- game over ----
        if s["over"]:
            self.state = "over"
            self.over_calls = 0
            self._j({"ev": "game_over", "cycle": self.cycle,
                     "score": s["score"], "lines_total": lines,
                     "pieces_cycle": self.pieces_cycle,
                     "clears_cycle": self.clears_cycle})
            self._png(f"gameover_c{self.cycle}.png")
            self.cycles_hist.append({
                "cycle": self.cycle, "score": s["score"],
                "lines": self.clears_cycle,
                "pieces": self.pieces_cycle})
            self._write_resume(s)
            self._prev_lines = None
            return (set(), 10)
        if s["paused"]:
            return (set(), 10)
        # ---- piece lifecycle ----
        typ = s["tet_type"]
        if typ in TYPES:
            # Lock detection (run1 lesson): Tetrade never exposes a
            # tet_type == -1 gap between lock and the next spawn, so the
            # old hook never fired and the bot storm-replanned against a
            # stale spawn_shape while fresh pieces fell unsteered.  A
            # managed live piece is "gone" when its type differs from
            # the managed one, its shape is no longer a rotation of the
            # spawn shape, or its y reset upward (y only grows during a
            # piece's life; hard drops go DOWN, rotation keeps the box).
            if (self.target is not None or self.awaiting_lock) and \
                    self.spawn_shape is not None:
                size = 4 if self.spawn_type <= 2 else 3
                live = [s["shape"][r * 4:(r + 1) * 4] for r in range(4)]
                known = any(ai.shape_after(self.spawn_shape, size, kk)
                            == live for kk in range(4))
                if typ != self.spawn_type or not known or \
                        s["tet_y"] < self._last_y:
                    self._on_lock(s)
                self._last_y = s["tet_y"]
            else:
                self._last_y = s["tet_y"]
        if typ not in TYPES:
            if self.target is not None or self.awaiting_lock:
                self._on_lock(s)
            return (set(), 5)
        if self.target is None and not self.awaiting_lock:
            # spawn (fresh cycle or right after lock)
            self.pieces += 1
            self.pieces_cycle += 1
            self.ring.clear()            # GIF: from this piece onwards
            return self._new_piece(s)
        if self.target is not None:
            self.last_live = {"x": s["tet_x"], "y": s["tet_y"],
                              "shape": [s["shape"][r * 4:(r + 1) * 4]
                                        for r in range(4)]}
            return self._steer(s)
        return (set(), 5)

    def _on_lock(self, s):
        """Landing verification — the verdict evidence of this task."""
        self.awaiting_lock = False
        tgt = self.target
        self.target = None
        if tgt is None or self.last_live is None:
            self._j({"ev": "lock", "cycle": self.cycle,
                     "piece": self.pieces, "verified": False,
                     "note": "no plan or no live read (panic drop)"})
            return
        shape = self.last_live["shape"]
        cells = ai.minos_of(shape)
        actual = shape_cols(cells, self.last_live["x"])
        planned = shape_cols(tgt["cells"], tgt["x"])
        ok = cols_within(actual, planned)
        cleared = (self.lines_at_spawn is not None and
                   self._lines_total(s) > self.lines_at_spawn)
        rec = {"ev": "lock", "cycle": self.cycle, "piece": self.pieces,
               "type": self.spawn_type,
               "plan": {"rot": tgt["rot"], "x": tgt["x"], "cols": planned,
                        "y_land": tgt["y_land"],
                        "lines_expected": tgt["lines"]},
               "land": {"x": self.last_live["x"], "cols": actual},
               "cols_within_1": ok, "cleared": cleared}
        # exact board diff for no-clear drops
        if self.spawn_grid is not None and not cleared:
            grid_now = self._grid(s)
            added = [(r, c) for r in range(HEIGHT) for c in range(WIDTH)
                     if grid_now[r][c] and not self.spawn_grid[r][c]]
            rec["board_diff_cells"] = len(added)
            planned_cells = {(tgt["y_land"] + r, tgt["x"] + c)
                             for r, c in tgt["cells"]}
            rec["exact_cells"] = (set(added) == planned_cells)
        self.decisions.append({"piece": self.pieces, "ok": ok,
                               "exact": rec.get("exact_cells"),
                               "cleared": cleared})
        self._j(rec)
        self.last_live = None
        self.spawn_grid = None
        self.lines_at_spawn = None

    # ---------- pause / resume across runs ----------
    def _pause_for_next_run(self, s, why):
        if self.paused_saved:
            self.state = "paused_done"
            return (set(), 10)
        self.paused_saved = True
        self.status = "paused_" + why
        self._j({"ev": "pause_for_next_run", "why": why,
                 "cycle": self.cycle, "score": s["score"],
                 "lines_total": self._lines_total(s),
                 "clears_cycle": self.clears_cycle})
        self._write_resume(s)
        try:
            res = self.loop.p.save_state(STATE_NAME)
            self._j({"ev": "savestate_saved", **res, "name": STATE_NAME})
        except Exception as e:
            self.status = "save_failed"
            self._j({"ev": "savestate_failed", "err": repr(e)})
        self._png(f"paused_c{self.cycle}.png")
        self.state = "paused_done"
        return (set(), 10)

    # ---------- game over -> refuse CONTINUE -> next cycle ----------
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
        self.cycle += 1
        self.clears_cycle = 0
        self.pieces_cycle = 0
        self.refused = False
        self.nav_retries = 0
        self.state = "nav"
        self.q = deque((({b} if b else set(), f) for b, f in NAV))
        self._j({"ev": "restart", "cycle": self.cycle,
                 "via": "START->menu->B->Marathon"})
        self._png(f"restart_menu_c{self.cycle}.png")
        return self.q.popleft()

    # ---------- gif ring ----------
    def _flush_ring(self):
        if not self.ring:
            return
        self.seg_n += 1
        if self.seg_n > 8:               # cap disk usage; best cycle wins
            self.ring.clear()
            return
        d = os.path.join(self.seg_dir, f"seg{self.seg_n:02d}_c{self.cycle}")
        os.makedirs(d, exist_ok=True)
        from PIL import Image
        for i, fr in enumerate(self.ring):
            if fr is None:
                continue
            try:
                Image.fromarray(fr).save(os.path.join(d, f"f{i:04d}.png"))
            except Exception:
                pass
        self._j({"ev": "gif_segment", "dir": os.path.basename(d),
                 "frames": len(self.ring), "cycle": self.cycle,
                 "clear_n": self.clear_n})
        self.ring.clear()

    # ---------- playloop contract ----------
    def act(self, step, obs):
        if self.play_start is not None:
            self.ring.append(obs.frame)
        if self.q:
            seg = self.q.popleft()
            self.frames_done += seg[1]
            return seg
        if self.state == "nav":
            self.state = "calib"
            return (set(), 10)
        if self.state == "calib":
            self._calibrate(obs)
            return (set(), 10)
        if self.state == "play":
            seg = self._play_step(obs)
            self.frames_done += seg[1]
            return seg
        if self.state == "over":
            seg = self._over_step(obs)
            self.frames_done += seg[1]
            return seg
        return (set(), 10)

    def terminal(self, obs):
        if self.state in ("done", "dead", "paused_done"):
            return "stop"
        if time.time() - self.t_start > self.wall_hard:
            self.status = "wall_hard_stop"
            self._j({"ev": "wall_hard_stop"})
            return "stop"
        if self.clears >= self.target_clears and \
                not getattr(self, "_target_hit_logged", False):
            self._target_hit_logged = True
            self._j({"ev": "target_reached", "clears": self.clears})
        return None

    # ---------- report ----------
    def summary(self):
        n = len(self.decisions)
        ok = sum(1 for d in self.decisions if d["ok"])
        exact = sum(1 for d in self.decisions
                    if d.get("exact") is True)
        return {
            "cycles_played": self.cycle,
            "pieces": self.pieces,
            "clears_total": self.clears,
            "score_max": self.score_max,
            "cycles": self.cycles_hist,
            "decisions": {"n": n, "within_1": ok,
                          "accuracy": round(ok / n, 3) if n else None,
                          "exact_board_diff": exact},
            "status": self.status,
        }


# ------------------------------------------------------------------
# runner
# ------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("new", "resume"), default="new")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wall", type=float, default=280.0,
                    help="wall-clock play budget per run (s)")
    ap.add_argument("--target-clears", type=int, default=24)
    ap.add_argument("--max-steps", type=int, default=60000)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    tag = time.strftime("%H%M%S")
    jf = open(os.path.join(args.out_dir, f"bot_{tag}.jsonl"), "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    loop = Playloop(CUE, WS, journal=J)
    bot = None
    booted = False
    try:
        b = loop.boot()
        booted = bool(b["booted"])
        J({"ev": "booted", **b})
        if args.mode == "resume":
            st = os.path.join(WS, "states", STATE_NAME + ".state")
            if not os.path.exists(st):
                print("RESUME_FAIL: no savestate at", st)
                return 2
            loop.p.load_state(STATE_NAME)
            J({"ev": "savestate_loaded", "name": STATE_NAME})
        bot = R19T3Bot(loop, args.out_dir, mode=args.mode,
                       wall_s=args.wall,
                       target_clears=args.target_clears, journal=J,
                       max_steps=args.max_steps)
        if args.mode == "resume":
            bot.seed_from_resume()
        report = loop.run(bot, args.max_steps, png_every=10 ** 9)
        J({"ev": "run_report", **report})
    finally:
        loop.close()
    out = {"mode": args.mode, "booted": booted,
           "started": time.strftime("%FT%TZ", time.gmtime()),
           "wall_s": round(time.time() - bot.t_start, 1) if bot else None,
           "summary": bot.summary() if bot else None}
    J({"ev": "RUN_DONE", **out})
    with open(os.path.join(args.out_dir, f"bot_report_{tag}.json"),
              "w") as f:
        json.dump(out, f, indent=1, default=str)
    sm = out.get("summary") or {}
    print("RUN_DONE mode=%s status=%s clears=%s pieces=%s score_max=%s "
          "acc=%s" % (args.mode, sm.get("status"), sm.get("clears_total"),
                      sm.get("pieces"), sm.get("score_max"),
                      (sm.get("decisions") or {}).get("accuracy")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
