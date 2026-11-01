"""ps1play.adapters.tetrade.package_spec — the tetrade.ps1game builder
(R65, Part F7).  The game's own knowledge-package descriptor; no other
game's material is referenced (the isolation rule).
"""
from __future__ import annotations

import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

DISC_SHA = ("7eb38eda1274b6c2dba81dc490598d5b8a9e683025a0afd604ec"
            "130d063c3cc1")

README = """# tetrade.ps1game — PS1Play game knowledge package

**Game:** Tetrade (Logan Campbell, **MIT**) — homebrew Tetris; the
SECOND registered PS1Play runtime game (R64), now with the R65
anchor-corrected Dellacherie policy.

**Maturity:** PARTIAL_AUTONOMOUS_PLAYER — real autonomous gameplay is
verified end-to-end (verified line clears, natural game overs,
NEXT-promotion cross-check 53/53); Marathon is endless, so no higher
level applies.

## What is in this package

| path | role |
|---|---|
| `plugin/adapter.py` | the runtime GameAdapter: RAM-read perception over the TetradeGame struct (base 0x1FECA0), entry/restart sequences, recovery |
| `plugin/policy.py` | the Dellacherie 2-ply policy **with the R65 measured ANCHOR_DELTA table** (the placement model matches the game's true columns) |
| `knowledge/anchor_table_r65.json` | the 28/28 measured (type, rotation) -> column-anchor deltas (the core RE knowledge of this package) |
| `knowledge/anchor_evidence_lockprobe.json` | the placement-decoding evidence (22 pre-drop/lock diffs) |
| `knowledge/improvement_record_r65.json` | the before/after record: 1.0 -> 23.83 lines/life |
| `knowledge/disc_pin.json` | disc identity + boot/entry/restart knowledge |
| `tests/` | the game's contract tests + real-emulator integration tests |

## The R65 discovery (what makes this package work)

The struct's piece x is NOT the left edge of the policy's rotation
model for every rotation: measured on the real game, the 3-wide
pieces (J/L/S/Z/T) render ONE COLUMN LEFT of the model at rotations
1 and 2 (I and O never shift).  The uncorrected R64 policy buried
39 holes per life; the corrected policy clears a mean of **23.83
lines per life** (max 36) — a ~24x improvement, verified through the
product path on 6 fresh episodes.  Zero memory writes; the policy
remains hand-written (training stays closed).

## Legal

This package contains **PS1Play's own knowledge only**.  You provide
your own legally obtained Tetrade v1.0 release (free homebrew, MIT,
github.com/Logan-Campbell/Tetrade); the runtime verifies its SHA-256
(`{disc_sha}`) before playing.  NOTE: unpatched homebrew discs
boot-loop in the OpenBIOS shell (the license-sector requirement) —
produce a LOCAL license-patched image from your own retail disc with
the runtime's `scripts/make_homebrew_lic.py` (the patched image stays
on your machine, exactly as in PS1Play's own sandbox).

## Quick start (inside a PS1Play runtime checkout)

```bash
python3 -m ps1play knowledge validate tetrade.ps1game
python3 -m ps1play knowledge install tetrade.ps1game
python3 -m ps1play test tetrade
python3 -m ps1play play tetrade --record
```

## Verified performance

* R64 acceptance: 2 episodes, 56 pieces, 1 verified line clear, NEXT
  cross-check 53/53, restart flow verified (uncorrected policy).
* R65 fresh benchmark (uncorrected): 0/1/2/1 lines across 4 lives
  (~25 pieces/life, 39 holes at death).
* R65 anchor-corrected (this package's policy): mean **23.83
  lines/life**, max 36, 2/6 episodes alive at the 10,000-frame
  budget (300+ pieces/life).

## Known limitations

* Perception is RAM-read (read-only); there is no visual model for
  Tetrade and none is claimed.
* The entry/restart frame sequences are tuned to the beetle+OpenBIOS
  backend; boot flakiness is MITIGATED (verified-ready + boot retry),
  not eliminated.
* The policy is legal but not a strong player: it dies to mid-game
  mis-drops; there is no hold piece and no 3-ply lookahead.
"""


def _disc_pin():
    return {
        "game_id": "tetrade",
        "title": "Tetrade",
        "source": "github.com/Logan-Campbell/Tetrade v1.0 (MIT)",
        "disc": {"image": "TETRADE_PSX.bin", "bytes": 3196368,
                 "sha256": DISC_SHA,
                 "note": "license-patched LOCAL image "
                         "(TETRADE_lic.bin) is what the runtime pins; "
                         "homebrew discs need license sectors to pass "
                         "the OpenBIOS CDChecker"},
        "boot": {"firmware": "OpenBIOS (third_party/openbios)",
                 "core": "beetle PSX (mednafen_psx_libretro.so)",
                 "struct": "TetradeGame @ RAM 0x1FECA0 (three "
                           "independent boots)",
                 "entry": "title START hold 120f -> menu settle 240f -> "
                          "B on '>Marathon Mode<' 12f -> START taps "
                          "<=4f (the PAUSED key-repeat trap) -> "
                          "countdown 280f",
                 "restart": "game over -> CIRCLE refuses the continue "
                            "-> menu START tap -> re-entry"},
        "observation": {
            "vector": "222 float32: board 20x10 row-major, current "
                      "piece one-hot + rot/x/y, NEXT one-hot, score, "
                      "lines, level, over, paused",
            "perception": "RAM-read (read-only snapshot), no visual "
                          "model"},
        "actions": {"ROT_CW": "A (Cross)", "MOVE_L": "LEFT",
                    "MOVE_R": "RIGHT", "HARD_DROP": "UP",
                    "IDLE": "no input", "PAUSE_TOGGLE": "START"},
        "terminal": "isGameOver @struct+2312 (natural game over)",
        "progress": "lines cleared (single+double+triple+tetrade)",
        "anchor_deltas": "see knowledge/anchor_table_r65.json — the "
                         "measured per-(type,rotation) column shift",
    }


def build_spec() -> dict:
    def rp(*p):
        return os.path.join(REPO, *p)

    files = [
        (rp("ps1play", "adapters", "tetrade", "adapter.py"),
         "plugin/adapter.py", "plugin_source"),
        (rp("ps1play", "adapters", "tetrade", "policy.py"),
         "plugin/policy.py", "policy_source"),
        (rp("ps1play", "adapters", "tetrade", "__init__.py"),
         "plugin/__init__.py", "plugin_source"),
        (rp("data", "r65", "r65_tetrade_anchor.json"),
         "knowledge/anchor_table_r65.json", "re_knowledge"),
        (rp("data", "r65", "r65_tetrade_lockprobe.json"),
         "knowledge/anchor_evidence_lockprobe.json", "evidence"),
        (rp("data", "r65", "r65_tetrade_improvement.json"),
         "knowledge/improvement_record_r65.json", "evidence"),
        (rp("data", "r63", "tetrade_full_loop_summary.json"),
         "knowledge/records_r63_full_loop.json", "evidence"),
        (rp("data", "r64", "r64_acceptance_summary.json"),
         "knowledge/records_r64_acceptance.json", "evidence"),
        (rp("tests", "test_r64_tetrade.py"),
         "tests/test_r64_tetrade.py", "test"),
        (rp("tests", "test_r64_integration.py"),
         "tests/test_r64_integration.py", "test"),
        ({"game_id": "tetrade", **_disc_pin()},
         "knowledge/disc_pin.json", "disc_knowledge"),
    ]
    return {
        "game_id": "tetrade",
        "title": "Tetrade (Logan Campbell, MIT)",
        "version": "1.1.0",
        "maturity": "PARTIAL_AUTONOMOUS_PLAYER",
        "serial": "homebrew (no serial)",
        "region": "NTSC (license-patched local image)",
        "revision": "v1.0",
        "files": files,
        "readme": README.format(disc_sha=DISC_SHA),
        "runtime": {
            "runtime_version_compat": ["1.0.0"],
            "components": {
                "adapter_tetrade": "1.0.0",
                "policy": "tetrade_dellacherie_2ply 1.1.0 "
                          "(anchor-corrected)",
            },
            "python_packages": ["numpy==2.1.3", "pillow>=10.0.0"],
        },
        "capabilities": {
            "autonomous_play": True,
            "objective": "Marathon endless survival (lines cleared); "
                         "no completion state exists",
            "diagnostics": ["contract tests", "real-emulator "
                            "integration tests", "disc hash pin",
                            "NEXT-promotion cross-check"],
            "test_command": "python3 -m ps1play test tetrade",
            "play_command": "python3 -m ps1play play tetrade",
        },
        "legal": {
            "assets_included": False,
            "user_must_provide": [
                "your own legally obtained Tetrade v1.0 release + a "
                "LOCAL license-patched image made from your own "
                "retail disc (scripts/make_homebrew_lic.py)"],
            "package_contains": "PS1Play's own adapter, policy, RE "
                                "knowledge, records and tests — no "
                                "game image, no BIOS",
            "game_license": "MIT (the game itself)",
        },
    }
