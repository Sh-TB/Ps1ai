"""Plugin system — universal base + one plugin per game.

A plugin teaches the framework three things about ONE game:
  - boot_script(): how to get from power-on to gameplay (learned/persisted)
  - features():    semantic values read from RAM (player pos, score, ...)
  - policy():      a human-like play policy (segments of buttons)

Everything is data + small hooks; the universal core does the rest.
"""
import os
import re

from .contract import (KNOWN_OPS, PluginCapabilities,  # noqa: F401
                       UnsupportedCapabilityError, CONTRACT_VERSION)


class GamePlugin:
    ID = "generic"
    SERIALS = ()
    BOOT_EXE_NAMES = ()             # identity fallback for homebrew discs
    PLUGIN_CONTRACT = CONTRACT_VERSION

    def __init__(self, profile):
        self.profile = profile          # dict, persisted per game

    # ---------- capability negotiation (contract v1) ----------
    # Subclasses opt IN to optional hooks by listing them here; the core
    # calls require(op) before using an optional hook, so an unsupported
    # operation is an explicit error, never a wrong answer.
    OPTIONAL_OPS = ()

    def capabilities(self):
        ops = {"boot_script", "features", "policy", "infer_state"}
        ops |= {o for o in self.OPTIONAL_OPS if o in KNOWN_OPS}
        for name in ("mission_ready",):
            if callable(getattr(self, name, None)) and \
                    getattr(type(self), name) is not GamePlugin.__dict__.get(name):
                ops.add(name)
        return PluginCapabilities(
            game_id=self.ID, serials=tuple(self.SERIALS),
            boot_exe_names=tuple(getattr(self, "BOOT_EXE_NAMES", ())),
            contract_version=getattr(self, "PLUGIN_CONTRACT", CONTRACT_VERSION),
            ops=frozenset(ops))

    def require(self, op):
        """Explicit capability gate — raises instead of pretending."""
        if not self.capabilities().supports(op):
            raise UnsupportedCapabilityError(
                f"plugin {self.ID!r} does not support op {op!r}")
        return True

    # ---------- hooks ----------
    def boot_script(self):
        """Compact default: wait for boot, tap START for ~7s, settle."""
        return [{"op": "wait", "frames": 1000},
                *[{"op": "tap", "btns": "START", "frames": 15, "every": 300}
                  for _ in range(15)],
                {"op": "wait", "frames": 435}]

    def features(self, mem, obs):
        """Semantic dict extracted from RAM. Base: observer stats only."""
        return {"changed_bytes": obs.get("changed_bytes")}

    def policy(self, ctx):
        """ctx: {'t','chunk','stall','feat'} -> list of segments
        [{'frames':n,'btns':set}] covering the chunk."""
        c = ctx["chunk"]
        segs = [{"frames": c - 15, "btns": {"RIGHT"}},
                {"frames": 15, "btns": {"RIGHT", "Y"}}]
        if ctx.get("stall", 0) > 300:
            return [{"frames": 15, "btns": {"START"}},
                    {"frames": c - 15, "btns": {"RIGHT"}}]
        if ctx.get("stall", 0) > 45:
            return [{"frames": 18, "btns": {"RIGHT", "B"}},
                    {"frames": c - 18, "btns": {"RIGHT"}}]
        return segs

    def infer_state(self, obs, feat):
        return "unknown"


class GenericPlugin(GamePlugin):
    ID = "generic"
    SERIALS = ()


class MetalSlugXPlugin(GamePlugin):
    ID = "metal_slug_x"
    SERIALS = ("SLUS-01212", "SLPM-8724", "SLPM-8608")

    # Issue #5 follow-up Phase 7: bounded encounter budget. Combat
    # branches return before the advance branch, so a fight that never
    # resolves consumes the whole mission timer. The policy now tracks
    # chunks with actors nearby but NO verified x progress; past the
    # budget it plays ONE bounded advance window (walk right with the
    # normal fire rhythm) and then resumes combat. Objectives are never
    # abandoned — the window only breaks the infinite repetition.
    ENCOUNTER_BUDGET_FRAMES = 1800     # 30 s of no verified progress
    ADVANCE_WINDOW_FRAMES = 300        # 5 s forced advance per cycle

    def __init__(self, profile):
        super().__init__(profile)
        self.prev_feat = None
        self._recover = 0        # defensive frames after death/hit
        self._hop_cd = 0         # cooldown for casual hops
        self._burst = 0          # fire-burst phase (human tap-fire rhythm)
        self._last_x = None      # encounter-budget progress tracker
        self._no_progress = 0    # frames with actors near but no x gain
        self._advance_left = 0   # remaining forced-advance frames
        self.deaths = 0
        self.hits = 0

    # ---------- zero-token telemetry (GameShark-seeded, read-only) ----------
    def _read_role(self, mem, spec):
        a, dt = spec["addr"], spec.get("dtype", "u16")
        if dt == "u8":
            return mem.u8(a)
        if dt == "u32":
            return mem.u32(a)
        return mem.u16(a)

    def _watch(self, mem):
        out = {}
        for role, spec in (self.profile.get("gsmap") or {}).items():
            if spec and spec.get("verified") and spec.get("addr") is not None:
                try:
                    out[role] = self._read_role(mem, spec)
                except Exception:
                    pass
        return out

    def boot_script(self):
        """Coarse pre-roll only: wait out the BIOS/PS-logo. Everything
        after (NOW LOADING -> SNK/Agetec -> title -> menu -> OK?/YES ->
        radio -> MISSION 1) is handled adaptively by enter_gameplay3's
        screen classifier, because boot timing varies +-1000f per run."""
        cached = self.profile.get("boot_script")
        if cached:
            return cached
        return [{"op": "wait", "frames": 900}]

    def features(self, mem, obs):
        """Rich semantic state — every value from RAM bytes, ZERO tokens."""
        feat = {"changed_bytes": obs.get("changed_bytes")}
        feat.update(self._watch(mem))
        dx = (self.profile.get("discovered") or {}).get("player_x")
        if dx and dx.get("addr") is not None:
            a = dx["addr"]
            feat["x"] = mem.u16(a) if dx.get("dtype") == "u16" else mem.u32(a)
        if feat.get("hp") is not None and feat["hp"] > 200:
            feat["hp_raw_bad"] = feat["hp"]          # watchlist miscalibrated

        # ---- event detection vs previous chunk (delta rules, still 0 tokens)
        ev = []
        prev = self.prev_feat
        if prev:
            if feat.get("hp") is not None and prev.get("hp") is not None:
                d = feat["hp"] - prev["hp"]
                if d < 0:
                    ev.append("hit")
                    self.hits += 1
                elif d > 40:
                    ev.append("healed_or_respawn")
            if feat.get("lives") is not None and prev.get("lives") is not None \
                    and feat["lives"] < prev["lives"]:
                ev.append("death")
                self.deaths += 1
            if feat.get("score") is not None and prev.get("score") is not None \
                    and feat["score"] > prev["score"]:
                ev.append("score_up")
                feat["score_delta"] = feat["score"] - prev["score"]
            if feat.get("bombs") is not None and prev.get("bombs") is not None \
                    and feat["bombs"] < prev["bombs"]:
                ev.append("grenade_used")
            if feat.get("ammo") is not None and prev.get("ammo") is not None \
                    and feat["ammo"] < prev["ammo"]:
                ev.append("shot_fired")
            if feat.get("x") is not None and prev.get("x") is not None:
                feat["vx"] = feat["x"] - prev["x"]
        feat["events"] = ev

        # ---- actor awareness from the entity block (still 0 tokens) ----
        eb = (self.profile.get("entities") or {}).get("main_block")
        if eb and feat.get("x") is not None:
            near = []
            step = eb.get("step", 4)
            for a in range(eb["start"], eb["end"], step):
                v = mem.u32(a)
                if 0 < v < 0x400000:
                    d = v - feat["x"]
                    if abs(d) < 0x4000:
                        near.append(d)
            if near:
                feat["actors_near"] = sum(1 for d in near if abs(d) < 0x2000)
                feat["nearest_actor_dx"] = min(near, key=abs)
        self.prev_feat = {k: v for k, v in feat.items()
                          if k not in ("events",)}
        return feat

    def policy(self, ctx):
        """Human-like reactive play: dodges when hit, restarts after death,
        tap-fires like a real player, hops obstacles, pushes right."""
        c = ctx["chunk"]
        stall = ctx.get("stall", 0)
        feat = ctx.get("feat") or {}
        ev = feat.get("events", [])
        hp = feat.get("hp")
        lives = feat.get("lives")
        bombs = feat.get("bombs")
        actors = feat.get("actors_near") or 0
        segs = []

        # ---- Phase 7: encounter budget bookkeeping -----------------
        x = feat.get("x")
        if x is not None:
            if self._last_x is not None and x == self._last_x:
                self._no_progress += c
            else:
                self._no_progress = 0
            self._last_x = x
        if self._no_progress > self.ENCOUNTER_BUDGET_FRAMES and \
                self._advance_left <= 0:
            self._advance_left = self.ADVANCE_WINDOW_FRAMES
        if self._advance_left > 0:
            # bounded advance window: walk right with the normal fire
            # rhythm (verified progress, not elapsed frames, ends it —
            # any x movement resets the no-progress counter above)
            self._advance_left = max(0, self._advance_left - c)
            if self._advance_left <= 0:
                self._no_progress = 0
            ctx["stall_reset"] = True
            k = min(16, c)
            self._hop_cd = 240
            return [{"frames": k, "btns": {"RIGHT", "B"}},
                    {"frames": max(0, c - k), "btns": {"RIGHT", "Y"}}]

        # ---- 1) death: continue screen / respawn ----
        if "death" in ev or lives == 0 or hp == 0:
            self._recover = 150
            ctx["stall_reset"] = True
            return [{"frames": 20, "btns": {"START"}},
                    {"frames": min(100, c - 20), "btns": set()}]
        # ---- 2) took a hit: dodge like a human (jump + keep moving) ----
        if "hit" in ev and self._recover <= 0:
            self._recover = 60
            k = min(20, c)
            return [{"frames": k, "btns": {"RIGHT", "B"}},
                    {"frames": c - k, "btns": {"RIGHT", "Y"}}]
        if self._recover > 0:
            self._recover -= c
        # ---- 3) stuck too long: hop harder; START is FORBIDDEN -------
        # A START during the mission opens the PAUSE menu, where further
        # stalls navigate toward QUIT -> attract (self-sabotage). Only
        # jump-and-shoot when blocked. (Loading screens: changed_bytes
        # tiny -> hop is harmless there too.)
        if stall >= 600:
            ctx["stall_reset"] = True
            k = min(24, c)
            return [{"frames": k, "btns": {"RIGHT", "B"}},
                    {"frames": k, "btns": {"RIGHT", "B"}},
                    {"frames": max(0, c - 2 * k), "btns": {"RIGHT", "Y"}}]
        # ---- 4) obstacle: hop over ----
        if stall > 90:
            k = min(18, c)
            return [{"frames": k, "btns": {"RIGHT", "B"}},
                    {"frames": c - k, "btns": {"RIGHT", "Y"}}]
        # ---- 5) cluster ahead + bombs: grenade it (humans do) ----
        if actors >= 4 and (bombs or 0) > 2:
            k = min(12, c)
            return [{"frames": k, "btns": {"A"}},
                    {"frames": c - k, "btns": {"RIGHT", "Y"}}]
        # ---- 6) default: advance + human tap-fire rhythm + casual hops ----
        if self._hop_cd > 0:
            self._hop_cd -= c
        left = c
        if self._hop_cd <= 0 and c > 120:
            segs.append({"frames": 16, "btns": {"RIGHT", "B"}})
            left -= 16
            self._hop_cd = 240
        self._burst = (self._burst + c) % 90
        if self._burst < 55:
            segs.append({"frames": left - 20, "btns": {"RIGHT", "Y"}})
        else:
            segs.append({"frames": left - 20, "btns": {"RIGHT"}})
        segs.append({"frames": 20, "btns": {"RIGHT", "Y"}})
        return segs

    def mission_ready(self, mem):
        """True when the mission structures are initialized (hp is a sane
        1..200 instead of 0xFF garbage). GameShark-seeded sanity gate."""
        try:
            spec = (self.profile.get("gsmap") or {}).get("hp")
            addr = spec["addr"] if spec and spec.get("addr") else 0x032764
            hp = mem.u16(addr)
            return 0 < hp <= 200
        except Exception:
            return False

    def infer_state(self, obs, feat):
        hp = feat.get("hp")
        if feat.get("x") is not None and obs.get("changed_bytes", 0) > 64:
            return "gameplay"
        if hp == 0 or feat.get("lives") == 0:
            return "maybe_gameover"
        return "unknown"


class TetradePlugin(GamePlugin):
    """Tetrade (MIT homebrew, Logan Campbell) — second-game vertical slice.

    Exists to prove the plugin contract: a second game must work through
    the shared core WITHOUT touching core implementation code. Semantics
    are minimal by design: boot, prove input causality, survive a menu.
    """
    ID = "tetrade"
    BOOT_EXE_NAMES = ("tetrade.exe",)
    OPTIONAL_OPS = ("detectors",)

    def __init__(self, profile):
        super().__init__(profile)
        self._beat = 0

    def boot_script(self):
        # Homebrew boots in seconds: settle, then a few START/X taps to
        # pass any 'press start' / mode-select screen. Over-tapping is
        # harmless in a menu-driven puzzle game.
        steps = [{"op": "wait", "frames": 180}]
        for _ in range(6):
            steps.append({"op": "tap", "btns": "START", "frames": 12,
                          "every": 90})
        steps.append({"op": "wait", "frames": 180})
        return steps

    def features(self, mem, obs):
        return {"changed_bytes": obs.get("changed_bytes")}

    def policy(self, ctx):
        # Deterministic play beat: nudge, drop, rotate — exercises the
        # full pad without needing game-specific RAM knowledge.
        c = ctx["chunk"]
        self._beat = (self._beat + 1) % 3
        if self._beat == 0:
            return [{"frames": min(20, c), "btns": {"RIGHT"}},
                    {"frames": max(0, c - 20), "btns": set()}]
        if self._beat == 1:
            return [{"frames": min(12, c), "btns": {"X"}},
                    {"frames": max(0, c - 12), "btns": set()}]
        return [{"frames": min(30, c), "btns": {"DOWN"}},
                {"frames": max(0, c - 30), "btns": set()}]

    def infer_state(self, obs, feat):
        if obs.get("changed_bytes", 0) > 16:
            return "gameplay"
        return "unknown"


class PowerPlayTriviaPlugin(GamePlugin):
    """Power Play — Sports Trivia (SLUS-01445): turn-based quiz, the
    cheapest full-game loop there is. Menu flow (verified frame-exact):
    title(START) -> SELECT A SPORT(x, ALL) -> SELECT A GAME(x, Tournament)
    -> HOW MANY PLAYERS(x, 1) -> controller check(x Continue)
    -> name entry(square adds 'A' x3, x Accept) -> icon select(x)
    -> quiz: question -> x locks answer -> feedback -> next question.
    Round/score screens are passed with x / START on stall."""
    ID = "power_play_trivia"
    SERIALS = ("SLUS-01445",)

    ANSWER_PERIOD = 450      # frames between answer taps (7.5 s, human pace)
    MENU_STALL_START = 1800  # static screen this long -> press START

    def __init__(self, profile):
        super().__init__(profile)
        self._answer_cd = 0      # frames until next answer tap
        self.answers = 0
        self.starts = 0

    def boot_script(self):
        cached = self.profile.get("boot_script")
        if cached:
            return cached

        def tap(btns, gap):
            # press + EXPLICIT release + idle gap. core.run() keeps the
            # last button set held when called with buttons=None, so a
            # bare tap op would turn into a long hold (verified bug).
            return [{"op": "tap", "btns": btns, "frames": 15},
                    {"op": "tap", "btns": "", "frames": 1},
                    {"op": "wait", "frames": max(0, gap - 16)}]

        steps = [{"op": "wait", "frames": 1800}]           # title
        steps += tap("START", 700)                          # title -> sport
        steps += tap("B", 900)                              # sport: ALL
        steps += tap("B", 900)                              # game: tournament
        steps += tap("B", 900)                              # players: 1
        steps += tap("B", 900)                              # controller check
        for _ in range(3):                                  # name 'AAA'
            steps += tap("SQ", 415)
        steps += tap("B", 1500)                             # name accept
        steps += tap("B", 1500)                             # icon accept
        steps += [{"op": "wait", "frames": 600}]            # Q1 fade-in
        return steps

    def features(self, mem, obs):
        # bucketed activity doubles as the watched value so AgentLoop's
        # stall counter freezes exactly when the screen is static
        cb = obs.get("changed_bytes") or 0
        return {"changed_bytes": cb,
                "x": cb // 100,
                "answers": self.answers}

    def policy(self, ctx):
        """Quiz rhythm: read the question, tap x to lock, wait out the
        feedback. A STATIC screen (changed_bytes tiny) gets START — that
        covers round-results / trophy screens where x does nothing.
        The orchestrator re-enters from the title via boot_script()."""
        c = ctx["chunk"]
        changed = (ctx.get("obs") or {}).get("changed_bytes") or 0
        static = changed < 500
        segs = []
        left = c
        if static:
            # results / round-over screens: START advances them
            self.starts += 1
            k = min(15, left)
            segs.append({"frames": k, "btns": {"START"}})
            left -= k
            if left > 0:
                segs.append({"frames": left, "btns": set()})
            return segs
        if self._answer_cd > 0:
            k = min(self._answer_cd, left)
            segs.append({"frames": k, "btns": set()})
            self._answer_cd -= k
            left -= k
        if left <= 0:
            return segs
        # answer now (lock the highlighted choice like a human slamming x)
        self._answer_cd = self.ANSWER_PERIOD
        self.answers += 1
        k = min(15, left)
        segs.append({"frames": k, "btns": {"B"}})
        left -= k
        if left > 0:
            segs.append({"frames": left, "btns": set()})
        return segs

    def infer_state(self, obs, feat):
        cb = obs.get("changed_bytes", 0) or 0
        if cb > 20000:
            return "quiz_active"
        return "unknown"


from .tetrade_play import TetradePlayPlugin  # noqa: E402 (circular-free)
from .psxmc_play import PSXMCPlayPlugin      # noqa: E402 (circular-free)
from .poy_poy import PoyPoyPlugin            # noqa: E402 (circular-free)


PLUGIN_CLASSES = [MetalSlugXPlugin, TetradePlugin, TetradePlayPlugin,
                  PSXMCPlayPlugin, PoyPoyPlugin, PowerPlayTriviaPlugin,
                  GenericPlugin]


def parse_serial(cue_path):
    """Read the .bin, return 'SLUS-01212' style serial from SYSTEM.CNF."""
    bin_path = None
    try:
        with open(cue_path, "r", errors="replace") as f:
            for line in f:
                if line.strip().upper().startswith("FILE"):
                    bin_path = line.split('"')[1]
                    break
    except OSError:
        return None
    if bin_path:
        cand = os.path.join(os.path.dirname(cue_path), bin_path)
        if os.path.exists(cand):
            cue_path = cand
    try:
        with open(cue_path, "rb") as f:
            head = f.read(256 * 1024)
    except OSError:
        return None
    m = re.search(rb"(S[CL][EU][SLP]_[0-9]{3}\.[0-9]{2})", head)
    if not m:
        return None
    s = m.group(1).decode()
    return s[:4] + "-" + s[5:].replace(".", "")


def read_boot_exe(cue_path):
    """Return the lowercase BOOT=cdrom:<exe> name from the disc image.

    Homebrew discs carry no SLUS_/SLPM_ serial, so SYSTEM.CNF's BOOT line
    is the identity fallback. Handles MODE2/2352 (user data at offset 24
    per 2352-byte sector) and plain 2048-byte images.
    """
    bin_path = None
    try:
        with open(cue_path, "r", errors="replace") as f:
            for line in f:
                if line.strip().upper().startswith("FILE"):
                    bin_path = line.split('"')[1]
                    break
    except OSError:
        return None
    path = os.path.join(os.path.dirname(cue_path), bin_path) \
        if bin_path else cue_path
    if not os.path.exists(path):
        return None
    try:
        with open(path, "rb") as f:
            raw = f.read(256 * 1024)
    except OSError:
        return None
    m = re.search(rb"BOOT\s*=\s*cdrom:\\?([^\r\n;]+?);?[0-9]*\s*\r?\n",
                  raw, re.IGNORECASE)
    if not m:
        m = re.search(rb"BOOT\s*=\s*cdrom:\\?([^\r\n;]+)", raw,
                      re.IGNORECASE)
    return m.group(1).decode(errors="replace").strip().lower() if m else None


def detect_plugin(serial, cue_path=None):
    for cls in PLUGIN_CLASSES:
        if serial and serial in cls.SERIALS:
            return cls
    if cue_path:
        boot = read_boot_exe(cue_path)
        for cls in PLUGIN_CLASSES:
            if boot and boot in tuple(getattr(cls, "BOOT_EXE_NAMES", ())):
                return cls
    return GenericPlugin

