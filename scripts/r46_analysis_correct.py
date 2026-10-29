#!/usr/bin/env python3
"""r46_analysis_correct.py — R46 offline correction (no boot).

The in-runner kill-table verdict mis-fired for two reasons:
  1. "chip" was any non-zero wide-net word delta - but 0x8c/0x94
     (and 0x8e/0x96) are position/animation words that churn on
     EVERY tap including the zero-input control (the R45 finding:
     +0x8E = screen-x).  Churn is not damage.
  2. Attribution ignored the R45 corpse evidence: the first-tap
     +500/+1000 events coincide with AIR entities entering the
     0x4be4 corpse state (R45 frontier_a tap 1: slots 33+23), not
     with damage to the targeted ground soldier.

This script rebuilds the kill table from the R46 jsonl + the R45
jsonl (the attribution key) with the CORRECT rules:
  - a death = the slot's st becomes 0x4be4 with x==0 (corpse);
  - candidate HP-word check = ONLY 0x9E/0xA4 (0x8E is screen-x,
    established R45; 0x8c/0x94/0x96/0xa0 = churn);
  - a prior-tap score event is attributable to slot S only if S
    was the target AND S died in that tap (kills score AT death
    is the open question - recorded, not assumed).

It amends the R46 boot-ledger entry 1 with outcome_corrected per
the corrected-filings precedent and writes the corrected table to
the evidence directory.
"""
from __future__ import annotations

import json
import os
import time

_REPO = "/home/z/my-project/ps1ai"
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r46")
R45_JSONL = os.path.join(_REPO, "data", "games", "SLUS-01212",
                         "truck_evidence", "r45", "r45_boot2_s2.jsonl")
R46_JSONL = os.path.join(EVID, "r46_boot1.jsonl")
LEDGER = os.path.join(_REPO, "scratch", "r46", "boots_used.json")

CORPSE_ST = 0x4BE4
CAND = ("0x9e", "0xa4")          # the live HP-word candidates
CHURN = ("0x8c", "0x8e", "0x94", "0x96", "0xa0", "0xa8")


def taps_of(path, frontier=None):
    """TAP events in order; the R46 runner's aimed taps lack the
    frontier field (the control taps carry it) - attach the current
    frontier from the FRONTIER_RESTORED / CENSUS_GROUND events."""
    out = []
    cur = None
    for line in open(path):
        e = json.loads(line)
        if e.get("ev") in ("FRONTIER_RESTORED", "CENSUS_GROUND"):
            cur = e.get("frontier")
        if e.get("ev") != "TAP":
            continue
        fr = e.get("frontier") or cur
        if frontier and fr != frontier:
            continue
        e = dict(e, frontier=fr)
        out.append(e)
    return out


def correct_pass(taps, label):
    """Rebuild the per-death table with the corrected rules."""
    rows = []
    seen = set()
    for i, t in enumerate(taps):
        for s, ent in (t.get("ent_after") or {}).items():
            si = int(s)
            if ent["st"] == CORPSE_ST and ent["x"] == 0.0 \
                    and si not in seen and si != 10:
                seen.add(si)
                # find the pre-death identity + candidate-word history
                pre = None
                cand_hist = []
                targeted = []
                for j in range(i + 1):
                    tj = taps[j]
                    ea = (tj.get("ent_after") or {}).get(s)
                    wd = (tj.get("word_deltas") or {}).get(s, {})
                    if ea and not (ea["st"] == CORPSE_ST
                                   and ea["x"] == 0.0):
                        pre = ea
                        cand_hist.append(
                            (tj["tap"], {c: wd.get(c, 0)
                                         for c in CAND}))
                    if (tj.get("target") or {}).get("slot") == si:
                        targeted.append(
                            {"tap": tj["tap"],
                             "dscore": tj.get("score_delta")})
                rows.append({
                    "pass": label, "slot": si,
                    "pre_death_st": hex(pre["st"]) if pre else None,
                    "pre_death_h": pre["h"] if pre else None,
                    "air_at_restore": (pre or {}).get("h", 0) > 80,
                    "death_tap": t["tap"],
                    "death_dscore": t.get("score_delta"),
                    "targeted_history": targeted,
                    "candidate_word_hist": cand_hist,
                    "cand_nonzero_when_alive": [
                        (tp, d) for tp, d in cand_hist
                        if any(d.values())]})
    return rows


def main():
    r46_a = correct_pass(taps_of(R46_JSONL, "r45_frontier_a"),
                         "R46/r45_frontier_a")
    r46_b = correct_pass(taps_of(R46_JSONL, "r45_frontier_b"),
                         "R46/r45_frontier_b")
    r45_a = correct_pass(taps_of(R45_JSONL, "r45_frontier_a"),
                         "R45/r45_frontier_a")
    out = {
        "schema": "ps1play.r46-corrected/1",
        "generated": time.strftime("%FT%TZ", time.gmtime()),
        "rules": {
            "death": "st->0x4be4 with x==0 (corpse row)",
            "candidates": "0x9E/0xA4 only (0x8E=screen-x per R45; "
                          "0x8c/0x94/0x96/0xa0/0xa8=churn - they "
                          "move in the ZERO-INPUT control tap)",
            "attribution": "the R45 corpse table is the key: the "
                           "first-tap +500/+1000 coincide with AIR "
                           "corpses (R45 tap1 slots 33+23), not with "
                           "the targeted ground soldier"},
        "deaths": r45_a + r46_b + r46_a,
    }
    # the corrected verdict summary
    s20 = [d for d in out["deaths"] if d["slot"] == 20
           and not d["air_at_restore"]]
    out["corrected_verdict"] = {
        "slot20_signature": [
            {"pass": d["pass"], "death_tap": d["death_tap"],
             "death_dscore": d["death_dscore"],
             "candidate_words_when_alive": d["cand_nonzero_when_alive"]}
            for d in s20],
        "reading":
            "the slot-20 ground soldier died with the flat +100 at "
            "the death tap in ALL THREE readouts (R45-a tap2, R46-b "
            "tap2, R46-a tap2) with NO 0x9E/0xA4 movement while "
            "alive - the R45 one-hit SIGNATURE replicates 3/3 "
            "deterministically for this entity; the class-wide "
            "one-hit reading stays UNPROVEN: the >= 3 distinct-kill "
            "bar was NOT met (the frontier worlds hold ~2 ground "
            "soldiers each; the second soldier died with dscore 0 "
            "at taps 11 - no +100 at death), and score events "
            "include +100 with NO tracked death (R45 taps 3/9) and "
            "deaths with NO score (R45 tap11 ground+air) - "
            "attribution stays the open problem",
        "harness_lessons": [
            "the ground-only census filter discarded the air-corpse "
            "evidence that attributes the +500/+1000 first-tap "
            "events (R46 defect; R45 tracked all kinds)",
            "the wreck/fire-state filter (0xA44C only) missed the "
            "evolved burning states (0xa264/0xa414; a landed shell "
            "burns on the ground) - 12/16 frontier_b taps were "
            "fired at an unkillable ground fire (dscore 0 x12)",
            "the in-runner verdict counted position churn as HP "
            "chip - the REFUTED verdict it printed is WITHDRAWN "
            "here (corrected-filings precedent)",
            "the st word is a STATE HANDLER, not identity: the "
            "same soldier reads 0x4054/0x42bc/0x5b0c/0x6730 across "
            "taps - class labels must use the pre-death row, and "
            "0x4054 vs 0x42bc are STATES of one soldier class"],
    }
    path = os.path.join(EVID, "corrected_kill_table.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("corrected table ->", path)
    for d in out["deaths"]:
        print(f"  {d['pass']}: slot {d['slot']} "
              f"st {d['pre_death_st']} h {d['pre_death_h']} "
              f"death_tap {d['death_tap']} dscore "
              f"{d['death_dscore']} targeted {d['targeted_history']}")
    # ---- ledger amendment (same entry, corrected-filings) ---------
    led = json.load(open(LEDGER))
    for ent in led["log"]:
        if ent["n"] == 1 and "outcome_corrected" not in ent:
            ent["outcome_corrected"] = (
                "the in-runner verdict REFUTED is WITHDRAWN: the "
                "kill-table counted position churn (0x8c/0x94/0x8e/"
                "0x96 move in the zero-input control tap) as HP chip "
                "and ignored the R45 air-corpse attribution (the "
                "+500/+1000 first-tap events = air entities dying, "
                "R45 tap1 slots 33+23).  Corrected reading: the "
                "slot-20 one-hit SIGNATURE (flat +100 at death, no "
                "0x9E/0xA4 movement) replicates 3/3 (R45-a, R46-b, "
                "R46-a); the class-wide >= 3 distinct-kill bar NOT "
                "met (second soldier died +0; +100 events exist with "
                "no tracked death) -> UNRESOLVED/PARTIAL, the HP-"
                "word hunt stays open.  Harness lessons: ground-only "
                "filter over-pruned attribution evidence; the wreck/"
                "fire filter missed the evolved burning states "
                "(12/16 frontier_b taps wasted on an unkillable "
                "ground fire); see "
                "truck_evidence/r46/corrected_kill_table.json")
    json.dump(led, open(LEDGER, "w"), indent=1)
    print("ledger entry 1 amended with outcome_corrected")
    # the corrected per-pass one-hit tally for the capsule
    ok = [d for d in s20 if d["death_dscore"] == 100
          and not d["cand_nonzero_when_alive"]]
    print(f"slot-20 signature confirmations: {len(ok)}/3 "
          f"(R45-a, R46-b, R46-a)")


if __name__ == "__main__":
    main()
