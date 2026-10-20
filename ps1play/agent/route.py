"""route.py — Mission-1 route ledger, stall detection, and the simplest
state-aware traversal policy (Issue #2 sections 5/7).

Design rules from the issue:
  * The route is a sequence of OBSERVED segments, not a frame script.
  * Labels: OBSERVED / VERIFIED / HEURISTIC / FAILED / UNKNOWN.
  * Stall detection is bounded: after N identical unsuccessful chunks
    the segment is classified stalled and the policy attempts ONE
    bounded recovery pattern before declaring the segment blocked.
  * Cheat-assisted and no-cheat results are recorded separately per
    segment (cheat_result / legit_result) and never merged.
"""
import hashlib
import json
import os
import time

# segment status labels
OBSERVED = "OBSERVED"
VERIFIED = "VERIFIED"
HEURISTIC = "HEURISTIC"
FAILED = "FAILED"
UNKNOWN = "UNKNOWN"

# policy modes (mirrors cheatprof.PROFILES)
MODE_CHEAT = "CHEAT_ASSISTED_EXPLORATION"
MODE_LEGIT = "LEGIT_CONTROLLER_RUN"


class StallDetector:
    """Bounded stall classification over chunk-level progress signals.

    update() consumes one chunk result:
      progress  — verified progress delta (or None when unverified)
      churn     — RAM bytes changed during the chunk
      score_delta — observed score delta
    A chunk counts as STALLED when movement evidence is absent; after
    `stall_limit` consecutive stalled chunks the detector enters
    RECOVERY for `recovery_chunks` chunks (bounded), then BLOCKED.
    """

    def __init__(self, stall_limit=4, recovery_chunks=3,
                 churn_floor=250, score_floor=1):
        self.stall_limit = int(stall_limit)
        self.recovery_chunks = int(recovery_chunks)
        self.churn_floor = int(churn_floor)
        self.score_floor = int(score_floor)
        self.stalled_chunks = 0
        self.recovery_left = 0
        self.state = "PROGRESS"
        self.blocked_segments = 0

    def _is_stalled(self, progress, churn, score_delta):
        moved = ((progress is not None and progress > 0)
                 or churn >= self.churn_floor
                 or (score_delta is not None and score_delta >= self.score_floor))
        return not moved

    def update(self, progress, churn, score_delta):
        if self.state == "BLOCKED":
            return self.state
        if self.state == "RECOVERY":
            self.recovery_left -= 1
            if self.recovery_left <= 0:
                self.state = "BLOCKED"
                self.blocked_segments += 1
            return self.state
        if self._is_stalled(progress, churn, score_delta):
            self.stalled_chunks += 1
            if self.stalled_chunks >= self.stall_limit:
                self.state = "RECOVERY"
                self.recovery_left = self.recovery_chunks
        else:
            self.stalled_chunks = 0
            self.state = "PROGRESS"
        return self.state

    def reset(self):
        self.stalled_chunks = 0
        self.recovery_left = 0
        self.state = "PROGRESS"

    def to_dict(self):
        return {"state": self.state,
                "stalled_chunks": self.stalled_chunks,
                "recovery_left": self.recovery_left,
                "blocked_segments": self.blocked_segments,
                "stall_limit": self.stall_limit,
                "recovery_chunks": self.recovery_chunks}


class RoutePolicy:
    """Deliberately simple traversal backbone (issue section 7).

    Ordinary traversal: hold RIGHT + burst fire; periodic jump. When
    the StallDetector enters RECOVERY the policy plays one bounded
    pattern (step-back + jump + sustained fire + optional grenades).
    BLOCKED freezes all output except fire (safety: keep shooting).

    decide() is a pure function of the global frame index and the
    detector state, so the button timeline is independent of chunk
    partitioning (same contract as RobustLegitPolicy v0.7).
    """

    FIRE_ON, FIRE_OFF = 8, 6
    JUMP_PERIOD = 200
    JUMP_HOLD = 13
    REC_LEFT = 30
    REC_HOP = 13
    GRENADE_PERIOD = 150

    def __init__(self, allow_grenades=False, jump_enabled=True):
        self.fc = 0
        self.allow_grenades = bool(allow_grenades)
        self.jump_enabled = bool(jump_enabled)
        self.hop_hold = 0
        self.hop_cd = self.JUMP_PERIOD
        self.press = 0
        self.stats = {"jump": 0, "grenade": 0, "recovery": 0}

    def decide(self, chunk, detector):
        segs = []
        prev = None
        for _ in range(chunk):
            state = detector.state if detector is not None else "PROGRESS"
            burst = (self.fc % (self.FIRE_ON + self.FIRE_OFF)) < self.FIRE_ON
            if state == "RECOVERY":
                u = self.fc % (self.REC_LEFT + self.REC_HOP + 30)
                self.stats["recovery"] += 1
                if u < self.REC_LEFT:
                    btns = {"LEFT", "Y"}
                elif u < self.REC_LEFT + self.REC_HOP:
                    btns = {"LEFT", "B"}
                else:
                    btns = {"RIGHT", "Y"}
                    if self.allow_grenades and \
                            self.fc % self.GRENADE_PERIOD == 0:
                        self.press = 4
                        self.stats["grenade"] += 1
            elif state == "BLOCKED":
                btns = {"Y"} if burst else set()
            else:
                btns = {"RIGHT"}
                if burst:
                    btns.add("Y")
                if self.jump_enabled:
                    if self.hop_hold > 0:
                        btns.add("B")
                        self.hop_hold -= 1
                    elif self.hop_cd <= 0:
                        self.hop_hold = self.JUMP_HOLD
                        self.hop_cd = self.JUMP_PERIOD + self.JUMP_HOLD
                        self.stats["jump"] += 1
                    else:
                        self.hop_cd -= 1
                if self.allow_grenades and \
                        self.fc % self.GRENADE_PERIOD == 0:
                    self.press = 4
                    self.stats["grenade"] += 1
            if self.press > 0:
                btns.add("A")
                self.press -= 1
            self.fc += 1
            if prev is not None and prev["btns"] == btns:
                prev["frames"] += 1
            else:
                prev = {"frames": 1, "btns": btns}
                segs.append(prev)
        return segs


class RouteLedger:
    """Append-only segment ledger with separate cheat/legit results."""

    def __init__(self, serial="SLUS-01212", mission="mission1",
                 segments=None, events=None):
        self.serial = serial
        self.mission = mission
        self.segments = list(segments or [])
        self.events = list(events or [])

    # -------------- segments --------------
    def start_segment(self, seg_id, landmark, entry_frame, mode,
                      progress=None, evidence=None, confidence=UNKNOWN):
        seg = {
            "id": seg_id,
            "landmark": landmark,
            "landmark_status": HEURISTIC if landmark else UNKNOWN,
            "mode": mode,                       # cheat-assisted | legit
            "entry_frame": int(entry_frame),
            "exit_frame": None,
            "progress_at_entry": progress,
            "progress_at_exit": None,
            "action_pattern": None,
            "hazard": None,
            "stalled": False,
            "recovery_used": False,
            "completed": None,
            "status": OBSERVED,
            "evidence": list(evidence or []),
        }
        self.segments.append(seg)
        return seg

    def close_segment(self, seg, exit_frame, progress=None, completed=None,
                      stalled=False, recovery_used=False, hazard=None,
                      action_pattern=None):
        seg["exit_frame"] = int(exit_frame)
        seg["progress_at_exit"] = progress
        seg["completed"] = completed
        seg["stalled"] = bool(stalled)
        seg["recovery_used"] = bool(recovery_used)
        seg["hazard"] = hazard
        seg["action_pattern"] = action_pattern
        if completed:
            seg["status"] = OBSERVED
        elif stalled:
            seg["status"] = FAILED
        return seg

    def add_event(self, kind, frame, **kw):
        ev = {"kind": kind, "frame": int(frame), "t": time.strftime(
            "%H:%M:%S")}
        ev.update(kw)
        self.events.append(ev)
        return ev

    # -------------- summary / serialization --------------
    def summary(self):
        by_mode = {}
        for s in self.segments:
            m = s.get("mode", "?")
            d = by_mode.setdefault(m, {"segments": 0, "completed": 0,
                                       "stalled": 0})
            d["segments"] += 1
            d["completed"] += 1 if s.get("completed") else 0
            d["stalled"] += 1 if s.get("stalled") else 0
        return {"serial": self.serial, "mission": self.mission,
                "segments_total": len(self.segments),
                "events": len(self.events), "by_mode": by_mode}

    def to_dict(self):
        return {"schema": "ps1play-route-ledger/1",
                "serial": self.serial, "mission": self.mission,
                "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
                "summary": self.summary(),
                "segments": self.segments, "events": self.events}

    def save(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=1)
        return path

    @classmethod
    def load(cls, path):
        with open(path) as f:
            data = json.load(f)
        return cls(serial=data.get("serial", "SLUS-01212"),
                   mission=data.get("mission", "mission1"),
                   segments=data.get("segments"),
                   events=data.get("events"))

    @staticmethod
    def file_sha256(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
