"""TetradePlayPlugin — full-game autoplay plugin (Issue #8; round 10).

Round-10 goal (Issue-8 DoD item 4): the COMPLETE loop — boot -> title ->
START -> menu -> CROSS -> Marathon -> real gameplay with VERIFIED score/
level causality -> NATURAL game over -> refuse CONTINUE -> restart ->
fresh menu/Marathon — must run THROUGH the plugin contract v1 with zero
core edits.  Rounds 7-9 proved the loop through scripts/playloop.py
policies; this plugin now carries the same capabilities itself.

Knowledge sources (all provenance-labeled):
  - source-first: MIT Logan-Campbell/Tetrade main.c @ v1.0 (5155664):
    struct layout, control semantics, scoring, LEVEL_GOAL, game-over/
    continue flow
  - live-verified: struct base 0x1FECA0 localized by input causality
    (scripts/tetrade_calib.py), anchors in ps1play/profiles/
    tetrade_lic.json `discovered.fields`; every feature read goes
    through them; the plugin NEVER writes RAM (MemoryView is
    read-only by construction).
  - round-7 lesson: the disc EXE ignores presses before ~900 frames;
    after a CONTINUE? refusal the game lands on the MAIN MENU
    (menuState persists), so a single START confirms Marathon again
    (START during RUNNING Marathon = PAUSE — restart taps are issued
    only when no live piece is on screen, never otherwise).
  - round-9 engine: 2-ply placement search (Dellacherie eval +
    explicit TETRIS bonus) with the NEXT piece READ from live RAM
    (nextTetriminos[0] @ base+896, promotion cross-check) — ported
    here from scripts/tetrade_r9_tetris.py so the plugin is
    self-contained.

Contract surface (contract v1):
  boot_script / features / policy / infer_state (+ detectors) are all
  declared via capabilities() and negotiated with require() by the
  consumer.  policy() speaks the core AgentLoop dialect
  (ctx = {"t","chunk","stall","feat","obs"}; legacy "fc" accepted) and
  returns segments summing EXACTLY to the chunk (core.run() holds the
  last button set when called with buttons=None — documented).

Chunk discipline (score-causality by construction): each policy call
does EXACTLY ONE of {rotate, translate, hard-drop}; the hard drop is
issued as the FIRST segment of its chunk with the live ghost_y - y
distance recorded, so every scoring event decomposes EXACTLY into
2*drop_cells (+ clear_table[lines] * level for clears) — the r9
per-frame gates re-derived at chunk granularity.
"""
from ..agent import tetris_ai
from ..agent.tetris_ai import (WIDTH, minos_of,      # noqa: F401
                               shape_after, drop_row, _clear_lines,
                               evaluate, plan_segments)
from .base import GamePlugin
from .contract import CONTRACT_VERSION

# ---- source ground truth (main.c @ v1.0, live-verified rounds 7-9) ----
SRC = {
    "repo": "https://github.com/Logan-Campbell/Tetrade",
    "file": "src/main.c",
    "commit": "5155664152162a0dc04dc1f0d4f3c807c1e15388 (tag v1.0)",
    "LEVEL_GOAL": 8,                     # totalLines >= 8*(level+1)
    "clear_table": {1: 200, 2: 500, 3: 700, 4: 1000},   # x level AFTER flip
    "hard_drop_per_cell": 2,
    "nextTetriminos0_type_off": 896,     # struct base + 896; stride 92
    "Tetrimino_sizeof": 92,
}

TETRIS_BONUS = 4000.0      # r9 engine constants (validated 715/715 next-read)
DEATH_PENALTY = -8000.0
K_EXPAND = 12


# ------------------------------------------------------------------
# 2-ply placement engine (ported from scripts/tetrade_r9_tetris.py)
# ------------------------------------------------------------------
def _well_term(heights, w):
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


def choose_2ply(grid, shape, tet_size, rot_limit, nxt, well_w=0.0):
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
            v1 = (tetris_ai.W_LINES[l1] + ev1["score"]
                  + (TETRIS_BONUS if l1 >= 4 else 0.0)
                  + _well_term(ev1["heights"], well_w))
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
                    v2 = (tetris_ai.W_LINES[l2] + ev2["score"]
                          + (TETRIS_BONUS if l2 >= 4 else 0.0)
                          + _well_term(ev2["heights"], well_w))
                    if m2 is None or v2 > m2:
                        m2 = v2
            tot = v1 + (m2 if m2 is not None else DEATH_PENALTY)
        if best_tot is None or tot > best_tot:
            best_tot, best = tot, cands[i]
    return {"rot": best[1], "x": best[2], "lines": best[3]}


def _fit(segs, c):
    """Trim/pad segments to sum EXACTLY to c frames (core.run() holds
    the last button set when called with buttons=None, so an
    under-filled chunk would hold the last press — documented bug)."""
    out = []
    left = c
    for s in segs:
        k = min(s["frames"], left)
        if k > 0:
            out.append({"btns": set(s["btns"]), "frames": k})
            left -= k
        if left <= 0:
            break
    if left > 0:
        out.append({"btns": set(), "frames": left})
    return out


def _idle(c):
    return _fit([{"btns": set(), "frames": c}], c)


class TetradePlayPlugin(GamePlugin):
    ID = "tetrade_play"
    SERIALS = ()
    BOOT_EXE_NAMES = ("tetrade.exe",)
    PLUGIN_CONTRACT = CONTRACT_VERSION
    OPTIONAL_OPS = ("detectors",)

    # frames after isGameOver before the CONTINUE? prompt is up (source:
    # destruction sweep >120f) — refuse with CIRCLE, never START (START
    # would CONTINUE the game instead of ending it).
    OVER_ANIM = 150

    # struct offsets relative to the TetradeGame base (source-derived,
    # live-verified in the profile; kept here for documentation and the
    # profile-less detectors degrade path).
    OFF = {"matrix": 0, "tet_type": 800, "tet_shape": 804, "tet_x": 868,
           "tet_y": 872, "tet_held": 876, "tet_rot": 880, "next_count": 892,
           "next0_type": 896, "score": 2276, "single": 2280, "double": 2284,
           "triple": 2288, "tetra": 2292, "move_cd": 2296, "set_time": 2300,
           "level": 2304, "ghost_y": 2308, "over": 2312, "paused": 2316}
    TYPES = (1, 2, 3, 4, 5, 6, 7)
    CLEAR_TABLE = SRC["clear_table"]
    LEVEL_GOAL = SRC["LEVEL_GOAL"]
    NAV_RETRIES = 3

    def __init__(self, profile):
        super().__init__(profile)
        disc = (profile.get("discovered") or {}).get("fields") or {}
        self.f = disc                    # absolute field addrs; {} -> degrade
        self.mode = "boot"    # boot|play|wrap|over|restart|done|dead
        self.cycles = int(profile.get("cycles", 1))
        self.target_lines = profile.get("target_lines")   # None = natural
        self.target_pieces = profile.get("target_pieces")
        self.well_w = float(profile.get("well_w", 0.0))

        # per-life counters (reset every fresh cycle)
        self.pieces = 0
        self.clears = 0
        self.cycle = 1                   # 1-based life counter
        # run totals
        self.totals = {"pieces": 0, "clears": 0, "plans": 0, "drops": 0}
        self.events = []                 # contract-visible event log

        # engine stats (honest next-read validation, r9 715/715 method)
        self.engine_stats = {"choose_calls": 0, "used_2ply": 0,
                             "next_ok_calls": 0, "tetris_plans": 0,
                             "n_promotions": 0, "n_promotion_match": 0,
                             "drops_planned": 0, "drops_score_exact": 0}

        # internal bookkeeping
        self.last_type = None
        self._last_shape = None
        self._rot_stuck = 0
        self._taps_issued = 0
        self._feat_prev = None
        self._drop_pending = 0           # cells of the UP issued since the
                                         # last observed feat (max 1 chunk)
        self._drop_issued = False        # one hard drop per piece
        self._over_fc = 0
        self._refused = False
        self._restart_stage = 0
        self._restart_wait = 0
        self._restart_taps = 0
        self._nav_retries = 0
        self._nav_seen = False           # boot_script() was issued
        self._fresh_seen = False         # fresh-cycle gate passed this life
        self._post_restart_clears = 0
        self._clear_n = 0
        self._flip_n = 0
        self._marathon_entered = False

    # ---------- boot (data, not code — cached from calibration) ----------
    def boot_script(self):
        """Title -> menu -> Marathon.  Round-7 lesson: the disc EXE
        needs ~900 frames before the title accepts input; B = PAD_CROSS
        is the menu confirm (libretro X maps to TRIANGLE — dead key)."""
        self._nav_seen = True
        cached = self.profile.get("boot_script")
        if cached:
            return cached
        steps = [{"op": "wait", "frames": 900}]
        # title -> menu (hold START ~2 s like a human)
        steps += [{"op": "tap", "btns": "START", "frames": 120},
                  {"op": "tap", "btns": "", "frames": 90},
                  {"op": "wait", "frames": 120}]
        # menu -> Marathon (B = PAD_CROSS through the beetle mapping)
        steps += [{"op": "tap", "btns": "B", "frames": 20},
                  {"op": "tap", "btns": "", "frames": 20},
                  {"op": "wait", "frames": 500}]
        return steps

    # ---------- features: zero-token semantic state ----------------------
    @staticmethod
    def _s32(v):
        return v - (1 << 32) if v >= (1 << 31) else v

    def _read(self, mem, name):
        off = self.f.get(name)
        return None if off is None else self._s32(mem.u32(off))

    def features(self, mem, obs):
        if not self.f:
            return {"changed_bytes": obs.get("changed_bytes")}
        m = mem
        g = self.f["matrix"]
        grid = [[int(m.u32(g + (r * 10 + c) * 4)) for c in range(10)]
                for r in range(20)]
        shape = [[int(m.u32(self.f["tet_shape"] + (r * 4 + c) * 4))
                  for c in range(4)] for r in range(4)]
        n0t = self._read(m, "next0_type")
        n0s = None
        if n0t in self.TYPES:
            base = self.f["next0_type"] + 4
            n0s = [[int(m.u32(base + (r * 4 + c) * 4))
                    for c in range(4)] for r in range(4)]
        feat = {
            "changed_bytes": obs.get("changed_bytes"),
            "board": grid,
            "board_occupied": sum(1 for row in grid for v in row if v),
            "shape": shape,
            "type": self._read(m, "tet_type"),
            "x": self._read(m, "tet_x"),
            "y": self._read(m, "tet_y"),
            "rot": self._read(m, "tet_rot"),
            "score": self._read(m, "score"),
            "single": self._read(m, "single"),
            "double": self._read(m, "double"),
            "triple": self._read(m, "triple"),
            "tetra": self._read(m, "tetra"),
            "level": self._read(m, "level"),
            "ghost_y": self._read(m, "ghost_y"),
            "game_over": self._read(m, "game_over"),
            "paused": self._read(m, "paused"),
            "next0_type": n0t,
            "next0_shape": n0s,
        }
        feat["lines_total"] = ((feat["single"] or 0)
                               + 2 * (feat["double"] or 0)
                               + 3 * (feat["triple"] or 0)
                               + 4 * (feat["tetra"] or 0))
        return feat

    # ---------- state classification (detectors op) -----------------------
    def _live_piece(self, feat):
        x, y = feat.get("x"), feat.get("y")
        return (feat.get("type") in self.TYPES
                and isinstance(x, int) and 0 <= x <= 10
                and isinstance(y, int) and 0 <= y <= 20)

    def _menu_like(self, feat):
        """No live piece, no game over, not paused — the title screen,
        the main menu, or the post-refusal menu (board state is NOT
        consulted: the dead board lingers until Marathon restarts)."""
        return (not feat.get("game_over") and not feat.get("paused")
                and not self._live_piece(feat))

    def _quiescent_fresh(self, feat):
        """Menu with a fully reset struct (title / pristine menu)."""
        return (self._menu_like(feat)
                and feat.get("type") in (0, -1, None)
                and feat.get("score") in (0, None)
                and feat.get("level") in (0, None))

    def _fresh_cycle(self, feat):
        """reset_tetris_game zeroes score/line-counters/level each life
        (round-7 verified on every restart).  Board occupancy is NOT a
        fresh signal: gravity piles pieces while the plugin is still
        navigating, so only the counters are authoritative."""
        return (feat.get("game_over") == 0 and feat.get("score") == 0
                and feat.get("single") == 0 and feat.get("double") == 0
                and feat.get("triple") == 0 and feat.get("tetra") == 0
                and feat.get("level") == 0)

    def infer_state(self, obs, feat):
        if not feat or ("type" not in feat and "board" not in feat):
            return "unknown"
        if feat.get("game_over"):
            return "gameover"
        if feat.get("paused"):
            return "paused"
        if self._live_piece(feat):
            return "marathon"
        if self._quiescent_fresh(feat):
            # honest hybrid label: RAM says menu-like with a reset
            # struct; title-vs-menu is provenance from the plugin's own
            # navigation phase (boot_script not yet issued -> title).
            return "menu" if self._nav_seen else "title"
        if self.mode in ("restart", "over") and self._menu_like(feat):
            return "menu"            # post-refusal menu (dead board)
        return "unknown"

    def detectors(self, mem):
        """Named detectors from live RAM (contract op `detectors`)."""
        feat = self.features(mem, {"changed_bytes": 0})
        return {"fields_present": bool(self.f),
                "live_piece": self._live_piece(feat),
                "game_over": bool(feat.get("game_over")),
                "paused": bool(feat.get("paused")),
                "menu_like": self._menu_like(feat),
                "quiescent_fresh": self._quiescent_fresh(feat),
                "fresh_cycle": self._fresh_cycle(feat),
                "state": self.infer_state({}, feat),
                "values": {k: feat.get(k) for k in
                           ("type", "x", "y", "score", "level",
                            "lines_total", "game_over", "paused",
                            "board_occupied")}}

    # ---------- events -----------------------------------------------------
    def _j(self, e, fc=None):
        if fc is not None:
            e["fc"] = fc
        self.events.append(e)
        return e

    # ---------- lifecycle helpers ------------------------------------------
    def _begin_life(self, feat, fc):
        """Reset per-life bookkeeping after the fresh-cycle gate passed."""
        self.pieces = 0
        self.clears = 0
        self._clear_n = 0
        self._fresh_seen = True
        self.last_type = None
        self._last_shape = None
        self._rot_stuck = 0
        self._taps_issued = 0
        self._feat_prev = feat
        self._drop_pending = 0
        self._drop_issued = False
        self._nav_retries = 0
        self.mode = "play"
        self._j({"ev": "fresh_cycle_verified", "cycle": self.cycle}, fc)
        if not self._marathon_entered:
            self._marathon_entered = True
            self._j({"ev": "marathon_entered", "cycle": self.cycle,
                     "png": True}, fc)

    def _game_over_enter(self, feat, fc):
        self.mode = "over"
        self._over_fc = 0
        self._refused = False
        self._j({"ev": "game_over", "cycle": self.cycle,
                 "score": feat.get("score"),
                 "lines_total": feat.get("lines_total"),
                 "level": feat.get("level"),
                 "pieces": self.pieces, "png": True}, fc)

    # ---------- causality bookkeeping (chunk granularity, exact) ----------
    def _bookkeep(self, feat, fc):
        prev = self._feat_prev
        if prev is None:
            return
        lines = feat.get("lines_total") or 0
        prev_lines = prev.get("lines_total") or 0
        score = feat.get("score")
        prev_score = prev.get("score")
        d_lines = lines - prev_lines
        d_score = (score - prev_score) if (score is not None
                                           and prev_score is not None) else 0
        level = feat.get("level") or 0

        # next-piece promotion cross-check (r9 method, chunk granularity):
        # a newly observed piece type must equal the previously read
        # nextTetriminos[0].type
        typ = feat.get("type")
        if typ in self.TYPES and self.last_type != typ \
                and prev.get("next0_type") is not None:
            st = self.engine_stats
            st["n_promotions"] += 1
            if prev.get("next0_type") == typ:
                st["n_promotion_match"] += 1

        drop_pts = 2 * self._drop_pending
        if d_lines > 0:
            kinds = {"d1": (feat.get("single") or 0)
                     - (prev.get("single") or 0),
                     "d2": (feat.get("double") or 0)
                     - (prev.get("double") or 0),
                     "d3": (feat.get("triple") or 0)
                     - (prev.get("triple") or 0),
                     "d4": (feat.get("tetra") or 0)
                     - (prev.get("tetra") or 0)}
            n_ev = sum(kinds.values())
            self.clears += d_lines
            self.totals["clears"] += d_lines
            self._clear_n += 1
            self._post_restart_clears += d_lines
            e = self._j({"ev": "line_clear", "cycle": self.cycle,
                         "delta": d_lines, "kinds": kinds, "level": level,
                         "lines_total": lines,
                         "score_prev": prev_score, "score": score,
                         "score_delta": d_score,
                         "drop_cells_pending": self._drop_pending,
                         "drop_pts": drop_pts,
                         "png": self._clear_n <= 3 or kinds["d4"] > 0}, fc)
            if n_ev == 1 and d_lines <= 4:
                expected = self.CLEAR_TABLE[d_lines] * level
                clear_pts = d_score - drop_pts
                e["expected_pts"] = expected
                e["clear_pts"] = clear_pts
                e["match"] = bool(clear_pts == expected)
            else:
                e["match"] = None
                e["note"] = "multi-event chunk — no single-event claim"
        elif d_score != 0:
            # drop points only: hard drop pays +2/cell (source-verified)
            self._j({"ev": "score_delta", "cycle": self.cycle,
                     "from": prev_score, "to": score,
                     "delta": d_score, "level": level,
                     "drop_cells_pending": self._drop_pending,
                     "drop_pts_expected": drop_pts,
                     "match": bool(d_score == drop_pts)}, fc)
            if d_score == drop_pts and self._drop_pending > 0:
                self.engine_stats["drops_score_exact"] += 1
        if feat.get("level") != prev.get("level") \
                and prev.get("level") is not None:
            thr = self.LEVEL_GOAL * ((prev.get("level") or 0) + 1)
            self._flip_n += 1
            self._j({"ev": "level_flip",
                     "frm": prev.get("level"), "to": feat.get("level"),
                     "lines_prev": prev_lines, "lines_total": lines,
                     "threshold": thr,
                     "threshold_ok": bool(prev_lines >= thr),
                     "score": score, "png": self._flip_n <= 2}, fc)
        self._drop_pending = 0
        self._feat_prev = feat

    # ---------- gameplay (one action class per chunk) ----------------------
    def _play_step(self, feat, c, fc):
        self._bookkeep(feat, fc)

        # game over transition (natural top-out)
        if feat.get("game_over"):
            self._game_over_enter(feat, fc)
            return _idle(c)

        # piece bookkeeping
        typ = feat.get("type")
        if typ not in self.TYPES:
            if self.last_type in self.TYPES:
                self.pieces += 1
                self.totals["pieces"] += 1
            self.last_type = typ if typ == -1 else None
            self._last_shape = None
            self._taps_issued = 0
            self._drop_issued = False
            return _idle(c)
        if typ != self.last_type:
            if self.last_type is not None:
                self.pieces += 1
                self.totals["pieces"] += 1
            self.last_type = typ
            self._rot_stuck = 0
            self._last_shape = None
            self._taps_issued = 0
            self._drop_issued = False
        if self._drop_issued:
            # hard drop already issued for this piece; wait for the spawn
            return _idle(c)

        # wrap-up (only when targets are configured; default = play until
        # the NATURAL top-out — required for the honest game-over gate)
        wrap = ((self.target_lines is not None
                 and self.clears >= self.target_lines)
                or (self.target_pieces is not None
                    and self.pieces >= self.target_pieces))
        if wrap and self.mode == "play":
            self.mode = "wrap"
            self._j({"ev": "wrap_up", "cycle": self.cycle,
                     "pieces": self.pieces, "clears": self.clears}, fc)
        if self.mode == "wrap":
            return _fit([{"btns": {"UP"}, "frames": 1},
                         {"btns": set(), "frames": 3}], c)

        # sanity gate: mid-lock transient reads can be garbage
        if not self._live_piece(feat):
            return _idle(c)

        # rotation-stuck detection (SRS kick rejection near a wall)
        shape_key = tuple(map(tuple, feat["shape"]))
        if self._last_shape == shape_key and self._taps_issued:
            self._rot_stuck += 1
        elif self._last_shape is not None and shape_key != self._last_shape:
            self._rot_stuck = 0
        self._last_shape = shape_key

        # 2-ply engine with the live NEXT piece (read-only)
        nxt = None
        if feat.get("next0_type") in self.TYPES and feat.get("next0_shape"):
            nxt = (feat["next0_type"], feat["next0_shape"])
        st = self.engine_stats
        st["choose_calls"] += 1
        if nxt is not None:
            st["next_ok_calls"] += 1
        target = choose_2ply(feat["board"], feat["shape"],
                             4 if typ <= 2 else 3,
                             rot_limit=1 if self._rot_stuck >= 2 else 4,
                             nxt=nxt, well_w=self.well_w)
        if nxt is not None:
            st["used_2ply"] += 1
        self.totals["plans"] += 1
        if target is None:                       # board too full
            self._j({"ev": "plan", "cycle": self.cycle, "type": typ,
                     "act": "none", "target": None}, fc)
            return _idle(c)
        if target["lines"] == 4:
            st["tetris_plans"] += 1

        # ONE action class per chunk (score-causality by construction)
        n_rot = 0 if self._rot_stuck >= 2 else target["rot"]
        if n_rot > 0:
            taps = min(2, n_rot, max(1, (c - 10) // 3))
            segs = []
            for _ in range(taps):
                segs.append({"btns": {"A"}, "frames": 1})   # CIRCLE CW
                segs.append({"btns": set(), "frames": 2})
            self._taps_issued = taps
            self._j({"ev": "plan", "cycle": self.cycle, "type": typ,
                     "act": "rotate", "rot_pending": n_rot - taps,
                     "want_x": target["x"],
                     "want_clear": target["lines"]}, fc)
            return _fit(segs, c)
        if feat["x"] != target["x"]:
            self._taps_issued = 0
            self._j({"ev": "plan", "cycle": self.cycle, "type": typ,
                     "act": "translate", "x": feat["x"],
                     "want_x": target["x"],
                     "want_clear": target["lines"]}, fc)
            return _fit(plan_segments(feat["x"], target["x"],
                                      drop_now=False), c)
        # aligned: hard drop as the FIRST segment, distance recorded
        dy = None
        if feat.get("ghost_y") is not None and feat.get("y") is not None:
            dy = max(0, feat["ghost_y"] - feat["y"])
        self._drop_pending = dy or 0
        self._drop_issued = True
        self.totals["drops"] += 1
        st["drops_planned"] += 1
        self._j({"ev": "plan", "cycle": self.cycle, "type": typ,
                 "act": "hard_drop", "x": feat["x"], "drop_cells": dy,
                 "want_clear": target["lines"]}, fc)
        return _fit([{"btns": {"UP"}, "frames": 1},
                     {"btns": set(), "frames": 3}], c)

    # ---------- game-over -> refuse -> restart ----------------------------
    def _over_step(self, feat, c, fc):
        if feat.get("game_over"):
            self._over_fc += c
            if self._over_fc >= self.OVER_ANIM and not self._refused:
                self._refused = True
                self.mode = "restart"
                self._restart_stage = 0
                self._restart_wait = 120      # menu settle
                self._restart_taps = 0
                self._nav_retries = 0
                self._j({"ev": "refuse_continue", "cycle": self.cycle,
                         "via": "A(PAD_CIRCLE)", "png": True}, fc)
                return _fit([{"btns": {"A"}, "frames": 3},
                             {"btns": set(), "frames": max(0, c - 3)}], c)
            return _idle(c)
        self.mode = "restart"                  # menu took over
        return self._restart_step(feat, c, fc)

    def _restart_step(self, feat, c, fc):
        # 0) the destruction/CONTINUE? screens must NEVER receive taps
        #    here (START would CONTINUE the game — the refusal's undo)
        if feat.get("game_over"):
            return _idle(c)
        # 1) fresh Marathon with a live piece -> restart VERIFIED
        if self._fresh_cycle(feat) and self._live_piece(feat):
            self._post_restart_clears = 0
            self.cycle += 1
            self._fresh_seen = False
            self.mode = "play"
            self._j({"ev": "restart_complete", "cycle": self.cycle,
                     "fresh": True, "png": True}, fc)
            return _idle(c)
        # 2) safety: never tap while a piece is live (START = PAUSE)
        if self._live_piece(feat):
            self._restart_wait -= c
            if self._restart_wait < -1800:
                self.mode = "dead"
                self._j({"ev": "restart_failed", "cycle": self.cycle,
                         "reason": "live piece but struct never reset"},
                        fc)
            return _idle(c)
        if feat.get("paused"):
            self._j({"ev": "restart_unpause", "cycle": self.cycle}, fc)
            return _fit([{"btns": {"START"}, "frames": 15},
                         {"btns": set(), "frames": max(0, c - 15)}], c)
        # 3) menu-like: settle, then the stage taps (START then B;
        #    covers the persistent-menu path and the title fallback)
        if self._restart_wait > 0:
            self._restart_wait -= c
            return _idle(c)
        if self._nav_retries >= self.NAV_RETRIES:
            self.mode = "dead"
            self._j({"ev": "restart_failed", "cycle": self.cycle,
                     "reason": "no fresh Marathon after retries"}, fc)
            return _idle(c)
        stage = self._restart_stage
        btn = "START" if stage == 0 else "B"
        self._restart_stage = (stage + 1) % 2
        if stage == 1:
            self._nav_retries += 1             # full START->B round used
        self._restart_taps += 1
        self._restart_wait = 600
        self._j({"ev": "restart_nav", "btn": btn, "stage": stage,
                 "attempt": self._nav_retries + 1,
                 "png": self._restart_taps == 1}, fc)
        return _fit([{"btns": {btn}, "frames": 20},
                     {"btns": set(), "frames": 20}], c)

    # ---------- main policy entry (contract hook) -------------------------
    def policy(self, ctx):
        c = ctx["chunk"]
        fc = ctx.get("fc", ctx.get("t", 0))
        feat = ctx.get("feat") or {}
        if not feat or ("type" not in feat and "board" not in feat):
            return _idle(c)                    # fields missing: honest idle

        if self.mode in ("boot", "done"):
            # wait for the plugin's own fresh-cycle discovery
            if self.mode == "boot":
                if feat.get("game_over"):
                    self._game_over_enter(feat, fc)   # attached mid-over
                    return _idle(c)
                if self._fresh_cycle(feat) and self._live_piece(feat):
                    self._begin_life(feat, fc)
                    return self._play_step(feat, c, fc)
            return _idle(c)

        if self.mode == "play":
            if not self._fresh_seen:
                if self._fresh_cycle(feat) and self._live_piece(feat):
                    self._begin_life(feat, fc)
                else:
                    return _idle(c)
            return self._play_step(feat, c, fc)

        if self.mode == "wrap":
            self._bookkeep(feat, fc)
            if feat.get("game_over"):
                self._game_over_enter(feat, fc)
                return _idle(c)
            return _fit([{"btns": {"UP"}, "frames": 1},
                         {"btns": set(), "frames": 3}], c)

        if self.mode == "over":
            return self._over_step(feat, c, fc)

        if self.mode == "restart":
            return self._restart_step(feat, c, fc)

        return _idle(c)

    # ---------- loop-completion guard (called by the consumer) ------------
    def maybe_finish(self, fc=None):
        """The consumer may call this after each chunk: the loop is
        COMPLETE when the final restart has been verified AND the fresh
        life produced >= 1 verified clear (fresh gameplay proof)."""
        if self.mode == "play" and self.cycle > self.cycles \
                and self._post_restart_clears >= 1:
            self.mode = "done"
            self._j({"ev": "loop_complete", "cycles": self.cycles,
                     "totals": dict(self.totals)}, fc)
            return True
        return False

    # ---------- verdict flags (honest summary for the consumer) -----------
    def verdict_flags(self):
        return {"state_change_confirmed": self.totals["pieces"] > 0,
                "gameplay_confirmed": self.totals["clears"] > 0,
                "pieces": self.totals["pieces"],
                "clears": self.totals["clears"],
                "cycles": self.cycle,
                "mode": self.mode,
                "engine": dict(self.engine_stats)}
