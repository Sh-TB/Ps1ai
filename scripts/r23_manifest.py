#!/usr/bin/env python3
"""r23_manifest.py — ORCHESTRATOR-ONLY manifest update for Round 23.

Adds:
  1. accepted[] entry: buzzybee (game #10) with FULL patch + boot history
     disclosure (boots 1-3 black-screen diagnosis, boots 4-5 the decisive
     2-instruction NTSC patch).
  2. round23_addendum: MSPSX RUNNING, BuzzyBee GAMEPLAY_CONFIRMED,
     the PAL-display backend finding, honest process notes.

Idempotent: refuses to add duplicates.
"""
import json
import os

P = "/home/z/my-project/ps1ai/data/homebrew/manifest.json"
d = json.load(open(P))

if not any(g["id"] == "buzzybee" for g in d["accepted"]):
    d["accepted"].append({
        "id": "buzzybee",
        "plugin": "GenericPlugin (dedicated plugin pending)",
        "source": "https://github.com/NDR008/BuzzyBee",
        "license": "MIT (c) 2021 NDR008 — file-header license in main.c "
                   "(no standalone LICENSE file; flagged)",
        "revision": "v1.0 HEAD + author v1.1 release image",
        "artifacts": [
            {"name": "BuzzyBee.ps-exe",
             "url": "https://github.com/NDR008/BuzzyBee/raw/master/"
                    "BuzzyBee.ps-exe",
             "bytes": 299008,
             "sha256": "9b0bfc089c33d6116f2e67436254a4ced6e26275a7cac83f5f0d"
                       "da95c909a8ba"},
            {"name": "buzzy.bin (author v1.1 scene-mirror image, "
                     "reference-only)",
             "url": "https://psx.arthus.net/homebrew/BuzzyBee_v1.1_image/"
                    "buzzy.bin",
             "bytes": 38692752,
             "sha256": "d5d7a62937c0e4a7cfe22b5eb73d2fbc869927b8744dfe1f7301"
                       "f839f7acc32d"}
        ],
        "boot_exe": "BUZZYBEE.EXE",
        "exe_t_addr": "0x80010000",
        "status": "ACCEPTED+TESTED 2026-10-28 (r23): GAMEPLAY_CONFIRMED "
                  "through the shared beetle core + OpenBIOS with a "
                  "DISCLOSED 2-instruction game-side NTSC patch "
                  "(SCREEN_HEIGHT 256->240 @0x80011C24, SetVideoMode "
                  "1->0 @0x80011C44; the game compiles setScreenMode into "
                  "PAL-only code). Anchors from the upstream map, "
                  "cross-validated live: gameState 0x80058830 (0->1 on "
                  "START, 1->99 on SELECT, back on resume), score "
                  "0x8005883C climbing +1/frame during play, bee "
                  "moves/vis-diff 122.4 (START scene) and 20.6 (flap). "
                  "PAL ROOT CAUSE (honest): boots 1-3 rendered BLACK "
                  "while the input state machine ran (gameState "
                  "transitions anchored in boot 3) — the PAL display "
                  "path (SetVideoMode(1) + SCREEN_HEIGHT=256) is broken "
                  "on beetle+OpenBIOS for this libgs game; NTSC-forced "
                  "renders perfectly. First PAL-forcing game in the "
                  "program. Boot history fully logged in "
                  "scratch-local boots_used.json (5 boots, every cap "
                  "amendment disclosed). Unpatched-EXE intake on "
                  "beetle = INPUT_RESPONSIVE-equivalent with black "
                  "display (not claimed as a ladder rung)."
    })
    print("accepted: +buzzybee")

if "round23_addendum" not in d:
    d["round23_addendum"] = {
        "date": "2026-10-28",
        "headline": "Round 23: MSPSX closes RUNNING (the r22 rung: "
                    "ps1play B=PSX CROSS held 40f > 33f SPI poll cadence "
                    "-> reveal 0->1 at cursor (1,1), layout B_y192_x12 "
                    "confirmed, no mine); BuzzyBee = game #10 "
                    "GAMEPLAY_CONFIRMED after the PAL black-screen "
                    "investigation (4 boots of honest diagnosis + the "
                    "decisive disclosed 2-instruction NTSC patch); "
                    "backend finding: PAL-forcing libgs games render "
                    "black on beetle+OpenBIOS while logic/input run",
        "mspsx": {
            "verdict": "RUNNING (1/1 boot)",
            "reveal": "button B (PSX CROSS on the beetle map) held 40f "
                      "-> revealed_total 0->1, board byte flip @0xCD, "
                      "cursor cell (1,1) revealed under layout "
                      "B_y192_x12 (off 0xCC: mine 0, neighbors 3), "
                      "lost=0, control_disable=0",
            "fix": "r22's two disclosed causes both fixed: correct "
                   "button (B, not X=Triangle) + hold 40f > 33f poll "
                   "cadence",
            "image": "mspsx_lic.bin rebuilt from the v0.1 release, "
                     "sha256 re-verified d35a189b...a4c5fa bit-identical"
        },
        "buzzybee": {
            "verdict": "GAMEPLAY_CONFIRMED (game #10)",
            "boots": "5 (1-3 diagnosis: repo-EXE image without its "
                     "CDDA track + author v1.1 image -> EXE loaded "
                     "(strings @0x8001FD10), alive, input state machine "
                     "anchored, display BLACK; 4-5: decisive NTSC "
                     "patch)",
            "patch": "2 instructions, byte-verified in-disc, disclosed "
                     "in manifest + docs + report: SCREEN_HEIGHT "
                     "256->240, SetVideoMode(1)->(0)",
            "root_cause": "PAL display path broken on beetle+OpenBIOS "
                          "for this game (384x240 frames captured "
                          "black); unpatched logic/input fine",
            "cdda": "repo-EXE image initially lacked audio track 2 "
                    "(main.c:52 tracks={2,0}; DsPlay(2,tracks,0)) — "
                    "added 60s silence track in the NTSC build; v1.1 "
                    "author image carries the real track"
        },
        "process": {
            "boot_caps": "every amendment (2->3, 3->4, 4->5) disclosed "
                         "in-script and logged BEFORE the run; boot 4 "
                         "script crash after 400 real frames counted "
                         "honestly",
            "indexing_bug": "r23t2 boot-2 forensics: host ram[] is "
                            "PHYSICAL (0x10000 == 0x80010000 KUSEG); "
                            "the 0x80010000 slice was out-of-bounds "
                            "(empty) — corrected, evidence re-derived",
            "asset_rollback": "3rd filesystem rollback wiped scratch/; "
                              "MSPSX + BuzzyBee artifacts re-fetched "
                              "and SHA-256 re-verified against r21/r22 "
                              "scout hashes (bit-identical)"
        }
    }
    print("+round23_addendum")

json.dump(d, open(P, "w"), indent=1)
print("manifest written,", len(d["accepted"]), "accepted,",
      list(k for k in d if k.startswith("round")), "addenda")
