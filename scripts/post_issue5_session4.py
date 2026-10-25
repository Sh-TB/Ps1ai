#!/usr/bin/env python3
"""post_issue5_session4.py — Issue #5 comment: the session-4 report
(F9 unblocked, the end-sequence decode, the policy patch, the paired
policy-only MISSION 1 banner)."""
import sys
sys.path.insert(0, "/home/z/my-project/scripts")
import gh_api

BODY = """## Issue #5 — session 4: F9 UNBLOCKED — the MISSION 1 banner through the shipped plugin policy (2026-10-25)

**Baseline → HEAD:** `b19ad97` → **`c1f81b3`**, pushed. Suite **466 passed + 1 xfailed**. The sandbox reset had wiped the checkpoints again — `pin_ckpt` (px 1164.0, 10 grenades, score 1200) was rebuilt live and reproduced the deterministic pin behaviour (warp k=18 → 992, wave 1064–1103). Machine-readable record: `data/games/SLUS-01212/truck_evidence/truck_resolution_session4.json`.

### §1 The F9 mystery resolved — the residual soldier was never unkillable

Session 3's "one residual frozen `0x4054` at 1072 that Y-bursts did not kill" decomposes into **two aiming bugs**, both fixed by evidence:

- **FACING**: the soldier sat at **dx −92..−120 — BEHIND the player** at the pin. The session-3 bursts turned 6f then fired 24f of Y computed from an anim-cycled row; the session-4 probes (`soldier_hp_probe*.py`) aim first, fire ONE 4f tap, and verify the corpse flip per shot. Result: **2 aimed bullets per soldier, 3/3 deterministic** (`soldier_bpp.py`, fresh `pin_ckpt` each attempt).
- **CORPSE MIS-AIM**: mid-anim corpses keep a valid screen-x until their ~+138f despawn and passed every filter — the policy fired at the dead while the live soldier walked. Killed soldiers flip `0x4054 → 0x4BE4` (then `0x5CC8`) and their row zeros at ~+138f.

**Liveness semantics (live-probed):** live = state family `{0x4054, 0x41FC}` — it **cycles unattended within ~600f** (v1 probe: slot 12 flipped with zero input), so `st == 0x4054` is not a liveness test; corpse = `{0x4BE4, 0x5CC8}` (stable). The soft-soldier HP **word** stays UNKNOWN honestly: a no-input MISS control moves **41 words** (incl. decaying `+0xce`/`+0xd2`) — the row diff is drowned by animation noise. Behavioural HP = 2 bullets.

### §2 The end sequence decoded — it runs BY ITSELF

The full release chain needs **no walking**: after the wave clear, on a STANDING player the game runs

`(0xB,0x1) @992 → (0,8) walker reset → (0xC,0x9) @ px 26.4` = the **MISSION 1 banner** ("MISSION 1" + "CLEAR TIME 0'09\"61" + "PRESS START", score 1500) — the same state `release_confirm` keyed on independently. Verified 6/6 across two harnesses (`chain_a_full.py` v6 scripted ×3; `policy_chain_trial.py` policy-only ×3). PNG committed: `truck_evidence/session4/chain_scripted_banner.png`.

Two fragilities found the hard way (each killed earlier iterations deterministically):
- **INPUT-FRAGILE**: any input during the `(0,8) → (0xC)` window skips/expedites the banner into a mission restart (px 982 → 26–32); walking during the banner expires its countdown (chain_a v3/v4).
- **RE-ARM**: walking back into the px-1164 clamp re-runs the pending-queue check — the pre-latch policy oscillated kill/walk/repin, burned all 10 grenades and died to the fallers (c=23, 3/3).

### §3 The policy patch (plugin layer only, zero core edits) — and the PAIRED trial

`ps1play/agent/combat.py`, every rule tied to a live observation:
(a) `scan_entities` drops `CORPSE_ST` rows (the mis-aim fix); (b) the **mission-end hold** — state `0xC` ×2 confirm, plus pre-banner trigger B (a `(0,8)` reset **inside the D7 zone**) latches a full no-input chunk immediately; (c) the **D7 zone latch** (px ≥ 1150; un-latch only on a restart reading px < 300) — never `advance` inside the pin cycle, walk-back floor 985 (the release ran standing at 992–1016); (d) `clamp_clear` aims soldier-family slots first (2-bullet kills, no UP-phase waste) and goes **SILENT on an empty zone scan**; (e) a valid-px restart reading un-latches into the next mission.

**Paired result (`policy_chain_trial.py`, same checkpoint, same budgets):**

| arm | runs | outcome |
|---|---|---|
| **fix** (this patch) | 3 | **MISSION_BANNER 3/3** — c=79, score 2500, **0 deaths**, deterministic |
| baseline (pre-patch: corpses included + no hold) | 3 | **0/3** — `death_no_respawn` ×3 (2 deaths each) |

The SHIPPED PLUGIN POLICY alone — no scripted inputs — now completes Mission 1 from the D7 checkpoint. Suite 466+1xfail (7 new tests in `tests/test_session4_release.py`; 3 legacy px-scope tests re-scoped below the D7 zone with citations).

### §4 Honest status

- `GAMEPLAY_VERIFIED` — the MISSION 1 completion banner **6/6** (3 scripted + 3 pure-policy) from the D7 checkpoint, real inputs only, no cheats, no memory writes.
- `UNKNOWN` (honest) — the wall mortarman (the faller source) survived 3–4 aimed taps in both arms; not needed for the release (the banner arrives with it alive), HP semantics unmeasured.
- **Still not claimed**: a full from-mission-start clear under the shipped policy alone (the checkpoint embeds the pre-D7 progress), and Mission 2 entry.

### §5 The single highest-value next action

**Extend the policy path backwards**: the same D7 discipline (queue-soldier priority + quiet-hold) applied from the mission start — the pre-pin sections already have verified per-section recipes (the truck 4-grenade kill, the chopper jump-lob); one paired trial from a fresh boot would upgrade "Mission 1 completable" into "Mission 1 cleared by the policy end-to-end", and then Mission 2 entry (the banner's START flow is already characterized)."""

s, d = gh_api.req("/repos/Sh-TB/Ps1ai/issues/5/comments", "POST",
                  {"body": BODY})
print("posted:", s, d.get("html_url", d))
