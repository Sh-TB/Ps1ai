"""ps1play.adapters.buzzybee — the BuzzyBee GameAdapter + policy (R65).

BuzzyBee (github.com/NDR008/BuzzyBee, MIT) is the THIRD runtime game
(the R64 recipe's second execution).  The game-specific knowledge
lives HERE and in its downloadable .ps1game package — the shared
runtime knows nothing about bees, wasps, flowers or rocks.

Provenance (the committed R23–R52 evidence this adapter is built on):
  * boot: the wrapped NTSC disc (upstream EXE 9b0bfc08… + the
    disclosed 2-instruction NTSC patch + the user's own license
    sectors) — boots and RENDERS on beetle+OpenBIOS (r23/r30);
    disc sha256 042b94bb… is the recorded bytes.
  * RAM anchors: ALL VERIFIED in data/knowledge/buzzybee/capsule.json
    (gameState 0x80058830, best 0x80058838, score 0x8005883C,
    input 0x8005881C/20/24, player 0x8005EDC0, wasp 0x8005EB7C,
    flowers 0x8005EBA0 stride 0x24 ×3, rocks 0x8005F55C, health
    0x8005EF48) — located by input causality and source layout, then
    live-cross-validated.
  * policy: bot_policy8 (R45-B → R48-B → R52-B), the tiered-margin
    guarantee planner — the R52-B dominance recipe PASSED at every
    tested cap (1800→2400, 9 passes, score = f − 99 exact).
  * perception is RAM-read (the loop Issue #6 documents; R63/R64
    precedent — per-game, read-only).

ZERO memory writes; ZERO core edits; legal controller input only.
"""
from ps1play.adapters.buzzybee.adapter import BuzzyBeeAdapter  # noqa: F401
from ps1play.adapters.buzzybee.policy import BuzzyPolicy      # noqa: F401

ADAPTER_VERSION = "1.0.0"
