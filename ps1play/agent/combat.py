"""combat.py — entity-aware combat/traversal policy for MSX Mission 1
(Issue #5 focused follow-up, session 3: user gameplay feedback).

USER-REPORTED DEFECTS this policy fixes (instrument-verified in
probe0_addresses.json):
  D1  walks THROUGH enemies without killing them (probe: 400f walk,
      score 0, HP 144->36, enemies passed on both sides)
  D2  dies with enemies BEHIND (probe: live slots at x 770-812 while
      player walked on at 838 — the "jeep behind" geometry)
  D3  keeps advancing after the section end-clamp instead of turning
      back to clear the rear (jeep / grenadier / chopper zone)
  D4  never faces the nearest threat — movement is fixed-RIGHT with a
      binary forward/back, independent of where enemies are

ADDRESS GROUND TRUTH (probe0 + Issues #3/#5, all RAM offsets):
  PLAYER_X   u32 fixed 16.16 @0x0CA2E0   (slot0+0x78; px = >>16)
             — moves at walk speed both directions (VERIFIED probe0)
  PLAYER_HP  u16 @0x0CA2F6               (slot0+0x8E; 144->36 damaged)
  ENTITY_TBL base 0x0CA268 stride 0x14C, slots 1..39:
             X = u32 @+0x78 (px >>16), HP = u16 @+0x8E
             enemy HP window 1..600 (352 = armored vehicle observed;
             hp>32767 = signed-negative transients, EXCLUDED)

STAGE-END IS DERIVED, NEVER A MAP CONSTANT: while the policy holds
RIGHT (progress intent) the player X must advance; when it stops
advancing across consecutive chunks the section is end-clamped — that
is the "map ends here" signal from game state alone. Response: stop
advancing, walk back, clear the rear zone, bounded up-left fire at
the rain-source/chopper area (w2_chopper_hp protocol B pattern).

PROJECTILE CLASSIFICATION (Issue-5 session-2 decode + heli-ladder
trace, both post-reader-fix): falling mortar shells occupy transient
table slots whose HEIGHT word u16 @slot+0x7E accelerates down to the
ground-contact value 64 (observed drop h128->64 in 1 frame; X stays
fixed-point px @+0x78). Their HP field is a PHASE/FUSE tag
(194/92/73/42 in flight; 352->101 fuse decay armed) — NOT enemy HP.
Rule: slot height > GROUND_HEIGHT = "projectile_air" -> never an
engage target; a near airborne shell triggers an immediate hop.
Disclosed limit: the ARMED GROUND-CREEP phase (h==64, creeping,
fuse-decay HP) is height-indistinguishable from a ground entity and
is NOT classified — the hop cadence + corridor movement remain the
only defenses there (heli-ladder patterns 1/2/10).

MID-RUN REAR CHECK (mission case 2: enemy behind -> TURN, engage,
RESUME): instrumented A/B (session 3) proved walking back into the
pursuit pack is the death pattern (v4) and standing still is death
(v3), yet every baseline death was rear-related. Compromise encoded
here: a CLOSE rear enemy (<= REAR_CHECK_X) that PERSISTS across
REAR_CHECK_PERSIST consecutive chunks triggers ONE bounded rear-check
chunk — a short LEFT tap to turn, standing LEFT-facing fire, dodge
hop — then the run-through backbone resumes. Bounded 1-in-N standing
exposure, never a walk-toward.

STALE-OBSERVATION INVALIDATION (mission case 8): a chunk-to-chunk
player-X jump larger than RESPAWN_JUMP_PX (normal walking covers
<40 px per 60f chunk) can only be a respawn / recovery / segment
change -> all wall/escalation/engage/pursuer state is stale and is
reset before the next decision.

SCENE/SCAN CONTRACT (ps1play-combat-scan/1):
  scan_entities() returns a list of {"slot","x_px","dx_px","hp",
  "kind"} for live enemies + airborne projectiles of the PLAYER only
  (slot 0 excluded), sorted by |dx|. kind: "enemy" | "projectile_air".
  The policy is a pure function of the scan + counters (unit-testable
  offline, no emulator).
"""
from __future__ import annotations

# ---- verified RAM geometry -------------------------------------------
PLAYER_X = 0x0CA2E0          # u32 fixed 16.16 -> px = raw >> 16
PLAYER_HP = 0x0CA2F6         # u16
TABLE = 0x0CA268
STRIDE = 0x14C
SLOTS = 40                   # slot 0 = player, 1..39 = world entities
ENEMY_HP_MAX = 600           # 352-armored-vehicle observed; 600 covers
ENEMY_HP_SIGNED = 32768      # hp >= this = transient tag, not an enemy

# ---- engagement geometry (px) ----------------------------------------
ENGAGE_WINDOW = 400          # scan window (reporting only)
ENGAGE_SHORT = 45            # front: point-blank only (never stand in
                             # the open — movement is life; forward
                             # fire bursts kill far enemies on the run)
REAR_ENGAGE = 300            # rear window while END-CLAMPED
REAR_ENGAGE_RUN = 0          # mid-run rear defense OFF: turning back
                             # mid-run is the instrumented death
                             # pattern; rear clearing belongs to the
                             # end-clamp state (where deaths actually
                             # happen — all baseline deaths were there)
FRONT_STAND = 60             # closer than this: hold ground, don't push
CLAMP_ESCALATE = [180, 300, 450]   # progressive walk-back distances
ENGAGE_BUDGET = 6            # chunks on one slot before walk-through
FORCE_ADVANCE = 2            # walk-through chunks after the budget
DODGE_HP_DROP = 8            # hp loss this chunk -> dodge reflex
DODGE_FRAMES = 14

# ---- projectile / rear-check / staleness (Issue #5 coder-2) ----------
GROUND_HEIGHT = 64           # +0x7E ground contact (session-2 decode)
PROJ_DODGE_X = 60            # airborne shell within this |dx| -> hop
REAR_CHECK_X = 130           # mid-run pursuer window (death geometry
                             # dx -54..-93, session-3 A/B)
REAR_CHECK_PERSIST = 4       # consecutive chunks before the check
REAR_CHECK_TURN = 6          # frames of LEFT tap to turn around
RESPAWN_JUMP_PX = 300        # px jump that invalidates stale state
                             # (walking covers <40px/chunk; the
                             # escalation test's synthetic fast walk
                             # peaks at ~161px/chunk; real respawn/
                             # continue reloads jump 300+px)

# ---- cadence (RoutePolicy-compatible) --------------------------------
FIRE_ON, FIRE_OFF = 8, 6
JUMP_PERIOD, JUMP_HOLD = 200, 13
GRENADE_PERIOD = 150
CLUSTER_N = 4                # grenade when this many in a 250px cluster
CLUSTER_WIN = 250

MODES = ("engage", "clamp_clear", "advance", "rear_check")


def scan_entities(mem, px=None):
    """Read the entity table; return live enemies + airborne
    projectiles sorted by |dx|.

    px: player world px (read from PLAYER_X when None).
    Schema: ps1play-combat-scan/1 (see module docstring); each entry
gains "kind": "enemy" (ground) or "projectile_air" (height word
@+0x7E above ground contact — verified falling-shell signature).
Unverified slots (hp 0/out-of-window, signed transients, x off-map)
are dropped — absence from this list means NOT OBSERVED, never
"area is safe"."""
    if px is None:
        px = int(mem.u32(PLAYER_X)) / 65536.0
    out = []
    for s in range(1, SLOTS):
        base = TABLE + s * STRIDE
        xw = int(mem.u32(base + 0x78))
        hp = int(mem.u16(base + 0x8E))
        if not xw or not hp:
            continue
        if hp >= ENEMY_HP_SIGNED or hp > ENEMY_HP_MAX:
            continue
        x_px = xw / 65536.0
        if not 0.0 < x_px < 4096.0:
            continue
        dx = x_px - px
        if abs(dx) > ENGAGE_WINDOW:
            continue
        h = int(mem.u16(base + 0x7E))
        out.append({"slot": s, "x_px": round(x_px, 1),
                    "dx_px": round(dx, 1), "hp": hp,
                    "kind": ("projectile_air" if h > GROUND_HEIGHT
                             else "enemy")})
    out.sort(key=lambda e: abs(e["dx_px"]))
    return out


class CombatPolicy:
    """Face-and-kill traversal: nearest threat (front OR rear) is
    engaged; the derived end-clamp switches to rear-clear; otherwise
    the proven RIGHT+fire backbone advances."""

    def __init__(self):
        self.fc = 0
        self.hop_hold = 0
        self.hop_cd = JUMP_PERIOD
        self.press = 0
        self.clamp_streak = 0
        self.clamp_entry_px = None
        self.clamp_round = 0            # escalation index
        self.clamp_upfire = False       # alternate walk-back / up-fire
        self.mode = "advance"
        self.engage_streak = 0
        self.engage_slot = None
        self.force_advance = 0
        self.last_hp = None
        self.last_observe_px = None
        self.rear_slot = None
        self.rear_streak = 0
        self._rear_t = 0
        self.stats = {"engage": 0, "clamp_clear": 0, "advance": 0,
                      "grenade": 0, "jump": 0, "rear_engage": 0,
                      "front_engage": 0, "dodge": 0,
                      "budget_walkthrough": 0, "rear_check": 0,
                      "proj_dodge": 0, "stale_reset": 0}

    # ----------------------------------------------------------------
    def _invalidate_stale(self):
        """Mission case 8: death/respawn/segment change invalidates every
        positional observation (wall position, escalation round, engage
        lock, pursuer streak)."""
        self.clamp_streak = 0
        self.clamp_entry_px = None
        self.clamp_round = 0
        self.clamp_upfire = False
        self.engage_slot = None
        self.engage_streak = 0
        self.rear_slot = None
        self.rear_streak = 0
        self.stats["stale_reset"] += 1

    # ----------------------------------------------------------------
    def observe(self, px, advanced, intent_right):
        """Feed per-chunk movement evidence (call once per chunk BEFORE
        decide). advanced: px gain this chunk (px). intent_right: the
        previous chunk's plan was forward progress."""
        if (self.last_observe_px is not None and
                abs(px - self.last_observe_px) > RESPAWN_JUMP_PX):
            self._invalidate_stale()      # respawn/teleport: all stale
        self.last_observe_px = px
        if intent_right:
            if advanced < 2.0:
                self.clamp_streak += 1
                if self.clamp_streak == 2:      # clamp (re-)detected
                    if self.clamp_entry_px is not None and px is not None \
                            and abs(px - self.clamp_entry_px) < 60:
                        # re-clamped at the same wall -> deepen budget
                        self.clamp_round = min(
                            self.clamp_round + 1,
                            len(CLAMP_ESCALATE) - 1)
                    self.clamp_entry_px = px
                    self.clamp_upfire = False
            else:
                self.clamp_streak = 0
                self.clamp_entry_px = None
        else:
            self.clamp_streak = 0

    # ----------------------------------------------------------------
    def decide(self, chunk, px, enemies, grenades=0, hp=None):
        """Return segments [{'frames','btns'}] covering `chunk` frames.

        px: player world px. enemies: scan_entities() output.
        grenades: current grenade count. hp: current player HP (enables
        the damage-triggered dodge reflex)."""
        segs = []
        prev = None

        def emit(n, btns):
            nonlocal prev
            if n <= 0:
                return
            if prev is not None and prev["btns"] == btns:
                prev["frames"] += n
            else:
                prev = {"frames": n, "btns": btns}
                segs.append(prev)

        # ---- threat selection: the PRESSING threat only -------------
        # Human MS play runs THROUGH the village firing forward; it
        # stops to fight only what is actually pressing: a point-blank
        # front enemy or a close rear enemy (the jeep), and at the
        # end-clamp it turns back to clear the rear zone.
        # Airborne projectiles (verified falling shells) are NEVER
        # engage targets — they are dodged below.
        clamped = self.clamp_streak >= 2
        cands = sorted(enemies or [], key=lambda e: abs(e["dx_px"]))
        foes = [e for e in cands if e.get("kind", "enemy") == "enemy"]
        airs = [e for e in cands if e.get("kind", "enemy") != "enemy"]
        proj_dodge = any(abs(e["dx_px"]) <= PROJ_DODGE_X for e in airs)
        if proj_dodge:
            self.stats["proj_dodge"] += 1
        near = None
        for e in foes:
            adx = abs(e["dx_px"])
            if e["dx_px"] >= 0:
                if adx <= ENGAGE_SHORT:
                    near = e
                    break
            else:
                limit = REAR_ENGAGE if clamped else REAR_ENGAGE_RUN
                if adx <= limit:
                    near = e
                    break

        # engage budget: never lock onto one slot forever
        if near is not None:
            if near["slot"] == self.engage_slot:
                self.engage_streak += 1
            else:
                self.engage_slot = near["slot"]
                self.engage_streak = 1
            if self.engage_streak > ENGAGE_BUDGET:
                self.force_advance = FORCE_ADVANCE
                self.engage_streak = 0
                self.engage_slot = None
                self.stats["budget_walkthrough"] += 1
        else:
            self.engage_streak = 0
            self.engage_slot = None

        # damage-triggered dodge reflex (standing still in the open is
        # how runs die; a hop breaks the aim)
        hp_drop = 0
        if hp is not None and self.last_hp is not None:
            hp_drop = max(0, self.last_hp - hp)
        self.last_hp = hp
        dodge = hp_drop >= DODGE_HP_DROP
        if dodge:
            self.stats["dodge"] += 1

        if self.force_advance > 0:
            # walk-through even through a threat: fire forward while
            # moving (baseline's survivable behaviour)
            mode = "advance"
            self.force_advance -= 1
        elif near is not None and not (clamped and near["dx_px"] < 0):
            # mid-run: engage only point-blank FRONT threats; at the
            # clamp a rear threat goes to the DEFENSIVE clear (below),
            # never a walk-toward (walking into the pursuit pack is
            # the instrumented death pattern)
            mode = "engage"
        elif not clamped and near is None and self.force_advance <= 0:
            # mission case 2 mid-run rear check: a PERSISTENT close
            # pursuer (the jeep geometry) earns ONE bounded turn-and-
            # fire chunk before the run resumes — direction correction,
            # never a walk-toward, never an infinite turn.
            pursuer = None
            for e in foes:
                if e["dx_px"] < 0 and abs(e["dx_px"]) <= REAR_CHECK_X:
                    pursuer = e
                    break
            if pursuer is not None and pursuer["slot"] == self.rear_slot:
                self.rear_streak += 1
            else:
                self.rear_slot = (pursuer["slot"]
                                  if pursuer is not None else None)
                self.rear_streak = 1 if pursuer is not None else 0
            if pursuer is not None and \
                    self.rear_streak >= REAR_CHECK_PERSIST:
                mode = "rear_check"      # counted by the stats[mode] line
                self.rear_streak = 0
                self.rear_slot = None
            else:
                mode = "advance"
        elif clamped:
            mode = "clamp_clear"
        else:
            mode = "advance"
        self.mode = mode
        self.stats[mode] = self.stats.get(mode, 0) + 1

        for fi in range(chunk):
            burst = (self.fc % (FIRE_ON + FIRE_OFF)) < FIRE_ON
            btns = set()

            if mode == "rear_check":
                # turn (short LEFT tap), then standing LEFT-facing fire
                # (empty btns keeps facing left — never a walk-toward);
                # bounded to this single chunk
                if self._rear_t < REAR_CHECK_TURN:
                    btns = {"LEFT"}
                elif burst:
                    btns = {"Y"}
                else:
                    btns = set()      # stand, keep facing left
                self._rear_t += 1
            elif mode == "engage":
                dx = near["dx_px"]
                rear = dx < 0
                adx = abs(dx)
                if rear:
                    self.stats["rear_engage"] += 1
                else:
                    self.stats["front_engage"] += 1
                face = {"LEFT"} if rear else {"RIGHT"}
                fire = face | {"Y"} if burst else face
                # keep closing while firing; only point-blank holds
                if adx > FRONT_STAND:
                    btns = fire
                else:
                    btns = fire          # point blank: hold & fire
                # grenade dense clusters (human behaviour)
                if grenades > 2 and self._cluster(enemies) and \
                        self.fc % GRENADE_PERIOD < 4:
                    btns = {"A"}
                    self.stats["grenade"] += 1
                # damage dodge: hop this instant (breaks enemy aim)
                if dodge and (self.fc % FIRE_ON) < DODGE_FRAMES:
                    btns.add("B")
                elif self._hop():
                    btns.add("B")
            elif mode == "clamp_clear":
                # DEFENSIVE rear-clear at the derived stage-end: hold
                # the line, fire LEFT into the pursuers (jeep /
                # grenadier — they walk into the bullets), alternate
                # UP-fire at the chopper/rain zone, HOP against the
                # mortar rain, grenades into the pack. Walk back only
                # on escalation rounds (no kill progress observed).
                back = CLAMP_ESCALATE[min(self.clamp_round,
                                          len(CLAMP_ESCALATE) - 1)]
                walked_back = (self.clamp_entry_px is not None and
                               px is not None and
                               self.clamp_entry_px - px >= back)
                phase = (self.fc // 240) % 2       # 4s alternation
                hop_now = (self.fc % 90) < JUMP_HOLD   # rain hop
                if self.clamp_round >= 2 and not walked_back:
                    btns = {"LEFT"} | ({"Y"} if burst else set())
                elif phase == 0:
                    btns = ({"LEFT", "Y"} if burst else {"LEFT"})
                else:
                    # UP-aim fire at the rain-source/chopper zone.
                    # w2_chopper_hp protocol B is UP+LEFT+Y SUSTAINED
                    # (MOVING); heli-ladder pattern 07 proved the
                    # STATIC variant is a death pattern (sword pack
                    # kills the standing firer, 0 source kills in
                    # 1037f) — never emit a static up-fire segment.
                    btns = ({"UP", "LEFT", "Y"} if burst
                            else {"UP", "LEFT"})
                if hop_now:
                    btns.add("B")
                if grenades > 2 and self.fc % GRENADE_PERIOD == 0:
                    btns = {"A"}
                    self.stats["grenade"] += 1
            else:
                # ---- proven traversal backbone ----------------------
                # walk-through: fire forward while advancing (standing
                # still is how runs die — route baseline evidence)
                btns = {"RIGHT"}
                if burst:
                    btns.add("Y")
                if self._hop():
                    btns.add("B")
                if self.fc % GRENADE_PERIOD == 0:
                    self.press = 4
                    self.stats["grenade"] += 1
                if self.press > 0:
                    btns.add("A")
                    self.press -= 1
            if proj_dodge and fi < JUMP_HOLD:
                # verified airborne shell within dodge radius: hop NOW
                # (heli-ladder: standing in the corridor is shell death)
                btns.add("B")
            self.fc += 1
            emit(1, btns)
        if mode == "rear_check":
            self._rear_t = 0
        return segs

    # ----------------------------------------------------------------
    def notify_escalate(self, px):
        """Runner calls when a clamp_clear round finished without
        un-clamping: deepen the walk-back budget."""
        self.clamp_round = min(self.clamp_round + 1,
                               len(CLAMP_ESCALATE) - 1)
        self.clamp_entry_px = px
        self.clamp_upfire = False

    def _hop(self):
        if self.hop_hold > 0:
            self.hop_hold -= 1
            return True
        if self.hop_cd <= 0:
            self.hop_hold = JUMP_HOLD
            self.hop_cd = JUMP_PERIOD + JUMP_HOLD
            self.stats["jump"] += 1
            return True
        self.hop_cd -= 1
        return False

    @staticmethod
    def _cluster(enemies):
        if not enemies:
            return False
        near = [e for e in enemies if abs(e["dx_px"]) <= CLUSTER_WIN]
        return len(near) >= CLUSTER_N
