"""ps1play.adapters.tetrade.policy — the built-in Tetrade policy (R64).

The R63 Dellacherie 2-ply heuristic (scripts/r63_tetrade_full_loop.py,
commit c708c03) ported VERBATIM behind the runtime `Policy` contract:

  * planning (per NEW piece only): 1-ply Dellacherie score over every
    (rotation, column) of the current piece on the locked board, then
    a 2-ply refinement of the top-8 placements against the NEXT piece
    (total = v + 0.5 * v_next). Weights are the classic Dellacherie
    table used by R63 — hand-written constants, NOT learned.
  * realization (per decision frame): the R63 execution semantics —
    rotate CW taps toward the target rot (game applies on press,
    >= 6f apart), then horizontal taps toward the target column
    (moveCooldown = 10f -> >= 11f apart), then one hard-drop frame
    (UP), then a 40f settle. Everything the engine sees is ONE frame
    of buttons per decision, exactly the runtime's one-frame-pulse
    contract.

Honest identity: a code-based policy — identity() reports the sha256
of this module's source so every episode record pins the exact policy
bytes that ran. No model, no training, no teacher (TRAINING STAYS
CLOSED).
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ps1play.runtime.errors import RuntimePolicyError
from ps1play.runtime.interfaces import (ActionDecision, GameObservation,
                                        Policy)

POLICY_VERSION = "1.1.0"
POLICY_NAME = "tetrade_dellacherie_2ply (R65 anchor-corrected, " \
              "hand-written; R63-ported)"

# ---- piece geometry (verbatim semantics from the MIT-licensed source)
BASE = {
    1: [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]],  # I
    2: [[0, 0, 0, 0], [0, 1, 1, 0], [0, 1, 1, 0], [0, 0, 0, 0]],  # O
    3: [[1, 0, 0, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # J
    4: [[0, 0, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # L
    5: [[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # Z
    6: [[0, 1, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # S
    7: [[0, 1, 0, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],  # T
}
W, H = 10, 20
Wts = {"lh": -4.500158, "epc": 3.418126, "rt": -3.217888,
       "ct": -9.348695, "holes": -7.899265, "wells": -3.385597}

# realization constants (R63 execution semantics)
ROT_COOLDOWN = 6       # idle frames after a rotate tap
MOVE_COOLDOWN = 11     # moveCooldown = 10 in the game
DROP_SETTLE = 40       # idle frames after the hard drop
MAX_ROT_TAPS = 4       # full circle; more means the plan is stale
MAX_MOVES = 12         # R63's horizontal-tap cap
MAX_FRAMES_ON_PLAN = 240   # stuck-plan fuse (forces the drop)

# ---- R65 measured anchor table (scripts/r65_tetrade_anchor.json) ----
# The struct's x is NOT the left edge of the policy's rot90 model for
# every rotation.  Measured on the real game (28/28 type x rotation
# combos, legal input only, read-only RAM): the game renders the
# 3-wide pieces (types 3..7) ONE COLUMN LEFT of the model at
# rotations 1 and 2; the I (1) and O (2) pieces never shift.  The
# delta is uniform across every measured x (n=4..5 per rotation-0
# combo, zero variance) and the realized SHAPE always matched the
# model (rotation semantics correct; only the column anchor drifts).
# Planning must use the TRUE columns or pieces bury holes (measured
# with the uncorrected model: 39 holes at death, 8/22 placements one
# column off — data/r65/r65_tetrade_lockprobe.json).
ANCHOR_DELTA = {(t, r): 0 for t in range(1, 8) for r in range(4)}
for _t in (3, 4, 5, 6, 7):
    ANCHOR_DELTA[(_t, 1)] = -1
    ANCHOR_DELTA[(_t, 2)] = -1

PHASES = ("ROTATE", "MOVE", "DROP", "SETTLE", "DONE")


def rot_shape(t: int, r: int) -> np.ndarray:
    return np.rot90(np.array(BASE[t], dtype=int), k=-r)


def cells(shape: np.ndarray) -> List[tuple]:
    return [(int(r), int(c)) for r, c in zip(*np.nonzero(shape))]


def drop_y(board: np.ndarray, shape: np.ndarray, x: int):
    for y in range(H + 1):
        for dr, dc in cells(shape):
            rr, cc = y + dr, x + dc
            if rr >= H or (rr >= 0 and cc >= 0 and board[rr, cc]):
                return y - 1
    return -1


def evaluate(board: np.ndarray, shape: np.ndarray, x: int):
    """Dellacherie features for a hypothetical placement (R63 port)."""
    y = drop_y(board, shape, x)
    if y < 0:
        return None, None
    placed = board.copy()
    for dr, dc in cells(shape):
        placed[y + dr, x + dc] = 1
    full = np.flatnonzero((placed == 1).all(axis=1))
    nclear = len(full)
    lh = H - (y + np.mean([dr for dr, _ in cells(shape)]))
    epc = 0
    if nclear:
        for dr, dc in cells(shape):
            if y + dr in set(full.tolist()):
                epc += 1
        epc *= nclear
    b = placed
    if nclear:
        keep = [r for r in range(H) if r not in set(full.tolist())]
        b = np.vstack([np.zeros((H - len(keep), W), dtype=int),
                       placed[keep]])
    pad = np.ones((H + 2, W + 2), dtype=int)
    pad[1:H + 1, 1:W + 1] = (b > 0)
    rt = 0
    for r in range(1, H + 1):
        row = pad[r]
        rt += int(np.sum(row[1:W + 1] != row[:W]))
    ct = 0
    for c in range(1, W + 1):
        col = pad[:, c]
        ct += int(np.sum(col[1:H + 1] != col[:H]))
    holes = 0
    for c in range(W):
        col = b[:, c]
        seen = False
        for r in range(H):
            if col[r]:
                seen = True
            elif seen:
                holes += 1
    wells = 0
    for c in range(W):
        r = 0
        while r < H:
            left = b[r, c - 1] if c else 1
            right = b[r, c + 1] if c < W - 1 else 1
            if not b[r, c] and left and right:
                k = 0
                while (r + k < H and not b[r + k, c]
                       and (c == 0 or b[r + k, c - 1])
                       and (c == W - 1 or b[r + k, c + 1])):
                    k += 1
                wells += k * (k + 1) // 2
                r += k
            else:
                r += 1
    score = (Wts["lh"] * lh + Wts["epc"] * epc + Wts["rt"] * rt
             + Wts["ct"] * ct + Wts["holes"] * holes
             + Wts["wells"] * wells)
    if nclear == 4:
        score += 8.0
    return score, {"lh": round(float(lh), 2), "epc": epc, "rt": rt,
                   "ct": ct, "holes": holes, "wells": wells,
                   "clear": nclear}


def plan_placement(board: np.ndarray, ptype: int, next_type: int):
    """The R63 2-ply plan, R65 anchor-corrected: best (rot, x) for the
    current piece, refined over the top-8 1-ply placements against the
    NEXT piece.  `x` candidates are STRUCT x values (what the
    controller steers to); all board physics run at the TRUE columns
    x + ANCHOR_DELTA[(type, rot)] (the measured column-anchor shift).
    Returns (r_t, x_t, info, v1) or None when no placement exists."""
    if not (1 <= ptype <= 7):
        return None
    shorts = []
    for r in range(4):
        shape = rot_shape(ptype, r)
        d = ANCHOR_DELTA[(ptype, r)]
        for x in range(-1, W):
            xe = x + d               # the TRUE game columns
            if any(xe + dc < 0 or xe + dc >= W for _, dc in cells(shape)):
                continue
            v, info = evaluate(board, shape, xe)
            if v is None:
                continue
            shorts.append((v, r, x, info))
    if not shorts:
        return None
    shorts.sort(key=lambda t: t[0], reverse=True)
    refined = None
    for v, r, x, info in shorts[:8]:
        shape = rot_shape(ptype, r)
        d = ANCHOR_DELTA[(ptype, r)]
        xe = x + d
        y = drop_y(board, shape, xe)
        if y < 0:
            continue
        b2 = board.copy()
        for dr, dc in cells(shape):
            b2[y + dr, xe + dc] = 1
        full = np.flatnonzero((b2 == 1).all(axis=1))
        for rr in full:
            b2[rr, :] = 0
        b2 = np.vstack([np.zeros((len(full), W), dtype=int), b2])[:H]
        bn = (b2 > 0).astype(int)
        vn = None
        if 1 <= next_type <= 7:
            for rn in range(4):
                sn = rot_shape(next_type, rn)
                for xn in range(-1, W):
                    if any(xn + dc < 0 or xn + dc >= W
                           for _, dc in cells(sn)):
                        continue
                    vv, _ = evaluate(bn, sn, xn)
                    if vv is not None and (vn is None or vv > vn):
                        vn = vv
        total = v + 0.5 * (vn if vn is not None else 0.0)
        if refined is None or total > refined[0]:
            refined = (total, r, x, info, v)
    if refined is None:
        return None
    total, r_t, x_t, info, v1 = refined
    return int(r_t), int(x_t), info, float(v1)


class DellacheriePolicy(Policy):
    """Per-frame realization of the R63 plan (see module docstring)."""

    def __init__(self, config=None, telemetry=None):
        self._tel = telemetry
        self._identity = {
            "name": POLICY_NAME,
            "version": POLICY_VERSION,
            "model_sha256": self._source_sha256(),
            "manifest_sha256": None,
            "kind": "built-in heuristic (no model, no training)",
        }
        self._n_calls = 0
        self._reset_plan()

    @staticmethod
    def _source_sha256() -> str:
        try:
            with open(os.path.abspath(__file__), "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except OSError:
            return "?"

    def _reset_plan(self) -> None:
        self._plan: Optional[Dict[str, Any]] = None
        self._plan_key: Optional[bytes] = None
        self._cooldown = 0
        self._paused_wait = 0
        self._paused_seen = False

    # ---- Policy surface ----
    def legal_actions(self) -> Sequence[str]:
        return ("IDLE", "ROT_CW", "MOVE_L", "MOVE_R", "HARD_DROP",
                "PAUSE_TOGGLE")

    def predict(self, observation: GameObservation) -> ActionDecision:
        if not observation.valid or observation.values is None:
            raise RuntimePolicyError(
                f"refusing invalid observation (frame "
                f"{observation.frame_id}): "
                f"{observation.invalid_reason or 'marked invalid'}")
        t0 = time.perf_counter()
        v = observation.values
        if v.shape != (TETRADE_VECTOR_LEN,):
            raise RuntimePolicyError(
                f"tetrade observation shape mismatch: expected "
                f"({TETRADE_VECTOR_LEN},), got {v.shape} "
                f"(frame {observation.frame_id})")
        board = (v[:200].reshape(20, 10) > 0.5).astype(int)
        tslot = v[200:207]
        ptype = int(np.argmax(tslot)) + 1 if tslot.sum() > 0.5 else 0
        rot = int(round(float(v[207]))) % 4
        x = int(round(float(v[208])))
        nslot = v[210:217]
        next_type = (int(np.argmax(nslot)) + 1
                     if nslot.sum() > 0.5 else 0)
        over = v[220] > 0.5
        paused = v[221] > 0.5

        action, diag = self._decide(board, ptype, rot, x, next_type,
                                    over, paused)
        ms = (time.perf_counter() - t0) * 1000.0
        self._n_calls += 1
        if self._tel is not None:
            self._tel.latency("policy_ms", ms)
        return ActionDecision(
            action=action, logits=None,
            frame_seq=observation.frame_seq,
            policy_name=self._identity["name"],
            policy_sha256=self._identity["model_sha256"],
            latency_ms=ms, diagnostics=diag)

    # ---- the decision state machine ----
    def _decide(self, board, ptype, rot, x, next_type, over, paused):
        diag: Dict[str, Any] = {"piece_type": ptype, "rot": rot,
                                "x": x, "next": next_type,
                                "paused": bool(paused),
                                "over": bool(over)}
        if over:
            self._reset_plan()
            diag["phase"] = "OVER"
            return "IDLE", diag
        # pause recovery: one START tap, then wait before re-tapping
        if paused:
            if self._paused_wait > 0:
                self._paused_wait -= 1
                diag["phase"] = "PAUSE_WAIT"
                return "IDLE", diag
            self._paused_wait = 30
            self._paused_seen = True
            diag["phase"] = "UNPAUSE"
            return "PAUSE_TOGGLE", diag
        if self._paused_seen:
            self._paused_seen = False
            self._paused_wait = 0
        # respawn transient (type not a live piece): idle, drop plan
        if not (1 <= ptype <= 7):
            self._reset_plan()
            diag["phase"] = "RESPAWN"
            return "IDLE", diag
        key = hashlib.blake2b(
            np.ascontiguousarray(board).tobytes(),
            digest_size=12).digest() + bytes([ptype, next_type])
        if self._plan is None or key != self._plan_key:
            plan = plan_placement(board, ptype, next_type)
            if plan is None:
                # no legal placement (board full to the spawn row):
                # hard drop and let the game declare game over
                self._plan = {"phase": "DROP", "r_t": rot, "x_t": x,
                              "taps": 0, "moves": 0, "frames": 0,
                              "forced": True}
                diag["forced"] = True
            else:
                r_t, x_t, info, v1 = plan
                self._plan = {"phase": "ROTATE", "r_t": r_t,
                              "x_t": x_t, "taps": 0, "moves": 0,
                              "frames": 0, "info": info, "v1": v1,
                              "forced": False}
            self._plan_key = key
        p = self._plan
        p["frames"] += 1
        diag.update({"phase": p["phase"], "r_t": p["r_t"],
                     "x_t": p["x_t"], "plan_frames": p["frames"],
                     "v1": p.get("v1"), "forced": p["forced"]})
        # the stuck-plan fuse: force the drop whatever the position
        if p["frames"] > MAX_FRAMES_ON_PLAN and \
                p["phase"] in ("ROTATE", "MOVE"):
            p["phase"] = "DROP"
            diag["fuse"] = True
        if self._cooldown > 0:
            self._cooldown -= 1
            diag["cooldown"] = self._cooldown
            return "IDLE", diag
        ph = p["phase"]
        if ph == "ROTATE":
            if rot != p["r_t"] and p["taps"] < MAX_ROT_TAPS:
                p["taps"] += 1
                self._cooldown = ROT_COOLDOWN
                return "ROT_CW", diag
            p["phase"] = "MOVE"
            return "IDLE", diag
        if ph == "MOVE":
            if x != p["x_t"] and p["moves"] < MAX_MOVES:
                p["moves"] += 1
                self._cooldown = MOVE_COOLDOWN
                return "MOVE_R" if x < p["x_t"] else "MOVE_L", diag
            p["phase"] = "DROP"
            return "IDLE", diag
        if ph == "DROP":
            p["phase"] = "SETTLE"
            self._cooldown = DROP_SETTLE
            return "HARD_DROP", diag
        # SETTLE exhausted (or DONE): plan complete
        self._reset_plan()
        diag["phase"] = "DONE"
        return "IDLE", diag

    # ---- Policy surface (rest) ----
    def reset(self) -> None:
        self._n_calls = 0
        self._reset_plan()

    def identity(self) -> Dict[str, Any]:
        return dict(self._identity)

    def close(self) -> None:
        pass


# the vector layout lives in adapter.py (the observation builder);
# this late import avoids a module-load cycle and keeps ONE source
# of truth for the layout (cross-checked by tests/test_r64_tetrade.py)
from .adapter import TETRADE_VECTOR_LEN  # noqa: E402
