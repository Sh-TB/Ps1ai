"""Mission 2 experiment instrumentation (Issue #9 §3-4).

decision_log.py — normalized decision records for every track (manual policy,
assisted tool, algorithm variant). One JSONL row per decision chunk:

    observation → candidates (considered/rejected + why) → selection
    (buttons/duration/expected) → actual post-state → prediction verdict
    → outcome counters → objective progress + confidence → evidence paths.

Game time (emulator frames) and wall-clock time are recorded separately.

Records stay compact: state features by value, full snapshots by hash+path
only. Large artifacts never enter the stream (mission §3).
"""
from __future__ import annotations

import hashlib
import json
import os
import time


def _sha(data) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()[:16]


CONFIRMED = "CONFIRMED"   # directly verified by a reliable state signal
OBSERVED = "OBSERVED"     # visible evidence supports the claim
INFERRED = "INFERRED"     # derived from behaviour or correlation
UNKNOWN = "UNKNOWN"       # insufficient evidence


class DecisionLog:
    """Append-only decision record writer (one file per run)."""

    def __init__(self, out_dir, run_id, track, commit, plugin, game,
                 emulator, checkpoint_id=None, evidence_dir=None):
        self.out_dir = os.fspath(out_dir)
        os.makedirs(self.out_dir, exist_ok=True)
        self.run_id = run_id
        self.header = {
            "run_id": run_id,
            "track": track,             # A=manual B=assisted C=algorithm D=combined
            "commit": commit,
            "plugin": plugin,
            "game": game,
            "emulator": emulator,
            "checkpoint_id": checkpoint_id,
            "evidence_dir": os.fspath(evidence_dir or self.out_dir),
        }
        self.path = os.path.join(out_dir, f"decisions_{run_id}.jsonl")
        with open(self.path, "w") as f:
            f.write(json.dumps({"header": self.header}) + "\n")
        self._t0 = time.time()
        self.counters = {
            "decisions": 0, "deaths": 0, "damage_events": 0,
            "stall_chunks": 0, "recoveries": 0, "restores": 0,
            "prediction_correct": 0, "prediction_wrong": 0,
        }

    # ------------------------------------------------------------------
    def decision(self, chunk, game_frame, observation, candidates, selected,
                 actual=None, objective=None, evidence=None):
        """Record one decision.

        observation: {feature: {"value":…, "provenance": CONFIRMED|OBSERVED|INFERRED|UNKNOWN}}
        candidates:  [{"action":…, "expected":…, "rejected":bool, "why":str}, …]
        selected:    {"action":…, "buttons":[…], "frames":int, "expected":str}
        actual:      {"post_state":{…}, "prediction_correct":bool, "death":bool,
                      "damage":int, "stall":bool, "recovery":str|None}
        objective:   {"progress":…, "confidence": CONFIRMED…, "note":str}
        evidence:    [{"path":…, "sha256_16":…}]  (paths live outside the stream)
        """
        self.counters["decisions"] += 1
        if actual:
            if actual.get("death"):
                self.counters["deaths"] += 1
            if actual.get("damage"):
                self.counters["damage_events"] += 1
            if actual.get("stall"):
                self.counters["stall_chunks"] += 1
            if actual.get("recovery"):
                self.counters["recoveries"] += 1
            if actual.get("prediction_correct") is True:
                self.counters["prediction_correct"] += 1
            elif actual.get("prediction_correct") is False:
                self.counters["prediction_wrong"] += 1
        row = {
            "ts": time.time(),
            "wall_s": round(time.time() - self._t0, 3),
            "chunk": chunk,
            "game_frame": game_frame,
            "observation": observation,
            "candidates": candidates,
            "selected": selected,
            "actual": actual or {},
            "objective": objective or {},
            "evidence": evidence or [],
        }
        with open(self.path, "a") as f:
            f.write(json.dumps(row, default=str) + "\n")
        return row

    def note(self, kind, **fields):
        """Non-decision event (boot, checkpoint save/restore, crash, abort)."""
        with open(self.path, "a") as f:
            f.write(json.dumps({"ts": time.time(),
                                "wall_s": round(time.time() - self._t0, 3),
                                "event": kind, **fields}) + "\n")

    def summary(self):
        return {"header": self.header,
                "counters": dict(self.counters),
                "wall_s": round(time.time() - self._t0, 3),
                "path": self.path}

    def write_summary(self):
        out = os.path.join(self.out_dir, f"summary_{self.run_id}.json")
        with open(out, "w") as f:
            json.dump(self.summary(), f, indent=1)
        return out


def load_decisions(path):
    """Read a decision log → (header, [rows])."""
    header, rows = None, []
    with open(path) as f:
        for line in f:
            d = json.loads(line)
            if "header" in d and header is None:
                header = d["header"]
            else:
                rows.append(d)
    return header, rows
