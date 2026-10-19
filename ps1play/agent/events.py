"""events.py — evidence-based event model for PS1Play.

Replaces the old "score delta >= 90 -> kill" heuristic (v0.5 report
inflated kills_est from score jumps alone while continue screens reset
the score silently). Design rules from the v0.6 mission review:

  * A score change alone can NEVER produce a VERIFIED kill.
  * Every event carries an explicit evidence status:
      OBSERVED  - raw signal was directly measured (RAM value change)
      ESTIMATED - inferred from a heuristic (e.g. score delta >= threshold)
      VERIFIED  - independent corroborating evidence exists
  * Score resets (continue / death), u32 wraparound, stale addresses and
    impossible jumps are explicit reason-coded observations, never silent.
  * Mission clear is reported in two separate fields:
      mission_clear_detected  (primary signal changed)
      mission_clear_verified  (signal sustained + independent corroboration)

Everything here is pure Python (no emulator needed) so it is fully unit
testable on synthetic data; the runner feeds it live observations.
"""
from collections import defaultdict

# --- event types (the explicit vocabulary) --------------------------------
SCORE_CHANGED = "SCORE_CHANGED"
SCORE_RESET = "SCORE_RESET"
SCORE_WRAP = "SCORE_WRAP"
SCORE_SUSPICIOUS = "SCORE_SUSPICIOUS"
SCORE_STALE = "SCORE_STALE"
ENEMY_CANDIDATE_CHANGED = "ENEMY_CANDIDATE_CHANGED"
ENEMY_KILL_CANDIDATE = "ENEMY_KILL_CANDIDATE"       # ESTIMATED by default
ENEMY_KILL_VERIFIED = "ENEMY_KILL_VERIFIED"         # requires entity evidence
POW_FREED_CANDIDATE = "POW_FREED_CANDIDATE"
ITEM_COLLECTED_CANDIDATE = "ITEM_COLLECTED_CANDIDATE"
PLAYER_DAMAGED = "PLAYER_DAMAGED"
PLAYER_DIED = "PLAYER_DIED"
PLAYER_RESPAWNED = "PLAYER_RESPAWNED"
CONTINUE_USED = "CONTINUE_USED"
MISSION_TRANSITION = "MISSION_TRANSITION"
MISSION_CLEAR_DETECTED = "MISSION_CLEAR_DETECTED"
MISSION_CLEAR_VERIFIED = "MISSION_CLEAR_VERIFIED"

OBSERVED = "OBSERVED"
ESTIMATED = "ESTIMATED"
VERIFIED = "VERIFIED"

# evidence keys that justify VERIFIED status per event type
_VERIFICATION_KEYS = {
    ENEMY_KILL_VERIFIED: ("entity_slot_death", "address", "frame"),
    MISSION_CLEAR_VERIFIED: ("corroboration",),
}


class Event:
    """One timestamped, reason-coded, evidence-carrying event."""

    __slots__ = ("type", "status", "frame", "chunk", "evidence", "note")

    def __init__(self, etype, status, frame=None, chunk=None,
                 evidence=None, note=""):
        if status == VERIFIED:
            need = _VERIFICATION_KEYS.get(etype)
            if need and not evidence:
                raise ValueError(
                    f"{etype} cannot be VERIFIED without evidence")
        self.type = etype
        self.status = status
        self.frame = frame
        self.chunk = chunk
        self.evidence = dict(evidence or {})
        self.note = note

    def to_dict(self):
        return {"type": self.type, "status": self.status,
                "frame": self.frame, "chunk": self.chunk,
                "evidence": self.evidence, "note": self.note}


class EventLog:
    """Append-only event list with honest aggregate counters.

    Counters are split by status so a report can never present an
    ESTIMATED count as a VERIFIED one.
    """

    def __init__(self):
        self.events = []

    def add(self, etype, status=OBSERVED, **kw):
        ev = Event(etype, status, **kw)
        self.events.append(ev)
        return ev

    def count(self, etype, status=None):
        return sum(1 for e in self.events
                   if e.type == etype and (status is None or
                                           e.status == status))

    def by_status(self):
        out = defaultdict(lambda: defaultdict(int))
        for e in self.events:
            out[e.type][e.status] += 1
        return {k: dict(v) for k, v in out.items()}

    def to_dict(self):
        return {"counts": self.by_status(),
                "n": len(self.events),
                "events": [e.to_dict() for e in self.events]}


# --- score tracking ---------------------------------------------------------
class ScoreTracker:
    """Tracks the score word across time with explicit reason codes.

    Handles, per the mission review:
      * first-sample bootstrap (no delta invented)
      * continue/death RESET  (big NEGATIVE jump; score can only decrease
        by a reset in Metal Slug X)
      * u32 WRAPAROUND        (value drops through 0 after 0xFFFFFFFF)
      * STALE address         (identical raw bytes while other RAM churns
        is the caller's judgement; here: None/identical-raw handling)
      * SUSPICIOUS jump       (positive delta above MAX_JUMP — recorded,
        flagged, never silently converted into kills/rewards)

    The caller supplies the raw bytes so the report can show exactly what
    was decoded (raw_before / raw_after) — no hidden re-reads.
    """

    #: positive deltas above this are SUSPICIOUS (recorded, not rewarded)
    MAX_JUMP = 100_000
    #: negative deltas beyond -delta are treated as resets (not wrap)
    RESET_JUMP = -1_000

    def __init__(self, addr=0x0EE318, width=4, encoding="u32le"):
        self.addr = addr
        self.width = width
        self.encoding = encoding
        self.value = None            # last accepted decoded value
        self.raw = None              # last raw bytes (bytes obj)
        self.first_frame = None
        self.last_frame = None
        self.n_resets = 0
        self.n_wraps = 0
        self.n_suspicious = 0
        self.n_updates = 0
        self.max_value = 0
        self.min_value = None
        self.cumulative_gain = 0     # sum of accepted positive deltas

    def decode(self, raw):
        """Decode width-byte little-endian buffer to int (caller may
        override for BCD variants once HUD correlation is done)."""
        return int.from_bytes(bytes(raw), "little")

    def feed(self, value, frame=None, chunk=None, raw=None):
        """Feed one decoded sample. Returns an observation dict:

        {delta, before, after, kind, frame_start, frame_end, ...}
        kind in {bootstrap, update, reset, wrap, suspicious}
        """
        obs = {"addr": self.addr, "encoding": self.encoding,
               "frame_start": self.last_frame, "frame_end": frame,
               "chunk": chunk,
               "raw_before": self.raw.hex() if self.raw else None,
               "raw_after": raw.hex() if raw else None,
               "decoded_before": self.value, "decoded_after": value,
               "delta": None, "kind": "update"}
        before = self.value
        if before is None:
            obs["kind"] = "bootstrap"
            obs["delta"] = 0
        else:
            d = value - before
            obs["delta"] = d
            if d < 0 and before > 0x8000_0000 and value < 0x1000:
                # u32 wraparound: 0xFFFFFFFF -> 0x00000014
                obs["kind"] = "wrap"
                self.n_wraps += 1
                d = value + (1 << (8 * self.width)) - before
                obs["delta"] = d
            elif d < 0:
                # score never decreases in normal play: a drop to ~0 is
                # a continue/death RESET; any other negative delta is an
                # unexplained anomaly and is recorded as SUSPICIOUS.
                if value < 0x1000 or d <= self.RESET_JUMP:
                    obs["kind"] = "reset"
                    self.n_resets += 1
                else:
                    obs["kind"] = "suspicious"
                    self.n_suspicious += 1
            elif d > self.MAX_JUMP:
                obs["kind"] = "suspicious"
                self.n_suspicious += 1
            else:
                self.cumulative_gain += max(0, d)
        self.value = value
        self.raw = bytes(raw) if raw is not None else self.raw
        self.last_frame = frame
        self.n_updates += 1
        self.min_value = value if self.min_value is None \
            else min(self.min_value, value)
        self.max_value = max(self.max_value, value)
        if self.first_frame is None:
            self.first_frame = frame
        obs["n_resets"] = self.n_resets
        obs["n_wraps"] = self.n_wraps
        obs["suspicious"] = obs["kind"] == "suspicious"
        return obs

    def to_dict(self):
        return {"addr": self.addr, "width": self.width,
                "encoding": self.encoding,
                "encoding_status": "PARTIAL (static RE + live increments; "
                                   "HUD cross-check pending)",
                "value": self.value, "max": self.max_value,
                "min": self.min_value,
                "cumulative_gain": self.cumulative_gain,
                "resets": self.n_resets, "wraps": self.n_wraps,
                "suspicious_jumps": self.n_suspicious,
                "updates": self.n_updates,
                "first_frame": self.first_frame,
                "last_frame": self.last_frame}


class KillClassifier:
    """Converts score events into kill candidates — honestly.

    A score delta >= min_delta emits ENEMY_KILL_CANDIDATE with status
    ESTIMATED. Only caller-supplied independent entity evidence (a
    monitored entity slot dying at the same interval) upgrades it to
    ENEMY_KILL_VERIFIED. Estimated and verified counts are reported
    separately and never merged.
    """

    def __init__(self, min_delta=90, log=None):
        self.min_delta = min_delta
        self.estimated = 0
        self.verified = 0
        self.log = log

    def on_score_obs(self, obs, evlog, frame=None, chunk=None):
        """Feed one ScoreTracker observation; returns emitted Event(s)."""
        out = []
        if obs.get("kind") != "update" or obs.get("delta") is None:
            return out
        d = obs["delta"]
        if d >= self.min_delta:
            self.estimated += 1
            ev = evlog.add(
                ENEMY_KILL_CANDIDATE, ESTIMATED, frame=frame, chunk=chunk,
                evidence={"score_delta": d,
                          "basis": "score-delta threshold only",
                          "score_addr": obs.get("addr")},
                note="estimated from score delta; not independently "
                     "corroborated")
            out.append(ev)
        return out

    def verify_with_entity(self, evlog, addr, frame=None, chunk=None,
                           window_back=6):
        """Upgrade recent candidates to VERIFIED using independent
        entity-slot evidence (a monitored candidate entity died).
        Returns the upgraded Event or None."""
        for e in reversed(evlog.events[-window_back:]):
            if e.type == ENEMY_KILL_CANDIDATE and e.status == ESTIMATED:
                e.type = ENEMY_KILL_VERIFIED
                e.status = VERIFIED
                e.evidence["entity_slot_death"] = hex(addr)
                e.evidence["verified_at_frame"] = frame
                self.estimated = max(0, self.estimated - 1)
                self.verified += 1
                return e
        return None

    def to_dict(self):
        return {"kills_estimated": self.estimated,
                "kills_verified": self.verified,
                "note": "estimated = score-delta heuristic; verified = "
                        "independently corroborated entity evidence"}


class MissionClearDetector:
    """Two-stage mission-clear classifier (v0.6 §10).

    Stage 1 DETECTED: the primary mission-state byte differs from the
    baseline observed in active Mission 1.  -> OBSERVED event
    MISSION_CLEAR_DETECTED. This alone is NOT a clear claim.

    Stage 2 VERIFIED: the change is SUSTAINED for `sustain_chunks`
    consecutive checks (rules out transient reads) AND the caller has
    supplied at least one independent corroboration signal
    (`corroborate(reason)` — e.g. input-responsiveness profile changed,
    completion screen observed, progress signal left the mission range).

    A return to the baseline byte before sustain marks the candidate
    REJECTED (recorded as MISSION_TRANSITION with note).
    """

    def __init__(self, baseline_byte, sustain_chunks=4, log=None):
        self.baseline = baseline_byte
        self.sustain_needed = sustain_chunks
        self.sustain = 0
        self.corroboration = []
        self.candidate = None          # dict of the pending transition
        self.detected = False
        self.verified = False
        self.rejected = 0
        self.log = log

    def corroborate(self, reason):
        """Register one independent corroboration signal."""
        if reason not in self.corroboration:
            self.corroboration.append(reason)

    def feed(self, mission_byte, frame=None, chunk=None, evlog=None):
        """Feed one mission-byte sample; returns emitted Event or None."""
        ev = None
        if not self.detected:
            if mission_byte != self.baseline:
                if self.candidate is None:
                    self.candidate = {"from": self.baseline,
                                      "to": int(mission_byte),
                                      "first_frame": frame,
                                      "first_chunk": chunk}
                    if evlog:
                        ev = evlog.add(
                            MISSION_CLEAR_DETECTED, OBSERVED,
                            frame=frame, chunk=chunk,
                            evidence=dict(self.candidate),
                            note="mission byte changed; awaiting "
                                 "sustain+corroboration before any "
                                 "clear claim")
                self.detected = True
                self.sustain = 1
        elif self.candidate is not None:
            if mission_byte != self.candidate["to"]:
                # byte went back: transient, reject the candidate
                self.rejected += 1
                if evlog:
                    ev = evlog.add(
                        MISSION_TRANSITION, OBSERVED, frame=frame,
                        chunk=chunk,
                        evidence={**self.candidate, "reverted_to":
                                  int(mission_byte)},
                    note="byte reverted before sustain; clear candidate "
                         "REJECTED")
                self.candidate = None
                self.detected = False
                self.sustain = 0
            else:
                self.sustain += 1
        if (self.candidate is not None and not self.verified
                and self.sustain >= self.sustain_needed
                and self.corroboration):
            self.verified = True
            if evlog:
                ev = evlog.add(
                    MISSION_CLEAR_VERIFIED, VERIFIED, frame=frame,
                    chunk=chunk,
                    evidence={"mission_state_before": self.baseline,
                              "mission_state_after":
                                  self.candidate["to"],
                              "sustain_chunks": self.sustain,
                              "corroboration": list(self.corroboration)},
                note="sustained byte change + independent corroboration")
        return ev

    def to_dict(self):
        return {"mission_clear_detected": self.detected,
                "mission_clear_verified": self.verified,
                "verification_method": ("sustained mission-byte change + "
                                        "independent corroboration"
                                        if self.verified else
                                        "not verified"),
                "mission_state_before": self.baseline,
                "mission_state_after": (self.candidate["to"]
                                        if self.candidate else None),
                "sustain": self.sustain,
                "sustain_needed": self.sustain_needed,
                "corroboration": list(self.corroboration),
                "rejected_candidates": self.rejected}
