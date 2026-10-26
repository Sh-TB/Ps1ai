"""msx_r11_lib.py — Round 11 (Task 17-a) shared sensors for MSX.

Two new reusable, mock-testable instruments built on the VERIFIED
address bank (probe0 + Issues #3/#5 + rounds 8-10):

  * WagonTracker — lifecycle tracker over the entity table
    (base 0x0CA268, stride 0x14C) that turns spawn->despawn runs into
    `crossed` events by GEOMETRY (an entity that first appears AHEAD of
    the player and is last seen BEHIND the player was crossed while the
    ride advanced).  This is the Issue-#7 wagon_crossed counter; the
    small/big KIND split is applied afterwards by
    split_kinds() from recorded per-event metrics — never guessed
    online.

  * PollDiffIndex — records per-poll word transitions in a RAM block
    and classifies words as kill_exact / kill_correlated / ambient
    against a list of event frames (the Segment-2 progress-latch
    watch).

  * count_waves — wave counter for the Segment-4 discriminator
    (armed-slot sightings after a clear window).

All readers are observational.  No RAM writes anywhere in this module.
"""
from __future__ import annotations

import numpy as np

TABLE = 0x0CA268
STRIDE = 0x14C
SLOTS = 24                      # polled window (wagon.py contract)

# u16 column indices inside one slot row (byte offset = 2 * index)
COL_ST = 0                      # +0x00 entity type word
COL_X_LO, COL_X_HI = 60, 61     # +0x78 s32.16 world x
COL_H = 63                      # +0x7E height word
COL_SX = 71                     # +0x8E screen x (wagon.py "hp" slot)
COL_HPA4 = 82                   # +0xA4 armor/HP word (round-9/10)

ARMORED_ST = 0xA0D0             # round-9 armored trio family
CHOPPER_ST = (0xAA94, 0xABDC, 0xA0D0, 0xAB94)
CORPSE_ST = (0x4BE4, 0x5CC8)

CROSS_MARGIN = 8.0              # px; ahead/behind safety margin
MIN_PERSIST_FRAMES = 45         # wagon-candidate presence (wagon.py)


def _row(ram, slot):
    base = TABLE + slot * STRIDE
    return ram[base:base + STRIDE].view("<u2").astype(np.int32)


def slot_view(ram, slot):
    """Live read of one slot row -> dict (or None when empty).

    NOTE on the +0x8E word: census naming calls it screen-x (`sx`),
    the proven wagon.py sensor calls it HP and keys occupancy on it.
    It is exposed here as BOTH `sx` and `hp8e` (same word) so either
    rule can be replayed offline.
    """
    r = _row(ram, slot)
    st = int(r[COL_ST])
    xw = (int(r[COL_X_HI]) << 16) | int(r[COL_X_LO])
    if xw >= 0x80000000:
        xw -= 0x100000000
    w8e = int(r[COL_SX])
    rec = {"st": st, "x": xw / 65536.0, "h": int(r[COL_H]),
           "sx": w8e, "hp8e": w8e, "hpA4": int(r[COL_HPA4])}
    if not rec["st"] and not rec["hpA4"] and abs(rec["x"]) < 1e-6:
        return None
    return rec


class WagonTracker:
    """Spawn->despawn lifecycle tracker with crossing geometry.

    Occupancy rule (default = the PROVEN wagon.py rule): the +0x8E
    word is non-zero AND the slot head bytes are non-trivial
    (wagon.py recorded 1,108 spawn / 1,095 despawn events with it in
    round 9).  rule="any" (st|hpA4|x) is selectable and every poll's
    raw row records st/x/h/hp8e/hpA4 so BOTH rules can be replayed
    offline.
    """

    def __init__(self, ram, every: int = 5,
                 persist_frames: int = MIN_PERSIST_FRAMES,
                 slots: int = SLOTS, margin: float = CROSS_MARGIN,
                 rule: str = "hp8e"):
        self.ram = ram
        self.every = max(1, int(every))
        self.persist_frames = int(persist_frames)
        self.slots = int(slots)
        self.margin = float(margin)
        self.rule = rule
        self._last_poll = None
        self._open: dict[int, dict] = {}
        self._occ: dict[int, bool] = {}
        self.spawns: list[dict] = []
        self.crossed: list[dict] = []
        self.raw_rows: list[dict] = []
        # slot 0 is the PLAYER (combat.py ground truth) — never tracked
        self._first_slot = 1

    # -- reading -------------------------------------------------------
    def _occupied(self, slot: int, v: dict | None) -> bool:
        if v is None:
            return False
        if self.rule == "hp8e":
            if v["hp8e"] == 0:
                return False
            a = TABLE + slot * STRIDE
            return any(self.ram[a:a + 16].tolist())
        return bool(v["st"] or v["hpA4"] or abs(v["x"]) >= 1e-6)

    def poll(self, frame: int, px: float) -> list[dict]:
        """Sample the table; close lifecycles; return crossed events."""
        if self._last_poll is not None and \
                frame - self._last_poll < self.every:
            return []
        self._last_poll = frame
        events = []
        row = {"frame": frame, "px": round(px, 1), "occ": {}}
        for s in range(self._first_slot, self.slots):
            v = slot_view(self.ram, s)
            row["occ"][s] = None if v is None else {
                "st": v["st"], "x": round(v["x"], 1), "h": v["h"],
                "hp8e": v["hp8e"], "hpA4": v["hpA4"]}
            occ = self._occupied(s, v)
            was = self._occ.get(s, False)
            if occ and not was:
                self.spawns.append({"slot": s, "frame": frame, **v})
                self._open[s] = {"slot": s, "f0": frame, "px0": px,
                                 "x0": v["x"], "st": v["st"],
                                 "h": v["h"], "hpA4": v["hpA4"],
                                 "x_last": v["x"], "f_last": frame,
                                 "samples": 1}
            elif occ:
                o = self._open.get(s)
                if o is None:                 # pre-existing occupancy
                    self._open[s] = {"slot": s, "f0": frame,
                                     "px0": px, "x0": v["x"],
                                     "st": v["st"], "h": v["h"],
                                     "hpA4": v["hpA4"],
                                     "x_last": v["x"], "f_last": frame,
                                     "samples": 1}
                    self.spawns.append({"slot": s, "frame": frame,
                                        **v, "pre_existing": True})
                else:
                    o["x_last"] = v["x"]
                    o["f_last"] = frame
                    o["st"] = v["st"]
                    o["h"] = v["h"]
                    o["hpA4"] = v["hpA4"]
                    o["samples"] += 1
            elif not occ and was:
                o = self._open.pop(s, None)
                if o is not None:
                    ev = self._close(o, px, frame)
                    if ev is not None:
                        self.crossed.append(ev)
                        events.append(ev)
            self._occ[s] = occ
        self.raw_rows.append(row)
        return events

    def _close(self, o, px_now, frame_now) -> dict | None:
        dur = o["f_last"] - o["f0"]
        spawn_ahead = o["x0"] > o["px0"] + self.margin
        end_behind = o["x_last"] < px_now - self.margin
        player_advanced = px_now > o["px0"] + self.margin
        return {"slot": o["slot"], "f0": o["f0"], "f1": o["f_last"],
                "dur_f": dur, "px0": round(o["px0"], 1),
                "px1": round(px_now, 1), "x0": round(o["x0"], 1),
                "x1": round(o["x_last"], 1), "st": o["st"],
                "h": o["h"], "hpA4": o["hpA4"], "samples": o["samples"],
                "spawn_ahead": spawn_ahead, "end_behind": end_behind,
                "player_advanced": player_advanced,
                "crossed": bool(spawn_ahead and end_behind),
                "crossed_strict": bool(spawn_ahead and end_behind
                                       and player_advanced),
                "persistent": bool(dur >= self.persist_frames)}

    # -- reporting -----------------------------------------------------
    def summary(self) -> dict:
        cross = [e for e in self.crossed if e["crossed"]]
        strict = [e for e in self.crossed if e["crossed_strict"]]
        pers = [e for e in cross if e["persistent"]]
        pers_s = [e for e in strict if e["persistent"]]
        return {"schema": "ps1play-r11-wagon-tracker/1",
                "table": TABLE, "stride": STRIDE,
                "slots": self.slots, "every": self.every,
                "polls": len(self.raw_rows),
                "spawn_events": len(self.spawns),
                "lifecycles_closed": len(self.crossed),
                "crossed_total": len(cross),
                "crossed_strict": len(strict),
                "crossed_persistent": len(pers),
                "crossed_strict_persistent": len(pers_s)}


def split_kinds(crossed: list[dict], persist: bool = True,
                strict: bool = False) -> dict:
    """Offline small/big KIND split over crossed events.

    Rule (evidence-first, re-derivable): the wagon family is the
    largest st-value cluster among (persistent) crossed events; within
    it the split key is the height word h (+0x7E).  Two well-separated
    h clusters (gap >= 8) split small/big (big = taller cluster); a
    single cluster or >2 clusters => kind stays 'unlabeled' and the
    count is reported honestly as one family.
    strict=True counts only crossed_strict lifecycles (the player
    actually advanced past the entity — excludes pinned-arena combat
    despawns that merely walk into a stationary player).
    Returns {"kinds": {kind: n}, "family_st": st, "split_rule": str,
             "split_key": [values]}.
    """
    key = "crossed_strict" if strict else "crossed"
    pool = [e for e in crossed
            if e.get(key) and (e.get("persistent") or not persist)]
    if not pool:
        return {"kinds": {}, "family_st": None, "split_rule": "EMPTY",
                "split_key": []}
    by_st: dict[int, int] = {}
    for e in pool:
        by_st[e["st"]] = by_st.get(e["st"], 0) + 1
    fam_st = max(by_st, key=lambda k: by_st[k])
    fam = [e for e in pool if e["st"] == fam_st]
    hs = sorted(e["h"] for e in fam)
    gaps = [(hs[i + 1] - hs[i], i) for i in range(len(hs) - 1)]
    g, i = max(gaps) if gaps else (0, 0)
    if len(set(hs)) >= 2 and g >= 8 and i + 1 < len(hs):
        thr = (hs[i] + hs[i + 1]) / 2.0
        kinds = {"small": sum(1 for e in fam if e["h"] <= thr),
                 "big": sum(1 for e in fam if e["h"] > thr)}
        rule = f"H_SPLIT thr={thr:g} gap={g}"
    else:
        kinds = {"unlabeled": len(fam)}
        rule = f"NO_SPLIT (h spread {hs[0]}..{hs[-1]})"
    return {"kinds": kinds, "family_st": fam_st, "split_rule": rule,
            "split_key": hs}


class PollDiffIndex:
    """Per-poll word transitions in a RAM block + event correlation.

    add_poll(frame, block_bytes) diffs against the previous poll and
    stores changed u16 offsets.  classify(event_frames, quiet_gap)
    labels every changing word:
      kill_exact     — changed ONLY in polls at/adjacent to event
                       frames (never across a quiet gap)
      kill_correlated— changed at event polls AND sometimes elsewhere
      ambient        — never tied to an event poll
    """

    def __init__(self, lo: int, hi: int):
        self.lo, self.hi = lo, hi
        self.prev = None
        self.frames: list[int] = []
        self.changed: list[set[int]] = []
        self.values: dict[int, list[int]] = {}

    def add_poll(self, frame: int, block: bytes) -> set[int]:
        cur = np.frombuffer(block, dtype="<u2").astype(np.int32)
        ch: set[int] = set()
        if self.prev is not None and len(self.prev) == len(cur):
            d = np.flatnonzero(self.prev != cur)
            ch = set(int(i) for i in d)
            for i in ch:
                self.values.setdefault(i, []).append(frame)
        self.prev = cur
        self.frames.append(frame)
        self.changed.append(ch)
        return ch

    def classify(self, event_frames: list[int], quiet_gap: int = 600
                 ) -> dict[int, dict]:
        ev = sorted(event_frames)
        out: dict[int, dict] = {}
        for idx, ch in enumerate(self.changed):
            if not ch:
                continue
            f = self.frames[idx]
            near = any(0 <= f - ef <= 120 or 0 <= ef - f <= 120
                       for ef in ev)
            # the previous poll's frame: a change visible at THIS poll
            # was produced between frames[idx-1] and f
            for i in ch:
                rec = out.setdefault(i, {"flips": [], "near_event": 0,
                                         "far": 0})
                rec["flips"].append(f)
                if near:
                    rec["near_event"] += 1
                else:
                    rec["far"] += 1
        labeled = {}
        for i, rec in out.items():
            if rec["near_event"] and rec["far"] == 0:
                cls = "kill_exact"
            elif rec["near_event"]:
                cls = "kill_correlated"
            else:
                cls = "ambient"
            labeled[i] = {"class": cls, "addr": self.lo + 2 * i,
                          "n_flips": len(rec["flips"]),
                          "near_event": rec["near_event"],
                          "far": rec["far"],
                          "first_flip": rec["flips"][0],
                          "flips": rec["flips"][:24]}
        return labeled


def count_waves(sightings: list[dict], clear_gap: int = 600) -> dict:
    """Wave segmentation for the Segment-4 discriminator.

    sightings: list of {"frame": f, "armed": bool} census rows (any
    armed CHOPPER_ST slot with hpA4 > 0).  A new WAVE starts when an
    armed sighting follows >= clear_gap frames after the previous
    armed sighting (or opens the series).  Sampling coarser than
    clear_gap would over-split — disclose the census cadence.
    """
    waves = []
    last_clear_start = None
    last_armed_end = None
    cur = None
    for s in sightings:
        f, armed = s["frame"], bool(s["armed"])
        if armed:
            gap_ok = last_armed_end is None or \
                (f - last_armed_end) >= clear_gap
            if cur is None or gap_ok:
                lat = None if last_clear_start is None \
                    else f - last_clear_start
                cur = {"start": f, "latency": lat, "end": f}
                waves.append(cur)
            else:
                cur["end"] = f
            last_armed_end = f
            last_clear_start = None
        else:
            if last_clear_start is None:
                last_clear_start = f
    lat = [w["latency"] for w in waves if w["latency"] is not None]
    return {"n_waves": len(waves), "waves": waves,
            "latencies": lat,
            "first_latency": lat[0] if lat else None}
