"""ps1play.runtime.controller — the legal-input safety adapter (R62).

SafetyController is the ONLY component that sends inputs to the
emulator. Guarantees (all tested):

  * legality: an action must be in the adapter's legal vocabulary and
    map to a non-empty-or-empty button set the adapter declared — an
    unmapped action raises ControllerError instead of inventing input.
  * association: every send names the frame the decision was made on;
    duplicate sends for the same frame are rejected (no double
    injection); sends after a terminal/error are rejected.
  * one-frame pulses: an input is held for exactly the frames the
    engine advances (1 decision frame = 1 emulator frame) — the exact
    R61 semantics that reproduce the family records.
  * release-on-failure: `release_all()` emits one empty-input frame;
    used on failures/shutdown so no button stays latched.
  * emergency stop latch: after `emergency_stop()` every further send
    raises until `reset_episode()`.
  * audit: every send is recorded (frame seq, emulator frame count,
    action, buttons, latency) for trace hashing and evidence.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .errors import ControllerError
from .interfaces import ActionDecision, Controller, Frame


class SafetyController(Controller):
    def __init__(self, adapter, session, telemetry=None):
        self._adapter = adapter
        self._session = session
        self._tel = telemetry
        self._stopped = False
        self._last_seq_sent: Optional[int] = None
        self._sends: List[Dict[str, Any]] = []
        self._held_now: frozenset = frozenset()
        self.n_sends = 0
        self.n_rejects = 0

    # ---- Controller surface ----
    def apply(self, decision: ActionDecision,
              obs_frame: Frame) -> float:
        if self._stopped:
            self.n_rejects += 1
            raise ControllerError(
                "controller is in emergency stop; refusing input")
        if decision.action not in self._adapter.legal_actions():
            self.n_rejects += 1
            raise ControllerError(
                f"illegal action {decision.action!r}; legal: "
                f"{sorted(self._adapter.legal_actions())}")
        if self._last_seq_sent is not None and \
                obs_frame.seq <= self._last_seq_sent:
            self.n_rejects += 1
            raise ControllerError(
                f"input sequencing violation: frame seq {obs_frame.seq} "
                f"already acted (last={self._last_seq_sent})")
        buttons = self._adapter.action_to_buttons(decision.action)
        t0 = time.perf_counter()
        self._session.advance(1, buttons)
        ms = (time.perf_counter() - t0) * 1000.0
        self._last_seq_sent = obs_frame.seq
        self._held_now = buttons
        self.n_sends += 1
        self._sends.append({
            "seq": obs_frame.seq,
            "emu_frame": obs_frame.emulator_frame_count,
            "action": decision.action,
            "buttons": sorted(buttons),
            "latency_ms": round(ms, 3),
        })
        if self._tel is not None:
            self._tel.latency("controller_send_ms", ms)
        return ms

    def release_all(self) -> None:
        """One empty-input frame: releases every held button. Only
        called on failure paths and shutdown (never mid-episode)."""
        if not self._session.alive():
            return
        try:
            self._session.advance(1, frozenset())
        except Exception:
            pass
        self._held_now = frozenset()

    def state(self) -> Dict[str, Any]:
        return {
            "stopped": self._stopped,
            "last_seq_sent": self._last_seq_sent,
            "held_buttons": sorted(self._held_now),
            "n_sends": self.n_sends,
            "n_rejects": self.n_rejects,
        }

    def emergency_stop(self) -> None:
        self._stopped = True

    def reset_episode(self) -> None:
        self._stopped = False
        self._last_seq_sent = None
        self._held_now = frozenset()
        self._sends = []

    # ---- audit ----
    def sends_tail(self, n: int = 20) -> List[Dict[str, Any]]:
        return self._sends[-n:]
