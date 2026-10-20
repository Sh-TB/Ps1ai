"""telemetry.py — structured telemetry adapter (Issue #4 Phase 3,
extended in Issue #5 Priority Refinement).

Every field links to a RAM-discovery record or a reproducible
experiment; fields without that link are emitted as None (UNKNOWN)
and are never guessed.  Field grades follow the Issue #4 evidence
rules: a candidate interpretation needs at least two independent
controlled experiments before it is labelled.

VERIFIED fields (each with >=2 independent experiments):

  score        u32le @0x0EE318 — static RE 9 xrefs (Issue #3 re_index),
               live kill event 0->244 deterministic (causality v5),
               live score collapse on death (route_timed 4900->0),
               Issue #2 series history.
  grenades     u8 @0x0EDCF4 — Issue #3 Phase-G live series 10..6,
               action-probe 3 fresh-restore decrements (2026-10-20),
               causality v5 main-leg + 2 dedicated decrements.
  scroll_x     u32le @0x0EB858 16.16 fixed-point camera/world scroll-x
               — scroll-dump series (+58.97/+60 per 40f RIGHT, frozen
               idle, LEFT reversal, left-boundary freeze), two-origin
               candidate agreement, shadow twin @0x0EB860 (identical
               series = double buffer).  Integer part = value >> 16.
  pad_mirror   u16le @0x0D4948 — held/release rhythm per D-pad bit,
               zero under no-input, static RE anchor (v3/v5 labs).

OBSERVED (one clean experiment, repeat pending):

  action_latch u8 @0x095790 — sticky "any action pressed" latch,
               0 at fresh spawn, 1 after any action button (2x2 trials);
               sticky semantics confirmed across causality v4 legs.

STATIC_EVIDENCE (source-level chain, live correlation in progress —
Issue #5 Priority Refinement):

  flags_word   u32le @0x0EE518 — per-player status flag word. Static:
               61 xrefs in the player-status block (score 0x0EE318 is
               the same region); OR-bit writes (e.g. 0x8006F058:
               lw/or/sw) and the HUD draws " GAME OVER" when the word
               == -1 (0x80071834: lw; bne -1 path skips; site 0x80071850
               prints string @0x80011580).  Live bit-level meaning per
               death/continue is NOT yet verified → treat as opaque.

UNKNOWN (no validated interpretation — always None):

  lives, continues, hp, player_x/y, facing, enemy/projectile slots,
  mission_clear flag.  Death is DERIVED (score collapse + churn), not
  a verified flag.  Metal Slug X mission play has NO countdown timer:
  bounded u8/u16/plain/BCD scans found zero strict decrements
  (progress probe v4); 0x0D47D4 stays a HEURISTIC pace sensor.

Issue #5 overlay mapping note: ENEMY.BIN is LIVE-VERIFIED verbatim at
VA 0x8009C0E8 (probe3 V1: 0 mismatch runs / 115,400 B); the overlay
does NOT touch the published GS lives/hp addresses — its 387 refs go
through the player-pointer word 0x800C9A98, which currently reads
0xA0 in our boot context (a handle, not a raw pointer).
"""
from __future__ import annotations

import json
import time

import numpy as np

# ---- field table (single source of truth) -------------------------
# CONTEXT MATTERS (2026-10-20 root-cause lesson): the boot flow first
# reaches the ATTRACT DEMO, which plays a scripted mission-1 run with
# its own HUD.  Variables verified inside demo micro-windows do NOT
# automatically transfer to real play.  Real play is reached by START
# taps and is PROVEN by input ownership (idle pad-mirror all-zero +
# RIGHT moves the world).
ADDR_SCORE = 0x0EE318
ADDR_GRENADES = 0x0EDCF4          # HUD '10' slot; strict -1 per throw
ADDR_BOMBS_DIGIT = 0x0EEE3A       # HUD bombs ones digit, tile base 0x4B
ADDR_BOMBS_DIGIT_SHADOW = 0x0EEF52
ADDR_CAMERA = 0x0CA2E0            # real-play scroll (16.16-ish u32)
ADDR_PAD_MIRROR = 0x0D4948
ADDR_ACTION_LATCH = 0x095790      # demo-context sticky latch
ADDR_DEMO_SCROLL = 0x0EB858       # demo-context movement accumulator
ADDR_PACE_SENSOR = 0x0D47D4       # HEURISTIC: freezes under input
ADDR_FLAGS_WORD = 0x0EE518        # STATIC_EVIDENCE: ==-1 gates GAME OVER

PROVENANCE = {
    "score": {"addr": hex(ADDR_SCORE), "width": "u32le",
              "grade": "VERIFIED",
              "evidence": ["issue3 re_index xrefs",
                           "causality v5 fire score 0->244 x2",
                           "route_timed death collapse 4900->0"]},
    "grenades": {"addr": hex(ADDR_GRENADES), "width": "u8",
                 "grade": "VERIFIED",
                 "evidence": ["issue3 phase-G series 10..6",
                              "realplay validate strict 10->9 x3",
                              "causality v5 decrement main+2"]},
    "bombs_digit": {"addr": hex(ADDR_BOMBS_DIGIT),
                    "width": "u8 tile (digit = byte - 0x4B)",
                    "grade": "OBSERVED",
                    "evidence": ["v4 press-scan 0x53->0x51 (-2 over "
                                 "2 throws)",
                                 "v4 control leg empty",
                                 "twin @0x0EEF52"]},
    "camera_fx": {"addr": hex(ADDR_CAMERA), "width": "u32le",
                  "grade": "OBSERVED",
                  "evidence": ["v4 long run: gain >2M raw in every "
                               "sampled window (9/9)",
                               "route_timed overlapping candidate "
                               "0xCA2E2 right_delta +175",
                               "controller trace monotone check "
                               "(pending live confirmation)"]},
    "pad_mirror": {"addr": hex(ADDR_PAD_MIRROR), "width": "u16le",
                   "grade": "VERIFIED",
                   "evidence": ["causality v3+v5 per-bit rhythm",
                                "no-input zero, static RE anchor",
                                "real-play ownership test (idle all "
                                "zero, demo bits gone)"]},
    "action_latch": {"addr": hex(ADDR_ACTION_LATCH), "width": "u8",
                     "grade": "OBSERVED",
                     "evidence": ["action probe 2x2 trials sticky latch",
                                  "sticky across causality v4 legs"]},
    "demo_scroll_fx": {"addr": hex(ADDR_DEMO_SCROLL),
                       "width": "u32le_16.16",
                       "grade": "OBSERVED",
                       "evidence": ["demo-context ONLY: +58.97/+60 per "
                                    "40f RIGHT, frozen idle, LEFT "
                                    "reversal, boundary freeze",
                                    "does NOT transfer to real play "
                                    "(real-start finding)"]},
    "pace_sensor": {"addr": hex(ADDR_PACE_SENSOR), "width": "u16le",
                    "grade": "HEURISTIC",
                    "evidence": ["decrements 1/frame ONLY without input "
                                 "(issue3, route_timed); NOT a timer"]},
    "flags_word": {"addr": hex(ADDR_FLAGS_WORD), "width": "u32le",
                   "grade": "OBSERVED",
                   "evidence": ["static: 61 exe xrefs, player-status "
                                "block; OR-bit writes 0x8006F058..74",
                                "static: ' GAME OVER' HUD draw gated "
                                "on the word (0x80071834->0x80071850)",
                                "live: full-run trace 2026-10-20 — "
                                "0xFF during active play, 0x1 exactly "
                                "on the 4 GAME OVER freezes (image "
                                "c050), each followed by a continue "
                                "restart (score 0 + grenade refill)"]},
}
UNKNOWN_FIELDS = ("lives", "continues", "hp", "player_x", "player_y",
                  "facing", "enemies", "projectiles", "mission_clear",
                  "timer", "bombs_reserve")


class TelemetryAdapter:
    """Structured snapshot + event derivation over a live PS1Play."""

    def __init__(self, play, include_unknown=False):
        self.p = play
        self.include_unknown = include_unknown
        self.prev = None

    # -- raw readers (all physical offsets, little-endian PS1) ------
    def read_score(self):
        return int(self.p.mem.u32(ADDR_SCORE))

    def read_grenades(self):
        return int(self.p.mem.u8(ADDR_GRENADES))

    def read_bombs_digit(self):
        """HUD bombs ones digit, tile-encoded (digit = byte - 0x4B)."""
        v = int(self.p.mem.u8(ADDR_BOMBS_DIGIT)) - 0x4B
        return v if 0 <= v <= 9 else None

    def read_camera_fx(self):
        return int(self.p.mem.u32(ADDR_CAMERA))

    def read_camera_x(self):
        return self.read_camera_fx() >> 16

    def read_pad_mirror(self):
        return int(self.p.mem.u16(ADDR_PAD_MIRROR))

    def read_action_latch(self):
        return int(self.p.mem.u8(ADDR_ACTION_LATCH))

    def read_flags_word(self):
        return int(self.p.mem.u32(ADDR_FLAGS_WORD))

    # -- structured snapshot ----------------------------------------
    def snapshot(self, buttons=None, frame=None):
        s = {
            "schema": "ps1play-telemetry/3",
            "frame": frame,
            "buttons": sorted(buttons) if buttons else [],
            "score": self.read_score(),
            "grenades": self.read_grenades(),
            "bombs_digit": self.read_bombs_digit(),
            "camera_x": self.read_camera_x(),
            "camera_fx": self.read_camera_fx(),
            "pad_mirror": self.read_pad_mirror(),
            "action_latch": self.read_action_latch(),
            "flags_word": self.read_flags_word(),
        }
        for f in UNKNOWN_FIELDS:
            s[f] = None            # never guessed
        s["pace_sensor"] = None
        s["demo_scroll_fx"] = None
        if self.include_unknown:
            s["pace_sensor"] = int(self.p.mem.u16(ADDR_PACE_SENSOR))
            s["demo_scroll_fx"] = int(self.p.mem.u32(ADDR_DEMO_SCROLL))
        s["provenance"] = {k: v["grade"]
                           for k, v in PROVENANCE.items()}
        return s

    # -- event derivation between two snapshots ----------------------
    def events(self, prev, cur):
        """Compact event list; all derived events are labelled DERIVED
        because no verified flag exists for them yet."""
        ev = []
        if prev is None:
            return ev
        ds = cur["score"] - prev["score"]
        if ds > 0:
            ev.append({"type": "score_gain", "delta": ds,
                       "grade": "DERIVED_ON_VERIFIED"})
        if ds <= -200:
            ev.append({"type": "death_candidate", "delta": ds,
                       "grade": "DERIVED",
                       "note": "score collapse; validate with churn"})
        if cur["grenades"] < prev["grenades"]:
            ev.append({"type": "grenade_used",
                       "delta": prev["grenades"] - cur["grenades"],
                       "grade": "DERIVED_ON_VERIFIED"})
        if cur["grenades"] > prev["grenades"]:
            ev.append({"type": "grenade_refill", "delta":
                       cur["grenades"] - prev["grenades"],
                       "grade": "DERIVED_ON_VERIFIED"})
        pb, cb = prev.get("bombs_digit"), cur.get("bombs_digit")
        if pb is not None and cb is not None and cb < pb:
            ev.append({"type": "bombs_digit_drop",
                       "delta": pb - cb, "grade": "DERIVED_ON_OBSERVED"})
        if cur["camera_fx"] < prev["camera_fx"] and \
                (prev["camera_fx"] - cur["camera_fx"]) > (1 << 20):
            ev.append({"type": "camera_wrap",
                       "grade": "DERIVED_ON_OBSERVED"})
        if prev.get("flags_word") != cur.get("flags_word") and \
                cur.get("flags_word") == 0xFFFFFFFF:
            ev.append({"type": "game_over_flags",
                       "grade": "DERIVED", "note": "flag word "
                       "saturated"})
        if prev.get("flags_word") == 0xFF and \
                cur.get("flags_word") == 0x1:
            ev.append({"type": "game_over_screen",
                       "grade": "OBSERVED",
                       "note": "0xFF->0x1 = GAME OVER screen "
                               "(4/4 live correlation, image c050)"})
        return ev

    def scroll_gain(self, prev, cur):
        """Wrap-safe integer camera gain from camera_fx raw words."""
        if prev is None:
            return 0
        d = cur["camera_fx"] - prev["camera_fx"]
        if d < -(1 << 24):          # raw wrap
            d += 1 << 32
        return d >> 16


class JsonlTrace:
    """Append-only JSONL trace writer (deterministic replay input)."""

    def __init__(self, path):
        self.path = path
        self._fh = open(path, "a", encoding="utf-8")

    def write(self, record):
        record.setdefault("ts_utc",
                          time.strftime("%FT%TZ", time.gmtime()))
        self._fh.write(json.dumps(record, ensure_ascii=True) + "\n")
        self._fh.flush()

    def close(self):
        self._fh.close()


def replay_gain(series):
    """Offline: wrap-safe integer gains from a list of scroll_fx values
    (used by tests to validate stall/clear logic without a live core)."""
    out = []
    for a, b in zip(series, series[1:]):
        d = b - a
        if d < -(1 << 24):
            d += 1 << 32
        out.append(d >> 16)
    return out


CLEAR_MIN_SCORE_GAIN = 5000
CLEAR_SCROLL_FROZEN_CHUNKS = 3


def is_clear_candidate(frozen_chunks, best_score_gain):
    """Mission-clear SHAPE detector — deliberately conservative.

    A mission-end tally looks like: scroll frozen for several chunks
    while the score jumps by a large one-off amount.  This is a
    CANDIDATE filter only: it must never be reported as a verified
    clear until the transition is observed with matching tally
    evidence (Issue #4 Phase 6 acceptance rules)."""
    return (frozen_chunks >= CLEAR_SCROLL_FROZEN_CHUNKS and
            best_score_gain >= CLEAR_MIN_SCORE_GAIN)
