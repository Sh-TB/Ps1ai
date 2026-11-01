"""ps1play.runtime.lifecycle — episode lifecycle state machine (R62).

A small, explicit state machine so every run follows the same
documented lifecycle and every transition is checked (invalid
transitions raise LifecycleError instead of producing undefined
behavior):

    INIT -> BOOTING -> READY -> EPISODE_ACTIVE -> EPISODE_END
                 ^                                 |
                 |  (restart policy accepts)       v
                 +----------- READY <--------------+
                                                  |
                                     (failure / stop)
                                                  v
                                STOPPING -> STOPPED | FAILED

`RestartPolicy` decides whether another episode may start, honoring:
episode count, wall-clock time limit, per-episode frame limits already
enforced by the engine, and the consecutive-failure cap (a broken
emulator must end the run, not loop forever).
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from .errors import EmergencyStop, LifecycleError

STATES = ("INIT", "BOOTING", "READY", "EPISODE_ACTIVE", "EPISODE_END",
          "STOPPING", "STOPPED", "FAILED")

_TRANSITIONS = {
    "INIT": {"BOOTING", "STOPPING"},
    "BOOTING": {"READY", "FAILED", "STOPPING"},
    "READY": {"EPISODE_ACTIVE", "STOPPING"},
    "EPISODE_ACTIVE": {"EPISODE_END", "STOPPING", "FAILED"},
    "EPISODE_END": {"READY", "STOPPING"},
    "STOPPING": {"STOPPED", "FAILED"},
    "STOPPED": set(),
    "FAILED": set(),
}


class Lifecycle:
    """Explicit lifecycle with checked transitions."""

    def __init__(self, telemetry=None):
        self.state = "INIT"
        self._tel = telemetry

    def require(self, *states: str) -> None:
        if self.state not in states:
            raise LifecycleError(
                f"operation requires state {states}, current is "
                f"{self.state}")

    def transition(self, to: str, *, reason: str = "") -> None:
        if to not in _TRANSITIONS.get(self.state, set()):
            raise LifecycleError(
                f"illegal lifecycle transition {self.state} -> {to}"
                + (f" ({reason})" if reason else ""))
        self.state = to
        if self._tel is not None:
            self._tel.emit("lifecycle", state=to, reason=reason)

    def in_terminal(self) -> bool:
        return self.state in ("STOPPED", "FAILED")

    def __repr__(self) -> str:
        return f"Lifecycle({self.state})"


class RestartPolicy:
    """Decides whether another episode may start.

    Args:
        max_episodes: 0 = unlimited (requires a time/frame limit).
        time_limit_s: wall-clock budget for the WHOLE run.
        max_consecutive_failures: stop after N consecutive failed
            episodes (a broken environment must never loop).
    """

    def __init__(self, *, max_episodes: int = 1,
                 time_limit_s: float = 300.0,
                 max_consecutive_failures: int = 2):
        self.max_episodes = int(max_episodes)
        self.time_limit_s = float(time_limit_s)
        self.max_consecutive_failures = int(max_consecutive_failures)
        self.t0 = time.time()
        self.episodes_done = 0
        self.consecutive_failures = 0

    def record(self, *, failed: bool) -> None:
        self.episodes_done += 1
        self.consecutive_failures = \
            (self.consecutive_failures + 1) if failed else 0

    def time_left_s(self) -> float:
        return self.time_limit_s - (time.time() - self.t0)

    def should_continue(self) -> tuple[bool, str]:
        """(continue?, reason when not)."""
        if self.max_episodes > 0 and \
                self.episodes_done >= self.max_episodes:
            return False, f"episode limit reached ({self.max_episodes})"
        # buffer: 5s or 5% of the budget, whichever is smaller — a
        # tiny budget (tests, smoke runs) must still be usable
        buffer_s = min(5.0, self.time_limit_s * 0.05)
        if self.time_left_s() <= buffer_s:
            return False, (f"time limit reached "
                           f"({self.time_limit_s:.0f}s)")
        if self.consecutive_failures >= self.max_consecutive_failures:
            return False, (f"{self.consecutive_failures} consecutive "
                           f"failures (cap "
                           f"{self.max_consecutive_failures})")
        return True, ""

    def summary(self) -> Dict[str, Any]:
        return {
            "episodes_done": self.episodes_done,
            "max_episodes": self.max_episodes,
            "time_left_s": round(self.time_left_s(), 1),
            "consecutive_failures": self.consecutive_failures,
        }


class StopWatch:
    """A hard wall-clock safety limit for one episode."""

    def __init__(self, seconds: float):
        self.deadline = time.time() + float(seconds)

    def expired(self) -> bool:
        return time.time() >= self.deadline

    def remaining(self) -> float:
        return self.deadline - time.time()


def raise_if_stopped(stop_flag: Optional[Dict[str, Any]]) -> None:
    """The engine's emergency-stop hook (shared dict)."""
    if stop_flag and stop_flag.get("stop"):
        raise EmergencyStop(
            str(stop_flag.get("reason", "emergency stop requested")))
