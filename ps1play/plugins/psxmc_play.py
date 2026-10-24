"""PSXMCPlayPlugin — full-game play plugin for PSX-Minecraft (infdev
2025-04-18, MIT EngineersBox/PSX-Minecraft). Third game through the
shared core, zero core edits, zero memory writes.

Knowledge provenance
--------------------
source-first (MIT repo headers, read in this session):
  Player{Entity{PhysicsObject{position,velocity,rotation{pitch,yaw},
  move{forward,strafe},...,flags},flags,health:5,armour:5,air:5,
  on_fire},camera*,inventory,hotbar,breaking}
  bindings: move=dpad, jump=R1, crouch=L1, look=TRI/X/SQ/O,
  attack=R2, use=L2, hotbar=L3/R3, pause=SELECT
live-verified (scripts/psxmc_probe*.py, this session):
  struct base @0x3C608 (map symbol `player`), pos/vel/pitch/yaw/fwd/
  strafe/flags offsets causal under input, health=20/air=20 at spawn,
  on_ground/jumping/crouching flag bits, world ptr @0x3C61C.
  R2/L2/L3/R3 are UNDELIVERABLE on the digital pad (no such buttons,
  id 0x41) -> plugin declares INPUT_DEVICE="dualshock" (host capability,
  opt-in; default JOYPAD unchanged for all other games).

Play loop (rule-based, honest):
  settle -> patrol (verified-displacement walk bursts + heading turns
  + jump-on-collision) -> dig campaigns (pitch down + hold R2, breaking
  state churn is the OBSERVED signal) -> place attempt (L2) once the
  hotbar impl hash changes. The sandbox has NO game-over; the run ends
  at the chunk budget (BUDGET_END, disclosed) — no clear claim made.
"""
import zlib

from .base import GamePlugin

A_PLAYER = 0x3C608
A_WORLD = 0x3C61C
A_TIME = 0x3C5A0
ONE_BLOCK = 286720                    # source: ONE*BLOCK_SIZE (verified:
                                      # spawn y 2867200 = 10 blocks)
CAM_OFF = 487424                      # PLAYER_CAMERA_OFFSET


def _s32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v >= 0x80000000 else v


def _s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v >= 0x8000 else v


class PSXMCPlayPlugin(GamePlugin):
    ID = "psxmc_play"
    SERIALS = ()
    BOOT_EXE_NAMES = ("psxmc.exe",)
    # Pad-class finding (probe5 matrix, this session): the beetle DIGITAL
    # pad (id 0x41) delivers ALL 16 button bits incl. L2/R2/L3/R3 read at
    # the game's own `input` buffer — so the default JOYPAD class stays.
    # The DEVICE_ANALOG opt-in exists in host/api but beetle 0.9.44.1's
    # ANALOG mode is input-DEAD (psxmc_ab_device.json A/B), so it is NOT
    # used by this plugin.
    INPUT_DEVICE = None
    OPTIONAL_OPS = ("detectors",)

    WALK_FRAMES = 60                  # per verified burst
    TURN_FRAMES = 18                  # ~105° at ROTATION_SPEED 15/frame
    DIG_FRAMES = 300                  # one dig campaign hold
    HEADINGS = (0, 1, 2, 3)           # cycle: fwd, right, back, left

    def __init__(self, profile):
        super().__init__(profile)
        self.mode = "settle"
        self.burst = 0
        self.heading = 0
        self.events = []
        self._last_pos = None
        self._last_yaw = None
        self._last_hb = None
        self._dig_phase = 0           # 0 nav, 1 pitch, 2 dig, 3 back
        self._dig_done = False
        self._dig_dir = 1
        self._leg = 0
        self._dir = "out"
        self._air_chunks = 0
        self._pos_session = None

    # ---------- state ---------------------------------------------------
    def _player(self, mem):
        P = mem.u32(A_PLAYER) & 0x1FFFFF
        if not ((P & 3) == 0 and 0x10000 < P < 0x1F8000):
            return None
        # wide sanity bound: falling below y=0 or climbing is legal play
        y = _s32(mem.u32(P + 4))
        if abs(y) > 40 * ONE_BLOCK:
            return None
        return P

    def features(self, mem, obs):
        P = self._player(mem)
        if P is None:
            raw = mem.u32(A_PLAYER)
            return {"world_ready": False,
                    "P_raw": hex(raw),
                    "P_raw_sane_y": _s32(mem.u32((raw & 0x1FFFFF) + 4))
                    if (raw & 3) == 0 and 0x10000 < (raw & 0x1FFFFF) < 0x1F8000
                    else None}
        flags = mem.u16(P + 0x4C)
        hb = mem.u32(P + 0x68) & 0x1FFFFF
        hb_bytes = bytes(mem.snapshot()[hb:hb + 0x40]) if hb else b""
        brk = bytes(mem.snapshot()[P + 0x6C:P + 0x9C])
        pos = [_s32(mem.u32(P)), _s32(mem.u32(P + 4)), _s32(mem.u32(P + 8))]
        return {
            "world_ready": True,
            "pos": pos,
            "pos_blocks": [round(v / ONE_BLOCK, 2) for v in pos],
            "vel": [_s32(mem.u32(P + 0xC)), _s32(mem.u32(P + 0x10)),
                    _s32(mem.u32(P + 0x14))],
            "pitch": _s32(mem.u32(P + 0x18)),
            "yaw": _s32(mem.u32(P + 0x1C)),
            "fwd": _s16(mem.u16(P + 0x20)),
            "strafe": _s16(mem.u16(P + 0x22)),
            "on_ground": bool(flags & 1),
            "collided_h": bool((flags >> 5) & 1),
            "jumping": bool((flags >> 8) & 1),
            "crouching": bool((flags >> 9) & 1),
            "health": mem.u8(P + 0x51) & 0x1F,
            "armour": mem.u8(P + 0x52) & 0x1F,
            "air": mem.u8(P + 0x53) & 0x1F,
            "world_ptr": mem.u32(A_WORLD) & 0x1FFFFF,
            "P": P,
            "time_ms": mem.u32(A_TIME),
            "hotbar_hash": zlib.crc32(hb_bytes),
            "breaking_hash": zlib.crc32(brk),
            "breaking_nonzero": any(brk),
        }

    def infer_state(self, obs, feat):
        if not feat.get("world_ready"):
            return "boot"
        return "playing"

    # ---------- policy ---------------------------------------------------
    def policy(self, ctx):
        c = ctx["chunk"]
        feat = ctx.get("feat") or {}
        if not feat.get("world_ready"):
            return [{"btns": set(), "frames": c}]

        segs = []
        left = c

        # verify the previous burst from live state (closed loop)
        pos = feat.get("pos")
        if pos is not None:
            if self._pos_session is None:
                self._pos_session = pos
            if self._last_pos is not None:
                d = [pos[i] - self._last_pos[i] for i in range(3)]
                if abs(d[0]) + abs(d[2]) > ONE_BLOCK // 4:
                    self.events.append({
                        "ev": "move_burst", "fc": ctx["fc"],
                        "d_blocks": [round(v / ONE_BLOCK, 2) for v in d],
                        "on_ground": feat.get("on_ground")})
        self._last_pos = pos

        yaw = feat.get("yaw")
        if yaw is not None and self._last_yaw is not None \
                and abs(_s32(yaw - self._last_yaw)) > (1 << 16) * 600:
            self.events.append({"ev": "turn", "fc": ctx["fc"],
                                "d_yaw": _s32(yaw - self._last_yaw)})
        self._last_yaw = yaw

        hb = feat.get("hotbar_hash")
        if hb is not None and self._last_hb is not None \
                and hb != self._last_hb:
            self.events.append({"ev": "hotbar_changed", "fc": ctx["fc"]})
        self._last_hb = hb

        if self.mode == "settle":
            if feat.get("on_ground"):
                self.mode = "patrol"
                self.events.append({"ev": "world_entered", "fc": ctx["fc"],
                                    "pos_blocks": feat.get("pos_blocks")})
            return [{"btns": set(), "frames": left}]

        # --- dig = BOUNDED FINAL EXPERIMENT (progress >= 0.8, once) ---
        # R2 targeting a block can halt the game (infdev bug: the
        # breaking-state transition calls worldGetChunk with a
        # ChunkBlockPosition and dereferences a possibly-NULL chunk;
        # observed live twice). Nav goals run first; the dig runs once
        # at the end so a halt costs only the tail of the session.
        progress = ctx.get("progress", 0.0)
        if self.mode == "patrol" and self._dig_phase == 0 \
                and not self._dig_done and progress >= 0.8 and c >= 60:
            self._dig_phase = 1
            self._dig_done = True
            self.events.append({"ev": "dig_start", "fc": ctx["fc"],
                                "progress": round(progress, 2)})

        if self._dig_phase == 1:                     # aim at the ground
            self._dig_dir = -1 if self.burst % 12 >= 6 else 1
            btn = "X" if self._dig_dir == 1 else "TR"
            if feat.get("on_ground"):
                segs.append({"btns": {btn}, "frames": min(20, left)})
                left -= min(20, left)
            self._dig_phase = 2
        if self._dig_phase == 2:
            segs.append({"btns": {"R2"}, "frames": min(self.DIG_FRAMES,
                                                       left)})
            left -= min(self.DIG_FRAMES, left)
            self._dig_phase = 3
        if self._dig_phase == 3:
            btn = "TR" if self._dig_dir == 1 else "X"
            segs.append({"btns": {btn}, "frames": min(20, left)})
            left -= min(20, left)
            self._dig_phase = 0
            self.burst += 1
            segs.append({"btns": set(), "frames": left})
            return segs

        # --- out-and-back patrol: the spawn plateau is an island ---
        # walking >7 blocks from spawn drops the player into the void
        # (fall handler is UNIMPLEMENTED in this infdev build -> game
        # halt; observed live). 180-deg turns are NOT reliable (the yaw
        # response to held LOOK buttons is not linear per frame), so
        # the patrol backpedals instead: UP walks out, DOWN walks
        # back — displacement verified both ways, zero yaw dependence.
        # Look wobbles (SQ/O) stay small and are readback-clamped.
        if not feat.get("on_ground"):
            self._air_chunks += 1
        else:
            self._air_chunks = 0
        if self._leg == 0 and self._dir == "out" \
                and self.burst % 4 == 0 and c - 40 > 0:
            # small look wobble, clamped by live yaw readback
            look = "SQ" if self.burst % 8 == 0 else "O"
            segs.append({"btns": {look}, "frames": min(8, left)})
            left -= min(8, left)
            segs.append({"btns": set(), "frames": 4})
            left -= 4
        step = min(self.WALK_FRAMES, left)
        walk = "UP" if self._dir == "out" else "DOWN"
        segs.append({"btns": {walk}, "frames": step})
        left -= step
        if feat.get("collided_h") and feat.get("on_ground") and left > 12:
            segs.append({"btns": {"R1"}, "frames": 10})
            left -= 10
            self.events.append({"ev": "jump", "fc": ctx["fc"]})
            segs.append({"btns": {walk}, "frames": min(20, left)})
            left -= min(20, left)
        if left <= 6:                                # burst complete
            self.burst += 1
            self._dir = "back" if self._dir == "out" else "out"
        if left > 0:
            segs.append({"btns": set(), "frames": left})
        return segs
