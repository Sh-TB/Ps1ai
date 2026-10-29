#!/usr/bin/env python3
"""r44_capsule_update.py — R44 (the 60% track, Issues #5/#9/#10):
append the round events to the msx capsule and replace
next_experiment.

Events (all honest-labeled, evidence-backed):
  1. stage-1 FALSIFICATION: the deaths=0 clean-resolve premise is
     unreachable from the shallow anchor - the c86/87 armor-zone death
     is DETERMINISTIC (bit-identical worlds through the divergence
     point across THREE boots in two rounds: R43 boot-5 c87, R44
     boot-1 c86 chunk-end, R44 boot-2 c86 chunk-end; px
     279/487.9/770.2/1044.7/951.1 at c0/20/40/60/80, score
     0/900/1200/2100/2700, php 79 at c80).  The only deaths=0 rebuild
     on record (r42t1) came from the LOST deep anchor r38_ckpt.
  2. R44 harness lessons: sensor ORDER (alive before leak at BOTH
     chunk ends - the boot-1 c86 mislabel and the boot-3 c21 mislabel
     were the same defect mirrored) + the WRAP signature named (px
     65494-65535 = the scene-transition world, seen ALIVE at R43
     boot-5 c160 php 242 and at R44 boot-3 c20-end; it must never feed
     max_px, the leak guard, or a frontier save - the sane-world clamp
     0<=px<5000) + the wrap-junk frontier save invalidated
     (r44_wrap_junk_boot3, forensics).
  3. fallback (b) executed (boots 3-4 reallocated, disclosed; cap 4/4):
     900-chunk push from the TAINTED r43_postkill (post-restart
     checkpoint-respawn lineage) - 8 continue-rescued deaths disclosed,
     score 4501->13704, the policy held at the 1272 clamp
     (clamp_clear loop), mission_end NEVER latched (0 latches;
     consistent with the R43 negative) - and the boot-7 FRONTIER LOSS
     REPAIRED: r44_frontier_b (px 1275.2) + r44_frontier_a (px 1341.2)
     saved with the sane-world clamp.
  4. next_experiment = R45 (fallback (a)): the 0x4054 soft-soldier
     HP-word readout from the saved frontier postures (restore-only).
"""
from __future__ import annotations

import json
import time

P = "/home/z/my-project/ps1ai/data/knowledge/msx/capsule.json"
EV_DIR = ("data/games/SLUS-01212/truck_evidence/r44/ "
          "(boots_used.json cap 4/4 + r44_boot[1,2]_s1 + "
          "r44_boot[3,4]_s3 jsonl+reports; scratch/r44/pngs local-only; "
          "buzzybee 40%-track round in scratch/r44b + "
          "docs/issue6_r44b_report.md)")


def main():
    c = json.load(open(P))
    ev = c["events"]
    now = time.strftime("%FT%TZ", time.gmtime())

    ev.append({
        "what": "R44 stage-1 FALSIFICATION (the capsule hypothesis "
                "premise): the clean deaths=0 resolve posture is "
                "UNREACHABLE by rebuild from the shallow anchor "
                "issue5_m1_start - the armor-zone death at c86/87 (px "
                "951.1, php 79 at c80, score 2700, mid-engage) is "
                "DETERMINISTIC: bit-identical world traces through the "
                "divergence point across THREE independent boots in "
                "two rounds (R43 boot-5 c87 chunk-start sensor, R44 "
                "boots 1+2 c86 chunk-end sensor; px "
                "279/487.9/770.2/1044.7/951.1 and score "
                "0/900/1200/2100/2700 identical at c0/20/40/60/80).  "
                "The only deaths=0 rebuild on record (r42t1) rebuilt "
                "from the LOST deep anchor r38_ckpt and never walked "
                "this zone.  Under the shipped policy the clean-"
                "resolve chain cannot START from the shallow anchor; "
                "the R43 negative therefore generalizes: until a deep "
                "deaths=0 posture source exists, the INTERACTIVE M2 "
                "entry stays unclaimable.",
        "status": "VERIFIED",
        "provenance": {"evidence": EV_DIR, "source": "R44 boots 1-2 "
                       "(r44t1_clean_resolve.py stage 1 x2, the "
                       "dynamic restart guard + the deaths=0 validity "
                       "requirement)"}})

    ev.append({
        "what": "R44 harness lessons (all rooted in measured failures, "
                "fixes applied in-round): (1) SENSOR ORDER at BOTH "
                "chunk ends - the alive/death check must precede the "
                "restart-leak check (boot 1 c86 and boot 3 c21 were "
                "the same defect mirrored: a mid-chunk death / a dead "
                "transition world got mislabeled restart_leak); "
                "(2) the WRAP SIGNATURE named: px 65494-65535 is the "
                "scene-transition world (seen ALIVE at R43 boot-5 "
                "c160 php 242 and at R44 boot-3 c20-end) - the "
                "sane-world clamp 0<=px<5000 now gates max_px, the "
                "leak guard, and frontier saves; the boot-3 frontier "
                "save that fired on the wrapped px (65494.4) was "
                "INVALIDATED and preserved as r44_wrap_junk_boot3 "
                "(forensics); (3) the corrected-filings precedent "
                "extended to same-entry outcome corrections (boots "
                "1-3 amended in place, disclosed).",
        "status": "OBSERVED",
        "provenance": {"evidence": EV_DIR, "source": "R44 boots 1-3 "
                       "(ledger outcome corrections)"}})

    ev.append({
        "what": "R44 fallback (b) executed (boots 3-4 reallocated from "
                "the pre-run plan, disclosed in the ledger; cap 4/4): "
                "the px-1272 clamp push from the on-disk TAINTED "
                "r43_postkill (post-restart checkpoint-respawn "
                "lineage, never a clean claim).  Boot 4 = the full "
                "900-chunk latch attempt: 8 continue-rescued deaths "
                "(counted + disclosed, the CHUNK_END_DEATH/chunk-start "
                "pairs), score 4501->13704 (the R43 boot-7 "
                "deterministic reproduction), the policy held at the "
                "1272 clamp in clamp_clear, mission_end NEVER latched "
                "(0 latches) - the R43 negative re-confirmed from a "
                "second independent run.  THE BOOT-7 FRONTIER LOSS "
                "REPAIRED: frontier postures SAVED with the "
                "sane-world clamp - r44_frontier_b (px 1275.2) and "
                "r44_frontier_a (px 1341.2, past the 1285-1310 wave).",
        "status": "OBSERVED",
        "provenance": {"evidence": EV_DIR, "source": "R44 boots 3-4 "
                       "(stage 3, the fallback-b pivot)"}})

    c["next_experiment"] = {
        "budget": "cap 2 disclosed pre-run (restore-only from the "
                  "saved r44 frontier postures; a rebuild boot only "
                  "if a frontier is lost, disclosed)",
        "hypothesis": "R45 = fallback (a), the deferred 0x4054 "
                      "soft-soldier HP-word readout: from "
                      "r44_frontier_a (px 1341.2) / r44_frontier_b "
                      "(px 1275.2) the aimed-fire readout at slots "
                      "13/16 (x 1150-1450, corpse/wreck excluded) "
                      "reads the soft-soldier HP word per tap "
                      "(+0x8E/+0xA4/+0x9E candidates) against "
                      "verified score gains - converting the last "
                      "unknown word into verified semantics with the "
                      "unchanged oracle (walker words + verified "
                      "score gains + alive 0x0EE518; never +0x8E in "
                      "any oracle).  The INTERACTIVE M2 entry remains "
                      "gated on a clean (deaths=0, no-restart) deep "
                      "resolve posture - no such source exists after "
                      "the r38_ckpt loss; producing one is a LATER "
                      "round's problem, not a fallback lever.",
        "method": "boot -> restore r44_frontier_a -> identify the "
                  "soft-soldier entity slots in x 1150-1450 "
                  "(corpse/wreck excluded) -> scripted aimed-fire "
                  "taps (disclosed inputs) -> per-tap word deltas "
                  "vs score deltas -> the readout table -> report; "
                  "repeat from r44_frontier_b if the slot set is "
                  "empty at 1341."}
    c["meta"]["last_updated"] = now
    c["meta"]["last_commit_note"] = (
        "R44 (60% track): stage-1 FALSIFIED (the c86/87 armor-zone "
        "death is deterministic 3/3 across R43/R44 - bit-identical "
        "worlds through the divergence; deaths=0 unreachable from the "
        "shallow anchor; r42t1's clean rebuild came from the LOST deep "
        "anchor) + harness lessons (sensor order both chunk ends, the "
        "px 65494-65535 wrap signature, sane-world clamp, wrap-junk "
        "frontier invalidated) + fallback (b): 900-chunk push from the "
        "tainted posture, 8 continue-rescued deaths disclosed, no "
        "latch (the R43 negative re-confirmed), FRONTIERS SAVED px "
        "1275.2 + 1341.2 (the boot-7 loss repaired); next_experiment "
        "= R45 fallback (a) the 0x4054 HP-word readout from the "
        "frontiers.")

    json.dump(c, open(P, "w"), indent=1)
    print("msx capsule: events", len(ev), "next_experiment = R45 "
          "(fallback a)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
