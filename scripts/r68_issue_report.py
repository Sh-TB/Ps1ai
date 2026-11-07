#!/usr/bin/env python3
"""r68_issue_report.py — post the evidence-grade R68 round report to
issue #9 (read back byte-identical)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req  # noqa: E402

BODY = """**R68 (the capsule lever executed) — the +500 n≥2 goal MET via the verbatim R66 tap replay, the zero-overlap discriminator RESOLVED, the R67 truck-kill claim corrected, the product-path failure-mode map.** Commit `89460f4` (remote main `1c1128992989`, tree-verified 42/42 blobs byte-identical via the Git Data API; the 2 Contents-API "mismatches" on the >1 MB evidence blobs are the documented tool limit, not a push failure).

* **The experiment track (ledger cap 3 disclosed pre-run, 3/3 spent).** Boot 1 (the env probe): the anchor restores alive (px 258.6, the record values) — and the SIXTH sandbox-rollback disclosure: the r66 frontiers were LOST (never committed — no-game-bytes). Boot 2 (the disclosed rebuild contingency): the R47/R66 stage-1 recipe verbatim → `frontiers_saved`, frontier_px **1254.8 = the R66 record EXACTLY** — the determinism dividend is now **7-for-7**. Boot 3 (the hunt): `r66t1.do_stage2(only="b")` — THE R66 CODE PATH ITSELF with the corridor gate as committed (CORPSE_ST {0x4BE4, 0x5CC8}; the amendment-G exclusion NOT applied; combat.py untouched): **THE +500 CAPTURED AT TAP 6 — slot16, st_pre 0x1e38, pay tail f1 — the causal chain BYTE-IDENTICAL to the R66 capture, the tap-kind sequence IDENTICAL end to end.** The amendment-G lesson CONFIRMED BY REPRODUCTION: the tap order IS part of the experiment. The +500 class stands **n=2**. Honest note: the CONNECT/KILL counters read 0/0 (no 0x42bc registration in the tap windows) while the score PAID at taps 2 (+1000) and 6 (+500) — the pay-before-registration law seen from the missing-registration side too.
* **The widened-set zero-overlap test — RESOLVED (the R67 PENDING closed).** +500 n=2 (R66 t6 + R68 t6) vs +1000 n=7 (2 R52 + 2 R66 + 2 R67): **19 union-net offsets** separate EVERY +500 pay-frame vector from EVERY +1000 vector (0x60, 0x62, 0x6c, 0x70, 0x74, 0x78, 0x7a, 0x8c, 0x8e, 0x94, 0x96, 0xc6, …). The delay law is TWO-CLASS: +500 pays tail f1 (2/2), +1000 pays tail f3/f4. Magnitude **+500 ×5 vs +1000 ×9**. The 19 offsets are the payment=f(wound_state) fingerprint candidates for the R69 source-first xref.
* **THE R67 CORRECTION (the honest-registry law):** the R67 "THE ARMORED TRUCK KILLED ON THE PRODUCT PATH (score 2300)" is **REFUTED** by the R68 read-only product-stack probe (the every-frame entity table): the truck row sat at **a4=160** (0x9E88, x 937.5, slot 14) from f1160 to the v1.4.2 death at f1462 — the truck was NEVER killed; the three lobs landed ONE connect (−100) + chips (−40); the score 2300 was the wave kills + chip events; the "truck AIRBORNE" death-shot reading is likewise corrected (the airborne object is the encounter's follower). The player died PINNED at px 1164 with the parked truck BEHIND at dx −226.5.
* **The product-path failure-mode map (four probe-pinned policy variants; adapter 0.3.0→0.4.0 + policy 1.5.0→1.6.2):** (a) **v1.5.0** W8/W9 (the kill transition + the hazard retreat) — the run reproduced the R67 trace BYTE-IDENTICAL (1462f/2300/91, the same trace_sha256): the chain never fires because the truck never dies; (b) **v1.6.0** unlimited lobs + the chase — 1318f/**2800 = the RECORD** (prior best 2300): the lobs LAND in the band (dx −133.5 from px 1071) driving a4 300→80, then FROZE at the band edge; (c) **v1.6.1** stand-ground chip-fire — 1218f/1400 a REGRESSION: the a4 sat FROZEN at 300 through five chip windows — **the bullets DO NOT reach a truck behind the pin** (the R38 chip model needs a CLEAR LINE); (d) **v1.6.2** the chase restored + the R38 gre40 cadence — 1318f/2800 tied: the **CONNECT RATE (~1/10)** is the named R69 blocker, not the cadence. Mission 1 NOT cleared (not claimed).
* **Honest status:** the suite **864 passed + 9 skipped + 1 xfailed** (zero weakened; 9 new offline tests); legal inputs only, zero RAM writes, no training, no runtime LLM; the m2_gate note unchanged; no issue closed; no duplicate issues. The intermediate probe artifacts (v1.5.0/v1.6.0) were overwritten in place by the fixed-path probe — disclosed; their pinned numbers live in the round report + the capsule; the v1.6.1 artifact survives.

**R69 (the next capsule lever):** product path — the connect-window policy (hold the measured throw posture px ~1071, |dx| 125..140, lob on the gre40 cadence ONLY inside the window: up to 7 throws in the ~280f band window ⇒ the kill inside the window at the measured rate); experiment track — the 19-offset +500 fingerprint xref'd in the ENEMY.BIN overlay @0x8009C0E8 + the EXE (offline, zero boots) to find the payment writer; one restore-only hunt pass if the writer is found (the R66 gate verbatim, the R68 disclosure pattern).

Evidence: `reports/r68/R68_ROUND_REPORT.md` + `data/games/SLUS-01212/truck_evidence/r68/` + `scripts/r68_*.py`. The issue STAYS OPEN."""


def main():
    s, d = req("/repos/Sh-TB/Ps1ai/issues/9/comments",
               method="POST",
               payload={"body": BODY})
    print("HTTP", s, "comment id:", d.get("id"))
    if s == 201:
        s2, comments = req("/repos/Sh-TB/Ps1ai/issues/9/comments?per_page=100")
        mine = [c for c in comments if c["id"] == d["id"]]
        ok = bool(mine) and mine[0]["body"] == BODY
        print("read-back byte-identical:", ok)
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
