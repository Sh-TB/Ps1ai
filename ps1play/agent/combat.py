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
Rule (two-stage, D8): scan_entities labels a slot "projectile_air"
from the RAW height word alone; the POLICY additionally verifies the
FALLING trajectory (height decreasing between consecutive sightings
of the same slot) before treating it as a dodgable projectile.
Live evidence (combat_live2, chunk 0-30): a STATIC elevated object
(slot 7 at x=264.0, height and hp constant for 16 chunks — elevated
scenery) was labelled projectile_air and burned 33 dodge hops, many
in the early village where no shell exists. A static/rising/first-
sighting airborne slot is now an UNVERIFIED airborne object: never
engaged, never dodged, counted in stats["proj_unverified"].
Disclosed limits: (a) a 1-frame-fall shell (h128->64, heli-ladder) is
gone before falling can be confirmed — the hop cadence + corridor
movement remain the real defense there; (b) a paradropping SOLDIER
also matches the falling signature mid-air and is dodged, not faced,
until it lands (h==64 -> enemy, engaged); (c) the ARMED GROUND-CREEP
phase (h==64, creeping, fuse-decay HP) is height-indistinguishable
from a ground entity and is NOT classified.

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

SESSION-4 COMBAT BEHAVIOURS (user feedback round 3, 2026-10-24):
  (a) FIRE DISCIPLINE: the traversal backbone no longer fires on a
      fixed cadence — forward fire only while a foe is actually ahead
      inside FRONT_FIRE_X (stats["advance_silent"] counts the silent
      move-only chunks). Advance grenades are cluster-gated the same
      way. No more aimless bursts into empty air.
  (b) STOP-AND-KILL (ENGAGE_SHORT 45 -> 200): a front soldier inside
      200 px STOPS the run — standing aimed fire until the slot dies/
      disappears (case-6 release) or ENGAGE_BUDGET expires into the
      walk-through. Soldiers are no longer RUN PAST (the D1 relapse
      the user re-reported: "you pass through the enemy").
  (c) MOVING DODGE: a verified falling shell within PROJ_DODGE_X now
      triggers hop + lateral escape AWAY from the faller — never a
      straight-up hop in place (the user's "you're jumping up — you
      must change position"; consistent with the heli must-move
      mechanic where hold-RIGHT was the only survivor pattern).
  (d) REAR KILL FOLLOW-THROUGH: the rear check is no longer one
      isolated chunk per campaign — repeat checks vs the SAME pursuer
      keep rear fire up; when the pursuer's hp is UNCHANGED across
      checks (verified no-progress = armor resists bullets), grenades
      join after REAR_GRENADE_AFTER checks (the proven anti-armor
      kill path); after REAR_CHECK_MAX checks without a kill signal
      the agent disengages honestly (stats["rear_gaveup"]) instead of
      standing forever; a vanished pursuer resolves the campaign
      (stats["rear_resolved"]).

SCENE/SCAN CONTRACT (ps1play-combat-scan/1, rev 2 — D8):
  scan_entities() returns a list of {"slot","x_px","dx_px","hp","h",
  "kind"} for live enemies + elevated slots of the PLAYER only
  (slot 0 excluded), sorted by |dx|. kind: "enemy" | "projectile_air"
  is the RAW height-word label (h > GROUND_HEIGHT); "h" carries the
  height so the policy can verify the FALLING trajectory across
  consecutive scans before dodging. The policy decision is a pure
  function of the scan stream + counters (unit-testable offline, no
  emulator).
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

# ---- section-walker sensors (Ghidra FUN_80021898 decompile, Issue #9
#      debugger deep dive 2026-10-24) ------------------------------------
# The camera/scroll section walker keeps its state in a small struct;
# the decompiled live code names these globals:
SECTION_STATE = 0x0EB5F4     # u16 section/state id (0x9, 0xE, 0xF seen
                             # in the walker branches)
SECTION_FLAGS = 0x0EB5D0     # u16 bit0 = advanced-this-step latch,
                             # 0x200 = final-state-complete latch
SECTION_PROGRESS = 0x0EB5D4  # u16 walker progress accumulator (also the
                             # step limit in the decompiled compare)

# ---- D7 pin signature (sectioncorr1 live correlation, 34 chunks) ------
# state 0xA was observed ONLY at the D7 wall pin (8/8 pin chunks, px
# 1159.8..1164.0, scroll frozen 0x048CFFFF) and NEVER mid-section.
# The 0x40 flag bit is CORROBORATION ONLY: it also appeared once
# mid-section at (state 0xB, flags 0x43) during a front-engage stall
# (chunk c12, px 1052) — so the discriminator is state==0xA, not the
# flag bit. Single-frame transients ((0x5,0x1) at c28, (0,0,0)/(0x5,0x1)
# at walker resets) must not fire the trigger -> PIN_CONFIRM
# consecutive readings are required before the policy reacts.
SECTION_PIN_STATE = 0xA
SECTION_PIN_FLAG = 0x40      # corroborating bit (not required)
SECTION_PIN_CONFIRM = 2      # consecutive pin readings before acting

# ---- engagement geometry (px) ----------------------------------------
ENGAGE_WINDOW = 400          # scan window (reporting only)
ENGAGE_SHORT = 200           # front stop-and-kill window (user
                             # directive "at least stop first and kill
                             # the soldier"): a front soldier inside
                             # this window STOPS the run — standing
                             # aimed fire until the slot dies/gone,
                             # bounded by ENGAGE_BUDGET. Was 45
                             # (point-blank only): soldiers at 60-150px
                             # were RUN PAST — the D1 relapse the user
                             # re-reported
FRONT_FIRE_X = 400           # on-the-run forward fire ONLY while a
                             # foe is actually ahead inside this
                             # window (fire discipline: no aimless
                             # bursts into empty air)
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
REAR_CHECK_MAX = 6           # consecutive follow-up checks vs one
                             # pursuer before honest disengagement
REAR_GRENADE_AFTER = 2       # hp-unchanged pursuer earns grenades
                             # after this many repeat checks (verified
                             # no-progress = armor resists bullets)
RESPAWN_JUMP_PX = 300        # px jump that invalidates stale state
                             # (walking covers <40px/chunk; the
                             # escalation test's synthetic fast walk
                             # peaks at ~161px/chunk; real respawn/
                             # continue reloads jump 300+px)
FALL_MAX_PER_CHUNK = 1200    # max height drop per 60f chunk still a
                             # fall (rain signature 1..20/f x 60f;
                             # anything larger = slot redefinition)

# ---- armor-hold (Issue #9 §8/§9-E/F: the clamp-death fix) ------------
# CLAMP-ROOT discriminator (this session): holding px 950-998 for 5400
# frames = ZERO deaths while the armored wave approached into range and
# got chipped (hp 340->214 under standing fire); pressing to the pin
# (px 1100-1164) died identically 4/4 to the one-shot -291 ram. The
# fatal contact is POSITION-DEPENDENT: it needs the agent at the pin
# with the truck charging. Fix: NEVER advance toward an armored foe
# (hp >= ARMOR_HP_MIN); stop and shoot it at range, grenade when close.
# CORRECTED SEMANTICS (Issue #5 truck campaign, 73c172d + this
# session's reach2 live probe): the historical key `hp >= 200` read
# +0x8E, which is the SCREEN-X — the 0x4054 right-side soldier
# (screen-x 240-340) mislocked as armor and armor_hold stalled the run
# 58 chunks at ~900 until the faller bombs killed the agent. The
# armored class must key the REAL HP u16@+0xA4 (truck 230-300 live,
# grenade = 100 dmg, GAMEPLAY_VERIFIED 8/8) and require GROUND contact
# (h == 64) so the airborne chopper (hp_a4 300, h 206-228, bullets
# cannot reach) never gets the stand-and-fire treatment.
ARMOR_HP_MIN = 200           # armored class on the REAL HP +0xA4
ARMOR_ENGAGE_X = 230         # trucks close to ~73-185px before the ram;
                             # stand ground anywhere inside this window
ARMOR_GRENADE_X = 110        # grenade is the proven anti-armor kill
                             # path (254->207 x3, +700 score)

# ---- cadence (RoutePolicy-compatible) --------------------------------
FIRE_ON, FIRE_OFF = 8, 6
JUMP_PERIOD, JUMP_HOLD = 200, 13
GRENADE_PERIOD = 150
CLUSTER_N = 4                # grenade when this many in a 250px cluster
CLUSTER_WIN = 250

MODES = ("engage", "clamp_clear", "advance", "rear_check")


# ---- corrected entity-field semantics (Issue #5 truck campaign,
#      uplob2..uplob12 live evidence 2026-10-25) --------------------------
# +0x8E is NOT hp: it is the SCREEN-X integer half of the u32 at +0x8C
# (world_x - camera_left; camera-scroll writer 0x80064674 adds deltas to
# +0x8C/+0x90 for every entity; no-fire Gate B2 decay 148->2 was the
# camera advancing, not damage; the truck '254->207' was movement).
# The ARMORED TRUCK's real HP is the u16 at +0xA4 (300 at the engage
# checkpoint; flat grenade = 100 dmg; death state word0 = 0xA304).
ENTITY_HP_A4 = 0xA4          # u16 armored-truck HP (live-verified)
TRUCK_DEATH_ST = 0xA304      # slot word0 after the death anim starts
FALLER_ST = 0xB4E4           # falling-bomb state word0 (hp_a4 == 30)
WALL_SOLDIER_ST = 0xE17C     # wall mortarman (the faller thrower)

# ---- session-4 (F9 unblock): wave-soldier liveness + mission end --
# Live wave soldiers CYCLE their state word0 between 0x4054 and
# 0x41FC with no input at all (soldier_hp_probe shp_100033: slot 12
# @1072 flipped within ~600f unattended) — "st == 0x4054" is NOT a
# liveness test.  The corpse states ARE stable: a killed soldier
# flips to 0x4BE4 (then 0x5CC8) and its row zeros out at ~+138f
# (shp2 shot-1 diff).  Before this filter the scan labelled
# mid-anim corpses (valid screen-x until despawn) as enemies — the
# policy aimed its fire at the dead and the live soldier survived:
# the mechanism behind session-3 F9's "Y-bursts did not kill".
CORPSE_ST = (0x4BE4, 0x5CC8)
SOLDIER_FAMILY_ST = (0x4054, 0x41FC)
# Mission-end sequence: the walker leaves the pin family and lands
# in state 0xC while the player sits at px 26.4 — the "MISSION 1 /
# CLEAR TIME / PRESS START" banner (chain_a_full x3/3, PNG evidence;
# release_confirm independently keyed on (0xC, 8/9) @ px 26.4).
# Walking during the banner expires its countdown into a mission
# restart (chain_a v3/v4) — the policy must HOLD (no input) here.
SECTION_MISSION_END = 0xC
MISSION_END_CONFIRM = 2      # consecutive readings (transient guard)

# D7 zone latch (session-4 policy trial evidence): the pin cycle
# RE-ARMS every time the policy walks back into the clamp (the
# pending-queue check runs on the px-1164 trigger) — kill/walk/repin
# oscillation burned all 10 grenades and died to the fallers
# (policy_chain_trial fix arm c=23, 3/3).  Once the player reaches
# the D7 clamp the policy stays in the defensive clear UNTIL the
# mission-end sequence: the end sequence comes to a STANDING player
# (chain_a v2/v6 evidence) — never walk into the re-pin.
D7_ZONE_PX = 1150.0          # >= this: the D7 clamp zone
D7_HOLD_PX = 985.0           # walk-back floor while latched (the
                             # warp/wave zone is 992+; the release
                             # ran standing at 992-1016)
D7_EXIT_PX = 300.0           # < this = mission restart (px 26-32):
                             # only a restart un-latches the zone


def scan_entities(mem, px=None):
    """Read the entity table; return live enemies + airborne
    projectiles sorted by |dx|.

    px: player world px (read from PLAYER_X when None).
    Schema: ps1play-combat-scan/1 (see module docstring); each entry
gains "kind": "enemy" (ground) or "projectile_air" (height word
@+0x7E above ground contact — verified falling-shell signature).
Unverified slots (hp 0/out-of-window, signed transients, x off-map)
are dropped — absence from this list means NOT OBSERVED, never
"area is safe".

    CORRECTED SEMANTICS (Issue #5 truck campaign): the legacy "hp"
key still carries the u16@+0x8E reading for backward compatibility,
but that field is the SCREEN-X integer ("sx" — the same value), NOT
health. New keys per entry: "sx" (= hp, honest name), "hp_a4" (u16
at +0xA4: the armored-truck HP, live-verified 300->0 under grenades,
0 on non-armored entities), "st" (state-handler word0 — distinguishes
the truck death 0xA304, faller bombs 0xB4E4, wall mortarman 0xE17C)."""
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
        st = int(mem.u16(base))
        if st in CORPSE_ST:
            # session-4: a corpse keeps a valid screen-x until its
            # ~+138f despawn — including it made the policy fire at
            # the dead while the live soldier walked (F9 unblock)
            continue
        hp_a4 = int(mem.u16(base + ENTITY_HP_A4))
        out.append({"slot": s, "x_px": round(x_px, 1),
                    "dx_px": round(dx, 1), "hp": hp, "sx": hp,
                    "h": h, "st": st, "hp_a4": hp_a4,
                    "kind": ("projectile_air" if h > GROUND_HEIGHT
                             else "enemy")})
    out.sort(key=lambda e: abs(e["dx_px"]))
    return out


def find_truck(enemies):
    """Return the live armored-truck entry from a scan_entities list,
    or None. Identity (live-verified, uplob5/6/7/9): ground contact
    (h == GROUND_HEIGHT), state word0 = 0x9E88 (the parked truck;
    unchanged across grenade hits uplob9 spam3/4) and a +0xA4 HP in
    [100, 600]. NOTE: 0x4054 is the RIGHT-side soldier (slot 10), not
    the truck — uplob1's screen-x mislock. The truck is never
    'kind: projectile_air'."""
    for e in enemies:
        if e.get("kind") != "enemy":
            continue
        if e.get("h") != GROUND_HEIGHT:
            continue
        if e.get("st") != 0x9E88:
            continue
        if 100 <= e.get("hp_a4", 0) <= 600:
            return e
    return None


def truck_kill_segments(px, truck, ammo, phase):
    """Pure decision function: the live-verified armored-truck kill
    routine (uplob7/9/10: 3/3 and 5/5 reproducible, 4 grenades,
    HP 300->0 via +0xA4).

    phase: None | {"mode": "approach"|"escape"|"spam", "until": f}
    Returns (segments, new_phase, done).
    Segments: [{'frames', 'btns'}] — the caller runs them verbatim.

    Geometry (proven): hit band = truck world x + 50..62 (player LEFT
    of the truck — the truck is BEHIND the player at the D7 zone);
    face-LEFT flat lob from the band connects (100 dmg); escape RIGHT
    ~110f to the clamp; when hp_a4 <= 200 stand at the clamp and spam
    face-LEFT alternating UP-lobs and flat lobs (~35f apart) — the
    chasing/parked truck eats them (200->100->0).
    done: True when truck["hp_a4"] <= 0 (death state 0xA304)."""
    if truck is None or truck.get("hp_a4", 0) <= 0:
        return [], phase, True
    tx = truck["x_px"]
    hp = truck["hp_a4"]
    mode = (phase or {}).get("mode")
    until = (phase or {}).get("until", 0)
    segs = []
    if mode == "escape" and until > 0:
        segs.append({"frames": min(until, 110), "btns": {"RIGHT"}})
        return segs, {"mode": "spam" if hp <= 200 else "approach",
                      "until": 0}, False
    if hp <= 200:
        # spam phase at the clamp (proven: kills from 200 in 2 hits)
        if ammo <= 0:
            return segs, phase, True
        up = ((phase or {}).get("n", 0) % 2 == 0)
        b = {"LEFT", "UP", "A"} if up else {"LEFT", "A"}
        segs.append({"frames": 2, "btns": {"LEFT"}})
        if up:
            segs.append({"frames": 3, "btns": {"UP"}})
            segs.append({"frames": 6, "btns": b})
        else:
            segs.append({"frames": 6, "btns": b})
        segs.append({"frames": 2, "btns": set()})
        segs.append({"frames": 22, "btns": set()})
        np_ = {"mode": "spam", "until": 0,
               "n": (phase or {}).get("n", 0) + 1}
        return segs, np_, False
    # approach to the hit band
    dx = tx - px
    if dx < -62:
        segs.append({"frames": 30, "btns": {"LEFT"}})
        return segs, {"mode": "approach", "until": 0}, False
    if dx > -50:
        segs.append({"frames": 12, "btns": {"RIGHT"}})
        return segs, {"mode": "approach", "until": 0}, False
    # in the band: the proven hit (face-left flat lob) then escape
    if ammo <= 0:
        return segs, phase, True
    segs.append({"frames": 2, "btns": {"LEFT"}})
    segs.append({"frames": 8, "btns": {"A"}})
    segs.append({"frames": 2, "btns": set()})
    segs.append({"frames": 110, "btns": {"RIGHT"}})
    return segs, {"mode": "spam" if hp - 100 <= 200 else "approach",
                  "until": 0, "n": 0}, False


SCAN_SCHEMA = "ps1play-combat-scan/1"


SECTION_SCHEMA = "ps1play-section-scan/1"


def scan_section(mem):
    """Read the camera/scroll section-walker state (read-only sensor).

    Provenance: Ghidra decompile of FUN_80021898 (Issue #9 debugger
    deep dive) — the walker's globals were identified statically from
    the live-referenced scroll word 0x0EB598. Semantics are OBSERVED
    from the decompiled control flow:
      state    u16 section id; the walker branches on 0x9, 0xE, 0xF
      flags    u16 bit0 = advanced-this-step, 0x200 = the final state
               (0xF) completed (section-complete latch)
      progress u16 walker accumulator
    UNCERTAINTY: state numbering is per-section and not exhaustively
    mapped — this sensor explains WHY the camera is pinned (D7) and
    when it releases; it must never be used as a safety assertion on
    its own. Absence/inconsistency = NOT OBSERVED, never "safe".

    LIVE CORRELATION (chopper_ckpt run sectioncorr1, 34 chunks, 2026
    -10-24): (state 0xB, flags 0x1) = walker advancing freely (px
    894->1140); (state 0xA, flags 0x43) = the D7 pin signature — px
    frozen at 1164.0 with scroll word frozen at 0x048CFFFF for the
    whole pin; single-frame transients (0,0,0) / (0x5,0x1) observed
    at walker resets. Refinement from the same timeline: state 0xA is
    the pin DISCRIMINATOR (8/8 pin chunks, never mid-section, flags
    inside the pin varied 0x43/0x1/0x0); the 0x40 flag bit is only
    CORROBORATION — it was also seen once mid-section at (0xB, 0x43)
    during a front-engage stall (chunk c12, px 1052).
    """
    state = int(mem.u16(SECTION_STATE))
    flags = int(mem.u16(SECTION_FLAGS))
    progress = int(mem.u16(SECTION_PROGRESS))
    return {"state": state, "flags": flags, "progress": progress,
            "schema": SECTION_SCHEMA,
            "complete": bool(flags & 0x200) or state == 0xF}


def validate_scan(scan, px=None, diagnostics=None):
    """Issue #9 §9-A: combat-state correctness — schema validation for
    scan_entities() output (contract ps1play-combat-scan/1).

    Every combat branch must receive well-formed fields; a malformed
    entry is a DIAGNOSTIC EVENT, never a silent "area is safe".
    Returns True when the scan satisfies the contract. When
    `diagnostics` (a dict) is passed, per-violation details are added as
    diagnostics["violations"] without raising.

    Contract:
      entry keys   slot(int 1..SLOTS-1), x_px(0<..<4096),
                   dx_px(x_px-px), hp(0<hp<ENEMY_HP_SIGNED),
                   h(int >=0), kind("enemy"|"projectile_air")
      invariants   kind == "projectile_air" iff h > GROUND_HEIGHT
                   |dx_px| = |x_px - px| (when px known)
                   sorted by |dx_px| ascending
    """
    ok = True
    violations = []
    prev_key = None
    for i, e in enumerate(scan or []):
        where = f"[{i}]"
        slot = e.get("slot")
        if not isinstance(slot, int) or not 1 <= slot < SLOTS:
            violations.append(f"{where} bad slot {slot!r}")
            ok = False
        x = e.get("x_px")
        if not isinstance(x, (int, float)) or not 0.0 < x < 4096.0:
            violations.append(f"{where} bad x_px {x!r}")
            ok = False
        hp = e.get("hp")
        if not isinstance(hp, int) or not 0 < hp < ENEMY_HP_SIGNED:
            violations.append(f"{where} bad hp {hp!r}")
            ok = False
        h = e.get("h")
        if not isinstance(h, int) or h < 0:
            violations.append(f"{where} bad h {h!r}")
            ok = False
        kind = e.get("kind")
        if kind not in ("enemy", "projectile_air"):
            violations.append(f"{where} bad kind {kind!r}")
            ok = False
        elif isinstance(h, int) and h >= 0 and \
                kind != ("projectile_air" if h > GROUND_HEIGHT else "enemy"):
            violations.append(f"{where} kind/kind-height mismatch "
                              f"(kind={kind} h={h})")
            ok = False
        if px is not None and isinstance(x, (int, float)):
            dx = e.get("dx_px")
            if not isinstance(dx, (int, float)) or \
                    abs(abs(dx) - abs(x - px)) > 0.51:
                violations.append(f"{where} dx_px {dx!r} != |x_px-px|")
                ok = False
        key = abs(e["dx_px"]) if isinstance(e.get("dx_px"),
                                            (int, float)) else None
        if key is None:
            violations.append(f"{where} missing dx_px")
            ok = False
        elif prev_key is not None and key < prev_key - 1e-9:
            violations.append(f"{where} sort order broken")
            ok = False
        else:
            prev_key = key
    if diagnostics is not None:
        diagnostics["violations"] = violations
        diagnostics["schema"] = SCAN_SCHEMA
        diagnostics["entries"] = len(scan or [])
    return ok


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
        self.rear_checks = 0           # follow-up checks, same pursuer
        self.rear_last_hp = None       # pursuer hp at the last check
        self.rear_hp_now = None        # pursuer hp this chunk
        self.armor_slot = None         # §8 armor-hold campaign slot
        self.armor_checks = 0
        self.armor_last_hp = None
        self.armor_hp_now = None
        self.armor_no_progress = False
        self._armor_t = 0              # frames since armor campaign start
        self.no_progress = False       # hp unchanged across checks
        self.prev_h = {}               # slot -> height at last sighting
        # D7 instrument pin (scan_section correlation, Issue #9)
        self.section_pinned = False    # instrument pin actively believed
        self.mission_end = False       # 0xC banner latch (session-4)
        self.me_streak = 0
        self.d7_zone = False           # D7 clamp-zone latch (s-4)
        self.sec_pin_streak = 0        # consecutive pin-signature readings
        self.sec_free_streak = 0       # consecutive non-signature readings
        self.stats = {"engage": 0, "clamp_clear": 0, "advance": 0,
                      "grenade": 0, "jump": 0, "rear_engage": 0,
                      "front_engage": 0, "dodge": 0,
                      "budget_walkthrough": 0, "rear_check": 0,
                      "proj_dodge": 0, "proj_unverified": 0,
                      "stale_reset": 0, "advance_silent": 0,
                      "rear_grenade": 0, "rear_resolved": 0,
                      "rear_gaveup": 0, "armor_hold": 0,
                      "armor_grenade": 0, "section_pin": 0,
                      "section_pin_release": 0}

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
        self.rear_checks = 0
        self.rear_last_hp = None
        self.rear_hp_now = None
        self.no_progress = False
        # §8 armor-hold state is positional too: a respawn/segment
        # change means the tracked truck campaign no longer applies
        self.armor_slot = None
        self.armor_checks = 0
        self.armor_last_hp = None
        self.armor_hp_now = None
        self.armor_no_progress = False
        self.prev_h = {}               # height memory is stale too (D8)
        # D7 instrument pin: the signature is GAME-STATE evidence read
        # fresh every chunk, not a positional observation — a px jump
        # (respawn/teleport) does NOT invalidate it. The streaks reset
        # (they must re-confirm from live readings), but section_pinned
        # stays until 2 consecutive live non-signature readings release
        # it. Reason: the F6 respawn geometry (respawn INSIDE the truck
        # kill zone) makes the defensive stance the safe default for the
        # <=2 extra chunks; dropping the pin on a px jump would resume
        # the run INTO the kill zone.
        self.sec_pin_streak = 0
        self.sec_free_streak = 0
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
        # session-4 D7 zone latch: entering the clamp zone latches the
        # defensive state; ONLY a mission restart (px < D7_EXIT_PX —
        # the restart sits at px 26-32) un-latches it.  The pin-cycle
        # warp to ~992 is 172px (< RESPAWN_JUMP_PX) and must NOT
        # un-latch — the queue may still hold live entities.
        if px is not None:
            if px >= D7_ZONE_PX:
                if not self.d7_zone:
                    self.d7_zone = True
                    self.stats["d7_zone_latch"] = \
                        self.stats.get("d7_zone_latch", 0) + 1
            elif px < D7_EXIT_PX and self.d7_zone:
                self.d7_zone = False
                self.stats["d7_zone_exit"] = \
                    self.stats.get("d7_zone_exit", 0) + 1
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
    def observe_section(self, sec, px_now=None):
        """Feed one scan_section() reading (call once per chunk, before
        decide; None = sensor not read this chunk, a no-op).
        px_now: the current player px (optional; enables the
        mission-restart unlatch — garbage/absent px never unlatches).

        Instrument-based D7-pin detection (Issue #9 debugger deep dive
        -> sectioncorr1 live correlation): the walker state 0xA
        POSITIVELY identifies the section pin, so the defensive
        clamp_clear response engages immediately — without waiting for
        the derived px-stagnation streak, which knockback wobble resets
        (sectioncorr1 c11-c20: px oscillated 1052->962->1057->953 while
        pinned-phase pressure continued; the derived streak kept
        resetting in exactly those chunks).

        Discipline: absence of the signature is NEVER a safety
        assertion (walker state numbering is not exhaustively mapped);
        release therefore requires SECTION_PIN_CONFIRM consecutive
        non-signature readings, and stale invalidation keeps the pin
        (see _invalidate_stale)."""
        if not sec:
            return
        # state 0xA alone is the discriminator: pin chunks were observed
        # with flags 0x43/0x1/0x0 (sectioncorr1 c25-33) — requiring the
        # 0x40 flag bit would falsely RELEASE the pin at (0xA, 0x0)
        # readings like c33.
        # Session-3 addition (Issue #5 D7 release campaign): a SECOND
        # live boot pins with the walker still in state 0xB — px frozen
        # 1164.0, flags 0x43 sustained, release 3/3 identical
        # (release_test.py rel1-3) once the section's pending entities
        # are cleared. The old-boot (0xB,0x43) readings (c12/c30) were
        # SINGLE transients, so the SECTION_PIN_CONFIRM consecutive
        # requirement still keeps them out; only a SUSTAINED
        # (0xB, flags&0x40) reading now latches the pin.
        sig = (sec.get("state") == SECTION_PIN_STATE or
               (sec.get("state") == 0xB and
                (sec.get("flags", 0) & SECTION_PIN_FLAG)))
        if sig:
            self.sec_pin_streak += 1
            self.sec_free_streak = 0
            if not self.section_pinned and \
                    self.sec_pin_streak >= SECTION_PIN_CONFIRM:
                self.section_pinned = True
                self.stats["section_pin"] += 1
        else:
            self.sec_pin_streak = 0
            if self.section_pinned:
                self.sec_free_streak += 1
                if self.sec_free_streak >= SECTION_PIN_CONFIRM:
                    self.section_pinned = False
                    self.sec_free_streak = 0
                    self.stats["section_pin_release"] += 1
        # session-4: the mission-end sequence (walker state 0xC at
        # px < 200 = the MISSION 1 banner).  Confirmed x2 consecutive
        # readings, then LATCHED for the rest of the run: every input
        # during the banner risks expiring its countdown into a
        # mission restart (chain_a v3/v4 paired evidence).  0xC is
        # NOT in the decompiled walker branch set (0x9/0xE/0xF) —
        # this latch is OBSERVED-live semantics, stated honestly.
        if sec.get("state") == SECTION_MISSION_END:
            self.me_streak += 1
            if not self.mission_end and \
                    self.me_streak >= MISSION_END_CONFIRM:
                self.mission_end = True
                self.stats["mission_end"] = \
                    self.stats.get("mission_end", 0) + 1
        else:
            self.me_streak = 0
        # trigger B (session-4 policy trial): the walker RESET with
        # the release flag (state 0, flags & 0x8) INSIDE the D7 zone
        # is the pre-banner step of the end sequence — the trial's
        # boundary reads saw (0,8) then the restart with 0xC never
        # sampled, because policy inputs during (0,8)->(0xC) skip the
        # banner.  Latch the hold IMMEDIATELY on this signature while
        # d7_zone (observed 3/3 in chain_a v2/v6 + the trial).
        if (not self.mission_end and self.d7_zone and
                sec.get("state") == 0 and
                (sec.get("flags", 0) & 0x8)):
            self.mission_end = True
            self.stats["mission_end"] = \
                self.stats.get("mission_end", 0) + 1
            self.stats["mission_end_prebanner"] = \
                self.stats.get("mission_end_prebanner", 0) + 1
        # unlatch: the banner expired into a mission restart — the
        # walker is back in a normal state at the restart position
        # (px 26-32, valid reading).  The banner itself (state 0xC or
        # the (0,8) reset) never unlatches; px 26.4 sits INSIDE the
        # restart window and must keep holding.
        if (self.mission_end and sec.get("state") not in (0, 0xC)
                and px_now is not None and 0.0 < px_now < 300.0):
            self.mission_end = False
            self.d7_zone = False
            self.me_streak = 0
            self.stats["mission_end_restart_resume"] = \
                self.stats.get("mission_end_restart_resume", 0) + 1

    # ----------------------------------------------------------------
    def decide(self, chunk, px, enemies, grenades=0, hp=None):
        """Return segments [{'frames','btns'}] covering `chunk` frames.

        px: player world px. enemies: scan_entities() output.
        grenades: current grenade count. hp: current player HP (enables
        the damage-triggered dodge reflex)."""
        segs = []
        prev = None

        # ---- §9-A schema pre-flight: a malformed scan is counted and
        # NEVER silently treated as "no threats observed". Behaviour is
        # unchanged (the branch still runs on what it can read); the
        # violation counter makes the anomaly visible in every ledger.
        diag = {}
        if not validate_scan(enemies, px=px, diagnostics=diag):
            self.stats["scan_schema_violations"] = \
                self.stats.get("scan_schema_violations", 0) + 1
            self.last_scan_diagnostics = diag

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
        # ---- mission-end HOLD (session-4, chain_a v3/v4 lesson) ----
        # Once the 0xC banner latches, ANY input (walking counts)
        # advances the banner's countdown into a mission restart.
        # Emit a full-chunk no-input segment and nothing else.
        if self.mission_end:
            self.mode = "mission_end_hold"
            self.stats["mission_end_hold"] = \
                self.stats.get("mission_end_hold", 0) + 1
            emit(chunk, set())
            return segs

        clamped = self.clamp_streak >= 2 or self.section_pinned
        cands = sorted(enemies or [], key=lambda e: abs(e["dx_px"]))
        foes = [e for e in cands if e.get("kind", "enemy") == "enemy"]
        airs = [e for e in cands if e.get("kind", "enemy") != "enemy"]
        # ---- D8 falling-trajectory verification --------------------
        # A RAW "projectile_air" label (h > 64) is NOT enough: dodge
        # only slots whose height DECREASED since the previous sighting
        # of the same slot (the verified rain signature at chunk
        # granularity). Static / rising / first-sighting elevated
        # objects stay unverified: never engaged, never dodged.
        dodgable = []
        next_h = {}
        for e in airs:
            hv = e.get("h")
            if hv is None:
                self.stats["proj_unverified"] += 1
                continue
            s = e["slot"]
            ph = self.prev_h.get(s)
            next_h[s] = hv
            if ph is not None and 0 < ph - hv <= FALL_MAX_PER_CHUNK:
                dodgable.append(e)
            else:
                self.stats["proj_unverified"] += 1
        self.prev_h = next_h
        proj_dodge = any(abs(e["dx_px"]) <= PROJ_DODGE_X
                         for e in dodgable)
        if proj_dodge:
            self.stats["proj_dodge"] += 1
        # MOVING dodge direction (user directive "you're jumping up —
        # you must CHANGE POSITION"): escape AWAY from the nearest
        # verified faller; never a straight-up in-place hop.
        dodge_move = None
        if dodgable:
            nf = min(dodgable, key=lambda e: abs(e["dx_px"]))
            dodge_move = "LEFT" if nf["dx_px"] > 0 else "RIGHT"
        # fire discipline: on-the-run forward fire only vs a real
        # ahead target (aimless-burst fix, user directive)
        ahead_fire = any(0 <= e["dx_px"] <= FRONT_FIRE_X for e in foes)
        # §8/§9-E/F armored-threat detection (before near-selection:
        # an armored foe outranks a closer soft foe — the soft one is
        # survivable at range, the truck's charge is the 4/4 killer).
        # AHEAD threats only (dx >= 0): rear threats keep the verified
        # rear_check/grenade campaign (the jeep geometry) — armor_hold
        # must never hijack the mid-run rear defence.
        armor_threat = None
        if not clamped:
            for e in foes:
                if e.get("hp_a4", 0) >= ARMOR_HP_MIN and \
                        e.get("h") == GROUND_HEIGHT and \
                        e["dx_px"] >= 0 and \
                        e["dx_px"] <= ARMOR_ENGAGE_X:
                    armor_threat = e
                    break
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

        if self.force_advance > 0 and not self.d7_zone:
            # walk-through even through a threat: fire forward while
            # moving (baseline's survivable behaviour).
            # session-4: NEVER inside the D7 zone — the "threat" is
            # the section's pending queue (the release condition);
            # walking past it re-arms the pin (the trial's
            # kill/walk/repin oscillation).  The budget expiry still
            # resets its counters below via the normal paths.
            mode = "advance"
            self.force_advance -= 1
        elif self.force_advance > 0:
            # D7 zone: burn the walkthrough budget in place (stand,
            # no input) — the queue entities must be KILLED, not passed
            mode = "clamp_clear"
            self.force_advance -= 1
        elif not clamped and armor_threat is not None:
            # §8/§9-E/F CLAMP-ROOT fix: an armored foe (hp >= 200) in
            # range = STOP AND SHOOT (user directive "at least stop
            # first"). Advancing into its charge path is the
            # instrumented 4/4 one-shot death at the pin; holding and
            # firing is the 0-death verified behaviour. Kill
            # follow-through: track hp across chunks; an hp-UNCHANGED
            # streak escalates to grenades (verified anti-armor path).
            mode = "armor_hold"
            if armor_threat["slot"] == self.armor_slot:
                self.armor_checks += 1
            else:
                self.armor_slot = armor_threat["slot"]
                self.armor_checks = 1
                self.armor_last_hp = None
                self._armor_t = 0
            self.armor_hp_now = armor_threat.get("hp_a4",
                                                 armor_threat["hp"])
            self.armor_no_progress = (self.armor_last_hp is not None and
                                      self.armor_hp_now ==
                                      self.armor_last_hp)
            self.armor_last_hp = self.armor_hp_now
        elif near is not None and \
                not ((clamped or self.section_pinned)
                     and near["dx_px"] < 0):
            # mid-run: engage only point-blank FRONT threats; at the
            # clamp a rear threat goes to the DEFENSIVE clear (below),
            # never a walk-toward (walking into the pursuit pack is
            # the instrumented death pattern)
            mode = "engage"
        elif (not clamped and not self.d7_zone and near is None
              and self.force_advance <= 0):
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
                if pursuer is not None and \
                        pursuer["slot"] != self.rear_slot:
                    # a NEW pursuer starts a fresh follow-through
                    # campaign (the old one ended unresolved)
                    self.rear_checks = 0
                    self.rear_last_hp = None
                self.rear_slot = (pursuer["slot"]
                                  if pursuer is not None else None)
                self.rear_streak = 1 if pursuer is not None else 0
            if pursuer is None and self.rear_checks:
                # the pursuer is GONE (dead/vanished): threat RESOLVED,
                # resume clean (case-6 release semantics for the rear;
                # kill evidence itself is the runner's job)
                self.stats["rear_resolved"] += 1
                self.rear_checks = 0
                self.rear_last_hp = None
                self.rear_hp_now = None
            if pursuer is not None and \
                    self.rear_streak >= REAR_CHECK_PERSIST:
                mode = "rear_check"      # counted by the stats[mode] line
                # kill follow-through bookkeeping: consecutive checks
                # vs the SAME pursuer, with VERIFIED hit comparison
                # (hp at this check vs the previous check — the
                # mission's hit-evidence rule)
                self.rear_hp_now = pursuer["hp"]
                self.no_progress = (self.rear_last_hp is not None and
                                    self.rear_hp_now ==
                                    self.rear_last_hp)
                self.rear_last_hp = self.rear_hp_now
                self.rear_checks += 1
                self.rear_streak = 0
                # rear_slot KEPT (not reset): the next chunk's same-slot
                # match must continue THIS campaign — resetting the slot
                # made every post-check chunk look like a new pursuer
                # and wiped the follow-through counters (session-4 bug
                # caught by test_rear_followthrough_escalates_to_grenade)
            else:
                mode = "advance"
        elif clamped or self.section_pinned or self.d7_zone:
            # session-3: the instrument pin (0xA, or a SUSTAINED
            # (0xB, flags&0x40)) holds the defensive clear even when
            # the derived px-stall streak flickers (knockback wobble)
            # session-4: the D7 zone latch keeps the clear through the
            # pin cycle (advance re-enters the clamp and re-arms the
            # pending queue — the trial's kill/walk/repin loop)
            mode = "clamp_clear"
        else:
            mode = "advance"
        self.mode = mode
        self.stats[mode] = self.stats.get(mode, 0) + 1
        if mode == "advance" and not ahead_fire:
            self.stats["advance_silent"] += 1

        for fi in range(chunk):
            burst = (self.fc % (FIRE_ON + FIRE_OFF)) < FIRE_ON
            btns = set()

            if mode == "rear_check":
                # turn (short LEFT tap), then standing LEFT-facing
                # fire; repeat checks vs an hp-UNCHANGED pursuer
                # escalate to GRENADES (verified no-progress = armor
                # resists bullets; the grenade is the proven
                # anti-armor kill path); empty btns keeps facing left
                # — never a walk-toward
                if self._rear_t < REAR_CHECK_TURN:
                    btns = {"LEFT"}
                elif (self.no_progress
                        and self.rear_checks > REAR_GRENADE_AFTER
                        and grenades > 0
                        and self.fc % 8 < 4):
                    btns = {"A"}
                    self.stats["rear_grenade"] += 1
                elif burst:
                    btns = {"Y"}
                else:
                    btns = set()      # stand, keep facing left
                self._rear_t += 1
            elif mode == "armor_hold":
                # stand ground; assert facing with a SHORT tap only at
                # campaign start (holding the direction key would WALK
                # toward the truck — facing persists once standing);
                # then standing aimed fire; hp-unchanged streak
                # escalates to GRENADES (the verified anti-armor kill
                # path — Y alone only chips). NEVER a walk-toward
                # (the pin-zone ram is 4/4 fatal).
                dx = armor_threat["dx_px"]
                face = {"LEFT"} if dx < 0 else {"RIGHT"}
                adx = abs(dx)
                if self._armor_t < 2:
                    btns = face              # face assert (2 frames)
                elif (self.armor_no_progress
                        and self.armor_checks > 2
                        and grenades > 0
                        and adx <= ARMOR_GRENADE_X
                        and self.fc % GRENADE_PERIOD < 4):
                    btns = {"A"}
                    self.stats["armor_grenade"] = \
                        self.stats.get("armor_grenade", 0) + 1
                elif burst:
                    btns = {"Y"}
                else:
                    btns = set()             # stand, keep facing
                self._armor_t += 1
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
                # DEFENSIVE stage-end clear: hold the line, fire INTO
                # the pending section entities (they ARE the release
                # condition — session-3: clearing the 2 frozen
                # soldiers released the pin 3/3 and reached the
                # MISSION 1 screen), alternate UP-fire at the
                # chopper/rain zone, HOP against the mortar rain,
                # grenades into the pack. Walk back only on
                # escalation rounds (no kill progress observed).
                # Session-3 aiming fix: the fire facing follows the
                # nearest live GROUND foe's side — the hard-coded
                # LEFT fired away from the respawn-side soldiers
                # (px 992 respawn, soldiers 1064-1103 = RIGHT).
                back = CLAMP_ESCALATE[min(self.clamp_round,
                                          len(CLAMP_ESCALATE) - 1)]
                walked_back = (self.clamp_entry_px is not None and
                               px is not None and
                               self.clamp_entry_px - px >= back)
                if self.d7_zone and px is not None and \
                        px <= D7_HOLD_PX:
                    # never retreat past the wave zone while latched:
                    # the release ran STANDING at 992-1016 and the
                    # end sequence comes to the player
                    walked_back = True
                gnd = [e for e in foes
                       if e.get("h", GROUND_HEIGHT) == GROUND_HEIGHT]
                fam = [e for e in gnd
                       if e.get("st") in SOLDIER_FAMILY_ST]
                # session-4 D7 discipline: the pending-queue soldiers
                # are the release condition — aim them FIRST (2 aimed
                # bullets each, soldier_bpp 3/3); when the zone is
                # QUIET (no family soldier, no ground foe) go SILENT:
                # the end sequence starts with the (0,8) walker reset
                # and ANY input during it skips the banner (the
                # policy trial's c=13->restart, 3/3)
                if self.d7_zone and not fam and not gnd and \
                        not airs:
                    btns = set()
                    self.stats["d7_quiet_hold"] = \
                        self.stats.get("d7_quiet_hold", 0) + 1
                elif self.clamp_round >= 2 and not walked_back:
                    btns = {"LEFT"} | ({"Y"} if burst else set())
                elif fam or (self.d7_zone and gnd):
                    # queue soldiers (or any zone ground foe): flat
                    # aimed fire only — no UP-phase alternation (the
                    # 4s UP window wasted half the dps; the scripted
                    # proof is 2 flat bullets per soldier)
                    nf = min(fam or gnd,
                             key=lambda e: abs(e["dx_px"]))
                    aim = "LEFT" if nf["dx_px"] < 0 else "RIGHT"
                    btns = ({aim, "Y"} if burst else {aim})
                else:
                    phase = (self.fc // 240) % 2   # 4s alternation
                    aim = "LEFT"
                    if gnd:
                        nf = min(gnd, key=lambda e: abs(e["dx_px"]))
                        aim = "LEFT" if nf["dx_px"] < 0 else "RIGHT"
                    if phase == 0:
                        btns = ({aim, "Y"} if burst else {aim})
                    else:
                        # UP-aim fire at the rain-source/chopper
                        # zone.  w2_chopper_hp protocol B is
                        # UP+<aim>+Y SUSTAINED (MOVING); heli-ladder
                        # pattern 07 proved the STATIC variant is a
                        # death pattern — never emit it static.
                        btns = ({"UP", aim, "Y"} if burst
                                else {"UP", aim})
                hop_now = (self.fc % 90) < JUMP_HOLD   # rain hop
                if hop_now and btns:
                    btns.add("B")
                if grenades > 2 and self.fc % GRENADE_PERIOD == 0 \
                        and btns:
                    btns = {"A"}
                    self.stats["grenade"] += 1
            else:
                # ---- traversal backbone (fire discipline, user
                # directive "you fire aimless bursts"): move ALWAYS,
                # fire forward ONLY while a foe is actually ahead
                # inside FRONT_FIRE_X; cluster grenades stay
                # target-gated the same way
                btns = {"RIGHT"}
                if burst and ahead_fire:
                    btns.add("Y")
                if self._hop():
                    btns.add("B")
                if (grenades > 2 and self._cluster(enemies)
                        and self.fc % GRENADE_PERIOD < 4):
                    btns = {"A"}
                    self.stats["grenade"] += 1
            if proj_dodge and fi < JUMP_HOLD:
                # verified airborne shell within dodge radius: MOVING
                # dodge NOW — hop + lateral escape AWAY from the
                # faller (user directive: never a straight-up hop in
                # place; heli must-move mechanic). The imminent shell
                # outranks the mode's own facing for these frames;
                # firing forward while escaping right is free.
                btns = {"B", dodge_move}
                if burst and dodge_move == "RIGHT":
                    btns.add("Y")
            self.fc += 1
            emit(1, btns)
        if mode == "rear_check":
            self._rear_t = 0
            if self.rear_checks >= REAR_CHECK_MAX:
                # honest disengagement: REAR_CHECK_MAX follow-ups
                # produced no kill signal — stop burning standing
                # exposure and resume the run (the pursuer streak
                # must rebuild before the next campaign)
                self.force_advance = FORCE_ADVANCE
                self.rear_checks = 0
                self.rear_last_hp = None
                self.stats["rear_gaveup"] += 1
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
