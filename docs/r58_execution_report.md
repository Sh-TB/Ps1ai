# R58 Execution Report — provenance forensics, the plateau, and the fresh-TEST win

> Round R58-continue, 2026-10-31, Issue #13 (the R57 workstream continued).
> Base `81b7954` (the R57 worklog entry). Primary: FlappyBirdPSX. All
> gameplay numbers are REAL emulator measurements (Beetle PSX 0.9.44.1 +
> OpenBIOS, the FlappyBirdPSX v0.1.0 ISO re-fetched after the sandbox
> recycle, sha256 `b45871d3…` verified, license sectors present).
> Budget 10000 frames. No RAM anywhere in the student pipeline
> (AST-scanned, import-blocked, hashed `no_teacher_trace` per process).
> Full suite: **638 passed + 2 skipped + 1 xfailed**.

## The headline

**`r58_dir2p_true.npz` (7,090 B) is the new champion — provenance-clean
by construction and genuinely beyond both the R57 champion and the
frozen C1 on 20 never-used TEST seeds** (mean **53.35** / median **51.0**
/ floor 10; C1: 47.65 / 40.0 with a 0-pipe catastrophe; the R57
champion: 42.25 / 36.5). Paired per-seed deltas: **+11.1 vs the R57
champion (W/T/L 8/8/4), +5.7 vs C1 (8/7/5)**. The champion's n=3 reps
are byte-identical on all 20 seeds.

## The forensic finding (honest correction of the R57 record)

The saved `r57_es2_dir2p.npz` is **NOT** the theta it was recorded as
(the iter-0 dir-2-plus ARS sample):

1. **Path equivalence first** — before doubting anything, the replay
   experiment (r58b) proved the in-process FlatPolicy and the deployed
   BrainClient produce **0/7345 action mismatches** on the champion's
   recorded k6 life, and k72=87 / k195=87 reproduce byte-exactly today.
   The decision paths were never the problem.
2. **The theta is wrong** (r58e): champion − si_v1 has norm 2.08 (one
   ARS step is 1.21), cosine 0.56 vs δ₂, and only **32.7% of its energy
   inside span{iters 0..4 directions}** (55° off). The saved weights
   cannot be any combination of the recorded ARS streams — a save
   incident whose cause is lost with the wiped scratch state.
3. **Recovery** (r58f): the true candidate is offline-reconstructable
   from committed artifacts (si_v1.npz + 0.03·δ₂, the committed r57f
   seeded stream). The reconstruction scores **EXACTLY the recorded
   pair: k6=87 and k60=87, both budget-alive @10000, 640 flaps each** —
   the r57 87/87 claim was real; only the save was wrong.

**What survives from R57**: all 24 published TEST numbers (deployed-path
measurements that reproduce exactly today), the bootstrap → si_v1
lineage claims, the PART 12 causality. **What is SUPERSEDED**: the
champion-checkpoint provenance (downgraded to UNKNOWN-beyond-si_v1) and
the champion k6=87/k60=87 claims (they belong to the true candidate;
the mis-saved npz measures 63 and 80@9253).

## The k210 deficit is closed — it belonged to the mis-save

Family re-validation (fresh boots, this round):

| seed | 6 | 12 | 30 | 45 | 60 | 90 | 210 |
|---|---|---|---|---|---|---|---|
| **r58_dir2p_true** | **87 alive** | 76 | 37 | 33 | **87 alive** | 68 | **42** |
| r57_es2_dir2p (mis-saved) | 63 | 87 alive | 37 | 30 | 80 | 68 | 13 |
| teacher refs | 51 | 38 | 37 | 34 | 38 | 34 | 42 (diag) |

The "k210 deficit (13–16 vs teacher 34)" — the round's named open
blocker — was a property of the mis-saved theta. The corrected base
reaches **teacher-level 42 on k210** (its death step 4966 vs the
teacher's diagnostic 4968). Against the teacher the base now meets or
beats 6 of 7 family seeds; k45 (33 vs 34) is the single −1.

## ARS round 2: exhausted (honest structural negative)

Fitness = mean(k90, k210)@10000, init = the corrected base, with
**save-at-selection** (the r57 lesson hard-wired: the candidate npz is
written in the same block as its fitness).

- Iter-0: **zero** of 12 perturbed rollouts exceeded the base fitness
  55; the entire update signal came from collapses. The candidate
  gated **k60 87→29** (catastrophic) with k90/k210 unchanged — REJECTED.
- The sibling sweep (r58g): ALL es2 iter-0 siblings reconstructed
  offline and measured — **6/12 exactly INVARIANT** (68/42), **6/12
  collapse** (k210→13/16/18, k90→43), **none better**. The base is a
  collapse plateau at σ=0.03.

## Self-imitation round 2: rejected by the gate, insight preserved

Fine-tuning the base on its own three lives (k6 87a + k60 87a + k12 76;
28,798 rows; the r57 arm-D recipe verbatim; epochs 4/6/8/15/25):

- e4: k12 76→**87 alive**, k45 33→**47** — but k60 87→**14**. REJECTED.
- e6: k45→44 — k60 87→29, k90 68→41. REJECTED.
- e8: k45→44 — k6 87→76 (−11 > 5). REJECTED.
- e15/e25: k90 68→41/43. REJECTED.

Every fine-tune trades the fragile 87s for mid-depth gains. Across
**three independent levers** (ARS directions, sibling directions, SI
gradients) the same structure appears: the base's 87-alive trajectories
are razor-edges, and no tested one-shot weight movement improves the
policy without collapsing one of them. The base is a sharp local
optimum — a genuine characterization of this policy landscape, and the
reason the round's artifacts stop here.

## The fresh TEST (the round's decisive evidence)

`data/learn/r58_seed_splits.json` committed BEFORE collection
(`fd1c1422`, read-back verified): 20 unseen seeds (9…219, the
multiples-of-3 rule, every prior use excluded), champion n=3,
references n=1, 100 episodes.

| model | mean | median | min | ≥40 | ≥50 |
|---|---|---|---|---|---|
| **r58_dir2p_true** | **53.35** | **51.0** | 10 | 12 | **10** |
| C1 (frozen R56 ref) | 47.65 | 40.0 | **0** | 10 | 6 |
| r57_es2_dir2p | 42.25 | 36.5 | 10 | 9 | 7 |

The champion wins the mean, the median, the floor, and the depth tail
against both references on seeds none of them ever saw. C1 keeps 5
paired seed wins — the champion is not uniformly dominant, and that is
disclosed.

## Limitations

- The r57 save incident's root cause is unknown (the scratch state that
  held the ARS loop was wiped by the sandbox recycle); the incident is
  mitigated structurally (save-at-selection) but not explained.
- k45 33 vs the teacher's 34; the 87-alive razor-edges; C1's 5 paired
  wins; ONNX still PENDING (native numpy is the deployment).
- The teacher k210=42 comes from this round's ASSISTED diagnostic
  (4968-step life); the r56-era teacher k210=34 was a 4000-frame
  measurement — both disclosed, not comparable directly.

## Reproduction

```
python3 scripts/r58b_path_divergence.py      # 0/7345 mismatches
python3 scripts/r58e_provenance_theta.py     # the break, offline
python3 scripts/r58f_reconstruct_dir2p.py    # rebuild the true candidate
python3 scripts/r57h_eval.py --model data/learn/r58_dir2p_true.npz \
    --seeds 6,60 --reps 1 --budget 10000     # 87/87 budget-alive
python3 scripts/r58i_test.py --seconds 480   # fresh TEST (resumable)
python3 scripts/r58j_stats.py                # the TEST statistics
```
