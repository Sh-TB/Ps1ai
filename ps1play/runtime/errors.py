"""ps1play.runtime.errors — typed runtime errors (R62).

Every failure mode the autonomous runtime can hit has a distinct type
so the engine can clean up precisely, report a meaningful exit code,
and never silently fall back to a different policy or teacher.
"""
from __future__ import annotations


class Ps1RuntimeError(RuntimeError):
    """Base class for every runtime failure. Carries an `exit_code`
    suggestion used by the CLI to map failures to shell exit codes."""

    exit_code = 1

    def __init__(self, message: str, *, detail: dict | None = None):
        super().__init__(message)
        self.detail = detail or {}


class ConfigError(Ps1RuntimeError):
    """Invalid or missing runtime configuration."""

    exit_code = 2


class AssetError(Ps1RuntimeError):
    """A required asset (ISO, model, manifest, BIOS, core) is missing
    or fails its hash/identity check."""

    exit_code = 3


class EmulatorError(Ps1RuntimeError):
    """The emulator failed to boot, died mid-session, or missed a
    deadline."""

    exit_code = 4


class FrameError(EmulatorError):
    """Frame capture returned nothing, wrong dimensions, or a stale
    frame where freshness was required."""

    exit_code = 4


class ControllerError(Ps1RuntimeError):
    """A controller input was illegal, duplicated, out of sequence, or
    the send failed."""

    exit_code = 5


class RuntimePolicyError(Ps1RuntimeError):
    """The policy failed to load, its identity check failed, or it
    rejected a (possibly malformed) observation. NEVER swallowed: a
    policy rejection is a hard runtime error, not a fallback trigger."""

    exit_code = 6


class AdapterError(Ps1RuntimeError):
    """The game adapter failed to build a valid observation or to
    classify the game state."""

    exit_code = 7


class LifecycleError(Ps1RuntimeError):
    """An episode-lifecycle transition was invalid (misuse of the
    state machine)."""

    exit_code = 8


class EmergencyStop(Ps1RuntimeError):
    """A user- or supervisor-requested emergency stop. Not a failure
    of the runtime itself; the CLI maps it to exit code 130."""

    exit_code = 130
