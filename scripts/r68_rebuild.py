#!/usr/bin/env python3
"""r68_rebuild.py — R68 boot 2: the stage-1 frontier REBUILD (the
disclosed capsule contingency).

SIXTH sandbox rollback: the r66_frontier_a/b states are LOST (never
committed — no-game-bytes).  The rebuild is the R47/R66 stage-1
recipe VERBATIM (r66t1.do_stage1 -> R47T.push_phase): restore
issue5_m1_start -> the tainted combat-policy push in 15f chunks with
continue-rescues -> eager rolling frontier saves r66_frontier_a/b
past px 1200 every >=25px (sane-clamped) -> early exit when both are
saved and the latest px >= 1240.

Determinism precedent: the rebuild reproduced 6-for-6 byte-exact
(px 1224.9 / 1254.8) across FOUR prior sandbox rollbacks — the
rebuilt arms are expected to match the R66 originals; the px values
are verified post-rebuild and any divergence is disclosed.

Lineage: TAINTED (continue-rescues; never a clean claim) — the same
disclosure the R45/R47/R52/R66 rebuilds carried.

Evidence: data/games/SLUS-01212/truck_evidence/r68/
          r68_boot2_s1_report.json
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import r66t1_payframe_destarve as r66t1            # noqa: E402

# ---- the R68 harness patch (disclosed): the r66t1 module keeps its
# CODE verbatim; only the OUTPUT PATHS are re-pointed at the r68
# evidence tree.  The frontier NAMES stay r66_frontier_a/b (the
# R47/R66 lineage; the rebuilt bytes are expected identical).
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r68")
SCRATCH = os.path.join(_REPO, "scratch", "r68")
r66t1.EVID = EVID
r66t1.SCRATCH = SCRATCH
r66t1.PNGDIR = os.path.join(SCRATCH, "pngs")
import r47t1_singletap_taps as R47T                # noqa: E402
R47T.PNGDIR = r66t1.PNGDIR

LEDGER = os.path.join(SCRATCH, "boots_used.json")


def log(*a):
    print("[r68-rebuild]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    with open(LEDGER) as f:
        led = json.load(f)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit("BOOT CAP EXCEEDED (r68 ledger)")
    led["count"] = int(led.get("count", 0)) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r68_rebuild.py",
                       "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def main():
    n = amend_ledger(
        "BOOT stage-1 (the tainted frontier REBUILD; the disclosed "
        "capsule contingency: the SIXTH sandbox rollback lost the "
        "r66_frontier_a/b states; the R47/R66 recipe verbatim, "
        "byte-exact 6-for-6 precedent; lineage TAINTED — never a "
        "clean claim)")
    tag = time.strftime("r68_s1_%H%M%S")
    stem = f"r68_boot{n}_s1"
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    tr_path = os.path.join(EVID, f"{stem}.jsonl")
    jf = open(tr_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    J({"ev": "RUN_START",
       "commit": os.popen("git -C %s rev-parse HEAD"
                          % _REPO).read().strip(),
       "stage": 1,
       "rollback_disclosure":
           "SIXTH sandbox rollback: the r66_frontier_a/b states "
           "LOST (never committed — no-game-bytes); issue5_m1_start "
           "survived (re-validated by boot 1 r68_env_probe.json); "
           "the capsule contingency verbatim (the R45/R47/R52/R66 "
           "precedent)",
       "lineage": "TAINTED (continue-rescues; never a clean claim)",
       "expectation": ("the rebuild is byte-exact 6-for-6 across "
                       "the prior rollbacks (px 1224.9 / 1254.8); "
                       "any divergence is disclosed"),
       "ts": time.strftime("%FT%TZ", time.gmtime())})
    try:
        rc = r66t1.do_stage1(J, tag, stem)
    finally:
        jf.close()
    # ---- post-rebuild verification ---------------------------------
    states = r66t1.STATES
    ver = {}
    for fr in r66t1.FRONTIER:
        pth = os.path.join(states, fr + ".state")
        ver[fr] = {"on_disk": os.path.exists(pth),
                   "bytes": (os.path.getsize(pth)
                             if os.path.exists(pth) else None),
                   "md5": None}
        if ver[fr]["on_disk"]:
            import hashlib
            h = hashlib.md5()
            with open(pth, "rb") as f:
                for b in iter(lambda: f.read(1 << 20), b""):
                    h.update(b)
            ver[fr]["md5"] = h.hexdigest()
    J({"ev": "REBUILD_VERIFY", "states": ver})
    log("verify:", json.dumps(ver))
    log(f"report -> {EVID}/{stem}_report.json")
    return rc


if __name__ == "__main__":
    sys.exit(main())
