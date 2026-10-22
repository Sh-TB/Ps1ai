"""msx_scene.py — the CANONICAL Metal Slug X scene adapter (Issue #5
focused follow-up, Phase 3 + Phase 5).

Problem this fixes (verified in the current call graph):
  * run_semantic.py / run_semantic2.py each augment WorldModel.read_world()
    inline with `threat` / `nearest_enemy` / `n_enemies` / ... — two
    private copies of the same glue.
  * WorldModel.read_world() itself returns the augmented keys ONLY on its
    early-return path (no player anchor); the normal path omits them, so
    any consumer that skips the inline augmentation sees a DIFFERENT
    scene shape for the same RAM.
  * WorldModel.threat() requires horizontal velocity (|vx| > 3): a
    falling bomb with vx ~ 0 is invisible to it. RAM traces from the
    Issue #5 gate probe prove the falling projectiles exist as transient
    entity-table slots (lifetime counter in the HP field 204..254 -> 0,
    the +0x7A word DECREASING as the object falls — height-above-ground
    convention).

This adapter is the ONE place that turns a raw read_world() result into
the documented MSX scene. Every scene-consuming MSX runner must go
through it; no runner may re-implement the glue.

Scene schema (ps1play-msx-scene/1)
----------------------------------
{
  "schema": "ps1play-msx-scene/1",
  "frame": int,                       # observation frame index
  "stale": bool,                      # last valid observation older than
                                      # STALE_FRAMES
  "player":  {"x": int|"unknown", "y": int|"unknown"},
  "enemies": [{"dx","dy","x","y","vx"}, ...]     # validated only
  "projectiles": [
      {"kind": "horizontal"|"falling"|"falling_candidate",
       "dx","dy","vx","x","y","slot"}, ...
  ],
  "n_enemies": int,
  "nearest_enemy": {...}|None,        # None means none OBSERVED
  "threat": {...}|None,               # nearest incoming projectile
  "threat_unknown": bool,             # True when the observation layer
                                      # is NOT certified: threat==None
                                      # then means "nothing seen", and
                                      # consumers must not treat the
                                      # scene as safe-by-default
  "provenance": {"worldmodel": bool, "player_anchor": str|"unknown",
                 "n_slots": int, "dropped_invalid": int,
                 "falling_candidates": int}
}

Rules:
  * missing/invalid fields are the string "unknown", never guessed
  * slots with x==0 or x>=0x10000 or |dx|>0x4000 are dropped (counted)
  * observations older than STALE_FRAMES mark the scene "stale"
  * a falling candidate is promoted only after FALL_CONFIRM_SAMPLES
    consecutive downward moves (>= FALL_MIN_STEP each); it is labelled
    "falling_candidate" until its lifetime-counter behaviour also
    matches (kind stays candidate), and consumers treat it as a threat
  * the shared SemanticPolicy is UNCHANGED: it keeps using threat /
    nearest_enemy / n_enemies. MSX-specific consumers additionally read
    threat_unknown.
"""
from __future__ import annotations

UNKNOWN = "unknown"
STALE_FRAMES = 600          # 10 s without a fresh observation
FALL_MIN_STEP = 2           # min per-sample downward step (field units)
FALL_CONFIRM_SAMPLES = 2    # consecutive downward samples to promote
FALL_MAX_XJITTER = 3        # |vx| gate: falling objects barely drift
LIFETIME_COUNTER_LOW = 204  # MSX transient-slot signature (gate probe)
LIFETIME_COUNTER_HIGH = 254

_SCHEMA = "ps1play-msx-scene/1"


class _SlotHistory:
    """Per-slot y tracker for the falling-candidate detector."""

    __slots__ = ("last_y", "down_streak")

    def __init__(self):
        self.last_y = None
        self.down_streak = 0


class MsxSceneAdapter:
    """Canonical WorldModel -> MSX scene translator."""

    def __init__(self, world_model=None, stale_frames=STALE_FRAMES):
        self.wm = world_model
        self.stale_frames = stale_frames
        self._hist = {}          # slot index -> _SlotHistory
        self._last_valid_frame = None

    # ----------------------------------------------------------------
    def build(self, raw_scene, frame, feat=None):
        """raw_scene: WorldModel.read_world() output (the normal-path
        shape: player/enemies/bullets/items/health). feat: the plugin
        features dict (optional; only used for provenance)."""
        if raw_scene is None:
            raw_scene = {}
        out = {
            "schema": _SCHEMA,
            "frame": frame,
            "stale": (self._last_valid_frame is not None and
                      frame - self._last_valid_frame > self.stale_frames),
            "player": {"x": UNKNOWN, "y": UNKNOWN},
            "enemies": [],
            "bullets": [],          # validated horizontal projectiles
            "projectiles": [],      # horizontal + falling candidates
            "health": [],           # pass-through (validated)
            "items": [],            # pass-through (validated)
            "n_enemies": 0,
            "nearest_enemy": None,
            "threat": None,
            "threat_unknown": False,
            "provenance": {"worldmodel": self.wm is not None,
                           "player_anchor": UNKNOWN,
                           "n_slots": 0,
                           "dropped_invalid": 0,
                           "falling_candidates": 0},
        }

        player = raw_scene.get("player")
        px = py = None
        if isinstance(player, dict):
            px, py = player.get("x"), player.get("y")
            if self._valid_coord(px):
                out["player"]["x"] = px
            if self._valid_coord(py):
                out["player"]["y"] = py
        if self.wm is not None and \
                getattr(self.wm, "player_x_addr", None):
            out["provenance"]["player_anchor"] = hex(self.wm.player_x_addr)

        # stale once the observation stream goes quiet
        has_content = bool(raw_scene.get("enemies") or
                           raw_scene.get("bullets") or px)
        if has_content:
            self._last_valid_frame = frame

        dropped = 0
        enemies = []
        for e in raw_scene.get("enemies") or []:
            if not self._valid_entry(e):
                dropped += 1
                continue
            enemies.append(dict(e))
        out["enemies"] = enemies
        out["n_enemies"] = len(enemies)
        if enemies:
            out["nearest_enemy"] = min(enemies,
                                       key=lambda e: abs(e.get("dx", 0)))
        out["provenance"]["dropped_invalid"] = dropped

        # ---- pass-through lists (validated) --------------------------
        health = [dict(h) for h in raw_scene.get("health") or []
                  if self._valid_entry(h)]
        items = [dict(i) for i in raw_scene.get("items") or []
                 if self._valid_entry(i)]
        out["health"] = health
        out["items"] = items

        # ---- projectiles: validated horizontal bullets ---------------
        projectiles = []
        hbullets = []
        for b in raw_scene.get("bullets") or []:
            if not self._valid_entry(b):
                dropped += 1
                continue
            p = dict(b)
            p["kind"] = "horizontal"
            p["slot"] = b.get("slot")
            projectiles.append(p)
            hbullets.append(dict(b))
        out["bullets"] = hbullets

        # ---- Phase 5: falling-projectile candidates ------------------
        # The world model classifies by X-speed only, so a falling bomb
        # (vx ~ 0) is never a "bullet". The adapter tracks slot y-series
        # itself: slot index = base offset (stable across frames).
        falling = 0
        for s in (raw_scene.get("enemies") or []) + \
                (raw_scene.get("bullets") or []):
            key = s.get("slot")
            if key is None:
                continue
            h = self._hist.setdefault(key, _SlotHistory())
            y = s.get("y")
            if not self._valid_coord(y):
                h.down_streak = 0
                continue
            if h.last_y is not None:
                dy = y - h.last_y
                vx = abs(s.get("vx", 0) or 0)
                if dy <= -FALL_MIN_STEP and vx <= FALL_MAX_XJITTER:
                    h.down_streak += 1
                else:
                    h.down_streak = 0
                if h.down_streak >= FALL_CONFIRM_SAMPLES:
                    p = dict(s)
                    p["kind"] = "falling_candidate"
                    p["dy_fall"] = dy
                    projectiles.append(p)
                    falling += 1
            h.last_y = y
        out["projectiles"] = projectiles
        out["provenance"]["falling_candidates"] = falling

        # ---- threat: nearest horizontal OR falling projectile --------
        # Horizontal: the world-model rule (moving toward the player).
        # Falling: any confirmed candidate above/over the player.
        best = None
        for p in projectiles:
            if p["kind"] == "horizontal":
                dx = p.get("dx", 0)
                vx = p.get("vx", 0)
                toward = (dx > 0 and vx < -3) or (dx < 0 and vx > 3)
                if toward and (best is None or
                               abs(dx) < abs(best.get("dx", 0))):
                    best = p
            else:                                   # falling_candidate
                dx = abs(p.get("dx", 0))
                if dx <= 0x600 and (best is None or
                                    dx < abs(best.get("dx", 0))):
                    best = p
        out["threat"] = best

        # "unknown != safe": without a certified player anchor the
        # world-model scene cannot be trusted to be complete
        if out["provenance"]["player_anchor"] == UNKNOWN:
            out["threat_unknown"] = True
        return out

    # ----------------------------------------------------------------
    @staticmethod
    def _valid_coord(v):
        return isinstance(v, int) and 0 < v < 0x10000

    def _valid_entry(self, e):
        if not isinstance(e, dict):
            return False
        x = e.get("x")
        if not self._valid_coord(x):
            return False
        dx = e.get("dx", 0)
        if not isinstance(dx, int) or abs(dx) > 0x4000:
            return False
        return True

    # ----------------------------------------------------------------
    def annotate_slot(self, raw_scene, slot_index, x, y, vx, hp):
        """Helper for runners: attach a slot index + the observed HP to
        one entity entry so build() can track its y-series."""
        for lst in (raw_scene.get("enemies") or [],
                    raw_scene.get("bullets") or []):
            e = lst[slot_index] if slot_index < len(lst) else None
            if e is not None and e.get("x") == x:
                e["slot"] = slot_index
                e["hp"] = hp
                if vx is not None:
                    e["vx"] = vx
                return True
        return False


def augment(raw_scene, frame, world_model=None, feat=None):
    """One-call convenience: build the canonical scene (module-level
    adapter instance per call site is preferred; this helper exists for
    runners that build scenes inline today)."""
    return MsxSceneAdapter(world_model).build(raw_scene, frame, feat)
