#!/usr/bin/env python3
"""r67_capsule_compact.py — bring the shipped msx capsule back under
the 64 KiB design cap WITHOUT losing a single fact (the R66
compaction pattern verbatim).

The R67 session appended three long events (56-58) which pushed the
canonical size to 70,313 B > 65,536 B.  This script compacts ONLY the
R67-owned prose; every number, address, state word, rule name, status
and evidence pointer is preserved.  The full narratives live in
reports/r67/, the worklog and the truck_evidence files.  Git history
keeps every prior capsule byte-for-byte.
"""
import json
import sys

sys.path.insert(0, ".")
from ps1play.knowledge import Capsule  # noqa: E402

P = "data/knowledge/msx/capsule.json"

EVENTS = {
    56: (
        "R67 the +500 HUNT (the lever verbatim; restore-only, ledger "
        "cap 3 disclosed, all spent: env probe + frontier_a + "
        "frontier_b): 0 NEW +500 captures - the n>=2 goal NOT met, "
        "the class stands n=1 (R66).  AMENDMENT-G LESSON: the "
        "disclosed 0x5b0c gate-corpset alignment (the product-"
        "adapter contract; the dry-run finding) changed the tap "
        "order on the byte-exact frontier_b and the trajectory "
        "diverged EXACTLY at tap 6 (R66: slot16 0x1e38 +500; R67: "
        "slot18 0x540c +100) - the +500 capture is a TRAJECTORY-"
        "SENSITIVE posture, not a standing frontier property.  "
        "Landscape: both frontiers target-starved past the "
        "spawner-cluster edge (the advance walked px 1246->1540 / "
        "1254->1546, NO targetable enemy rows); fresh 0x4054 "
        "soldiers exist only AT the restore census (frontier_a: "
        "slot20) and churn out of the fresh class before the tap.  "
        "+1000 REPLICATED x2 (0x42bc pay tail f3; 0x3f48 pay tail "
        "f4 - the exact R66 st_pre->tail signature).",
    ),
    57: (
        "R67 the WIDENED-SET zero-overlap test: +500 n=1 vector vs "
        "+1000 n=6 (2 R52 + 2 R66 + 2 R67) - 19 union-net offsets "
        "separate the single +500 vector from ALL six +1000 "
        "vectors, but at n=1 the intersection IS that capture's "
        "own set (identity words dominate) - the CLASS "
        "discriminator stays PENDING until n>=2 +500.  Established: "
        "the +1000 delay signature reproduces ACROSS ROUNDS (0x42bc"
        "->tail f3 in R66 AND R67; 0x3f48->tail f4 in both) - the "
        "st_pre->delay law is the strongest live lead.  Magnitude "
        "table: +500 x4 vs +1000 x9.",
    ),
    58: (
        "R67 the PRODUCT-PATH TRUCK CAMPAIGN (policy 1.1.0->1.4.2 + "
        "adapter 0.3.0, 40 offline tests): THE ARMORED TRUCK KILLED "
        "ON THE PRODUCT PATH - T2 grenade sequencing (3 lobs x -100 "
        "vs hp_a4 300 verbatim) took it to zero, the death shot "
        "shows it AIRBORNE; ep1 score 2300 = the RECORD (prior best "
        "1300, R66).  The rule chain: T1 identity = the 0x9E88 "
        "state word (code 7) - the v1.1.0 (sc=6, h=64) identity was "
        "a FALSE-POSITIVE TRAP (ground soldiers in walk/throw "
        "states also present (6, h=64); the hold froze at px 493 on "
        "a scenery row; the read-only probe read the REAL truck "
        "live at 937.5/h64/a4=300); T3 soldiers-before-the-truck-"
        "gun (a clear-line escort holds the lob; a corridor-blocked "
        "one does not - the R49 model); the REAR FIGHT (BACK = the "
        "legal LEFT button; the loop-probe evidence: at the section "
        "pin the wave AND the truck are BEHIND the player - three "
        "identical v1.0.0-v1.3.0 forward-only deaths); T5 the "
        "outer-edge hold (90..135; the dx-52 hold LOST the gun "
        "duel); T7 the blast retreat (the 3-lobs kill exploded the "
        "player standing in the band).  CADENCE LAW (v1.2.0's "
        "regression, restored in v1.3.0): the fire cadence is part "
        "of the deterministic wave trajectory - the top-tick 12f "
        "cadence starved the wave (0 kills, the truck never "
        "entered, zero a4>=100 rows in the probe); the v1.0.0 13f "
        "rhythm reproduced the R66 record byte-exact.  Mission 1 "
        "NOT cleared: the post-kill death (the second truck / the "
        "death animation) is the named next blocker; ep2 continues "
        "from the section start (score 2300 at 366f).",
    ),
}


def main():
    c = json.load(open(P))
    ev = c["events"]
    n_r67 = 0
    for i, e in enumerate(ev):
        w = e.get("what", "")
        if w.startswith("R67 the +500 HUNT"):
            ev[i]["what"] = EVENTS[56]
            n_r67 += 1
        elif w.startswith("R67 the WIDENED-SET"):
            ev[i]["what"] = EVENTS[57]
            n_r67 += 1
        elif w.startswith("R67 the PRODUCT-PATH TRUCK"):
            ev[i]["what"] = EVENTS[58]
            n_r67 += 1
    assert n_r67 == 3, n_r67
    json.dump(c, open(P, "w"), indent=1, ensure_ascii=False)
    cap = Capsule.load(P)
    print("compacted:", cap.size_bytes(), "bytes")
    assert cap.size_bytes() < 64 * 1024, "still over the cap"
    print("under the 64 KiB cap OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
