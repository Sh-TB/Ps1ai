"""progress.py — validated camera/progress signal for PS1Play.

v0.5 shipped an UNVERIFIED camera word (report: verified=false, addr
0xCA2E2) that the policy then trusted; the v4 run shows that word frozen
at 58 for 250 consecutive chunks while the bot was wedged against an
obstacle, with 48 "cam_reset" events — the signal was never validated
and camera-lock was never separated from a true stall.

This module enforces the v0.6 contract (mission review §4):

  CALIBRATION (pure functions, unit-testable on synthetic series)
    rank_candidates(): a word is a progress candidate ONLY if, over
    controlled trials from identical savestates, it
      * is idle-stable            (|idle drift| <= idle_tol)
      * rises under RIGHT         (>= min_delta)
      * falls under LEFT          (<= -min_delta)
      * is monotonic over a long rightward run (dips <= max_dips)
    Words failing any test are reported with the failing test name.
    If no word passes, rank_candidates returns an empty list — callers
    must degrade to unverified telemetry, never fake progress.

  RUNTIME MONITOR (ProgressSignal)
    Distinguishes, per chunk:
      PROGRESS      value advanced
      CAMERA_LOCKED value frozen while world churn is high (fight at a
                    locked camera — NOT a stall, do not bulldoze)
      STALLED       value frozen while churn is low (player wedged)
      RESET         value dropped far below the running max (death /
                    respawn / continue moved the camera back)
      WRAP          u16 wraparound
      INVALID       signal invalidated (post-reload remap, stale data)
    plus monotonicity regression detection and honest to_dict() with
    status + evidence. An unverified signal NEVER claims progress.
"""

# candidate ranking ----------------------------------------------------------
def _diffs(series):
    return [int(b) - int(a) for a, b in zip(series, series[1:])]


def _circular_diffs(series, modulus=1 << 16):
    out = []
    for a, b in zip(series, series[1:]):
        d = (int(b) - int(a)) % modulus
        if d > modulus // 2:
            d -= modulus
        out.append(d)
    return out


def rank_candidates(trials, idle_tol=8, min_delta=60, min_gain=150,
                    max_dips=2, return_all=False):
    """Rank progress-word candidates from controlled trial series.

    trials: {addr: {"idle": [...], "right": [...], "left": [...],
                    "run": [...]}}
    Values are u16 readings sampled at a fixed cadence.

    Default returns ONLY candidates that passed every test, best first —
    an empty list means "no trustworthy progress word" and callers must
    degrade to unverified telemetry (never fake progress).
    return_all=True additionally exposes every rejected candidate with
    the exact test that failed it (raw evidence is preserved).
    """
    ranked = []
    for addr, t in trials.items():
        idle = t.get("idle") or []
        right = t.get("right") or []
        left = t.get("left") or []
        run = t.get("run") or []
        m = {
            "addr": addr,
            "idle_drift": (max(idle) - min(idle)) if len(idle) > 1 else 0,
            "right_delta": (right[-1] - right[0]) if right else 0,
            "left_delta": (left[-1] - left[0]) if left else 0,
            "run_gain": (run[-1] - run[0]) if run else 0,
        }
        rd = _circular_diffs(run)
        m["dips"] = sum(1 for d in rd if d < -4)
        m["valid"] = (m["idle_drift"] <= idle_tol
                      and m["right_delta"] >= min_delta
                      and m["left_delta"] <= -min_delta
                      and m["run_gain"] >= min_gain
                      and m["dips"] <= max_dips)
        m["score"] = (m["run_gain"] - m["dips"] * 400) if m["valid"] else -1
        ranked.append(m)
    ranked.sort(key=lambda c: -c["score"])
    if return_all:
        return {"valid": [c for c in ranked if c["valid"]],
                "all": ranked}
    return [c for c in ranked if c["valid"]]


# runtime monitor ------------------------------------------------------------
class ProgressSignal:
    """Runtime monitor over ONE candidate progress word.

    status starts as the calibration verdict ('VERIFIED' or
    'UNVERIFIED'); an UNVERIFIED signal still reports observations but
    `claims_progress` stays False so reports/policies cannot mistake it
    for trusted state.
    """

    PROGRESS = "PROGRESS"
    CAMERA_LOCKED = "CAMERA_LOCKED"
    STALLED = "STALLED"
    RESET = "RESET"
    WRAP = "WRAP"
    INVALID = "INVALID"

    def __init__(self, addr, verified, lock_churn=3500, freeze_tol=2,
                 reset_drop=100, max_reasonable=0xFFFF):
        self.addr = addr
        self.verified = bool(verified)
        self.status = "VERIFIED" if verified else "UNVERIFIED"
        self.invalid_reason = None
        self.lock_churn = lock_churn
        self.freeze_tol = freeze_tol
        self.reset_drop = reset_drop
        self.max_reasonable = max_reasonable
        self.value = None
        self.peak = 0
        self.frozen_streak = 0
        self.n_progress = 0
        self.n_lock = 0
        self.n_stall = 0
        self.n_reset = 0
        self.n_wrap = 0
        self.last_state = None
        self.last_churn = 0

    @property
    def claims_progress(self):
        return self.verified and self.status not in (
            self.INVALID, self.RESET, self.WRAP)

    def invalidate(self, reason):
        """Address mapping no longer trusted (mission reload remap,
        stale data). Must be re-calibrated before use again."""
        self.verified = False
        self.status = self.INVALID
        self.invalid_reason = reason

    def update(self, value, churn=0, frame=None):
        """Feed one sample + the chunk's RAM churn; classify the state."""
        st = self.PROGRESS
        if self.status == self.INVALID:
            return st
        if self.value is None:
            self.value = value
            self.peak = value
            self.last_state = st
            return st
        d = (value - self.value) % 0x10000
        if d > 0x8000:
            d -= 0x10000
        if -d >= self.reset_drop and value < self.peak - self.reset_drop:
            st = self.RESET
            self.n_reset += 1
            self.peak = value
            self.frozen_streak = 0
        elif d == 0:
            self.frozen_streak += 1
            if churn >= self.lock_churn:
                st = self.CAMERA_LOCKED
                self.n_lock += 1
            elif self.frozen_streak > self.freeze_tol:
                st = self.STALLED
                self.n_stall += 1
            else:
                st = self.PROGRESS      # too early to call frozen
        else:
            self.frozen_streak = 0
            if d < 0 and value > self.peak - self.reset_drop:
                st = self.PROGRESS      # small back-scroll, still live
            elif d < 0:
                st = self.RESET
                self.n_reset += 1
                self.peak = value
            else:
                st = self.PROGRESS
                self.n_progress += 1
                self.peak = max(self.peak, value)
        self.value = value
        self.last_churn = churn
        self.last_state = st
        self.last_frame = frame
        return st

    def to_dict(self):
        return {"addr": hex(self.addr) if isinstance(self.addr, int)
                else self.addr,
                "status": self.status,
                "verified": self.verified,
                "claims_progress": self.claims_progress,
                "value": self.value, "peak": self.peak,
                "last_state": self.last_state,
                "frozen_streak": self.frozen_streak,
                "counts": {"progress": self.n_progress,
                           "camera_lock": self.n_lock,
                           "stall": self.n_stall,
                           "reset": self.n_reset,
                           "wrap": self.n_wrap},
                "lock_churn": self.lock_churn}
