# R57 MASTER MISSION — THE STUDENT MUST LEARN BEYOND THE TEACHER

> Canonical verbatim intake text of the R57 mission (owner-provided,
> 2026-10-31). Committed unchanged so that `docs/r57_mission_review.md`
> and the R57 issue can reference a stable in-repo text.
> Repository: Sh-TB/Ps1ai. Primary game: FlappyBirdPSX. Regression game:
> hello_pong. Existing GitHub issue: #12 Flappy, #11 Pong. Previous
> completed round: R56. Previous reported commit: f5a47a6.

    STRICT BOOTSTRAP → AUTONOMOUS SELF-PLAY → SELF-IMPROVEMENT

## MISSION — READ THIS FIRST

R56 improved the reported Flappy score from 155 to 173 aggregate pipes
across five seeds.

Reported R56 C1:

    k6   = 51
    k30  = 37
    k60  = 38
    k90  = 34
    k210 = 13

    Total = 173

Historical teacher comparison:

    51 / 37 / 38 / 34 / 34 = 194

R56 also exposed important limitations:

- The new 173 result was not proven to be caused by autonomous student
  learning.
- Fresh traces and between-boot variation contributed to the observed
  difference.
- Some mining corrections damaged the cloned behavior.
- C2 and C4 produced substantial regressions.
- The k210 generalization gap remains.
- The previous PPO experiments suffered from policy saturation and
  action-distribution problems.
- Self-imitation did not independently discover new behavior under
  purely deterministic action selection.

R57 must address the actual learning problem.

## THE PRODUCT WE WANT

A small game-playing student that:

1. Receives limited initial instruction from a teacher.
2. Learns the basic visual rules.
3. Stops receiving teacher actions and teacher labels.
4. Plays the real game independently.
5. Discovers strategies through its own experiments.
6. Learns from its own successes and failures.
7. Continues improving beyond the teacher's demonstrated skill.
8. Eventually reaches 30, 40, 50 or more pipes without needing the
   teacher.

The teacher is NOT the permanent trainer. The teacher is NOT allowed to
define the student's ceiling. The teacher is NOT an oracle for difficult
student states.

The student is the actual product.

## PART 1 — AUDIT THE EXISTING R55/R56 MODELS AND DATA

Before training anything:

1. Synchronize with remote and verify the actual HEAD.
2. Confirm R56 commit f5a47a6.
3. Read the full R55 and R56 worklogs.
4. Read Issue #12 and its latest comments.
5. Inspect all policy checkpoints and model artifacts.
6. Inspect every training dataset used by R55/R56.
7. Identify the exact provenance of every label.
8. Reproduce the reported R56 C1 result if possible.

Important checkpoints and candidates to inspect:

- R55 p6v7h128 BC-only.
- R56 C1.
- R56 C2.
- R56 C3.
- R56 C4.
- Any later or superior checkpoint discovered in the repository.

Do not assume that C1 is a genuinely new learned model. R56 reports that
its improvement may come from new traces and run variation.

For each checkpoint, record:

- Source checkpoint.
- Training dataset.
- Dataset checksum.
- Teacher/student provenance.
- Number of teacher-labeled examples.
- Maximum pipe index represented in teacher labels.
- Training configuration.
- Model checksum.
- Per-seed evaluation.

CRITICAL DATA-PROVENANCE RULE:

A student checkpoint may only qualify as an R57 teacher-bootstrap student
if its teacher-derived training labels contain no teacher actions beyond
the first 20 successfully passed pipes per teacher episode.

If the R55 or R56 checkpoint contains labels from later teacher
behavior, it may remain a useful historical comparison, but it MUST NOT
be silently treated as a student trained under the new 20-pipe teacher
limit.

Do not erase historical checkpoints. Do not rewrite their provenance. Do
not pretend an old checkpoint has a cleaner training history than it
actually has.

Create a dataset provenance manifest. Every demonstration must identify:

- episode_id
- seed_id
- source_type: teacher or student
- source_checkpoint
- frame_index
- passed_pipe_count
- observation_id
- action
- dataset_split
- provenance_hash

Any teacher example after pipe 20 must be excluded from the qualified
R57 initialization dataset.

## PART 2 — TEACHER BOOTSTRAP: EXACTLY LIMITED KNOWLEDGE

The teacher has one job: teach the basic game.

Teacher demonstration rule: for every teacher demonstration episode:

- Start at the normal game start.
- Use the validated teacher.
- Record visual observations and legal actions.
- Stop recording teacher demonstrations immediately after 20 visually
  confirmed pipe passages.
- The teacher may die before 20.
- Never record teacher labels beyond the 20-pipe boundary.
- Never ask the teacher to recover a student.
- Never ask the teacher to demonstrate the 21st pipe.
- Never use teacher decisions to improve late-game behavior.

Collect several demonstration episodes with varied seeds. Use
approximately 10–20 teacher demonstration episodes as an initial
experiment, subject to runtime and data quality.

The teacher dataset should contain enough examples to show the student:

- Bird appearance and position.
- Pipe appearance and gap geometry.
- Relevant visual motion.
- Legal controller actions.
- Basic flap timing.
- Ordinary successful pipe passages.
- Basic game-over conditions.

Do not make the dataset artificially uniform. Keep real observations,
including difficult initial cases.

Add a hard automated test: NO TEACHER LABEL AFTER PIPE 20.

Also add a data audit that proves this restriction holds for every
demonstration episode.

After this phase, disable the teacher.

## PART 3 — BUILD THE QUALIFIED INITIAL STUDENT

Train a clean bootstrap student using only the permitted teacher
demonstrations. Use the best validated small visual architecture
available in the repository. Preserve R55/R56 historical checkpoints
separately.

The new qualified bootstrap model must have a clear name, for example:

    r57_bootstrap_bc

Do not force the bootstrap student to score 30 or 40. Its purpose is to
learn the basic visual behavior.

Measure its actual performance in the real PS1 game. Record:

- Per-seed score.
- Mean and median.
- Minimum and maximum.
- Number of episodes passing 10, 15 and 20 pipes.
- Model size.
- Checksum.
- CPU inference time.

If this clean bootstrap student scores only 10–15, that is acceptable as
an honest starting point.

Do not reuse teacher-derived late-game knowledge under a different
filename.

## PART 4 — HARD SEPARATION: TEACHER IS NOW OFF

After bootstrap, the training pipeline must run without teacher access.
The student must independently generate every new training trajectory.

Disallowed after bootstrap:

- Teacher action queries.
- Teacher recovery actions.
- Teacher-generated late-game labels.
- Teacher-selected actions for difficult situations.
- Teacher trace replay as a source of new labels.
- DAgger querying the teacher for the student's mistakes.
- Hidden-state expert actions.

Allowed:

- Student-generated observations.
- Student-generated actions.
- Student-generated rewards.
- Student-generated successful trajectories.
- Student-generated failure trajectories.
- Student self-imitation.
- Student policy search.
- Training from its own previous experiments.

The teacher process should be unavailable during student-only training,
not merely inactive by convention.

Add a no-teacher execution mode and executable tests that fail if the
student training pipeline calls any teacher action function.

Record a runtime trace proving that the teacher was not called.

The student must continue playing after pipe 20. Student episodes must
never inherit the teacher's 20-pipe demonstration limit.

## PART 5 — VISUAL-ONLY OBSERVATION AND REWARD

The deployed policy must receive only rendered visual information.

Allowed policy inputs:

- Current frame.
- Previous frames.
- Compact visual features.
- Frame-derived motion.
- Visually estimated bird position.
- Visually estimated velocity.
- Visually estimated gap geometry.
- Previous legal action.
- Compact policy memory if necessary.

Forbidden:

- Emulator RAM reads.
- Hidden bird coordinates.
- Internal velocity.
- Internal pipe positions.
- Game-engine collision flags.
- Internal score variables.
- Privileged simulator state.
- Seed identity as a policy feature.
- Teacher-only information.

The reward system must use the same visual evidence available to the
student.

Primary objective: +1 for each uniquely visually confirmed pipe passage.

Requirements:

- Detect each passage only once.
- No duplicate rewards.
- No reward for simply approaching a pipe.
- No hidden RAM counter.
- No internal collision flag.
- Visual game-over detection.
- Natural episode termination.

Start with sparse, clean rewards. Do not add large reward-shaping
systems just because learning is difficult. If reward shaping is
introduced, implement a separate ablation and prove that it improves
real pipe counts.

Audit observer reliability:

- BirdObserverV7.
- GapTrackerV7.
- Pipe tracking.
- Frame ordering.
- Score-glyph false positives.
- Motion estimation.
- Passage-event detection.
- Terminal-event detection.

Keep observation provenance for every training episode. An inaccurate
observation or reward must not silently become a trusted training
example.

## PART 6 — THE STUDENT MUST EXPLORE NEW BEHAVIOR

R56 exposed a fundamental problem: a deterministic student that only
strengthens the actions it already chooses cannot reliably discover new
strategies.

R57 must provide genuine, mathematically valid exploration.

Do not use fake exploration. Do not select an action with argmax and
then calculate a fabricated stochastic log-probability for PPO. Do not
use a temperature in the probability calculation that differs from the
actual action-selection process. Do not silently change action-selection
rules between rollout collection and policy updates.

Every recorded action must have the correct probability under the
behavior policy that actually selected it.

Investigate the actual Flappy action contract first. Do not assume an
action count or encoding.

### Candidate A — CONFIDENCE-AWARE STOCHASTIC POLICY

If the policy exposes logits:

- Define an explicit valid action distribution.
- Use confidence or action-margin estimates to adjust exploration.
- Preserve a very strong preference for the current best action in
  high-confidence states.
- Permit meaningful exploration in uncertain states.
- Ensure every legal action has a valid probability.
- Record the exact probability used to select each action.
- Store the policy version and distribution parameters.

One possible construction is:

    p_behavior(a|s) =
        (1 - epsilon(s)) * p_policy(a|s)
        + epsilon(s) * p_exploration(a|s)

Where epsilon(s) changes according to confidence, p_policy is the actual
current policy distribution, p_exploration is a valid distribution over
legal actions, and all quantities are saved with the rollout.

Do not copy this formula blindly. Validate that the action distribution
is appropriate for the real game's action timing.

### Candidate B — CORRECT ON-POLICY PPO

If PPO is used:

- Use actual sampled actions from the behavior policy.
- Record exact old log-probabilities.
- Calculate new log-probabilities under the new policy.
- Correctly calculate probability ratios.
- Keep rollout policy versions explicit.
- Correctly calculate GAE.
- Avoid cross-episode bootstrap contamination.
- Use proper episode termination and truncation handling.
- Monitor KL divergence.
- Monitor entropy.
- Monitor action-distribution changes.
- Use conservative policy updates.
- Keep the previous champion unchanged until evaluation proves an
  improvement.

If near-deterministic BC logits are saturated, investigate the root
cause. Possible solutions to evaluate:

- A separate policy-logit calibration layer.
- A small policy temperature with consistent action selection and
  probability calculation.
- Confidence-aware exploration.
- Conservative initialization of the actor distribution.
- Entropy regularization.
- Smaller policy updates.
- A properly initialized value network.

Do not claim PPO works merely because its loss decreases. The learned
policy must improve actual real-game results.

### Candidate C — POPULATION-BASED POLICY SEARCH

Implement or evaluate a CPU-friendly alternative: Evolution Strategies
(ES), Augmented Random Search (ARS), or Cross-Entropy Method (CEM).

Rationale: the student has a small policy network and an episodic
objective that is directly measurable: passed pipes. A population-based
method may avoid some of the sensitivity of gradient updates around
saturated logits.

Possible procedure:

1. Start from a frozen student checkpoint.
2. Generate controlled policy variations.
3. Evaluate candidates on the same training seed set.
4. Measure actual visually confirmed pipe passages.
5. Rank candidates using mean and median performance.
6. Keep the best robust candidates.
7. Generate the next population.
8. Preserve the previous champion.
9. Validate each promising generation independently.

Use paired seeds to reduce variance. Do not allow a lucky single episode
to determine the winning candidate. Preserve the original student as an
immutable champion.

### Candidate D — SELF-IMITATION

The student may learn from its own successful episodes. Only the
student's own trajectories qualify.

Possible process:

- Keep best student episodes.
- Preserve diverse successful trajectories.
- Identify consistent successful action patterns.
- Train from the student's own decisions.
- Avoid over-weighting one seed.
- Prevent self-imitation from collapsing exploration.

R56 showed that DAgger was harmful in the tested setup. Do not
reintroduce teacher DAgger under another name. Self-imitation must be
based exclusively on student experiences.

## PART 7 — EXPERIMENTALLY CHOOSE THE BEST LEARNER

Do not assume PPO is automatically best. Build controlled experiments:

- A. Frozen qualified bootstrap BC.
- B. BC + confidence-aware exploration + correct PPO.
- C. BC + ES/ARS or CEM policy search.
- D. Best method + student self-imitation, if useful.

Use the same training budget and comparable seed exposure. Do not modify
many unrelated variables simultaneously.

For every experiment, record:

- Model initialization.
- Algorithm.
- Hyperparameters.
- Training seeds.
- Rollout count.
- Episode count.
- Real-game score.
- Policy checksum.
- Runtime.
- CPU time.
- Failure reasons.
- Validation result.

Compare algorithms using validation seeds. Choose the method that
produces the strongest reproducible student, not the method with the
most impressive-looking training loss.

If PPO fails but ES succeeds, keep ES. If ES fails but PPO succeeds,
keep PPO. If both fail, report the actual blocker and preserve the best
previous student.

Do not combine multiple methods without controlled evidence that the
combination helps.

## PART 8 — LEARN FROM THE STUDENT'S OWN FAILURES

Build student-only failure mining. For every student death, record:

- Last confirmed pipe passed.
- Visual bird trajectory.
- Last several observations.
- Recent legal actions.
- Current pipe.
- Next pipe.
- Gap estimate.
- Estimated bird velocity.
- Confidence of each visual measurement.
- Last valid observation.
- Last action before death.
- Whether perception was stable.
- Whether the action was plausibly responsible.

Classify failures:

1. Bird perception failure.
2. Pipe perception failure.
3. Velocity estimation failure.
4. Gap tracking failure.
5. Incorrect action timing.
6. Unnecessary flap.
7. Late flap.
8. Early flap.
9. Action timing/physics uncertainty.
10. Genuine unexplored state.
11. Uncertain cause.

Do not label every death as a wrong-action problem. If visual perception
was wrong, fix perception first. If the observation was correct but the
action failed, preserve the experience for student learning.

For a confirmed difficult state:

- Use the student's own experience.
- Try alternative legal action sequences.
- Evaluate the continuation through actual game runs whenever possible.
- Record which alternatives survive.
- Add successful outcomes to student-generated data.
- Do not ask the teacher for the correct action.

A simulator may help propose candidates, but real emulator runs must
decide whether those candidates work.

## PART 9 — FULL EPISODES, NOT ARTIFICIAL SCORE CAPS

Teacher demonstrations are capped at 20 successful pipes. Student
episodes are NOT capped at 20.

Student training must continue beyond 10, 20, 30, 40 and 50 pipes. Use a
documented frame budget sufficiently long to allow 50+ pipes when the
gameplay permits it.

Do not terminate episodes when the student matches the teacher. Do not
restart merely because the student reaches 20. Do not artificially reset
the score counter.

Normal evaluation must start from the authentic game start. Keep any
advanced-state experiment separate from normal full-game evaluation. The
main score must always be the actual number of visually confirmed
passages in a full episode.

## PART 10 — PROTECT AGAINST FORGETTING

As the student learns later-game behavior, it must not forget how to
survive the beginning.

Use a balanced training experience set containing:

- Early-game states from student episodes.
- Middle-game states from student episodes.
- Later-game states from student episodes.
- Successful trajectories.
- Diverse seeds.
- Difficult but valid observations.

Do not let late-game mining destroy the early-game policy.

Maintain an immutable champion checkpoint. A new version replaces the
champion only if it passes the required validation criteria.

Use a regression gate:

- Early survival must not collapse.
- Median pipe count must improve or remain statistically compatible with
  the prior champion.
- No major seed group may be sacrificed without an explicit documented
  trade-off.

If catastrophic forgetting occurs, investigate replay, experience
balancing, conservative updates or policy regularization. Do not merely
increase model size.

## PART 11 — TRAINING, VALIDATION AND TEST SEPARATION

Create three separate seed groups.

TRAIN: used for actual student experience generation and policy
optimization.

VALIDATION: used for checkpoint selection and hyperparameter tuning.

TEST: held out until the final selected model is frozen.

All previously used R55/R56 seeds must be considered development or
validation material. Do not claim generalization based only on k6, k30,
k60, k90 or k210. Use at least 20 previously unseen final test seeds if
runtime permits. Do not use final test scores to adjust
hyperparameters.

For each final test seed:

- Start the real PS1 game normally.
- Run the frozen student.
- Disable teacher access.
- Disable privileged state access.
- Use the same action timing and frame budget.
- Record the full visual trace.
- Record the visually confirmed pipe score.
- Save the model checksum.

Repeat cases when boot nondeterminism requires it. Report per-seed
results.

Required statistics:

- Mean.
- Median.
- P25.
- P75.
- Minimum.
- Maximum.
- Standard deviation.
- Number reaching 10+ pipes.
- Number reaching 20+ pipes.
- Number reaching 30+ pipes.
- Number reaching 40+ pipes.
- Number reaching 50+ pipes.

Never confuse the sum of multiple runs with a single-game score.

## PART 12 — SUCCESS TARGETS

The first qualified objective:

- Clean bootstrap uses only the first 20 teacher pipes.
- Student receives no later teacher actions.
- Student plays complete episodes independently.
- Student produces its own training experiences.
- Student shows measurable learning beyond bootstrap.

Performance target:

- Median of at least 20 pipes on new test seeds.
- Repeated episodes above 20.
- Evidence that post-bootstrap learning caused improvement.

Next target:

- Median of at least 30 pipes on unseen test seeds.
- At least 75% of test episodes reach 20+ pipes.
- No dependence on one exceptionally lucky seed.

Stretch target:

- Median approaching 40 pipes.
- Multiple independent episodes exceed 40.

Long-term target:

- Repeated 50+ pipe episodes.
- Continued improvement without teacher assistance.

These are goals, not permission to fabricate results. If the student
does not reach 30, report the best reproducible result. Explain whether
the blocker is exploration, reward, perception, physics, policy
capacity, training budget, generalization, or emulator nondeterminism.

A failed attempt at 30 is still useful if the experiment establishes
exactly why the student failed.

## PART 13 — REAL-GAME VALIDATION IS MANDATORY

The real FlappyBirdPSX emulator is the final authority. A simulator
result is not a real-game result. A synthetic frame result is not a
real-game result. An offline rollout is not a real-game result.

Every selected candidate must pass real emulator evaluation.

Compare:

1. Qualified clean bootstrap BC.
2. Frozen R55 BC reference.
3. Frozen R56 C1 reference.
4. Best independent-learning candidate.
5. Teacher, limited to its first 20 pipes only.

Historical uncapped teacher scores may be shown as historical context,
but must not be used to pretend the teacher is still allowed to teach
after 20.

For the final evaluation, include: actual game screenshots, full episode
traces, controller actions, visual observation records, pipe passage
evidence, death frames, model checksum, frame budget, per-seed score.

## PART 14 — PERFORMANCE AND PORTABILITY

Preserve the small-model objective. R55 student was approximately 7 KB.
Measure the R57 model against that reference.

Record:

- Artifact size.
- Parameter count.
- Input feature size.
- Output action contract.
- CPU inference latency.
- Peak memory.
- Dependencies.
- Model checksum.

Do not require a GPU. Do not require a paid API. Do not require an
online teacher. Do not require a large LLM.

Keep the training environment separate from deployment. The deployed
student must require only:

    Rendered game frames
        ↓
    Visual feature extraction
        ↓
    Small student model
        ↓
    Legal controller actions
        ↓
    PS1 game

If ONNX export is practical:

- Export the winning inference policy.
- Compare native and ONNX outputs.
- Compare action probabilities.
- Run ONNX Runtime CPU inference.
- Evaluate the actual game with the ONNX model.
- Confirm that no training-only modules are required.

Do not claim portability just because an ONNX file exists.

## PART 15 — AUTOMATED TESTS

Add tests for:

TEACHER: every demonstration stops at 20 pipes; no teacher label exists
after the cap; early teacher death works; provenance is preserved.

BOOTSTRAP: only permitted teacher data is used; historical late-game
labels are excluded; dataset manifest matches actual training data.

STUDENT: runs with teacher disabled; runs without RAM access; uses legal
actions only; continues after 20; generates its own training episodes;
can save and reload checkpoints.

EXPLORATION: actual action distribution is recorded; action
log-probability matches action selection; no fake
argmax/log-probability mismatch; policy updates are numerically stable;
exploration can produce alternative actions; the champion remains
preserved.

REWARD: pipe passage is visually confirmed; one pipe produces one
reward; no duplicated reward; no RAM-derived reward.

LEARNING: student-generated episodes are distinguished from teacher
demonstrations; self-imitation uses student data only; training can
resume; model selection uses validation only.

EVALUATION: test seeds are not used for training; full-episode results
are recorded; frame budgets are equal; aggregate statistics are correct.

RUN: full existing R55/R56 regression suite; all R57 unit tests; full
Flappy integration tests; Pong regression; at least three independent
end-to-end student runs; final held-out test evaluation.

Passing tests alone does not prove learning. Real-game performance is
required.

## PART 16 — EXPERIMENT AUTOMATION

Create a reproducible R57 experiment runner. It must support:

- Bootstrap checkpoint loading.
- Teacher-disabled mode.
- Student rollout generation.
- Visual-only reward collection.
- PPO or selected alternative.
- Self-imitation if validated.
- Checkpoint creation.
- Validation evaluation.
- Champion preservation.
- Resume after interruption.
- Machine-readable results.
- Per-episode traces.

Keep disk usage manageable. Do not store every raw frame forever.
Preserve important frames around: first pipe passage, pipe 10, pipe 20,
pipe 30, pipe 40, pipe 50, policy exploration events, death events,
observation failures.

Use compact trajectory storage. Do not lose evidence needed to explain a
failure.

## PART 17 — GITHUB AND WORKLOG

Use existing Issue #12. Do not create a duplicate Flappy issue unless a
genuinely separate root problem exists.

Update the issue with:

- Strict teacher cutoff.
- Data provenance audit.
- Clean bootstrap result.
- Student-only learning evidence.
- Algorithm selected.
- Failed algorithm experiments.
- Per-seed results.
- Test-seed separation.
- Model checksum.
- CPU measurements.
- ONNX verification status.
- Real-game screenshots and traces.

Write a complete R57 worklog. Use status labels: IMPLEMENTED, TESTED,
OBSERVED, PARTIAL, BLOCKED, PENDING, SUPERSEDED. Distinguish
implementation from actual observed behavior.

The repository's technical documentation must remain in English.

Preserve all historical R55/R56 evidence. Commit and push the completed
round. Verify the remote commit by reading it back.

## PART 18 — AUTONOMOUS EXECUTION

Work autonomously. Install free dependencies as needed. Debug failing
scripts without asking the user about minor errors. Inspect actual
source before modifying it.

Do not invent results. Do not replace real emulator runs with
simulation. Do not manipulate scores, rewards, frame budgets, episode
limits or seed selection. Do not remove difficult seeds. Do not use
teacher data beyond the permitted boundary. Do not spend most of the
round improving the teacher.

Prioritize the student's genuine independent learning. If an algorithm
fails, establish why and preserve the result. If CPU limitations prevent
the complete target, report the measured limitation and best
reproducible partial result. Do not declare success based on code
completion.

## FINAL DELIVERABLES

At completion, report:

1. Starting commit.
2. Final commit.
3. R55/R56 checkpoint provenance.
4. Qualified bootstrap checkpoint.
5. Teacher demonstration episode count.
6. Proof of the 20-pipe cutoff.
7. Proof of teacher-disabled learning.
8. RAM-access audit.
9. Visual observation and reward audit.
10. Learning algorithm and exact configuration.
11. Number of student-generated episodes.
12. Number of policy updates.
13. Checkpoint history.
14. Per-seed training results.
15. Per-seed validation results.
16. At least 20 unseen test results, if feasible.
17. Mean, median, P25, P75, min, max and standard deviation.
18. Number reaching 20, 30, 40 and 50 pipes.
19. Comparison with the clean bootstrap model.
20. Comparison with frozen R55/R56 references.
21. CPU performance and model size.
22. ONNX status, if implemented.
23. Full test results.
24. Screenshots and visual traces.
25. GitHub Issue #12 update.
26. R57 worklog.
27. Exact reproduction command.
28. Honest unresolved limitations.

## FINAL PRODUCT PRINCIPLE

The teacher provides the first 20 pipes of knowledge. After that, the
student is alone. The student must:

- Observe.
- Decide.
- Act.
- Succeed or fail.
- Remember.
- Experiment.
- Improve.

The student must be allowed to discover actions that the teacher never
demonstrated.

We are not building a recorder of teacher behavior. We are building a
learner.

The most important evidence is not that the student can repeat 20 pipes.
It is that the student can independently discover how to reach 30, then
40, then 50 and beyond.

The teacher's skill is a starting point, not a limit.

Build R57 around independent student improvement.
