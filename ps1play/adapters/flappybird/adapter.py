"""ps1play.adapters.flappybird — the FlappyBirdPSX GameAdapter (R62).

Wires the proven components into the runtime's GameAdapter contract
WITHOUT duplicating any of them:

  * frame downsample: ps1play.learn.games._small_rgb (the exact
    320x240 -> 60x80x3 area average every R61 record used)
  * perception: ps1play.learn.visual_only BirdObserverV7 +
    GapTrackerV7 + features_flappy_v7 (AST-guarded module, frozen
    semantics)
  * state machine: the EXACT R61 deployed loop semantics — vector
    BEFORE the action-history update, history AFTER it
    (build_vector / advance_history mirror r61e_deploy_loop, whose
    behavior is regression-pinned)
  * scoring: ps1play.runtime.scoring.PassageCounter (equivalence-tested
    against scripts/r57_lib)
  * game surface: FlappyEnv reach_ready / start_episode / game_over

The adapter owns ALL per-episode state and drops it in
reset_episode() — no observer/tracker/counter state can leak across
episodes.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from ps1play.runtime.errors import AdapterError, EmulatorError
from ps1play.runtime.interfaces import (ActionDecision, Frame,
                                        GameAdapter, GameObservation)
from ps1play.runtime.scoring import PassageCounter

ADAPTER_VERSION = "1.0.0"


class FlappyBirdAdapter(GameAdapter):
    game_id = "flappybird"
    version = "1.0.0"

    # The 10-feature v7 layout (the frozen model's input contract).
    FEATURE_NAMES = ("by", "vy", "gc", "dx", "g0", "g1",
                     "flap_run", "since_flap", "last_gc", "since_gap")

    def __init__(self, env, telemetry=None):
        self.env = env
        self._tel = telemetry
        self.reset_episode()
        self.episode_frames_started: Optional[int] = None
        self._last_obs_diag: Dict[str, Any] = {}
        self._pending_gc: Optional[float] = None

    # ---- lifecycle ----
    def wait_ready(self, deadline_s: float) -> Any:
        """Boot flow -> the GET READY screen (anchor saved pre-seed)."""
        t0 = time.time()
        try:
            self.env.reach_ready()
        except Exception as e:
            raise EmulatorError(
                f"flappy ready flow failed: {type(e).__name__}: {e}")
        if time.time() - t0 > deadline_s:
            raise EmulatorError(
                f"flappy ready flow exceeded deadline ({deadline_s}s)")
        return True

    def start_episode(self, seed_k: int) -> int:
        """Restore the ready anchor -> k idle frames -> the r15 start
        sequence (B 3f -> 4f idle -> B 2f -> 4f idle)."""
        self.reset_episode()
        try:
            consumed = self.env.start_episode(int(seed_k))
        except Exception as e:
            raise EmulatorError(
                f"episode start failed (k={seed_k}): "
                f"{type(e).__name__}: {e}")
        self.episode_frames_started = consumed
        if self._tel is not None:
            self._tel.emit("episode_start", seed_k=int(seed_k),
                           start_frames=int(consumed))
        return int(consumed)

    def reset_episode(self) -> None:
        """Fresh perception + counters; zero state carried over."""
        from ps1play.learn import visual_only as VO  # noqa: PLC0415
        self._observer = VO.BirdObserverV7()
        self._tracker = VO.GapTrackerV7()
        self._since_flap = 99
        self._flap_run = 0
        self._last_gc = -1.0
        self._since_gap = 40
        self._prev_action: Optional[str] = None
        self._pending_gc = None
        self._pending_gc_raw = None
        self._passages = PassageCounter()
        self._flaps = 0
        self._steps = 0
        self.episode_frames_started = None
        self._last_obs_diag = {}

    # ---- observation ----
    def observe(self, frame: Frame) -> GameObservation:
        """One small frame -> the RAW v7 10-vector (normalization is
        INSIDE the ONNX graph — the vector here is unnormalized by
        contract)."""
        try:
            from ps1play.learn.games import _small_rgb  # noqa: PLC0415
            small = _small_rgb(frame.rgb)
            x, pending = self._build_vector(small)
            self._pending_gc = pending
            diag = {
                "bird_y": float(x[0]), "vy": float(x[1]),
                "gap_center": float(x[2]), "gap_dx": float(x[3]),
                "flap_run": int(x[6]), "since_flap": int(x[7]),
                "last_gc": float(x[8]), "since_gap": int(x[9]),
                "bird_detected": bool(x[0] >= 0),
                "gap_locked": bool(x[8] >= 0),
                "small_shape": list(small.shape),
            }
            self._last_obs_diag = diag
            return GameObservation(
                values=np.asarray(x, dtype=np.float32),
                frame_seq=frame.seq, frame_id=frame.frame_id,
                timestamp=frame.timestamp, valid=True,
                diagnostics=diag)
        except AdapterError:
            raise
        except Exception as e:
            # hard failure: NEVER hand a malformed vector to the model
            return GameObservation(
                values=None, frame_seq=frame.seq, frame_id=frame.frame_id,
                timestamp=frame.timestamp, valid=False,
                invalid_reason=f"{type(e).__name__}: {e}",
                diagnostics=self._last_obs_diag)

    def _build_vector(self, small: np.ndarray):
        """The exact R61 deployed state machine (r61e_deploy_loop
        semantics: vector BEFORE the history update)."""
        x = np.asarray(self._vector_from_small(small), dtype=np.float32)
        if x.shape != (10,) or not np.all(np.isfinite(x)):
            raise AdapterError(
                f"observation builder produced an invalid vector: "
                f"shape={x.shape} finite="
                f"{bool(np.all(np.isfinite(x)))}")
        return x, self._pending_gc_raw

    def _vector_from_small(self, small: np.ndarray):
        from ps1play.learn import visual_only as VO  # noqa: PLC0415
        by_obs, vy_obs = self._observer.step(small, self._prev_action)
        gc_raw, dx, g0, g1, _b = VO._flappy_gap_raw2(small,
                                                     by_hint=by_obs)
        gc_obs = self._tracker.step((gc_raw, g0, g1, dx + 160.0))
        self._pending_gc_raw = gc_obs
        x = VO.features_flappy_v7(
            small, by_obs, vy_obs, since_flap=self._since_flap,
            last_gc=self._last_gc, since_gap=self._since_gap,
            flap_run=self._flap_run, gc_obs=gc_obs)
        return x

    def note_action(self, decision: ActionDecision,
                    observation: GameObservation) -> None:
        """The exact deployed history update (AFTER the decision,
        BEFORE the next observation): since_flap/flap_run/last_gc/
        since_gap."""
        action = decision.action
        pending = self._pending_gc
        if action == "FLAP":
            self._since_flap = 0
            self._flap_run = min(self._flap_run + 1, 9)
            self._flaps += 1
        else:
            self._since_flap = min(self._since_flap + 1, 99)
            self._flap_run = 0
        if pending is not None:
            self._last_gc = float(pending)
            self._since_gap = 0
        else:
            self._since_gap = min(self._since_gap + 1, 40)
        self._prev_action = action
        self._steps += 1
        self._pending_gc = None

    # ---- actions ----
    def legal_actions(self) -> Sequence[str]:
        return ("HOVER", "FLAP")

    def action_to_buttons(self, action: str) -> frozenset:
        """The legal input contract: FLAP = B (Cross) held for exactly
        the one decision frame (the 2-frame pulse semantics of the game
        are satisfied by the engine's own 1-frame decisions — the exact
        R61 record semantics); HOVER = no input."""
        if action == "FLAP":
            return frozenset({"B"})
        if action == "HOVER":
            return frozenset()
        raise AdapterError(f"unmapped action {action!r}")

    # ---- post-advance scoring/terminal ----
    def post_advance(self, frame: Frame) -> Dict[str, Any]:
        """Full-res scoring on the frame AFTER the action: passage
        counting + terminal detection (the beige GAME OVER panel)."""
        nf = frame.rgb
        from ps1play.learn.perception import (  # noqa: PLC0415
            flappy_bird_y, flappy_gap_target_r15, flappy_green_mask)
        by, _n = flappy_bird_y(nf)
        _g, bx = flappy_gap_target_r15(
            flappy_green_mask(nf), by if by is not None else -1)
        passed = self._passages.fire(bx, step=self._steps)
        terminal = bool(self.env.game_over(nf))
        return {
            "pipe_passed": passed,
            "pipes": int(self._passages.count),
            "passage_step": (self._passages.events[-1]
                             if passed else None),
            "terminal": terminal,
            "death_reason": "game_over" if terminal else None,
            "bird_y_fullres": by,
            "band_x": bx,
        }

    # ---- misc ----
    @property
    def passages(self) -> int:
        return int(self._passages.count)

    @property
    def flaps(self) -> int:
        return int(self._flaps)

    @property
    def steps(self) -> int:
        return int(self._steps)

    def snapshot(self) -> Dict[str, Any]:
        try:
            d = dict(self._last_obs_diag)
            d["pipes"] = self._passages.count
            d["steps"] = self._steps
            return d
        except Exception:
            return {}

    def episode_stats(self) -> Dict[str, int]:
        return {"pipes": int(self._passages.count),
                "actions": int(self._flaps),
                "decisions": int(self._steps)}
