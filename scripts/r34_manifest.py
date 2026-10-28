#!/usr/bin/env python3
"""r34_manifest.py — append the round34 addendum to the homebrew
manifest (data/homebrew/manifest.json)."""
import json

P = "/home/z/my-project/ps1ai/data/homebrew/manifest.json"
m = json.load(open(P))
assert "round34_addendum" not in m, "already appended"

m["round34_addendum"] = {
    "date": "2026-10-28",
    "headline": (
        "Round 34: the instrumented-beetle lever executed — the "
        "r30-r32 'environment-level input regression' is REFUTED as "
        "an observation artifact (r30t2/t5/t6 read the 0x8005xxxx "
        "game words RAW against the 2MiB physical ram[] mapping; "
        "r23's helpers subtracted the KUSEG base; r30t6's padbuf "
        "poke was a no-op for the same reason). The class split "
        "loses its buzzybee leg; instrumented bus trace (core md5 "
        "f2383b2f, grep [PSXBUS]) shows the kernel ISR served real "
        "button bytes on the pad bus for buzzybee AND tetrade on "
        "the same binary. BuzzyBee deep systems COMPLETE in one "
        "boot (ALL_PHASES_OK): drain -3/frame and score +1/frame "
        "exact, enemy -1500 edge observed, death -> gs5 with "
        "bestScore==score==1000 (non-degenerate 0->1000 rise), "
        "auto-return 6.4s deterministic (f2392 twice), score reset "
        "+ bestScore retention on run 2, game-over screen PNG "
        "'YOUR LAST ATTEMPT: 1000 / YOUR BEST SCORE: 1000', GIF "
        "mirrored. Ladder: buzzybee stays GAMEPLAY_CONFIRMED with "
        "the systems closure on top; mspSX already PLAYING "
        "(accepted #9). Suite 565+1xfail untouched; 5 disclosed "
        "boots (caps 2 -> amend 3 -> 4 -> 5)."),
    "correction": {
        "what": "r30 input-regression + r30-r32 class split "
                "(minecraft+tetrade alive, doukutsu+buzzybee dead) "
                "were observation artifacts of raw 0x8005xxxx reads "
                "against physical ram[] (empty slice -> 0)",
        "evidence": [
            "r23 scripts: core.ram[va - 0x80000000:...] (correct)",
            "r30t2/t5/t6: core.ram[va:va+4] with va=0x8005xxxx (void)",
            "r34t1 bus trace: L2bus nz=0800 served 50x for buzzybee "
            "START on the instrumented core; tetrade CROSS nz=0040 "
            "identical path",
            "r34t2 corrected reads: input words live (40/40 hold "
            "frames pad=8), gs 0->1, score 19->65->131, kernel "
            "padbuf button bytes land",
        ],
        "scope": ("buzzybee leg of the class split void; doukutsu "
                  "r30t8/r32 'dead' evidence was vision-based and "
                  "stands as observed, but the class theory itself "
                  "is unproven; r31 CCP(1) retraction unaffected "
                  "(already killed by its own control in r32)"),
    },
    "r34_buzzybee_deep": {
        "phases": "ALL_PHASES_OK (r34t3 boot 4)",
        "details": (
            "source-matched trajectory: health 5999, drain -3/frame "
            "exact (dh=-90/30f), enemy contact -1500 edge (dh=-1590 "
            "= drain+contact), score +1/frame exact (ds=+30/30f); "
            "death -> gs5, bestScore = max() verified 0->1000 rise "
            "and equality retention; auto-return 381f (~6.4s > 6s "
            "spec) with score reset + best retained + health "
            "re-init 5999; run 2 with 30 flap bursts; score cap "
            "1000 observed twice (mechanism not disassembled, "
            "honest residual); flower +1000 never observed live"),
        "visual": (
            "death screen 'YOUR LAST ATTEMPT: 1000 / YOUR BEST "
            "SCORE: 1000' PNG (scratch/r34/shots/"
            "death_screen_f02101.png); evidence GIF docs/"
            "evidence_gifs/r34_buzzybee_deep_systems.gif; "
            "auto-return frame f2392 identical across r34t3/r34t4 "
            "(deterministic)"),
    },
    "instrumented_core": {
        "binary": "mednafen_psx_libretro_psxbus_r34.so",
        "md5": "f2383b2f6ea08c0509b08540963e49b2",
        "canonical_md5_untouched": "447b7ebf9e0805d0ebb222256ed62958",
        "rollback_retained": "79f8fac0",
        "edits": "grep [PSXBUS]: input.c L0fe (frontend callback "
                 "view); frontio.c L1dev (gamepad device buttons, "
                 "on change) + L2bus (0x42 bus responses, nonzero "
                 "logged) + dtr counter + 120f heartbeat counters",
    },
    "boots": "5 disclosed (r34t1 x2, r34t2, r34t3, r34t4); caps "
             "disclosed pre-run: 2 -> amendment 3 -> 4 -> 5",
    "scripts": [
        "scripts/r34t1_bus_probe.py",
        "scripts/r34t2_buzzybee_reprieve.py",
        "scripts/r34t3_buzzybee_deep_complete.py",
        "scripts/r34t4_buzzybee_deathshot.py",
        "scripts/r34_buzzybee_gif.py",
    ],
    "no_game_bytes": True,
    "suite": "565 passed + 1 xfailed (untouched)",
}

json.dump(m, open(P, "w"), indent=1, ensure_ascii=False)
print("round34_addendum appended;", len(m), "top-level keys")
