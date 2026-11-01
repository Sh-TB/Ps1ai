"""ps1play.adapters.buzzybee.package_spec — the buzzybee.ps1game
builder (R65, Part E4).  The game's own knowledge-package descriptor;
no other game's material is referenced (the isolation rule).
"""
from __future__ import annotations

import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

DISC_SHA = ("042b94bb29907e75b4eadd0699619eb770089bf8880adf31f26bc"
            "c591a1bb093")
EXE_SHA = ("9b0bfc089c33d6116f2e67436254a4ced6e26275a7cac83f5f0dda"
           "95c909a8ba")

README = """# buzzybee.ps1game — PS1Play game knowledge package

**Game:** BuzzyBee (NDR008, **MIT**) — homebrew survival flyer; the
THIRD registered PS1Play runtime game (R65), playing with the R52-B
proven bot_policy8 planner.

**Maturity:** PARTIAL_AUTONOMOUS_PLAYER — real autonomous gameplay is
verified end-to-end through the product path: the score law EXACT
(score = play_frames − 96), natural game overs, and the full
game-over -> title -> restart cycle; survival is endless, so no
higher level applies.

## What is in this package

| path | role |
|---|---|
| `plugin/adapter.py` | the runtime GameAdapter: RAM-read perception (all anchors VERIFIED in the capsule), the 2-frame flap press pipeline, gs=5 recovery |
| `plugin/policy.py` | bot_policy8 — the tiered-margin guarantee planner (R45-B → R48-B → R52-B), ported verbatim behind the Policy contract |
| `knowledge/capsule.json` | the provenance-grade knowledge capsule: 14 VERIFIED memory fields with evidence links |
| `knowledge/acceptance_r65.json` | the R65 acceptance record (3 episodes, the score law checks) |
| `knowledge/gs5_probe_r65.json` | the R65 game-over state characterization (resolves the capsule's score-cap UNKNOWN) |
| `knowledge/disc_pin.json` | disc identity + boot/state knowledge |
| `tools/` | the EXACT recipes to build YOUR OWN playable disc from the upstream EXE + your own retail disc's license sectors |
| `tests/` | the game's contract tests + real-emulator integration tests |

## What this package knows (the hard-won parts)

* The bee physics: tap impulse −3072 (1/1024 px/frame), gravity
  +256/frame², clamp y ∈ [18, 172]; the slam guard (never tap at
  vy ≤ −3000).
* The wasp: 1.5 px/f approach, y-band [wy−13, wy+43], y-bounce off
  [2, 142]; the tiered danger window and the committed pre-danger
  hold the planner uses to survive it.
* The pad truth: a flap press must be held EXACTLY 2 frames (then 1
  idle frame) or the bee never lifts (measured: 389 one-frame
  presses left the bee pinned at the floor).
* gameState: 0 title, 1 playing, 5 GAME OVER (hp depleted; auto-
  returns to the title after ~380 frames), 99 select.
* The score law: score = play_frames − offset (R52-B: −99 via the
  checkpoint protocol; the runtime path: −96) — verified EXACT.

## Legal

This package contains **PS1Play's own knowledge only**.  BuzzyBee is
free homebrew (MIT); you fetch the upstream `BuzzyBee.ps-exe`
(SHA-256 `{exe_sha}`) and build your own LOCAL disc image with the
included tools — the recipe copies the 16 license sectors from YOUR
OWN retail PS1 disc (any one you own); the wrapped image stays on
your machine and is never distributed.  The runtime verifies the
wrapped image's SHA-256 (`{disc_sha}`) before playing.

## Quick start (inside a PS1Play runtime checkout)

```bash
python3 -m ps1play knowledge validate buzzybee.ps1game
python3 -m ps1play knowledge install buzzybee.ps1game
python3 tools/build_wrapped_disc.py       # your own image (local)
python3 -m ps1play test buzzybee
python3 -m ps1play play buzzybee --record
```

## Verified performance (R65 acceptance)

3 episodes through `python3 -m ps1play play buzzybee`: ep1 alive at
the 6000-frame budget (score 5904), ep2 continues the run and dies a
natural game over (7537), ep3 restarts from the title and dies
naturally again (2808).  Every score check matches the law exactly.
The R52-B dominance record: 9 planner passes across caps 1800→2400
with zero hits in the treated arms.

## Known limitations

* Perception is RAM-read (read-only); there is no visual model for
  BuzzyBee and none is claimed.
* The wrapped-disc recipe is Linux/x86-64 (beetle + OpenBIOS); the
  NTSC patch (2 disclosed game-side instructions) is required on
  this backend — PAL renders black.
* The planner's guarantee margin was validated on the tested caps;
  longer runs hit deterministic hit-waves (documented in R52-B).
"""


def _disc_pin():
    return {
        "game_id": "buzzybee",
        "title": "BuzzyBee",
        "source": "github.com/NDR008/BuzzyBee (MIT, in-header)",
        "exe": {"name": "BuzzyBee.ps-exe", "bytes": 299008,
                "sha256": EXE_SHA, "load": "PS-EXE wrap -> MODE2/2352 "
                "disc (scripts/iso9660_min.py recipe in tools/)"},
        "disc": {"image": "buzzybee_ntsc_lic.bin", "bytes": 11334288,
                 "sha256": DISC_SHA,
                 "note": "upstream EXE + the disclosed 2-instruction "
                         "NTSC patch (SCREEN_HEIGHT 256->240 "
                         "@0x80011C24, SetVideoMode 1->0 @0x80011C44) "
                         "+ the 16 license sectors from YOUR OWN "
                         "retail disc"},
        "boot": {"firmware": "OpenBIOS (third_party/openbios)",
                 "core": "beetle PSX (mednafen_psx_libretro.so)",
                 "ready_state": "gameState @0x80058830 == 1 (PLAYING; "
                                "0=title, 5=game over, 99=select)"},
        "observation": {
            "vector": "15 float32: by, bvy, ex, ey, evy, flower[0..2] "
                      "x/y, score, gs, hp, best",
            "perception": "RAM-read (read-only snapshot), all anchors "
                          "VERIFIED (see knowledge/capsule.json)"},
        "actions": {"FLAP": "B (Cross) — the proven 2-frame hold + 1 "
                            "idle frame (pipelined by the adapter)",
                    "HOVER": "no input"},
        "terminal": "gameState 5 (hp depleted game over; auto-returns "
                    "to title ~380f later)",
        "progress": "score (+1 per play frame — the verified law)",
    }


def build_spec() -> dict:
    def rp(*p):
        return os.path.join(REPO, *p)

    files = [
        (rp("ps1play", "adapters", "buzzybee", "adapter.py"),
         "plugin/adapter.py", "plugin_source"),
        (rp("ps1play", "adapters", "buzzybee", "policy.py"),
         "plugin/policy.py", "policy_source"),
        (rp("ps1play", "adapters", "buzzybee", "__init__.py"),
         "plugin/__init__.py", "plugin_source"),
        (rp("data", "knowledge", "buzzybee", "capsule.json"),
         "knowledge/capsule.json", "re_knowledge"),
        (rp("data", "r65", "r65_buzzybee_acceptance.json"),
         "knowledge/acceptance_r65.json", "evidence"),
        (rp("data", "r65", "r65_buzzybee_gs5.json"),
         "knowledge/gs5_probe_r65.json", "evidence"),
        (rp("scripts", "r30t0_buzzybee_asset.py"),
         "tools/build_wrapped_disc.py", "disc_build_tool"),
        (rp("scripts", "r23t2_ntsc_patch_and_wrap.py"),
         "tools/ntsc_patch_and_wrap.py", "disc_build_tool"),
        (rp("scripts", "iso9660_min.py"),
         "tools/iso9660_min.py", "disc_build_tool"),
        (rp("tests", "test_r65_buzzybee.py"),
         "tests/test_r65_buzzybee.py", "test"),
        (rp("tests", "test_r65_integration.py"),
         "tests/test_r65_integration.py", "test"),
        ({"game_id": "buzzybee", **_disc_pin()},
         "knowledge/disc_pin.json", "disc_knowledge"),
    ]
    return {
        "game_id": "buzzybee",
        "title": "BuzzyBee (NDR008, MIT)",
        "version": "1.0.0",
        "maturity": "PARTIAL_AUTONOMOUS_PLAYER",
        "serial": "homebrew (PS-EXE wrap)",
        "region": "NTSC (patched)",
        "revision": "v1.0 HEAD (author v1.1 image reference-only)",
        "files": files,
        "readme": README.format(exe_sha=EXE_SHA, disc_sha=DISC_SHA),
        "runtime": {
            "runtime_version_compat": ["1.0.0"],
            "components": {
                "adapter_buzzybee": "1.0.0",
                "policy": "buzzybee_bot_policy8 1.0.0 (R52-B port)",
            },
            "python_packages": ["numpy==2.1.3", "pillow>=10.0.0"],
        },
        "capabilities": {
            "autonomous_play": True,
            "objective": "endless survival (score = play frames); no "
                         "completion state exists",
            "diagnostics": ["contract tests", "real-emulator "
                            "integration tests", "disc hash pin",
                            "score-law check (exact)"],
            "test_command": "python3 -m ps1play test buzzybee",
            "play_command": "python3 -m ps1play play buzzybee",
        },
        "legal": {
            "assets_included": False,
            "user_must_provide": [
                "the upstream BuzzyBee.ps-exe (free homebrew, MIT) "
                "+ one of your own retail PS1 discs for the 16 "
                "license sectors"],
            "package_contains": "PS1Play's own adapter, policy, "
                                "provenance capsule, disc-build "
                                "recipes, records and tests — no game "
                                "image, no BIOS, no license data",
            "game_license": "MIT (c) 2021 NDR008",
        },
    }
