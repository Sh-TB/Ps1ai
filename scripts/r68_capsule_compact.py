#!/usr/bin/env python3
"""r68_capsule_compact.py — bring the shipped msx capsule back under
the 64 KiB design cap WITHOUT losing a single fact (the R66/R67
compaction pattern verbatim).

The R68 session appended four long events (59-62) which pushed the
canonical size to 75,257 B > 65,536 B.  This script compacts ONLY
the R68-owned prose; every number, address, state word, rule name,
status and evidence pointer is preserved.  The full narratives live
in reports/r68/, the worklog and the truck_evidence files.  Git
history keeps every prior capsule byte-for-byte.
"""
import json
import sys

sys.path.insert(0, ".")
from ps1play.knowledge import Capsule  # noqa: E402

P = "data/knowledge/msx/capsule.json"

EVENTS = {
    59: (
        "R68 the +500 n>=2 GOAL MET (ledger cap 3 disclosed, 3/3 "
        "spent: env probe + the stage-1 frontier REBUILD (the "
        "disclosed SIXTH-rollback contingency; the rebuilt arms "
        "byte-exact, frontier_px 1254.8 = the R66 record, the "
        "determinism dividend 7-for-7) + the pass-B hunt): the R66 "
        "pass-B tap sequence replayed VERBATIM (the corridor gate "
        "as committed in r66t1 — CORPSE_ST {0x4BE4, 0x5CC8}, the "
        "amendment-G exclusion NOT applied) and THE +500 CAPTURED "
        "AT TAP 6: slot16, st_pre 0x1e38, pay tail f1 — the causal "
        "chain BYTE-IDENTICAL to the R66 capture; the tap-kind "
        "sequence IDENTICAL to the R66 pass-B end to end.  "
        "AMENDMENT-G LESSON CONFIRMED BY REPRODUCTION: the gate "
        "variant WAS the R67 divergence.  The +500 class stands "
        "n=2.  Honest note: the CONNECT/KILL counters read 0/0 "
        "(the 0x42bc registration never appeared in the tap "
        "windows) while the score PAID at taps 2 (+1000) and 6 "
        "(+500) — the pay-before-registration law seen from the "
        "missing-registration side too.",
    ),
    60: (
        "R68 the WIDENED-SET ZERO-OVERLAP DISCRIMINATOR RESOLVED "
        "(the R67 PENDING item closed): +500 n=2 vectors (R66 t6 + "
        "R68 t6) vs +1000 n=7 banked (2 R52 + 2 R66 + 2 R67) — 19 "
        "union-net offsets separate EVERY +500 from EVERY +1000 "
        "(the intersection: 0x60, 0x62, 0x6c, 0x70, 0x74, 0x78, "
        "0x7a, 0x8c, 0x8e, 0x94, 0x96, 0xc6, ...).  DELAY LAW "
        "TWO-CLASS: +500 pays tail f1 (2/2), +1000 pays tail f3/f4. "
        "Magnitude table: +500 x5 vs +1000 x9.  The 19 offsets are "
        "the payment=f(wound_state) fingerprint candidates for the "
        "R69 source-first hunt.",
    ),
    61: (
        "R68 THE R67 CORRECTION (the honest-registry law): the R67 "
        "'TRUCK KILLED, score 2300' event is REFUTED by the "
        "read-only product-stack probe — the truck row sat at "
        "a4=160 (0x9E88, x 937.5, slot 14) from f1160 to the v1.4.2 "
        "death at f1462; the truck was NEVER killed on the product "
        "path; the score came from the wave kills + chip events; "
        "the 3 lobs landed ONE connect (-100) + chips (-40).  The "
        "'truck AIRBORNE' death-shot reading likewise corrected "
        "(the airborne object is the encounter's follower).  The "
        "player died PINNED at px 1164 with the parked truck "
        "behind at dx -226.5 — outside the lob band (135) and the "
        "chip reach (the bullets never arrive).",
    ),
    62: (
        "R68 the PRODUCT-PATH FAILURE-MODE MAP (four variants, "
        "probe-pinned; adapter 0.4.0 = the truck dead family "
        "{0xA304, 0xA44C, 0xA45C} in the corpse filter + the "
        "dead_truck_x kill signature; policy 1.5.0->1.6.2; 9 new "
        "offline tests, the suite 864 green): (a) v1.5.0 W8/W9 — "
        "the run reproduced the R67 v1.4.2 trace BYTE-IDENTICAL "
        "(1462f/2300/91): the chain never fires because the truck "
        "never dies; (b) v1.6.0 unlimited lobs + the chase — ep1 "
        "1318f/2800 = the RECORD; the lobs LANDED in the band (dx "
        "-133.5, px 1071) driving a4 300->80, then FROZE at the "
        "band edge (the chase walked against the scroll, px "
        "1071->1105.8 while pressing BACK); (c) v1.6.1 stand-"
        "ground chip-fire — 1218f/1400 = a REGRESSION: the a4 sat "
        "at 300 FROZEN through five chip windows — THE BULLETS DO "
        "NOT REACH a truck behind the pin (the wave + the scenery "
        "eat the shot; the R38 chip model needs a CLEAR LINE); "
        "(d) v1.6.2 the chase restored + the R38 gre40 cadence — "
        "1318f/2800 (the record tied), the same a4 floor 80: the "
        "CONNECT RATE (~1/10, the R38 evidence) is the named R69 "
        "blocker, not the cadence.  Mission 1 NOT cleared (not "
        "claimed).",
    ),
}


def main():
    c = json.load(open(P))
    ev = c["events"]
    n_r68 = 0
    for i, e in enumerate(ev):
        w = e.get("what", "")
        if not isinstance(w, str):
            continue
        if w.startswith("R68 the +500 n>=2 GOAL MET"):
            ev[i]["what"] = EVENTS[59]
            n_r68 += 1
        elif w.startswith("R68 the WIDENED-SET"):
            ev[i]["what"] = EVENTS[60]
            n_r68 += 1
        elif w.startswith("R68 THE R67 CORRECTION"):
            ev[i]["what"] = EVENTS[61]
            n_r68 += 1
        elif w.startswith("R68 the PRODUCT-PATH FAILURE-MODE MAP"):
            ev[i]["what"] = EVENTS[62]
            n_r68 += 1
    assert n_r68 == 4, n_r68
    json.dump(c, open(P, "w"), indent=1, ensure_ascii=False)
    cap = Capsule.load(P)
    print("compacted:", cap.size_bytes(), "bytes")
    assert cap.size_bytes() < 64 * 1024, "still over the cap"
    print("under the 64 KiB cap OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
