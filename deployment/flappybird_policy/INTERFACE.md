# INTERFACE.md — the perception-to-action contract of the final
# FlappyBirdPSX policy

> R61 Section 5 deliverable. This document specifies EVERY stage of the
> inference chain, every feature, every sentinel, every boundary
> behavior — everything an independent implementer needs to drive the
> real game through the deployed ONNX policy without reading the
> training implementation. The schema in this document is ENFORCED at
> runtime by `flappybird_policy/schema.py`.

## 0. The chain

```
game frame (320x240 RGBA, emulator)
  -> area-average downsample  -> small frame (60x80x3 uint8)
  -> BirdObserverV7.step(small, own_prev_action)  -> by, vy
  -> _flappy_gap_raw2(small, by_hint=by)          -> gc_raw, dx, g0, g1
  -> GapTrackerV7.step((gc_raw, g0, g1, dx+160))  -> gc (or None)
  -> state construction (features_flappy_v7)      -> x (10,) float32
  -> ONNX policy (graph normalizes internally)    -> action_idx
  -> action mapping                               -> "HOVER" | "FLAP"
  -> legal controller input (pad1 B / none)
  -> emulator steps one frame
```

Ownership: stages 1–4 (perception) and 7 (action injection) are
HOST-side adapters — pure frame processing with NO learned weights;
stage 5–6 (the decision) is the ONNX artifact. The deployment package
owns stages 5–6 and validates the x that crosses the boundary.

## 1. Frame ingest

- Input: one emulator frame, 320×240, RGB (alpha dropped).
- Downsample: exact 4×4-block area average → 60×80×3 uint8
  (`np.clip(reshape.mean, 0, 255).astype(uint8)`; the 320→80 / 240→60
  splits are exact, so block-mean == the general linspace reference).
- One small frame per emulated frame; the perception consumes small
  frames only (plus the policy's OWN previous action — see §8).

## 2. BirdObserverV7 — bird state

Purpose: track the bird's y through multi-cue evidence (orange face +
white body blocks, the score-glyph box excluded) fused with the
MEASURED physics.

- Units: full-res y px (multiply small-frame rows by 4); the search
  band is small-rows 5..46 (≈ y 20..184 full-res).
- Physics (measured on 183 corpus impulse events, r55k):
  flap impulse **−8.0 px/f applied on the 2nd frame of a flap pulse**;
  the rise arc decelerates at **+1.0 px/f²** (integer steps); the fall
  accelerates at **+0.125 px/f²** with the screen dy **rounded
  half-up**; no fall terminal cap.
- Riding window: the evidence window RIDES the physics prediction and
  grows with the blind-streak length — static junk cannot latch the
  tracker (the R54 latch class is fixed at the source).
- Outputs per step: `by` (float, full-res y px) or **None** when lost;
  `vy` (float px/frame, signed, negative = rising).
- Initialization: `y=None, vy=0, run=0, ever=False, since_trust=99`.
- Reset: `reset()` between episodes (see §9). There is NO cross-
  episode state of any kind.

## 3. Gap finder v3 (`_flappy_gap_raw2`) — instantaneous gap reading

- Pipe mask: the measured hue rule `(g > r+8) & (b < g−40)` on the
  small frame (accepts the pipe gradient's bright (216,232,128) and
  shaded (80,120,40) ends; rejects sky/clouds/buildings).
- Band pick: column-sum bands over small-columns 30..80 (≥2-col runs,
  1-col dips merged); a band overlapping the bird's fixed columns
  (36..47) is preferred — "the pipe the bird must fly through".
- Gap edges: core-window profile (a row is PIPE iff ANY 3 adjacent
  band columns are ≥50% green) → free runs ≥8 rows → the sharpest
  valid edge pair; `g0` = top edge, `g1` = bottom edge (full-res y
  px, `row*4`).
- Constant-gap decontamination: the physical gap height is
  SOURCE-CONSTANT 70 px, so a free run >82 px proves bird-occlusion;
  the center pins on the edge AWAY from the bird (top+35 / bottom−35).
- Outputs: `(gc, dx, g0, g1, by)` with **−1.0 sentinels when missing**
  (no band / no valid run): `gc=dx=g0=g1=−1.0`. `dx` = band center x
  ×4 − 160 (signed offset from screen center, full-res x px).

## 4. GapTrackerV7 — temporal filter + pipe identity

- Input: the tuple `(gc_raw, g0, g1, bx=dx+160)` (bx = band center x,
  full-res) or None.
- Filtering: median-of-3 history; same-pipe consistency gate ±24 px;
  adopt-immediately within ±8 px; a mid-size shift needs 2-of-3;
  ACQUIRE needs 3 persistent readings within a 10 px spread (the gap
  is vertically static per pipe).
- Pipe identity: pipes scroll left ~1.4 px/f, so a band-center JUMP
  RIGHT >12 px = a NEW pipe → all state resets except the caller's
  stale-gap memory; 10-step refractory suppresses double-jumps.
- Output: the filtered `gc` (float) or **None** (no lock). The
  CALLER's stale-gap memory (`last_gc`, `since_gap`) carries across
  None outputs exactly like the full-res law's memory.

## 5. State construction — the 10-feature vector (v7)

`x = [by, vy, gc, dx, g0, g1, flap_run, since_flap, last_gc, since_gap]`
— float32, EXACTLY this order. Sentinels and ranges (ENFORCED):

| i | name | unit | missing/init | enforced range |
|---|------|------|--------------|----------------|
| 0 | by | full-res y px | −1.0 (lost) | [−1, 240] |
| 1 | vy | px/frame (neg = up) | 0.0 | [−10, 10] (clipped by construction) |
| 2 | gc | full-res y px | −1.0 (no gap) | [−1, 240] |
| 3 | dx | signed x px from center | −1.0 | [−160, 160] |
| 4 | g0 | gap top edge, y px | −1.0 | [−1, 240] |
| 5 | g1 | gap bottom edge, y px | −1.0 | [−1, 240] |
| 6 | flap_run | own consecutive FLAPs | 0 | [0, 9] (capped) |
| 7 | since_flap | frames since own FLAP | 99 at episode start | [0, 99] (capped) |
| 8 | last_gc | last valid gap center | −1.0 until first lock | [−1, 240] |
| 9 | since_gap | frames since last valid gap | 40 at episode start | [0, 40] (capped) |

Notes:
- `gc` in x is the TRACKER-filtered value when the tracker holds a
  lock, otherwise the raw −1.0 sentinel. (`last_gc`/`since_gap` give
  the model the memory of the last lock.)
- `by` is the observer's corrected state (not the raw centroid);
  −1.0 only before the first-ever fix.
- `vy` is the observer's integrated velocity (physics + gated
  measurement correction), clipped to ±10 by construction.
- The same-sensor discipline: the policy MUST see exactly the vector
  the perception emitted — nothing is imputed, smoothed or replaced
  at the boundary. Invalid values are REJECTED (never coerced).

## 6. Normalization + the decision

- The graph input `x` is the RAW vector above; normalization is
  INSIDE the graph: `x_norm = (x − mean) / (std + 1e-6)` (float32;
  constants in the manifest, verified at load).
- Forward: `h = relu(x_norm @ W1 + b1)` (10→128), `logits = h @ W2 +
  b2` (128→2).
- Outputs: `logits` [N,2] (order [HOVER, FLAP]) and `action_idx` [N]
  int64. ArgMax = first-max (`select_last_index=0`): **an exact tie
  resolves to HOVER** — identical to the reference numpy argmax.
- Determinism: same float32 input → same action (single-threaded CPU
  session).

## 7. Action mapping + legality

- `HOVER` → inject NO buttons this frame.
- `FLAP` → inject pad1 **B** (the libretro Cross bit — the controller
  truth-table trap: B here is Cross, NOT the "X" triangle) while the
  emulator steps exactly one frame.
- Legality: pad1 buttons only, the same 14 buttons a real DualShock
  has; one decision per emulated frame; the decision made on frame t
  applies during the step [t, t+1).
- No artificial cooldown in the adapter: the game's own flap pulse is
  2 frames (the impulse lands on the pulse's 2nd frame — §2 physics);
  the policy's rhythm lives in `flap_run`/`since_flap`.

## 8. What the policy is allowed to know (mission-legal input set)

Rendered frames + the policy's OWN action history (`flap_run`,
`since_flap`, `own_prev_action` feeding the observer's pulse
integration). NO RAM, NO score read, NO teacher, NO assisted reader,
NO future frames. This is the audited boundary; the deployment package
imports nothing that could widen it.

## 9. Episode lifecycle

- Init (per episode): fresh BirdObserverV7 + fresh GapTrackerV7 +
  counters at their init values (§5) + `own_prev_action=None`.
- No-pipe state: before the first pipe enters the band window, the
  gap block is the −1 sentinel set; the model also gets `last_gc`/
  `since_gap` = its init values. This is a normal, trained-for state.
- Occlusion / observer uncertainty: the observer may return `by=None`
  briefly (score-glyph overlap, pipe pass) — the feature carries the
  −1/0 sentinels; the tracker may lose its lock (returns None) —
  `last_gc`/`since_gap` carry. The consumer MUST NOT interpolate or
  hold stale values beyond what these features encode.
- Transitions: pipe passes are NOT observable as events at this layer
  (the band-center jump is internal tracker state). Score is never an
  input.
- Terminal state: the GAME-OVER panel (a large beige rectangle in the
  band rows 60..150 / cols 90..230: `r>185 & g>175 & b<200 & r>b+20`
  over >35% of the band) ends the episode; after detection the host
  resets (§9 init) and starts the next episode. The policy itself has
  no terminal concept — the host stops calling it.
- Reset between episodes: re-create BOTH perception objects; never
  reuse them across episodes (verified: stale state changes actions).

## 10. Frame timing assumptions

- One decision per emulated frame (60 fps nominal; the emulator runs
  unthrottled headless — the GAME is frame-driven, so the decision
  cadence is the game's own frame cadence, not wall time).
- The frame handed to the perception is the frame BEFORE the input
  lands (decision t → input during [t, t+1)) — one-frame latency is
  part of the trained behavior.
- The emulator is deterministic: identical (savestate, inputs) pairs
  produce byte-identical frames (verified R61); episodes therefore
  reproduce byte-exactly.

## 11. What is game-specific vs reusable

- Game-specific (must be re-implemented per game): frame ingest
  geometry, BirdObserverV7, the gap finder, GapTrackerV7, the feature
  schema, the action mapping, the terminal-state detector.
- Reusable as-is: the deployment package (load → verify hashes →
  validate schema → run session → argmax), the manifest/evidence
  discipline, the episode-lifecycle pattern, the legal-input
  principle. See REUSE_BOUNDARY.md.
