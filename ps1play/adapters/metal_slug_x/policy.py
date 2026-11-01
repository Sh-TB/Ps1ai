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
    steal the bullet — the R49 player-bullet-victim-locked model).

The movement rule is the proven issue4 semantics: walk RIGHT, hop on
a cadence, stop-and-fire front mortals inside the engage window, the
bounded stall ladder (jump burst -> grenade -> keep walking), never
fire blind through a blocker.
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
POLICY_VERSION = "1.0.0"

ENGAGE_SHORT = 220.0
FIRE_COOLDOWN = 12
HOP_PERIOD = 120
HOP_LEN = 3
STALL_DECISIONS = 120
GRENADE_CD = 90
PROGRESS_PX = 1.0

# state codes that can absorb a bullet or register a payment
MORTAL_CODES = (1, 2, 3, 5, 6)
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
        return ("IDLE", "WALK", "FIRE", "HOP", "GRENADE")

    def reset(self) -> None:
        self._fire_cd = 0
        self._gren_cd = 0
        self._hop_left = 0
        self._since_hop = 0
        self._stall = 0
        self._last_px = None

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
                "corridor_predicate": "r66_corrected"}

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
            if sc == 0 and dx == 0.0:
                continue
            ents.append((dx, sc))

        if not alive:
            self._last_diag = {"rule": "dead", "px": px}
            return "IDLE"

        # ---- stall sensor (world-px progress) ----------------------
        if self._last_px is None or px >= self._last_px + PROGRESS_PX:
            self._stall = 0
        else:
            self._stall += 1
        self._last_px = px

        # ---- engagement (the R66 corridor predicate) ---------------
        target = None
        blocker = None
        cands = sorted((e for e in ents
                        if e[1] in MORTAL_CODES and 8.0 < e[0]
                        <= ENGAGE_SHORT),
                       key=lambda e: e[0])
        if cands:
            t_dx, t_sc = cands[0]
            blocker = next((b for b in ents
                            if b[1] in MORTAL_CODES and b != cands[0]
                            and 0.0 < b[0] < t_dx), None)
            if blocker is None:
                target = (t_dx, t_sc)
        if target is not None and self._fire_cd == 0:
            self._fire_cd = FIRE_COOLDOWN
            self._last_diag = {"rule": "engage",
                               "target_dx": round(target[0], 1),
                               "target_sc": target[1]}
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
            return "HOP"
        self._since_hop += 1
        if self._since_hop >= HOP_PERIOD:
            self._since_hop = 0
            self._hop_left = HOP_LEN - 1
            return "HOP"

        # ---- cooldowns + default walk -------------------------------
        if self._fire_cd > 0:
            self._fire_cd -= 1
        if self._gren_cd > 0:
            self._gren_cd -= 1
        self._last_diag = {"rule": "walk", "stall": self._stall,
                           "n_ent": len(ents)}
        return "WALK"
