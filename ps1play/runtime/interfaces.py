"""ps1play.runtime.interfaces — the R62 runtime contracts.

Five interfaces compose the autonomous game-playing loop:

    FrameSource  -- latest emulator frame, ordered, staleness-tagged
    GameAdapter  -- game-specific perception + state + action mapping
    Policy       -- the frozen decision function (the R61 ONNX consumer)
    Controller   -- the ONLY sender of legal controller inputs
    Emulator     -- boot / advance / capture / teardown of the core

Plus the value objects that flow between them (Frame, GameObservation,
ActionDecision, EpisodeResult). The contracts are deliberately small;
the FlappyBird adapter, the deployment policy package, and the beetle
session implement them WITHOUT the runtime knowing any game detail.

Frame/action association contract (tested):

    observation frame N (seq=n)  ->  decision N  ->  controller input N
        ->  emulator advances exactly one frame  ->  frame N+1 (seq=n+1)

The engine enforces this: a controller send must name the frame the
decision was made on, and the next captured frame must be strictly
newer (larger emulator frame count).
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .errors import ControllerError, FrameError

# ------------------------------------------------------------------
# value objects
# ------------------------------------------------------------------


@dataclass
class Frame:
    """One captured emulator frame.

    seq: capture sequence number (monotonic per FrameSource).
    emulator_frame_count: the core's own rendered-frame counter at
        capture time — the authoritative ordering/staleness signal.
    rgb: full-resolution (H, W, 3) uint8.
    timestamp: wall-clock time.time() at capture.
    stale: True when the emulator had not rendered anything new since
        the previous capture (frames_run unchanged).
    """

    seq: int
    emulator_frame_count: int
    rgb: np.ndarray
    timestamp: float
    stale: bool = False

    @property
    def frame_id(self) -> str:
        return f"seq{self.seq}@emu{self.emulator_frame_count}"


@dataclass
class GameObservation:
    """The adapter-built observation handed to the policy.

    values: float32 vector (10 for flappy v7) or None when invalid.
    valid: False ONLY for hard errors (bad frame, adapter failure);
        legitimate game situations (no pipe yet, occlusion, GET READY)
        are represented by the v7 sentinels inside `values` — the model
        was trained with them. Invalid observations are NEVER sent to
        the policy.
    """

    values: Optional[np.ndarray]
    frame_seq: int
    frame_id: str
    timestamp: float
    valid: bool
    invalid_reason: Optional[str] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionDecision:
    """One policy decision."""

    action: str                      # adapter-legal action name
    logits: Optional[List[float]]    # optional raw diagnostics
    frame_seq: int
    policy_name: str
    policy_sha256: str
    latency_ms: float
    diagnostics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class EpisodeResult:
    """The complete per-episode record (mission Stage B list)."""

    episode: int
    game: str
    seed_k: int
    rep: int
    result: str                      # alive | death | error | stopped
    death_reason: Optional[str]
    pipes: int
    frames: int
    flaps: int
    actions: int
    decisions: int
    errors: List[str]
    wall_s: float
    started_ts: float
    ended_ts: float
    trace_sha256: str
    policy_name: str
    policy_sha256: str
    manifest_sha256: str
    emulator_tag: str
    screenshots: List[str] = field(default_factory=list)
    video: Optional[str] = None
    trace_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


# ------------------------------------------------------------------
# interfaces
# ------------------------------------------------------------------


class FrameSource(ABC):
    """Ordered access to the latest emulator frame."""

    @abstractmethod
    def latest(self, require_fresh: bool = True) -> Frame:
        """Return the newest rendered frame.

        require_fresh=True raises FrameError when the emulator has not
        rendered anything since the previous capture (a stale frame
        would break the frame/action association contract).
        """

    @abstractmethod
    def capture_latency_ms(self) -> float:
        """Exponential moving average of the last capture latency."""

    @abstractmethod
    def close(self) -> None:
        """Release capture resources (idempotent)."""


class GameAdapter(ABC):
    """Game-specific perception, state and action mapping.

    Implementations must be importable WITHOUT any training module and
    must build observations that satisfy the frozen policy's input
    contract. Per-episode state lives here and MUST be fully reset by
    reset_episode().
    """

    game_id: str = "?"

    @abstractmethod
    def wait_ready(self, deadline_s: float) -> Any:
        """Drive the emulator from boot to a state where an episode can
        start (e.g. the GET READY screen), raising EmulatorError on
        timeout."""

    @abstractmethod
    def start_episode(self, seed_k: int) -> int:
        """Begin one episode from a known state. Returns the number of
        emulator frames consumed by the start sequence."""

    @abstractmethod
    def observe(self, frame: Frame) -> GameObservation:
        """Build the policy observation from one frame."""

    @abstractmethod
    def legal_actions(self) -> Sequence[str]:
        """The complete legal action vocabulary."""

    @abstractmethod
    def action_to_buttons(self, action: str) -> frozenset:
        """Map an action to the controller buttons held for ONE frame."""

    @abstractmethod
    def post_advance(self, frame: Frame) -> Dict[str, Any]:
        """After the emulator advanced: score/terminal detection.
        Returns {'pipe_passed': bool, 'terminal': bool,
                 'death_reason': str|None, ...}."""

    @abstractmethod
    def reset_episode(self) -> None:
        """Drop ALL per-episode state (observer, tracker, counters)."""

    @abstractmethod
    def snapshot(self) -> Dict[str, Any]:
        """Current human-readable state for live status (bird y, gap,
        validity...). Must never raise."""

    @abstractmethod
    def episode_stats(self) -> Dict[str, int]:
        """Generic per-episode counters for the result record:
        {'pipes': int, 'actions': int, 'decisions': int}. The engine
        maps these into the EpisodeResult regardless of game."""

    def note_action(self, decision: ActionDecision,
                    observation: GameObservation) -> None:
        """Optional post-decision hook: update the adapter's action
        history (e.g. flap counters) exactly once per decision, BEFORE
        the next observation is built. Default: no-op."""


class Policy(ABC):
    """The decision function boundary."""

    @abstractmethod
    def predict(self, observation: GameObservation) -> ActionDecision:
        """Decide one action for a VALID observation. Invalid input
        must raise, never be 'fixed'."""

    @abstractmethod
    def legal_actions(self) -> Sequence[str]:
        """The action names this policy emits."""

    @abstractmethod
    def reset(self) -> None:
        """Clear per-episode decision state (e.g. flap counters held
        outside the model)."""

    @abstractmethod
    def identity(self) -> Dict[str, Any]:
        """name / version / model_sha256 / manifest_sha256."""

    @abstractmethod
    def close(self) -> None:
        """Release model resources (idempotent)."""


class Controller(ABC):
    """The only component allowed to send inputs to the emulator."""

    @abstractmethod
    def apply(self, decision: ActionDecision,
              obs_frame: Frame) -> float:
        """Send the decision's input for exactly one emulator frame.

        Contract: the input corresponds to `obs_frame` (the frame the
        decision was made on); the emulator advances one frame; the
        NEXT captured frame must have a larger emulator_frame_count.
        Returns the send latency in ms.
        """

    @abstractmethod
    def release_all(self) -> None:
        """Force-release every button (one empty-input frame). Used on
        failures and shutdown only — never mid-episode."""

    @abstractmethod
    def state(self) -> Dict[str, Any]:
        """Held buttons, last sent action/frame, counters."""

    @abstractmethod
    def emergency_stop(self) -> None:
        """Latch: refuse every further input until reset_episode()."""

    @abstractmethod
    def reset_episode(self) -> None:
        """Clear the stop latch and per-episode counters."""


class Emulator(ABC):
    """The emulator lifecycle (boot, health, capture, input, teardown).

    Implementations boot in their factory/classmethod (e.g.
    `EnvSession.boot_new`) — a constructor that fails raises a typed
    EmulatorError/AssetError, never half-boots. `boot_info` carries
    the identification after a successful boot.
    """

    @abstractmethod
    def frames(self) -> FrameSource:
        """The frame source for this session."""

    @abstractmethod
    def advance(self, frames: int, buttons: frozenset) -> None:
        """Advance exactly `frames` frames holding `buttons`."""

    @abstractmethod
    def alive(self) -> bool:
        """False once the core has died or been shut down."""

    @abstractmethod
    def serialize(self) -> bytes:
        """Savestate blob (for episode anchor restore)."""

    @abstractmethod
    def unserialize(self, blob: bytes) -> None:
        """Restore a savestate (renders once before the next capture)."""

    @abstractmethod
    def tag(self) -> str:
        """One-line identification (core name/version + boot info)."""

    @abstractmethod
    def close(self) -> None:
        """Stop and clean up (idempotent, no leaked resources)."""


# ------------------------------------------------------------------
# helpers shared by implementations
# ------------------------------------------------------------------


def check_frame_shape(rgb: np.ndarray, *,
                      min_h: int = 1, min_w: int = 1) -> None:
    """Shared frame validation: dtype uint8, 3 channels, non-empty."""
    if rgb is None:
        raise FrameError("frame capture returned None")
    if not isinstance(rgb, np.ndarray) or rgb.ndim != 3 or \
            rgb.shape[2] != 3 or rgb.dtype != np.uint8:
        raise FrameError(
            f"invalid frame: expected (H,W,3) uint8, got "
            f"{type(rgb).__name__} shape={getattr(rgb, 'shape', None)} "
            f"dtype={getattr(rgb, 'dtype', None)}")
    if rgb.shape[0] < min_h or rgb.shape[1] < min_w:
        raise FrameError(f"frame too small: {rgb.shape}")


def monotonic_ms(t0: float) -> float:
    return (time.perf_counter() - t0) * 1000.0
