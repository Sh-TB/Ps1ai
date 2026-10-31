# REUSE_BOUNDARY.md — what ports to another game (R61 Section 12)

The R61 mission explicitly does NOT build a universal framework. This
note marks the exact boundary so the next game integration starts from
facts, not hope.

## Reusable as-is (game-agnostic)

- **The policy loading + verification pattern** (`policy.py`):
  manifest binding, sha256 enforcement, session init, version
  reporting, close/reset lifecycle. Copy the module, change nothing.
- **The strict input contract pattern** (`schema.py`): named features,
  documented sentinels, enforced ranges, reject-never-coerce. Per
  game: swap the feature table and ranges.
- **The episode lifecycle pattern**: fresh perception per episode,
  counters at documented init values, terminal detection by the host,
  no cross-episode state.
- **The evidence discipline**: artifact + sidecar + manifest + hashed
  traces + pre-registered splits + read-back verification. Entirely
  game-agnostic.
- **The runner pattern** (`r61e_deploy_loop.py`): chunked, resumable,
  fault-loud evaluation loops with per-episode records (trace hash,
  pipes, frames, flaps, death reason).

## Game-specific (must be re-implemented per game)

| component | flappy-specific content |
|---|---|
| frame ingest | 320×240 → 60×80×3 exact block mean |
| bird observer | BirdObserverV7 (multi-cue bird evidence, measured physics: impulse −8 @ pulse frame 2, rise +1.0 px/f², fall +0.125 px/f², half-up rounding) |
| gap finder | pipe hue rule `(g>r+8)&(b<g−40)`, band pick, 70 px constant-gap decontamination |
| gap tracker | median-of-3, ±24 consistency, 12 px pipe-identity jump, acquire-3 protocol |
| feature schema | the 10 dims (INTERFACE.md §5) |
| action mapping | HOVER/FLAP → pad1 B (Cross), one frame per decision |
| terminal detector | beige GAME-OVER panel rule |
| seed semantics | k idle frames pre-press seeds the RNG |

## The plug-in shape for a new game

```
newgame_adapter/
  observer.py     frames -> game state features (the hard part)
  schema.py       feature names + ranges + sentinels (enforced)
  actions.py      action names -> legal pad buttons
  terminal.py     game-over / episode-end detector
  policy/         load_policy + model + manifest (reuse verbatim)
```

The shared contract is one function: `frames + own-action-history ->
validated vector -> policy.predict -> legal buttons -> emulator`.
Everything else above is the game's own physics read from pixels.

## What does NOT generalize

- The FlappyBird policy itself (weights, features, physics priors) —
  no cross-game claim exists or is implied.
- hello_pong's student is a separate 4-feature policy; its 8/2 vs 7/0
  result is a regression gate for the shared infrastructure, not
  transfer evidence.
- The measured physics constants (impulse/gravity/rounding) are
  FlappyBirdPSX's; every game needs its own measured dynamics.
