#!/usr/bin/env python3
"""r24_evidence.py — Round 24 evidence assembly (orchestrator-only).

1. Evidence GIF from the boot-3 captured PNG sequence (menu -> DOWN ->
   UP -> New Game -> intro transmission). Disclosed: assembled from the
   run's captured frames, not a continuous 1:1 capture (R25 will do a
   continuous capture during the gameplay boot).
2. Manifest update: doukutsupsx status advance + round24_addendum.
   Orchestrator-only write (single writer; no concurrency).
"""
import json
import os

REPO = "/home/z/my-project/ps1ai"
SHOTS = os.path.join(REPO, "scratch", "r24", "doukutsu", "shots")
GIF_DIR = os.path.join(REPO, "docs", "evidence_gifs")
MANIFEST = os.path.join(REPO, "data", "homebrew", "manifest.json")

SEQ = [
    ("menu_confirmed_f02614.png", 55),
    ("menu_down_f02804.png", 55),
    ("menu_up_f02844.png", 55),
    ("pre_new_f02916.png", 40),
    ("post_new_f03040.png", 40),
    ("new_watch_2_f03220.png", 45),
    ("new_watch_5_f03400.png", 45),
    ("new_final_f03640.png", 90),
]


def build_gif():
    from PIL import Image
    frames = []
    for name, ms in SEQ:
        p = os.path.join(SHOTS, name)
        im = Image.open(p).convert("P", palette=Image.ADAPTIVE, colors=64)
        frames.append((im, ms))
    os.makedirs(GIF_DIR, exist_ok=True)
    out = os.path.join(GIF_DIR, "r24_doukutsu_menu_newgame.gif")
    frames[0][0].save(out, save_all=True, append_images=[f for f, _ in frames[1:]],
                      duration=[m for _, m in frames], loop=0, optimize=True)
    print("gif:", out, os.path.getsize(out), "bytes")


def update_manifest():
    m = json.load(open(MANIFEST))
    for g in m["accepted"]:
        if g["id"] == "doukutsupsx":
            g["status"] = (
                "ACCEPTED+TESTED 2026-10-28 (r24): BOOTED_TITLE + "
                "INPUT_RESPONSIVE + STATE_CHANGE_CONFIRMED through the "
                "shared beetle core + OpenBIOS with the local image "
                "(rebuilt r24t0, sha256 bf15559e...7554 byte-identical to "
                "r13; the release carries its own US license block). "
                "3 disclosed boots: boot1 settle-heuristic bug (FAILED, "
                "counted), boot2 bright-phase misread (intro cutscene, "
                "0x9098 cluster retracted as menu anchor -> it is the "
                "kernel pad driver prev/cur state; cutscene->menu state "
                "change via CROSS skip PNG'd), boot3 full pass: menu gate "
                "(near-static, mean 34.81, ctrl<=0.15), menu cursor "
                "DOWN->Load / UP->New (PNG-verified) with RAM set-algebra "
                "55 reverted / 51 retouch, CROSS on New -> 'From somewhere, "
                "a transmission...' intro dialog (ram_flip 107,413, "
                "PNG'd). Honest note: r13's 'title menu @f1740' was in "
                "retrospect the same intro cutscene; r24 corrects the "
                "record with PNGs. GIF: docs/evidence_gifs/"
                "r24_doukutsu_menu_newgame.gif (assembled from captured "
                "frames). Next rung (r25): in-game movement.")
            g["boots_used_r24"] = 3
    m["round24_addendum"] = {
        "date": "2026-10-28",
        "headline": "Round 24 train 1: Cave Story (doukutsupsx) breaks its "
                    "r13 ceiling - BOOTED_TITLE + INPUT_RESPONSIVE + "
                    "STATE_CHANGE_CONFIRMED with PNG-verified menu cursor "
                    "and New Game -> intro dialog",
        "process": {
            "rollback": "4th filesystem rollback repaired from origin "
                        "(08e8688); capstone reinstalled; suite 565+1xfail",
            "user_directive": "next 10 trains = complete previously "
                              "accepted games; new-game intake struggles "
                              "shelved (MSX stage-loader + BKBS parked)",
            "boots": "3 for doukutsu, every amendment and misread "
                     "disclosed in boots_used.json",
        },
        "doukutsupsx": {
            "verdict": "STATE_CHANGE_CONFIRMED (menu cursor + New Game "
                       "-> intro)",
            "boot1": "settle heuristic bug: bright shell frame @f60 read "
                     "as title; probes hit the intro; FAILED recorded",
            "boot2": "bright phase @f1860 = intro cutscene (PNG), NOT the "
                     "title menu; CROSS skip -> real menu (PNG f2760); "
                     "0x9098 RAM cluster retracted (kernel pad prev/cur "
                     "state, not a menu cursor)",
            "boot3": "menu gate (static, mean 34.81) -> DOWN/UP cursor "
                     "PNG-verified (Load/New) + 55/51 set-algebra -> New "
                     "Game -> 'From somewhere, a transmission...' "
                     "(ram_flip 107,413)",
            "correction": "r13's 'title @f1740' was the same cutscene "
                          "misread; corrected with PNG evidence",
        },
    }
    json.dump(m, open(MANIFEST, "w"), indent=1)
    print("manifest updated:", len(m["accepted"]), "accepted")


if __name__ == "__main__":
    build_gif()
    update_manifest()
