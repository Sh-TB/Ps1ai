#!/usr/bin/env python3
"""update_registry_issue5b.py — second honesty pass (post dead-probe
series). All invincibility candidates are now evidence-graded:

  hp_freeze      FAILED (already; 0xCA2FE false positive)
  invuln_blink   VERIFIED -> FAILED (0xEF13F freeze does not gate the
                 village helicopter-bomb kill; the b2 900f freeze test
                 was shorter than the ~2100f baseline -> unsound)
  lives_mirror   NEW entry, FAILED (0xCB225 freeze = mirror/HUD; game
                 over still came, lives2 end frame = TITLE screen)
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

    e = reg.entries.get("invuln_blink")
    if e:
        reg.update_status(
            "invuln_blink", "FAILED",
            evidence={
                "addr": "0xef13f",
                "note": ("issue5_deathprobe d1/d2/d3 + frameprobe f1/f2: "
                         "player died at the village with 0xEF13F frozen "
                         "at 0x20; killer = tall vertical explosion "
                         "(follower-helicopter bomb, f2 f002092.png). "
                         "The b2 900f freeze test was shorter than the "
                         "~2100f baseline death window -> unsound "
                         "verification. Status VERIFIED -> FAILED."),
                "verdict": "REJECTED as invincibility",
            })

    reg.entries["lives_mirror"] = {
        "name": "lives_mirror",
        "effect": ("candidate lives freeze at u8 0xCB225 — REJECTED: "
                   "freezing it did not gate game-over (end frame = "
                   "TITLE screen); the word is a mirror/HUD shadow"),
        "codes": ["<derived: 300CB225 00<high> (this boot family)>"],
        "status": "FAILED",
        "mechanism": "data freeze candidate from 30f-series scan",
        "evidence": [{
            "series": [2, 2, 2, 2, 1, 1, 0, 0],
            "note": ("issue5_lives2_l2: freeze test recorded 3 respawn-"
                     "like score events but the run still fell through "
                     "to the title; verdict was initially recorded as "
                     "TESTED and is corrected here to FAILED"),
            "t": "2026-10-21",
        }],
        "region_applicability": "SLUS-01212 NTSC-U",
        "source_inspected": "2026-10-21",
        "source_url": "derived in-project (issue5_livesprobe2.py)",
    }

    e2 = reg.entries.get("bombs")
    if e2:
        e2.setdefault("observation", "")
        e2["observation"] = (
            "VERIFIED and used as the traversal cheat (freeze at the "
            "live strict-series anchor, 300EDCF4 000A family); the "
            "published instruction patch 800398BE 2400 = sb $v0,0xB6"
            "($a1) NOP — the only structurally-sound published code "
            "(analyze_patch_sites.py: ammo patches a JAL, time/lives "
            "patch lw $sp-loads, invuln codes corrupt JAL/GTE words)")

    reg.save()
    out = {k: v.get("status") for k, v in reg.entries.items()}
    print(json.dumps(out, indent=1))
    problems = reg.validate()
    print("validate:", "OK" if not problems else problems)


if __name__ == "__main__":
    main()
