# R46-B (Issue #6, the 40% track): the score mechanism is TIME — every delta is +1/frame

**Round**: R46 (buzzybee). **Protocol**: restore-only, boot = the core+rom load only; the preserved `scratch/r45b/state_r45b_gs1.bin` (READ-ONLY). One `bot_policy5` arm, 1500 f, the R45-B arm-A protocol verbatim (same checkpoint, same kw, same pass/pickup/attribution machinery). **Boot ledger**: cap amended 1→2, disclosed (boot 1 = killed by the operator shell timeout at f≈268/1500 — the runner was healthy; the re-run added a one-boot timing probe: 407 fps across raw/loop/telemetry 60 f variants, the slowness never reproduced, the probe world discarded by a clean re-restore).

## The mechanism — PER_FRAME_TIME

Per-frame u32 reads at `0x8005883C` for the whole arm (`frames_T.jsonl`, one `sc` per frame):

| quantity | value |
|---|---|
| score at start → end | 0 → **1401** |
| delta frames | 1401 |
| **+1 climb frames** | **1401 (the whole gain)** |
| jumps (any delta ≠ +1) | **[] — none** |
| non-climb windows | one 32 f ready phase at the start |
| wasp-pass contribution | **0** (6 passes, all dodged) |
| flower-pickup contribution | **0 score** (+997 HP × 2, 1 caused) |

The r23 manifest note ("score climbs +1/frame during play") is now measured end-to-end: **the score is survival time**. The 1401 line — invariant across four policy families (A recipe, policy5, policy6, policy7) — is the climb-frame count of a 1500 f window, **not** a reward structure and **not** a policy deficit. Wasp passes and flowers drive nothing but the pass table and HP.

## Determinism

The exact policy5 line reproduced for the **third independent time** across processes: score 1401 / hp 5666 / 6 passes / 0 hits (R43-B arm B, R45-B arm A, R46-T). Cross-process restore determinism re-confirmed.

## The R47 lever (follows from the mechanism)

Score is time, so ≥ 1550 = **survive the climb past ~1550 frames**: `bot_policy5` verbatim at `CAP_F 1700` (extend to 1800 only if 1700 finishes with 0 hits), restore-only, cap 1. The oracle line is unchanged (score ≥ 1550 AND hits 0 AND caused ≥ 2). The real risk is not scoring but **late-game wasp density vs the guarantee planner** — the first hit past the 1500 f frontier would be the finding.

Evidence: `scratch/r46b/` (boots_used.json with the timeout-kill amendment, frames_T.jsonl with per-frame sc, metrics_r46b.json, boot_log_r46b.json). No copyrighted bytes; legal inputs only; no RAM writes.
