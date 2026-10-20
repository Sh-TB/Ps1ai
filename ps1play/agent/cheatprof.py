"""cheatprof.py — cheat experiment classes with HARD profile isolation.

Issue #2 requires two independent execution profiles:

  CHEAT_ASSISTED_EXPLORATION — only individually VERIFIED codes, only
        after the operator explicitly opts in (--opt-in / opt_in=True).
  LEGIT_CONTROLLER_RUN      — ordinary controller input; ANY cheat is a
        hard violation. Every legit run calls assert_clean() before and
        after; the interval log must stay empty.

The engine underneath is ps1play.agent.gameshark.GameShark (per-frame
RAM patching over the live libretro SYSTEM_RAM view — the same behavior
as hardware GameShark/PAR). This module adds the policy layer:

  * explicit opt-in (a cheat-assisted session cannot exist silently)
  * registry-backed code selection (CANDIDATE codes are refused)
  * per-interval cheat activity log (which cheats, exact frames)
  * no-cheat assertion for legit runs

Copyright addresses live in data/games/<serial>/cheats.json (registry);
this module never hard-codes game addresses.
"""
import json
import os
import time
from copy import deepcopy

from ps1play.agent.gameshark import GameShark, GSCode

CHEAT_ASSISTED = "CHEAT_ASSISTED_EXPLORATION"
LEGIT = "LEGIT_CONTROLLER_RUN"
PROFILES = (CHEAT_ASSISTED, LEGIT)

# registry statuses (issue section 9)
ST_CANDIDATE = "CANDIDATE"
ST_TESTED = "TESTED"
ST_VERIFIED = "VERIFIED"
ST_FAILED = "FAILED"
ST_BLOCKED = "BLOCKED"
STATUSES = (ST_CANDIDATE, ST_TESTED, ST_VERIFIED, ST_FAILED, ST_BLOCKED)


class ProfileViolation(Exception):
    """Raised when a run violates its own profile contract."""


class CheatSession:
    """Opt-in cheat runner for CHEAT_ASSISTED_EXPLORATION.

    LEGIT_CONTROLLER_RUN sessions refuse every enable() and expose
    assert_clean(); CHEAT_ASSISTED sessions require opt_in=True at
    construction time — there is no way to enable a code without it.
    """

    def __init__(self, play, profile, opt_in=False, gs=None):
        if profile not in PROFILES:
            raise ProfileViolation(
                f"unknown profile {profile!r} — expected one of "
                f"{', '.join(PROFILES)}")
        if profile == CHEAT_ASSISTED and not opt_in:
            raise ProfileViolation(
                "CHEAT_ASSISTED_EXPLORATION requires an explicit operator "
                "opt-in (opt_in=True / --opt-in). Default gameplay must "
                "never silently apply cheats.")
        self.play = play
        self.profile = profile
        self.gs = gs if gs is not None else GameShark(play.mem)
        # frame interval log: exactly which cheats were active when
        self._active = frozenset()
        self._interval_open = None      # (frame_start, names)
        self.intervals = []             # [{start,end,cheats}]
        self.enable_log = []

    # ---------------- contract checks ----------------
    def assert_clean(self, where=""):
        """LEGIT hard gate: no cheat may be active. Raises on violation."""
        if self.gs.enabled:
            names = ", ".join(sorted(self.gs.enabled))
            raise ProfileViolation(
                f"LEGIT_CONTROLLER_RUN violation{f' at {where}' if where else ''}:"
                f" active cheats [{names}] — a legit run must use only "
                "ordinary controller input")
        return True

    # ---------------- code management ----------------
    def enable(self, name, codes):
        """Enable a named cheat (list of GSCode or raw strings). Only
        cheat-assisted sessions may call this."""
        if self.profile == LEGIT:
            raise ProfileViolation(
                "LEGIT_CONTROLLER_RUN refuses cheat activation — use "
                "profile CHEAT_ASSISTED_EXPLORATION with an explicit "
                "opt-in for cheat experiments")
        parsed = [c if isinstance(c, GSCode) else GSCode(c) for c in codes]
        self._close_interval()
        self.gs.enable(name, parsed)
        self._active = frozenset(n for n in self.gs.enabled)
        self._open_interval()
        self.enable_log.append(
            {"t": time.strftime("%H:%M:%S"), "op": "enable", "name": name,
             "codes": [c.raw for c in parsed]})
        return True

    def disable(self, name):
        self._close_interval()
        ok = self.gs.disable(name)
        self._active = frozenset(self.gs.enabled)
        self._open_interval()
        if ok:
            self.enable_log.append(
                {"t": time.strftime("%H:%M:%S"), "op": "disable",
                 "name": name})
        return ok

    def disable_all(self):
        self._close_interval()
        self.gs.disable_all()
        self._active = frozenset()
        self._open_interval()

    # ---------------- per-frame application ----------------
    def tick(self, frame=None):
        """Call once after every core.run_frame() while running."""
        self.gs.tick()
        now = frozenset(self.gs.enabled)
        if now != self._active:
            self._close_interval(frame)
            self._active = now
            self._open_interval(frame)

    def run_frames(self, frames, buttons):
        """Run `frames` with the session ticking each frame (hardware GS
        cadence) and frame accounting via play.t."""
        f0 = self.play.t
        self.play.core.set_buttons(buttons)
        for _ in range(frames):
            self.play.core.run_frame()
            self.tick(frame=self.play.t)
        return self.play.t - f0

    # ---------------- interval bookkeeping ----------------
    def _open_interval(self, frame=None):
        self._interval_open = (
            self.play.t if frame is None else frame,
            sorted(self._active))

    def _close_interval(self, frame=None):
        if self._interval_open is None:
            return
        start, names = self._interval_open
        end = self.play.t if frame is None else frame
        if end > start or names:
            self.intervals.append({"start": int(start), "end": int(end),
                                   "cheats": names})
        self._interval_open = None

    def finalize_intervals(self):
        self._close_interval()
        return list(self.intervals)

    def active_names(self):
        return sorted(self._active)


def derive_freeze_code(play, addr, value=None, dtype="u16"):
    """Build a freeze GSCode for a LIVE-ANCHORED address.

    u16 -> w16 code 8XXXXXXX YYYY; u8 -> w8 code 3XXXXXXX 00YY.
    The player-state cluster is dynamically placed per boot, so derived
    freeze codes are re-derived from fresh, event-verified anchors at
    every run (never copied across boots)."""
    if dtype == "u8":
        v = int(play.mem.u8(addr)) if value is None else int(value)
        return GSCode(f"3{addr:07X} 00{v & 0xFF:02X}"), v
    v = int(play.mem.u16(addr)) if value is None else int(value)
    return GSCode(f"8{addr:07X} {v & 0xFFFF:04X}"), v


def quick_verify_freeze(play, session, code, addr, base_state,
                        action=frozenset(), frames=120,
                        pre=15, post=90, dtype="u16"):
    """One-shot baseline/treatment check for a derived freeze code.

    baseline: from base_state, `action` moves the counter
    treatment: with the code enabled (ticked per frame), it cannot
    Both arms start from the SAME savestate. Restores base_state.
    Returns {"works", "baseline", "treatment", "addr", "code"}.
    """
    read = play.mem.u8 if dtype == "u8" else play.mem.u16

    def arm(with_code):
        play.load_state(base_state)
        play.core.run(10, frozenset())
        v0 = read(addr)
        if with_code:
            session.enable("_qvfz", [code])
        play.core.set_buttons(set(action))
        for _ in range(pre):
            play.core.run_frame()
            if with_code:
                session.gs.tick()
        play.core.set_buttons(frozenset())
        for _ in range(frames):
            play.core.run_frame()
            if with_code:
                session.gs.tick()
        play._advance()
        v1 = read(addr)
        if with_code:
            session.disable("_qvfz")
        return [int(v0), int(v1)]

    base = arm(False)
    treat = arm(True)
    play.load_state(base_state)
    works = bool(base[0] != base[1] and treat[0] == treat[1])
    return {"works": works, "baseline": base, "treatment": treat,
            "addr": hex(addr), "code": code.raw}


class CheatRegistry:
    """Machine-readable registry for one game revision
    (data/games/<serial>/cheats.json)."""

    REQUIRED_FIELDS = ("name", "effect", "codes", "status")

    def __init__(self, path, entries=None):
        self.path = path
        # deep copy: callers may pass a loaded JSON dict they also use
        # elsewhere; status updates must never leak across instances
        self.entries = deepcopy(entries) if entries else {}

    # -------------- IO --------------
    @classmethod
    def load(cls, path):
        if not os.path.exists(path):
            return cls(path, {})
        with open(path) as f:
            data = json.load(f)
        entries = data.get("cheats", data) if isinstance(data, dict) else {}
        reg = cls(path, entries)
        # preserve the full document (game identity, mechanism notes,
        # provenance) so status updates round-trip without data loss
        meta = {k: v for k, v in data.items()
                if k not in ("cheats", "schema", "updated")} \
            if isinstance(data, dict) else {}
        reg.meta = meta
        return reg

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        payload = dict(getattr(self, "meta", {}))
        payload["schema"] = "ps1play-cheat-registry/1"
        payload["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        payload["cheats"] = self.entries
        with open(self.path, "w") as f:
            json.dump(payload, f, indent=1, sort_keys=True)

    # -------------- queries --------------
    def validate(self):
        """Structural check; returns list of problems (empty = ok)."""
        problems = []
        for name, e in self.entries.items():
            for field in self.REQUIRED_FIELDS:
                if field not in e:
                    problems.append(f"{name}: missing field {field}")
            if e.get("status") not in STATUSES:
                problems.append(f"{name}: bad status {e.get('status')!r}")
            if not e.get("codes"):
                problems.append(f"{name}: no code lines")
        return problems

    def verified_names(self):
        return sorted(n for n, e in self.entries.items()
                      if e.get("status") == ST_VERIFIED)

    def codes_for(self, names, require_verified=True):
        """Resolve names -> list of (name, raw_code). Refuses anything
        that is not VERIFIED when require_verified — a CANDIDATE code is
        a hypothesis, not a usable cheat (issue sections 2/4/9)."""
        out = []
        for name in names:
            e = self.entries.get(name)
            if e is None:
                raise ProfileViolation(
                    f"cheat {name!r} not in registry {self.path}")
            if require_verified and e.get("status") != ST_VERIFIED:
                raise ProfileViolation(
                    f"cheat {name!r} has status {e.get('status')!r} — "
                    "only VERIFIED codes may drive "
                    "CHEAT_ASSISTED_EXPLORATION")
            for raw in e["codes"]:
                out.append((name, raw))
        return out

    def update_status(self, name, status, evidence=None, **fields):
        if status not in STATUSES:
            raise ValueError(f"bad status {status!r}")
        e = self.entries.setdefault(name, {"codes": []})
        e["status"] = status
        if evidence:
            e.setdefault("evidence", []).append(
                {"t": time.strftime("%Y-%m-%d %H:%M:%S"), **evidence})
        e.update(fields)
        e["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")


def verify_survival_freeze(play, session, code, addr, base_state,
                           frames=300):
    """In-run check for a survival (HP) freeze.

    The anchor itself (perception.find_player_hp) already proved that
    freezing THIS word at THIS value keeps the player alive through a
    danger window where the baseline dies. This check only proves the
    code MECHANISM applies in this run: with the code enabled, after a
    danger window the word still reads the frozen value and the game is
    still input-responsive. Baseline damage is recorded as context but
    never gates (enemies may not reach the player in a given window).
    """
    play.load_state(base_state)
    play.core.run(10, frozenset())
    session.enable("_svz", [code])
    for _ in range(2):
        play.core.run_frame()
        session.gs.tick()
    frozen = int(play.mem.u16(addr))
    play.core.set_buttons(frozenset())
    for _ in range(frames):
        play.core.run_frame()
        session.gs.tick()
    play._advance()
    end_val = int(play.mem.u16(addr))
    from mission import responsive
    alive, gate = responsive(play)
    session.disable("_svz")
    play.load_state(base_state)
    return {"works": bool(end_val == frozen and alive),
            "frozen_value": frozen, "end_value": end_val,
            "alive": bool(alive), "gate": list(gate),
            "addr": hex(addr), "code": code.raw}
