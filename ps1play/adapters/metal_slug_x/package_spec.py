"""ps1play.adapters.metal_slug_x.package_spec — the metal_slug_x.ps1game
builder (R65, Part G5).

Metal Slug X is NOT a registered runtime game yet: no runtime adapter
exists and none is claimed.  This package ships the game's REVERSE-
ENGINEERING knowledge (the provenance-grade capsule, the verified
memory structures, the mission map/route/death-path analysis and the
disc identity) so a user with a compatible legal copy can install the
knowledge, verify their disc against the pinned identity and review
every verified fact WITHOUT repeating the original analysis.  The
maturity level is honest: INPUT_VERIFIED (boot + input causality are
proven; no autonomous gameplay loop ships in this package).
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

**Maturity:** INPUT_VERIFIED — the disc identity, boot, input
causality, real-play telemetry and extensive verified memory
knowledge are committed; **no autonomous gameplay loop ships in this
package** (Mission 1 is NOT completed; see the honest status below).

## What is in this package

| path | role |
|---|---|
| `knowledge/capsule.json` | the provenance-grade RE capsule: VERIFIED/OBSERVED/BLOCKED statuses for every claim, 52 evidence events, artifact references |
| `knowledge/entities.json` | the entity table (0x800CA268, stride 0x14C; HP @+0x8E, spawn @+0xA0) and its damage-entry analysis |
| `knowledge/death_path.json` | the death path analysis (the three death paths incl. mission-timer expiry) |
| `knowledge/mission1_map.json`, `knowledge/mission1_route.json` | the Mission 1 route knowledge |
| `knowledge/truck_blocker.md` | the truck-blocker resolution record |
| `knowledge/disc_pin.json` | disc identity + emulator/core pin |

## What is verified (and what is NOT)

* VERIFIED: the entity table and HP semantics (damage entry
  enemy_800A41D8), the game-over state sensor u32 0x0EE518, the
  wound/heal telemetry families (+500 ×3 / +1000 ×7 magnitude
  records), the corridor-gate invulnerability predicate (n=4),
  survival through the Iron Nokana mid-boss arena, three death
  paths, controller ownership and real-play telemetry v3.
* NOT CLAIMED: Mission 1 completion (the corridor-gate starvation,
  the +500 pay-frame capture and the accumulator discriminator
  remain OPEN experiments), boss HP control (BLOCKED: slots immune
  to all tested weapons), any autonomous playthrough.
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
5. The runtime's generic harness (boot / observe / act / checkpoint /
   replay) works with any disc — the knowledge tells you WHAT the
   addresses mean, not how to write to them (the zero-writes rule
   stands for legitimate gameplay).
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
            "contradicted": "0x0CA2E0 is NOT a progress meter "
                            "(CONTRADICTED; contradiction guard "
                            "active)"},
        "status": "INPUT_VERIFIED — no runtime adapter, no autonomous "
                  "play; Mission 1 open",
    }


def build_spec() -> dict:
    def rp(*p):
        return os.path.join(REPO, *p)

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
        ({"game_id": "metal_slug_x", **_disc_pin()},
         "knowledge/disc_pin.json", "disc_knowledge"),
    ]
    return {
        "game_id": "metal_slug_x",
        "title": "Metal Slug X (SNK, SLUS-01212)",
        "version": "0.1.0",
        "maturity": "INPUT_VERIFIED",
        "serial": "SLUS-012.12",
        "region": "NTSC/U",
        "revision": "SLUS-01212 (the committed disc)",
        "files": files,
        "readme": README.format(disc_sha=DISC_SHA),
        "runtime": {
            "runtime_version_compat": ["1.0.0"],
            "components": {
                "runtime_adapter": "NONE (diagnostic knowledge "
                                   "package only)",
            },
            "python_packages": ["numpy==2.1.3"],
        },
        "capabilities": {
            "autonomous_play": False,
            "objective": "Mission 1 clear — OPEN (not achieved; the "
                         "first unresolved blocker is the corridor-"
                         "gate starvation / +500 pay-frame capture)",
            "diagnostics": ["disc identity check",
                            "capsule provenance review",
                            "generic harness compatibility"],
            "test_command": None,
            "play_command": None,
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
