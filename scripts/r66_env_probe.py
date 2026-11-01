#!/usr/bin/env python3
"""r66_env_probe.py — R66 Phase 0: environment + checkpoint validation.

The cheapest decisive pre-experiment check, run BEFORE any R66 boot is
spent on gameplay questions:

  1. boot the real product stack (beetle 0.9.44 + OpenBIOS override +
     the retail SLUS-01212 disc) through the proven boot gate
     (input ownership + mission gate);
  2. snap the world (px / score / php / grenades / alive);
  3. restore the ONLY surviving pre-R53 checkpoint issue5_m1_start
     (Oct 20) and validate it (alive + sane px + score);
  4. record the R66 baseline facts for reports/r66/R66_BASELINE.md.

Ledger discipline (the R45-R52 precedent): this probe IS boot 1 of the
R66 ledger.  It answers the environment question only; the frontier
rebuild and the pay-frame experiment are SEPARATE disclosed boots.
No gameplay claim is made from this probe.

Evidence: data/games/SLUS-01212/truck_evidence/r66/r66_env_probe.json
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
                    "truck_evidence", "r66")
SCRATCH = os.path.join(_REPO, "scratch", "r66")
LEDGER = os.path.join(SCRATCH, "boots_used.json")
CKPT = "issue5_m1_start"
STATES = "/home/z/my-project/emu/ws/states"


def log(*a):
    print("[r66-env]", *a, file=sys.stderr, flush=True)


def amend_ledger(reason, cap=1):
    os.makedirs(SCRATCH, exist_ok=True)
    os.makedirs(EVID, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({
                "cap": cap,
                "count": 0,
                "log": [],
                "note": ("R66 ledger: boot 1 = the environment probe "
                         "(r66_env_probe.py).  The r52 frontiers are "
                         "LOST (scratch/r52 gone with the sandbox "
                         "reset) - disclosed pre-run; the frontier "
                         "rebuild and the pay-frame experiment get "
                         "their OWN disclosed ledger entries."),
            }, f, indent=1)
    with open(LEDGER) as f:
        led = json.load(f)
    led["count"] = int(led.get("count", 0)) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r66_env_probe.py",
                       "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


def main():
    t0 = time.time()
    n = amend_ledger("BOOT (env probe + checkpoint validation only)")
    if n > 1:
        raise SystemExit("env probe boot cap exceeded")
    out = {
        "schema": "ps1play.r66-env-probe/1",
        "generated_utc": time.strftime("%FT%TZ", time.gmtime()),
        "commit": os.popen("git -C %s rev-parse HEAD" % _REPO).read().strip(),
        "boot_ledger": {"n": n, "purpose": "env_probe"},
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
            png = os.path.join(d, "r66_env_boot.png")
            Image.fromarray(rgb).save(png)
    except Exception as e:                                  # noqa: BLE001
        log("png failed:", repr(e)[:120])
    out["boot"]["png"] = png

    # ---- checkpoint validation --------------------------------------
    ck_ok = os.path.exists(os.path.join(STATES, CKPT + ".state"))
    out["checkpoint"] = {"name": CKPT, "on_disk": ck_ok}
    if ck_ok:
        p.load_state(CKPT)
        m = p.mem
        t1.wait_alive(m, p, wait=10)
        s1 = t1.snap(m)
        s1["alive"] = bool(t1.alive(m))
        out["checkpoint"]["restored_world"] = s1
        out["checkpoint"]["valid"] = bool(
            s1["alive"] and 0.0 < s1["px"] < 5000 and s1["php"] > 0)
        log(f"checkpoint {CKPT}: {s1} valid={out['checkpoint']['valid']}")
        # survival probe: 60 idle frames must keep the world alive
        p.core.run(60, set())
        s2 = t1.snap(m)
        s2["alive"] = bool(t1.alive(m))
        out["checkpoint"]["after_60f_idle"] = s2
        out["checkpoint"]["survives_60f"] = bool(s2["alive"])
    out["wall_s"] = round(time.time() - t0, 1)
    outpath = os.path.join(EVID, "r66_env_probe.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1, default=str)
    log("report:", outpath)
    return 0


if __name__ == "__main__":
    sys.exit(main())
