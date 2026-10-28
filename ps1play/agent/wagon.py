"""Wagon sensor (Issue #7) — count train-wagons crossed in Mission 1.

Why: the repo has NO live progress sensor (camera_fx saturates ~255;
score is per-life — Issue #5 L5-3).  The user-defined acceptance for
Mission-1 progress is "cross at least 50 wagons, small and big".
The train/POW section shows wagons as long-lived objects that spawn
from the right and despawn behind the player while the ride advances.

Design (evidence-first, no game hack):
  * Poll the VERIFIED entity table (base 0x800CA268, stride 0x14C,
    R38 note: the u16 at +0x8E is the historical 'HP' address whose
    semantic label was later CONTRADICTED for world entities — see the
    MSX capsule; occupancy telemetry only treats NON-ZERO as
    'slot occupied', which is semantics-agnostic at this level, with a
    recorded blind spot for entities within ~1px of the camera edge)
    every `every` frames.
  * Occupancy rule is recorded, never hard-guessed: a slot is occupied
    when its HP word is non-zero AND its fingerprint (stable head
    bytes) is non-trivial; the raw HP series for every slot is logged
    so rules can be re-derived offline from the same trace.
  * Transitions empty->occupied emit `spawn` events (with a full slot
    dump, base64, for offline classification); occupied->empty emit
    `despawn`.  occupied->occupied never re-spawns (double-count
    guard).
  * Long-lived heuristic: presence for >= `persist_frames` sampled
    frames marks an entity `persistent` (wagon-candidate).  Small/big
    KIND labels come from offline clustering of slot dumps correlated
    with frame captures — the sensor never guesses a kind online.

Everything is observational: no RAM writes, no cheats, no rewinds.
"""
from __future__ import annotations

import base64

import numpy as np

TABLE_VA = 0x800CA268
RAM_MASK = 0x1FFFFF
TABLE = TABLE_VA & RAM_MASK          # 0x0CA268
STRIDE = 0x14C
SLOTS = 24                            # polled window; real population
HP_OFF = 0x8E                         # occupancy word (historical 'HP'
                                      # address; semantics corrected —
                                      # see MSX capsule CONTRADICTED event)
FP_LEN = 0x10                         # fingerprint head bytes


def _slot_base(slot: int) -> int:
    return TABLE + slot * STRIDE


class WagonSensor:
    """Frame-sampled lifecycle tracker over the entity table."""

    def __init__(self, ram: np.ndarray, every: int = 10,
                 persist_frames: int = 45, slots: int = SLOTS):
        self.ram = ram
        self.every = max(1, int(every))
        self.persist_frames = int(persist_frames)
        self.slots = int(slots)
        self._last_poll = None
        self._occ: dict[int, bool] = {}
        self._first_seen: dict[int, int] = {}
        self._present_samples: dict[int, int] = {}
        self.spawns: list[dict] = []
        self.despawns: list[dict] = []
        self.series: list[dict] = []      # compact hp series per poll

    # ---------- raw reads ----------
    def hp(self, slot: int) -> int:
        a = _slot_base(slot) + HP_OFF
        return int(self.ram[a] | (self.ram[a + 1] << 8))

    def slot_bytes(self, slot: int, n: int = STRIDE) -> bytes:
        a = _slot_base(slot)
        return bytes(bytearray(self.ram[a:a + n]))

    def fingerprint(self, slot: int) -> str:
        """Stable head-hash: first FP_LEN bytes of the slot.  Position-
        like fields live deeper in the struct, so the head is the most
        stable identity proxy; full dumps are kept for re-derivation."""
        a = _slot_base(slot)
        head = bytes(bytearray(self.ram[a:a + FP_LEN]))
        return head.hex()[:16]

    def occupied(self, slot: int) -> bool:
        """Recorded occupancy rule v1: HP != 0 and non-zero fingerprint.
        The full HP series is logged so the rule can be revised
        offline without re-running the game."""
        return self.hp(slot) != 0 and any(self.slot_bytes(slot, FP_LEN))

    # ---------- sampling ----------
    def poll(self, frame: int) -> list[dict]:
        """Sample all slots; return any new lifecycle events."""
        if self._last_poll is not None and \
                frame - self._last_poll < self.every:
            return []
        self._last_poll = frame
        events: list[dict] = []
        row = {"frame": frame, "hp": [self.hp(s) for s in
                                      range(self.slots)]}
        for s in range(self.slots):
            occ = self.occupied(s)
            was = self._occ.get(s, False)
            if occ and not was:
                ev = {"type": "spawn", "slot": s, "frame": frame,
                      "hp": self.hp(s), "fp": self.fingerprint(s),
                      "dump_b64": base64.b64encode(
                          self.slot_bytes(s)).decode("ascii")}
                self.spawns.append(ev)
                self._first_seen[s] = frame
                self._present_samples[s] = 0
                events.append(ev)
            elif not occ and was:
                ev = {"type": "despawn", "slot": s, "frame": frame,
                      "present_samples": self._present_samples.get(s, 0),
                      "age": frame - self._first_seen.get(s, frame)}
                self.despawns.append(ev)
                self._present_samples[s] = 0        # lifecycle closed
                events.append(ev)
            elif occ:
                self._present_samples[s] = \
                    self._present_samples.get(s, 0) + 1
            self._occ[s] = occ
        row["occ"] = "".join("1" if self._occ.get(s) else "0"
                             for s in range(self.slots))
        self.series.append(row)
        return events

    # ---------- reporting ----------
    def persistent_slots(self) -> dict[int, dict]:
        """Slots whose sampled presence >= persist_frames (wagon
        candidates; kind labels are applied offline)."""
        out = {}
        for s in range(self.slots):
            n = self._present_samples.get(s, 0)
            frames_present = n * self.every
            if n and frames_present >= self.persist_frames:
                spawns = [e for e in self.spawns if e["slot"] == s]
                out[s] = {
                    "present_samples": n,
                    "frames_present": frames_present,
                    "spawn_count": len(spawns),
                    "fps": [e["fp"] for e in spawns],
                    "first_frames": [e["frame"] for e in spawns],
                }
        return out

    def summary(self) -> dict:
        return {
            "schema": "ps1play-wagon/1",
            "table_va": TABLE_VA,
            "stride": STRIDE,
            "slots_polled": self.slots,
            "every": self.every,
            "polls": len(self.series),
            "spawn_events": len(self.spawns),
            "despawn_events": len(self.despawns),
            "persistent_slots": self.persistent_slots(),
        }
