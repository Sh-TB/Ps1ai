# R57 Mission Review — line-by-line audit of `docs/r57_mission.md`

> Reviewer: R57 intake round, 2026-10-31, at repo state `f5a47a6`.
> Method: every section of the mission was read against the repository's
> actual R55/R56 evidence — Issue #12 comments, `data/learn/*` artifacts,
> `ps1play/learn/*` sources, and the `scripts/r53*`–`r56*` round scripts.
> Verdicts: **[OK]** verified sound · **[GAP]** unspecified, needs a
> decision before implementation · **[RISK]** plausible failure mode,
> needs a mitigation · **[FIX]** concrete change to make.
> Companion issue: the R57 autonomous-learning workstream issue
> (cross-linked from Issue #12; #12 remains the parent thread).

## 0. Verdict summary

The mission is **coherent and implementable as written**. Its diagnosis
matches the repository's own measured history: the R56 155→173 jump is
trace-sample variance, not proven autonomous learning; three mining
mechanisms regressed the clone (C2/C3/C4); teacher-DAgger at student
drift states reproduced the teacher's own failing actions; and the k210
seed (13 vs 34) is the single generalization deficit. The 20-pipe
teacher cutoff, the teacher-process-off rule, the anti-fake-exploration
rules and the full-episode rule are all enforceable with the repo's
existing machinery (five explicit modes in `ps1play/learn/modes.py`,
the subprocess brain, the AST boundary scan, the `.npz.json` provenance
sidecars).

**22 findings** were filed: 8 OK-with-notes, 9 GAPs, 5 RISKs (some
sections carry more than one). None is a blocker; every GAP has a
concrete proposed resolution that keeps the mission's constraints
intact. The consolidated list is §3; the recommended execution order,
grounded in the measured evidence, is §4.

## 1. Numeric consistency check (recomputed)

- `51 + 37 + 38 + 34 + 13 = 173` ✓ (R56 C1, matches
  `data/learn/r56_flappy_evidence.json` and the Issue #12 round comment).
- `51 + 37 + 38 + 34 + 34 = 194` ✓ (historical teacher aggregate).
- R55 champion `155 = 51/37/20/34/13` ✓ (Issue #12 R55 comment).
- "R55 student was approximately 7 KB" ✓ (R55 artifact 7,101 B; C1
  artifact 7,080 B — `data/learn/flappy_student_feat_r56_c1.npz`).
- **[FIX — minor]** Mission header says "C2 and C4 produced substantial
  regressions"; the Issue #12 evidence shows **C2 ≈ 111, C3 ≈ 107,
  C4 = 119, all vs C1 = 173** — i.e. C3 also regressed. The PART 1
  audit must record all four candidates; do not carry the header's
  incomplete summary forward.
- **[NOTE]** Both headline numbers are five-seed **aggregates**. PART 11
  itself forbids confusing aggregate sums with single-game scores; all
  R57 reporting must therefore use per-seed tables + the full statistic
  set, with aggregates shown only as historical context.

## 2. Findings by section

### Header / MISSION — READ THIS FIRST

- **[OK]** The seven stated limitations of R56 are each traceable to a
  measured result in the Issue #12 thread (variance finding, C2–C4
  regressions, k210 deficit, PPO saturation, deterministic self-imitation
  failure). Honest starting point.
- **[OK]** "The student is the actual product" — this is the correct
  product definition and matches the P0→P4 checkpoint ladder already in
  the worklogs.
- **[FIX]** PART 17 says "Use existing Issue #12. Do not create a
  duplicate Flappy issue unless a genuinely separate root problem
  exists." The owner has directed that R57 gets its own issue. Resolution
  adopted for this round: the new issue is scoped as the **R57
  autonomous-learning workstream** (teacher-off self-improvement), which
  is a genuinely separate root workstream from #12's general
  visual-learning track; the new issue cross-links #12 in both
  directions and #12 remains the parent evidence thread. No content is
  duplicated between them.

### PART 1 — Audit

- **[OK]** Sync → verify HEAD → read worklogs → read #12 → inspect
  checkpoints → provenance manifest: the right order; nothing may be
  trained before the audit.
- **[OK]** The checkpoint list matches what actually exists:
  `flappy_student_feat_p6v7h128.npz` (R55 champion recipe), C1–C4, plus
  the p5v7/p6v7/p7v7 families. The audit should also sweep the p7v7
  h128/h192 and w1–w3 variants so "any later or superior checkpoint" is
  a complete sweep, not a spot check.
- **[GAP]** "Reproduce the reported R56 C1 result if possible" — "if
  possible" is an escape hatch. **FIX:** make it a defined protocol:
  N=3 fresh boots per dev seed (k6/k30/k60/k90/k210), report per-seed
  spread. This is not overhead — it is exactly the boot-variance
  measurement PART 11 needs later, and R53–R56 showed between-boot
  variation is a first-class variable.
- **[GAP]** The manifest field list is good but incomplete.
  **FIX:** add `cutoff_frame` (frame index of the 20th visually confirmed
  passage — see PART 2), `boot_id` (R53's per-boot seed-timing variation
  makes boot identity a provenance field), `feature_version` (7 today),
  `action_contract_id`, and `emulator_core_version`.
- **[GAP]** The 20-pipe rule needs an exact cutoff definition.
  **FIX:** cutoff = the frame index at which passage #20 is visually
  confirmed; every `(observation, action)` pair with
  `frame_index >= cutoff_frame` is excluded from teacher labels —
  including the action taken on the cutoff frame itself (conservative).
  `passed_pipe_count <= 20` then becomes an assertable invariant on the
  manifest, and "Maximum pipe index represented in teacher labels" is
  the audit output.
- **[OK]** "Do not erase historical checkpoints / do not rewrite
  provenance" — consistent with the repo's append-only evidence
  discipline.

### PART 2 — Teacher bootstrap

- **[OK]** "Stop recording immediately after 20 visually confirmed pipe
  passages" + "the teacher may die before 20" — correct asymmetry: the
  cap is a ceiling, not a target.
- **[GAP]** Passage confirmation must be a single source of truth.
  **FIX:** the demonstration recorder must use the *same* visual
  passage-event detector that PART 5's reward system uses. Two detectors
  would let labels and rewards disagree — exactly the class of silent
  inconsistency PART 5's "observation provenance" rule exists to prevent.
- **[GAP]** 10–20 episodes is a range, not a protocol. **FIX:** fix 15
  episodes over ≥ 10 distinct boot/seed combinations ( TRAIN-family only
  — see PART 11 finding), record per-episode pipe count, and require
  ≥ 5 episodes to reach the full 20 (enough post-passage footage of
  ordinary successful flight without ever labeling past 20).
- **[RISK]** Teacher episode action timing must equal the evaluation
  protocol (the flappy flap is a 2-frame pulse per the r54 v4 finding;
  the runner holds STEP=2). If demos are recorded at a different cadence
  than closed-loop play, the BC learns a timing the evaluator never
  reproduces. **FIX:** one `action_contract_id` constant shared by
  collect, train and eval, asserted in a test.
- **[OK]** "Never ask the teacher to recover a student" — bans DAgger
  from bootstrap, consistent with the R55/R56 finding that teacher-DAgger
  at drift states reproduced failing actions.

### PART 3 — Bootstrap student

- **[OK]** "Do not force the bootstrap student to score 30 or 40… 10–15
  is acceptable" — honest expectation-setting; the mission's own targets
  in PART 12 then measure *post-bootstrap learning*, not bootstrap
  quality.
- **[GAP]** No model-selection rule. With only ~15 episodes, the failure
  mode is overfit. **FIX:** select the training epoch by **validation
  closed-loop median pipe count** (small fixed VAL boot budget), never by
  training loss; freeze `r57_bootstrap_bc` + sidecar manifest and treat
  it as immutable thereafter (PART 10's champion rule applies from this
  moment).
- **[OK]** "Do not reuse teacher-derived late-game knowledge under a
  different filename" — the anti-laundering rule. The repo's
  `.npz.json` sidecar convention makes it checkable: sidecar dataset
  hash must equal the qualified dataset's hash.

### PART 4 — Hard separation

- **[OK]** The disallowed/allowed lists are exact and match the R55/R56
  honest negatives (teacher-DAgger harmful; whole-tail relabels harmful —
  both stay banned).
- **[OK]** "The teacher process should be unavailable… not merely
  inactive by convention" — enforceable today: the brain already runs as
  a subprocess, and the repo has an AST boundary-scan pattern
  (`visual_only.py`, numpy+stdlib only).
- **[GAP]** Enforcement mechanics unspecified. **FIX (three layers):**
  (1) **AST layer** — the student training runner's source is AST-scanned
  for any import/call of `ps1play.learn.teacher` (the existing scan
  extended with a teacher-module denylist);
  (2) **process layer** — the student-only runner executes the brain
  subprocess with an import hook that raises on `ps1play.learn.teacher`
  import, so a violation crashes instead of silently succeeding;
  (3) **trace layer** — the runner appends `{ts, event, module}` JSON
  lines to a `no_teacher_trace.jsonl` (start, episode boundaries, end,
  hash); a test asserts the trace exists, is complete, and contains no
  teacher events. The `scripts/r54h_flappy_dagger.py` path must be
  unreachable from the R57 runner (test: import graph check).
- **[RISK]** "Record a runtime trace proving that the teacher was not
  called" is only as strong as the trace's own integrity. **FIX:** hash
  the trace file at run end and store the hash in the round's evidence
  JSON next to the model checksum.

### PART 5 — Visual-only observation and reward

- **[OK]** Allowed/forbidden input lists match `visual_only.py`'s
  boundary exactly (frames + own action history; seed identity banned as
  a feature). No drift between mission and code.
- **[OK]** "+1 for each uniquely visually confirmed pipe passage" with
  the no-duplicates requirement is the right sparse objective.
- **[GAP]** Deduplication key unspecified. **FIX:** one reward per
  `(episode_id, pipe_index)` where `pipe_index` is the tracker's
  monotonically increasing passage counter; a passage event only fires
  on a gap-crossing transition (gap ahead → gap behind at bird x), never
  on proximity. Test: replay any recorded episode, assert
  `len(rewards) == confirmed_passages` and `rewards` strictly increasing
  in pipe_index.
- **[RISK]** Sparse reward + ~7 KB policy + CPU-only is the hardest
  configuration in the mission; PPO on +1-per-pipe over thousands of
  frames may simply not move within budget. The mission already answers
  this correctly ("Start with sparse… if shaping is introduced, separate
  ablation"). **MITIGATION:** budget the shaping ablation *after* the
  ES/ARS arm (see PART 6/7 findings), and let the failure classifier
  (PART 8) — not reward shaping — be the first lever on credit
  assignment.
- **[GAP]** Observer audit names the right components but no acceptance
  threshold. **FIX:** require per-component published reliability on a
  held-out frame corpus (e.g. bird-y error p90 ≤ 2 px outside the
  overlap regime; passage false-positive rate = 0 on the replay corpus)
  and — the known hard case — a measured error profile *inside the
  pipe-overlap regime*, where R54 documented the centroid latch
  (~95–105 px frozen while the true bird falls 77→139; every color mask
  fails there, worst-16% error 76 px). Rows with observer confidence
  below threshold are dropped from training; deaths in low-confidence
  windows are classified as perception failures first (PART 8's own
  rule).
- **[FIX]** Terminal-event detection should be pinned by the same
  standard: game-over is a visual state; a test must show
  `terminal_frame` agrees with the death frame across a replay corpus,
  and that episodes end naturally (no budget-cut that silently looks like
  a death — budget exhaustion must be recorded as truncation, per PART
  6's PPO requirements).

### PART 6 — Exploration

- **[OK]** The four anti-fake-exploration rules (no argmax-then-fake-
  logprob, no temperature mismatch, no rollout/update rule change, exact
  recorded probabilities) directly close the documented R55/R56 PPO bug.
  This is the most important correctness block in the mission.
- **[RISK — Candidate A]** `p_behavior = (1-ε)·p_policy + ε·p_exploration`
  is a valid mixture, but if PPO trains on behavior-collected rollouts,
  the **old log-probability must be `log p_behavior`** (mixture
  included), not `log p_policy` — otherwise the probability ratio is
  wrong in exactly the way the mission forbids. **FIX:** store both
  `log p_policy` and `log p_behavior` per step; the PPO ratio uses the
  behavior one; a test asserts `logsumexp(log p_behavior) == 0` over
  legal actions and that a sampled action's stored probability
  reproduces the sampler's acceptance probability.
- **[RISK — exploration cost]** A random flap in flappy is often lethal;
  uniform ε destroys episode length and with it the signal. **FIX:**
  ε(s) must be concentrated in high-uncertainty gate-approach states
  (small |gap-alignment margin| or low policy margin) and ~0 in
  cruise states; cap the per-episode count of exploration actions so
  rollouts stay informative; log every exploration action with its
  ε(s) for post-hoc analysis.
- **[OK — Candidate C priority]** ES/ARS/CEM is the strongest fit to the
  measured situation: episodic, directly measurable objective (confirmed
  pipes); tiny parameter count (~7 KB policy ⇒ few hundred to few
  thousand perturbable parameters); CPU-only; and **immune to the
  saturated-logit gradient pathology** that broke the previous PPO
  attempts. R55/R56's two gradient-path failures (PPO saturation,
  weight-tuned relabel mixing) both pushed toward population search.
  **RECOMMENDATION:** run C first, B second, A as the exploration layer
  on whichever wins, D last (PART 7 ordering below).
- **[OK — Candidate D]** "Do not reintroduce teacher DAgger under another
  name" — the exact guard the evidence demands.
- **[OK]** "Investigate the actual Flappy action contract first" — and
  the contract is already measured in-repo: binary {NONE, FLAP}, flap =
  2-frame pulse, physics fitted from 45k frames (impulse −8 on the
  pulse's 2nd frame, rise decel +1.0 px/f², fall +0.125 px/f², rounded
  half-up). The contract id goes into the manifest (PART 1 fix).

### PART 7 — Choose the best learner

- **[OK]** Four controlled arms (A frozen BC / B exploration+PPO /
  C population search / D self-imitation) with equal budgets and
  "if both fail, report the blocker and preserve the best previous
  student" — honest decision rule, no algorithm idolatry.
- **[GAP]** No budget is attached to an arm. Boots are the scarce
  resource and R53+ showed they are not interchangeable (between-boot
  variation). **FIX:** fix per-arm budgets *before* starting — e.g.
  ≤ 60 training boots/arm, identical dev-seed exposure, paired seeds
  across arms, arms interleaved (not sequential blocks) so boot
  drift hits all arms equally. Declare the wall-clock/CPU budget in the
  round worklog before the first training boot.
- **[OK]** "Choose the method that produces the strongest reproducible
  student, not the method with the most impressive-looking training
  loss" — matches the repo's OBSERVED-vs-IMPLEMENTED discipline.
- **[FIX]** Execution order within the round: **C (ES/ARS) → B (correct
  PPO) → A (exploration layer on the winner) → D (self-imitation only if
  B/C produced long student lives to imitate)**. D before B/C has no
  material: R56's deterministic self-imitation had nothing new to imitate
  precisely because no autonomous long lives existed yet.

### PART 8 — Failure mining

- **[OK]** The 11-class failure taxonomy with "do not label every death
  as a wrong-action problem" is exactly right; the R54 overlap-latch
  finding proves the point (a perception failure masquerading as an
  action failure would poison the data).
- **[OK]** "If visual perception was wrong, fix perception first" — and
  the mission should name the known hard case explicitly:
  **the pipe-overlap centroid latch** (bird frozen at ~95–105 px while
  the true bird falls 77→139; every color mask fails; the same-tier
  teacher survives only by never entering the regime). The two already
  proposed levers — per-column green-profile template matching, or a
  tiny learned CNN observer — both stay frames-only and should be the
  FIRST perception workstream of R57, because every student deviation
  enters the overlap regime.
- **[RISK]** "Try alternative legal action sequences… add successful
  outcomes to student-generated data" is *close to* the machinery that
  failed three times in R55/R56 (whole-tail relabels 140→91 at weight 3,
  123 at weight 1; risky-lookahead labels spurious; surgical flips
  C4 = 119 vs C1's 173). The failure mode was: mined labels teach a
  second flight style that interferes with the cloned behavior.
  **FIX:** mining in R57 (a) uses **student** deaths only (never teacher
  tails), (b) is gated by closed-loop validation *before* champion
  promotion (the regression gate of PART 10), (c) enters training at
  small weight with an explicit ablation arm, and (d) prefers the
  PART 6 population search — which explores alternatives *in behavior*,
  not in labels — over more relabeling. If mining is tried, it is arm D+
  with its own accept/reject verdict, never merged silently.
- **[GAP]** Counterfactual continuation needs a determinism protocol.
  **FIX:** same boot, identical input prefix replayed to frame T, branch
  at T, n=3 repeats (boot nondeterminism is documented); the sim lab
  (`scripts/r55k_sim_lab.py` precedent, zero boots) may *propose*
  candidates, but survival is only recorded when a real emulator run
  shows it — as the mission already requires.

### PART 9 — Full episodes

- **[OK]** "Student episodes are NOT capped at 20"; no restart at 20; no
  score reset; main score = confirmed passages in a full episode. The
  teacher's 20-pipe limit must never leak into the student's episode
  terminator — a test should assert the student runner has no
  passage-count-based termination at all.
- **[GAP]** The frame budget is left undocumented. **FIX:** derive it
  from measured cadence — R53–R55 traces put ~30 pipes at ≈ 4,400–4,400+
  frames of play, i.e. roughly 145 frames/pipe including intro; 50 pipes
  ⇒ ≈ 7,300 frames. Set the full-episode budget at **10,000 frames**
  (≈ 2× the 50-pipe estimate, headroom for the k210-style slow cadence)
  and record the exact value in the runner config + every episode
  record. Budget exhaustion is truncation, never reported as death.

### PART 10 — Anti-forgetting

- **[OK]** Balanced experience (early/mid/late states), immutable
  champion, regression gate. The R55 w1–w3 weight experiments are the
  precedent: unbalanced mixing *measurably* degraded the clone — the
  gate is not paranoia.
- **[GAP]** "Statistically compatible" is not defined. **FIX:** numeric
  gate before any champion replacement: VAL median not worse by more
  than 2 pipes AND no single dev seed worse by more than 5 AND
  10-pipe survival rate not down more than 10 points, evaluated on the
  fixed VAL boots with n=3 repeats. If a trade-off is intended, it is
  documented and separately approved — as the mission says.
- **[OK]** "Do not merely increase model size" — the ~7 KB reference
  stays the budget (PART 14).

### PART 11 — Splits

- **[OK]** TRAIN/VAL/TEST with all R55/R56 seeds as dev/VAL, ≥ 20 unseen
  TEST seeds, per-seed reporting, full statistic set, and the "never
  confuse the sum of multiple runs with a single-game score" rule.
- **[GAP]** Split membership must be fixed *before* PART 2 collection,
  or teacher demos can silently contaminate TEST. **FIX:** commit the
  seed list file (train/val/test ids) in the first R57 commit; the
  bootstrap collector refuses boot seeds not in TRAIN; a test asserts
  disjointness.
- **[FIX]** TEST seeds must be **retired** after the final evaluation —
  never trained on, never used for model selection in any later round,
  otherwise they become dev material by attrition. Record the retirement
  in the worklog.
- **[GAP]** Repeat protocol for boot nondeterminism. **FIX:** n=3 boots
  per TEST seed, fixed in advance, report per-seed median-of-3 (and the
  spread), so "repeat cases when boot nondeterminism requires it" cannot
  become "repeat until the number looks good."
- **[OK]** k6/k30/k60/k90/k210 formally demoted to VAL — this ends the
  round-over-round reuse of the same five numbers as "generalization."

### PART 12 — Targets

- **[OK]** Ladder 20 → 30 → 40 → 50 with "goals, not permission to
  fabricate," and the requirement to name the blocker category if 30 is
  not reached. Context check: the teacher's five-seed aggregate 194
  (mean ≈ 38.8) and C1's median 34 mean the *first* target (median 20 on
  NEW seeds) is deliberately below the dev-champion level — the right
  design, because it must be hit by post-bootstrap learning on unseen
  seeds, not by cloning.
- **[NOTE]** "Evidence that post-bootstrap learning caused improvement"
  is the actual scientific claim of R57. **FIX:** pre-register the
  comparison: bootstrap BC vs final student, same TEST protocol, plus
  the frozen C1 reference — improvement = TEST median increase with the
  regression gate still satisfied, not a lucky single episode (PART 6's
  paired-seed rule).

### PART 13 — Real-game validation

- **[OK]** Emulator as final authority; simulator/synthetic/offline
  explicitly disqualified; five-way comparison including "Teacher,
  limited to its first 20 pipes only" with uncapped teacher numbers
  allowed only as historical context. This is the honest framing.
- **[OK]** Evidence pack (screenshots, traces, actions, passage evidence,
  death frames, checksums, frame budget, per-seed score) matches the
  repo's existing evidence-JSON discipline (`data/learn/r5x_*_evidence.json`).

### PART 14 — Performance and portability

- **[OK]** 7 KB reference (R55 = 7,101 B), artifact size + parameter
  count + latency + dependencies + checksum recorded; no GPU/paid
  API/online teacher; deployment chain = frames → features → small model
  → legal actions → game.
- **[RISK]** ONNX export adds a runtime dependency the repo currently
  does not need (deployment today: numpy + stdlib, AST-scanned).
  **FIX:** ONNX stays optional exactly as written, but the acceptance
  bar should be stated: adopt only if native and ONNX outputs agree to
  float tolerance *and* a consumer exists; otherwise file the native
  numpy path as the deployment artifact and mark ONNX PENDING — "do not
  claim portability just because an ONNX file exists" already says this.

### PART 15 — Automated tests

- **[OK]** The test matrix covers teacher cutoff, bootstrap purity,
  student isolation, exploration validity, reward dedup, provenance
  splits, resume, and the full existing regression suite. Mapped to
  concrete files, the suite extension is:
  `test_r57_teacher_cutoff.py` (no label ≥ cutoff_frame; early-death
  episodes), `test_r57_no_teacher.py` (AST denylist + import-hook
  crash + trace integrity), `test_r57_reward.py` (dedup, no RAM path,
  truncation≠death), `test_r57_exploration.py` (probability
  reconstruction, mixture normalization, behavior-logprob ratios),
  `test_r57_splits.py` (disjoint seeds, retired TEST), plus the existing
  `test_learning_boundary` extended to the student training runner.
- **[OK]** "Passing tests alone does not prove learning" — the correct
  epistemic order.

### PART 16 — Automation

- **[OK]** Runner supports bootstrap loading, teacher-disabled mode,
  rollouts, visual rewards, learner selection, checkpointing, champion
  preservation, resume, machine-readable results, per-episode traces.
- **[FIX]** Add two operational rules: (1) trace/schema versioning in
  every artifact (episode records and manifests carry a `schema`
  field), and (2) the key-frame list (first passage, 10/20/30/40/50,
  exploration events, deaths, observation failures) is written into the
  episode record's `keyframes` index, not a separate ad-hoc dump, so
  failure analysis can find them programmatically.

### PART 17 — GitHub and worklog

- **[OK]** Status labels (IMPLEMENTED/TESTED/OBSERVED/PARTIAL/BLOCKED/
  PENDING/SUPERSEDED), English technical docs, preserve historical
  evidence, verify the remote commit by reading it back — all match the
  standing repo discipline.
- **[FIX]** The issue split adopted for this round (owner-directed): a
  **new issue** carries the R57 autonomous-learning workstream; #12
  remains the parent thread and receives a cross-link comment, not
  duplicated content. R57 results still land in both places: evidence
  comments on #12 per its convention, workstream status on the new
  issue.

### PART 18 — Autonomous execution

- **[OK]** Standard honesty clauses; "do not spend most of the round
  improving the teacher" is the right priority guard (the teacher is
  done — 194 aggregate, verified twice).
- **[OK]** "Do not declare success based on code completion" — this is
  the clause that separates R57 from R56's variance confound.

### FINAL DELIVERABLES

- **[OK]** All 28 items are collectible from the repo's existing artifact
  conventions (evidence JSONs, sidecar manifests, worklog, issue
  comments). Items 6/7/8 (cutoff proof, teacher-off proof, RAM audit)
  are backed by the PART 4/15 enforcement machinery; item 16 (20 unseen
  test results) is the only budget-sensitive item and is correctly
  qualified "if feasible."
- **[FIX]** Add item 29: **boot-variance record** (the PART 1
  reproduction protocol output), since every cross-round comparison now
  depends on it.

## 3. Consolidated findings

| # | Section | Verdict | One-line resolution |
|---|---------|---------|---------------------|
| 1 | Header | FIX | New R57 issue = separate workstream; #12 cross-linked, remains parent |
| 2 | Header/§1 | FIX | Record C2≈111, C3≈107, C4=119 in the audit (header's "C2 and C4" is incomplete) |
| 3 | PART 1 | GAP | C1 reproduction = defined protocol (3 boots/seed, spread reported) |
| 4 | PART 1 | GAP | Manifest += cutoff_frame, boot_id, feature_version, action_contract_id, emulator version |
| 5 | PART 1 | GAP | Exact cutoff definition; exclude frame ≥ cutoff_frame incl. cutoff action |
| 6 | PART 2 | GAP | Passage detector = the same one used for rewards (single source of truth) |
| 7 | PART 2 | GAP | 15 episodes, ≥10 boots, ≥5 reaching 20; TRAIN seeds only |
| 8 | PART 2 | RISK | One action_contract_id shared by collect/train/eval (2-frame flap pulse) |
| 9 | PART 3 | GAP | Model selection by VAL closed-loop median; bootstrap checkpoint immutable from birth |
| 10 | PART 4 | GAP | 3-layer teacher-off enforcement: AST denylist + import-hook crash + hashed trace |
| 11 | PART 5 | GAP | Reward dedup key (episode_id, pipe_index); crossing-transition only |
| 12 | PART 5 | GAP | Observer acceptance thresholds incl. the overlap-latch regime |
| 13 | PART 6 | RISK | PPO ratios use log p_behavior (mixture), stored alongside log p_policy |
| 14 | PART 6 | RISK | ε(s) concentrated in uncertain gate-approach states; per-episode exploration cap |
| 15 | PART 7 | GAP | Fixed per-arm boot budget; arms interleaved, paired seeds |
| 16 | PART 8 | RISK | Mining = student deaths only, small weight, gated, separate arm (3 prior failures) |
| 17 | PART 8 | GAP | Counterfactual replay protocol: same boot, branch at T, n=3 |
| 18 | PART 9 | GAP | Frame budget = 10,000 frames; truncation ≠ death, recorded as truncation |
| 19 | PART 10 | GAP | Numeric regression gate (median −2 / seed −5 / survival −10pts, n=3) |
| 20 | PART 11 | GAP | Seed list committed before collection; TEST retired after use; n=3 fixed |
| 21 | PART 14 | RISK | ONNX optional with stated acceptance bar; native numpy remains deployment |
| 22 | Deliverables | FIX | += item 29: boot-variance record |

## 4. Recommended execution order (evidence-grounded)

1. **P0 audit + splits (no boots for training):** checkpoint/dataset
   provenance sweep, seed-list commit, manifest schema, C1 reproduction
   protocol. *(PART 1, 11)*
2. **P1 bootstrap collection + clean BC:** 15 capped teacher episodes;
   `r57_bootstrap_bc` selected on VAL; cutoff + purity tests green.
   *(PART 2, 3)*
3. **P2 teacher-off machinery:** the three enforcement layers + trace;
   runner runs with teacher import impossible. *(PART 4, 15)*
4. **P3 learner arms, C first:** ES/ARS on the frozen bootstrap (immune
   to the saturated-logit pathology; episodic objective is exactly its
   input), then correct-PPO with the mixture-logprob fix, then the
   confidence-aware exploration layer on the winner, self-imitation last
   and only if long student lives exist. Fixed per-arm budgets;
   interleaved paired boots. *(PART 6, 7)*
5. **P4 perception:** the overlap-latch fix (template matching or tiny
   CNN observer, frames-only) — prerequisite for any 30+ median, since
   every post-pipe-20 deviation enters the overlap regime. *(PART 5, 8)*
6. **P5 final evaluation + promotion:** numeric regression gate, 20 TEST
   seeds × 3 boots, five-way comparison, evidence pack, issue + worklog
   + verified push. *(PART 9–13, 17)*

## 5. Relationship to Issue #12

Issue #12 is the FlappyBirdPSX visual-learning parent thread and keeps
its history (teacher tier 194; C1 = 173; the honest negatives). The new
R57 issue owns the autonomous-learning workstream defined by the
mission: 20-pipe bootstrap, teacher-off learning, exploration validity,
the learner bake-off, and the unseen-seed evaluation. Both issues are
cross-linked; no evidence is duplicated — #12 links to the R57 issue for
workstream status, the R57 issue links to #12 for historical evidence.
