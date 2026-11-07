#!/usr/bin/env python3
"""r68_env_probe.py — R68 Phase 0: environment + budget validation
(boot 1 of the r68 ledger, cap 3 disclosed pre-run).

The R66/R67 pattern verbatim.  THIS sandbox is the SIXTH rollback
disclosure: the r66_frontier_a/b states are LOST (never committed —
no-game-bytes); issue5_m1_start (Oct 20) SURVIVED.  The capsule
contingency applies verbatim: a rebuild boot, disclosed (boot 2).

Ledger: cap 3 DISCLOSED PRE-RUN —
  boot 1 = this env probe (the anchor restore-validation + the
           frontier loss recorded on THIS machine);
  boot 2 = the stage-1 frontier rebuild (r68_rebuild.py; the
           disclosed contingency; the 6-for-6 byte-exact rebuild
           precedent — the rebuilt arms are expected byte-identical
           to the R66 originals, px-verified post-rebuild);
  boot 3 = the stage-2 pass-B hunt (r68_passb_hunt.py; the R66
           pass-B tap sequence VERBATIM — the corridor gate as
           committed in r66t1, NOT the r67 amendment-G variant —
           the third +500 attempt; the capsule lever R68 line).

GOAL: the +500 class needs n>=2 (the R52/R66/R67 magnitude table:
+500 x4 vs +1000 x9); the widened-set zero-overlap test re-runs on
any new capture (offline, zero boots).  m2_gate unchanged.

Evidence: data/games/SLUS-01212/truck_evidence/r68/r68_env_probe.json
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

import r39t1_baseline as t1                       # noqa: E402
from issue4_controller import boot                # noqa: E402

EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r68")
SCRATCH = os.path.join(_REPO, "scratch", "r68")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
STATES = "/home/z/my-project/emu/ws/states"
ANCHOR = "issue5_m1_start"
FRONTIERS = ("r66_frontier_a", "r66_frontier_b")


def log(*a):
    print("[r68-env]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({
                "cap": 3,
                "count": 0,
                "log": [],
                "note": (
                    "R68 cap 3 DISCLOSED PRE-RUN: boot 1 = the env "
                    "probe (this script); boot 2 = the stage-1 "
                    "frontier REBUILD (the disclosed contingency: "
                    "SIXTH sandbox rollback lost the r66_frontier_a/b "
                    "states — never committed, no-game-bytes; the "
                    "rebuild recipe is the R47/R66 stage-1 verbatim, "
                    "byte-exact 6-for-6 across the prior rollbacks); "
                    "boot 3 = the stage-2 pass-B hunt (the R66 "
                    "pass-B tap sequence VERBATIM: the corridor gate "
                    "as committed in r66t1 — combat.CORPSE_ST = "
                    "{0x4BE4, 0x5CC8}, NOT the r67 amendment-G "
                    "variant — the trajectory-sensitivity lesson: "
                    "the tap order is part of the experiment).  "
                    "GOAL: a third +500 capture (the class stands "
                    "n=1); the widened-set zero-overlap test re-runs "
                    "offline on any new capture.  m2_gate unchanged."),
            }, f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit("BOOT CAP EXCEEDED (r68 ledger)")
    led["count"] = int(led.get("count", 0)) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r68_env_probe.py",
                       "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def validate_ckpt(p, m, name):
    r = {"name": name, "on_disk":
         os.path.exists(os.path.join(STATES, name + ".state"))}
    if not r["on_disk"]:
        return r
    p.load_state(name)
    t1.wait_alive(m, p, wait=10)
    s1 = t1.snap(m)
    s1["alive"] = bool(t1.alive(m))
    r["restored_world"] = s1
    r["valid"] = bool(s1["alive"] and 0.0 < s1["px"] < 5000
                      and s1["php"] > 0)
    log(f"checkpoint {name}: {s1} valid={r['valid']}")
    if name != ANCHOR:
        p.core.run(60, set())
        s2 = t1.snap(m)
        s2["alive"] = bool(t1.alive(m))
        r["after_60f_idle"] = s2
        r["survives_60f"] = bool(s2["alive"])
    return r


def main():
    t0 = time.time()
    n = amend_ledger("BOOT (env probe + budget validation only)")
    if n > 1:
        raise SystemExit("env probe boot cap exceeded")
    out = {
        "schema": "ps1play.r68-env-probe/1",
        "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
        "commit": os.popen("git -C %s rev-parse HEAD"
                           % _REPO).read().strip(),
        "boot_ledger": {"n": n, "purpose": "env_probe"},
        "rollback_disclosure": (
            "SIXTH sandbox rollback: scratch/ and the savestate "
            "workspace were reset — r66_frontier_a/b LOST (never "
            "committed — no-game-bytes); issue5_m1_start (Oct 20) "
            "SURVIVED.  The capsule contingency (a rebuild boot, "
            "disclosed) applies verbatim at boot 2."),
        "frontiers_on_disk": {
            f: os.path.exists(os.path.join(STATES, f + ".state"))
            for f in FRONTIERS},
    }
    log("booting (openbios + beetle + SLUS-01212)...")
    p, fwmode = boot()
    m = p.mem
    out["boot"] = {"fw_mode": fwmode,
                   "wall_s": round(time.time() - t0, 1),
                   "world": dict(t1.snap(m), alive=bool(t1.alive(m)))}
    log(f"boot world: {out['boot']['world']}")

    out["checkpoints"] = []
    anchor_ok = False
    for ck in (ANCHOR,) + FRONTIERS:
        r = validate_ckpt(p, m, ck)
        out["checkpoints"].append(r)
        if ck == ANCHOR:
            anchor_ok = bool(r.get("valid"))
    out["anchor_valid"] = anchor_ok
    out["wall_s"] = round(time.time() - t0, 1)
    outpath = os.path.join(EVID, "r68_env_probe.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1, default=str)
    log("report:", outpath)
    log("anchor_valid:", anchor_ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
