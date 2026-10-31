# R59 Execution Report — the linear-path soup: a family-dominant
# candidate, an aggregate TEST win, and the honesty of heavy tails

> Round R59-continue, 2026-10-31, Issue #13 (the R57 workstream
> continued). Base `d5b6c52` (the R58 head). Primary: FlappyBirdPSX;
> hello_pong regression re-verified. All gameplay numbers are REAL
> emulator measurements (Beetle PSX 0.9.44.1 + OpenBIOS; the
> FlappyBirdPSX v0.1.0 ISO re-fetched after the sandbox recycle,
> sha256 `b45871d3…` manifest-verified). Budget 10000 frames. No RAM
> anywhere in the student pipeline (AST-scanned, import-blocked, hashed
> `no_teacher_trace` per process). hello_pong regression: **PASS**
> (exact R54 reproduction).

## The question this round answers

R58 ended on a thrice-replicated structural finding: the base
`r58_dir2p_true` is a **sharp local optimum** — every tested one-shot
weight move (ARS directions, sibling directions, SI fine-tunes) either
did nothing or collapsed one of the razor-edges (k6/k60 87-alive).
R59 tests the one move class never tried: **the linear path**
`θ(α) = (1−α)·base + α·cand` between two working checkpoints — a 1-D
family of soups, not a single point.

## R59-A: the path probe (real emulator, in-process proven path)

Razor seeds k6/k60 first, then the gain seeds; every episode
teacher-off with a hashed trace.

**e4 path (`r58_si_v2_e4`, |u| = 0.785): NO soup point.** The gains
(k12→87-alive, k45→47) exist only near α = 1, while both razor-edges
die by α = 0.5 (k6 63, k60 14); k45 even dips 33→30 at α = 0.25. The
gains and the collapses live in the same narrow region — the path
crosses the basin boundary before it pays.

**e6 path (`r58_si_v2_e6`, |u| = 1.025): SOUP POINT at α = 0.10.**
Full family, deployed path (BrainClient), VAL seeds n = 3 boots:

| seed | base | **r59_soup_e6a010** | Δ |
|---|---|---|---|
| k6 | 87 alive | **87 alive** (640 flaps) | 0 |
| k12 | 76 @8798 | 76 @8798 | 0 |
| k30 | 37 @4401 | 37 @4401 | 0 |
| k45 | 33 @3957 | **40 @4753** | **+7** |
| k60 | 87 alive | **87 alive** (640 flaps) | 0 |
| k90 | 68 @7894 | 68 @7895 ×3 | 0 |
| k210 | 42 @4966 | 42 @4966 ×3 | 0 (exact) |

**The candidate strictly dominates the base on the family.** The
regression gate passes with zeros (VAL median Δ 0 ≤ 2; max drop
0 ≤ 5; 10-pipe survival unchanged). The path map around the point is
measured too: k210 collapses between α = 0.10 (42 @4966 — the base's
exact death frame) and α = 0.15 (18 @2260); the k12→87-alive gain
arrives only by α = 0.25 (where k210 is already dead). α = 0.10 is the
max-gain point with margin — and the R58 k45 −1 vs the teacher is
**closed** (40 vs 34).

## The fresh TEST (pre-registered, then measured)

Split committed BEFORE collection (`21f3e0d3`, read-back verified):
multiples-of-4 rule, every prior use excluded (r53–r56 history, R57 +
R58 TEST, R58/R59 dev). 20 unseen seeds × (candidate n=3 + 2 refs n=1)
= **100 episodes**, every rep byte-identical.

| model | mean | median | min | ≥40 | ≥50 | ≥85 |
|---|---|---|---|---|---|---|
| **r59_soup_e6a010** | **57.55** | **52.5** | **24** | 14 | **11** | 5 |
| base (r58 champ) | 53.65 | 49.0 | 10 | 13 | 10 | 3 |
| C1 (frozen R56) | 55.00 | 49.5 | 0 | 14 | 10 | **6** |

Paired: **+3.90 vs base** (W/T/L 2/15/3) and **+2.55 vs C1**
(W/T/L 4/11/5). The honest shape of these numbers:

- **15/20 seeds are byte-identical to the base.** The soup is the base
  almost everywhere.
- The 5 divergent seeds swing **both ways**: k64 37→85 (+48), k76
  10→87-alive (+77) — but k80 62→36 (−26), k140 73→55 (−18), k56 −3.
  vs C1: k88 is C1's 0-catastrophe vs the soup's 87 (+87), k136/k140/
  k124 +25…+37 — but k44 −47 (C1 87), k80 −42 (C1 78), k148 −25.
- So the round's claim is **aggregate-level**: mean, median and floor
  improve against BOTH references. It is **not** per-seed reliability —
  a 0.10-norm weight move acts as a butterfly trigger on branch-prone
  lives, and the tails are heavy in both directions.

**Promotion**: `r59_soup_e6a010` is the R59 champion — every
pre-registered gate passes (family strict dominance; VAL untouched)
and all three TEST aggregates favor it. Disclosed with the promotion:
the weak per-seed evidence, C1's alive-depth edge (6 vs 5 seeds ≥85),
and that the family's +7 did not generalize as per-seed dominance.

## hello_pong regression — PASS

The R54 head-to-head re-run verbatim (artifact re-fetched through the
documented r12 procedure, zip+bin sha256 verified): teachers v1/v2
**7 scored / 0 conceded** each, student `pong_student_feat_p4d4`
**8 scored / 2 conceded** — the exact R54 record; the student still
outscores both teachers (8 vs 7).

## Honest limitations

- The TEST advantage is aggregate-level; the paired per-seed evidence
  is weak (2W/3L vs base, heavy tails both directions). A conservative
  stance (keeping the base as champion) is defensible; the promotion
  follows the same aggregate rule that promoted the R58 champion.
- The razor-edge 87s are unchanged by design (byte-identical), i.e.
  still razor-edges.
- ONNX export remains PENDING (native numpy is the deployment per the
  review bar).
- The R59 TEST seeds are retired after this round, per protocol.

## Reproduction

```
python3 scripts/r59a_linpath.py --cand data/learn/r58_si_v2_e6.npz \
    --alphas 0.1 --seeds 45            # the +7 probe
python3 scripts/r57h_eval.py --model data/learn/r59_soup_e6a010.npz \
    --seeds 45,60 --reps 1 --budget 10000
python3 scripts/r59b_test.py --seconds 480   # fresh TEST (resumable)
python3 scripts/r59c_stats.py                # the TEST statistics
python3 scripts/r54c_pong_eval.py --tag r59regress_s --agents feat \
    --dagger 0 --feat-art data/learn/pong_student_feat_p4d4.npz
```

Evidence: `data/learn/r59_flappy_evidence.json` ·
`data/learn/r59_seed_splits.json` · `data/learn/r59_linpath_results.json`
· scripts r59a–r59e · worklog entry R59-continue.
