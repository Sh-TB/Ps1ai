# R66 GAMEPLAY RESULTS — the real product-path runs

Round: **R66** · Evidence:
`data/games/SLUS-01212/truck_evidence/r66/r66_product_run.json`,
`data/games/SLUS-01212/truck_evidence/r66/product_run/` (episode
records + screenshots), `reports/r66/R66_ACTIVE_EXECUTION_PATH.md`.

## 1. What ran

The REAL product path — the registered plugin, the package policy, the
real emulator, legal controller inputs, read-only observation, no RAM
writes, no runtime LLM, no save-state rewinds:

```bash
python3 -m ps1play play metal_slug_x --episodes 2 --max-frames 10000 \
    --verbose --screenshot --output data/r66          # run 1
python3 -m ps1play play metal_slug_x --episodes 2 --max-frames 10000 \
    --output /tmp/r66_rep                             # run 2 (determinism)
```

Preflight verified the disc pin (`45cde149…`, serial SLUS-01212), the
core (`effff7bb…`) and the OpenBIOS BIOS before boot. Boot → ready →
2 episodes per run.

## 2. Results (byte-identical across the two runs)

| episode | result | frames | score max | actions | death scene |
|---|---|---|---|---|---|
| ep1 k=6 | death (game_over) | 1666 | **1100** | 87 | the armored-truck encounter |
| ep2 k=12 | death (game_over) | 388 | **1300** | 13 | re-entry death |

* Determinism: run 2 reproduced run 1's outcome metrics exactly
  (same frames, scores, action counts) — the deterministic rules
  policy on the deterministic emulator.
* The player advanced the world from the spawn (px 258.6) to the truck
  zone (**px ~1164** at the 1200-frame status line); the score rose
  0 → 1100 → 1300 through real payments (the +100/+500/+1000 classes
  the R48-R66 telemetry documents).
* The death screenshot (`product_run/shots/ep001_k6_end_death.png`)
  shows the truck encounter: the armored truck at the roadblock, two
  soldiers, score 1100, the PRESS START banner — the SAME blocker the
  R38-R52 workstream documented, now reproduced through the product
  path.

## 3. Mission-1 completion status

**NOT cleared — and not claimed.** The furthest VERIFIED product-path
milestone: the truck encounter zone (px ~1164) with real score
payments. The TAINTED-lineage experiment frontiers (px 1224.9 / 1254.8,
6 continue-rescues — labeled, never a clean claim) remain the
furthest-recorded postures. The next concrete blocker: the truck fight
itself (the R38-R52 evidence: hp_a4 300, grenades −100 each, the
grenade sequencing + soldier prioritization the current policy does
not do).

## 4. Legality ledger (per-claim)

| rule | this run |
|---|---|
| legal PS1 controller inputs only | YES (RIGHT/Y/B/A/START mappings; `tests/test_r66_msx_adapter.py::TestAdapterContract`) |
| GameShark / cheats / RAM writes / freezing | ZERO (the adapter reads; nothing writes) |
| runtime LLM calls | ZERO (the policy is a deterministic rule set) |
| new RL / training | ZERO |
| screenshot pixels as policy input | ZERO (screenshots are evidence only; the policy consumes RAM-read observations) |
| save-state rewinds in claimed play | ZERO (the adapter never touches save states) |

## 5. Performance (Phase 14 measurement)

* boot → ready: ~29 s wall (the env probe; the engine budget is 60 s
  with 2 retries).
* Decision-loop throughput: ep1 = 1666 frames in 9.6 s wall
  (~174 fps effective incl. per-frame capture at 0.4 ms).
* Perception latency: ~0.4 ms/frame (frame capture EMA); policy
  latency: sub-millisecond (the rules are O(5) over the packed
  entities).
* The highest-cost diagnostic step historically was blind boot
  spending; the R66 ledger + dry-run discipline kept this round to
  FOUR experiment boots for two primary experiments.
