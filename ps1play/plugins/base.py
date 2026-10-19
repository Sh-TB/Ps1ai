"""Plugin system — universal base + one plugin per game.

A plugin teaches the framework three things about ONE game:
  - boot_script(): how to get from power-on to gameplay (learned/persisted)
  - features():    semantic values read from RAM (player pos, score, ...)
  - policy():      a human-like play policy (segments of buttons)

Everything is data + small hooks; the universal core does the rest.
"""
import os
import re


class GamePlugin:
    ID = "generic"
    SERIALS = ()

    def __init__(self, profile):
        self.profile = profile          # dict, persisted per game

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

    def __init__(self, profile):
        super().__init__(profile)
        self.prev_feat = None
        self._recover = 0        # defensive frames after death/hit
        self._hop_cd = 0         # cooldown for casual hops
        self._burst = 0          # fire-burst phase (human tap-fire rhythm)
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


PLUGIN_CLASSES = [MetalSlugXPlugin, GenericPlugin]


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


def detect_plugin(serial):
    for cls in PLUGIN_CLASSES:
        if serial and serial in cls.SERIALS:
            return cls
    return GenericPlugin

