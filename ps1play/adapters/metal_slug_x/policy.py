"""ps1play.adapters.metal_slug_x.policy — the Mission-1 policy (R66).

A deterministic, evidence-backed RULE-BASED policy.  No training, no
model, no runtime LLM, no RAM writes: the policy consumes ONLY the
adapter's read-only RAM observation and emits legal pad actions.

The R66 correction is IN this policy: the engagement rule uses the
R66 corridor predicate — an entity blocks a shot only if it can
ABSORB the bullet or REGISTER the payment.  Concretely (the R66
pass-A GATE_DIAG evidence, n=13+13 skips):

  * state code 4 (0xab94, bullet-TRANSPARENT) never blocks and is
    never targeted (the n=4 piercing evidence, R50/R51);
  * airborne projectile classes never block (the R66 dump: the top
    blockers were projectile_air entities that cannot interact with
    player bullets);
  * every other mortal between player and target blocks (it can
    steal the bullet — the R49 player-bullet-victim-locked model),
    including the armored truck (code 7 — the R38 chip evidence).

The movement rule is the proven issue4 semantics: walk RIGHT, hop on
a cadence, stop-and-fire front mortals inside the engage window, the
bounded stall ladder (jump burst -> grenade -> keep walking), never
fire blind through a blocker.

v1.1.0 (R67) — THE TRUCK ENCOUNTER RULES (the R67 capsule lever, the
product-path truck campaign; every rule is committed-evidence-backed):

  T1. TRUCK IDENTITY at observation level: state code 7 (SC_TRUCK
      = the capsule's 0x9E88 state word, mapped by the adapter).
      The R67 product run + the read-only truck-zone probe CAUGHT
      the v1.1.0 identity defect: ground soldiers in their walk/
      throw animation states (0x1594/0x1be0/0x1e38/0x340c/...) all
      present (sc=6, h=64, a4=0) — the (6, h=64) identity froze
      the T5 hold on a FALSE truck at px 493 (ep2 stuck 10000f).
      The probe read the REAL truck live: 0x9E88 at x 937.5, h=64,
      a4=300 (the capsule's parked-truck posture verbatim).
      hp_a4 is NOT in the read-only 21-float observation — the
      policy uses the EVIDENCED COUNTS instead (fresh truck
      hp_a4 = 300, grenade = 100 damage -> 3 grenades per truck).

  T2. GRENADE SEQUENCING (the R38 A/B evidence + the Oct-25 lob
      recipe): when the truck-like entity is inside the lob band
      TRUCK_LOB_MIN=40 .. TRUCK_LOB_MAX=135 world px -> GRENADE,
      at most TRUCK_GRENADES=3 per episode (the fresh-truck HP
      budget), cooldown GRENADE_CD, only while the LIVE grenade
      counter > 0.  NO corridor check on the lob (the Oct-25
      recipe is a lob: it clears ground blockers — disclosed).

  T3. SOLDIERS BEFORE THE TRUCK GUN (the D7 release recipe): a
      CLEAR-LINE escort soldier (state code in {1,2,3}, nothing
      mortal between player and soldier) HOLDS the lob — bullets
      go to the escort until it dies (frozen 0x4054 soldiers take
      2 AIMED bullets, the R40 evidence).  An escort BEHIND the
      truck is corridor-blocked (the R49 bullet-steal model) and
      never holds the lob: the grenade, which arcs, is the correct
      weapon there.

  T4. BUDGET INTERACTION: the truck grenade budget (3) is SEPARATE
      from the stall-ladder grenade budget (3, unchanged); both
      respect the live grenade counter.  After the truck budget is
      spent the fight posture below continues (the R38 evidence:
      sustained fire chips armored hp_a4 by ~10 per hit window).

  T5. THE HOLD (the R67 ep1 product-run lesson): at or inside the
      lob band's far edge the player NEVER advances — no WALK, no
      forward HOP (both walk the gun line; the R67 ep1 death was
      point-blank beside the truck with no rule able to engage).
      In the band: lob on schedule, standing chip-fire during the
      cooldown (the R38 posture), IDLE otherwise.
"""
from __future__ import annotations

import hashlib
import os
import time
from typing import Any, Dict, Sequence

from ps1play.runtime.errors import RuntimePolicyError
from ps1play.runtime.interfaces import (ActionDecision, GameObservation,
                                        Policy)

POLICY_NAME = "msx_mission1_rules"
POLICY_VERSION = "1.4.2"

# the hold band's inner edge (the R67 loop-probe lesson: holding at
# dx 52 — point-blank in the truck gun's line — LOST the duel; the
# R38 winning posture stood off and chipped.  The player holds the
# lob band's OUTER region 90..135 and backs off below 90.)
TRUCK_HOLD_MIN = 90.0

# the truck encounter (the R67 evidence-backed constants)
TRUCK_CODE = 7                   # SC_TRUCK (0x9E88; the R67 probe:
                                 #   ground soldiers in walk/throw
                                 #   states also present (6, h=64)
                                 #   — the (6, h=64) identity was a
                                 #   false-positive trap that froze
                                 #   the T5 hold at px 493)
TRUCK_LOB_MIN = 40.0             # the lob band (the Oct-25 recipe
TRUCK_LOB_MAX = 135.0            #   53-135, near edge widened for
                                 #   the arc — disclosed margin)
TRUCK_GRENADES = 3               # fresh hp_a4 300 / -100 per grenade
TRUCK_SPOT = 400.0               # the adapter's scan window (the
                                 #   probe's parked-truck posture sat
                                 #   at dx -226.5 — OUTSIDE the old
                                 #   220 engage window; T6 approach
                                 #   must reach it from there)
SOLDIER_CODES = (1, 2, 3)        # soft / wound / recovery

ENGAGE_SHORT = 220.0
FIRE_COOLDOWN = 12
HOP_PERIOD = 120
HOP_LEN = 3
STALL_DECISIONS = 120
GRENADE_CD = 90
PROGRESS_PX = 1.0

# state codes that can absorb a bullet or register a payment
# (7 = the armored truck: the R38 A/B evidence — sustained fire
# chips its hp_a4 — so it absorbs bullets and blocks for the
# corridor and escort-line checks)
MORTAL_CODES = (1, 2, 3, 5, 6, 7)
TRANSPARENT_CODE = 4


def _self_sha() -> str:
    with open(os.path.abspath(__file__), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class Mission1Policy(Policy):
    """The deterministic Mission-1 rules policy (game-owned)."""

    def __init__(self, config=None, telemetry=None):
        self._tel = telemetry
        self._sha = _self_sha()
        self._fire_cd = 0
        self._gren_cd = 0
        self._hop_left = 0
        self._since_hop = 0
        self._stall = 0
        self._last_px = None
        self._grenades_used = 0
        self._truck_grenades_used = 0
        self._facing = "R"            # v1.4.0: the player's facing
        self._last_diag: Dict[str, Any] = {}

    # ---- Policy contract ----
    def predict(self, observation: GameObservation) -> ActionDecision:
        t0 = time.perf_counter()
        try:
            action = self._decide(observation)
        except RuntimePolicyError:
            raise
        except Exception as e:
            raise RuntimePolicyError(
                f"msx mission1 policy failed: {type(e).__name__}: {e}")
        dt = (time.perf_counter() - t0) * 1000.0
        if self._tel is not None:
            self._tel.latency("policy_ms", dt)
        return ActionDecision(
            action=action, logits=None,
            frame_seq=observation.frame_seq,
            policy_name=f"{POLICY_NAME}:{POLICY_VERSION}",
            policy_sha256=self._sha, latency_ms=dt,
            diagnostics=dict(self._last_diag))

    def legal_actions(self) -> Sequence[str]:
        return ("IDLE", "WALK", "BACK", "FIRE", "HOP", "GRENADE")

    def reset(self) -> None:
        self._fire_cd = 0
        self._gren_cd = 0
        self._hop_left = 0
        self._since_hop = 0
        self._stall = 0
        self._last_px = None
        self._truck_grenades_used = 0
        self._facing = "R"

    def identity(self) -> Dict[str, Any]:
        # the engine's record seam reads identity()["name"] and
        # ["model_sha256"] (the R64 generic contract — the tetrade
        # policy uses the same keys for its built-in heuristic).
        return {"name": f"{POLICY_NAME}:{POLICY_VERSION}",
                "policy_name": POLICY_NAME,
                "policy_version": POLICY_VERSION,
                "model_sha256": self._sha,
                "policy_sha256": self._sha,
                "deterministic": True,
                "trained": False,
                "kind": "built-in rules (no model, no training)",
                "corridor_predicate": "r66_corrected",
                "truck_rules": "r67_grenade_sequencing"}

    def close(self) -> None:
        self._tel = None

    # ---- the rules ----
    def _decide(self, obs: GameObservation) -> str:
        x = obs.values
        alive = x[4] > 0.5
        px = float(x[0])
        gren = int(x[3])
        ents = []
        for i in range(5):
            dx = float(x[6 + 3 * i])
            sc = int(x[7 + 3 * i])
            h = float(x[8 + 3 * i])
            if sc == 0 and dx == 0.0:
                continue
            ents.append((dx, sc, h))

        if not alive:
            self._last_diag = {"rule": "dead", "px": px}
            return "IDLE"

        # ---- stall sensor (world-px progress) ----------------------
        if self._last_px is None or px >= self._last_px + PROGRESS_PX:
            self._stall = 0
        else:
            self._stall += 1
        self._last_px = px

        # ---- the facing helpers (v1.4.0) ----------------------------
        # FIRE shoots the FACING; WALK/HOP face right, BACK faces
        # left.  Every movement decision below books its facing.
        def turn_toward(side):
            if side == self._facing:
                return None
            return "WALK" if side == "R" else "BACK"

        def clear_line(dx_t):
            """No mortal between the player and a target at dx_t
            (the R66 corridor predicate, mirrored for the rear)."""
            if dx_t > 0:
                return not any(0.0 < b[0] < dx_t for b in ents
                               if b[1] in MORTAL_CODES)
            return not any(dx_t < b[0] < 0.0 for b in ents
                           if b[1] in MORTAL_CODES)

        # ---- the truck encounter (front OR rear) --------------------
        truck_any = next((e for e in ents
                          if e[1] == TRUCK_CODE and e[2] >= 64.0
                          and 0.0 < abs(e[0]) <= TRUCK_SPOT), None)
        if truck_any is not None:
            dx_t = truck_any[0]
            side_t = "R" if dx_t > 0 else "L"
            # T3: soldiers before the truck gun (the D7 recipe) —
            # the escort may stand on EITHER side; a clear-line
            # escort outranks the lob.
            soldier = next((e for e in ents
                            if e[1] in SOLDIER_CODES
                            and 8.0 < abs(e[0]) <= ENGAGE_SHORT
                            and clear_line(e[0])), None)
            if soldier is not None:
                side_s = "R" if soldier[0] > 0 else "L"
                if self._facing != side_s:
                    mv = turn_toward(side_s)
                    self._facing = side_s
                    self._last_diag = {"rule": "truck_escort_turn",
                                       "escort_dx": soldier[0]}
                    return mv
                if self._fire_cd == 0:
                    self._fire_cd = FIRE_COOLDOWN
                    self._last_diag = {"rule": "truck_escort_first",
                                       "target_dx": round(soldier[0], 1),
                                       "target_sc": soldier[1]}
                    return "FIRE"
            # T7: THE BLAST RETREAT (the R67 v1.4.0 product-run
            # lesson: the 3-lobs kill took the truck to 0 hp_a4 and
            # its death explosion killed the player standing in the
            # band — score 2300, the truck AIRBORNE in the death
            # shot).  Once the lob budget is spent, LEAVE the blast
            # radius until the truck leaves the observation (dead ->
            # the wreck row is not code 7).
            if self._truck_grenades_used >= TRUCK_GRENADES \
                    and abs(dx_t) <= TRUCK_LOB_MAX + 80.0:
                mv = "WALK" if side_t == "L" else "BACK"
                self._facing = "R" if mv == "WALK" else "L"
                self._last_diag = {"rule": "truck_blast_retreat",
                                   "truck_dx": round(dx_t, 1)}
                return mv
            # T2: the grenade sequencing (the R38 A/B evidence + the
            # Oct-25 lob recipe; a lob arcs — no corridor check).
            in_band = TRUCK_LOB_MIN <= abs(dx_t) <= TRUCK_LOB_MAX
            if in_band and abs(dx_t) >= TRUCK_HOLD_MIN \
                    and soldier is None and gren > 0 \
                    and self._gren_cd == 0 \
                    and self._truck_grenades_used < TRUCK_GRENADES:
                if self._facing != side_t:
                    mv = turn_toward(side_t)
                    self._facing = side_t
                    self._last_diag = {"rule": "truck_turn",
                                       "truck_dx": round(dx_t, 1)}
                    return mv
                self._gren_cd = GRENADE_CD
                self._truck_grenades_used += 1
                self._last_diag = {"rule": "truck_grenade",
                                   "truck_dx": round(dx_t, 1),
                                   "truck_h": truck_any[2],
                                   "grenades_used":
                                       self._truck_grenades_used}
                return "GRENADE"
            # T5: THE HOLD (at or inside the band: never advance
            # PAST the truck; stand and fight — the R38 posture).
            # v1.4.2: the hold lives in the band's OUTER region
            # (90..135) — below 90 the player BACKS OFF (the probe:
            # the dx-52 hold lost the gun duel, php 202 -> death).
            if abs(dx_t) <= TRUCK_LOB_MAX:
                if self._fire_cd > 0:
                    self._fire_cd -= 1
                if self._gren_cd > 0:
                    self._gren_cd -= 1
                if abs(dx_t) < TRUCK_HOLD_MIN:
                    # the back-off owns the sub-90 regime entirely
                    # (the facing turns AWAY — no lob turn here, or
                    # the policy would flip-flop WALK/BACK)
                    mv = "BACK" if side_t == "R" else "WALK"
                    self._facing = "L" if mv == "BACK" else "R"
                    self._last_diag = {"rule": "truck_hold_back_off",
                                       "truck_dx": round(dx_t, 1)}
                    return mv
                if self._facing != side_t:
                    mv = turn_toward(side_t)
                    self._facing = side_t
                    self._last_diag = {"rule": "truck_hold_turn",
                                       "truck_dx": round(dx_t, 1)}
                    return mv
                if in_band and self._fire_cd == 0:
                    self._fire_cd = FIRE_COOLDOWN
                    self._last_diag = {"rule": "truck_chip_fire",
                                       "truck_dx": round(dx_t, 1)}
                    return "FIRE"
                self._last_diag = {"rule": "truck_hold",
                                   "truck_dx": round(dx_t, 1)}
                return "IDLE"
            # T6: approach a truck out of the band (walk to it) —
            # NEVER re-approach once the lob budget is spent (the
            # blast retreat owns that case; the dying truck leaves
            # the observation on its own).
            if self._truck_grenades_used < TRUCK_GRENADES:
                mv = "WALK" if side_t == "R" else "BACK"
                self._facing = side_t
                self._last_diag = {"rule": "truck_approach",
                                   "truck_dx": round(dx_t, 1)}
                return mv
            # the budget is spent and the truck is outside the blast
            # margin: fall through to the generic rules — the dying
            # truck leaves the observation on its own (the wreck row
            # is not code 7), and a still-alive truck (a higher
            # hp_a4 variant, the capsule's [100,600] range) re-enters
            # the T7 retreat as the player drifts near it: a stable
            # edge patrol, never a frozen hold.
            self._last_diag = {"rule": "truck_spent_watch",
                               "truck_dx": round(dx_t, 1)}

        # ---- engagement (the R66 corridor predicate; FRONT) ---------
        target = None
        blocker = None
        cands = sorted((e for e in ents
                        if e[1] in MORTAL_CODES and 8.0 < e[0]
                        <= ENGAGE_SHORT),
                       key=lambda e: e[0])
        if cands:
            t_dx, t_sc = cands[0][:2]
            blocker = next((b for b in ents
                            if b[1] in MORTAL_CODES and b != cands[0]
                            and 0.0 < b[0] < t_dx), None)
            if blocker is None:
                target = (t_dx, t_sc)
        if target is not None:
            if self._facing != "R":
                # one WALK frame turns the player right (this branch
                # never runs at the default facing R — the v1.0.0
                # stream is preserved)
                self._facing = "R"
                self._last_diag = {"rule": "face_front",
                                   "target_dx": round(target[0], 1)}
                return "WALK"
            if self._fire_cd == 0:
                self._fire_cd = FIRE_COOLDOWN
                self._last_diag = {"rule": "engage",
                                   "target_dx": round(target[0], 1),
                                   "target_sc": target[1]}
                return "FIRE"

        # ---- REAR ENGAGE (v1.4.0; the R67 loop-probe evidence) ------
        # the wave walks PAST the pinned player (the right-side
        # spawns walking left): a rear mortal in the window with a
        # clear rear line is engaged — the D7 release recipe needs
        # the wave DEAD, and a forward-only policy stands pinned
        # while the rear kills it (the v1.0.0-v1.3.0 death shape,
        # three identical product runs).
        rcands = sorted((e for e in ents
                         if e[1] in MORTAL_CODES
                         and -ENGAGE_SHORT <= e[0] < -8.0),
                        key=lambda e: -e[0])
        if rcands and target is None:
            # the FRONT axis owns the facing while a front target is
            # engageable (the v1.0.0 discipline); the rear rule only
            # takes over a clear field — otherwise the policy would
            # flip-flop facings and freeze both cooldowns.
            r_e = rcands[0]
            if not any(r_e[0] < b[0] < 0.0 for b in ents
                       if b[1] in MORTAL_CODES and b is not r_e):
                if self._facing != "L":
                    self._facing = "L"
                    self._last_diag = {"rule": "face_rear",
                                       "target_dx": round(r_e[0], 1)}
                    return "BACK"
                if self._fire_cd == 0:
                    self._fire_cd = FIRE_COOLDOWN
                    self._last_diag = {"rule": "rear_engage",
                                       "target_dx": round(r_e[0], 1),
                                       "target_sc": r_e[1]}
                    return "FIRE"

        # ---- the bounded stall ladder -------------------------------
        if self._stall >= STALL_DECISIONS and gren > 0 \
                and self._gren_cd == 0 and self._grenades_used < 3:
            self._gren_cd = GRENADE_CD
            self._stall = self._stall // 2
            self._grenades_used += 1
            self._last_diag = {"rule": "stall_grenade",
                               "stall": self._stall}
            return "GRENADE"

        # ---- hop cadence --------------------------------------------
        if self._hop_left > 0:
            self._hop_left -= 1
            self._facing = "R"          # HOP = RIGHT+B
            return "HOP"
        self._since_hop += 1
        if self._since_hop >= HOP_PERIOD:
            self._since_hop = 0
            self._hop_left = HOP_LEN - 1
            self._facing = "R"
            return "HOP"

        # ---- cooldowns + default walk -------------------------------
        # the v1.0.0 walk-path tick VERBATIM (v1.3.0 restoration: the
        # v1.2.0 top-of-decide tick changed the fire cadence 13f->12f
        # and the deterministic wave trajectory diverged — the
        # walk-through starved the soldier wave (0 kills), the
        # section gate never resolved, the armored truck NEVER
        # entered (the probe: zero a4>=100 rows), and the player
        # died pinned at px 1164.  The v1.0.0/v1.1.0 cadence is the
        # evidence-backed wave-fight rhythm.)
        if self._fire_cd > 0:
            self._fire_cd -= 1
        if self._gren_cd > 0:
            self._gren_cd -= 1
        self._facing = "R"              # the default walk faces right
        self._last_diag = {"rule": "walk", "stall": self._stall,
                           "n_ent": len(ents)}
        return "WALK"
