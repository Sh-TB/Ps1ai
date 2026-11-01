"""ps1play.adapters.metal_slug_x.package_spec — the metal_slug_x.ps1game
builder (R65 Part G5; R66 update).

R66 changes: the game IS a registered runtime game now
(`python3 -m ps1play play metal_slug_x` through the standard product
path, deterministic Mission-1 rules policy), the corridor-gate
starvation is ROOT-CAUSED and fixed (the R66 evidence-corrected
predicate), and the +500 pay-frame capture exists.  The package
maturity moves INPUT_VERIFIED -> GAMEPLAY_VERIFIED (gameplay state —
alive word, score, world px, entities — is policy-driven through the
product path and re-validated by the R66 boots) and stays honestly
BELOW PARTIAL_AUTONOMOUS_PLAYER: every product run still dies at the
armored-truck encounter and Mission 1 is NOT cleared.
"""
from __future__ import annotations

import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

DISC_SHA = ("45cde149878fe945d0219fd0f61ca09856aee66bdcc9119de21c0583"
            "f1d0667d")

README = """# metal_slug_x.ps1game — PS1Play game knowledge package

**Game:** Metal Slug X (SNK, 2001, SLUS-01212, NTSC/U) — the
permanently prioritized PRIMARY gameplay project.

**Maturity:** GAMEPLAY_VERIFIED (R66) — the disc identity, boot,
input causality, real-play telemetry, verified memory knowledge AND
the R66 product-path gameplay (the deterministic Mission-1 rules
policy driving real episodes through `python3 -m ps1play play
metal_slug_x`) are committed.  Mission 1 is NOT completed and the
package claims no autonomous completion.

## What is in this package

| path | role |
|---|---|
| `knowledge/capsule.json` | the provenance-grade RE capsule: VERIFIED/OBSERVED/BLOCKED statuses for every claim, 52 evidence events, artifact references |
| `knowledge/entities.json` | the entity table (0x0CA268, stride 0x14C; HP @+0x8E, spawn @+0xA0) and its damage-entry analysis |
| `knowledge/death_path.json` | the death path analysis (the three death paths incl. mission-timer expiry) |
| `knowledge/mission1_map.json`, `knowledge/mission1_route.json` | the Mission 1 route knowledge |
| `knowledge/truck_blocker.md` | the truck-blocker resolution record |
| `knowledge/r66_findings.json` | the R66 increment: the corridor-gate starvation root cause + fix, the +500 pay-frame capture, the payment ledger, the product-path record |
| `knowledge/disc_pin.json` | disc identity + emulator/core pin |

## What is verified (and what is NOT)

* VERIFIED: the entity table and HP semantics (damage entry
  enemy_800A41D8), the game-over state sensor u32 0x0EE518, the
  wound/heal telemetry families (the magnitude table is now +500 x4
  vs +1000 x7 across R48-R66), survival through the Iron Nokana
  mid-boss arena, three death paths, controller ownership and
  real-play telemetry v3, and (R66) the product-path gameplay loop
  with byte-identical determinism across independent runs.
* R66 NEW (OBSERVED): the corridor-gate starvation ROOT CAUSE — the
  R50/R51 predicate counted non-absorbing, non-paying entities
  (in-flight projectile_air rows and the bullet-TRANSPARENT 0xab94
  wasp) as blockers, and the protocol never advanced the player; the
  corrected predicate (blockers must be able to ABSORB the bullet or
  REGISTER the payment) produced the missing +500 capture at pay-
  frame granularity.  The pay-frame law: the score accumulator pays
  on the internal damage event (~2 frames BEFORE the victim's
  visible 0x5b0c registration); the slot12@0xa0 pulse is the
  registration witness, NOT a magnitude discriminator (its instant
  value is churn phase — one banked +1000 pay frame also shows 257).
* NOT CLAIMED: Mission 1 completion (every product run dies at the
  armored-truck encounter; the pay-frame discriminator needs n>=2
  +500 captures), boss HP control (BLOCKED: slots immune to all
  tested weapons), any autonomous playthrough.
* The game-over sensor earlier interpreted as a camera/progress
  meter (0x0CA2E0) is CONTRADICTED for the progress role — the
  capsule keeps the contradiction guard; do not reuse it as
  progress.

## Legal

This package contains **PS1Play's own reverse-engineering knowledge
only** — no game image, no BIOS, no copyrighted assets.  You provide
your own legally obtained Metal Slug X (SLUS-01212) disc; the disc
identity this knowledge was built against is SHA-256 `{disc_sha}`
(compute it over your .bin and compare before trusting any address
here — a different revision may shift every address).

## How a user uses this knowledge

1. `python3 -m ps1play knowledge validate metal_slug_x.ps1game`
2. `python3 -m ps1play knowledge install metal_slug_x.ps1game`
3. Verify your disc: sha256 over your .bin == `{disc_sha}`.
4. Read `knowledge/capsule.json`: every memory field carries its
   status and provenance; only VERIFIED/OBSERVED facts are usable as
   ground truth (the capsule enforces this programmatically).
5. With the ps1play runtime installed, `python3 -m ps1play play
   metal_slug_x` runs the deterministic Mission-1 rules policy on
   YOUR legal copy (legal pad inputs only, zero RAM writes, no
   training) — and `knowledge/r66_findings.json` tells you exactly
   what the policy knows, what it cannot do yet (the truck), and
   which experiment is next.
"""


def _disc_pin():
    return {
        "game_id": "metal_slug_x",
        "title": "Metal Slug X (USA)",
        "serial": "SLUS-012.12",
        "region": "NTSC/U",
        "disc": {"sha256": DISC_SHA,
                 "note": "the exact disc every committed record was "
                         "made with; other revisions may shift every "
                         "address"},
        "boot": {"core": "beetle PSX (mednafen_psx_libretro.so)",
                 "firmware": "the user's own BIOS (retail title)",
                 "overlay": "ENEMY.BIN @ 0x8009C0E8 (468 Ghidra "
                            "functions); main EXE 3957 functions"},
        "key_structures": {
            "entity_table": "0x800CA268, stride 0x14C, HP @+0x8E, "
                            "spawn @+0xA0 (VERIFIED)",
            "damage_entry": "enemy_800A41D8 (VERIFIED)",
            "game_over_sensor": "u32 0x0EE518 (0xFF play / 0x1 menus+"
                                "GAME OVER, OBSERVED 4/4)",
            "score": "u32 0x0EE318 (VERIFIED; pays on the internal "
                     "damage event, R66 pay-frame law)",
            "player_x": "u32 0x0CA2E0 16.16 (VERIFIED as the player "
                        "world-x; NOT a progress meter — the "
                        "contradiction guard stays)",
            "contradicted": "0x0CA2E0 is NOT a progress meter "
                            "(CONTRADICTED; contradiction guard "
                            "active)"},
        "status": "GAMEPLAY_VERIFIED — registered runtime game "
                  "(play metal_slug_x); Mission 1 open",
    }


def _r66_findings() -> dict:
    """A package-local digest of the R66 increment (no game bytes)."""
    ana = json_load(os.path.join(
        REPO, "data", "games", "SLUS-01212", "truck_evidence", "r66",
        "r66_analysis.json"))
    prod = json_load(os.path.join(
        REPO, "data", "games", "SLUS-01212", "truck_evidence", "r66",
        "r66_product_run.json"))
    return {
        "round": "R66",
        "starvation_root_cause": ana.get("starvation", {}).get(
            "verdict", "see r66_analysis.json"),
        "gate_fix": "the corrected corridor predicate (blockers must "
                    "absorb the bullet or register the payment) — "
                    "TESTED in-game; it produced the +500 capture",
        "magnitude_table": {
            "plus500_n": ana.get("magnitude_table", {}).get(
                "plus500_n"),
            "plus1000_n": ana.get("magnitude_table", {}).get(
                "plus1000_n"),
        },
        "pay_frame_law": ana.get("delay_signature", {}).get("verdict"),
        "discriminator_status": ana.get("discriminator", {}).get(
            "verdict", "PENDING"),
        "product_path": {
            "command": prod.get("command"),
            "determinism": prod.get("determinism"),
            "milestone": prod.get("milestone"),
        },
        "evidence_refs": [
            "data/games/SLUS-01212/truck_evidence/r66/"
            "r66_analysis.json",
            "data/games/SLUS-01212/truck_evidence/r66/"
            "r66_product_run.json",
            "data/games/SLUS-01212/truck_evidence/r66/r66_boot3_s2a.jsonl",
            "data/games/SLUS-01212/truck_evidence/r66/r66_boot4_s2b.jsonl",
        ],
    }


def json_load(path):
    import json
    with open(path) as f:
        return json.load(f)


def build_spec() -> dict:
    def rp(*p):
        return os.path.join(REPO, *p)

    r66_path = rp("scratch", "r66_findings_tmp.json")
    with open(r66_path, "w") as f:
        import json
        json.dump(_r66_findings(), f, indent=1)

    files = [
        (rp("data", "knowledge", "msx", "capsule.json"),
         "knowledge/capsule.json", "re_knowledge"),
        (rp("data", "games", "SLUS-01212", "entities.json"),
         "knowledge/entities.json", "re_knowledge"),
        (rp("data", "games", "SLUS-01212", "death_path.json"),
         "knowledge/death_path.json", "re_knowledge"),
        (rp("data", "games", "SLUS-01212", "mission1_map.json"),
         "knowledge/mission1_map.json", "re_knowledge"),
        (rp("data", "games", "SLUS-01212", "mission1_route.json"),
         "knowledge/mission1_route.json", "re_knowledge"),
        (rp("docs", "truck_blocker_resolution.md"),
         "knowledge/truck_blocker.md", "analysis"),
        (r66_path, "knowledge/r66_findings.json", "re_knowledge"),
        (rp("tests", "test_r66_msx_adapter.py"),
         "tests/test_msx_r66.py", "test"),
        ({"game_id": "metal_slug_x", **_disc_pin()},
         "knowledge/disc_pin.json", "disc_knowledge"),
    ]
    return {
        "game_id": "metal_slug_x",
        "title": "Metal Slug X (SNK, SLUS-01212)",
        "version": "0.2.0",
        "maturity": "GAMEPLAY_VERIFIED",
        "serial": "SLUS-012.12",
        "region": "NTSC/U",
        "revision": "SLUS-01212 (the committed disc)",
        "files": files,
        "readme": README.format(disc_sha=DISC_SHA),
        "runtime": {
            "runtime_version_compat": ["1.0.0"],
            "components": {
                "runtime_adapter": (
                    "ps1play.adapters.metal_slug_x (the repo ships it; "
                    "this package ships the game's OWN knowledge the "
                    "adapter and policy were built from)"),
            },
            "python_packages": ["numpy==2.1.3"],
        },
        "capabilities": {
            "autonomous_play": True,
            "objective": "Mission 1 clear — OPEN (not achieved; every "
                         "product run still dies at the armored-truck "
                         "encounter, px ~1164; the next blockers are "
                         "the truck fight and the n>=2 +500 pay-frame "
                         "discriminator captures)",
            "diagnostics": ["disc identity check",
                            "capsule provenance review",
                            "generic harness compatibility",
                            "product-path gameplay (R66)"],
            "test_command": "python3 -m ps1play test metal_slug_x",
            "play_command": "python3 -m ps1play play metal_slug_x",
        },
        "legal": {
            "assets_included": False,
            "user_must_provide": [
                "your own legally obtained Metal Slug X (SLUS-01212) "
                "disc"],
            "package_contains": "PS1Play's own reverse-engineering "
                                "knowledge and analysis — no game "
                                "image, no BIOS, no copyrighted "
                                "assets",
            "game_license": "commercial (SNK) — knowledge about the "
                            "game is not the game",
        },
    }
