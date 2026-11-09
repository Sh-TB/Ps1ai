#!/usr/bin/env python3
"""r69_issue_report.py — post the evidence-grade R69 round report to
issue #9 (read back byte-identical)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req  # noqa: E402

BODY = """**R69 (the capsule lever executed) — the +500 fingerprint xref: the kill-credit tables FOUND, the payment writer NARROWED; the connect-window product verdict: the window IS REAL — 2 confirmed truck connects at the exact posture, one short of the kill.** Commit `2672203` (remote main `b3a77dbaed90`, tree-verified 33/33 blobs byte-identical via the Git Data API).

* **The experiment track (lead 1, OFFLINE, ZERO boots — `r69_fingerprint_xref.py`).** Full-text capstone decode of the EXE text (155,136 insns) + the ENEMY.BIN overlay (28,850 insns @0x8009C0E8; sha `1508b532…`/`cab64009…` verified before the scan). Findings: (1) the 19 zero-overlap offsets are touched by 750 EXE + 132 decompiled overlay functions; (2) the score word **0x800EE318 has EXACTLY 9 direct code xrefs**, all in the EXE HUD/credit cluster 0x800472c0..0x80052820 — the cluster's `score_add` reads the entity record **+0xCC/+0xD0/+0xD4** (+0xD0 IS a fingerprint offset); (3) the amounts 500/1000 appear in **NO code immediate** — both candidates FALSIFIED by their own bytes (`0x800b03cc addiu $v1,$v1,0x3e8` = the state-handler ADDRESS arithmetic `lui 0x800b|0x3e8`; `0x80088e8c addiu $a1,$zero,0x1f4` = a clamp bound) — and in NO EXE table; (4) **THE KILL-CREDIT u16 TABLES FOUND in the overlay data head**: 0x8009C134 (n=43), 0x8009C48C (n=44), 0x8009C91C (n=23) — values 200..1100 including 500 and 1000; the +500 class = the 0x1f4 entries; (5) the overlay TAIL (0x800AB230..0x800B83B0, UNDECOMPILIED by the committed 468-function pass) carries **207 fingerprint accesses (72 stores, 14/19 offsets)** and the damage dispatch (`enemy_800A41D8` → `func_0x800ae794`/`func_0x800ae7cc`) runs there. **VERDICT: the payment writer NARROWED** (the overlay damage tail + the credit tables; the exact store is a RUNTIME fact for the watchpoint hunt). The capsule's conditional next step ("one restore-only hunt pass IF the writer is found") is honestly NOT triggered — and the SEVENTH sandbox rollback is disclosed (the r66 frontiers lost again; the R68 rebuild stays byte-exact reproducible).
* **The product track (lead 2; policy 1.6.2→1.7.0→1.7.1, the C1 connect-window rule; product boots + 2 read-only probes, the R64/R67/R68 diag-track precedent).** **v1.7.0 ran the capsule's window [125, 140] — the outer half is FALSIFIED**: ep1 1154f/2200 (a regression), 3 in-window throws at dx −139.5/−136.5/−136.5 **ALL MISSED** — the truck a4 FROZEN at 300 through the whole fight (0 connects); the ~+12px/throw animation drift + the section scroll re-created the R68 window-closure failure (px 1074 → 1108.8 pinned). **v1.7.1 TIGHTENED the window to [130, 135]** (bracketing the only observed connect, the R68 record's −133.5): **THE CONNECT WINDOW IS REAL.** ep1 **1318f/1700 — the record death FRAME tied**: **7 gre40 throws** (the capsule's "up to 7 throws" EXACT), **EVERY throw at dx −133.5 EXACTLY** (px 1071.0, the record posture verbatim — the approach/retreat discipline fought the drift), the truck **a4 300 → 200 (f989) → 100 (f1153) = TWO CONFIRMED CONNECTS** (throws 3 and 7; the connect rate **2/7 = 29%** at the exact posture vs the R38 ~1/10 baseline) — **the truck died ONE connect SHORT**: the SECTION SCROLL shoved the player out of the window mid-cooldown (px 1071 → 1105.8 pinned, truck_dx −168.3, 3 grenades left unspendable); the T5 chip-fire withdrawal held (the truck damage is PURE lob connects). ep2 (k=12) 386f/1700 — the R68 v1.6.0 ep2 frame-exact (the pre-truck wave section dominates). The truck was NOT killed (honestly recorded); the R68 score record 2800 stands.
* **NEW FACTS (the R70 leads).** (1) The connect is **(posture × PHASE)-gated**: 2/7 connects from the IDENTICAL throw posture, the connects 164f apart (f989/f1153) — the truck vulnerability-cycle lead; (2) the truck-fight window is **scroll-capped** (~280f, 7 gre40 throws max) — the kill needs the connect rate ≥ 3/7 = 43%. Zero-overlap re-run NOT triggered (no new +500 capture — the wave paid +300/+100 only).
* **Honest status:** the suite **876 passed + 10 skipped + 1 xfailed** (16 new offline tests: the connect-window edges, the cooldown hold, the retreat symmetry, the escort override, the live-counter budget, the W8/W9 regression, determinism; the R66/R67 truck tests updated to the C1 committed rule with the evidence noted in-test; zero weakened); legal inputs only, zero RAM writes, no training, no runtime LLM; the m2_gate note unchanged; no issue closed; no duplicate issues. Capsule: +2 R69 events with provenance + 13 owned prose blocks compacted (every number/address/status preserved), canonical under the 64 KiB warn cap.

**R70 (the next capsule lever):** product path — the connect **PHASE law** (find the truck vulnerability cycle behind the 164f connect spacing and time the gre40 cadence to the phase; the kill needs ≥ 3/7 inside the ~280f scroll-capped window); experiment track — ONE restore-only watchpoint pass on 0x800EE318 to log the payment-writer PC (the R69 xref narrowed it to the overlay damage tail + the credit tables 0x8009C134/0x8009C48C/0x8009C91C; requires the disclosed frontier rebuild).

Evidence: `data/games/SLUS-01212/truck_evidence/r69/` (the xref JSON+MD, both connect probes, the product run record + shots) + `scripts/r69_*.py`. The issue STAYS OPEN."""


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
