#!/usr/bin/env python3
"""r37_issue10_report.py — post the R37 addendum to Issue #10 (verified
after posting by re-reading the comment)."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """## R37 addendum — knowledge-capsule system, MSX prior-art import, cheat-DB anchor probe (2026-10-29)

Task executed end-to-end this round: reconcile -> research -> implement -> test -> bounded probe -> commit. Commit `b363cf4` on `main` (pushed via API; local HEAD `b363cf46628a`). Suite: **577 passed + 1 xfail** (12 new tests, all 565 pre-existing green; xfail preserved).

### 0. Environment reconciliation (Part 1)
- 8th filesystem rollback detected: local `main` had regressed to `6b97fbe`; repaired to `origin/main` = `002223c` (R36) via fetch+reset. Boot stack re-verified (beetle core, OpenBIOS, local retail disc). capstone reinstalled.
- Historical results (R35 mspSX win, BuzzyBee bot, MSX D7 pin @1164) treated as historical per task; not re-claimed.
- Issue #10 Gate A state re-read (Ghidra 11.4.2 corpus, MSX static KB 4,915 EXE + 331 overlay fns, m2c ranked #4 EXPERIMENT-FURTHER) — extended, not duplicated.

### 1. Prior-art matrix — new inspected entries (Part 2, source-inspected)
| Candidate | What was inspected | Classification | Decision |
|---|---|---|---|
| **TechnicallyComputers/Metal-Slug-X-Recomp** | cloned; `catalog_identity.json` declares **SLUS-01212 = our exact build**; `analysis/functions.tsv` = **2,931 EXE functions** (addr/size/confidence/args/ret/callers/callees) + `edges.json` 7,725 call edges; progressive symbols = **1 named** (`PSX_FN_BootEntry 0x80082A44`); generated C is **mechanical, not original source**; **no ENEMY.BIN overlay coverage**; **no LICENSE file found** (checked) | METHOD_REUSABLE (static analysis data) + NOT original-source | **ADOPT (data only)**: functions.tsv + edges.json imported to `data/knowledge/msx/external/` with `PROVENANCE.md` (reference-only, license gap recorded, requires owning the game; generated C not imported) |
| gamehacking.org MSX NTSC-U (`/game/89284`, Code Master/nolberto82) + cheatcc 2001 variants | full code list read | CALIBRATION_ONLY until validated | **ADOPT as hypotheses** (see §3) |
| psxdatacenter SLUS-01212 | identity page (publisher/date/track count) | CALIBRATION_ONLY | cross-check recorded in capsule identity |
| PS1Recomp / psxrecomp ecosystem | via the recomp repo's pipeline (psxrecomp-analyze outputs above) | METHOD_REUSABLE | PENDING (tool itself not yet run locally) |
| PSXLE (tiptree), RillAi, jev-game-agent, pokemon-agents, ViZDoom, Stable-Retro | prior Gate A + this round's survey; nothing PS1-RAM-first beats our beetle path for the gameplay backend | NOT_APPLICABLE / METHOD_ONLY | REJECT as frameworks; observation model (action-frame-duration, termination contracts) noted for Part 6 |
| PSXPrev / jpsxdec / RetroReversing | prior rounds' inspection recorded in `docs/tools_matrix_issue6.md` | AUXILIARY | unchanged |

Decomps note: REDRIVER2 / silent-hill / sotn / mgs_reversing remain **reconstruction projects, not reusable semantics for SLUS-01212**; the only MSX-specific prior art found is the recomp above (static boundaries/call-graph only, 1 symbol).

### 2. Implemented reusable capability (Parts 4-6) — code, not a list
- **`ps1play.knowledge`**: `ps1play.capsule/1` schema — per-fact STATUS (`VERIFIED/OBSERVED/INFERRED/UNKNOWN/CONTRADICTED/BLOCKED`), provenance (`source`+`evidence`) **mandatory for VERIFIED/OBSERVED**; portability limits (warn >64 KiB, **hard reject >128 KiB**); artifact references require `path+sha256` (no embedded dumps); compact queries (`fields_by_role`, `functions_near`, `contradictions`); **`require_observable` gate** — reward/ground-truth consumers cannot silently use INFERRED facts (loud `CapsuleError`); `fields_by_role(min_status=True)` fails loudly when no observable field exists (no empty-list lie).
- **`AnalysisCache`**: key = sha256(game_id, input-hashes, tool, config); per-key invalidation (`invalidate(game_id, tool=None)`); `UnsupportedAddress` error type (explicit failure instead of silent zero).
- **Knowledge CLI** (`scripts/ps1play_knowledge.py`, delegated from the existing `ps1play_cli.py` so the gameplay surface is untouched): `capsule-validate`, `capsule-query [--role|--near|--unknowns]`, `capsule-build`, `cache-stat`, `intake-game --game X --budget-minutes N --resume` implementing the 10-stage pipeline with **per-stage cache decisions** and a local-assets gate that reports the exact missing prerequisite instead of pretending.
- **Three capsules built from local verified evidence only**: `buzzybee` 6.6 KB (14 VERIFIED fields incl. entity map, 3 controls, systems-closure events), `mspsx` 3.7 KB (win + sensor set), **`msx` 8.0 KB** (closed-source target: VERIFIED entity table 0x800CA268 stride 0x14C HP+0x8E from Issue #5 A/B; cheat-DB leads recorded as **INFERRED with struct-consistency notes**; 5 events incl. D7-pin facts; unknowns + next-experiment). All < 64 KiB.

### 3. MSX bounded probe — honest results (Part 3)
`scripts/r37t1_msx_cheat_anchors.py`, **boot cap 2 disclosed before run, 2/2 used**, read-only (no writes, no cheats):
- Reach attempt: pure-input menu ladder (r17 ground truth) **NOT reproduced** after rollback #8 — states byte regressed 9→6 under repeated CROSS; the r17 checkpoints that made later rounds cheap were wiped. **New reproducibility fact**: the ladder depends on checkpoint state; the recorded next experiment is a cursor-struct-driven re-walk (0x957D8-0x957F8 polling).
- Hypothesis verdicts (`scratch/r37/msx_anchors/verdicts.json`): H1 score-P1 `0x800EE318` → **OBSERVED_ZERO** (plausible, stable in the no-input control window, no in-game causal window reached); H2 prisoners `0x80087A78` / H3 unlock byte `0x800D4213` → OBSERVED consistent (H3 corroborates the r20 unlock-counter block); H4 P1-HP `0x800CA2F6` → **BLOCKED** (ladder). All cheat-DB addresses stay **INFERRED in the capsule** — none promoted without in-game causality.
- **Best-supported D7 cause (unchanged but now better characterized)**: camera-pin release condition unowned; mosque-cannon pin-lift remains the single highest-information experiment (per r35), now with the recomp call-graph imported as the function-suspicion shortlist source (2,931 fns queryable offline — no Ghidra re-run needed for boundary/edge questions).

### 4. Tests + measured costs (Parts 7-8)
- `tests/test_knowledge.py`: 12 tests — identity/status/provenance gates, ground-truth promotion lock, artifact hash rule, size hard limit, queries (incl. verified-only loud failure), roundtrip, cache hit/miss/**invalidation-on-changed-input**, `UnsupportedAddress`, CLI delegation (subprocess), shipped-capsule validation. Full suite **577+1xfail in ~9 s**.
- Cache reuse **proven**: 2nd `intake-game --resume` run = **10 HIT / 0 MISS, 0.0 s**.
- Measured (honest, no fabricated speedups): rollback repair ~2 min; capsule build <1 s each; MSX capsule (7.9 KB) now answers identity/RAM/prior-art/next-experiment questions without re-reading the 682-line worklog + 455-line sources doc; external import makes 2,931 functions + 7,725 edges queryable at zero emulator cost. HISTORICAL baseline: D7 investigation spanned r17→r35 across many sessions — the capsule records this as provenance, not as a measured speedup.

### 5. Claim-status table
| Claim | Status |
|---|---|
| Capsule schema + provenance gates + size limits | IMPLEMENTED, TESTED |
| Fingerprint cache + invalidation | IMPLEMENTED, TESTED (hit/miss/invalidate) |
| Knowledge CLI + intake 10-stage with cache decisions | IMPLEMENTED, TESTED (offline stages) |
| Emulator probe stage of intake (in-game windows) | PARTIAL (assets gate + ladder BLOCKED this round) |
| 3 capsules (buzzybee/mspsx source-assisted, msx closed-source) | IMPLEMENTED, TESTED (validate + size) |
| MSX cheat-DB anchors (score/prisoners/unlock/HP) | PENDING (INFERRED; in-game validation = next experiment) |
| MSX D7 pin resolution | BLOCKED (best cause + next experiment recorded) |
| MSX-Recomp import (2,931 fns, same build) | IMPLEMENTED (data + provenance; license gap disclosed) |
| Learning-environment contract (Part 6) | PENDING (contract requirements now specified in capsule + harness terms; next round) |
| Prior-art matrix extension | IMPLEMENTED (this comment + capsule prior_art) |

Next highest-value steps: (1) cursor-struct menu re-walk to unblock H1/H4 validation windows; (2) D7 pin-lift experiment with the imported call-graph as the shortlist; (3) Part 6 env-contract test on mspSX (known-good) then MSX.

Local evidence: `scratch/r37/msx_anchors/`, `data/knowledge/{buzzybee,mspsx,msx}/capsule.json`, `data/knowledge/msx/external/PROVENANCE.md`. Worklog: R37 entry. Cross-links: #3 (entity table), #5 (A/B anchors), #6 (runtime + intake), #9 (decision loop)."""

s, r = req(f"/repos/{REPO}/issues/10/comments", "POST",
           {"body": BODY})
print("POST status:", s, "comment id:", r.get("id"))
if s in (200, 201):
    s2, r2 = req(f"/repos/{REPO}/issues/10/comments/{r['id']}")
    ok = r2.get("body", "").startswith("## R37 addendum")
    print(f"VERIFY: re-read comment {r2.get('id')} len={len(r2.get('body',''))} "
          f"head_ok={ok} url={r2.get('html_url')}")
    sys.exit(0 if ok else 1)
sys.exit(1)
