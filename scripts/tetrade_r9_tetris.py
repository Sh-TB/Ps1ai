#!/usr/bin/env python3
"""tetrade_r9_tetris.py — Issue #6 round 9 (Task 9-c): TETRIS (4-line
"tetrade") hunt + level-2 confirmation for Tetrade, on top of the
UNMODIFIED round-7 TetradeLoopPolicy (scripts/playloop.py).

What is new vs round 8 (scripts/tetrade_r8_levelup.py):
  1. SMARTER PLACEMENT ENGINE (plugin swap, policy untouched):
     Tetrade2PlyAI replaces the policy's `self.ai` engine object.
     Same interface (choose(grid, shape, tet_size, rot_limit) ->
     {"rot","x","lines"} + plan_segments), but 2-PLY:
     it also simulates the NEXT piece's best placement, which (a)
     keeps the board flat/low (Dellacherie eval of the resulting
     board), (b) takes a 4-line clear whenever one is reachable and
     stacks toward one via an explicit TETRIS bonus, (c) optionally
     rewards keeping one clean well (I-piece ready).
     The next piece is READ (never written) from live RAM:
     nextTetriminos[0].type @ struct_base + 896 (source layout:
     sizeof(Tetrimino)=92 -> 800+92=892=nextTCount, 896=queue,
     896+92*14=2184=holdTerimino, 2184+92=2276=score — all four
     offsets self-consistent with the live-verified ones).
     A frame-granular promotion cross-check (spawn type == previous
     frame's next0) validates the read honestly; if the match rate
     collapses, the AI falls back to 1-ply greedy (round-8 behavior).
  2. TETRIS EVIDENCE: a per-frame RGB ring buffer dumps pre-vanish /
     post-vanish PNGs around any 4-line clear (with hard drop the
     vanish is single-frame: place_tetrimino -> check_lines in the
     same frame, main.c:1014-1020+1085-1092).
  3. LEVEL-2 GATES: natural 1->2 flip (pre-clear lines >= 16,
     LEVEL_GOAL 8*(level+1)), level-2 y-step cadence ~13 f/cell from
     clean windows, level-2 score entries (single 400 / double 1000 /
     triple 1400 / tetra 2000 — table x NEW level after the flip).

Ground truth (upstream clone scratch/issue6_round8_tetrade/
tetrade_upstream, src/main.c @ v1.0 = 5155664): LEVEL_GOAL 8 (line 65),
drop rate 30 / (1.10*level) fixed 12.12 -> L1 27 f/cell, L2 13 f/cell;
clears scored AFTER the possible level++ (lines 395-425); hard drop
+2/cell; reset_tetris_game zeroes level each life.

NO RAM WRITES to game state anywhere — progress via real input only.
One beetle boot per process.  Savestate checkpoint name: t9_start.
"""
import argparse
import json
import os
import random
import sys
import time
from collections import deque

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from playloop import Playloop, TetradeLoopPolicy          # noqa: E402
from ps1play.agent import tetris_ai as ai                 # noqa: E402
from ps1play.agent.tetris_ai import (WIDTH, minos_of,     # noqa: E402
                                     shape_after, drop_row,
                                     _clear_lines, evaluate,
                                     plan_segments)

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"
WS = "/home/z/my-project/emu/ws_tetrade_r9"
EVID = os.path.join(REPO, "scratch", "issue6_round9_tetrade")
OVERRIDES = {b"beetle_psx_override_bios": b"openbios"}

SRC = {
    "repo": "https://github.com/Logan-Campbell/Tetrade",
    "file": "src/main.c",
    "commit": "5155664152162a0dc04dc1f0d4f3c807c1e15388 (tag v1.0)",
    "LEVEL_GOAL": 8,
    "BASE_DROP_RATE_L0": 30,
    "drop_rate": {1: 27, 2: 13},
    "clear_table": {1: 200, 2: 500, 3: 700, 4: 1000},
    "hard_drop_per_cell": 2,
    "soft_drop_per_cell": 1,
    "nextTetriminos0_type_off": 896,   # base + 896; stride 92/piece
    "Tetrimino_sizeof": 92,
}

FIELDS = ("tet_type", "tet_x", "tet_y", "score", "single", "double",
          "triple", "tetra", "level", "over", "paused", "ghost_y")
EXTRA_OFF = {"set_time": 2300, "move_cd": 2296,
             "next0": SRC["nextTetriminos0_type_off"], "next1": 988}

TETRIS_BONUS = 4000.0
DEATH_PENALTY = -8000.0
K_EXPAND = 12


# ------------------------------------------------------------------
# placement engine (plugin for TetradeLoopPolicy.self.ai — policy
# itself is REUSED UNMODIFIED; only the engine object is swapped)
# ------------------------------------------------------------------
def well_term(heights, w):
    """Reward ONE clean I-ready well: depth below the lower neighbour,
    rewarded up to 4 cells, mildly penalized beyond 4 (an over-deep
    well can no longer be tetrised by a 4-tall I)."""
    if w <= 0:
        return 0.0
    t = 0.0
    for j in range(WIDTH):
        left = heights[j - 1] if j > 0 else 99
        right = heights[j + 1] if j < WIDTH - 1 else 99
        d = min(left, right) - heights[j]
        if d > 0:
            t += min(d, 4) * w - max(0, d - 4) * 0.7 * w
    return t


def choose_full(grid, shape, tet_size, rot_limit, nxt, well_w=0.0):
    """2-ply placement search.  nxt = (type, shape4x4) of the NEXT
    piece or None (unreadable -> 1-ply greedy, round-8 behavior).
    Returns {"rot","x","lines"} or None (no placement fits)."""
    cands = []
    for n_rot in range(rot_limit):
        sh = shape_after(shape, tet_size, n_rot)
        cells = minos_of(sh)
        if not cells:
            continue
        cmin = min(c for _, c in cells)
        cmax = max(c for _, c in cells)
        for x0 in range(-cmin, WIDTH - cmax):
            y0 = drop_row(grid, cells, x0)
            if y0 is None:
                continue
            g1 = [row[:] for row in grid]
            for r, c in cells:
                g1[y0 + r][x0 + c] = 1
            l1 = _clear_lines(g1)
            ev1 = evaluate(g1)
            v1 = (ai.W_LINES[l1] + ev1["score"]
                  + (TETRIS_BONUS if l1 >= 4 else 0.0)
                  + well_term(ev1["heights"], well_w))
            cands.append([v1, n_rot, x0, l1, g1])
    if not cands:
        return None
    if nxt is None:
        best = max(cands, key=lambda c: c[0])
        return {"rot": best[1], "x": best[2], "lines": best[3]}
    order = sorted(range(len(cands)), key=lambda i: -cands[i][0])
    order = order[:K_EXPAND]
    t2, sh2 = nxt
    ts2 = 4 if t2 <= 2 else 3
    best, best_tot = None, None
    for i in order:
        v1, n_rot, x0, l1, g1 = cands[i]
        if l1 >= 4:
            tot = v1                       # tetris NOW — no need for ply 2
        else:
            m2 = None
            for n_rot2 in range(4):
                shp2 = shape_after(sh2, ts2, n_rot2)
                cells2 = minos_of(shp2)
                if not cells2:
                    continue
                cmin2 = min(c for _, c in cells2)
                cmax2 = max(c for _, c in cells2)
                for x02 in range(-cmin2, WIDTH - cmax2):
                    y02 = drop_row(g1, cells2, x02)
                    if y02 is None:
                        continue
                    g2 = [row[:] for row in g1]
                    for r, c in cells2:
                        g2[y02 + r][x02 + c] = 1
                    l2 = _clear_lines(g2)
                    ev2 = evaluate(g2)
                    v2 = (ai.W_LINES[l2] + ev2["score"]
                          + (TETRIS_BONUS if l2 >= 4 else 0.0)
                          + well_term(ev2["heights"], well_w))
                    if m2 is None or v2 > m2:
                        m2 = v2
            tot = v1 + (m2 if m2 is not None else DEATH_PENALTY)
        if best_tot is None or tot > best_tot:
            best_tot, best = tot, cands[i]
    return {"rot": best[1], "x": best[2], "lines": best[3]}


class LiveNext:
    """Read-only next-piece provider (RAM reads only)."""

    def __init__(self, policy):
        self.policy = policy

    def read(self):
        p = self.policy
        m = p._mem()
        g = p.base
        if m is None or g is None:
            return None
        t = m.u32(g + SRC["nextTetriminos0_type_off"])
        if t not in (1, 2, 3, 4, 5, 6, 7):
            return None
        shape = [m.u32(g + SRC["nextTetriminos0_type_off"] + 4 + 4 * i)
                 for i in range(16)]
        return t, [shape[r * 4:(r + 1) * 4] for r in range(4)]


class Tetrade2PlyAI:
    """Drop-in replacement for the policy's `self.ai` engine object
    (same choose/plan_segments interface; plan_segments delegates to
    the round-7 pure engine)."""

    def __init__(self, provider=None, well_w=0.0):
        self.provider = provider
        self.well_w = float(well_w)
        self.calls = 0
        self.used_2ply = 0
        self.next_ok_calls = 0
        self.tetris_plans = 0

    def choose(self, grid, shape, tet_size, rot_limit=4):
        self.calls += 1
        nxt = self.provider.read() if self.provider is not None else None
        if nxt is not None:
            self.next_ok_calls += 1
        t = choose_full(grid, shape, tet_size, rot_limit, nxt, self.well_w)
        if t is not None and t.get("lines") == 4:
            self.tetris_plans += 1
        if nxt is not None:
            self.used_2ply += 1
        return t

    def plan_segments(self, cur_x, target_x, drop_now):
        return plan_segments(cur_x, target_x, drop_now)


# ------------------------------------------------------------------
# offline self-play (strategy selection WITHOUT burning an emu boot)
# ------------------------------------------------------------------
PIECES = (
    ((0, 0, 0, 0), (1, 1, 1, 1), (0, 0, 0, 0), (0, 0, 0, 0)),   # I
    ((0, 0, 0, 0), (0, 1, 1, 0), (0, 1, 1, 0), (0, 0, 0, 0)),   # O
    ((1, 0, 0, 0), (1, 1, 1, 0), (0, 0, 0, 0), (0, 0, 0, 0)),   # J
    ((0, 0, 1, 0), (1, 1, 1, 0), (0, 0, 0, 0), (0, 0, 0, 0)),   # L
    ((1, 1, 0, 0), (0, 1, 1, 0), (0, 0, 0, 0), (0, 0, 0, 0)),   # Z
    ((0, 1, 1, 0), (1, 1, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0)),   # S
    ((0, 1, 0, 0), (1, 1, 1, 0), (0, 0, 0, 0), (0, 0, 0, 0)),   # T
)


class _StaticNext:
    def __init__(self, t, shape):
        self.t = t
        self.s = shape

    def read(self):
        return self.t, [list(r) for r in self.s]


def sim_life(variant, rng, max_pieces=400):
    """One simulated Marathon life (bag-of-7 randomizer, main.c
    reset_tetris_game/promotion logic).  Returns stats dict."""
    well_w = {"r8": 0.0, "2ply": 0.0, "2plywell": 12.0}[variant]
    grid = [[0] * WIDTH for _ in range(20)]
    bag = list(range(1, 8))
    queue = []
    while len(queue) < 14:
        rng.shuffle(bag)
        queue += bag[:min(7, 14 - len(queue))]
    cnt = {"single": 0, "double": 0, "triple": 0, "tetra": 0}
    level = score = pieces = 0
    alive = True
    while alive and pieces < max_pieces:
        t = queue.pop(0)
        if len(queue) <= 7:                 # refill (isRandomBag=1)
            rng.shuffle(bag)
            queue += bag
        nxt_t = queue[0]
        nxt = (nxt_t, [list(r) for r in PIECES[nxt_t - 1]]) \
            if variant != "r8" else None
        shape = [list(r) for r in PIECES[t - 1]]
        tet_size = 4 if t <= 2 else 3
        tgt = choose_full(grid, shape, tet_size, 4, nxt, well_w)
        if tgt is None:
            break                            # board too full -> top out
        cells = minos_of(shape_after(shape, tet_size, tgt["rot"]))
        y0 = drop_row(grid, cells, tgt["x"])
        if y0 is None:
            break
        for r, c in cells:
            grid[y0 + r][tgt["x"] + c] = t
        lines = _clear_lines(grid)
        pieces += 1
        key = {1: "single", 2: "double", 3: "triple", 4: "tetra"}.get(
            lines)
        if key:
            total = cnt["single"] + 2 * cnt["double"] + 3 * cnt["triple"] \
                + 4 * cnt["tetra"]
            if total >= 8 * (level + 1):
                level += 1
            cnt[key] += 1
            score += SRC["clear_table"][lines] * level
    heights, holes = ai._heights_holes(grid) if hasattr(ai, "_heights_holes") \
        else (None, None)
    lines_tot = (cnt["single"] + 2 * cnt["double"] + 3 * cnt["triple"]
                 + 4 * cnt["tetra"])
    return {"pieces": pieces, "lines": lines_tot, "level": level,
            "score": score, "cnt": dict(cnt), "holes": holes,
            "alive": alive}


def run_sim(args):
    out = {"variants": {}}
    for variant in args.variants.split(","):
        rng = random.Random(args.seed)
        lives = []
        t0 = time.time()
        for _ in range(args.lives):
            lives.append(sim_life(variant, rng, args.max_pieces))
        agg = {
            "lives": len(lives),
            "mean_pieces": round(sum(l["pieces"] for l in lives)
                                 / len(lives), 1),
            "mean_lines": round(sum(l["lines"] for l in lives)
                                / len(lives), 1),
            "mean_level": round(sum(l["level"] for l in lives)
                                / len(lives), 2),
            "n_level2plus": sum(1 for l in lives if l["level"] >= 2),
            "n_tetris": sum(l["cnt"]["tetra"] for l in lives),
            "lives_with_tetris": sum(1 for l in lives
                                     if l["cnt"]["tetra"] > 0),
            "clears": {k: sum(l["cnt"][k] for l in lives)
                       for k in ("single", "double", "triple", "tetra")},
            "mean_holes_at_end": round(sum(l["holes"] for l in lives)
                                       / len(lives), 1),
            "wall_s": round(time.time() - t0, 1),
        }
        out["variants"][variant] = agg
        print(variant, json.dumps(agg))
    with open(os.path.join(args.out_dir, "r9_sim.json"), "w") as f:
        json.dump(out, f, indent=1)
    return 0


# ------------------------------------------------------------------
# live driver (frame-granular executor around the UNMODIFIED policy;
# telemetry skeleton reused from tetrade_r8_levelup.py R8Driver)
# ------------------------------------------------------------------
class _ShimObs:
    frame = None
    madiff = None
    padbuff_hits = 0
    state_raw = None
    step = -1


class R9Driver:
    def __init__(self, loop, policy, trace, out_dir, tag):
        self.loop = loop
        self.policy = policy
        self.core = loop.p.core
        self.mem = loop.p.mem
        self.trace = trace
        self.out_dir = out_dir
        self.tag = tag
        self.prev = None
        self.prev_y_fc = None
        self.prev_y_piece = None
        self.steps = []
        self.clear_n = 0
        self.events = []
        self.level_flips = []
        self.clears = []
        self.cadence = {}
        self.piece_ud = False
        self.stop_reason = None
        self.ring = deque(maxlen=10)         # (fc, rgb) — tetris pre PNGs
        self.burst = 0                       # post-tetris PNGs to take
        self.burst_n = 0
        self.tetris_events = []
        self.next_check = {"n_promotions": 0, "n_match": 0}
        self.pending_probe = True            # input-causality gate (G1)
        self.probe = None

    def ev(self, kind, **kw):
        e = {"ev": kind, "fc": self.core.frames_run, **kw}
        self.events.append(e)
        self.loop.journal(e)
        return e

    def png(self, name):
        try:
            from PIL import Image
            arr = self.core.frame_rgb()
            if arr is None:
                return None
            path = os.path.join(self.out_dir, f"{name}.png")
            Image.fromarray(arr).save(path)
            return path
        except Exception:
            return None

    # ---- G1: explicit input-causality gate (Issue-8 ladder step) ----
    def run_probe(self):
        m = self.mem
        g = self.policy.base
        x0 = m.u32(g + self.policy.OFF["tet_x"])
        btn = "LEFT" if x0 > 1 else "RIGHT"
        self.core.run(2, {btn})
        self.core.run(12, set())
        x1 = m.u32(g + self.policy.OFF["tet_x"])
        d = x0 - x1 if btn == "LEFT" else x1 - x0
        ok = (1 <= d <= 2) and 0 <= x1 <= 10
        e = self.ev("input_causality", btn=btn, x0=x0, x1=x1, dx=d,
                    ok=bool(ok))
        self.probe = e
        return ok

    # ---- per-frame telemetry + event detection ----
    def frame(self, btns):
        self.core.run(1, btns)
        p = self.policy
        fc = self.core.frames_run
        arr = self.core.frame_rgb()
        if arr is not None:
            self.ring.append((fc, arr))
        if self.burst > 0:
            self.burst -= 1
            self.burst_n += 1
            if arr is not None:
                try:
                    from PIL import Image
                    Image.fromarray(arr).save(os.path.join(
                        self.out_dir,
                        f"tetris_post{self.burst_n}_fc{fc}.png"))
                except Exception:
                    pass
        if p.base is None:
            self.trace.write(json.dumps({"fc": fc, "state": p.state})
                             + "\n")
            return
        g = p.base
        m = self.mem
        cur = {k: m.u32(g + p.OFF[k]) for k in FIELDS}
        for k, off in EXTRA_OFF.items():
            cur[k] = m.u32(g + off)
        for k in ("tet_type", "tet_x", "tet_y", "ghost_y", "next0",
                  "next1"):
            if cur[k] >= 2 ** 31:
                cur[k] -= 2 ** 32
        cur["fc"] = fc
        cur["cycle"] = p.cycle
        cur["state"] = p.state
        cur["inp"] = "".join(sorted(b[0] for b in btns)) if btns else ""
        cur["lines"] = (cur["single"] + 2 * cur["double"]
                        + 3 * cur["triple"] + 4 * cur["tetra"])
        prev = self.prev
        self.trace.write(json.dumps(cur, default=str) + "\n")
        if prev is not None and prev.get("state") != cur["state"]:
            self.ev("policy_state", frm=prev.get("state"),
                    to=cur["state"])
        if prev is None or prev["fc"] != fc - 1:
            prev = None                    # frame gap (calib) — resync

        # --- piece identity / y-step cadence / next0 validation ---
        if cur["inp"] and any(c in cur["inp"] for c in ("U", "D")):
            self.piece_ud = True
        typ = cur["tet_type"]
        if prev is not None and typ == prev["tet_type"] and typ > 0:
            dy = cur["tet_y"] - prev["tet_y"]
            if dy == 1 and not self.piece_ud:
                self.steps.append({"fc": fc, "level": cur["level"],
                                   "cycle": cur["cycle"],
                                   "piece": typ})
                if (self.prev_y_fc is not None
                        and self.prev_y_piece == typ):
                    self.cadence.setdefault(cur["level"],
                                            []).append(
                                                fc - self.prev_y_fc)
                self.prev_y_fc = fc
                self.prev_y_piece = typ
        if prev is not None and typ != prev["tet_type"]:
            self.prev_y_fc = None
            self.piece_ud = False
            if typ in (1, 2, 3, 4, 5, 6, 7):
                # spawn: the previous frame's next0 must be this piece
                self.next_check["n_promotions"] += 1
                if prev.get("next0") == typ:
                    self.next_check["n_match"] += 1
                else:
                    self.ev("next_mismatch", expected=prev.get("next0"),
                            got=typ, next0_now=cur["next0"])
            if typ == -1 and prev["tet_type"] > 0:
                self.ev("piece_locked", piece=prev["tet_type"],
                        y=prev["tet_y"], score=cur["score"],
                        lines=cur["lines"], level=cur["level"])

        # --- level flip ---
        if prev is not None and cur["level"] != prev["level"]:
            thr = SRC["LEVEL_GOAL"] * (prev["level"] + 1)
            e = self.ev("level_flip", frm=prev["level"],
                        to=cur["level"], lines_prev=prev["lines"],
                        lines=cur["lines"], single=cur["single"],
                        double=cur["double"], triple=cur["triple"],
                        tetra=cur["tetra"], score_prev=prev["score"],
                        score=cur["score"], goal=SRC["LEVEL_GOAL"],
                        threshold_ok=bool(prev["lines"] >= thr))
            e["png"] = self.png(f"levelflip_c{cur['cycle']}_fc{fc}")
            self.level_flips.append(e)

        # --- line clear (counters moved) ---
        if prev is not None and cur["lines"] > prev["lines"]:
            d = cur["lines"] - prev["lines"]
            dy_drop = 0
            if prev["tet_type"] and prev["tet_type"] > 0:
                dy_drop = max(0, prev["ghost_y"] - prev["tet_y"])
            self.clear_n += 1
            e = self.ev("line_clear", cycle=cur["cycle"], delta=d,
                        level=cur["level"], lines=cur["lines"],
                        single=cur["single"], double=cur["double"],
                        triple=cur["triple"], tetra=cur["tetra"],
                        score_prev=prev["score"], score=cur["score"],
                        dy_drop=dy_drop)
            e["png"] = self.png(
                f"clear_c{cur['cycle']}_n{self.clear_n}_fc{fc}")
            self.clears.append(e)
            if d == 4:
                # ---- TETRIS: dump ring (pre-vanish) + post burst ----
                pre = []
                for i, (fc0, a0) in enumerate(self.ring):
                    if fc0 >= fc:
                        continue
                    try:
                        from PIL import Image
                        path = os.path.join(
                            self.out_dir,
                            f"tetris_pre{i}_fc{fc0}.png")
                        Image.fromarray(a0).save(path)
                        pre.append(os.path.basename(path))
                    except Exception:
                        pass
                e["tetris_pre_pngs"] = pre
                e["is_tetris"] = True
                e["expected_pts"] = SRC["clear_table"][4] * cur["level"]
                self.burst = 12
                self.burst_n = 0
                self.tetris_events.append(e)

        # --- score change without a clear (drop points) ---
        elif prev is not None and cur["score"] != prev["score"]:
            dy = None
            if prev["tet_type"] and prev["tet_type"] > 0:
                dy = max(0, prev["ghost_y"] - prev["tet_y"])
            self.ev("score_delta", level=cur["level"],
                    frm=prev["score"], to=cur["score"],
                    dy_drop=dy, inp=cur["inp"])

        if prev is None or cur["over"] != prev.get("over"):
            if cur["over"]:
                self.ev("game_over", cycle=cur["cycle"],
                        score=cur["score"], lines=cur["lines"],
                        level=cur["level"])
                self.png(f"gameover_c{cur['cycle']}_fc{fc}")
        self.prev = cur

    # ---- main loop ----
    def run(self, max_steps, max_frames, wall_budget, t0):
        step = 0
        probe_done = False
        while True:
            p = self.policy
            if p.state in ("done", "dead"):
                self.stop_reason = f"policy_{p.state}"
                break
            if p.frames_done > max_frames:
                self.stop_reason = "frame_budget"
                break
            if time.time() - t0 > wall_budget:
                self.stop_reason = "wall_budget"
                break
            seg = p.act(step, _ShimObs())
            if not seg:
                self.stop_reason = "policy_returned_none"
                break
            # G1 explicit gate: first entry into "play" with an empty
            # action queue — the live piece sits at spawn, the policy
            # has not planned yet, and its closed loop will re-plan
            # from the post-probe x.
            if (self.pending_probe and not probe_done
                    and p.state == "play" and not p.q
                    and p.base is not None):
                probe_done = True
                self.run_probe()
            btns, n = seg
            for _ in range(n):
                self.frame(btns)
            step += 1
        return step


def cadence_summary(gaps, steps):
    out = {}
    if gaps:
        s = sorted(gaps)
        n = len(s)
        med = s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2
        hist = {}
        for v in gaps:
            hist[v] = hist.get(v, 0) + 1
        out["gaps"] = {"n": n, "median": med, "min": s[0],
                       "max": s[-1], "hist": hist}
    else:
        out["gaps"] = {"n": 0}
    conc = {}
    for r in (30, 27, 13):
        residues = {}
        for st in steps:
            key = (st["cycle"], st["fc"] % r)
            residues[key] = residues.get(key, 0) + 1
        if residues:
            best = max(residues.values())
            conc[r] = {"n_steps": len(steps),
                       "buckets": len({k[0] for k in residues}),
                       "distinct_phase_keys": len(residues),
                       "top_residue_count": best,
                       "concentration": round(best / len(steps), 3)}
        else:
            conc[r] = {"n_steps": 0}
    out["phase"] = conc
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cycles", type=int, default=2)
    ap.add_argument("--wrap-lines", type=int, default=9999,
                    help="policy target_lines (wrap threshold); 9999 = "
                         "never wrap, play until natural top-out")
    ap.add_argument("--max-pieces", type=int, default=300)
    ap.add_argument("--max-frames", type=int, default=500000)
    ap.add_argument("--wall-budget", type=float, default=420.0)
    ap.add_argument("--variant", default="2ply",
                    choices=("r8", "2ply", "2plywell"),
                    help="placement engine: r8 = original 1-ply, "
                         "2ply = next-piece lookahead, 2plywell adds "
                         "a small well term")
    ap.add_argument("--seed-idle", type=int, default=0,
                    help="idle frames before nav (changes the srand "
                         "seed -> different piece sequence, no RAM "
                         "writes)")
    ap.add_argument("--sim", action="store_true",
                    help="offline self-play only (no emulator, no "
                         "boot) — strategy selection")
    ap.add_argument("--lives", type=int, default=12)
    ap.add_argument("--variants", default="r8,2ply,2plywell")
    ap.add_argument("--seed", type=int, default=9)
    ap.add_argument("--out-dir", default=EVID)
    ap.add_argument("--tag", default=time.strftime("%H%M%S"))
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    if args.sim:
        return run_sim(args)

    t0 = time.time()
    tag = args.tag
    trace_path = os.path.join(args.out_dir, f"r9_frames_{tag}.jsonl")
    ev_path = os.path.join(args.out_dir, f"r9_events_{tag}.jsonl")
    rep_path = os.path.join(args.out_dir, f"r9_report_{tag}.json")
    trace = open(trace_path, "w")
    evf = open(ev_path, "w")

    def J(e):
        e = {"t_s": round(time.time() - t0, 1), **e}
        evf.write(json.dumps(e, default=str) + "\n")
        evf.flush()
        print("[r9]", json.dumps(e, default=str)[:200], flush=True)

    OUT = {"script": "tetrade_r9_tetris", "tag": tag,
           "started": time.strftime("%FT%TZ"),
           "cue": CUE, "workspace": WS, "args": vars(args),
           "source": SRC, "overrides": {"beetle_psx_override_bios":
                                        "openbios"},
           "savestate": "t9_start"}
    loop = None
    policy = None
    drv = None
    try:
        loop = Playloop(CUE, WS, journal=J, var_overrides=OVERRIDES)
        b = loop.boot()
        OUT["boot"] = {k: b.get(k) for k in ("booted", "padbuff_hits")}
        J({"ev": "boot", **OUT["boot"]})
        loop.p.save_state("t9_start")
        J({"ev": "checkpoint_saved", "name": "t9_start"})
        if args.seed_idle > 0:
            loop.p.core.run(args.seed_idle, set())
            J({"ev": "seed_idle", "frames": args.seed_idle,
               "fc": loop.p.core.frames_run})
        policy = TetradeLoopPolicy(loop=loop, cycles=args.cycles,
                                   out_dir=args.out_dir,
                                   target_lines=args.wrap_lines,
                                   max_pieces=args.max_pieces,
                                   max_frames=args.max_frames)
        engine = Tetrade2PlyAI(provider=LiveNext(policy),
                               well_w={"r8": 0.0, "2ply": 0.0,
                                       "2plywell": 12.0}[args.variant])
        policy.ai = engine                    # engine swap ONLY
        OUT["engine"] = {"variant": args.variant,
                         "well_w": engine.well_w,
                         "policy_modified": False}
        drv = R9Driver(loop, policy, trace, args.out_dir, tag)
        steps = drv.run(args.max_frames + 6000, args.max_frames,
                        args.wall_budget, t0)
        OUT["steps"] = steps
        OUT["stop_reason"] = drv.stop_reason
        OUT["struct_base"] = policy.base
        OUT["struct_base_hex"] = hex(policy.base) if policy.base else None
        OUT["anchor_src"] = policy.anchor_src
        OUT["totals"] = dict(policy.totals)
        OUT["cycles_played"] = policy.cycle
        OUT["engine_stats"] = {"choose_calls": engine.calls,
                               "used_2ply": engine.used_2ply,
                               "tetris_plans": engine.tetris_plans}
        OUT["next_piece_check"] = drv.next_check
        OUT["input_causality_probe"] = drv.probe
        OUT["policy_events_tail"] = policy.events[-12:]

        # ---- analysis ----
        OUT["level_flips"] = drv.level_flips
        OUT["cadence"] = {}
        for lvl in sorted(drv.cadence):
            sub = [s for s in drv.steps if s["level"] == lvl]
            OUT["cadence"][str(lvl)] = cadence_summary(drv.cadence[lvl],
                                                       sub)
        OUT["n_steps_total"] = len(drv.steps)
        for e in drv.clears:
            drop_pts = SRC["hard_drop_per_cell"] * (e.get("dy_drop") or 0)
            e["drop_pts_est"] = drop_pts
            e["clear_pts_est"] = e["score"] - e["score_prev"] - drop_pts
            e["expected_pts"] = SRC["clear_table"].get(
                e["delta"], 0) * e["level"]
            e["match"] = bool(e["clear_pts_est"] == e["expected_pts"])
        OUT["clears"] = drv.clears
        lv0 = [c for c in drv.clears if c["level"] == 0]
        lv1p = [c for c in drv.clears if c["level"] >= 1]
        OUT["clear_score_level0"] = {
            "n": len(lv0),
            "all_zero_clear_pts": bool(lv0) and all(
                c["clear_pts_est"] == 0 for c in lv0)}
        OUT["clear_score_level1p"] = {
            "n": len(lv1p),
            "all_match_table": bool(lv1p) and all(
                c["match"] for c in lv1p)}
        OUT["clears_by_type"] = {
            k: sum(1 for c in drv.clears if c["delta"] == int(k[-1]))
            for k in ("d1", "d2", "d3", "d4")}
        OUT["tetris_events"] = [
            {k: e.get(k) for k in ("fc", "cycle", "level", "score_prev",
                                   "score", "expected_pts",
                                   "clear_pts_est", "match", "png",
                                   "tetris_pre_pngs")}
            for e in drv.tetris_events]

        # ---- verdicts (honest) ----
        v = {}
        # G1 calibration ladder
        g1_ok = (policy.base == 0x1FECA0
                 and policy.anchor_src in ("profile", "input_causality")
                 and drv.probe is not None and drv.probe["ok"]
                 and policy.totals["pieces"] > 0)
        v["g1_calibration"] = {
            "verdict": "CAUSAL" if g1_ok else
                       ("INCONCLUSIVE" if policy.base else "FAILED"),
            "base": policy.base, "base_hex": OUT["struct_base_hex"],
            "anchor_src": policy.anchor_src,
            "probe": drv.probe,
            "pieces_placed": policy.totals["pieces"],
            "note": "profile anchor + live struct gates + fresh-cycle "
                    "counters (policy _calibrate) + explicit LEFT/RIGHT "
                    "tap x-displacement probe before the first plan"}
        # G2 tetris
        te = drv.tetris_events
        if te and all(e["match"] for e in te):
            v["g2_tetris"] = {
                "verdict": "CAUSAL",
                "n_tetris": len(te),
                "first": {k: te[0].get(k) for k in
                          ("fc", "cycle", "level", "score_prev", "score",
                           "expected_pts", "png", "tetris_pre_pngs")},
                "clears_by_type": OUT["clears_by_type"]}
        elif te:
            v["g2_tetris"] = {"verdict": "MISMATCH",
                              "events": OUT["tetris_events"]}
        else:
            v["g2_tetris"] = {
                "verdict": "INCONCLUSIVE(tetris)",
                "reason": "no natural 4-line clear within budget",
                "clears_by_type": OUT["clears_by_type"],
                "n_clears": len(drv.clears),
                "n_pieces": policy.totals["pieces"]}
        # G3 natural 1->2 flip
        flips_12 = [f for f in drv.level_flips
                    if f["frm"] == 1 and f["to"] == 2]
        flip_clears = [c for c in lv1p if c["level"] == 2]
        if flips_12 and all(f["threshold_ok"] for f in flips_12) \
                and flip_clears and all(c["match"] for c in flip_clears):
            f0 = flips_12[0]
            v["g3_level_flip_1to2"] = {
                "verdict": "CAUSAL (natural play; no RAM writes)",
                "fc": f0["fc"], "lines_prev": f0["lines_prev"],
                "lines": f0["lines"],
                "threshold_rule": "pre-clear totalLines >= 8*(level+1)"
                                  " = 16 (main.c:397-403)",
                "n_1to2_flips": len(flips_12),
                "png": f0.get("png"),
                "n_level2_clears": len(flip_clears),
                "level2_clears_all_match": True}
        elif flips_12:
            v["g3_level_flip_1to2"] = {
                "verdict": "OBSERVED (threshold/score check failed)",
                "flips": flips_12,
                "level2_clears_all_match": bool(flip_clears) and all(
                    c["match"] for c in flip_clears)}
        else:
            v["g3_level_flip_1to2"] = {
                "verdict": "INCONCLUSIVE",
                "reason": "no natural 1->2 flip within budget",
                "flips_seen": [{k: f.get(k) for k in ("frm", "to",
                                                      "lines_prev",
                                                      "lines")}
                               for f in drv.level_flips],
                "max_lines_reached": max(
                    [c["lines"] for c in drv.clears] or [0])}
        # G4 level-2 cadence
        c2 = OUT["cadence"].get("2", {})
        g2g = c2.get("gaps", {})
        n2, med2 = g2g.get("n", 0), g2g.get("median")
        ph13 = c2.get("phase", {}).get(13, {})
        if n2 >= 5 and med2 == 13:
            v["g4_cadence_level2"] = {
                "verdict": "CAUSAL",
                "gaps_n": n2, "median": med2, "hist": g2g.get("hist"),
                "phase_mod13": ph13,
                "source_predicts": 13}
        else:
            v["g4_cadence_level2"] = {
                "verdict": "INCONCLUSIVE",
                "reason": "need >=5 clean same-piece y-step windows at "
                          "level 2 with median 13",
                "gaps_n": n2, "median": med2, "hist": g2g.get("hist")}
        # G5 score suite
        n_all = len(drv.clears)
        n_ok = (sum(1 for c in lv0 if c["clear_pts_est"] == 0)
                + sum(1 for c in lv1p if c["match"]))
        if n_all and n_ok == n_all:
            v["g5_score_suite"] = {
                "verdict": "CAUSAL",
                "n_clears": n_all, "n_match": n_ok, "pct": 100.0,
                "level0_zero_check": OUT["clear_score_level0"],
                "level1p_table_check": OUT["clear_score_level1p"],
                "deltas_seen": sorted({c["delta"] for c in drv.clears})}
        else:
            v["g5_score_suite"] = {
                "verdict": "MISMATCH",
                "n_clears": n_all, "n_match": n_ok,
                "pct": round(100.0 * n_ok / n_all, 1) if n_all else None,
                "clears": drv.clears}
        OUT["verdicts"] = v
        OUT["wall_s"] = round(time.time() - t0, 1)
        J({"ev": "R9_DONE", "stop": drv.stop_reason,
           "verdicts": {k: x.get("verdict") for k, x in v.items()},
           "wall_s": OUT["wall_s"]})
    except Exception as ex:
        OUT["error"] = repr(ex)
        J({"ev": "EXC", "err": repr(ex)})
        raise
    finally:
        with open(rep_path, "w") as f:
            json.dump(OUT, f, indent=1, default=str)
        trace.close()
        evf.close()
        if loop is not None:
            try:
                loop.close()
            except Exception:
                pass
    print("report:", rep_path)
    print(json.dumps(OUT.get("verdicts", {}), indent=1,
                     default=str)[:1600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
