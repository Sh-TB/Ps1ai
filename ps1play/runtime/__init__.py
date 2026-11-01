"""ps1play.runtime — the autonomous game-playing runtime (R62).

One orchestration layer over the proven components:

    python3 -m ps1play play flappybird

Components: errors (typed failures), interfaces (FrameSource /
GameAdapter / Policy / Controller / Emulator contracts), config,
telemetry (JSONL events + run manifest), session (emulator lifecycle +
ordered frame capture), controller (legal-input safety), policy_runtime
(the frozen R61 ONNX champion boundary), lifecycle (state machine +
restart policy), engine (the loop), recorder (screenshots/video),
scoring (pipe passages), registry (game plug-in boundary).
"""
from .config import RUNTIME_VERSION, RuntimeConfig  # noqa: F401
from .errors import (AssetError, ConfigError, ControllerError,
                     EmulatorError, EmergencyStop, FrameError,
                     LifecycleError, Ps1RuntimeError, RuntimePolicyError)
from .interfaces import (ActionDecision, Controller, Emulator, Frame,
                         FrameSource, GameAdapter, GameObservation,
                         Policy)
