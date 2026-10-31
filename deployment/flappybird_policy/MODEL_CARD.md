# MODEL CARD — r59_soup_e6a010 / r60_soup_e6a010.onnx

## Model identity

| field | value |
|---|---|
| game | FlappyBirdPSX v0.1.0 (IcePanorama, Unlicense) |
| architecture | MLP 10 → 128 → 2, ReLU; 1,466 float32 params (7,182 B ONNX) |
| classes | `[HOVER, FLAP]` (argmax first-max; ties → HOVER) |
| checkpoint | `data/learn/r59_soup_e6a010.npz` (sha256 `72c79f30…`) |
| ONNX artifact | `data/learn/r60_soup_e6a010.onnx` (sha256 `4dd592a7…`, opset 17, IR 8) |
| provenance | soup: `r58_dir2p_true + 0.10 * (r58_si_v2_e6 − r58_dir2p_true)` — a convex combination of two self-imitation checkpoints; NO new training at the soup step |
| lineage | R53–R56 BC/DAgger/mining → R57 20-pipe teacher-capped bootstrap + ARS → R58 self-imitation + provenance forensics → R59 linear-path soup → R60 ONNX export |
| training data | teacher demonstrations capped at 20 visually confirmed pipes per episode + student self-generated lives (teacher-off, hashed no-teacher traces) |
| input | RAW v7 decision vector (10 float32) — see INTERFACE.md |
| output | logits [N,2] + action_idx [N] int64 |

## Intended use

Driving FlappyBirdPSX through a legal-input emulator adapter, one
decision per emulated frame, from rendered frames only. The decision
function is this ONNX graph; the perception (frames → 10 features) is
the host adapter documented in INTERFACE.md.

## Performance (verified, real emulator, budget 10,000 frames)

- Family (VAL, 7 seeds, exact reproduction every round):
  k6 87-alive, k12 76@8798, k30 37@4401, k45 40@4753, k60 87-alive,
  k90 68@7895, k210 42@4966.
- R59 fresh TEST (20 unseen seeds × n=3, retired after use): mean 57.55
  vs base 53.65 vs C1 55.00; median 52.5; min 24. Aggregate-level win.
- R61 fresh validation (30 NEW unseen seeds, n=2): mean 52.30
  (base 46.87, C1 53.37); median 48.0; min 10; alive-at-budget 6/30.
  vs base W/T/L 6/23/1; vs C1 7/11/12 — **C1 and the champion are
  statistically comparable on this split; the champion strictly
  dominates its own base.** Per-seed results are heavy-tailed; no
  universal-superiority claim is made.

## Out-of-scope uses

- Any other game (including hello_pong — a separate policy; its
  regression is a gate, not evidence of generalization).
- Real-time guarantees (the emulator is frame-driven; wall-clock
  timing is not part of any claim).
- Human-facing safety contexts. This is a research artifact for a
  homebrew game.

## Honest limitations

See KNOWN_LIMITATIONS.md (perception latch class, heavy-tailed seeds,
host-side perception dependency, float32-CPU parity scope).
