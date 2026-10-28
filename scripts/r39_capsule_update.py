#!/usr/bin/env python3
"""r39_capsule_update.py — R39 Task 6: reconcile the MSX knowledge
capsule against the R39 live evidence and append the new events.

Rules honored (R38 schema + R39 task):
 - every status change / new event carries provenance (evidence path
   + source) and the honest status label (OBSERVED unless the artifact
   identity was re-verified);
 - the R38 "mission-timer restart" interpretation of the trial
   outcomes is marked CONTRADICTED: every recorded
   banner_expired_restart in the R38/R39 series was a mid-chunk DEATH
   (px == 0.0 in the RESTART_SEEN events; the death handler never
   ran) — the trials measured time-to-first-death;
 - the +0x8E rule is untouched (never HP; not in any oracle);
 - no claim is promoted beyond its evidence.
"""
import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
CAPSULE = os.path.join(_REPO, "data", "knowledge", "msx", "capsule.json")

R39_EVID = ("data/games/SLUS-01212/truck_evidence/r39/"
            "r39_boot_reports.json + scratch/r39/r39_boot1.jsonl + "
            "scratch/r39/r39_boot2.jsonl (R39 boots 1-6, ledger "
            "scratch/r39/boots_used.json)")

NEW_EVENTS = [
    {
        "what": "R39 boot-1 matched-anchor delivery A/B (one boot, "
                "anchor r39_anchor = the first aa_kill chunk with the "
                "chopper inside 160px, BASE reproduced R38 trialAA1 "
                "exactly first): the 15f-chunked in-policy J1 delivery "
                "connected 0/8 while the Session-3 ATOMIC script "
                "delivery (same anchor, same 2400f budget) connected "
                "2/12 (verified hp_a4 300->200 and 200->100). The "
                "delivery mechanism, not geometry alone, is the "
                "first-order connect-rate factor.",
        "status": "OBSERVED",
        "provenance": {"evidence": R39_EVID,
                       "source": "R39 boot 1 (commit 1fa362b+)"}},
    {
        "what": "R39 connect-band revision from release-frame evidence: "
                "EVERY verified chopper connect sits at cycle-start "
                "|dx| 13.7-29 (Session-3 4x, boot-1 atomic 2x, boot-4 "
                "in-policy 1x) while the close hovers at |dx| 3-8.6 "
                "missed 4/4 (the UP-lob arcs over a too-close target) "
                "and throws beyond 30 never connected (0/5+ across "
                "arms). The R39 aa rule throws only inside "
                "[AA_THROW_DX_MIN=10, AA_THROW_DX=35].",
        "status": "OBSERVED",
        "provenance": {"evidence": R39_EVID,
                       "source": "R39 boots 1+4+6 + session-3 "
                                 "report_chk_J1_051704.json"}},
    {
        "what": "R39 hover/anchor fact: the chopper's patrol includes "
                "multi-second HOVERS at x 1132-1155 near the D7 clamp "
                "wall (frame capture: frozen at 1132.3 for 18+ frames "
                "with st flipping 0xAA94->0xABDC; census: x=1155.1 "
                "held across 75f), so a player anchored at the clamp "
                "(px ~1164) sees |dx| inside the connect band every "
                "patrol period. Walking TOWARD the chopper (boot-3 "
                "v2.1) dragged the player into the 992+ wave zone and "
                "was reverted.",
        "status": "OBSERVED",
        "provenance": {"evidence": R39_EVID,
                       "source": "R39 boot-1 frame telemetry + boot-2/3 "
                                 "per-chunk traces"}},
    {
        "what": "R39 harness correction (supersedes the R38 trial "
                "outcome reading): EVERY banner_expired_restart "
                "recorded by the r38t2/r39 trial harnesses (R38 "
                "trialA1/A2 c268, trialAA1/AA2 c227, R39 BASE c227) "
                "was actually a mid-chunk DEATH (px == 0.0, sec "
                "[0,0] in the RESTART_SEEN events; the chunk-end "
                "restart check fired before the next-iteration death "
                "handler). There is NO evidence of a mission-timer "
                "restart wall at c227/c268; those trials measured "
                "time-to-first-death. R39's fixed harness waits out "
                "the respawn and passes the game's continue screen "
                "with the issue-4 recover_v2 START tap (counted and "
                "disclosed separately from deaths).",
        "status": "CONTRADICTED",
        "provenance": {"evidence": "scratch/r38/trials.jsonl "
                                   "RESTART_SEEN px=0.0 + "
                                   "scratch/r39/r39_boot2.jsonl",
                       "source": "R39 boot-4/5/6 harness analysis"}},
    {
        "what": "R39 in-policy atomic delivery connects live: the "
                "v2.2 aa_kill rule (aim locked at cycle start, the 19f "
                "J1 window finished atomically, band-gated throws, "
                "anchor positioning, the R38 cooldown rain-hop) landed "
                "verified hp_a4 drops in two independent boots "
                "(boot-4 c143: 300->200 with score +200; boot-6 c271: "
                "300->200). 13 throws per 300-chunk campaign window at "
                "the current engagement share; the chopper was NOT "
                "killed in-policy yet (2 of 3 connects needed).",
        "status": "OBSERVED",
        "provenance": {"evidence": R39_EVID,
                       "source": "R39 boots 4+6 (v2.2 rule, commit "
                                 "post-1fa362b)"}},
]

NEW_NEXT_EXPERIMENT = {
    "budget": "2 boots, ~40k frames (the R39 ledger closed at 6 "
              "disclosed boots: 1 baseline+A/B, 1 treatment, "
              "amendments 2->3->4->5->6 pre-run)",
    "hypothesis": "R40: the connect rate is no longer the delivery "
                  "(atomic J1 connects in-policy) but the THROW "
                  "OPPORTUNITY share: aa_kill held only 76/300 chunks "
                  "(25%) while engage held 118 (39%) - the policy "
                  "locks onto non-queue enemies (wall mortarman / wave "
                  "soldiers) while the chopper is the pending-queue "
                  "blocker. Rank the queue entities above non-queue "
                  "enemies inside the pin context (or verify whether "
                  "the mortarman is itself a queue entity - killing it "
                  "also stops the lethal rain), then the existing "
                  "atomic cadence should land the remaining 2 connects "
                  "inside one campaign window -> queue clear -> pin "
                  "release -> the mission-end chain.",
    "method": "boot 1: census WHO engage locks onto during the pin "
              "(read-only mode/threat trace) + the grenade flight "
              "time from the frame-level census (for a future "
              "arrival-band gate); boot 2: the queue-priority trial "
              "from r38_ckpt with the boot-6 harness (deaths + "
              "continues handled, per-throw telemetry). Oracle = "
              "chopper hp_a4 300->0 + the section release + the "
              "banner predicate; never +0x8E."
}


def main():
    with open(CAPSULE) as f:
        cap = json.load(f)
    ev = cap.setdefault("events", [])
    have = {e.get("what", "")[:60] for e in ev}
    added = 0
    for e in NEW_EVENTS:
        if e["what"][:60] in have:
            continue
        ev.append(dict(e))
        added += 1
    cap["next_experiment"] = NEW_NEXT_EXPERIMENT
    meta = cap.setdefault("meta", {})
    meta["r39_reconciled"] = (
        "R39: delivery-fidelity A/B, connect band [10,35] with the "
        "13.7 floor, hover/anchor fact, the death-misreport "
        "correction of the R38 trial outcomes, in-policy atomic "
        "connects; next_experiment replaced (the blocker is the "
        "throw-opportunity share, not the delivery)")
    with open(CAPSULE, "w") as f:
        json.dump(cap, f, indent=1)
        f.write("\n")
    print(f"capsule updated: +{added} events, next_experiment replaced")

    # validate through the shipped loader (schema + provenance
    # requirements) and re-verify the artifact hashes
    sys.path.insert(0, _REPO)
    from ps1play.knowledge.capsule import Capsule
    cap2 = Capsule.load(CAPSULE)
    n_art = cap2.verify_artifacts()
    print(f"validate: OK ({len(cap2['events'])} events, "
          f"{n_art} artifacts hash-verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
