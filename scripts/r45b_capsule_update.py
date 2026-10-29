#!/usr/bin/env python3
"""r45b_capsule_update.py — R45 (buzzybee, the 40% track, Issue #6):
append the round event to the buzzybee capsule and replace
next_experiment."""
from __future__ import annotations

import json
import time

P = "/home/z/my-project/ps1ai/data/knowledge/buzzybee/capsule.json"


def main():
    c = json.load(open(P))
    ev = c["events"]
    now = time.strftime("%FT%TZ", time.gmtime())

    ev.append({
        "what": "R45 environment rebuild + the tiered-margin round "
                "(disclosed): the sandbox rollback lost the disc AND "
                "the r43b gs1 checkpoint; the disc was rebuilt "
                "internet-first BEFORE the boot (upstream "
                "NDR008/BuzzyBee@master EXE sha256 9b0bfc08... = "
                "byte-identical to the r23/r42b/r44b reference; the "
                "committed r23t2 wrap script output sha256 042b94bb... "
                "= byte-identical to the capsule-recorded artifact; "
                "0 boots) and boot 1 rebuilt the gs1 checkpoint "
                "in-process (settle 900f -> START -> gs1 -> "
                "serialize; the r42b precedent).  The round: arm A = "
                "bot_policy5 verbatim, arm B = bot_policy7 (the "
                "TIERED margin: GM 8 pre-danger t_enter>20 / GM 12 "
                "in-window; the policy6 flower-proximity selection "
                "and the bail unchanged), 1500f/arm on the shared "
                "checkpoint.  HONEST NEGATIVE (the third consecutive "
                "score-tie): B 0 hits / 6-of-6 / score 1401 TIE / "
                "caused 1 (<2) - the tiered margin genuinely engaged "
                "(GM8 held 453 dodge frames with ZERO hits = the "
                "looser tier is safe at this checkpoint) but the "
                "outcomes CONVERGED with arm A (score 1401, hp 5666, "
                "6 passes, flaps 82/81).  CONSTRUCTIVE: the 1401 "
                "line is INVARIANT across four policy families (A "
                "recipe, policy5, policy6, policy7) = the "
                "checkpoint's fixed reward structure (6 wasp passes "
                "per 1500f), NOT a policy deficit; the flowers drive "
                "HEALTH (+997 each), not score.  Breaking >= 1550 "
                "requires leaving the dodge axis: per-frame score "
                "telemetry (0x8005883C is readable per frame) to "
                "locate the actual score-source events, then either "
                "a longer horizon (more passes) or targeting the "
                "discovered source.  The margin-floor revert protocol "
                "did not fire (0 hits).",
        "status": "VERIFIED",
        "evidence": "scratch/r45b/ (boots_used.json cap 1/1 + "
                    "frames_A/B.jsonl + metrics_r45b.json + "
                    "boot_log_r45b.json); report "
                    "docs/issue6_r45b_report.md",
        "ts": now})

    c["next_experiment"] = {
        "id": "R46",
        "budget": "0-1 boots (restore-only from the r45b gs1 "
                  "checkpoint while it survives)",
        "hypothesis": "the score SOURCE is identifiable: per-frame "
                      "u32 reads at 0x8005883C during one bot_policy5 "
                      "arm (1500f) localize every score delta to its "
                      "frame + game state (wasp pass completion vs "
                      "dodge timing vs idle), converting the 1401 "
                      "invariant from a curiosity into a mechanism; "
                      "if pass-completion dominates, the >= 1550 "
                      "lever is a longer CAP_F (more passes) with "
                      "the dominance constraints unchanged (0 hits, "
                      "caused >= 2)",
        "method": "restore-only, 1 boot max: instrument run_arm with "
                  "a per-frame score read (cheap: one u32 per frame "
                  "into the jsonl) -> one bot_policy5 arm -> the "
                  "score-source table -> decide the R47 lever from "
                  "the mechanism, not from another policy variant",
    }

    json.dump(c, open(P, "w"), indent=1, ensure_ascii=False)
    print(f"buzzybee capsule updated: {len(ev)} events; "
          f"next={c['next_experiment']['id']}")


if __name__ == "__main__":
    main()
