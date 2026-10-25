#!/usr/bin/env python3
"""post_issue5_session6.py — session-6 report comment on Issue #5.
Updates only — no new issues (mission rule)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
import gh_api                                                     # noqa

B5 = """## Session 6 — MISSION 2 (the TRAIN mission) ENTERED — GAMEPLAY_VERIFIED 3/3; the session-5 "death" SUPERSEDED (2026-10-25)

**Base:** `21d92db` → **`f5a6b1a`** (pushed, API-verified). Suite **466 passed + 1 xfailed** (zero plugin edits — script-level session). Trigger: the user's directive "continue the train" = the declared session-5 next action (mission-2 entry).

### S6-F1 — the session-5 "deterministic death at c43" is a MEASUREMENT ARTIFACT (`GAMEPLAY_VERIFIED`, 5 boots)

`scripts/lives_banner_variant.py` re-ran the e2e with a death-frame PNG burst + full 36-slot censuses:

- php is **stable 155 for 12 hold chunks** (c30–c41), then flips to 0 exactly when px tears down to 0.0 — no damage trajectory exists.
- The death-frame PNGs show the player **STANDING, no death animation**, under the **"PAYS BONUS 60 / PRESS START" tally HUD with `1UP=2` (lives intact)** (`session6/tally_death_f0_1UP2_no_animation.png`, `tally_death_f1_pays_bonus.png`).
- ⇒ The c42–43 event is the **mission-clear tally teardown** tripping the `alive()` sensor (php>0), NOT a combat death. Session-5's "faller rain / last life" attribution is **withdrawn**; the banner was always reached with lives remaining.

### S6-F2 — the declared "pre-window chopper kill" DISSOLVES (`OBSERVED`)

**Zero** `0xAA94/0xABDC` (chopper) rows across 19 D7-zone + 8 hold censuses (36-slot scans). The chopper visible in the post-clear scene PNGs is set-dressing/boss-not-engaged. The guarded interlude (abort-on-(0,*)/0xC, throw cap 80, close-in waits) never fired in any run — kept as a no-op.

### S6-F3 — MISSION 2 ENTRY, the headline (`GAMEPLAY_VERIFIED` 3/3 bit-identical: lives5/6/7)

Post-banner flow, all real inputs (continue-accept + walk = disclosed scripted probes):

1. banner PASS (the hardened predicate; c=95 with the forensics frames, c=107 bare — runs 1–4 reproduce session-5 exactly);
2. `W`: no-input watch → the `(0xB,1)` **CONTINUE? countdown** screen (`postbanner_continue_screen.png`);
3. `S`: **one START tap accepts** → end-zone gameplay px 992, score kept 3301 (`continue_accepted_endzone.png`);
4. `M`: walk RIGHT → the **MSX-logo transition** (`m2_transition_msx_logo.png`) → loading (flags 0) → **score reset 7800→0** → **fresh M2 spawn px 74.6** (php 74, gren 10) → **train gameplay: POWs + soldiers on the cars, px 404, score 3800** (`m2_train_entry_pow_soldiers.png`, `m2_train_gameplay_px404.png`).

The session-4/5 open item **"Mission 2 entry NOT claimed" is now CLAIMED with PNG evidence**.

### S6-F4/F5

- gsmap lives `0x0475A8` reads `0xFFFF` constant through everything — **not live** in this context (task-13 re-confirmed); the 1UP HUD is the only lives truth.
- The forensics frames perturb determinism (2 teardown events vs 1; banner c=95 vs c=107) — but lives5/6/7 are bit-identical, and the bare predicate reproduces session-5.

### Honest limits & next

- Mission-2 gameplay **beyond the walk probe** is NOT claimed (no M2 policy, no M2 clear).
- Next: (a) re-derive the px/walker/entity vocabulary on the **M2 train route** (moving-ground combat — riding the cars while soldiers board); (b) fix the harness `alive()` predicate for scene teardowns; (c) a live lives address or 1UP-HUD OCR.

Machine-readable record: `data/games/SLUS-01212/truck_evidence/truck_resolution_session6.json` (+ `session6/` PNGs, 7)."""

if __name__ == "__main__":
    s, d = gh_api.req("/repos/Sh-TB/Ps1ai/issues/5/comments",
                      method="POST", payload={"body": B5})
    print("HTTP", s, "->", d.get("html_url", d) if isinstance(d, dict)
          else d)
