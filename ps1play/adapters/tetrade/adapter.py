"""ps1play.adapters.tetrade.adapter — the Tetrade GameAdapter (R64).

Implements the FULL runtime GameAdapter contract for Tetrade
(homebrew Tetris, the #8/R63 game) with the R63-proven sequences and
anchor map. Perception is RAM-read-based (the loop Issue #8 itself
documents; R63 precedent) — the flappy vision model does NOT
generalize and is not used. ZERO memory writes, ZERO core edits.

Observation vector (float32, 222 values — the layout is ONE source of
truth here; policy.py decodes it and the tests cross-check):

    [0:200)   board, row-major 20x10, 0/1 (struct matrix@+0, >0)
    [200:207) current piece type one-hot (types 1..7; all-zero
              during the transient respawn state)
    [207]     current rot (0..3)      [208] x      [209] y
    [210:217) NEXT piece one-hot (nextTetriminos[0].type@+896)
    [217]     score @+2276           [218] lines = single+double+
                                     triple+tetrade @+2280..2292
    [219]     level @+2304
    [220]     isGameOver @+2312      [221] isGamePaused @+2316

Episode records: the generic `pipes` progress counter carries the
LINES CLEARED for this game (registry progress_label="lines"); every
record's full game state (score, per-kind clears, level) is in the
adapter snapshot / post_advance diagnostics.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

from ps1play.runtime.errors import AdapterError, EmulatorError
from ps1play.runtime.interfaces import (ActionDecision, Frame,
                                        GameAdapter, GameObservation)

ADAPTER_VERSION = "1.0.0"

# ---- the R63 anchor map (TetradeGame, mips o32, int32 fields) --------
O_MATRIX = 0
O_TYPE, O_SHAPE, O_X, O_Y, O_ROT = 800, 804, 868, 872, 880
O_N0 = 896            # nextTetriminos[14].type@+896+92k; [0] is NEXT
O_SCORE = 2276
O_SINGLE, O_DOUBLE, O_TRIPLE, O_TETRADE = 2280, 2284, 2288, 2292
O_LEVEL = 2304
O_OVER = 2312
O_PAUSED = 2316
BOARD_H, BOARD_W = 20, 10

TETRADE_VECTOR_LEN = 200 + 7 + 3 + 7 + 5   # 222

# entry/restart frame constants (R63 probe1-proven; see module docs)
BOOT_SETTLE = (900, 60)
TITLE_START_HOLD = 120    # title -> menu (pre-game; no pause logic)
MENU_SETTLE = 240
SELECT_HOLD = 12          # B/CROSS on ">Marathon Mode<"
SELECT_SETTLE = 60
BEGIN_TAP = 4             # START tap — a 60f+ hold lands PAUSED
COUNTDOWN = 280           # PAUSE_TIME = 180f in the source
BEGIN_TAIL = 120
RESTART_TAIL = 120        # game-over screen -> continue prompt
CONTINUE_REFUSE = 4       # CIRCLE refuses the continue (source:919)
RESTART_MID = (180, 120)  # after refusal, before the menu START tap
RESTART_MENU_TAP = 4
RESTART_MENU_SETTLE = 150

SCAN_RETRY = 60
SCAN_STEP = 20
ENTRY_ATTEMPTS = 3        # R63's ledger: 3/7 boots failed the entry
                          # before the fixes — the product retries


class TetradeAdapter(GameAdapter):
    game_id = "tetrade"
    version = ADAPTER_VERSION

    FEATURE_NAMES = (
        *(f"board_{r:02d}_{c}" for r in range(BOARD_H)
          for c in range(BOARD_W)),
        *(f"type_{t}" for t in range(1, 8)),
        "rot", "x", "y",
        *(f"next_{t}" for t in range(1, 8)),
        "score", "lines", "level", "over", "paused",
    )

    def __init__(self, env, telemetry=None):
        self.env = env
        self._tel = telemetry
        # boot-scoped entry state (survives reset_episode — the
        # engine calls reset_episode before EVERY episode, but the
        # continue-screen restart decision is per-BOOT, not
        # per-episode)
        self._at_menu = False
        self._ever_started = False
        self._fresh_ready = False
        self._boot_base: Optional[int] = None
        self.reset_episode()

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

    @staticmethod
    def _i32(ram: np.ndarray, byte_off: int) -> int:
        return int(ram.view("<i4")[byte_off // 4])

    def _read_state(self, ram: Optional[np.ndarray] = None) \
            -> Dict[str, Any]:
        ram = self._snapshot() if ram is None else ram
        a = ram.view("<i4")
        b = self._base
        board = a[b // 4:b // 4 + BOARD_H * BOARD_W] \
            .reshape(BOARD_H, BOARD_W).copy()
        single = self._i32(ram, b + O_SINGLE)
        double = self._i32(ram, b + O_DOUBLE)
        triple = self._i32(ram, b + O_TRIPLE)
        tetrade = self._i32(ram, b + O_TETRADE)
        return {
            "board": board,
            "type": self._i32(ram, b + O_TYPE),
            "x": self._i32(ram, b + O_X),
            "y": self._i32(ram, b + O_Y),
            "rot": self._i32(ram, b + O_ROT),
            "next0": self._i32(ram, b + O_N0),
            "score": self._i32(ram, b + O_SCORE),
            "single": single, "double": double, "triple": triple,
            "tetrade": tetrade,
            "lines": int(single + double + triple + tetrade),
            "level": self._i32(ram, b + O_LEVEL),
            "over": self._i32(ram, b + O_OVER),
            "paused": self._i32(ram, b + O_PAUSED),
        }

    # ------------------------------------------------------------ --
    # struct location (the FIXED R63 scan: full window range, the
    # transient type=-1 respawn accepted by the secondary filter,
    # retry with a live piece for the primary signature)
    # ------------------------------------------------------------ --
    @staticmethod
    def _find_base_candidates(ram: np.ndarray,
                              allow_paused: bool = False) -> List[int]:
        a4 = ram.view("<i4")
        n = len(a4)
        wins = sliding_window_view(a4, 200)[: n - 590]
        for vmax in (7, 15):
            ok = ((wins >= 0) & (wins <= vmax)).all(axis=1)
            nz = ((wins > 0).sum(axis=1) <= 80)
            cand = np.flatnonzero(ok & nz)
            if not len(cand):
                continue
            c4 = cand * 4

            def at(off):
                return a4[(c4 + off) // 4]

            t_cur = at(O_TYPE)
            t_next = at(O_N0)
            m = (((t_cur >= 1) & (t_cur <= 7)) | (t_cur == -1)) \
                & (t_next >= 1) & (t_next <= 7) \
                & (at(O_LEVEL) == 0) & (at(O_SCORE) == 0) \
                & (at(O_OVER) == 0)
            if not allow_paused:
                m = m & (at(O_PAUSED) == 0)
            hits = c4[m]
            if len(hits):
                return [int(h) for h in hits]
        return []

    def _locate_base(self, deadline: float,
                     allow_paused: bool = False) -> int:
        """Locate the TetradeGame struct; prefers the previously seen
        base when it is still a live candidate (the struct address is
        stable within one boot — R63 restart evidence)."""
        prev = self._boot_base
        last_n = 0
        for attempt in range(SCAN_RETRY):
            ram = self._snapshot()
            bases = self._find_base_candidates(ram,
                                               allow_paused=allow_paused)
            last_n = len(bases)
            a4 = ram.view("<i4")
            live = [b for b in bases
                    if 1 <= int(a4[(b + O_TYPE) // 4]) <= 7]
            if prev is not None and prev in bases:
                return prev
            if live:
                return live[0]
            if time.time() > deadline:
                break
            self.env.run(SCAN_STEP, set())
        raise EmulatorError(
            f"TetradeGame struct not located after {SCAN_RETRY} "
            f"scans (last candidate count={last_n}) — refusing to "
            f"guess a RAM base")

    # ------------------------------------------------------------ --
    # entry / restart flows (R63 sequences, verbatim frame counts)
    # ------------------------------------------------------------ --
    def _run(self, frames: int, buttons: frozenset = frozenset()) \
            -> None:
        self.env.run(int(frames), set(buttons))

    def wait_ready(self, deadline_s: float) -> Any:
        """Boot settle + title -> menu -> ENTER Marathon -> locate the
        struct. wait_ready's completion is a VERIFIED ready state: a
        fresh Marathon is running and the struct base is located. This
        is what makes the engine's boot-retry meaningful — beetle keeps
        global emulator state, so a second in-process boot may stick
        forever at the OpenBIOS cube (observed 2026-11-01; recorded in
        the #5 worklog) — the adapter DETECTS that by failing the
        scan, and the engine re-boots a fresh core."""
        t0 = time.time()
        try:
            self._run(BOOT_SETTLE[0])
            self._run(BOOT_SETTLE[1])
            self._run(TITLE_START_HOLD, frozenset({"START"}))
            self._run(MENU_SETTLE)
            consumed = self._entry_sequence()
            # the scan IS the verification: a located struct with a
            # live piece = the game really booted and Marathon runs
            self._base = self._locate_base(
                min(time.time() + max(5.0,
                    SCAN_RETRY * SCAN_STEP / 100.0),
                    t0 + deadline_s))
            self._boot_base = self._base
            self._at_menu = False
            self._ever_started = True
            self._fresh_ready = True
            st = self._read_state()
            self._prev_lines = int(st["lines"])
            self._prev_score = int(st["score"])
            self._lines = int(st["lines"])
            self._score = int(st["score"])
            self._last_diag = self._state_diag(
                st, base=self._base, fresh=True, phase="wait_ready")
            if self._tel is not None:
                self._tel.emit("tetrade_ready", base=self._base,
                               hex_base=hex(self._base),
                               start_frames=int(consumed),
                               score=int(st["score"]),
                               lines=int(st["lines"]))
            if time.time() - t0 > deadline_s:
                raise EmulatorError(
                    f"tetrade ready flow exceeded deadline "
                    f"({deadline_s}s)")
            return True
        except EmulatorError:
            raise
        except Exception as e:
            raise EmulatorError(f"tetrade ready flow failed: "
                                f"{type(e).__name__}: {e}")

    def _continue_refusal(self) -> int:
        """The R63 restart prefix: on the continue screen, refuse with
        CIRCLE and settle back to the menu. Returns frames used."""
        self._run(RESTART_TAIL)
        self._run(CONTINUE_REFUSE, frozenset({"A"}))
        self._run(RESTART_MID[0])
        self._run(RESTART_MID[1])
        self._run(RESTART_MENU_TAP, frozenset({"START"}))
        self._run(RESTART_MENU_SETTLE)
        return (RESTART_TAIL + CONTINUE_REFUSE + sum(RESTART_MID)
                + RESTART_MENU_TAP + RESTART_MENU_SETTLE)

    def _entry_sequence(self) -> int:
        """Menu -> Marathon -> countdown done. Returns frames used."""
        self._run(SELECT_HOLD, frozenset({"B"}))
        self._run(SELECT_SETTLE)
        self._run(BEGIN_TAP, frozenset({"START"}))
        self._run(COUNTDOWN)
        self._run(BEGIN_TAP, frozenset({"START"}))
        self._run(BEGIN_TAIL)
        return (SELECT_HOLD + SELECT_SETTLE + BEGIN_TAP + COUNTDOWN
                + BEGIN_TAP + BEGIN_TAIL)

    def _recover_to_menu(self) -> int:
        """State-driven best-effort recovery to a clean MENU state
        (used both before an entry and after a failed attempt):
        whatever the game is doing — mid-play, paused (the R63
        key-repeat trap), on the game-over/continue screen — legally
        finish it (hard drops / unpause taps), refuse the continue
        with CIRCLE, and settle back to the menu. Returns frames used
        (0 when no struct is findable — the caller then just retries
        the entry from wherever the menus are)."""
        used = 0
        base = self._boot_base
        if base is None:
            try:
                base = self._locate_base(
                    time.time() + 3.0, allow_paused=True)
            except EmulatorError:
                return 0
        self._base = base
        try:
            st = self._read_state()
        except EmulatorError:
            return used
        if not st["over"]:
            used += self._force_game_over()
        used += self._continue_refusal()
        self._ever_started = True
        self._at_menu = True
        return used

    def _force_game_over(self, cap_frames: int = 3000) -> int:
        """Legally END a still-running game with REAL input only: hard
        drop every live piece (UP), unpause if needed, wait for the
        natural spawn-overlap game over. Used when the previous
        episode ended ALIVE at its budget (the engine stops mid-game;
        the continue screen only exists after a game over). Returns
        the frames consumed; raises EmulatorError past the cap."""
        if self._boot_base is None:
            return 0
        self._base = self._boot_base
        used = 0
        while used < cap_frames:
            st = self._read_state()
            if st["over"]:
                return used
            if st["paused"]:
                self._run(BEGIN_TAP, frozenset({"START"}))
                self._run(30)
                used += BEGIN_TAP + 30
            elif 1 <= st["type"] <= 7:
                self._run(2, frozenset({"UP"}))
                self._run(24)
                used += 26
            else:
                self._run(20)
                used += 20
        raise EmulatorError(
            f"could not reach a natural game over within {cap_frames} "
            f"frames of legal hard-drops — refusing to restart from "
            f"an unknown state")

    def start_episode(self, seed_k: int) -> int:
        """Begin one episode. Episode 1 follows a successful
        wait_ready directly (the game is ALREADY in a verified fresh
        Marathon — only the counters reset). Episodes >= 2 recover to
        the menu (legally finishing any running game), re-enter
        Marathon and re-locate the struct, retrying up to
        ENTRY_ATTEMPTS times (R63's failed-entry ledger, automated).
        seed_k is RECORDED but does NOT control the game: the
        zero-writes rule forbids seeding the game's internal RNG.
        Returns the emulator frames consumed."""
        consumed = 0
        if self._fresh_ready and self._boot_base is not None:
            # wait_ready just verified this exact state — do not
            # double-enter; only reset the per-episode counters
            self._base = self._boot_base
            st = self._read_state()
            self._prev_lines = int(st["lines"])
            self._prev_score = int(st["score"])
            self._lines = int(st["lines"])
            self._score = int(st["score"])
            self._last_diag = self._state_diag(st, base=self._base,
                                               fresh=True,
                                               phase="episode_start")
            if self._tel is not None:
                self._tel.emit("tetrade_episode_start",
                               seed_k=int(seed_k), base=self._base,
                               hex_base=hex(self._base),
                               start_frames=0, reused_ready=True,
                               score=int(st["score"]),
                               lines=int(st["lines"]))
            self._fresh_ready = False
            return 0
        self._base = None
        last_err: Optional[EmulatorError] = None
        for attempt in range(ENTRY_ATTEMPTS):
            try:
                if not self._at_menu:
                    # NOT at a clean menu (a previous episode ran on
                    # this boot, or a previous attempt wedged the
                    # game): recover to the menu first — legally
                    # finish any running game, refuse the continue
                    consumed += self._recover_to_menu()
                consumed += self._entry_sequence()
                self._at_menu = False
                self._ever_started = True
                self._base = self._locate_base(
                    time.time()
                    + max(5.0, SCAN_RETRY * SCAN_STEP / 100.0))
                self._boot_base = self._base
                st = self._read_state()
                self._prev_lines = int(st["lines"])
                self._prev_score = int(st["score"])
                self._lines = int(st["lines"])
                self._score = int(st["score"])
                self._last_diag = self._state_diag(
                    st, base=self._base, fresh=True,
                    entry_attempt=attempt)
                if self._tel is not None:
                    self._tel.emit(
                        "tetrade_episode_start", seed_k=int(seed_k),
                        base=self._base, hex_base=hex(self._base),
                        start_frames=int(consumed),
                        entry_attempt=attempt,
                        score=int(st["score"]),
                        lines=int(st["lines"]))
                return int(consumed)
            except EmulatorError as e:
                last_err = e
                if self._tel is not None:
                    self._tel.emit("tetrade_entry_retry",
                                   attempt=attempt,
                                   error=str(e)[:200])
                consumed += self._recover_to_menu()
        raise last_err if last_err is not None else EmulatorError(
            "tetrade entry failed")

    def reset_episode(self) -> None:
        """Drop ALL per-episode state (counters, struct base). The
        boot-scoped entry flags (_at_menu/_ever_started) survive by
        design — see __init__."""
        self._base: Optional[int] = None
        self._prev_lines = 0
        self._prev_score = 0
        self._lines = 0
        self._score = 0
        self._presses = 0
        self._steps = 0
        self._last_diag: Dict[str, Any] = {}

    # ------------------------------------------------------------ --
    # observation
    # ------------------------------------------------------------ --
    @staticmethod
    def _state_diag(st: Dict[str, Any], **extra) -> Dict[str, Any]:
        return {
            "type": int(st["type"]), "x": int(st["x"]),
            "y": int(st["y"]), "rot": int(st["rot"]),
            "next": int(st["next0"]), "score": int(st["score"]),
            "lines": int(st["lines"]), "level": int(st["level"]),
            "over": bool(st["over"]), "paused": bool(st["paused"]),
            "filled": int((st["board"] > 0).sum()),
            "single": int(st["single"]), "double": int(st["double"]),
            "triple": int(st["triple"]), "tetrade": int(st["tetrade"]),
            **extra,
        }

    def observe(self, frame: Frame) -> GameObservation:
        """One frame -> the 222-value RAM observation (layout in the
        module docstring). All legitimate game states (respawn
        transient, pause, game over) are IN-vector; invalid is only a
        hard failure (RAM read / struct lost)."""
        try:
            if self._base is None:
                raise AdapterError(
                    "observe before start_episode (no struct base)")
            st = self._read_state()
            v = np.zeros(TETRADE_VECTOR_LEN, dtype=np.float32)
            v[:200] = (st["board"] > 0).astype(np.float32).ravel()
            t = int(st["type"])
            if 1 <= t <= 7:
                v[200 + t - 1] = 1.0
            v[207] = float(st["rot"])
            v[208] = float(st["x"])
            v[209] = float(st["y"])
            nt = int(st["next0"])
            if 1 <= nt <= 7:
                v[210 + nt - 1] = 1.0
            v[217] = float(st["score"])
            v[218] = float(st["lines"])
            v[219] = float(st["level"])
            v[220] = 1.0 if st["over"] else 0.0
            v[221] = 1.0 if st["paused"] else 0.0
            diag = self._state_diag(st)
            self._lines = int(st["lines"])
            self._score = int(st["score"])
            self._last_diag = diag
            return GameObservation(
                values=v, frame_seq=frame.seq, frame_id=frame.frame_id,
                timestamp=frame.timestamp, valid=True,
                diagnostics=diag)
        except (AdapterError, EmulatorError):
            raise                     # typed failures stay typed
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
        if decision.action != "IDLE":
            self._presses += 1

    # ------------------------------------------------------------ --
    # actions
    # ------------------------------------------------------------ --
    def legal_actions(self) -> Sequence[str]:
        return ("IDLE", "ROT_CW", "MOVE_L", "MOVE_R", "HARD_DROP",
                "PAUSE_TOGGLE")

    def action_to_buttons(self, action: str) -> frozenset:
        """The R63 input map (this stack's libretro naming): A =
        CIRCLE (rotate CW), B = CROSS, UP = hard drop, START toggles
        pause. Every action is ONE frame of buttons (the runtime's
        one-frame-pulse contract)."""
        if action == "IDLE":
            return frozenset()
        if action == "ROT_CW":
            return frozenset({"A"})
        if action == "MOVE_L":
            return frozenset({"LEFT"})
        if action == "MOVE_R":
            return frozenset({"RIGHT"})
        if action == "HARD_DROP":
            return frozenset({"UP"})
        if action == "PAUSE_TOGGLE":
            return frozenset({"START"})
        raise AdapterError(f"unmapped action {action!r}")

    # ------------------------------------------------------------ --
    # post-advance scoring / terminal
    # ------------------------------------------------------------ --
    def post_advance(self, frame: Frame) -> Dict[str, Any]:
        """Read the counters AFTER the action frame: a line-clear
        event is any increase of single+double+triple+tetrade; the
        terminal is isGameOver (spawn overlap)."""
        st = self._read_state()
        lines = int(st["lines"])
        score = int(st["score"])
        line_event = lines > self._prev_lines
        score_delta = score - self._prev_score
        self._prev_lines = lines
        self._prev_score = score
        self._lines = lines
        self._score = score
        terminal = bool(st["over"])
        diag = self._state_diag(st)
        self._last_diag = diag
        return {
            "pipe_passed": bool(line_event),
            "pipes": lines,             # generic progress = LINES
            "line_event": bool(line_event),
            "score": score, "score_delta": score_delta,
            "terminal": terminal,
            "death_reason": "game_over" if terminal else None,
            "paused": bool(st["paused"]),
            **diag,
        }

    # ------------------------------------------------------------ --
    # misc
    # ------------------------------------------------------------ --
    def snapshot(self) -> Dict[str, Any]:
        try:
            d = dict(self._last_diag)
            d["lines"] = int(self._lines)
            d["score"] = int(self._score)
            d["presses"] = int(self._presses)
            d["steps"] = int(self._steps)
            d["base"] = self._base
            return d
        except Exception:
            return {}

    def episode_stats(self) -> Dict[str, int]:
        """Generic counters: `pipes` = lines cleared (the registry's
        progress_label for this game), `actions` = real button
        presses, `decisions` = policy decisions."""
        return {"pipes": int(self._lines),
                "actions": int(self._presses),
                "decisions": int(self._steps)}
