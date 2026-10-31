#!/usr/bin/env python3
"""r61_issue_update.py — post the R61 FINAL CLOSURE report to Issue #13
and close it (every release gate passed), then read both back."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req, REPO  # noqa: E402

BODY = """**R61 FINAL CLOSURE report (the R57 workstream, concluded) — badges: IMPLEMENTED / TESTED / OBSERVED / PASS.** Evidence: `data/learn/r61_final_closure.json` · `docs/r61_final_closure.md` · `docs/r61_training_record.md` · `data/learn/r61_gate_result.json`. Commit `6949ed4` (base `d8bcbd3`). Suite **667 passed + 1 skipped + 1 xfailed**. hello_pong regression **PASS** (teachers 7/0 each, student 8/2 — the exact R54/R59/R60 record).

## Final status

```
TRAINING_STATUS:  CLOSED
DEPLOYMENT_STATUS: VERIFIED
EMULATOR_STATUS:   VERIFIED
REGRESSION_STATUS: PASS
RELEASE_STATUS:    PASS
```

## The frozen final model (provenance-proof, unchanged)

- champion checkpoint `data/learn/r59_soup_e6a010.npz` — sha256 `72c79f3091ed14e8dd497ddc52570bb4660bfc6367e6b50eb8a8aa1eff8a28f4`
- ONNX artifact `data/learn/r60_soup_e6a010.onnx` (7,182 B, opset 17) — sha256 `4dd592a7118a5c4de7b44166b42b8d09d53fbb59330d36d0ba2746393dc11044`
- `FINAL_MODEL_MANIFEST.json` (read-only, shipped into the package) — sha256 `10d9ec7f9ee96373927d6b006d0569a2f3083c10d2f035f0d7657dbd6133352b`
- Audit 14/14 PASS (`scripts/r61a_model_audit.py`): the champion npz **bitwise re-derived** as `r58_dir2p_true + 0.10*(r58_si_v2_e6 − r58_dir2p_true)`; every ONNX initializer bitwise-equal; topology/opset/dtype/action-mapping verified; no checkpoint swap. **No retraining happened in R61.**

## The independent deployment package (usable artifact)

`deployment/flappybird_policy/` — numpy + onnxruntime ONLY; **zero training/teacher imports** (AST scan + fresh-subprocess proof with `ps1play` unreachable); `load_policy / predict / predict_batch / logits_batch / reset / close` + hash-verified identity; strict enforced input contract (reject, never coerce); CLI smoke `python3 -m flappybird_policy`; pinned deps; full docs (README / INSTALL / INTERFACE / MODEL_CARD / KNOWN_LIMITATIONS / TROUBLESHOOTING / REUSE_BOUNDARY). **Clean-room install PASS** (fresh venv, pinned deps only).

## Verification evidence

- **Parity** (`r61b_parity_suite.py`): **220,522 deterministic vectors**, 3-way (inline numpy reference / bare ORT / the package as external consumer): argmax 100%, **max |Δlogit| 0.0** on every pair, min top-2 margin 4.23e-4; 6/6 malformed classes rejected; R60's 4,200 REAL vectors rechecked exact.
- **Emulator family reproduction through the package**: 7/7 byte-exact (k6 87-alive/640 · k12 76@8798/560 · k30 37@4401/281 · k45 40@4753/302 · k60 87-alive/640 · k90 68@7895/512 · k210 42@4966/322).
- **Fresh pre-registered validation**: 30 unseen seeds (k%7 rule, every prior use excluded; split on disk 9.5 min before collection) × champion n=2 + base n=1 + C1 n=1 = **180 episodes / 719,714 frames**; champion reps **byte-identical on all 30 seeds**; 37 cross-process duplicate groups byte-identical. Per-episode records with trace sha256: `data/learn/r61_validation_rows.jsonl`.
- **Comparison (same split)**: champion 52.30 mean / 48.0 median / min 10 / 6 alive vs base 46.87 / 38.0 / 10 / 2 (W/T/L **6/23/1** — strictly dominates its base) vs C1 53.37 / 50.0 / 12 / 5 (W/T/L 7/11/12 — **disclosed trade-off: C1 and the champion are statistically comparable on this split**; the R59 aggregate TEST win stands as published; no retraining triggered).
- **Robustness**: fault-injection tests green (missing/corrupt model, hash mismatch, garbage manifest, missing onnxruntime, NaN/Inf/dtype/shape/range rejection, close/reset lifecycle, runner failures surfaced as typed `LoopError`). Two runner incidents were detected, disclosed, fixed and pinned by regression tests (`data/learn/r61_runner_incident.json`).
- **Profile**: sustained 10,000 calls p50 **0.037 ms** / p95 0.048 ms (~22.5k calls/s); model load 14 ms; peak RSS delta 18.2 MB; the host perception adapter (1.11 ms/frame) dominates — inference is ~30× cheaper. **CPU-only suitable.**
- **Release gate**: `python3 scripts/r61_final_verify.py` → **9/9 PASS** (`data/learn/r61_gate_result.json`).

## Honest limitations

The ONNX graph is the decision function ONLY (perception is host-side numpy, documented in INTERFACE.md); parity is claimed for float32 CPU executors; the pipe-overlap perception latch class remains open (mitigated, documented); per-seed behavior is heavy-tailed; Linux/x86-64 portability only; the R57 save incident stays documented-not-fixable; no screenshots for the 187 grid episodes (trace hashes + byte-identical reps + live re-runs are the episode evidence).

## Closing

Every training stage R53→R60 is recorded in `docs/r61_training_record.md` (methods retained vs rejected with measured reasons; split hygiene; teacher-off enforcement; reproducibility). **The training workstream is closed: future work belongs to deployment and other-game integration, not further FlappyBird training.** Closing this issue as completed — all release gates passed.
"""

EDIT_BODY = """**R61 FINAL CLOSURE report (the R57 workstream, concluded) — badges: IMPLEMENTED / TESTED / OBSERVED / PASS.** Evidence: `data/learn/r61_final_closure.json` · `docs/r61_final_closure.md` · `docs/r61_training_record.md` · `data/learn/r61_gate_result.json`. Commit `6949ed4` (base `d8bcbd3`). Suite **667 passed + 1 skipped + 1 xfailed**. hello_pong regression **PASS** (teachers 7/0 each, student 8/2 — the exact R54/R59/R60 record).

**Final status: `TRAINING_STATUS: CLOSED` · `DEPLOYMENT_STATUS: VERIFIED` · `EMULATOR_STATUS: VERIFIED` · `REGRESSION_STATUS: PASS` · `RELEASE_STATUS: PASS`**

**Frozen model (provenance-proof, unchanged):** champion `r59_soup_e6a010.npz` sha256 `72c79f30…` (bitwise re-derived soup: `r58_dir2p_true + 0.10*(r58_si_v2_e6 − r58_dir2p_true)`); ONNX `r60_soup_e6a010.onnx` sha256 `4dd592a7…`; `FINAL_MODEL_MANIFEST.json` read-only. Audit 14/14 PASS — no retraining in R61.

**The usable artifact:** `deployment/flappybird_policy/` — an independent consumer (numpy + onnxruntime only, zero training/teacher imports — AST + fresh-subprocess proof), strict enforced input contract, hash-verified identity, CLI smoke, pinned deps, full docs, **clean-room install PASS**.

**Verification:** 220,522-vector 3-way parity — argmax 100%, max |Δlogit| **0.0**; family reproduction through the package **7/7 byte-exact**; fresh pre-registered 30-seed validation ×(2+1+1) = **180 episodes / 719,714 frames**, champion reps byte-identical on all 30 seeds; comparison: vs base W/T/L **6/23/1** (52.30 vs 46.87 mean), vs C1 **7/11/12** (disclosed trade-off — statistically comparable on this split; the R59 aggregate TEST win stands; the stop rule held, no retraining); fault-injection suite green (two runner incidents disclosed + fixed + regression-tested); sustained profile p50 0.037 ms/call, perception dominates at 1.11 ms/frame; release gate **9/9 PASS**.

**Honest limitations:** decision-only ONNX boundary (perception is host-side numpy per INTERFACE.md); float32-CPU parity scope; the pipe-overlap latch class remains open (mitigated); heavy-tailed per-seed behavior; Linux/x86-64 only; no screenshots for grid episodes (trace hashes + byte-identity + live re-runs are the evidence).

Every stage R53→R60 is recorded in `docs/r61_training_record.md` (retained vs rejected methods with measured reasons, split hygiene, teacher-off enforcement). **The training workstream is closed: future work belongs to deployment and other-game integration, not further FlappyBird training.**"""


def main():
    s, c = req(f"/repos/{REPO}/issues/13/comments", method="POST",
               payload={"body": EDIT_BODY})
    print("comment POST:", s, c.get("id"))
    cid = c.get("id")
    s2, c2 = req(f"/repos/{REPO}/issues/comments/{cid}")
    print("comment read-back:", s2,
          "match:", c2.get("body") == EDIT_BODY)
    s3, i = req(f"/repos/{REPO}/issues/13", method="PATCH",
                payload={"state": "closed", "state_reason": "completed"})
    print("issue close:", s3, i.get("state"))
    s4, i2 = req(f"/repos/{REPO}/issues/13")
    print("issue read-back:", s4, "state:", i2.get("state"),
          "comments:", i2.get("comments"))
    return 0 if (s2 == 200 and c2.get("body") == EDIT_BODY
                 and i2.get("state") == "closed") else 2


if __name__ == "__main__":
    sys.exit(main())
