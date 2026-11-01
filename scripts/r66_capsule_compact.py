#!/usr/bin/env python3
"""r66_capsule_compact.py — the R66 final-mile fix, part 2: bring the
shipped msx capsule back under the 64 KiB design cap WITHOUT losing a
single fact.  The R66 session committed the capsule AFTER the release
gate had run (the 19:34 edit never re-entered the suite), so the
shipped state broke two shipped-validation tests: event 55 carried the
non-schema status 'TESTED' (fixed first, -> OBSERVED) and the four new
R66 events pushed the canonical size to 67,378 B > 65,536 B.

This script compacts ONLY R66-owned prose (events 52-55 + the R67
next_experiment) and drops the stale R45-era top-level last_commit_note
(superseded by meta.last_commit_note; nothing reads it).  Every number,
address, status and evidence pointer is preserved; the full narratives
already live in reports/r66/, the worklog and the truck_evidence files.
Git history keeps every prior capsule byte-for-byte.
"""
import json
import sys

sys.path.insert(0, ".")
from ps1play.knowledge import Capsule  # noqa: E402

P = "data/knowledge/msx/capsule.json"

EVENTS = {
    52: (
        "R66 gate diagnostics (the R53 lever): the per-skip GATE_DIAG dump "
        "(13 skips, r66_boot3_s2a.jsonl) ROOT-CAUSED the R52 starvation - "
        "the R50/R51 corridor predicate counted non-absorbing, non-paying "
        "entities as blockers: the bullet-TRANSPARENT 0xab94 wasp (8 "
        "rejections) and in-flight projectile_air rows "
        "(0xbdf8/0x1be0/0x2950/0x9558/0xac64); the player never advanced "
        "(px 1255.2 across all skips).  A protocol-predicate defect in the "
        "MSX workstream, not an observer/runtime defect."
    ),
    53: (
        "R66 the +500 CAPTURED AT THE PAY FRAME (R48-R52 never reached "
        "it): pass B (corrected predicate: blockers must absorb the bullet "
        "or register the payment) tap 6: score 7702->8202 (+500) at tail "
        "f1 = the bullet-impact frame, victim pre-hit; 0x5b0c registration "
        "at tail f3; slot12@0xa0 pulse (257->2, rec 4) co-timed.  Two more "
        "+1000s (0x42bc tail f3; 0x3f48 tail f4): magnitude table +500 x4 "
        "vs +1000 x7.  PAY-FRAME LAW: the accumulator pays on the internal "
        "damage event ~2 frames BEFORE the visible registration (3/3 "
        "captures).  +500 is not confined to 0x42bc connects; kills do "
        "not always pay (0xa718->0x515c, dscore=0)."
    ),
    54: (
        "R66 the accumulator candidate RESOLVED as a witness, not a "
        "discriminator: slot12@0xa0 dips to 2 co-timed with EVERY kill "
        "registration (n=2) but its instant value is churn phase - a "
        "banked +1000 pay frame also shows 257.  The 19-offset target-slot "
        "pay-frame vectors separate this round but identity words "
        "dominate; the discriminator stays PENDING until n>=2 +500 "
        "captures exist (the delay signature tail-f1 vs tail-f3/f4 is the "
        "lead)."
    ),
    55: (
        "R66 the FOURTH RUNTIME GAME: metal_slug_x registered (adapter "
        "0.2.0 + the deterministic Mission-1 rules policy with the "
        "corrected corridor predicate; 19 offline tests incl. the "
        "isolation suite).  play metal_slug_x: two byte-identical runs "
        "(ep1 death 1666f score 1100 at the armored truck, px ~1164; ep2 "
        "388f score 1300); legal inputs only, zero RAM writes, no "
        "training.  Mission 1 NOT cleared - the truck is the next "
        "blocker.  The frontier rebuild re-proven 6-for-6 "
        "(px 1224.9/1254.8)."
    ),
}

NEXT_EXP = {
    "id": "R67",
    "budget": "restore-only arms from the r66 frontiers while they survive "
              "on disk (a rebuild boot only if lost, disclosed)",
    "hypothesis": "the delay signature (+500 tail f1, +1000 tail f3/f4) "
                  "plus the 19 candidate offsets separate the magnitudes "
                  "once n>=2 +500 captures exist; the corrected gate makes "
                  "fresh 0x4054 targets reachable at the frontiers",
    "method": "restore r66_frontier_a/b -> CONNECT taps preferring fresh "
              "0x4054 with the pay-frame telemetry verbatim until TWO +500 "
              "captures land -> the zero-overlap test on the widened set "
              "-> the product-path truck campaign (grenade sequencing "
              "hp_a4 300/-100; soldiers before the truck gun) as the "
              "separate gameplay track",
    "m2_gate_note": "unchanged - interactive M2 entry stays gated on a "
                    "clean (deaths=0, no-restart) deep resolve posture",
}


def main():
    d = json.load(open(P))
    n0 = len(Capsule(d).to_json().encode())

    for i, text in EVENTS.items():
        assert d["events"][i]["what"], i
        d["events"][i]["what"] = text

    old_exp = d.get("next_experiment", {})
    assert old_exp.get("id") == "R67", old_exp.get("id")
    d["next_experiment"] = NEXT_EXP

    dropped = d.pop("last_commit_note", None)
    assert dropped is None or "R45" in dropped[:8], \
        "expected the stale R45 note (or already dropped)"

    # stale round-bookkeeping reconcile notes (R39/R43) — preserved in
    # git history and in each round's own report; meta.last_commit_note
    # (R66) stays as the current note
    for k in ("r39_reconciled", "r43_reconciled"):
        if d["meta"].pop(k, None) is not None:
            print(f"meta.{k} dropped")

    json.dump(d, open(P, "w"), indent=1, ensure_ascii=False)
    open(P, "a").write("\n")

    c = Capsule.load(P)
    c.validate()
    n1 = c.size_bytes()
    print(f"size {n0} -> {n1} (cap 65536, margin {65536 - n1})")
    print(f"top-level last_commit_note dropped: "
          f"{len(dropped) if dropped else 0} B (already gone = 0)")
    assert n1 < 65536, "still over the cap"


if __name__ == "__main__":
    main()
