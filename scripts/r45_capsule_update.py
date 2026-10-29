#!/usr/bin/env python3
"""r45_capsule_update.py — R45 (the 60% track, Issues #5/#9/#10):
append the round events to the msx capsule and replace
next_experiment.

Events (all honest-labeled, evidence-backed):
  1. SANDBOX ROLLBACK + rebuild: the R43/R44 states (r43_postkill,
     r44_postkill, r44_frontier_a/b) are LOST to the filesystem
     rollback; issue5_m1_start (Oct 20) survived; the capsule
     contingency applied (a rebuild boot, disclosed).  Two background
     launches died silently in boot_to_demo (no jsonl event beyond
     RUN_START) — refunded per the corrected-filings precedent; the
     two-stage foreground protocol (stage-1 rebuild / stage-2
     readout) then ran clean within cap 2/2.
  2. The tainted frontier rebuild (stage 1, 48 s wall): eager saves
     r45_frontier_b (px 1254.8, census 13) + r45_frontier_a
     (px 1240+, the rolling pair); 6 deaths / 6 continue-rescues
     counted and disclosed — TAINTED lineage, never a clean claim.
  3. The 0x4054 soft-soldier HP-word readout (stage 2, restore-only
     from r45_frontier_a px 1224.9 score 6702): 1 zero-input control
     tap + 14 aimed taps vs the disclosed wide net (u16 0x88..0xA8
     step 2) + the 3 capsule candidates.  BOUNDED NEGATIVE on the
     candidates + a constructive finding:
       - +0xA4 = 0 for the soldier throughout (armored-only, the
         truck semantics hold);
       - +0x9E silent (no meaningful delta across all 15 taps);
       - +0x8E = screen-x again (drifts with movement; the 0x8C/0x94
         shadow words move in sync — no damage tracking);
       - the soldier (slot 20, st 0x4054, dx +60.8) died on the 2nd
         aimed tap with the flat +100 at the death tap — consistent
         with the ONE-HIT kill class: no word in 0x88..0xA8 behaved
         as a damage counter (n = 1 soldier, cap 2/2 spent);
       - score events: +500 (tap 1, attribution unresolved: a
         projectile gone + an off-census spawn gone — prisoner/food
         or multi-kill, OBSERVED), +100 x 3 (soldier-class kills);
       - protocol note: after the ground entities died the aimed
         taps fell back to AIRBORNE projectiles (dscore 0 — shells
         are not damageable by gunfire); the next round filters
         kind == 'enemy' for tap targets.
  4. next_experiment = R46: replicate the one-hit finding across
     >= 3 soldier kills from the SAVED r45 frontier postures
     (restore-only, cap 1 — the frontiers SURVIVE on disk), with the
     ground-only tap-target filter; the INTERACTIVE M2 entry remains
     gated on a deep deaths=0 source (a later round's problem).
"""
from __future__ import annotations

import json
import time

P = "/home/z/my-project/ps1ai/data/knowledge/msx/capsule.json"
EV_DIR = ("data/games/SLUS-01212/truck_evidence/r45/ "
          "(boots_used.json cap 2/2 with the refunded ghost entries + "
          "r45_boot2_s1/s2 jsonl+reports; scratch/r45/pngs "
          "local-only; the frontier states r45_frontier_a/b survive "
          "in the local emulator workspace)")


def main():
    c = json.load(open(P))
    ev = c["events"]
    now = time.strftime("%FT%TZ", time.gmtime())

    ev.append({
        "what": "R45 SANDBOX ROLLBACK + the disclosed rebuild: the "
                "R43/R44 states (r43_postkill, r44_postkill, "
                "r44_frontier_a/b) are LOST to the filesystem "
                "rollback; the session-5 anchor issue5_m1_start "
                "(Oct 20) SURVIVED; the capsule contingency applied "
                "verbatim (a rebuild boot only if a frontier is "
                "lost, disclosed).  Two background launches died "
                "silently inside boot_to_demo (ledger + RUN_START "
                "only) - refunded per the corrected-filings "
                "precedent; the two-stage FOREGROUND protocol "
                "(stage-1 rebuild / stage-2 readout) then ran clean "
                "inside cap 2/2 (48 s + 29 s wall).",
        "status": "VERIFIED",
        "evidence": EV_DIR, "ts": now})

    ev.append({
        "what": "R45 tainted frontier rebuild (stage 1): the eager "
                "rolling saves captured COMBAT-LIVE postures - "
                "r45_frontier_b (px 1254.8, census 13 live in the "
                "x 1150-1450 window) + r45_frontier_a; 6 deaths / 6 "
                "continue-rescues counted and disclosed; the rebuilt "
                "frontier lineage is TAINTED (never a clean claim) - "
                "the INTERACTIVE M2 gate is untouched by this round.",
        "status": "OBSERVED",
        "evidence": EV_DIR, "ts": now})

    ev.append({
        "what": "R45 the 0x4054 soft-soldier HP-word readout "
                "(restore-only from r45_frontier_a px 1224.9 score "
                "6702): 1 zero-input control tap + 14 aimed taps "
                "against the 3 capsule candidates (+0x8E/+0xA4/+0x9E) "
                "plus the disclosed exploratory wide net (u16 "
                "0x88..0xA8 step 2).  BOUNDED NEGATIVE on the "
                "candidates + a constructive finding: +0xA4 = 0 "
                "throughout (armored-only; the truck semantics "
                "hold), +0x9E silent, +0x8E = screen-x again (the "
                "0x8C/0x94 shadows move in sync - no damage "
                "tracking); the slot-20 soldier (st 0x4054, dx "
                "+60.8) died on the 2nd aimed tap with the flat "
                "+100 at the death tap = the ONE-HIT kill class - "
                "no word in 0x88..0xA8 behaved as a damage counter "
                "(n = 1 soldier; cap 2/2 spent).  Score events: "
                "+500 (tap 1, attribution unresolved - OBSERVED), "
                "+100 x 3 (soldier-class).  Protocol note for R46: "
                "the tap fallback hit AIRBORNE projectiles after the "
                "ground entities died (dscore 0) - filter "
                "kind=='enemy'.",
        "status": "VERIFIED",
        "evidence": EV_DIR, "ts": now})

    c["next_experiment"] = {
        "id": "R46",
        "budget": "cap 1 disclosed pre-run (restore-only from the "
                  "SAVED r45_frontier_a/b - they survive on disk; "
                  "the boot is the core+rom load only)",
        "hypothesis": "the soft-soldier ONE-HIT kill finding "
                      "replicates: >= 3 ground (kind=='enemy') "
                      "0x4054-class kills from the frontier postures, "
                      "each dying to a single aimed tap with the flat "
                      "+100 and NO candidate-word decrement before "
                      "death - converting the soldier class to "
                      "'one-hit, no tracked HP word' with the "
                      "unchanged oracle (walker words + verified "
                      "score gains + alive 0x0EE518; never +0x8E); "
                      "any multi-tap kill or any decrementing word "
                      "REFUTES the one-hit reading and reopens the "
                      "HP-word hunt at the non-candidate offsets",
        "method": "boot -> restore r45_frontier_b (px 1254.8, census "
                  "13) -> census -> ground-only aimed taps (kind=="
                  "'enemy', corpse/wreck excluded) -> per-tap wide "
                  "net + score deltas -> kill table; restore "
                  "r45_frontier_a for a second pass in the same "
                  "boot if kills < 3; report",
        "m2_gate_note": "the INTERACTIVE M2 entry remains gated on a "
                        "clean (deaths=0, no-restart) deep resolve "
                        "posture - no such source exists after the "
                        "r38_ckpt loss; producing one is a LATER "
                        "round's problem, not a fallback lever",
    }
    c["last_commit_note"] = (
        "R45 (60% track): sandbox rollback disclosed (the R43/R44 "
        "states lost; the anchor survived; the capsule contingency "
        "applied) + the two-stage foreground protocol after two "
        "silent background deaths (refunded per corrected-filings); "
        "tainted frontier rebuild (6 deaths/6 rescues, r45_frontier_b "
        "px 1254.8 census 13 + r45_frontier_a) + the 0x4054 readout "
        "= BOUNDED NEGATIVE on +0x8E/+0xA4/+0x9E (0xA4 armored-only "
        "0, 0x9E silent, 0x8E screen-x again) + the ONE-HIT soldier "
        "finding (flat +100 at the 2nd-tap death, no decrementing "
        "word in the disclosed 0x88..0xA8 net, n=1); next = R46 the "
        "one-hit replication (ground-only taps, restore-only cap 1).")

    json.dump(c, open(P, "w"), indent=1, ensure_ascii=False)
    print(f"capsule updated: {len(ev)} events; next={c['next_experiment']['id']}")


if __name__ == "__main__":
    main()
