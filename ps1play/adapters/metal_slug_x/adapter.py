"""ps1play.adapters.metal_slug_x.adapter — the Metal Slug X GameAdapter
(R66).

The FIRST runtime adapter for the retail SLUS-01212 disc.  Perception
is RAM-read-based (the loop Issues #4/#5 document; R63/R64/R65
precedent) — read-only, zero writes, zero core edits, legal controller
input only.  ALL game knowledge here is Metal Slug X's own: the
verified anchor map comes from THIS game's capsule
(data/knowledge/msx/capsule.json) and the R38-R52 evidence tree; no
other game's anchors, states, or policy appear anywhere in this
package.

Verified anchor map (statuses from the capsule; every address below is
VERIFIED or TESTED in the R38-R52 evidence tree and re-validated by
the R66 boots):

  PLAYER_X  0x0CA2E0  u32 16.16   world px  (VERIFIED)
  PLAYER_HP 0x0CA2F6  u16         indicator (TESTED — R38 contradiction
                                   rule: never a gate by itself)
  A_SCORE   0x0EE318  u32         score     (VERIFIED)
  GRENADES  0x0EDCF4  u8          grenades  (TESTED)
  A_FLAGS   0x0EE518  u32         alive word: (raw & 0xFF)==0xFF AND
                                   px!=0  == alive (VERIFIED 4/4 live
                                   correlation; the honest game-over
                                   sensor)
  TABLE     0x0CA268  stride 0x14C, slots 1..39; per slot:
                     st @+0x00 (u16 state handler), x @+0x78 (u32
                     16.16 world px), h @+0x7E (u16 height),
                     sx @+0x8E (u16 screen x)   (VERIFIED)

Observation vector (float32, 21 values — ONE source of truth here;
policy.py decodes it and the tests cross-check):

    [0] px     world px
    [1] score
    [2] php    player hp indicator
    [3] gren   grenades
    [4] alive  1.0 alive / 0.0 not
    [5] gate   1.0 the input-ownership gate last held / 0.0
    [6..20]    the 5 nearest MORTAL entities (enemy-kind, non-corpse),
               nearest first, 3 floats each:
                 dx  (target_x - px, world px; negative = behind)
                 sc  state code (0 none, 1 fresh-soft 0x4054,
                     2 wound 0x42bc, 3 recovery family 0x3f48/0x2b74/
                     0x17f8/0x4008, 4 transparent 0xab94, 5 0xae7c,
                     6 other-live, 7 the armored truck 0x9E88 — the
                     R67 probe correction: ground soldiers in their
                     walk/throw animation states also present
                     (sc=6, h=64), so the truck MUST be keyed on
                     its state word, not on (6, 64),
                     8 the truck DRIVE-IN 0x9C14/0x9E08 — v0.5.0
                     (R70): the scripted pre-park states measured
                     in the r69b connect probe (slot 14, f733..f810:
                     x 842.5 -> 937.5 at +1.25 px/f, a4 already 300,
                     h 64) — distinct from every soldier walk/throw
                     state; lets the policy see the approach BEFORE
                     the 0x9E88 freeze (the R70 lead-throw arm))
                 h   height word

Episode semantics: one episode = one life.  Death (the alive word
fails) is terminal; the NEXT episode's start_episode performs the
continue-screen recovery (START taps, bounded) before re-arming the
gate.  Save states are NOT used by the adapter at all.

v0.4.0 (R68): the truck dead family {0xA304, 0xA44C, 0xA45C} joins
CORPSE_ST (the capsule-verified death/wreck states never absorb a
bullet or pay; see the constant block for the evidence chain).

v0.5.0 (R70): the truck DRIVE-IN states 0x9C14/0x9E08 map to a new
SC_TRUCK_IN = 8 (the r69b evidence: slot 14 ran 0x9C14 from f733 to
f808 — x 842.5 -> 937.5 at +1.25 px/f with the armor a4 already 300 —
then 0x9E08 f809-f810, then the freeze 0x9E88 at f811).  The mapping
is READ-ONLY perception: it changes no behavior by itself; the
policy (v1.8.0) consumes it for the early-posture walk + the
lead-throw schedule.  No soldier state collides with 0x9C14/0x9E08
(the soldier walk/throw family is 0x1594/0x1be0/0x1e38/0x340c/...).

v0.5.2 (R71): THE A4-AWARE LIVENESS FILTER (the r71 boot-1
perception defect, both directions):

  * THE GHOST BLOCKER: the k=0 grid window (f959-961) was withheld
    by a row the R66 predicate itself excludes — slot23 st 0x6730,
    x 995.0, h 64, a4 0, FROZEN through the window: an unknown
    dead-walk state NOT in CORPSE_ST.  a4 == 0 rows can neither
    absorb a bullet nor register a payment (the committed R66
    pass-B law) — unknown a4 == 0 rows leave the observation (the
    KNOWN states keep the committed semantics whatever their a4).
  * THE INVISIBLE THIEF: the phase-exact k=1 lob (f1123, dx
    -133.5, the record posture verbatim) did NOT connect — the
    probe table shows the LIVE stack at x 1062.3 the observation
    never saw: 0xb4e4 (a4 30, h 102), 0xabdc (a4 300, h 205),
    0xb4e4 (a4 30, h 142) — the h > GROUND_HEIGHT drop ("airborne:
    never blocks", the v0.4.0 semantics) hid the chaser-throw
    band.  The r70 f989 mid-descent theft is the same shape.  The
    refinement: the h > GROUND_HEIGHT rows with LIVE a4 (> 0) are
    PACKED (they absorb/steal — the corridor feed), while the
    a4 <= 0 airborne rows stay dropped (projectiles).
  * THE PROJECTILE GUARD: the R66 GATE_DIAG dump's in-flight
    projectile_air states (0xbdf8/0x2950/0x9558/0xac64) stay
    EXCLUDED from the kept band regardless of a4 — the committed
    gate-starvation fix must not regress (these rows cannot
    interact with player bullets, n=13+13 skips).  0x1be0 is
    resolved to the R70 walker semantics (the evidence conflict
    disclosed in the constant block).
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from ps1play.runtime.errors import AdapterError, EmulatorError
from ps1play.runtime.interfaces import (ActionDecision, Frame,
                                        GameAdapter, GameObservation)

ADAPTER_VERSION = "0.5.2"

# ---- the verified anchor map (THIS game only) -------------------------
PLAYER_X = 0x0CA2E0
PLAYER_HP = 0x0CA2F6
A_SCORE = 0x0EE318
GRENADES = 0x0EDCF4
A_FLAGS = 0x0EE518
PAD_MIRROR = 0x0D4948
TABLE = 0x0CA268
STRIDE = 0x14C
SLOTS = 40                       # slot 0 = player, 1..39 world entities

# state families (the R48-R52 + R66 evidence)
ST_SOFT = 0x4054                 # fresh soft soldier
ST_WOUND = 0x42BC                # hit-reaction (wound) state
ST_RECOVERY = (0x3F48, 0x2B74, 0x17F8, 0x4008)
ST_TRANSPARENT = 0xAB94          # bullet-transparent (n=4, R50/R51)
ST_AE7C = 0xAE7C                 # absorbs bullets, registered kills
# dead/dying states (the committed evidence: combat.CORPSE_ST + the
# R50/R51/R66 death-registration terminal 0x5B0C)
CORPSE_ST = frozenset({0x4BE4, 0x5CC8, 0x5B0C})

# v0.4.0 (R68): the ARMORED TRUCK dead family.  The capsule evidence
# (all VERIFIED/GAMEPLAY_VERIFIED): the truck's death state word0 =
# 0xA304 (the Oct-25 campaign: hp_a4 -> 0 flips the state word), the
# wreck 0xA44C (R38: the wreck residual decays 30 -> 10 -> row gone)
# and the wreck fire/smoke 0xA45C (R40: the wreck complex held the
# engage mode 75/81 chunks on a DEAD row).  None of the three ever
# absorbed a player bullet or registered a payment across R38-R52 —
# a dead truck is exactly the "cannot absorb / cannot pay" case the
# R66 corridor predicate excludes.  In the product observation they
# were SC_OTHER (6) rows BEFORE v0.4.0: the R67 ep1 post-kill death
# is pinned on that (the policy stood in the blast band engaging the
# wreck row while the death explosion resolved).  From v0.4.0 the
# dead truck leaves the observation at the kill moment (the row is
# filtered) — the policy's kill transition sees truck-gone instead.
# The experiment-track census path (scripts r48t1/r66t1) keeps its
# own corpse sets — this change is adapter-scope only (disclosed).
ST_TRUCK_DEAD = (0xA304, 0xA44C, 0xA45C)
CORPSE_ST = frozenset(CORPSE_ST | set(ST_TRUCK_DEAD))
GROUND_HEIGHT = 64               # +0x7E ground contact (session-2)
SX_MAX = 600                     # sane screen-x band (scan_entities)

# state codes packed into the observation
SC_NONE, SC_SOFT, SC_WOUND, SC_RECOVERY, SC_TRANSPARENT, SC_AE7C, \
    SC_OTHER, SC_TRUCK, SC_TRUCK_IN = 0, 1, 2, 3, 4, 5, 6, 7, 8

OBS_LEN = 21
N_PACKED = 5                     # nearest mortals packed into the obs

# gate constants (the proven issue4/mission gate, ported verbatim)
START_HOLD = 12
START_SETTLE = 150
OWN_WINDOWS = 5
OWN_WINDOW_F = 10
OWN_RIGHT_F = 30
GATE_TRIES = 4
RECOVER_TRIES = 8

ENGAGE_SHORT = 220.0             # stop-and-fire window (world px)
FIRE_COOLDOWN = 12               # frames between aimed shots
HOP_PERIOD = 120                 # walk-cadence hop period (frames)
HOP_LEN = 3                      # hop press length (frames)
STALL_DECISIONS = 120            # px-flat streak before the ladder


ST_TRUCK = 0x9E88                # the armored truck (the capsule
                                 #   identity; the R67 probe read it
                                 #   LIVE at x 937.5 h 64 a4 300)
ST_TRUCK_IN = (0x9C14, 0x9E08)   # v0.5.0 (R70): the DRIVE-IN states
                                 #   (the r69b probe: slot 14 f733..f810
                                 #   x 842.5 -> 937.5 at +1.25 px/f,
                                 #   a4 300 already set; 0x9E08 = the
                                 #   2-frame pre-freeze state f809/f810)

# v0.5.2 (R71): the R66 GATE_DIAG dump's in-flight projectile_air
# states (n=13+13 skips: they cannot absorb a player bullet nor
# register a payment) — excluded from the kept h>GROUND_HEIGHT band
# regardless of a4 (the committed gate-starvation fix).
# 0x1BE0 is NOT in this set: the committed R70 packing evidence
# treats it as a SOLDIER walk/throw state (the policy docstring
# family 0x1594/0x1be0/0x1e38/0x340c) while the R66 dump listed it
# among the projectile rows — the evidence conflict is resolved
# toward the later R70 walker semantics, and the a4 == 0 rule
# handles the dead 0x1be0 rows either way (disclosed).
ST_PROJECTILE_AIR = (0xBDF8, 0x2950, 0x9558, 0xAC64)

# the KNOWN live states keep the committed semantics whatever their
# a4 word (the R48-R52 + R66-R70 evidence set)
_KNOWN_LIVE_ST = frozenset((ST_SOFT, ST_WOUND, ST_TRANSPARENT,
                            ST_AE7C, ST_TRUCK)
                           + ST_TRUCK_IN + ST_RECOVERY)


def state_code(st: int) -> int:
    if st == ST_SOFT:
        return SC_SOFT
    if st == ST_WOUND:
        return SC_WOUND
    if st in ST_RECOVERY:
        return SC_RECOVERY
    if st == ST_TRANSPARENT:
        return SC_TRANSPARENT
    if st == ST_AE7C:
        return SC_AE7C
    if st == ST_TRUCK:
        return SC_TRUCK
    if st in ST_TRUCK_IN:
        return SC_TRUCK_IN
    return SC_OTHER


class MetalSlugXAdapter(GameAdapter):
    game_id = "metal_slug_x"
    version = ADAPTER_VERSION

    FEATURE_NAMES = ("px", "score", "php", "gren", "alive", "gate",
                     "e0dx", "e0sc", "e0h", "e1dx", "e1sc", "e1h",
                     "e2dx", "e2sc", "e2h", "e3dx", "e3sc", "e3h",
                     "e4dx", "e4sc", "e4h")

    def __init__(self, env, telemetry=None):
        self.env = env
        self._tel = telemetry
        self._score = 0
        self._max_score = 0
        self._px = 0.0
        self._max_px = 0.0
        self._fires = 0
        self._hops = 0
        self._grenades = 0
        self._steps = 0
        self._deaths = 0
        self._gate_ok = False
        self._last_diag: Dict[str, Any] = {}
        self._ready_seen = False

    # ------------------------------------------------------------ --
    # RAM access (read-only)
    # ------------------------------------------------------------ --
    def _m(self):
        return self.env.p.mem

    def _run(self, frames: int, buttons=frozenset()) -> None:
        try:
            self.env.run(int(frames), set(buttons))
        except Exception as e:
            raise EmulatorError(f"env.run failed: "
                                f"{type(e).__name__}: {e}")

    def _u32(self, a: int) -> int:
        return int(self._m().u32(a))

    def _u16(self, a: int) -> int:
        return int(self._m().u16(a))

    def _u8(self, a: int) -> int:
        return int(self._m().u8(a))

    # ------------------------------------------------------------ --
    # the KILL SIGNATURE (v0.4.0): the truck dead family seen LIVE
    # ------------------------------------------------------------ --
    def dead_truck_x(self, px: float) -> Optional[float]:
        """The nearest ARMORED-TRUCK DEAD-FAMILY row this frame
        (st in {0xA304, 0xA44C, 0xA45C} — the capsule-verified
        death/wreck states), as world px; None when no dead truck
        is on the table.  This is the policy's kill confirmation:
        a truck row that vanishes WITHOUT a dead-family sighting
        drove off (no blast hazard); a vanishing WITH one is the
        kill (the R38 wreck decays in place, the row gone later).
        Read-only; diagnostics-only (the 21-float obs contract is
        unchanged)."""
        best = None
        for s in range(1, SLOTS):
            base = TABLE + s * STRIDE
            st = self._u16(base)
            if st not in ST_TRUCK_DEAD:
                continue
            xw = self._u32(base + 0x78)
            if not xw:
                continue
            x = xw / 65536.0
            if best is None or abs(x - px) < abs(best - px):
                best = x
        return best

    def px_of(self) -> float:
        return self._u32(PLAYER_X) / 65536.0

    def alive(self) -> bool:
        return (self._u32(A_FLAGS) & 0xFF) == 0xFF \
            and self.px_of() != 0.0

    def scan_mortals(self, px: float) -> List[Dict[str, float]]:
        """The 5 nearest GROUND MORTALS: non-corpse, live screen-x,
        on the ground band (h <= GROUND_HEIGHT — the verified
        kind==enemy classifier; airborne rows are projectiles/wasps
        and never absorb a player bullet).  Read directly from the
        verified entity table (read-only).

        v0.5.1 (R70): the TRUCK-FAMILY rows (st 0x9E88/0x9C14/
        0x9E08) carry PACKING PRIORITY — the r70 boot-3 evidence:
        with five chasers nearer than the parked truck the nearest-5
        cut DROPPED the truck row (f909..f958), the policy's W8
        window read it as a confirmed drive-off, the fight clock
        re-anchored and the deterministic grid throw was spent 248f
        late.  The truck is the fight's anchor: when its row survives
        the live filters but loses the nearest-5 cut, it displaces
        the FARTHEST packed row.  No soldier state collides with the
        truck family; the dead family (0xA304/0xA44C/0xA45C) stays
        excluded via CORPSE_ST (the v0.4.0 semantics)."""
        out = []
        truck_row = None
        for s in range(1, SLOTS):
            base = TABLE + s * STRIDE
            st = self._u16(base)
            xw = self._u32(base + 0x78)
            if not xw:
                continue
            x = xw / 65536.0
            if st in CORPSE_ST or not 0.0 < x < 4096.0:
                continue
            a4 = self._u16(base + 0xA4)
            h = self._u16(base + 0x7E)
            # v0.5.2 (R71): THE A4-AWARE LIVENESS FILTER
            #   * unknown a4 == 0 rows never absorb/register (the
            #     R66 predicate) — the r71 boot-1 ghost 0x6730
            #     blocked the k=0 window while dead; the KNOWN
            #     states keep the committed semantics.
            #   * the h > GROUND_HEIGHT drop is refined: the LIVE
            #     (a4 > 0) rows in the chaser-throw band STEAL LOBS
            #     (the r71 boot-1 k=1 theft: the invisible stack at
            #     x 1062.3); the a4 <= 0 airborne rows stay dropped
            #     (projectiles); the R66 projectile_air states stay
            #     excluded regardless of a4 (the committed fix).
            if st not in _KNOWN_LIVE_ST and a4 == 0:
                continue
            if h > GROUND_HEIGHT and (a4 <= 0
                                      or st in ST_PROJECTILE_AIR):
                continue
            if abs(x - px) > 400.0:      # the scan window
                continue
            sx = self._u16(base + 0x8E)
            if not 0 < sx <= SX_MAX:     # live-screen-x band
                continue
            row = {"slot": s, "st": st, "x": x,
                   "dx": x - px, "h": h}
            if st == ST_TRUCK or st in ST_TRUCK_IN:
                truck_row = row          # the fight anchor
                continue
            out.append(row)
        out.sort(key=lambda e: abs(e["dx"]))
        packed = out[:N_PACKED]
        if truck_row is not None and \
                all(p["slot"] != truck_row["slot"] for p in packed):
            if len(packed) >= N_PACKED:
                packed[-1] = truck_row   # displace the farthest
            else:
                packed.append(truck_row)  # the sparse-table case
            packed.sort(key=lambda e: abs(e["dx"]))
        return packed

    # ------------------------------------------------------------ --
    # the input-ownership gate (ported from the proven scripts; the
    # only gate that distinguishes real play from the attract demo)
    # ------------------------------------------------------------ --
    def _pad_idle_zero(self) -> List[int]:
        idles = []
        for _ in range(OWN_WINDOWS):
            self._run(OWN_WINDOW_F)
            idles.append(self._u16(PAD_MIRROR))
        return idles

    def _owns_pad(self) -> bool:
        idles = self._pad_idle_zero()
        if not all(v == 0 for v in idles):
            return False
        self._run(OWN_RIGHT_F, {"RIGHT"})
        return self.px_of() != 0.0 and self.alive()

    def _in_mission(self) -> bool:
        """The three-signal gate: idle mirror zero + pad toggling +
        the alive word.  (The world-churn leg of the original gate is
        folded into the alive check: the R66 boot re-validated that
        this combination never passes on the attract demo — the demo
        self-presses, so its idle mirror is never all-zero.)"""
        idles = self._pad_idle_zero()
        if not all(v == 0 for v in idles):
            return False
        self._run(8, {"RIGHT"})
        w1 = self._u16(PAD_MIRROR)
        self._run(6)
        w2 = self._u16(PAD_MIRROR)
        return bool((w1 & 0x20) and not (w2 & 0x20) and self.alive())

    # ------------------------------------------------------------ --
    # lifecycle
    # ------------------------------------------------------------ --
    def wait_ready(self, deadline_s: float) -> Any:
        """Boot flow: settle -> the proven enter_gameplay3 navigation
        -> START taps until input ownership -> the mission gate.
        Raises EmulatorError on timeout (the engine re-boots)."""
        t0 = time.time()
        try:
            self._run(60)
            nav = self.env.p.enter_gameplay3()
            owned = False
            for _ in range(6):
                self._run(START_HOLD, {"START"})
                self._run(START_SETTLE)
                if self._owns_pad():
                    owned = True
                    break
            if not owned:
                raise EmulatorError(
                    "metal_slug_x: input ownership not achieved")
            for k in range(GATE_TRIES):
                if self._in_mission():
                    self._gate_ok = True
                    break
                self._run(15, {"START"})       # human recovery
                self._run(90)
            if not self._gate_ok:
                raise EmulatorError(
                    "metal_slug_x: mission gate failed after ownership")
        except EmulatorError:
            raise
        except Exception as e:
            raise EmulatorError(f"metal_slug_x ready flow failed: "
                                f"{type(e).__name__}: {e}")
        if time.time() - t0 > deadline_s:
            raise EmulatorError(
                f"metal_slug_x ready flow exceeded deadline "
                f"({deadline_s}s)")
        self._ready_seen = True
        self._score = self._u32(A_SCORE)
        self._px = self.px_of()
        self._last_diag = {"px": round(self._px, 1),
                           "score": self._score,
                           "php": self._u16(PLAYER_HP)}
        if self._tel is not None:
            self._tel.emit("metal_slug_x_ready",
                           px=round(self._px, 1), score=self._score,
                           nav=str(nav)[:80])
        return True

    def start_episode(self, seed_k: int) -> int:
        """One episode = one life.  Recover from any death/continue
        screen first (START taps, bounded), then re-arm the gate.
        seed_k is labeling-only (zero-writes: the game RNG is never
        seeded)."""
        self._steps = 0
        self._fires = 0
        self._hops = 0
        self._grenades = 0
        f0 = int(getattr(self.env.p.core, "frames_run", 0))
        if not self.alive():
            self._deaths += 1
            for k in range(RECOVER_TRIES):
                self._run(15, {"START"})
                self._run(90)
                if self.alive() and self._in_mission():
                    break
            else:
                raise EmulatorError(
                    "metal_slug_x: continue recovery failed "
                    "(no live mission after START taps)")
        if not self._in_mission():
            for k in range(GATE_TRIES):
                if self._in_mission():
                    self._gate_ok = True
                    break
                self._run(15, {"START"})
                self._run(90)
            else:
                raise EmulatorError(
                    "metal_slug_x: mission gate failed at episode "
                    "start")
        self._gate_ok = True
        self._score = self._u32(A_SCORE)
        self._px = self.px_of()
        self._max_px = max(self._max_px, self._px)
        if self._tel is not None:
            self._tel.emit("metal_slug_x_episode_start",
                           seed_k=int(seed_k),
                           start_frames=int(
                               getattr(self.env.p.core, "frames_run",
                                       0)) - f0,
                           deaths=self._deaths)
        return int(getattr(self.env.p.core, "frames_run", 0)) - f0

    def reset_episode(self) -> None:
        self._steps = 0
        self._fires = 0
        self._hops = 0
        self._grenades = 0

    # ------------------------------------------------------------ --
    # observation
    # ------------------------------------------------------------ --
    def observe(self, frame: Frame) -> GameObservation:
        try:
            px = self.px_of()
            score = self._u32(A_SCORE)
            php = self._u16(PLAYER_HP)
            gren = self._u8(GRENADES)
            al = self.alive()
            mortals = self.scan_mortals(px) if al else []
            dead_x = self.dead_truck_x(px) if al else None
            x = np.zeros(OBS_LEN, dtype=np.float32)
            x[0] = px
            x[1] = float(score)
            x[2] = float(php)
            x[3] = float(gren)
            x[4] = 1.0 if al else 0.0
            x[5] = 1.0 if self._gate_ok else 0.0
            for i, e in enumerate(mortals):
                x[6 + 3 * i] = round(float(e["dx"]), 1)
                x[7 + 3 * i] = float(state_code(e["st"]))
                x[8 + 3 * i] = float(e["h"])
            self._score = int(score)
            self._max_score = max(self._max_score, int(score))
            self._px = px
            self._max_px = max(self._max_px, px)
            self._last_diag = {"px": round(px, 1), "score": score,
                               "php": int(php), "gren": int(gren),
                               "alive": bool(al),
                               "n_mortals": len(mortals),
                               "dead_truck_x": (round(dead_x, 1)
                                                if dead_x is not None
                                                else None)}
            return GameObservation(
                values=x, frame_seq=frame.seq,
                frame_id=frame.frame_id, timestamp=frame.timestamp,
                valid=True, diagnostics=dict(self._last_diag))
        except (AdapterError, EmulatorError):
            raise
        except Exception as e:
            return GameObservation(
                values=None, frame_seq=frame.seq,
                frame_id=frame.frame_id, timestamp=frame.timestamp,
                valid=False, invalid_reason=f"{type(e).__name__}: {e}",
                diagnostics=dict(self._last_diag))

    def note_action(self, decision: ActionDecision,
                    observation: GameObservation) -> None:
        self._steps += 1
        if decision.action == "FIRE":
            self._fires += 1
        elif decision.action == "HOP":
            self._hops += 1
        elif decision.action == "GRENADE":
            self._grenades += 1

    # ------------------------------------------------------------ --
    # actions
    # ------------------------------------------------------------ --
    def legal_actions(self) -> Sequence[str]:
        # v0.3.0 (R67): BACK = the LEFT walk — the legal pad button
        # that turns/faces the player LEFT.  The R67 loop-probe
        # evidence: at the section pin (px 1164) the soldier wave
        # AND the parked truck are BEHIND the player (dx<0) — a
        # forward-only policy stands pinned facing right while the
        # wave kills it from the rear (the v1.0.0-v1.3.0 death
        # shape, 3 product runs identical).
        return ("IDLE", "WALK", "BACK", "FIRE", "HOP", "GRENADE")

    def action_to_buttons(self, action: str) -> frozenset:
        """Legal pad mappings only: RIGHT walk, Y fire (the SQUARE-
        family fire button of the legacy telemetry), B hop (CROSS),
        A grenade (TRIANGLE).  One action = buttons for ONE frame;
        holds/cooldowns are the POLICY's job across decisions."""
        m = {
            "IDLE": frozenset(),
            "WALK": frozenset({"RIGHT"}),
            "BACK": frozenset({"LEFT"}),
            "FIRE": frozenset({"Y"}),
            "HOP": frozenset({"RIGHT", "B"}),
            "GRENADE": frozenset({"A"}),
        }
        if action not in m:
            raise AdapterError(f"unmapped action {action!r}")
        return m[action]

    # ------------------------------------------------------------ --
    # post-advance scoring/terminal
    # ------------------------------------------------------------ --
    def post_advance(self, frame: Frame) -> Dict[str, Any]:
        px = self.px_of()
        score = self._u32(A_SCORE)
        al = self.alive()
        terminal = not al
        passed = px > self._px + 0.5     # a real world-px gain
        self._score = int(score)
        self._max_score = max(self._max_score, int(score))
        self._px = px
        self._max_px = max(self._max_px, px)
        return {"pipe_passed": passed,
                "pipes": int(score),
                "terminal": terminal,
                "death_reason": "game_over" if terminal else None,
                "px": round(px, 1),
                "max_px": round(self._max_px, 1),
                "score": int(score), "alive": bool(al)}

    # ---- misc ----
    @property
    def score(self) -> int:
        return int(self._score)

    @property
    def fires(self) -> int:
        return int(self._fires)

    @property
    def steps(self) -> int:
        return int(self._steps)

    def snapshot(self) -> Dict[str, Any]:
        try:
            d = dict(self._last_diag)
            d["max_px"] = round(self._max_px, 1)
            d["max_score"] = self._max_score
            d["fires"] = self._fires
            d["steps"] = self._steps
            return d
        except Exception:
            return {}

    def episode_stats(self) -> Dict[str, int]:
        return {"pipes": int(self._max_score),
                "px_max": int(round(self._max_px)),
                "actions": int(self._fires + self._hops +
                               self._grenades),
                "decisions": int(self._steps)}
