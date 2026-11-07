#!/usr/bin/env python3
"""r67_issue_report.py — post the R67 round report to issue #9 (the
R66 pattern): the evidence-grade comment, read back byte-identical.
"""
import sys

sys.path.insert(0, "/home/z/my-project/scripts")
from gh_api import req  # noqa: E402

BODY = """**R67 (the capsule lever executed) — the +500 hunt, the widened-set test, and the product-path TRUCK KILL.** Commit `bf5a3c8` (remote main `bf5a3c848156`, tree-verified 37/37 blobs byte-identical via the Git Data API; the 4 Contents-API "mismatches" on the >1 MB report blobs are the documented tool limit, not a push failure).

* **The experiment track (restore-only, ledger cap 3 disclosed pre-run, 3/3 spent).** The offline contract dry-run (`scripts/r67_dryrun.py`, 24/24) ran BEFORE any boot and caught + pinned a REAL gate defect: the R66 experiment gate's corpse set (`combat.CORPSE_ST`) lacked the death-registration terminal `0x5B0C` that the committed PRODUCT adapter contract includes — amendment G aligned the hunt gate with the product contract (the R66 script untouched, the delta pinned by tests). Boot 1 (the env probe): the anchor + BOTH r66 frontiers restore alive on this machine (px 1246.2 / 1254.8, alive) — the restore-only budget line held. Boots 2-3 (the hunt passes): **0 NEW +500 captures — the n≥2 goal NOT MET, honestly recorded**; the +1000 class replicated ×2 (0x42bc → pay tail f3, 0x3f48 → pay tail f4 — the exact R66 signature).
* **The amendment-G lesson:** on the byte-exact frontier_b the trajectory diverged EXACTLY at tap 6 (R66: slot16 0x1e38 +500; R67: slot18 0x540c +100) — **the +500 capture is a TRAJECTORY-SENSITIVE posture, not a standing property of the frontier; the tap order is part of the experiment.** The frontiers are target-starved past the spawner-cluster edge; fresh 0x4054 soldiers exist only at restore time.
* **The widened-set zero-overlap test (offline, zero boots):** +500 n=1 pay-frame vector vs +1000 n=6 vectors (2 R52 + 2 R66 + 2 R67): 19 union-net offsets separate the single +500 vector from all six — but at n=1 the intersection IS that capture's own set (identity words dominate): **the class discriminator stays PENDING.** What IS established: the st_pre→delay law reproduces ACROSS ROUNDS (0x42bc→tail f3, 0x3f48→tail f4 in both). Magnitude table **+500 ×4 vs +1000 ×9**.
* **The gameplay track (policy msx_mission1_rules 1.1.0→1.4.2, adapter 0.2.0→0.3.0, 40 offline tests): THE ARMORED TRUCK KILLED ON THE PRODUCT PATH** — the T2 grenade sequencing (3 lobs × −100 vs hp_a4 300, the capsule semantics verbatim) took it to zero and the death screenshot shows the truck AIRBORNE; ep1 score **2300 = the RECORD** (previous best 1300). The rule chain, each step a measured lesson: T1 the truck identity = the 0x9E88 state word (code 7 — the v1.1.0 (sc=6, h=64) identity was a FALSE-POSITIVE TRAP: ground soldiers in walk/throw animation states also present (6, 64); the hold froze at px 493 on a scenery row; the read-only truck-zone probe read the REAL truck live at 937.5 / h64 / a4=300); T3 soldiers-before-the-truck-gun (a clear-line escort holds the lob; a corridor-blocked one does not — the R49 model); **the REAR FIGHT** (BACK = the legal LEFT button; the loop-probe evidence: at the section pin the wave AND the truck are BEHIND the player — three identical v1.0.0-v1.3.0 forward-only deaths); T5 the outer-edge hold 90..135 (the dx-52 hold LOST the gun duel); T7 the blast retreat (the 3-lobs kill exploded the player standing in the band).
* **The cadence law:** the fire cadence is part of the deterministic wave trajectory — the v1.2.0 top-tick 12f cadence starved the wave (0 kills, the truck never entered, zero a4≥100 rows in the probe); the v1.0.0 13f rhythm restored in v1.3.0 reproduced the R66 record BYTE-EXACT (1666f/1100/87 and 388f/1300/13).
* **Honest status:** Mission 1 NOT cleared — the post-kill death (the second truck / the death animation) is the named next blocker. Full suite **858 passed + 3 skipped + 1 xfailed** (zero weakened); legal inputs only, zero RAM writes, no training; the m2_gate note unchanged; no issue closed; no duplicate issues.
* **R68 (the next capsule lever):** product path — a wreck-aware policy extension (the wreck 0xA44C / death state 0xA304 are capsule knowledge) that retreats through the truck-kill and re-engages the SECOND truck with the same T2 sequencing until the roadblock section clears; experiment track — ONE restore-only boot replaying the R66 pass-B tap sequence VERBATIM (the amendment-G gate reverted for the hunt only) for the third +500 attempt.

Evidence: `reports/r67/R67_ROUND_REPORT.md` + `data/games/SLUS-01212/truck_evidence/r67/` + `scripts/r67_*.py`. The issue STAYS OPEN."""


def main():
    s, d = req("/repos/Sh-TB/Ps1ai/issues/9/comments",
               method="POST", payload={"body": BODY})
    print("HTTP", s)
    print("comment url:", d.get("html_url", d))
    if s == 201:
        # read back byte-identical
        s2, comments = req("/repos/Sh-TB/Ps1ai/issues/9/comments?per_page=100")
        mine = [c for c in comments if c["id"] == d["id"]]
        ok = bool(mine) and mine[0]["body"] == BODY
        print("read-back byte-identical:", ok)
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
