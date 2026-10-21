#!/usr/bin/env python3
"""update_registry_issue5.py — honesty update of cheats.json (Issue #5
addendum Phase 2/6):

  hp_freeze    VERIFIED -> FAILED  (false positive: player died 4x with
               0xCA2FE frozen in issue5_recon_recon1; Metal Slug is a
               one-hit-death game — that word is not the lethal gate)
  invuln_blink NEW -> VERIFIED      (u8 @0xEF13F post-respawn blink
               timer; freeze 0x20 = unhittable, freeze-tested vs live
               enemies, issue5_blink_b2)
  ammo         observation note: default pistol is natively infinite
               (0x2DCD8 reads 0xFF); only special-weapon ammo needs an
               anchor — traversal does not require it.
"""
import json
import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
from ps1play.agent.cheatprof import CheatRegistry  # noqa: E402

PATH = os.path.join(_REPO, "data/games/SLUS-01212/cheats.json")


def main():
    reg = CheatRegistry.load(PATH)
    e = reg.entries.get("hp_freeze")
    if e:
        reg.update_status(
            "hp_freeze", "FAILED",
            evidence={
                "addr": "0xca2fe",
                "code": "800CA2FE 0090",
                "note": ("player died 4x in issue5_recon_recon1 with the "
                         "word frozen at 0x90 (flags 0xFF->1 at chunks "
                         "32/65/103/138); the word sits in the per-life "
                         "0xCA2E0 cluster, not a lethal gate"),
                "verdict": "false positive — SUPERSEDED by invuln_blink",
            })
        e["effect"] = ("SUPERSEDED: was believed to be player HP freeze; "
                       "not the lethal-damage gate (see evidence)")

    reg.entries["invuln_blink"] = {
        "name": "invuln_blink",
        "effect": ("TRUE invincibility: per-frame freeze of the "
                   "post-respawn invulnerability (blink) timer u8; the "
                   "player becomes unhittable — walked into live enemy "
                   "contact for 900 frames with zero deaths while the "
                   "baseline dies deterministically (~c35 village)"),
        "codes": ["<derived per boot: 300EF13F 00<high blink value>",
                  "300EF13F 0020 (this boot family, freeze value 32)"],
        "status": "VERIFIED",
        "mechanism": ("data freeze of the game's own invulnerability "
                      "timer; discovery: 5-frame-cadence sampling at "
                      "mission-start control handover, countdown series "
                      "[32,24,17,10,2,0,...] reproduced across savestate "
                      "reload, then freeze-test vs live enemies"),
        "evidence": [{
            "addr": "0xef13f",
            "dtype": "u8",
            "series": [32, 24, 17, 10, 2, 0, 0],
            "protocol": ("sample -> reload(savestate) -> resample -> "
                         "freeze -> 900-frame enemy-contact walk"),
            "verdict": "INVULN_VERIFIED",
            "t": "2026-10-21 (run issue5_blink_b2)",
            "note": ("address stable across this session's boots "
                     "(0xEDCF4 grenade anchor equally stable); per-boot "
                     "re-derivation is kept as safety"),
        }],
        "region_applicability": "SLUS-01212 NTSC-U, this boot flow",
        "required_infrastructure": ("headless libretro host + GameShark "
                                    "tick; 5f-cadence countdown sampling "
                                    "at mission start"),
        "source_inspected": "2026-10-21",
        "source_url": "derived in-project (issue5_blink2.py)",
    }

    e2 = reg.entries.get("ammo")
    if e2:
        e2["observation"] = (
            "default pistol ammo is natively infinite on this revision "
            "(published cluster reads 0xFF); only special-weapon pickups "
            "have a draining counter — full-map traversal does not "
            "require the ammo patch (bombs + blink suffice)")

    reg.save()
    out = {k: v.get("status") for k, v in reg.entries.items()}
    print(json.dumps(out, indent=1))
    problems = reg.validate()
    print("validate:", "OK" if not problems else problems)


if __name__ == "__main__":
    main()
