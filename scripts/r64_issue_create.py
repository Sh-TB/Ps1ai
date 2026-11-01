#!/usr/bin/env python3
"""r64_issue_create.py — open the R64 tracking issue (the #14 pattern):
Tetrade as the second runtime game."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

TITLE = ("[R64] Tetrade — the second runtime game "
         "(one-command `python3 -m ps1play play tetrade`)")

BODY = """## Goal

Execute the `docs/r62_architecture.md` "adding a second game" recipe for real: ship **Tetrade** as the runtime's second registered game, on top of the fresh R63 evidence (commit `c708c03` — full loop re-delivery for #8: struct at `0x1FECA0`, anchor map verified live, Dellacherie 2-ply policy, 1 verified clear, natural game over, restart).

`python3 -m ps1play play tetrade` must work exactly like `play flappybird` — same engine, controller, telemetry, lifecycle, CLI, exit-code vocabulary, episode records. **No runtime-core game knowledge** (the only core amendment allowed: a *generic* per-game policy factory in the registry, because Tetrade's policy is a built-in hand-written heuristic, not a frozen model package).

## Definition of DONE

1. **Adapter**: `ps1play/adapters/tetrade/` implements the full `GameAdapter` contract — R63-proven entry sequence (incl. the disclosed PAUSED key-repeat trap: START taps ≤4f), struct scan with the live-piece retry, RAM-read perception (zero writes, zero core edits), the R63 restart flow (CONTINUE refused with CIRCLE → fresh Marathon verified) for episodes ≥ 2.
2. **Policy**: `DellacheriePolicy` — the R63 2-ply planner ported verbatim (weights, features, NEXT-piece refinement) behind the runtime `Policy` contract; per-frame action realization (rotate → move → hard drop) with the game's own cooldowns; identity = sha256 of the policy source (no model, **no training**).
3. **Generic wiring**: registry carries the game (+ policy factory + progress label); `resolve_iso`/preflight pin the Tetrade disc hash (`7eb38eda…`); `config.validated()` accepts every *registered* game (registry-driven, not a hardcoded list).
4. **Tests**: offline contracts (Dellacherie math vs hand-computed boards, policy state machine, adapter vector layout, synthetic-RAM struct scan, registry/config/CLI) + real-emulator integration (boot → ready → episode start → struct located; a short engine episode) — added, never weakened.
5. **Acceptance**: real `python3 -m ps1play play tetrade` runs with committed evidence — ≥1 verified line clear through the PRODUCT path, natural game over, a second episode restarting fresh (score/lines/level 0, empty board), committed trace/summary/screenshots.
6. **No regression**: the full suite green (R62's 731+1xfail preserved) and the R62 release gate re-run PASS; TRAINING STAYS CLOSED (Tetrade's policy is hand-written; nothing retrains, no model touched).

## Honesty / boundaries

- Perception is **RAM-read-based** for Tetrade (the loop #8 itself documents; R63 precedent) — the flappy vision model does NOT generalize and is not used.
- `seed_k` is recorded for run labeling only: the zero-writes rule forbids seeding the game's internal RNG, so piece sequences are not seed-controlled (disclosed in every record's docs).
- The heuristic policy is legal but weak (R63: 1 clear / 28 pieces); the bar is the DoD, not a score target.
"""

s, i = req(f"/repos/{REPO}/issues", method="POST",
           payload={"title": TITLE, "body": BODY,
                    "labels": []})
print("issue POST:", s, "#", i.get("number"), i.get("state"))
s2, i2 = req(f"/repos/{REPO}/issues/{i['number']}")
print("read-back:", s2, i2.get("title") == TITLE,
      i2.get("body") == BODY)
sys.exit(0 if (s == 201 and s2 == 200 and i2.get("body") == BODY) else 1)
