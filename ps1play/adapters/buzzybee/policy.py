"""ps1play.adapters.buzzybee.policy — the BuzzyBee built-in policy.

The R48-B bot_policy8 (tiered-margin guarantee planner with the
committed pre-danger hold), ported VERBATIM from the committed
R45-B/R48-B/R52-B scripts (scripts/r43b_planner.py,
r45b_preposition_margin.py, r48b_committed_seek.py) behind the
runtime Policy contract.  This is GAME-SPECIFIC knowledge: it models
BuzzyBee's bee physics (impulse -3072, gravity +256/f, clamp
[18,172]), the wasp's 1.5 px/f approach and its y-band [wy-13,
wy+43], and the flower seek — nothing here may be reused by another
game's plugin.

The R52-B acceptance record: the dominance recipe PASSED at every
tested cap 1800→2400 (arm B: hits 0, dodges complete, caused >= 2;
score = f − 99 EXACT across six caps; the 9th pass arrived).
Hand-written, no model, no training — training stays closed.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, Optional, Sequence

import numpy as np

from ps1play.runtime.errors import RuntimePolicyError
from ps1play.runtime.interfaces import (ActionDecision, GameObservation,
                                        Policy)

POLICY_VERSION = "1.0.0"
POLICY_NAME = "buzzybee_bot_policy8 (R52-B port, hand-written; " \
              "tiered-margin guarantee planner)"

# ---- the calibrated game constants (main.c / r35b / r43b) ------------
Y_MIN, Y_MAX = 18, 172           # player y clamp (px)
PASS_END_X = -41                 # wasp fully past the bee
ENGAGE_X = 137                   # default engage distance
WASP_SPEED = 1.5                 # px per frame (measured)
BAND_TOP_OFF, BAND_BOT_OFF = -13, 43   # the wasp's y-band offsets

# r45b tiers (verbatim)
T_ENTER_MIN = 20
TIER_PRE, TIER_IN = 8, 12
COMMIT_PROX = 8.0                # |tgt - fl_target| within one TGT_STEP

# r43b planner (verbatim)
SIM_CAP = 200                    # forward-sim horizon cap (frames)
TGT_STEP = 8                     # candidate-target quantization (px)
IMPULSE = -3072                  # the tap impulse (1/1024 px/frame)
GRAVITY = 256                    # px/frame²  (1/1024 units)
SLAM_GUARD = -3000               # never tap at pre-tap vy <= this
FLOWER_HI = 170.0                # flower seek horizon (px)
HOVER_Y = 95.0


def px(v: int) -> int:
    """C integer division by 1024 (truncation toward zero)."""
    return -((-v) // 1024) if v < 0 else v // 1024


def predict_wasp_y(ey: float, evy: float, t: int) -> float:
    """Simulate wasp y (px) for t frames with bounce off [2,142]."""
    y, v = float(ey), evy
    for _ in range(max(0, int(t))):
        y += v
        if y < 2:
            y, v = 2, abs(v)
        elif y > 142:
            y, v = 142, -abs(v)
    return y


def sim_bee_hold(by, bvy, side, target, horizon):
    """Forward-simulate the bee under the hold-controller (tap iff the
    side rule fires and bvy > -3000).  Physics (main.c, calibrated):
    impulse -3072 on the tap frame, then move (v/1024 px), then
    gravity +256/f; clamp [Y_MIN, Y_MAX].  The discrete loop climbs
    ~1.3-2.5 px MORE than the recorded rise_px calibration over one
    tap - absorbed by GM=12 plus the per-frame closed-loop replanning
    (each frame re-plans from fresh state, so model error does not
    accumulate)."""
    y, v = float(by), int(bvy)
    traj = []
    for _ in range(horizon):
        if side == "above":
            flap = y > target + 4 and v > -3000
        else:
            # below: there is NO downward impulse - any tap would rise
            # the bee back INTO the band, so the below hold is pure
            # free-fall (the residual rise already inside v included).
            flap = False
        if flap:
            v -= 3072
        y += v / 1024.0
        v += 256
        if y < Y_MIN:
            y, v = Y_MIN, max(v, 0)
        elif y > Y_MAX:
            y, v = Y_MAX, min(v, 0)
        traj.append(y)
    return traj


def danger_window(ex, horizon):
    """The contact frames: the wasp closes at 1.5 px/f; contact is
    possible only while ex(t) in [-36, 32] (the lever's window).
    Returns (t_enter, t_exit) as 1-based frame indices into the sim
    trajectory, or None when the window is already over."""
    t_enter = max(1, int((ex - 32.0) / 1.5) + 1)
    t_exit = min(horizon, int((ex + 36.0) / 1.5) + 1)
    if t_enter > t_exit:
        return None
    return t_enter, t_exit


def guaranteed_gm(traj, ey, evy, win, side, gm):
    """True iff every DANGER-window frame keeps the bee outside the
    predicted band with the gm margin (r43b `guaranteed` with the
    margin as a parameter — the R45-B tiering)."""
    for t in range(win[0] - 1, win[1]):
        y = traj[t]
        wy = predict_wasp_y(ey, evy, t + 1)
        top, bot = wy - 13, wy + 43
        if side == "above":
            if y > top - gm:
                return False
        else:
            if y < bot + gm:
                return False
    return True


def traj_control_now(by, bvy, side, target):
    if side == "above":
        return by > target + 4 and bvy > -3000
    return False          # below: never tap (any tap rises into the band)


def fl_target_of(flowers, flower_hi=FLOWER_HI):
    """The nearest active flower target (the x,y pairs in px)."""
    best = None
    for fx, fy in flowers:
        if 0 < fx <= flower_hi and (best is None or fx < best[1]):
            best = (fy + 5, fx)
    return best[0] if best else None


def plan_exit8(by, bvy, ey, evy, ex, flowers, sticky,
               tier_pre=TIER_PRE, tier_in=TIER_IN,
               t_enter_min=T_ENTER_MIN, commit_prox=COMMIT_PROX):
    """The tiered planner with the COMMITTED pre-danger hold.

    Returns (flap, target, side, planned, gm, seek_hold) where
    seek_hold marks a committed flower-proximity hold (mode flower)."""
    horizon = max(2, min(SIM_CAP, int((ex + 36.0) / 1.5) + 2))
    win = danger_window(ex, horizon)
    center = ey + 15.0
    if win is None:            # window over: wasp past, anything goes
        side = "above" if by < center else "below"
        sticky.pop("hold8", None)
        return False, float(by), side, True, tier_in, False
    in_window = win[0] <= t_enter_min
    gm = tier_in if in_window else tier_pre
    fl_target = fl_target_of(flowers)
    hold = sticky.get("hold8")
    # ---- the COMMITTED pre-danger hold ------------------------------
    if hold is not None and not in_window:
        side, tgt = hold
        traj = sim_bee_hold(by, bvy, side, tgt, horizon)
        if guaranteed_gm(traj, ey, evy, win, side, gm):
            flap = traj_control_now(by, bvy, side, tgt)
            seek_hold = bool(fl_target is not None
                             and abs(tgt - fl_target) <= commit_prox)
            return flap, float(tgt), side, True, gm, seek_hold
        sticky.pop("hold8", None)      # guarantee failed: re-enumerate
    sticky.pop("hold8", None)          # in-window: verbatim re-plan
    cands = []
    for tgt in range(Y_MIN + 4, Y_MAX - 3, TGT_STEP):
        cands.append(("above", tgt))
        cands.append(("below", tgt))
    if fl_target is not None:
        cands.sort(key=lambda c: (abs(c[1] - fl_target),
                                  0 if (c[0] == "above") == (by < center)
                                  else 1, abs(c[1] - by)))
    else:
        cands.sort(key=lambda c: (0 if (c[0] == "above") == (by < center)
                                  else 1, abs(c[1] - by)))
    for side, tgt in cands:
        traj = sim_bee_hold(by, bvy, side, tgt, horizon)
        if guaranteed_gm(traj, ey, evy, win, side, gm):
            if not in_window:
                sticky["hold8"] = (side, tgt)     # COMMIT
            flap = traj_control_now(by, bvy, side, tgt)
            seek_hold = bool(
                not in_window and fl_target is not None
                and abs(tgt - fl_target) <= commit_prox)
            return flap, float(tgt), side, True, gm, seek_hold
    # ---- bail: maximize the distance from the band center ----------
    sticky.pop("hold8", None)
    side = "above" if by < center else "below"
    if side == "above":
        tgt = max(Y_MIN + 4, Y_MIN + 10)
    else:
        tgt = min(Y_MAX - 4, Y_MAX - 10)
    flap = traj_control_now(by, bvy, side, tgt)
    return flap, float(tgt), side, False, gm, False


def bot_policy8(s, sticky, engage=200, flower_hi=FLOWER_HI,
                hover_y=HOVER_Y, tier_pre=TIER_PRE, tier_in=TIER_IN,
                t_enter_min=T_ENTER_MIN):
    """The R48-B committed-seek policy (verbatim semantics).

    s = {'by','bvy','e':[x,y,vy],'fl':[(fx,fy)x3]}; sticky = per-episode
    state dict.  Returns (flap, target, mode)."""
    by, bvy = s["by"], s["bvy"]
    ex, ey, evy = s["e"][0], s["e"][1], s["e"][2]
    if PASS_END_X < ex <= engage:
        flap, target, side, planned, gm, seek_hold = plan_exit8(
            by, bvy, ey, evy, ex, s["fl"], sticky, tier_pre, tier_in,
            t_enter_min)
        prev_side = sticky.get("side")
        flipped = (sticky.get("vy") is not None
                   and (sticky["vy"] < 0) != (evy < 0))
        sticky["vy"] = evy
        sticky["side"] = side
        sticky["planned"] = planned
        sticky["gm"] = gm
        sticky["flip"] = bool(flipped or
                              (prev_side is not None
                               and prev_side != side))
        return flap, target, "flower" if seek_hold else "dodge"
    # no-wasp phase: the COMMITTED flower seek
    sticky["side"] = None
    sticky["vy"] = None
    sticky["planned"] = None
    sticky["gm"] = None
    sticky["flip"] = False
    sticky.pop("hold8", None)          # the pass is over: uncommit
    idx = sticky.get("seek_idx8")
    flowers = s["fl"]
    if idx is not None:
        if idx >= len(flowers) or \
                not (0 < flowers[idx][0] <= flower_hi):
            idx = None                 # the committed flower is gone
    if idx is None:
        best = None
        for i, (fx, fy) in enumerate(flowers):
            if 0 < fx <= flower_hi and (best is None or fx < best[1]):
                best = (i, fx, fy)
        idx = best[0] if best else None
    sticky["seek_idx8"] = idx
    if idx is not None:
        fx, fy = flowers[idx]
        target = max(Y_MIN + 2, min(Y_MAX - 2, fy + 5))
        return (by > target + 4 and bvy > -3000), target, "flower"
    return (by > hover_y and bvy > -3000), hover_y, "hover"


class BuzzyPolicy(Policy):
    """Per-frame realization of bot_policy8 behind the Policy
    contract: each predict() decodes the 15-float observation, runs
    the verbatim planner and maps flap -> FLAP, else HOVER."""

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
        self.reset()

    @staticmethod
    def _source_sha256() -> str:
        try:
            with open(os.path.abspath(__file__), "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()
        except OSError:
            return "?"

    # ---- Policy surface ----
    def legal_actions(self) -> Sequence[str]:
        return ("HOVER", "FLAP")

    def predict(self, observation: GameObservation) -> ActionDecision:
        if not observation.valid or observation.values is None:
            raise RuntimePolicyError(
                f"refusing invalid observation (frame "
                f"{observation.frame_id}): "
                f"{observation.invalid_reason or 'marked invalid'}")
        t0 = time.perf_counter()
        v = observation.values
        if v.shape != (15,):
            raise RuntimePolicyError(
                f"buzzybee observation shape mismatch: expected "
                f"(15,), got {v.shape} (frame {observation.frame_id})")
        gs = int(round(float(v[12])))
        by, bvy = float(v[0]), float(v[1])
        ex, ey, evy = float(v[2]), float(v[3]), float(v[4])
        fl = [(float(v[5 + 2 * i]), float(v[6 + 2 * i]))
              for i in range(3)]
        score = float(v[11])
        if gs != 1:
            # outside PLAYING: idle (the adapter owns state recovery)
            diag = {"mode": "not_playing", "gs": gs,
                    "score": score, "hold": None}
            return self._decision("HOVER", diag, observation, t0)
        s = {"by": by, "bvy": bvy, "e": [ex, ey, evy], "fl": fl}
        flap, target, mode = bot_policy8(s, self._sticky)
        diag = {"mode": mode, "target": round(float(target), 1),
                "flap": bool(flap),
                "side": self._sticky.get("side"),
                "planned": self._sticky.get("planned"),
                "gm": self._sticky.get("gm"),
                "score": score}
        return self._decision("FLAP" if flap else "HOVER", diag,
                              observation, t0)

    def _decision(self, action, diag, observation, t0) \
            -> ActionDecision:
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

    def reset(self) -> None:
        self._sticky: Dict[str, Any] = {}
        self._n_calls = 0

    def identity(self) -> Dict[str, Any]:
        return dict(self._identity)

    def close(self) -> None:
        pass
