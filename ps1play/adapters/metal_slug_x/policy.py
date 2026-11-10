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

  W8 (v1.5.0, amended v1.6.0). THE KILL TRANSITION: when the
      engaged truck leaves the observation AFTER AT LEAST ONE lob
      was thrown at it, the truck state resets (moot under the
      unlimited budget) and the W9 hazard arms.  Adapter 0.4.0
      filters the truck dead family {0xA304, 0xA44C, 0xA45C}, so
      the kill lands as a truck-gone transition.

  W9 (v1.5.0, R68). THE POST-KILL HAZARD RETREAT: the truck-gone
      kill transition arms a bounded hazard at the truck's
      last-known world px — the player retreats OUT of the blast
      band (|dx| > TRUCK_LOB_MAX + 80, the T7 margin) before
      advancing again.  Bounded (TRUCK_KILL_HAZARD_F frames),
      self-clears on distance; the cooldowns tick through it.

  C1 (v1.7.0, R69). THE CONNECT WINDOW (the R69 capsule lever, the
      product track): the R68 record run proved the lobs LAND at
      dx -133.5 from the STATIONARY THROW POSTURE (px 1071, the
      truck parked at 937.5): a4 300 -> 80 and FROZE at the band
      edge — the 90f cadence spent the ~280f window on 3 lobs.
      v1.7.0 narrows the fight to the MEASURED landing window:
        * the lob fires ONLY while |dx| in [TRUCK_CONNECT_MIN,
          TRUCK_CONNECT_MAX] = [125, 140], on the gre40 cadence
          (the R38 max-DPS evidence), facing correct, no
          clear-line escort, live grenade counter the only budget;
        * |dx| > 140: walk TOWARD the truck (the T6' chase,
          verbatim);
        * |dx| < 125 INSIDE the hold regime: RETREAT away (the
          sub-90 back-off generalized — standing inside 125
          stands in the gun line AND wastes the window; the R67
          dx-52 duel loss + the R68 connect posture at 133.5);
        * during the grenade cooldown the posture HOLDS (IDLE).
          The T5 standing chip-fire is WITHDRAWN for this test:
          the v1.6.1 evidence showed the bullets may not reach a
          truck behind the pin, and the window test isolates ONE
          variable — the lob cadence at the measured posture.
      The capsule hypothesis: the band window ~280f => up to 7
      throws => the kill inside the window at the measured rate.

      v1.7.1 (the R69 probe correction): the probe FALSIFIED the
      capsule's outer half — 3 in-window throws at dx -139.5/
      -136.5/-136.5 ALL missed (the truck a4 FROZEN at 300, 0
      connects) while the only observed connect remains the R68
      record's -133.5.  The window is TIGHTENED to [130, 135]:
      bracketing the measurement, the outer edge back at the R68
      band edge (135.4) where the window closed.  The scroll drift
      is measured too: each throw's animation costs ~+12px (the
      R68 record run drifted 1071 -> 1105.8 on 3 throws; the R69
      probe 1074 -> 1108.8 the same +35px) — the approach rule
      re-enters the tightened window after every throw.

  P1/P2/P3 (v1.8.0, R70). THE PHASE LAW (the R70 capsule lever,
      the product truck campaign; the r69b connect-probe
      evidence, slot 14):

      * the freeze: f811 (st 0x9E88 first seen; x 937.5, a4 300,
        sx 65 all frozen thereafter);
      * the two CONFIRMED connects landed at f989 and f1153 —
        the PERIOD 164f apart, both = freeze + 14 (mod 164);
      * the flight EXACTLY 30f twice (f959 -> f989,
        f1123 -> f1153);
      * the f877 lob landed f907 — 82f from BOTH grid points —
        and MISSED (the width < 82f, the center-hits connect).

      P1 — THE FIGHT CLOCK + THE PHASE GATE: the clock anchors on
      the freeze frame (the first SC_TRUCK sighting); the lob
      fires only when the land (throw + 30f) sits ON the grid
      freeze + 178 + 164k (tolerance 2f, one throw per grid k).
      The two R69 accidental connects become DETERMINISTIC.

      P2 — THE DRIVE-IN POSTURE (adapter v0.5.0 SC_TRUCK_IN = 8,
      the 0x9C14/0x9E08 states): during the scripted approach the
      park x is known (937.5, three records) so the C1 window
      semantics run on the PREDICTED post-freeze dx = 937.5 - px:
      the player walks to the record posture ~60f EARLIER than
      v1.7.1 managed (the r69b walk reached px 1071 only at
      f875 — after the freeze-window k=0 at f795 was gone).

      P3 — THE LEAD THROW (the R70 falsifiable arm): the k=0
      window (land = freeze + 14) sits BEFORE the first proven
      grid point; the throw must fire DURING the drive-in at
      freeze - 16, gated on the live closing-rate estimate (valid
      on >= 2 static frames, the disclosed precision limit +-2f)
      and the predicted-land window.  IF the lead connects: three
      connects (f825 + f989 + f1153) = a4 300 -> 0 = THE TRUCK
      KILL at ~f1153, 165f before the scripted scroll death at
      f1318.  IF it misses: the law is refuted at k=0 (honestly
      recorded) and the run still secures the deterministic
      f989/f1153 pair.

  THE R70 PROBE CORRECTIONS (v1.8.1; the r70_phase_probe evidence,
  boot 1): the v1.8.0 boot DIVERGED from the record timeline (the
  early walk dragged the section soldiers into the corridor; the
  f989 lob was STOLEN mid-descent by an interloper at dx ~-119 —
  the R49 steal model EXTENDED to lobs; the swarm then shoved the
  player out of the posture (the knockback from f985, exactly 164f
  before the r69 record's f1149 push — the scroll cycle and the
  vulnerability cycle are the SAME 164f clock, the independent
  second confirmation) and killed the player at f1154.  THE
  CORRECTIONS:

    C2. THE CORRIDOR GUARD (the lob refutation): the 'the arc
        clears the ground blockers' property is REFUTED — a lob
        descending into an occupied corridor is EATEN.  The C1
        lob now requires clear_line(dx_t) (the R66 corridor
        predicate); on the r69b record timeline the corridor was
        clean at every throw, so the guard is a no-op there.

    C3. THE DRIVE-IN HYGIENE: the truckin escort check drops the
        clear_line filter — ANY soldier within 8..220 on either
        side outranks the posture walk (turn + FIRE until the
        zone is clean); the r70 walk through an uncleared section
        is the root cause of the corridor thieves.

    C4. THE WIDTH PROBE (one-shot, the R70b arm): on the FIRST
        clean-hold frame at the posture (the corridor clear, the
        grenade ready) the policy books ONE sacrificed throw —
        the land sits at freeze + ~59 (the arrival-time offset):
        a CONNECT measures the window width >= 45f and unlocks
        the 3-connect kill schedule (the probe + the grid pair);
        a miss bounds the width < 45f (honestly recorded) and
        the grid pair still pays the 2 connects.

  THE R68 PROBE CORRECTION (scripts/r68_postkill_probe.py, the
  product stack v1.5.0, 1462f): the R67 "truck KILLED, score 2300"
  reading is HEREBY CORRECTED — the truck NEVER died.  The three
  lobs (f875/f972/f1063) landed ONE connect (-100) + sustained
  chips (-40): the truck row sat at a4=160 (0x9E88, x 937.5, h 64,
  slot 14) from f1160 to the death at f1462.  The player died
  PINNED at px 1164 (the section pin) with the PARKED truck behind
  at dx -226.5 — outside the lob band (135) and outside the T7
  blast margin (215): the v1.4.2 truck_spent_watch posture stood
  in the truck's gun line for ~300 frames with NO weapon that
  reaches.  The score 2300 came from the wave kills + chip events,
  not a truck kill.  CONSEQUENCES (v1.6.0):
    T2'. the lob budget is UNLIMITED — the live grenade counter is
         the only budget (the 3-lobs cap assumed every lob lands;
         the R38 kill evidence needed 3 CONNECTS at a ~1/10 rate);
    T6'. the STAND-GROUND CHIP-FIRE (v1.6.1): out of the lob band
         the BULLETS still reach — turn toward the truck and
         chip-fire on the cooldown while |dx| <= 220 (the R38
         sustained-fire model; the R68 probe: the a4 froze at 80
         the moment the fire stopped); beyond 220, walk toward.
         The v1.6.0 chase walk LOST ground (the px drifted +35
         while pressing BACK) and stood in the gun line.

  K1 (v1.9.0, R71). THE COOLDOWN CHIP-FIRE (the chip-connect kill
      schedule — the R71 capsule lever): the R70 evidence measured
      the chip payments (-10 a4 / +100 score) as a SECOND damage
      path: the C4 width probe landed a wrong-phase chip (300 ->
      290), the best boot ran a4 300 -> 230 on the escort strays
      at ~26f cadence under the walker feed, and the R68 record
      fight netted 1 connect + chips (-40).  THE KILL MATH (the
      R70 report): chips (-10 each) + TWO centered connects (-100
      each) reach a4 0 INSIDE the scroll-capped window — the kill
      does NOT need three phase-connects.  v1.9.0 therefore fires
      the aimed chip-fire DURING the grenade cooldown / the
      phase-hold at the record posture:
        * the chip-fire requires the corridor to the truck CLEAR
          (the C2 predicate on the bullet line — the v1.6.1
          failure mode, the bullets eaten by the corridor feed,
          is exactly what the guard removes);
        * the chip-fire requires NO escort (the T3 rule keeps
          precedence — bullets go to clear-line escorts first);
        * the chip-fire NEVER delays a grid throw: the grenade
          keeps priority when the phase opens with a ready
          grenade (the code order below); the fire cadence stays
          the escort FIRE_COOLDOWN (the wave-trajectory cadence
          law — the 12f rhythm is the verified section rhythm);
        * the corridor-feed law (the R70 boot-4 evidence): when
          the corridor is OCCUPIED the chip-fire is WITHHELD and
          the posture HOLDS — the walkers get cleaned by the
          escort rule first, so the corridor is clean AT each
          grid window and no bullet is wasted into the feed.
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
POLICY_VERSION = "1.9.0"

# the hold band's inner edge (the R67 loop-probe lesson: holding at
# dx 52 — point-blank in the truck gun's line — LOST the duel; the
# R38 winning posture stood off and chipped.  The player holds the
# lob band's OUTER region 90..135 and backs off below 90.)
# v1.7.0 (R69): TRUCK_HOLD_MIN is SUPERSEDED by the connect window
# (TRUCK_CONNECT_MIN) — the constant stays only for the W9
# blast-margin arithmetic lineage.
TRUCK_HOLD_MIN = 90.0

# C1 (v1.7.0, R69): THE CONNECT WINDOW — the measured landing band.
# The R68 record run: the lobs LANDED at dx -133.5 (px 1071, the
# truck parked at 937.5); the window brackets the measurement.
TRUCK_CONNECT_MIN = 130.0
TRUCK_CONNECT_MAX = 135.0
# v1.8.4 (R70): THE SPATIAL THROW BAND — the boot-4 evidence: the
# k=1 grid throw at dx -130.5 (the phase PERFECT, the corridor
# CLEAN) MISSED (no a4 transition), while every observed connect
# sits at dx -133.5 EXACTLY (the R68 record + the r69b pair) and
# the v1.7.0 outer throws (-136.5/-139.5) missed.  The connect
# geometry is ~+-3px TIGHT around -133.5; the quantized posture
# values are -130.5/-133.5/-135.4 — the band [131.5, 135.0]
# admits ONLY the proven -133.5 and rejects every measured miss.
# Below the band the C1-cont regime RETREATS (re-centers) so a
# knockback-drifted player is back at -133.5 inside the 3-frame
# phase tolerance.
TRUCK_THROW_MIN = 131.5
TRUCK_THROW_MAX = 135.0
# v1.7.0 ran the capsule's [125, 140]; the probe FALSIFIED the outer
# half: 3 in-window throws at dx -139.5/-136.5/-136.5 ALL missed
# (the truck a4 FROZEN at 300 through the whole fight — 0 connects),
# while the ONLY observed connect on the product path remains the
# R68 record's dx -133.5.  v1.7.1 tightens the window to [130, 135]
# (bracketing the measurement; the outer edge back at the R68 band
# edge 135.4 where the window closed).

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
TRUCK_KILL_HAZARD_F = 180        # W9: the post-kill hazard window
                                 #   (the death explosion + margin;
                                 #   self-clears on distance first)
TRUCK_GONE_CONFIRM_F = 12        # W8: the truck-gone confirmation
                                 #   window (a scan flicker must
                                 #   NOT fire the kill chain; the
                                 #   dead row stays gone)
SOLDIER_CODES = (1, 2, 3)        # soft / wound / recovery
ESCORT_CODES = (1, 2, 3, 5, 6)   # C5 (v1.8.2, R70): the corridor-
                                 #   ABSORBING escort classes minus
                                 #   the truck — the r70 boot-2
                                 #   evidence: the chasers approach
                                 #   in their walk/throw animation
                                 #   states (sc=6 — the R67 probe
                                 #   correction: ground soldiers)
                                 #   and the SOLDIER_CODES-only
                                 #   escort rules never engaged them
                                 #   (the corridor filled, the C2
                                 #   guard blocked the grid throw,
                                 #   the width probe was stolen);

ENGAGE_SHORT = 220.0
FIRE_COOLDOWN = 12
HOP_PERIOD = 120
HOP_LEN = 3
STALL_DECISIONS = 120
GRENADE_CD = 90
TRUCK_GRENADE_CD = 40           # the R38 encounter2 gre40 evidence:
                                #   "grenade every 40f = max DPS on
                                #   the truck" — the kill must land
                                #   INSIDE the ~280f band window
                                #   (the v1.6.0 probe: 3 lobs at the
                                #   90f cadence reached a4=80 and the
                                #   window closed)

# ---- R70 (v1.8.0): THE PHASE LAW -------------------------------------
# The r69b connect-probe evidence (slot 14, the parked truck):
#   * the freeze at f811 (st 0x9E88 first seen; x 937.5, a4 300,
#     sx 65 — ALL frozen thereafter);
#   * the two CONFIRMED connects landed at f989 and f1153 — the
#     PERIOD 164f apart, both = freeze + 14 (mod 164) (178 = 14 +
#     164, 342 = 14 + 2*164);
#   * the flight is EXACTLY 30f twice (f959 -> f989, f1123 -> f1153);
#   * the f877 lob landed f907 — 82f from BOTH grid points — and
#     MISSED: the window width is < 82f (the grid is real, the
#     center-hits connect).
# The kill needs THREE connects (a4 300 -> 0 at -100/connect): the
# schedule = the k=0 LEAD (land freeze+14, thrown DURING the
# drive-in — the truck parks at the measured 937.5 regardless; the
# player holds the record posture from f625-era evidence) + the
# grid k=0/k=1 (the two PROVEN connects, now deterministic).
TRUCK_LOB_FLIGHT = 30.0         # frames throw -> land (2/2 exact)
TRUCK_PHASE_PERIOD = 164.0      # the vulnerability cycle (2/2)
TRUCK_PHASE_BASE = 178.0        # the first grid land = freeze + 178
TRUCK_PHASE_TOL = 2.0           # the grid tolerance (frames)
TRUCK_LEAD_LAND = 14.0          # the k=0 lead land = freeze + 14
TRUCK_LEAD_CAP = 2              # the disclosed lead-throw cap
TRUCK_PARK_X = 937.5            # the scripted park (R68 probe + the
                                #   R69 v1.7.0/v1.7.1 runs — 3 records)
TRUCK_PARK_DX = -133.5          # the parked dx at the record posture
TRUCK_POSTURE_PX = 1071.0       # the record posture (R68/R69)
TRUCK_IN_DX_RATE = 1.25         # the drive-in closing rate (r69b:
                                #   f733 x 842.5 -> f808 x 937.5)
SC_TRUCK_IN = 8                 # the adapter v0.5.0 drive-in code
TRUCK_WIDTH_PROBE = 1           # C4: the one-shot width-probe cap
# K1 (v1.9.0, R71): the aimed cooldown chip-fire MASTER ARM.  The
# R71 boot-3 one-variable falsification arm patches this module
# attribute to False (disclosed pre-run in the probe's BOOT event):
# the boots 1-2 evidence — the phase-exact throws MISSED 0/2 on the
# v1.9.0 stream (the boot-1 k=1 theft stack + the boot-2 k=0
# corpse-field flyover) while the r69b gre40 volley connected 2/7
# from the SAME postures — so the question boot 3 answers: does the
# K1 chip-fire input stream itself perturb the vulnerability phase
# (the R67 cadence-law precedent: the fire cadence is part of the
# deterministic wave trajectory)?  False restores the exact v1.8.5
# hold semantics on the v0.5.2 adapter.
TRUCK_CHIP_FIRE = True
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
        self._truck_present = False   # v1.5.0: the truck-gone tracking
        self._truck_gone_f = 0        # v1.6.0: the confirmation window
        self._last_truck_dx = None    # v1.5.0: the last-known truck dx
        self._hazard = 0              # v1.5.0: W9 hazard frames left
        self._hazard_px = None        # v1.5.0: W9 the truck's world px
        self._truck_fight_f = 0       # v1.8.0: P1 the freeze-frame
                                      #   fight clock (the phase anchor)
        self._phase_last_k = -1       # v1.8.0: the last grid k thrown
        self._lead_spent = 0          # v1.8.0: the lead throws booked
        self._truckin_dx = None       # v1.8.0: the last drive-in dx
        self._truckin_px = None       # v1.8.0: the last drive-in px
        self._truckin_static = 0      # v1.8.0: the static-history count
        self._width_probed = 0        # v1.8.1: C4 the width probe
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
        self._truck_present = False
        self._truck_gone_f = 0
        self._last_truck_dx = None
        self._hazard = 0
        self._hazard_px = None
        self._truck_fight_f = 0
        self._phase_last_k = -1
        self._lead_spent = 0
        self._truckin_dx = None
        self._truckin_px = None
        self._truckin_static = 0
        self._width_probed = 0

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
                "corridor_predicate": "r70_corridor_guard",
                "truck_rules": "r71_chip_connect"}

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

        # ---- W9: the post-kill hazard retreat (v1.5.0) -------------
        # armed by the truck-gone kill transition below; the player
        # leaves the blast band before anything else (the R67 ep1
        # death: standing in the band while the death explosion
        # resolved).  The cooldowns tick through (the one-tick-per-
        # decision invariant); the hazard self-clears on distance.
        if self._hazard > 0:
            self._hazard -= 1
            if self._hazard_px is None or \
                    abs(self._hazard_px - px) > TRUCK_LOB_MAX + 80.0:
                self._hazard = 0          # out of the blast band
            else:
                if self._fire_cd > 0:
                    self._fire_cd -= 1
                if self._gren_cd > 0:
                    self._gren_cd -= 1
                mv = "BACK" if self._hazard_px > px else "WALK"
                self._facing = "L" if mv == "BACK" else "R"
                self._last_diag = {"rule": "truck_kill_retreat",
                                   "hazard_px":
                                       round(self._hazard_px, 1),
                                   "t_left": self._hazard}
                return mv

        # ---- the truck encounter (front OR rear) --------------------
        truck_any = next((e for e in ents
                          if e[1] == TRUCK_CODE and e[2] >= 64.0
                          and 0.0 < abs(e[0]) <= TRUCK_SPOT), None)
        truckin = next((e for e in ents
                        if e[1] == SC_TRUCK_IN and e[2] >= 64.0
                        and 0.0 < abs(e[0]) <= TRUCK_SPOT), None)
        if truck_any is not None:
            dx_t = truck_any[0]
            side_t = "R" if dx_t > 0 else "L"
            # P1 (v1.8.0, R70): THE FIGHT CLOCK — the phase anchor is
            # the FREEZE frame (the first SC_TRUCK sighting; the
            # r69b evidence: f811, st 0x9E88, x 937.5, a4 300, sx 65
            # all frozen thereafter).  The clock freezes through a
            # scan flicker (the W8 window) and resets only via the
            # episode reset — a confirmed-gone truck never returns
            # to the live table (the R40 wreck-complex evidence).
            if self._truck_present:
                self._truck_fight_f += 1
            else:
                # the RE-ANCHOR: a fresh truck = a fresh fight —
                # the grid bookkeeping and the lead budget reset
                # with the clock (the second-truck regression: the
                # stale k blocked the new fight's k=0 window)
                self._truck_fight_f = 0
                self._phase_last_k = -1
                self._lead_spent = 0
            self._truck_present = True        # v1.5.0: seen this frame
            self._truck_gone_f = 0            # v1.6.0: reset the window
            self._last_truck_dx = dx_t
            # T3: soldiers before the truck gun (the D7 recipe) —
            # the escort may stand on EITHER side; a clear-line
            # escort outranks the lob.
            soldier = next((e for e in ents
                            if e[1] in ESCORT_CODES
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
            # T7 REMOVED in v1.6.0 (the R68 probe correction): the
            # budget-spent blast retreat stood DOWN the fight while
            # the truck was still alive (the R68 probe: the truck
            # survived at a4=160 and the retreat posture left the
            # pinned player in the gun line with no reaching
            # weapon).  The post-kill blast safety is W9's job (the
            # kill transition retreats); the alive-truck fight is
            # T2'/T5/T6' below.
            # C1 (v1.7.0, R69): THE CONNECT WINDOW — the grenade
            # sequencing narrowed to the MEASURED landing band (the
            # R38 A/B evidence + the Oct-25 lob recipe: a lob arcs —
            # no corridor check; v1.6.0 stands: the budget is
            # UNLIMITED — the live grenade counter is the only
            # budget).  The R68 record run proved the lobs LAND at
            # dx -133.5 from the stationary throw posture (px 1071);
            # the window [125, 140] brackets that measurement.
            # During the cooldown the posture HOLDS (IDLE); the T5
            # chip-fire is WITHDRAWN for this test (the v1.6.1
            # evidence: the bullets may not reach; the window test
            # isolates ONE variable — the lob cadence at the
            # measured posture).
            in_win = TRUCK_CONNECT_MIN <= abs(dx_t) \
                <= TRUCK_CONNECT_MAX
            # P1 (cont., v1.8.0): THE PHASE GATE — the lob fires only
            # ON the vulnerability grid: the land (throw + the 30f
            # flight) must sit on freeze + 178 + 164k (the r69b
            # connects f989/f1153; the f877-center miss bounds the
            # width < 82f).  During the cooldown the connect hold
            # keeps precedence (the v1.7.1 semantics); off-grid with
            # a ready grenade the posture HOLDS (the phase-hold).
            phase_off = (self._truck_fight_f + TRUCK_LOB_FLIGHT
                         - TRUCK_PHASE_BASE) % TRUCK_PHASE_PERIOD
            phase_k = int(round((self._truck_fight_f + TRUCK_LOB_FLIGHT
                                 - TRUCK_PHASE_BASE)
                                / TRUCK_PHASE_PERIOD))
            phase_open = (phase_off <= TRUCK_PHASE_TOL
                          and phase_k != self._phase_last_k)
            # C2 (v1.8.1, R70): THE CORRIDOR GUARD — the r70 boot-1
            # evidence REFUTED the unconditional arc: a lob
            # descending into an occupied corridor is EATEN (the
            # f989 theft by the interloper at dx ~-119).  The lob
            # fires only over a CLEAN descent corridor (the R66
            # predicate on the truck's live dx; a no-op on the
            # r69b record timeline where the corridor was clean at
            # every throw).
            corridor_ok = clear_line(dx_t)
            throw_win = TRUCK_THROW_MIN <= abs(dx_t) \
                <= TRUCK_THROW_MAX

            def chip_fire():
                # K1 (v1.9.0, R71): THE COOLDOWN CHIP-FIRE — runs only
                # inside the corridor-cleared throw branch (the branch
                # guard IS the C2 bullet-line guard; the v1.6.1
                # bullets-eaten failure mode is what the guard
                # removes).  The grenade keeps priority: the
                # phase-open throw below never waits for the fire
                # cadence.  The cadence stays the escort FIRE_COOLDOWN
                # (the verified 12f wave rhythm — the cadence law).
                # The boot-3 falsification arm: TRUCK_CHIP_FIRE=False
                # restores the exact v1.8.5 idle-hold semantics (the
                # disclosed patch — the one-variable test).
                if not TRUCK_CHIP_FIRE:
                    if self._gren_cd > 0:
                        self._last_diag = {
                            "rule": "truck_connect_hold",
                            "truck_dx": round(dx_t, 1)}
                    else:
                        self._last_diag = {
                            "rule": "truck_phase_hold",
                            "truck_dx": round(dx_t, 1),
                            "fight_f": self._truck_fight_f,
                            "phase_off": round(phase_off, 1)}
                    return "IDLE"
                if self._fire_cd == 0:
                    if self._facing != side_t:
                        mv = turn_toward(side_t)
                        self._facing = side_t
                        self._last_diag = {
                            "rule": "truck_chip_turn",
                            "truck_dx": round(dx_t, 1)}
                        return mv
                    self._fire_cd = FIRE_COOLDOWN
                    self._last_diag = {
                        "rule": "truck_chip_fire",
                        "truck_dx": round(dx_t, 1),
                        "fight_f": self._truck_fight_f,
                        "phase_off": round(phase_off, 1)}
                    return "FIRE"
                self._last_diag = {"rule": "truck_chip_wait",
                                   "truck_dx": round(dx_t, 1),
                                   "fire_cd": self._fire_cd,
                                   "gren_cd": self._gren_cd}
                return "IDLE"

            if throw_win and soldier is None and corridor_ok \
                    and gren > 0:
                if self._fire_cd > 0:
                    self._fire_cd -= 1
                if self._gren_cd > 0:
                    self._gren_cd -= 1
                    # K1: the cooldown chip-fire (the corridor is
                    # clear here by the branch guard; the aimed
                    # bullets are the SECOND damage path — the R70
                    # chip evidence + the kill math: the chips + TWO
                    # centered connects reach a4 0 in-window).
                    return chip_fire()
                if not phase_open:
                    # C4 (v1.8.1, R70b): THE WIDTH PROBE — the
                    # post-freeze arm: the first clean in-window
                    # hold with a ready grenade books ONE
                    # sacrificed throw (the land offset = the
                    # arrival-time offset, ~freeze + 59): a CONNECT
                    # = one third of the kill AND the width's lower
                    # edge measured; a miss bounds the width
                    # honestly.  One shot, ever (the cap; the
                    # truckin pre-freeze arm has the lead priority).
                    if self._width_probed < TRUCK_WIDTH_PROBE:
                        if self._facing != side_t:
                            mv = turn_toward(side_t)
                            self._facing = side_t
                            self._last_diag = {
                                "rule": "truck_width_turn",
                                "truck_dx": round(dx_t, 1)}
                            return mv
                        self._gren_cd = TRUCK_GRENADE_CD
                        self._width_probed += 1
                        self._truck_grenades_used += 1
                        self._last_diag = {
                            "rule": "truck_width_probe",
                            "truck_dx": round(dx_t, 1),
                            "fight_f": self._truck_fight_f,
                            "width_probed": self._width_probed,
                            "grenades_used":
                                self._truck_grenades_used}
                        return "GRENADE"
                    # K1: the phase-hold chip-fire (the probe spent;
                    # the corridor is clear; the aimed bullets are the
                    # second damage path while the grid window is
                    # closed).
                    return chip_fire()
                if self._facing != side_t:
                    mv = turn_toward(side_t)
                    self._facing = side_t
                    self._last_diag = {"rule": "truck_turn",
                                       "truck_dx": round(dx_t, 1)}
                    return mv
                self._gren_cd = TRUCK_GRENADE_CD
                self._phase_last_k = phase_k
                self._truck_grenades_used += 1
                self._last_diag = {"rule": "truck_connect_grenade",
                                   "truck_dx": round(dx_t, 1),
                                   "truck_h": truck_any[2],
                                   "fight_f": self._truck_fight_f,
                                   "phase_k": phase_k,
                                   "grenades_used":
                                       self._truck_grenades_used}
                return "GRENADE"
            # C1 (cont.): INSIDE the hold regime (|dx| <= 140) but
            # not lobbing (no grenades / escort uncleared / below
            # the window): the cooldowns tick; below TRUCK_CONNECT_
            # MIN the player RETREATS away (the sub-90 back-off
            # generalized: standing inside 125 stands in the gun
            # line AND wastes the window; the R67 dx-52 duel loss).
            # The facing turns AWAY — no lob turn here, or the
            # policy would flip-flop WALK/BACK.
            if abs(dx_t) <= TRUCK_CONNECT_MAX:
                if self._fire_cd > 0:
                    self._fire_cd -= 1
                if self._gren_cd > 0:
                    self._gren_cd -= 1
                if abs(dx_t) < TRUCK_CONNECT_MIN:
                    # the sub-90 back-off generalized (v1.7.0): the
                    # away-retreat below the hold band.  (The v1.8.4
                    # re-center VARIANT is WITHDRAWN: the boot-5
                    # evidence — a -33px truck-gun knockback pinned
                    # the player at px 1038 for 126f (the scroll
                    # cancels the walk) and the gun line killed at
                    # f1076; no walk wins that state, so the band
                    # below the throw gate HOLDS instead of walking.)
                    mv = "BACK" if side_t == "R" else "WALK"
                    self._facing = "L" if mv == "BACK" else "R"
                    self._last_diag = {"rule": "truck_connect_retreat",
                                       "truck_dx": round(dx_t, 1)}
                    return mv
                self._last_diag = {"rule":
                                       ("truck_recenter_hold"
                                        if abs(dx_t) < TRUCK_THROW_MIN
                                        else "truck_hold"),
                                   "truck_dx": round(dx_t, 1)}
                return "IDLE"
            # T6' (v1.7.0 threshold = TRUCK_CONNECT_MAX; the R68
            # probe evidence): OUT OF THE CONNECT WINDOW (|dx| > 140)
            # = walk TOWARD the truck (re-enter the window).
            # THE TWO R68 FAILURE MODES, both probe-pinned:
            #   * v1.6.1's stand-ground chip-fire: the bullets DO
            #     NOT reach a truck behind the pin — the a4 sat at
            #     300 FROZEN through five 12f chip windows (the
            #     wave soldiers + the pin scenery eat the shot);
            #     the player died standing in the gun line.
            #   * the v1.4.2 spent_watch standoff: the same death,
            #     slower.
            # The v1.6.0 chase reached the band and held px 1071
            # (dx -133.5) where the lobs LANDED (the arc clears the
            # ground blockers — the disclosed lob property) and
            # drove a4 300 -> 80.  The band window closed only
            # because the 90f cadence spent it on 3 lobs; C1 above
            # fires the R38 gre40 max-DPS cadence so the kill lands
            # INSIDE the window.
            if gren > 0:
                if self._fire_cd > 0:
                    self._fire_cd -= 1
                if self._gren_cd > 0:
                    self._gren_cd -= 1
                mv = "WALK" if side_t == "R" else "BACK"
                self._facing = side_t
                self._last_diag = {"rule": "truck_approach",
                                   "truck_dx": round(dx_t, 1)}
                return mv
            # no grenades: nothing reaches a banded truck — fall
            # through to the generic rules (disclosed edge).
            self._last_diag = {"rule": "truck_spent_watch",
                               "truck_dx": round(dx_t, 1)}
        elif truckin is not None:
            # ---- P2/P3 (v1.8.0, R70): THE DRIVE-IN ARM -------------
            # The r69b evidence: the truck runs st 0x9C14 f733..f808
            # (x 842.5 -> 937.5 at +1.25 px/f, the armor a4 already
            # 300), then 0x9E08 (2f), then the freeze.  The park x is
            # SCRIPTED (937.5 — three records), so the POST-freeze dx
            # is predictable DURING the approach: pred_dx =
            # TRUCK_PARK_X - px.  The arm (a) walks the player to the
            # record posture EARLY (the C1 semantics on the predicted
            # dx) and (b) books the k=0 LEAD throw: the land must hit
            # freeze + 14 (the grid's backward extrapolation — the
            # R70 falsifiable arm), i.e. the throw at freeze - 16
            # (flight 30f), gated on the live closing-rate estimate
            # (valid only on >= 2 static player frames).
            dx_i = truckin[0]
            side_i = "R" if dx_i > 0 else "L"
            if self._fire_cd > 0:
                self._fire_cd -= 1
            if self._gren_cd > 0:
                self._gren_cd -= 1
            # the drive-in static history (the velocity validity)
            if self._truckin_dx is not None \
                    and px == self._truckin_px:
                self._truckin_static += 1
            else:
                self._truckin_static = 0
            v_in = (dx_i - self._truckin_dx) \
                if self._truckin_static >= 1 else 0.0
            self._truckin_px = px
            self._truckin_dx = dx_i
            # T3 mirror (C3, v1.8.1): ANY soldier within the engage
            # band on EITHER side outranks the arm — the clear_line
            # filter is DROPPED (the r70 boot-1 root cause: the walk
            # through an uncleared section dragged the soldiers into
            # the corridor as chasers; the occluded ones fall to the
            # same cadence — the R49 front-first steal model).
            soldier_i = next((e for e in ents
                              if e[1] in ESCORT_CODES
                              and 8.0 < abs(e[0]) <= ENGAGE_SHORT), None)
            if soldier_i is not None:
                side_s = "R" if soldier_i[0] > 0 else "L"
                if self._facing != side_s:
                    mv = turn_toward(side_s)
                    self._facing = side_s
                    self._last_diag = {"rule": "truckin_escort_turn",
                                       "escort_dx": soldier_i[0]}
                    return mv
                if self._fire_cd == 0:
                    self._fire_cd = FIRE_COOLDOWN
                    self._last_diag = {"rule": "truckin_escort_first",
                                       "target_dx":
                                           round(soldier_i[0], 1),
                                       "target_sc": soldier_i[1]}
                    return "FIRE"
            pred_dx = TRUCK_PARK_X - px
            in_pred = TRUCK_CONNECT_MIN <= abs(pred_dx) \
                <= TRUCK_CONNECT_MAX
            throw_pred = TRUCK_THROW_MIN <= abs(pred_dx) \
                <= TRUCK_THROW_MAX
            ftf = None
            if v_in > 0.05:
                ftf = (TRUCK_PARK_DX - dx_i) / v_in
            lead_open = (throw_pred and gren > 0
                         and self._gren_cd == 0
                         and ftf is not None
                         and self._truckin_static >= 2
                         and self._lead_spent < TRUCK_LEAD_CAP
                         and clear_line(pred_dx)
                         and abs(ftf - (TRUCK_LOB_FLIGHT
                                        - TRUCK_LEAD_LAND))
                         <= TRUCK_PHASE_TOL)
            if lead_open:
                if self._facing != side_i:
                    mv = turn_toward(side_i)
                    self._facing = side_i
                    self._last_diag = {"rule": "truck_lead_turn",
                                       "truckin_dx": round(dx_i, 1),
                                       "ftf": round(ftf, 1)}
                    return mv
                self._gren_cd = TRUCK_GRENADE_CD
                self._lead_spent += 1
                self._truck_grenades_used += 1
                self._last_diag = {"rule": "truck_lead_throw",
                                   "truckin_dx": round(dx_i, 1),
                                   "ftf": round(ftf, 1),
                                   "pred_dx": round(pred_dx, 1),
                                   "lead_spent": self._lead_spent,
                                   "grenades_used":
                                       self._truck_grenades_used}
                return "GRENADE"
            if in_pred:
                # C4 (v1.8.1, R70b): THE WIDTH PROBE — the FIRST
                # clean-hold frame at the posture books ONE
                # sacrificed throw (the corridor to the LAND point
                # must be clear; the lead, if open, has priority
                # above).  The land offset is the arrival-time
                # offset (~freeze + 59 on the v1.8.1 timeline): a
                # CONNECT = one third of the kill AND the width's
                # lower edge measured; a miss bounds the width
                # honestly.  One shot, ever (the cap).
                corridor_i = clear_line(pred_dx)
                # the probe yields to the lead: it fires only when
                # the lead is SPENT or its ftf window has PASSED
                # (the 2-static-frame history must exist first — the
                # v1.8.1 test-taught ordering)
                lead_dead = (self._lead_spent >= TRUCK_LEAD_CAP
                             or (ftf is not None
                                 and ftf < TRUCK_LOB_FLIGHT
                                 - TRUCK_LEAD_LAND
                                 - TRUCK_PHASE_TOL))
                if throw_pred and corridor_i and gren > 0 \
                        and self._gren_cd == 0 \
                        and self._truckin_static >= 2 \
                        and lead_dead \
                        and self._width_probed < TRUCK_WIDTH_PROBE:
                    if self._facing != side_i:
                        mv = turn_toward(side_i)
                        self._facing = side_i
                        self._last_diag = {"rule": "truck_width_turn",
                                           "pred_dx":
                                               round(pred_dx, 1)}
                        return mv
                    self._gren_cd = TRUCK_GRENADE_CD
                    self._width_probed += 1
                    self._truck_grenades_used += 1
                    self._last_diag = {"rule": "truck_width_probe",
                                       "pred_dx": round(pred_dx, 1),
                                       "truckin_dx": round(dx_i, 1),
                                       "width_probed":
                                           self._width_probed,
                                       "grenades_used":
                                           self._truck_grenades_used}
                    return "GRENADE"
                # the record posture held (IDLE) — the C1 semantics
                # on the predicted dx; the cooldowns ticked above.
                self._last_diag = {"rule": "truckin_hold",
                                   "pred_dx": round(pred_dx, 1),
                                   "ftf": (round(ftf, 1)
                                           if ftf is not None
                                           else None),
                                   "corridor": corridor_i,
                                   "static": self._truckin_static}
                return "IDLE"
            if abs(pred_dx) > TRUCK_CONNECT_MAX:
                # approach the record posture (toward the park)
                mv = "WALK" if side_i == "R" else "BACK"
                self._facing = side_i
                self._last_diag = {"rule": "truckin_approach",
                                   "pred_dx": round(pred_dx, 1)}
                return mv
            # |pred_dx| < THROW_MIN: HOLD (v1.8.5 — the re-center
            # walk withdrawn, see the C1-cont note; the throw gate
            # alone blocks the off-center spend)
            self._last_diag = {"rule": "truckin_hold",
                               "pred_dx": round(pred_dx, 1)}
            return "IDLE"
        elif self._truck_present:
            # ---- W8 (v1.6.0): the truck-gone CONFIRMATION window --
            # a scan flicker must NOT fire the kill chain: the truck
            # must stay absent TRUCK_GONE_CONFIRM_F consecutive
            # decisions.  During the window an ENGAGED truck's
            # absence holds position (never walk INTO a possible
            # blast); a never-engaged truck's absence lets the
            # generic rules continue.
            self._truck_gone_f += 1
            if self._truck_gone_f < TRUCK_GONE_CONFIRM_F:
                if self._truck_grenades_used >= 1:
                    self._last_diag = {"rule": "truck_gone_hold",
                                       "gone_f": self._truck_gone_f}
                    return "IDLE"
                # never engaged: fall through to the generic rules
            else:
                # the disappearance is CONFIRMED.  THE KILL
                # SIGNATURE: the adapter saw a dead-family row
                # (0xA304/0xA44C/0xA45C — the capsule-verified
                # kill states) THIS FRAME -> the truck died (the
                # wreck decays in place, the R38 evidence).  A
                # vanishing WITHOUT the dead row = the truck drove
                # off: reset, NO hazard, move on.
                self._truck_present = False
                self._truck_gone_f = 0
                dead_x = obs.diagnostics.get("dead_truck_x") \
                    if obs.diagnostics else None
                if self._truck_grenades_used >= 1:
                    self._truck_grenades_used = 0
                    self._gren_cd = 0
                    if dead_x is not None:
                        # W9: the kill confirmed — leave the blast
                        # band before advancing (the hazard sits at
                        # the WRECK's own position, the blast
                        # center).
                        self._hazard = TRUCK_KILL_HAZARD_F
                        self._hazard_px = float(dead_x)
                        if abs(self._hazard_px - px) <= \
                                TRUCK_LOB_MAX + 80.0:
                            mv = "BACK" if self._hazard_px > px \
                                else "WALK"
                            self._facing = "L" if mv == "BACK" \
                                else "R"
                            self._last_diag = {
                                "rule": "truck_kill_retreat",
                                "hazard_px":
                                    round(self._hazard_px, 1),
                                "t_left": self._hazard}
                            return mv
                        self._last_diag = {
                            "rule": "truck_kill_transition",
                            "hazard_px":
                                round(self._hazard_px, 1)}
                    else:
                        self._last_diag = {
                            "rule": "truck_drove_off",
                            "last_dx": (round(self._last_truck_dx, 1)
                                        if self._last_truck_dx
                                        is not None else None)}

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
