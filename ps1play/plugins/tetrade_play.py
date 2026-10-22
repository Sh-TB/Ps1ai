"""TetradePlayPlugin — full-game autoplay plugin (Issue #8, T5).

Second-generation Tetrade plugin: plays REAL Tetris through the shared
core with zero core edits and zero memory writes.

Knowledge sources (all provenance-labeled):
  - source-first: MIT Logan-Campbell/Tetrade main.c struct layout,
    control semantics, scoring, game-over/continue flow
  - live-verified: struct base localized by input causality
    (scripts/tetrade_calib.py), anchors stored in the profile
    `discovered.fields` dict; every feature read goes through them.

Learning loop implemented here (documented in docs/tetrade_playthrough.md):
  screen/boot calibration -> RAM struct localization by input causality ->
  per-piece closed-loop control (read shape/x/rot from RAM, pick the best
  placement with the pure evaluator ps1play.agent.tetris_ai, steer with
  measured hold semantics, verify after every tap, re-plan from live state
  every chunk — the loop is stateless and idempotent per piece).
"""
from ..agent import tetris_ai
from .base import GamePlugin


class TetradePlayPlugin(GamePlugin):
    ID = "tetrade_play"
    SERIALS = ()
    BOOT_EXE_NAMES = ("tetrade.exe",)
    OPTIONAL_OPS = ("detectors",)

    # frames after isGameOver before the CONTINUE? prompt is up (source:
    # destruction sweep >120f) — refuse with CIRCLE, never START (START
    # would CONTINUE the game instead of ending it).
    OVER_ANIM = 150

    def __init__(self, profile):
        super().__init__(profile)
        disc = (profile.get("discovered") or {}).get("fields") or {}
        self.f = disc                    # field offsets, empty -> features {}
        self.mode = "play"               # play | wrap | over | done
        self.pieces = 0
        self.clears = 0
        self.singles = 0
        self.last_type = None
        self._rot_stuck = 0
        self._over_fc = 0
        self._refused = False
        self._last_shape = None
        self._feat_prev = None
        self.events = []

    # ---------- boot (data, not code — cached from calibration) ----------
    def boot_script(self):
        cached = self.profile.get("boot_script")
        if cached:
            return cached
        steps = [{"op": "wait", "frames": 900}]
        # title -> menu (hold START ~2 s like a human)
        steps += [{"op": "tap", "btns": "START", "frames": 120},
                  {"op": "tap", "btns": "", "frames": 90},
                  {"op": "wait", "frames": 120}]
        # menu -> Marathon (B = PAD_CROSS through beetle mapping)
        steps += [{"op": "tap", "btns": "B", "frames": 20},
                  {"op": "tap", "btns": "", "frames": 20},
                  {"op": "wait", "frames": 500}]
        return steps

    # ---------- features: zero-token semantic state ----------------------
    def _read(self, mem, name):
        off = self.f.get(name)
        return mem.u32(off) if off is not None else None

    def features(self, mem, obs):
        if not self.f:
            return {"changed_bytes": obs.get("changed_bytes")}
        m = mem
        g = self.f["matrix"]
        grid = [[int(m.u32(g + (r * 10 + c) * 4)) for c in range(10)]
                for r in range(20)]
        shape = [[int(m.u32(self.f["tet_shape"] + (r * 4 + c) * 4))
                  for c in range(4)] for r in range(4)]
        typ = self._read(m, "tet_type")
        feat = {
            "changed_bytes": obs.get("changed_bytes"),
            "board": grid,
            "board_occupied": sum(1 for row in grid for v in row if v),
            "shape": shape,
            "type": typ,
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
        }
        lines_total = ((feat["single"] or 0) + 2 * (feat["double"] or 0)
                       + 3 * (feat["triple"] or 0) + 4 * (feat["tetra"] or 0))
        feat["lines_total"] = lines_total
        return feat

    # ---------- state classification (detectors op) -----------------------
    def infer_state(self, obs, feat):
        if feat.get("game_over"):
            return "gameover"
        if feat.get("paused"):
            return "paused"
        if feat.get("type") in (1, 2, 3, 4, 5, 6, 7):
            return "gameplay"
        return "unknown"

    # ---------- policy -----------------------------------------------------
    def policy(self, ctx):
        """Return action segments for this chunk (stateless re-plan)."""
        c = ctx["chunk"]
        feat = ctx.get("feat") or {}
        over = feat.get("game_over") or 0

        # --- done: loop closed (title after refusal/countdown) ------------
        if self.mode == "done":
            return [{"btns": set(), "frames": c}]

        # --- game over: destruction anim, then refuse CONTINUE once -------
        if over:
            self.mode = "over"
            self._over_fc += c
            if self._over_fc >= self.OVER_ANIM and not self._refused:
                self._refused = True
                self.events.append({"ev": "refuse_continue", "fc": ctx["fc"]})
                return [{"btns": {"A"}, "frames": 3},     # A = PAD_CIRCLE
                        {"btns": set(), "frames": max(0, c - 3)}]
            return [{"btns": set(), "frames": c}]

        # not over anymore: if we refused, the game reset us to the title
        if self._refused:
            self.mode = "done"
            return [{"btns": set(), "frames": c}]

        # sanity gate: mid-lock transient reads can be garbage (x=-1) —
        # never plan on them, just idle one chunk
        x_ok = feat.get("x") is not None and 0 <= feat.get("x") <= 10
        y_ok = feat.get("y") is not None and 0 <= feat.get("y") <= 20
        typ = feat.get("type")
        if not (x_ok and y_ok) or typ not in (1, 2, 3, 4, 5, 6, 7):
            return [{"btns": set(), "frames": c}]        # between pieces

        # --- wrap-up: stop steering, top out honestly ---------------------
        if (self.mode == "play"
                and self.pieces >= ctx.get("target_pieces", 30)
                and self.clears >= ctx.get("target_lines", 6)):
            self.mode = "wrap"
            self.events.append({"ev": "wrap_up", "fc": ctx["fc"],
                                "pieces": self.pieces,
                                "clears": self.clears})

        typ = feat.get("type")
        if typ not in (1, 2, 3, 4, 5, 6, 7):
            return [{"btns": set(), "frames": c}]        # between pieces

        # --- piece bookkeeping --------------------------------------------
        if typ != self.last_type:
            if self.last_type is not None:
                self.pieces += 1
            self.last_type = typ
            self._rot_stuck = 0
            self._last_shape = None

        # score/lines event bookkeeping (verification evidence)
        if getattr(self, "_feat_prev", None):
            d_lines = feat["lines_total"] - self._feat_prev["lines_total"]
            if d_lines > 0:
                self.clears += d_lines
                self.events.append({"ev": "line_clear", "fc": ctx["fc"],
                                    "delta": d_lines,
                                    "score": feat["score"],
                                    "lines_total": feat["lines_total"]})
        self._feat_prev = feat

        segs = []
        left = c
        if self.mode == "wrap":
            segs.append({"btns": {"UP"}, "frames": min(2, left)})
            left -= min(2, left)
            segs.append({"btns": set(), "frames": left})
            return segs

        # --- closed-loop play: re-plan from live state every chunk --------
        grid = feat["board"]
        shape = feat["shape"]
        tet_size = 4 if typ <= 2 else 3
        x_cur = feat.get("x", 0)
        shape_key = tuple(map(tuple, shape))

        # rotation-stuck detection: same shape across chunks while taps
        # were issued means the SRS kick rejected the rotation near a wall
        if self._last_shape == shape_key:
            self._rot_stuck += 1
        else:
            self._rot_stuck = 0
        self._last_shape = shape_key

        target = tetris_ai.choose(
            grid, shape, tet_size,
            rot_limit=1 if self._rot_stuck >= 2 else 4)
        if target is None:                                # board too full
            segs.append({"btns": {"UP"}, "frames": min(2, left)})
            left -= min(2, left)
            segs.append({"btns": set(), "frames": left})
            return segs

        # 1) rotation taps (max 2 per chunk, verify next chunk)
        n_rot = 0 if self._rot_stuck >= 2 else target["rot"]
        taps = min(2, n_rot, max(0, (left - 10) // 3))
        for _ in range(taps):
            segs.append({"btns": {"A"}, "frames": 1})     # A = PAD_CIRCLE CW
            segs.append({"btns": set(), "frames": 2})
            left -= 3
        if n_rot > taps:                                  # finish next chunk
            segs.append({"btns": set(), "frames": left})
            return segs

        # 2) translation + 3) hard drop via per-cell plan (closed loop:
        #    next chunk re-reads x and corrects any miscount)
        drop_now = (target["x"] == x_cur)
        segs += tetris_ai.plan_segments(x_cur, target["x"], drop_now)
        used = sum(s["frames"] for s in segs)
        if used < left:
            segs.append({"btns": set(), "frames": left - used})
        return segs
