#!/usr/bin/env python3
"""r69_issue4_addendum.py — post the R69 product-path addendum to
issue #4 (read back byte-identical)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req  # noqa: E402

BODY = """**R69 addendum (the product path + the truck status) — the connect window IS REAL: the first confirmed truck-connect evidence on the product path (a4 300 → 100, pure lob connects), one connect short of the kill.** Commit `2672203` (remote main `b3a77dbaed90`, tree-verified 33/33 blobs).

* **v1.7.0 (the capsule's window [125, 140]) — the outer half FALSIFIED:** ep1 1154f/2200, 3 in-window throws at dx −139.5/−136.5/−136.5 ALL MISSED (the truck a4 FROZEN at 300, 0 connects); the ~+12px/throw animation drift + the section scroll re-created the R68 window-closure failure.
* **v1.7.1 (the window TIGHTENED to [130, 135], bracketing the only observed connect −133.5): THE CONNECT WINDOW IS REAL.** ep1 **1318f/1700 — the record death FRAME tied**: **7 gre40 throws** (the capsule's "up to 7 throws" EXACT), **EVERY throw at dx −133.5 EXACTLY** (px 1071.0, the record posture verbatim), the truck **a4 300 → 200 (f989) → 100 (f1153) = TWO CONFIRMED CONNECTS** (the connect rate 2/7 = 29% at the exact posture vs the R38 ~1/10 baseline) — **ONE connect SHORT**: the SECTION SCROLL shoved the player out of the window mid-cooldown (px 1071 → 1105.8 pinned, truck_dx −168.3, 3 grenades unspendable). The T5 chip-fire withdrawal held: the truck damage is PURE lob connects. The truck was NOT killed (honestly recorded); the R68 score record 2800 stands.
* **The new R70 leads:** the connect is **(posture × PHASE)-gated** (2/7 from the IDENTICAL posture; the connects 164f apart — the truck vulnerability-cycle lead); the fight window is scroll-capped (~280f, 7 gre40 throws max) — the kill needs the connect rate ≥ 3/7.
* **Mission 1 clear: NOT achieved** — the truck kill remains the concrete blocker (R70: the phase-timed connect policy; plus the experiment-track watchpoint pass on the payment writer — the R69 xref FOUND the kill-credit u16 tables in the overlay data head 0x8009C134/0x8009C48C/0x8009C91C and NARROWED the writer to the undecompiled overlay damage tail). The acceptance bar of this issue (a real interactive Mission 1 clear with control ownership, legal input, a genuine completion indicator, reproducible evidence, an independent repeat, zero hidden writes) remains unmet and unclaimed.

Evidence: `data/games/SLUS-01212/truck_evidence/r69/r69_product_run.json` + `product_run/` (episode records + screenshots) + `r69_connect_probe.jsonl` (v1.7.0) + `r69b_connect_probe.jsonl` (v1.7.1) + `r69_fingerprint_xref.{json,md}` · tests `tests/test_r69_msx_connect_window.py` (16 new offline tests; the suite 876 green). The issue STAYS OPEN."""


def main():
    s, d = req("/repos/Sh-TB/Ps1ai/issues/4/comments",
               method="POST",
               payload={"body": BODY})
    print("HTTP", s, "comment id:", d.get("id"))
    if s == 201:
        s2, comments = req("/repos/Sh-TB/Ps1ai/issues/4/comments?per_page=100")
        mine = [c for c in comments if c["id"] == d["id"]]
        ok = bool(mine) and mine[0]["body"] == BODY
        print("read-back byte-identical:", ok)
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
