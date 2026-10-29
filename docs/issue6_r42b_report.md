# Round 42-B report — BuzzyBee policy-v4 dominance A/B (Issue #6)

Date: 2026-10-29 · Track: the **40% side-train** (per the user's 60/40 focus
directive: ~60% Metal Slug X / ps1ai main line, ~40% other games) · Game:
BuzzyBee (homebrew, NTSC-forced wrap) · Venue: this report + a cross-link
comment on Issue #6.

## What ran

The buzzybee capsule lever, executed exactly as recorded: **"policy-v4
(arc-checked below-side taps + fx>0 flower window) reaches dominance
(0 hits/1500f)"** — A/B **bot-v4 vs bot-A** on a gs1 savestate checkpoint,
1500f per arm, restores are not boots.

- `scripts/r42b_bot_v4.py` (single committed script; the A arm runs the
  recorded r35 bot-A recipe `bot_policy2(engage=150, margin=16,
  flower_hi=160, hover=95)` unchanged; the B arm runs `bot_policy4` =
  `bot_policy3` + one targeted fix: the below-side corrective flap's
  arc-check clears the **predicted band bottom over the whole 14f tap
  window** (max ey+43 from the bounce sim, +4 extra clearance) instead of
  the current-frame band bottom, with `engage=200` earlier commitment).
- Boot ledger `scratch/r42b/boots_used.json`: **cap 1, 1 boot used**.
  One **pre-boot abort filing corrected and disclosed** (the first
  invocation filed count=1 then crashed at `load_game` — zero emulator
  boots consumed; count reset before the real boot, per the R40 protocol).

## Environment rebuild (disclosed, both artifacts sha-verified)

The sandbox scratch cleanup had removed BOTH the r35b gs1 savestate and
the local patched disc image. Rebuilt before the boot:

1. **BuzzyBee.ps-exe re-fetched from upstream** `NDR008/BuzzyBee@master`
   (the internet-first rule): sha256
   `9b0bfc089c33d6116f2e67436254a4ced6e26275a7cac83f5f0dda95c909a8ba` —
   **byte-identical** to the r23 reference artifact the wrap script
   asserts.
2. The disc rebuilt with the committed `r23t2_ntsc_patch_and_wrap.py`:
   output sha256 `042b94bb29907e75b4eadd0699619eb770089bf8880adf31f26bcc591a1bb093`
   — **byte-identical** to the sha recorded in the buzzybee capsule
   ("patched image sha 042b94bb… local-only"). The NTSC 2-instruction
   patch disclosure (r23) carries over unchanged.
3. The gs1 checkpoint rebuilt inside boot 1 (settle 900f → START → gs1 →
   serialize → `scratch/r42b/state_r42b_gs1.bin`). It is NOT the r35b
   checkpoint frame-for-frame (different absolute timing), so cross-run
   comparisons with the r35 numbers are qualitative only; the A/B inside
   this run shares one checkpoint and is exact.

## Result: the v4 dominance hypothesis is **CONTRADICTED**

| metric (1500f cap) | A (bot-A recipe) | B (policy-v4) |
|---|---|---|
| enemy hits (−1503 edges) | **2** | **2** |
| passes / dodges | 5 / 3 | 6 / 4 |
| survival | 1500f, alive | 1502f, alive |
| score | 1401 | 1403 |
| pickups (total / caused-attributed) | 3 / 0 | 4 / 0 |
| flaps | 98 | 100 |
| hp end | 4758 | 1790 |

- Primary oracle (v4 hits == 0) **failed on both arms**: 2 hits each —
  v4 is **not dominant**; the capsule hypothesis is recorded
  **CONTRADICTED**. Secondary: v4 was not worse than A (score +2, +1
  dodge, +1 pickup) — the predictive arc-check did not hurt, it just did
  not remove the residual hit mode.
- Hit forensics (all four −1503 events in both arms' jsonl): every hit is
  the same shape — the wasp ARRIVES at contact-x (ex ∈ [−36, 32]) while
  the bee is still **inside the 56px contact band** [ey−13, ey+43], at
  low altitude (by 24–58) under a high wasp (ey 10–29). In arm B the last
  hit had `side=above` with the bee already falling back into the band
  (bvy +1024 at contact) — the side COMMIT is right, but nothing
  guarantees the bee is OUT of the predicted band by the time the wasp
  crosses ex=32.
- Pickup attribution stayed `caused=0` (pickups land while the policy is
  in dodge/hover mode, so the seek-duration attribution window misses) —
  the same accounting artifact r35 recorded; pickups are real (+997
  edges) but not attributable under this scheme.

## Next lever (recorded in the capsule as R43)

**Contact-time trajectory guarantee**: replace the reactive side-commit
with a planner — at engage time, simulate (bee gravity/tap physics ×
wasp bounce y) forward to ex=32 and choose the exit (above/below + tap
schedule) that has the bee out of the predicted band for the whole
ex ∈ [−36, 32] window; re-plan on vy-flip. Secondary: widen the pickup
attribution to "flower-mode or dodge-mode with a flower target held
within the last N frames". Tertiary: hp discipline — arm B ended at
1790 hp (2 hits) vs A 4758: hit timing, not count, drove the difference
(B's second hit came ~130f earlier), worth a per-hit frame delta metric.

Legitimacy: legal inputs only (CROSS taps + one START); savestates as
labeled diagnostic anchors; restores are not boots; no RAM writes, no
cheats; both rebuilt artifacts sha-verified against the recorded
references; no copyrighted bytes committed (the image stays local under
`emu/`, which is gitignored).

Evidence: `scripts/r42b_bot_v4.py` · `scratch/r42b/` (boot log,
frames_A/B.jsonl, metrics_r42b.json, shots) · this report.
