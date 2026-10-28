#!/usr/bin/env python3
"""r25_evidence.py — Round 25 close-out (orchestrator-only):
manifest doukutsupsx -> GAMEPLAY_CONFIRMED + round25_addendum."""
import json
import os

REPO = "/home/z/my-project/ps1ai"
MANIFEST = os.path.join(REPO, "data", "homebrew", "manifest.json")

m = json.load(open(MANIFEST))
for g in m["accepted"]:
    if g["id"] == "doukutsupsx":
        g["status"] = (
            "ACCEPTED+TESTED 2026-10-28 (r24+r25): GAMEPLAY_CONFIRMED "
            "through the shared beetle core + OpenBIOS with the local "
            "image (sha256 bf15559e...7554). r24 (3 boots): BOOTED_TITLE "
            "+ INPUT_RESPONSIVE (menu cursor PNG-verified Load/New) + "
            "STATE_CHANGE (New Game -> intro dialog). r25 (5 boots, "
            "cumulative 8): the intro chain needed ~80 dialog-advance "
            "CROSS pulses (hammer approach after 3 disclosed detector "
            "failures); boot 7 PNG'd the Start Point room (Quote + Lv0/"
            "3-hearts HUD @pulse80) and its end probes knocked Quote "
            "into the water pool engaging the AIR 70 drowning counter; "
            "boot 8 clean direction protocol on 4 revert-class words: "
            "0xbd072/0xbd07f deltas [-16,+16,-16,+16] (x-position/camera "
            "class, direction-consistent x2), legs vis 0.47-0.53 vs "
            "ctrl<=0.157. GIF: docs/evidence_gifs/r25_doukutsu_movement."
            "gif (continuous capture). Detector lessons disclosed: "
            "typewriter dialog noise passes naive idle-subtraction AND "
            "two-round agreement; only the narrow revert-class set is "
            "input-driven.")
        g["boots_used_r24_r25"] = 8
m["round25_addendum"] = {
    "date": "2026-10-28",
    "headline": "Round 25: Cave Story reaches GAMEPLAY_CONFIRMED - the "
                "first PSX port rung above r13's BOOTED_TITLE; ~80-pulse "
                "intro chain measured, Start Point room entered, player "
                "movement anchored direction-consistently",
    "doukutsupsx": {
        "verdict": "GAMEPLAY_CONFIRMED (boots 4-8, cumulative 8)",
        "intro_chain": "menu -> New -> ~80 CROSS-advanced dialogs "
                       "(transmission -> island scenes -> terminal "
                       "'Connecting to network' -> ...) -> Start Point",
        "boot7": "Start Point PNG (Quote + HUD) @pulse80; movement "
                 "probes knocked Quote into the water: AIR 70 drowning "
                 "counter engaged (game systems react)",
        "boot8": "clean direction protocol: 0xbd072 [-16,+16,-16,+16], "
                 "0xbd07f identical, legs vd 0.47-0.53 vs ctrl<=0.157",
        "detector_lessons": "typewriter-reveal noise passes idle "
                            "subtraction and two-round agreement; "
                            "revert-class + direction protocol is the "
                            "reliable discriminator",
        "honest": "no WON claim, no weapon/level anchors yet; air/water "
                  "system observed but not RAM-localized",
    },
}
json.dump(m, open(MANIFEST, "w"), indent=1)
print("manifest updated: doukutsupsx GAMEPLAY_CONFIRMED + round25_addendum")
