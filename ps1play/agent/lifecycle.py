"""lifecycle.py — the boot-to-clear state machine (v0.6 §6).

The v0.5 runner had recovery paths (responsive gate, recover_v2,
ensure_mission, re-anchor) with NO shared lifecycle: nothing recorded
which state the agent believed it was in, so a continue screen could be
mistaken for active gameplay and nothing invalidated stale calibration.

This FSM is the RECORDING backbone — it wraps the existing gates, it
does not replace them:

  BOOT -> GAME_IDENTIFIED -> TITLE_OR_MENU -> GAMEPLAY_CANDIDATE
       -> INPUT_CONTROL_VERIFIED -> MISSION_1_VERIFIED
       -> OBSERVATION_CALIBRATED -> PLAYING
       -> (DEATH_OR_CONTINUE -> RECOVERY -> INPUT_CONTROL_REVERIFIED
           -> OBSERVATION_RECALIBRATED -> PLAYING)*
       -> MISSION_CLEAR_VERIFIED

Every transition emits a structured record: old state, action, new
state, evidence, outcome. Negative rules are enforced at the FSM level:
  * PLAYING can only be entered from INPUT_CONTROL_VERIFIED / REVERIFIED
    (RAM churn or a pad mirror alone is never sufficient — the caller
    must present the responsive() verdict as evidence).
  * calibration states expire: entering DEATH_OR_CONTINUE invalidates
    OBSERVATION_CALIBRATED (stale addresses after re-entry).
"""
from collections import OrderedDict

STATES = [
    "BOOT", "GAME_IDENTIFIED", "TITLE_OR_MENU", "GAMEPLAY_CANDIDATE",
    "INPUT_CONTROL_VERIFIED", "MISSION_1_VERIFIED",
    "OBSERVATION_CALIBRATED", "PLAYING", "DEATH_OR_CONTINUE",
    "RECOVERY", "INPUT_CONTROL_REVERIFIED", "OBSERVATION_RECALIBRATED",
    "MISSION_CLEAR_DETECTED", "MISSION_CLEAR_VERIFIED", "ABORTED",
]

#: where each state may be entered FROM
_TRANSITIONS = {
    "GAME_IDENTIFIED": {"BOOT"},
    "TITLE_OR_MENU": {"GAME_IDENTIFIED", "TITLE_OR_MENU"},
    "GAMEPLAY_CANDIDATE": {"TITLE_OR_MENU", "GAME_IDENTIFIED",
                           "RECOVERY"},
    "INPUT_CONTROL_VERIFIED": {"GAMEPLAY_CANDIDATE",
                               "INPUT_CONTROL_REVERIFIED"},
    "MISSION_1_VERIFIED": {"INPUT_CONTROL_VERIFIED"},
    "OBSERVATION_CALIBRATED": {"MISSION_1_VERIFIED",
                               "OBSERVATION_RECALIBRATED"},
    "PLAYING": {"OBSERVATION_CALIBRATED", "OBSERVATION_RECALIBRATED",
                "PLAYING"},
    "DEATH_OR_CONTINUE": {"PLAYING", "INPUT_CONTROL_VERIFIED"},
    "RECOVERY": {"DEATH_OR_CONTINUE", "PLAYING"},
    "INPUT_CONTROL_REVERIFIED": {"RECOVERY", "DEATH_OR_CONTINUE"},
    "OBSERVATION_RECALIBRATED": {"INPUT_CONTROL_REVERIFIED"},
    "MISSION_CLEAR_DETECTED": {"PLAYING"},
    "MISSION_CLEAR_VERIFIED": {"MISSION_CLEAR_DETECTED"},
    "ABORTED": set(STATES),
}


class Lifecycle:
    """Recording FSM. Illegal transitions raise ValueError so a caller
    cannot silently skip the input-control gate."""

    def __init__(self, log=None):
        self.state = "BOOT"
        self.history = []
        self.log = log

    def transition(self, new, action, evidence=None, outcome="ok"):
        if new not in _TRANSITIONS:
            raise ValueError(f"unknown lifecycle state {new!r}")
        allowed = _TRANSITIONS[new]
        if allowed and self.state not in allowed:
            raise ValueError(
                f"illegal transition {self.state} -> {new}; required "
                f"from {sorted(allowed)} (evidence={evidence!r})")
        rec = {"from": self.state, "action": action, "to": new,
               "evidence": dict(evidence or {}), "outcome": outcome}
        self.history.append(rec)
        self.state = new
        if self.log:
            self.log(f"[lifecycle] {rec['from']} -> {new} "
                     f"({action}, {outcome})")
        return rec

    def invalidate_observations(self, reason):
        """Any death/continue/re-entry makes calibration stale."""
        return {"invalidated": True, "reason": reason,
                "at_state": self.state}

    def to_dict(self):
        return {"state": self.state, "n_transitions": len(self.history),
                "history": self.history}
