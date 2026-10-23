#!/usr/bin/env python3
"""post_issue5_repro_series.py — the owed reproducible rear_check live
series (4/4 identical firings) + the four-category final report."""
import sys
sys.path.insert(0, "/home/z/my-project/scripts")
import gh_api

BODY = """## Reproducibility batch — the owed rear_check live series DELIVERED (4/4) + four-category final report (2026-10-23)

**Baseline:** HEAD `b283b19` + this batch (pushed, API-verified). Suite re-verified **384 passed + 1 xfailed** before the live series. This closes the one item the previous comment left open ("rear_check … live-OBSERVED once; a reproducible live series is still owed").

### 1. The series (deliverable: same checkpoint, four independent boots)

`scripts/msx_ckpt_policy_pass.py` re-ran the identical policy-driven `chopper_ckpt` pass (px 810.3, UNFROZEN, first-death endpoint) three more times (`policy_pass2/3/4`):

| pass | rear_check firing | geometry at firing | buttons | outcome |
|---|---|---|---|---|
| pass1 (prior) | chunk 25 | slot 14 x 1126.5, dx −37.5, hp 254, h 64 | `B+LEFT+Y` (one chunk) | died chunk 26 |
| pass2 | chunk 25 | identical | identical | died chunk 26 |
| pass3 | chunk 25 | identical | identical | died chunk 26 |
| pass4 | chunk 25 | identical | identical | died chunk 26 |

**4/4 identical firings across four independent emulator boots** — enemy-behind now triggers direction correction REPRODUCIBLY, not just once (offline `test_case2_rear_pursuer_turns_bounded` + this series). Ledger D2 direction correction: live-OBSERVED → **live-TESTED**.

### 2. Honest disclosure (same runs)

The fired Y-burst did **not** change the truck's hp (254→254 in all 4 passes): the armored vehicle resists forward fire from that geometry — the grenade-equipped `clamp_clear` path remains the proven kill mechanism (session-3: 5901 clamp kills). D2 kill follow-through vs armor stays **PARTIAL**; every pass still dies at the clamp one chunk later (one-shot −291 truck ram at px 1164 — the D6/D7 corridor-lethality blocker, unchanged).

### 3. Minor matrix update

hello_pong (`marconvcm/ps1_dev`) re-verified via API: **0 releases exist** (the CI only publishes on tags, none pushed) and Docker is absent from the sandbox for a source build → matrix entry demoted PENDING → **BLOCKED** (`docs/simple_games_ranking.md`). The category-2/3/4 (enemy-bearing homebrew) gap stands.

### 4. Final report (mission deliverable 7)

`docs/final_report_coder2.md` — the whole Coder-2 mission consolidated into the four required categories: **fixed+unit-tested / real-emulator-verified / partially verified / still blocked+why**, plus the acceptance-criteria scorecard (6/6 MET, with D2 kill-follow-through and D6/D7 honestly carved out as partial/blocked) and the deliverable index. Updated `docs/defect_ledger.md` carries the new labels.

**Commands:** `python -m pytest tests/ -q`; `python scripts/msx_ckpt_policy_pass.py --tag policy_passN --chunks 60`. Evidence local: `evidence/heli_ladder/policy_pass{1..4}/` (trace.jsonl + report JSON per pass).
"""

st, r = gh_api.req(f"/repos/{gh_api.REPO}/issues/5/comments",
                   method="POST", payload={"body": BODY})
print("HTTP", st, "->", r.get("html_url", r))
