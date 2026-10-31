#!/usr/bin/env python3
"""r58_issue_report.py — post the R58-continue round report to Issue #13
and read it back."""
import json
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = r"""
**R58-continue round report (the R57 workstream, continued the same
day) — badges: IMPLEMENTED / TESTED / OBSERVED.** Evidence:
`data/learn/r58_flappy_evidence.json` · `docs/r58_execution_report.md`.
Suite: **638 passed + 2 skipped + 1 xfailed**.

## 1. The R57 record, corrected by forensics [OBSERVED]

- The in-process ARS decision path and the deployed BrainClient were
  proven identical FIRST (replay: **0/7345** action mismatches on a
  recorded real life; k72=87 / k195=87 reproduce byte-exactly today).
- The saved `r57_es2_dir2p.npz` is **NOT** the recorded iter-0
  dir-2-plus theta: |θ−θ_si| = 2.08 vs one ARS step 1.21, cos 0.56 vs
  δ₂, **32.7%** of the displacement inside the recorded ARS subspace
  (55° off) — a save incident (root cause lost with the wiped scratch).
- **Recovery**: `r58_dir2p_true.npz` = si_v1 + 0.03·δ₂ rebuilt from the
  committed artifacts + the committed seeded stream — it scores EXACTLY
  the recorded pair **k6=87 AND k60=87 budget-alive @10000** (640 flaps
  each). The 87/87 claim was real; only the save was wrong.
- **Survives**: all 24 R57 TEST numbers (reproduce exactly), the
  lineage, PART 12 causality. **SUPERSEDED**: the champion-npz
  provenance (downgraded UNKNOWN-beyond-si_v1) and its 87/87
  attributions (the mis-saved theta measures 63 / 80@9253).

## 2. The k210 deficit is CLOSED [OBSERVED]

It belonged to the mis-save. The corrected base reaches **teacher-level
42 on k210** (death @4966 vs the teacher diagnostic's 4968). Family
(fresh boots, deterministic): k6 **87 alive**, k12 76, k30 37, k45 33,
k60 **87 alive**, k90 68, k210 **42** — meets or beats the teacher on 6
of 7 family seeds (k45 −1). The one teacher episode this round was an
ASSISTED diagnostic in a teacher-only process (no student labels).

## 3. ARS round 2 — exhausted (honest structural negative) [OBSERVED]

Fitness mean(k90,k210)@10000, init = the corrected base,
**save-at-selection** (the r57 lesson hard-wired). Iter-0: **zero** of
12 rollouts beat the base fitness 55; the candidate gated k60 87→29 →
REJECTED. Sibling sweep: ALL es2 iter-0 siblings measured — 6/12
exactly invariant (68/42), 6/12 collapse, none better. **The base is a
collapse plateau at σ=0.03.**

## 4. Self-imitation round 2 — gate-rejected, insight kept [OBSERVED]

Fine-tune on the base's own three lives (28,798 rows, arm-D recipe,
epochs 4/6/8/15/25): e4 lifts k12→87-alive and k45 33→**47** but
collapses k60 87→**14**; e6/e8 trade k6/k90 down; e15/e25 drop k90.
Every fine-tune trades the fragile 87s for mid-depth gains —
thrice-replicated across ARS/siblings/SI: **the base is a sharp local
optimum; no tested one-shot weight move improves it.**

## 5. The fresh TEST — the student beyond both references [OBSERVED]

Split committed BEFORE collection (`fd1c1422`, read-back verified):
20 never-used seeds, champion n=3, refs n=1, 100 episodes.

| model | mean | median | min | ≥50 |
|---|---|---|---|---|
| **r58_dir2p_true** | **53.35** | **51.0** | 10 | **10/20** |
| C1 (frozen R56) | 47.65 | 40.0 | **0** | 6/20 |
| r57_es2_dir2p | 42.25 | 36.5 | 10 | 7/20 |

Paired: **+11.1** vs the R57 champion (W/T/L 8/8/4), **+5.7** vs C1
(8/7/5, C1 holds a 0-pipe catastrophe seed). Champion n=3
byte-identical on all 20 seeds.

## 6. Honest limitations

The incident's root cause is unknown (scratch wiped) — mitigated
structurally, not explained. k45 33 vs teacher 34. The 87-alive
trajectories are razor-edges. C1 keeps 5 paired wins (not uniformly
dominated). ONNX: PENDING (native numpy is the deployment per the
review bar). Teacher k210=42 is this round's ASSISTED diagnostic
(4968-step life) vs the r56-era 34@4000 — disclosed, not directly
comparable.

**Artifacts**: `r58_dir2p_true.npz` (7,090 B, ≤4 MiB bar) + the
gate-rejected `r58_si_v2_e*.npz` preserved; scripts r58a–r58j;
worklog entry R58-continue.
"""


def main():
    s, c = req(f"/repos/{REPO}/issues/13/comments", method="POST",
               payload={"body": BODY})
    assert s == 201, (s, c)
    cid = c["id"]
    s, back = req(f"/repos/{REPO}/issues/comments/{cid}")
    assert s == 200 and back["body"] == BODY
    print("comment posted + read back:", cid)


if __name__ == "__main__":
    main()
