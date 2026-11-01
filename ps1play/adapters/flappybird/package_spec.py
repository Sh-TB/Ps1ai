"""ps1play.adapters.flappybird.package_spec — the flappybird.ps1game
builder (R65, Part B/C3).

The game's OWN knowledge-package descriptor: everything a user needs
to install, test and play FlappyBirdPSX with their own legal copy,
WITHOUT repeating the reverse engineering.  No other game's material
is referenced here (the isolation rule).
"""
from __future__ import annotations

import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
DEP = os.path.join(REPO, "deployment", "flappybird_policy")

DISC_SHA = ("b45871d32c7910784b26128c3f4ed48d181e31dfd693f4e5efa"
            "187cf2296f0ed")

README = """# flappybird.ps1game — PS1Play game knowledge package

**Game:** FlappyBirdPSX (IcePanorama, **Unlicense**) — the R61 frozen
champion plays it autonomously through the PS1Play runtime.

**Maturity:** PARTIAL_AUTONOMOUS_PLAYER — real autonomous gameplay is
verified end-to-end (87-pipe records, deterministic reproduction,
30-seed pre-registered evaluation); FlappyBird has no completion
state, so no higher level applies.

## What is in this package

| path | role |
|---|---|
| `plugin/adapter.py` | the runtime GameAdapter (perception wiring, action mapping, terminal detection) |
| `policy/flappybird_policy/` | the INDEPENDENT frozen policy package: the ONNX model, its authority manifest, loader, docs (the exact R61 champion, sha-pinned) |
| `knowledge/perception_visual_only.py` | the game-specific perception module (BirdObserverV7 + GapTrackerV7 + the 10-feature vector) |
| `knowledge/disc_pin.json` | disc identity + boot/terminal knowledge |
| `knowledge/records_*.json` | the historical + fresh performance records |
| `tests/` | the game's contract tests (run them from the PS1Play runtime checkout) |

## Legal

This package contains **PS1Play's own knowledge only** — no game
image, no BIOS, no copyrighted assets. You provide your own legally
obtained copy of FlappyBirdPSX (free homebrew,
github.com/IcePanorama/FlappyBirdPSX v0.1.0); the runtime verifies
its SHA-256 (`{disc_sha}`) before playing.

## Quick start (inside a PS1Play runtime checkout)

```bash
python3 -m ps1play knowledge validate flappybird.ps1game
python3 -m ps1play knowledge install flappybird.ps1game
python3 -m ps1play knowledge list
python3 -m ps1play test flappybird          # the package's contract tests
python3 -m ps1play play flappybird          # autonomous play (headless)
python3 -m ps1play play flappybird --record # + GIF evidence
```

## Verified performance (the committed records)

* R61 family seeds byte-exact: k6/k60 = **87 pipes alive** at the
  10,000-frame budget (640 flaps); k12 76; k30 37; k45 40; k90 68.
* R61 pre-registered 30-seed evaluation: mean 52.30, median 48,
  min 10, max 87, 6/30 alive at budget.
* R65 fresh reserve-seed run through the product path (10 never-used
  seeds): mean 45.70, median 40, max 87 — the 87-pipe record
  reproduced on 3 fresh seeds; cross-process determinism exact.

## Known limitations

* The champion dies on ~1/3 of seeds early (heavy-tailed seed
  variance — documented in the R61 closure); the model is a
  small-MLP policy on a 10-feature vector, not a full visual agent.
* The package's perception (BirdObserverV7/GapTrackerV7) is tuned to
  FlappyBirdPSX v0.1.0's exact rendering; other versions are not
  covered by any record.
* CPU-only, headless runtime (no window mode).
"""


def _disc_pin():
    return {
        "game_id": "flappybird",
        "title": "FlappyBirdPSX",
        "source": "github.com/IcePanorama/FlappyBirdPSX v0.1.0 "
                  "(Unlicense)",
        "disc": {"image": "flappybirdpsx-v0.1.0.iso",
                 "bytes": 571536, "sha256": DISC_SHA,
                 "track_mode": "MODE2/2352 with license sectors "
                               "(direct boot, no patching)"},
        "boot": {"firmware": "OpenBIOS (third_party/openbios)",
                 "core": "beetle PSX (mednafen_psx_libretro.so)",
                 "ready_state": "the GET READY screen; the adapter "
                                "saves the anchor pre-seed",
                 "start_sequence": "B 3f -> 4f idle -> B 2f -> 4f idle "
                                   "after k idle frames (the seed k "
                                   "creates the pipe sequence)"},
        "observation": {
            "vector": "10 float32 features: by, vy, gc, dx, g0, g1, "
                      "flap_run, since_flap, last_gc, since_gap",
            "frame": "320x240 -> 60x80x3 area-average downsample",
            "normalization": "inside the ONNX graph (the vector is "
                             "unnormalized by contract)"},
        "actions": {"FLAP": "B (Cross) held the one decision frame",
                    "HOVER": "no input"},
        "terminal": "the beige GAME OVER panel (visual detector)",
        "progress": "pipes passed (PassageCounter, band-x edge events)",
    }


def build_spec() -> dict:
    def rp(*p):
        return os.path.join(REPO, *p)

    files = [
        (rp("ps1play", "adapters", "flappybird", "adapter.py"),
         "plugin/adapter.py", "plugin_source"),
        (rp("ps1play", "learn", "visual_only.py"),
         "knowledge/perception_visual_only.py", "perception_source"),
        (rp("data", "learn", "FINAL_MODEL_MANIFEST.json"),
         "knowledge/model_authority_manifest.json",
         "policy_authority_manifest"),
        (rp("data", "learn", "r61_validation_summary.json"),
         "knowledge/records_r61_validation.json", "evidence"),
        (rp("data", "learn", "r61_final_closure.json"),
         "knowledge/records_r61_closure.json", "evidence"),
        (rp("data", "r65", "r65_flappy_fresh_summary.json"),
         "knowledge/records_r65_fresh.json", "evidence"),
        (rp("tests", "test_r62_runtime.py"), "tests/test_r62_runtime.py",
         "test"),
        (rp("tests", "test_r62_integration.py"),
         "tests/test_r62_integration.py", "test"),
        (rp("tests", "test_r61_deployment.py"),
         "tests/test_r61_deployment.py", "test"),
        (rp("tests", "test_policy_frames.py"),
         "tests/test_policy_frames.py", "test"),
        (rp("tests", "test_learn_features_v2.py"),
         "tests/test_learn_features_v2.py", "test"),
    ]
    # the whole independent policy package
    for root, _dirs, fnames in os.walk(DEP):
        for fn in sorted(fnames):
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, DEP)
            files.append((full, f"policy/flappybird_policy/{rel}",
                          "policy_package"))
    files.append((
        {"game_id": "flappybird", **_disc_pin()},
        "knowledge/disc_pin.json", "disc_knowledge"))
    return {
        "game_id": "flappybird",
        "title": "FlappyBirdPSX (IcePanorama, Unlicense)",
        "version": "1.0.0",
        "maturity": "PARTIAL_AUTONOMOUS_PLAYER",
        "serial": "homebrew (no serial)",
        "region": "NTSC",
        "revision": "v0.1.0",
        "files": files,
        "readme": README.format(disc_sha=DISC_SHA),
        "runtime": {
            "runtime_version_compat": ["1.0.0"],
            "components": {
                "adapter_flappybird": "1.0.0",
                "policy": "flappybird_policy (R61 frozen champion, "
                          "sha 4dd592a7…)",
            },
            "python_packages": ["numpy==2.1.3", "onnxruntime==1.19.2",
                                "pillow>=10.0.0"],
        },
        "capabilities": {
            "autonomous_play": True,
            "objective": "endless survival (pipes passed); no "
                         "completion state exists",
            "diagnostics": ["contract tests", "disc hash pin",
                            "determinism (byte-identical replays)"],
            "test_command": "python3 -m ps1play test flappybird",
            "play_command": "python3 -m ps1play play flappybird",
        },
        "legal": {
            "assets_included": False,
            "user_must_provide": [
                "your own legally obtained FlappyBirdPSX v0.1.0 ISO "
                "(free homebrew, Unlicense)"],
            "package_contains": "PS1Play's own adapter, perception, "
                                "frozen policy package, records and "
                                "tests — no game image, no BIOS",
            "game_license": "Unlicense (the game itself)",
        },
    }
