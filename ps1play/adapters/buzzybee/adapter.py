"""ps1play.adapters.buzzybee.adapter — the BuzzyBee GameAdapter (R65).

Implements the FULL runtime GameAdapter contract for BuzzyBee with the
R23–R52-proven anchors and sequences.  Perception is RAM-read-based
(the loop Issue #6 documents; R63/R64 precedent) — read-only, zero
writes, zero core edits.

Observation vector (float32, 15 values — ONE source of truth here;
policy.py decodes it and the tests cross-check):

    [0]  by    bee y (px, 20.5-space screen coords, clamped 18..172)
    [1]  bvy   bee y velocity (raw 1/1024 px/frame units)
    [2]  ex    wasp x (px; closes at 1.5 px/f from the right)
    [3]  ey    wasp y (px)
    [4]  evy   wasp y velocity (px/f)
    [5..10]    flower[0..2] x, y (px; inactive flowers carry x<=0)
    [11] score @0x8005883C (+1 per frame during play)
    [12] gs    gameState @0x80058830 (0 title, 1 playing, 99 select)
    [13] hp    player health @0x8005EF48
    [14] best  best score @0x80058838

Episode records: the generic `pipes` progress counter carries the
SCORE for this game (registry progress_label="score"); hp/best are in
the observation and the adapter snapshot.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional, Sequence

import numpy as np

from ps1play.runtime.errors import AdapterError, EmulatorError
from ps1play.runtime.interfaces import (ActionDecision, Frame,
                                        GameAdapter, GameObservation)

ADAPTER_VERSION = "1.0.0"

# ---- the VERIFIED anchor map (capsule + r35b header) -----------------
GS = 0x80058830          # gameState: 0 title, 1 playing, 99 select
BEST = 0x80058838
SCORE = 0x8005883C
HITF, HITE = 0x80058840, 0x80058844
INPUT_PAD, INPUT_TRIG, INPUT_HELD = 0x8005881C, 0x80058820, 0x80058824
PLAYER, ENEMY = 0x8005EDC0, 0x8005EB7C
FLOWERS, ROCKS = 0x8005EBA0, 0x8005F55C
HEALTH, TIMER = 0x8005EF48, 0x8005F548
FLOWER_STRIDE = 0x24
N_FLOWERS = 3
RAM_BASE = 0x80000000

# the calibrated geometry (main.c, r35b header — the policy's constants)
Y_MIN, Y_MAX = 18, 172           # player y clamp (px)
FACTOR = 1024                    # position fixed-point factor

OBS_LEN = 15

BOOT_SETTLE = 900                # the R52 checkpoint recipe settle
START_HOLD = 15                  # title START hold frames
START_POLL = 600                 # max wait for gs 0 -> 1
GS_TITLE, GS_PLAYING, GS_SELECT, GS_OVER = 0, 1, 99, 5


def px(v: int) -> int:
    """C integer division by 1024 (truncation toward zero)."""
    return -((-v) // FACTOR) if v < 0 else v // FACTOR


class BuzzyBeeAdapter(GameAdapter):
    game_id = "buzzybee"
    version = ADAPTER_VERSION

    FEATURE_NAMES = ("by", "bvy", "ex", "ey", "evy",
                     "f0x", "f0y", "f1x", "f1y", "f2x", "f2y",
                     "score", "gs", "hp", "best")

    def __init__(self, env, telemetry=None):
        self.env = env
        self._tel = telemetry
        self._score = 0
        self._flaps = 0
        self._steps = 0
        self._last_diag: Dict[str, Any] = {}
        self._ready_seen = False
        # the flap press pipeline (see action_to_buttons): the proven
        # r45-B press is B held EXACTLY 2 frames, then 1 idle frame
        # (the game's pad read needs the 2-frame hold; the idle frame
        # guarantees the next press has an edge).  The runtime loop is
        # 1 decision = 1 frame, so the adapter pipelines the tail of
        # each press across the following decisions.
        self._press_hold = 0
        self._force_idle = 0

    # ------------------------------------------------------------ --
    # RAM access (read-only; the only emulator primitives used are
    # env.run(frames, buttons) and env.p.mem.snapshot())
    # ------------------------------------------------------------ --
    def _snapshot(self) -> np.ndarray:
        try:
            return np.frombuffer(bytes(self.env.p.mem.snapshot()),
                                 dtype=np.uint8)
        except Exception as e:
            raise EmulatorError(f"RAM snapshot failed: "
                                f"{type(e).__name__}: {e}")

    def _i32(self, ram: np.ndarray, va: int) -> int:
        return int(ram.view("<i4")[(va - RAM_BASE) // 4])

    def _u32(self, ram: np.ndarray, va: int) -> int:
        return int(ram.view("<u4")[(va - RAM_BASE) // 4])

    def _obj(self, ram: np.ndarray, base: int) -> Dict[str, int]:
        """One game entity (fn/idx/tf + pos/vel) — the r35b layout."""
        return {"y": self._i32(ram, base + 0x0C),
                "x": self._i32(ram, base + 0x10),
                "xv": self._i32(ram, base + 0x14),
                "yv": self._i32(ram, base + 0x18)}

    def _read_state(self, ram: Optional[np.ndarray] = None) \
            -> Dict[str, Any]:
        ram = self._snapshot() if ram is None else ram
        p = self._obj(ram, PLAYER)
        e = self._obj(ram, ENEMY)
        fl = [self._obj(ram, FLOWERS + FLOWER_STRIDE * i)
              for i in range(N_FLOWERS)]
        return {"gs": self._i32(ram, GS),
                "best": self._i32(ram, BEST),
                "score": self._i32(ram, SCORE),
                "hp": self._i32(ram, HEALTH),
                "p": p, "e": e, "fl": fl}

    def _run(self, frames: int, buttons: frozenset = frozenset()) \
            -> None:
        try:
            self.env.run(int(frames), set(buttons))
        except Exception as e:
            raise EmulatorError(f"env.run failed: "
                                f"{type(e).__name__}: {e}")

    # ------------------------------------------------------------ --
    # lifecycle
    # ------------------------------------------------------------ --
    def wait_ready(self, deadline_s: float) -> Any:
        """Boot flow: settle -> the title (gs==0) -> START -> PLAYING
        (gs==1, VERIFIED ready state)."""
        t0 = time.time()
        try:
            self._run(BOOT_SETTLE)
            st = self._read_state()
            if st["gs"] == GS_TITLE:
                self._run(START_HOLD, frozenset({"START"}))
            # poll for the verified ready state
            while True:
                st = self._read_state()
                if st["gs"] == GS_PLAYING:
                    break
                if st["gs"] == GS_TITLE and time.time() - t0 < \
                        deadline_s:
                    self._run(START_HOLD, frozenset({"START"}))
                if time.time() - t0 > deadline_s:
                    raise EmulatorError(
                        f"buzzybee ready flow timed out at "
                        f"gs={st['gs']} (deadline {deadline_s}s)")
                self._run(30)
        except EmulatorError:
            raise
        except Exception as e:
            raise EmulatorError(f"buzzybee ready flow failed: "
                                f"{type(e).__name__}: {e}")
        self._ready_seen = True
        self._score = int(st["score"])
        self._last_diag = {"gs": st["gs"], "score": st["score"],
                           "hp": st["hp"]}
        if self._tel is not None:
            self._tel.emit("buzzybee_ready", gs=st["gs"],
                           score=int(st["score"]), hp=int(st["hp"]))
        if time.time() - t0 > deadline_s:
            raise EmulatorError(
                f"buzzybee ready flow exceeded deadline ({deadline_s}s)")
        return True

    def start_episode(self, seed_k: int) -> int:
        """Episode = the live PLAYING state (seed_k is labeling-only:
        the zero-writes rule never seeds the game RNG).  State-driven
        recovery: gs=5 (the game-over screen, R65-measured) auto-
        returns to the title within ~400 frames; gs=0 takes START."""
        self._steps = 0
        self._flaps = 0
        self._press_hold = 0
        self._force_idle = 0
        st = self._read_state()
        if st["gs"] == GS_OVER:
            self._wait_gs(GS_TITLE, 700)
        if self._read_state()["gs"] == GS_TITLE:
            self._run(START_HOLD, frozenset({"START"}))
            self._wait_gs(GS_PLAYING, START_POLL)
            st = self._read_state()
        if st["gs"] != GS_PLAYING:
            raise EmulatorError(
                f"buzzybee episode start failed: gs={st['gs']} "
                "(not PLAYING after recovery)")
        self._score = int(st["score"])
        if self._tel is not None:
            self._tel.emit("buzzybee_episode_start",
                           seed_k=int(seed_k), start_frames=0)
        return 0

    def _wait_gs(self, gs_wanted: int, max_frames: int) -> None:
        for _ in range(max_frames // 30):
            if self._read_state()["gs"] == gs_wanted:
                return
            self._run(30)
        if self._read_state()["gs"] != gs_wanted:
            raise EmulatorError(
                f"buzzybee wait for gs={gs_wanted} timed out")

    def reset_episode(self) -> None:
        self._steps = 0
        self._flaps = 0
        self._press_hold = 0
        self._force_idle = 0

    # ------------------------------------------------------------ --
    # observation
    # ------------------------------------------------------------ --
    def observe(self, frame: Frame) -> GameObservation:
        try:
            st = self._read_state()
            p, e = st["p"], st["e"]
            x = np.zeros(OBS_LEN, dtype=np.float32)
            x[0] = px(p["y"]); x[1] = float(p["yv"])
            x[2] = px(e["x"]); x[3] = px(e["y"])
            x[4] = px(e["yv"])
            for i, f in enumerate(st["fl"]):
                x[5 + 2 * i] = px(f["x"])
                x[6 + 2 * i] = px(f["y"])
            x[11] = float(st["score"])
            x[12] = float(st["gs"])
            x[13] = float(st["hp"])
            x[14] = float(st["best"])
            self._score = int(st["score"])
            self._last_diag = {"by": float(x[0]),
                               "bvy": float(x[1]),
                               "ex": float(x[2]), "ey": float(x[3]),
                               "score": st["score"], "gs": st["gs"],
                               "hp": st["hp"]}
            return GameObservation(
                values=x, frame_seq=frame.seq,
                frame_id=frame.frame_id, timestamp=frame.timestamp,
                valid=True, diagnostics=dict(self._last_diag))
        except (AdapterError, EmulatorError):
            raise
        except Exception as e:
            return GameObservation(
                values=None, frame_seq=frame.seq,
                frame_id=frame.frame_id, timestamp=frame.timestamp,
                valid=False, invalid_reason=f"{type(e).__name__}: {e}",
                diagnostics=dict(self._last_diag))

    def note_action(self, decision: ActionDecision,
                    observation: GameObservation) -> None:
        """Count real button presses (every non-IDLE action maps to
        exactly one button frame)."""
        self._steps += 1
        if decision.action != "HOVER":
            self._flaps += 1

    # ------------------------------------------------------------ --
    # actions
    # ------------------------------------------------------------ --
    def legal_actions(self) -> Sequence[str]:
        return ("HOVER", "FLAP")

    def action_to_buttons(self, action: str) -> frozenset:
        """FLAP = the tap button (libretro B = CROSS) as the proven
        r45-B press: B held EXACTLY 2 frames, then 1 forced idle frame
        (the pad read needs the 2-frame hold; the idle frame gives the
        next press its edge).  The runtime loop is 1 decision = 1
        frame, so the press tail is pipelined across decisions — one
        press = one impulse, exactly the physics the policy models.
        HOVER = no input."""
        if action not in ("FLAP", "HOVER"):
            raise AdapterError(f"unmapped action {action!r}")
        if self._press_hold > 0:
            self._press_hold -= 1
            return frozenset({"B"})      # the press's 2nd frame
        if self._force_idle > 0:
            self._force_idle -= 1
            return frozenset()           # the post-press edge frame
        if action == "FLAP":
            self._press_hold = 1
            self._force_idle = 1
            return frozenset({"B"})
        return frozenset()

    # ------------------------------------------------------------ --
    # post-advance scoring/terminal
    # ------------------------------------------------------------ --
    def post_advance(self, frame: Frame) -> Dict[str, Any]:
        st = self._read_state()
        gs, hp, score = int(st["gs"]), int(st["hp"]), int(st["score"])
        terminal = gs != GS_PLAYING
        reason = None
        if gs == GS_OVER:
            reason = "game_over"       # gs=5: hp depleted -> game over
        elif gs != GS_PLAYING:
            reason = f"game_state_{gs}"
        passed = score > self._score     # +1/frame during play
        self._score = score
        return {"pipe_passed": passed,
                "pipes": score,
                "terminal": terminal,
                "death_reason": reason,
                "gs": gs, "hp": hp, "score": score}

    # ---- misc ----
    @property
    def score(self) -> int:
        return int(self._score)

    @property
    def flaps(self) -> int:
        return int(self._flaps)

    @property
    def steps(self) -> int:
        return int(self._steps)

    def snapshot(self) -> Dict[str, Any]:
        try:
            d = dict(self._last_diag)
            d["score"] = self._score
            d["steps"] = self._steps
            return d
        except Exception:
            return {}

    def episode_stats(self) -> Dict[str, int]:
        return {"pipes": int(self._score),
                "actions": int(self._flaps),
                "decisions": int(self._steps)}
