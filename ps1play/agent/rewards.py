"""rewards.py — reward AUDIT mode (v0.6 §12). Log-only, no training.

Every component is logged separately and defaults to ZERO unless its
observation is independently verified. Holding RIGHT earns nothing when
the progress signal is unverified or the player is wedged (frozen
progress + low churn); RAM churn is never a reward; unverified sensors
disable their component entirely.

Usage: build one RewardAudit per run, call .accumulate() with the same
validated observations the policy already computes, and dump the log
next to the report. A later RL experiment must train on components that
pass `audit.enabled(component)`, never on raw heuristics.
"""
import time


class RewardAudit:
    #: component -> required sensor key (None = always available)
    REQUIRES = {
        "score_delta": "score",
        "progress_delta": "progress",
        "verified_kill": "kill_verified",
        "verified_pickup": "pickup_verified",
        "damage_penalty": "lives_hp",
        "death_penalty": "lives_hp",
        "time_penalty": None,                  # always available
        "stall_penalty": "progress",
        "exploration_novelty": None,           # cheap, always available
    }

    def __init__(self, sensor_status=None, weights=None):
        # sensor_status: {"score": bool, "progress": bool,
        #                 "kill_verified": bool, "pickup_verified": bool,
        #                 "lives_hp": bool}
        self.sensor = dict(sensor_status or {})
        self.weights = dict(weights or {})
        self.log = []
        self.totals = {k: 0.0 for k in self.REQUIRES}

    def enabled(self, component):
        req_sensor = self.REQUIRES[component]
        if req_sensor is None:
            return True
        return bool(self.sensor.get(req_sensor))

    def accumulate(self, chunk, score_delta=0.0, progress_delta=0.0,
                   kills_verified=0, pickups_verified=0, deaths=0,
                   damage=0, stalled_chunks=0, novelty=0.0, **_):
        """Compute one row of component values with all gates applied."""
        row = {"chunk": chunk, "ts": time.time(), "components": {}}
        c = row["components"]
        c["score_delta"] = (self.weights.get("score_delta", 1.0)
                            * score_delta) if self.enabled("score_delta") \
            else 0.0
        c["progress_delta"] = (self.weights.get("progress_delta", 1.0)
                               * progress_delta) if \
            self.enabled("progress_delta") else 0.0
        c["verified_kill"] = float(kills_verified) if \
            self.enabled("verified_kill") else 0.0
        c["verified_pickup"] = float(pickups_verified) if \
            self.enabled("verified_pickup") else 0.0
        c["damage_penalty"] = -float(damage) if \
            self.enabled("damage_penalty") else 0.0
        c["death_penalty"] = -float(deaths) if \
            self.enabled("death_penalty") else 0.0
        c["time_penalty"] = self.weights.get("time_penalty", -0.001)
        c["stall_penalty"] = (self.weights.get("stall_penalty", -0.01)
                              * stalled_chunks) if \
            self.enabled("stall_penalty") else 0.0
        c["exploration_novelty"] = float(novelty)
        for k, v in c.items():
            self.totals[k] = self.totals.get(k, 0.0) + v
        self.log.append(row)
        return row

    def to_dict(self):
        return {"sensor_status": dict(self.sensor),
                "enabled": {k: self.enabled(k) for k in self.REQUIRES},
                "totals": dict(self.totals),
                "rows": self.log,
                "note": "audit only; no policy decisions consumed these "
                        "values"}
