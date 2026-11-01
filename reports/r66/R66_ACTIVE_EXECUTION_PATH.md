# R66 ACTIVE EXECUTION PATH — which code actually runs when Metal Slug X plays

Round: **R66** · Issue anchors: #4 (mission clear), #5 (RE master task),
#6 (architecture), #9 (decision loop), #10 (closed-source recovery).

## 1. The R65 baseline answer (recorded, then changed by R66)

At R65 there was **NO product execution path for Metal Slug X**: the
game was not in the runtime registry
(`ps1play/runtime/registry.py::_register_defaults` registered only
flappybird / tetrade / buzzybee) and `python3 -m ps1play play
metal_slug_x` failed with `unknown game`. The only "active" MSX path
was the legacy experiment workstream:

```
scripts/rNNt1_*.py  (R38–R52 experiment runners)
  ├─ issue4_controller.boot_to_demo()      boot: labconfig → PS1Play.api
  │    └─ p.enter_gameplay3()               generic navigation
  │    └─ START taps + owns_pad()           input ownership (pad mirror 0x0D4948)
  ├─ ps1play.agent.route.RoutePolicy        movement (MSX semantics in
  │    │                                    the SHARED agent package — a
  │    │                                    pre-isolation-law legacy)
  │    └─ ps1play.agent.combat              entity table scan 0x0CA268
  ├─ run_mission1_legit.recover_v2          continue-screen rescue
  └─ the r48/r50/r51/r52 telemetry layers   census_full/frame_walk/...
```

That workstream is a SCRIPT stack, not a product path: no registry, no
engine lifecycle, no per-episode records, no release-gate coverage.

## 2. The R66 product path (built this round, then verified live)

R66 registered Metal Slug X as the FOURTH runtime game. The verified
execution path of `python3 -m ps1play play metal_slug_x` (every step
executed for real this round; evidence in
`data/games/SLUS-01212/truck_evidence/r66/r66_product_run.json`):

```
ps1play/__main__.py::_cmd_play
  → RuntimeConfig.validated()                     registry membership check
  → RuntimeEngine.preflight()                     disc sha256 pin
  │    (session.EXPECTED_ISO_SHA["metal_slug_x"] = 45cde149…; a mismatch
  │     refuses to boot — AssetError)
  → RuntimeEngine.boot()                          EnvSession.boot_new →
  │    registry.make_env → adapters.metal_slug_x env factory
  │    (BaseEnv over the owner's lawful local copy, dedicated
  │     workspace ws_r66_msx, OpenBIOS override)
  │  → registry.adapter_for_game → MetalSlugXAdapter
  │  → registry.policy_for_game → Mission1Policy (built-in factory)
  │  → SafetyController
  │  → adapter.wait_ready(): settle → enter_gameplay3 → START taps →
  │    _owns_pad (idle pad-mirror zero + RIGHT response) → _in_mission
  │    (pad toggle + alive word) — the engine RETRIES the boot on failure
  → per episode:
       adapter.start_episode (continue-screen recovery, bounded)
       loop (1 decision = 1 frame):
         adapter.observe  → GameObservation(21 floats; RAM reads only:
         │   player_x 0x0CA2E0 u32 16.16, score 0x0EE318, hp 0x0CA2F6,
         │   grenades 0x0EDCF4, alive 0x0EE518, entity table 0x0CA268
         │   stride 0x14C → 5 nearest GROUND mortals (st,x,h,sx bands))
         policy.predict   → Mission1Policy._decide (the R66 corridor
         │   predicate: only absorbing/registering mortals block;
         │   transparent 0xab94 and airborne rows never do)
         controller.apply → legal pad buttons for ONE frame
         adapter.post_advance → score/px/alive; terminal on the
         │   alive-word failure (death → next episode recovers)
  → EpisodeResult persisted (data/r66/episodes.jsonl)
```

**Isolation proof:** all Metal Slug X semantics (anchors, state
families, corridor predicate, gate, recovery) live in
`ps1play/adapters/metal_slug_x/` (adapter.py + policy.py +
package_spec.py). The shared runtime knows the game only through the
registry entry (id + disc path + hash pin) — enforced by
`tests/test_r66_msx_adapter.py::TestIsolation`
(no cross-game imports; no MSX addresses in `ps1play/runtime/*.py`).

## 3. Evidence that the inspected policy is the policy that ran

* The episode records carry
  `policy_name: "msx_mission1_rules:1.0.0"`,
  `policy_sha256: 4e6470053115cb41…` — the sha256 of
  `ps1play/adapters/metal_slug_x/policy.py` as served by
  `Mission1Policy.identity()` at run time.
* Two independent runs produced byte-identical outcome metrics
  (1666f/1100 and 388f/1300, 87/13 actions) — the deterministic
  policy's signature through the real engine.
* The run manifest pins core sha `effff7bb…`, BIOS sha
  `0a9685d9…`, disc sha `45cde149…` (serial SLUS-01212 in the boot
  info).

## 4. What still runs OUTSIDE the product path (honest map)

* The R66 EXPERIMENT boots (the pay-frame hunt) still go through the
  legacy script stack (`scripts/r66t1_payframe_destarve.py` importing
  the r39..r52 layers) — that is the disclosed experiment workstream,
  labeled TAINTED where lineage requires it, and it is where the
  pay-frame telemetry lives.
* `ps1play/agent/route.py` + `ps1play/agent/combat.py` remain in the
  shared agent package as MSX-semantics legacy code (pre-dating the
  isolation law). R66 did NOT move them (risk discipline); the R66
  adapter reimplements what it needs inside the game package instead.
  Migration of the legacy modules into the MSX package is recorded as
  future work (Issue #6 owns the architecture ledger).
