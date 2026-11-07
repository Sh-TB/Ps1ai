#!/usr/bin/env python3
"""r68_issue4_addendum.py — post the R68 product-path addendum to
issue #4 (read back byte-identical)."""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req  # noqa: E402

BODY = """**R68 addendum (the product path + the truck status) — the R67 truck-kill claim REFUTED, the failure-mode map recorded, the record 2800.** Commit `89460f4` (remote main `1c1128992989`, tree-verified 42/42 blobs).

* **The R67 correction (the honest-registry law):** the R67 "THE ARMORED TRUCK KILLED ON THE PRODUCT PATH (T2 3-lobs vs hp_a4 300, score 2300)" is **REFUTED** by the R68 read-only product-stack probe: the truck row sat at **a4=160** (0x9E88, x 937.5, h 64, slot 14) from f1160 to the v1.4.2 death at f1462 — the truck was NEVER killed on the product path; the three lobs landed ONE connect (−100) + chips (−40); the score 2300 was the wave kills + chip events; the "truck AIRBORNE" death-shot reading is likewise corrected. The player died PINNED at px 1164 with the parked truck BEHIND at dx −226.5.
* **The failure-mode map (four probe-pinned policy variants; adapter 0.4.0 = the truck dead family {0xA304, 0xA44C, 0xA45C} in the corpse filter + the dead_truck_x kill signature; policy 1.5.0→1.6.2):** v1.5.0 W8/W9 = the R67 trace BYTE-IDENTICAL (the chain never fires — the truck never dies); v1.6.0 the chase = 1318f/**2800 = the RECORD** (the lobs LAND in the band dx −133.5: a4 300→80, then FROZE at the band edge); v1.6.1 the stand-ground chip-fire = 1218f/1400 REGRESSION (**the bullets DO NOT reach a truck behind the pin** — the wave + the pin scenery eat the shot; the R38 chip model needs a CLEAR LINE); v1.6.2 the chase + the R38 gre40 cadence = 1318f/2800 tied — the **CONNECT RATE (~1/10)** is the named R69 blocker.
* **Mission 1 clear: NOT achieved** — the truck kill itself is the next concrete blocker (R69: the connect-window policy — hold the measured throw posture px ~1071, |dx| 125..140, lob on the gre40 cadence ONLY inside the window). The acceptance bar of this issue (a real interactive Mission 1 clear with control ownership, legal input, a genuine completion indicator, reproducible evidence, an independent repeat, zero hidden writes) remains unmet and unclaimed.

Evidence: `data/games/SLUS-01212/truck_evidence/r68/r68_product_run.json` + `product_run/` (episode records + screenshots) + `r68_postkill_probe_v161_chipstand.jsonl` · `reports/r68/R68_ROUND_REPORT.md` · tests `tests/test_r66_msx_adapter.py` (+9 R68 offline tests, the suite 864 green). The issue STAYS OPEN."""


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
