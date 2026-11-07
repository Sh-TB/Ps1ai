#!/usr/bin/env python3
"""r67_env_probe.py — R67 Phase 0: environment + restore-only budget
validation (boot 1 of the r67 ledger, cap 3 disclosed pre-run).

The cheapest decisive pre-experiment check, the R66 pattern verbatim:

  1. boot the real product stack (beetle 0.9.44 + OpenBIOS override +
     the retail SLUS-01212 disc) through the proven boot gate;
  2. snap the world;
  3. restore-validate issue5_m1_start (the Oct-20 anchor) AND BOTH
     r66 frontiers (r66_frontier_a/b — the R67 restore-only budget
     line depends on them being alive on THIS machine: a fresh
     sandbox session, the FIFTH rollback disclosure);
  4. NO gameplay claim is made from this probe.

Ledger discipline: this probe IS boot 1 of the R67 ledger.  The two
hunt passes are SEPARATE disclosed boots (2 and 3).

Evidence: data/games/SLUS-01212/truck_evidence/r67/r67_env_probe.json
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
                    "truck_evidence", "r67")
SCRATCH = os.path.join(_REPO, "scratch", "r67")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
STATES = "/home/z/my-project/emu/ws/states"
CKPTS = ("issue5_m1_start", "r66_frontier_a", "r66_frontier_b")


def log(*a):
    print("[r67-env]", *a, file=sys.stderr, flush=True)


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
                    "R67 cap 3 DISCLOSED PRE-RUN (restore-only "
                    "round): boot 1 = the env probe "
                    "(r67_env_probe.py: boot -> restore-validate "
                    "issue5_m1_start + BOTH r66 frontiers on THIS "
                    "machine); boot 2 = the frontier_a hunt; boot 3 "
                    "= the frontier_b hunt.  NO rebuild boot: the "
                    "r66 frontiers SURVIVED on disk (verified "
                    "pre-run; the capsule budget line verbatim).  "
                    "FIFTH sandbox rollback disclosure: this "
                    "session's sandbox is fresh; nothing was lost "
                    "(frontiers + anchor verified by the dry-run "
                    "file checks), but restore aliveness on THIS "
                    "machine is exactly what boot 1 validates.  "
                    "GOAL: PAY500_GOAL=2 shared across the round "
                    "(atomic counter), fresh-soft 0x4054 preference, "
                    "de-starve advance armed on BOTH passes, "
                    "pay-frame telemetry verbatim.  m2_gate "
                    "unchanged."),
            }, f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit("BOOT CAP EXCEEDED (r67 ledger)")
    led["count"] = int(led.get("count", 0)) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r67_env_probe.py",
                       "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def validate_ckpt(p, m, name):
    """Restore + validate one checkpoint (alive + sane px + survives
    a short idle).  Records honestly; no gameplay claim."""
    r = {"name": name, "on_disk":
         os.path.exists(os.path.join(STATES, name + ".state"))}
    if not r["on_disk"]:
        return r
    p.load_state(name)
    m = p.mem
    t1.wait_alive(m, p, wait=10)
    s1 = t1.snap(m)
    s1["alive"] = bool(t1.alive(m))
    r["restored_world"] = s1
    r["valid"] = bool(s1["alive"] and 0.0 < s1["px"] < 5000
                      and s1["php"] > 0)
    log(f"checkpoint {name}: {s1} valid={r['valid']}")
    if name != CKPTS[0]:
        # the frontiers must ALSO survive a short idle (the hunt
        # restores them and runs controls before the first tap)
        p.core.run(60, set())
        s2 = t1.snap(m)
        s2["alive"] = bool(t1.alive(m))
        r["after_60f_idle"] = s2
        r["survives_60f"] = bool(s2["alive"])
    return r


def main():
    t0 = time.time()
    n = amend_ledger("BOOT (env probe + restore-only budget "
                     "validation only)")
    if n > 1:
        raise SystemExit("env probe boot cap exceeded")
    out = {
        "schema": "ps1play.r67-env-probe/1",
        "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
        "commit": os.popen("git -C %s rev-parse HEAD"
                           % _REPO).read().strip(),
        "boot_ledger": {"n": n, "purpose": "env_probe"},
        "restore_only_budget": {
            "frontiers_on_disk": {
                f: os.path.exists(os.path.join(STATES, f + ".state"))
                for f in CKPTS[1:]},
        },
    }
    log("booting (openbios + beetle + SLUS-01212)...")
    p, fwmode = boot()
    m = p.mem
    boot_t = time.time() - t0
    s0 = t1.snap(m)
    s0["alive"] = bool(t1.alive(m))
    out["boot"] = {"fw_mode": fwmode, "wall_s": round(boot_t, 1),
                   "world": s0}
    log(f"boot world: {s0}")

    png = None
    try:
        from PIL import Image
        rgb = p.core.frame_rgb()
        if rgb is not None:
            d = os.path.join(SCRATCH, "pngs")
            os.makedirs(d, exist_ok=True)
            png = os.path.join(d, "r67_env_boot.png")
            Image.fromarray(rgb).save(png)
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])
    out["boot"]["png"] = png

    # ---- checkpoint validation (the anchor + BOTH frontiers) --------
    out["checkpoints"] = []
    ok = True
    for ck in CKPTS:
        r = validate_ckpt(p, m, ck)
        out["checkpoints"].append(r)
        if r["on_disk"]:
            ok = ok and bool(r.get("valid"))
            if ck != CKPTS[0]:
                ok = ok and bool(r.get("survives_60f"))
    out["restore_only_budget_ok"] = bool(ok)
    out["wall_s"] = round(time.time() - t0, 1)
    outpath = os.path.join(EVID, "r67_env_probe.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1, default=str)
    log("report:", outpath)
    log("restore_only_budget_ok:", ok)
    return 0


if __name__ == "__main__":
    sys.exit(main())
