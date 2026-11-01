#!/usr/bin/env python3
"""r66_side_smallgames.py — the R66 side task: TWO easy small
homebrew games, chosen by download size, probed for automation
feasibility on the CURRENT stack (one boot each, generic probes).

Selection (per the user's request: pick simple games by size from the
committed homebrew manifest, data/homebrew/manifest.json):

  1. psx-minecraft  (MIT, PSXMC.bin 329,280 B + the infdev tarball
     695,797 B — the SMALLEST accepted candidate; already
     ACCEPTED+TESTED in the Issue-6 round: boots to world render,
     input-responsive) — the live re-probe validates it on the R66
     stack and asks the automation question with RAM evidence.
  2. zenmai (MIT, zenmai-zork.psexe 700,416 B — the second-smallest
     permissive candidate; a Zork I port: TEXT state, deterministic
     parser semantics) — fetched fresh (the local copy was lost to
     the sandbox rollback), license-patched locally (the Issue-6
     boot gate), booted, probed.

Feasibility probe (generic, game-agnostic): idle 60f vs RIGHT 60f vs
LEFT 60f — RAM churn + pixel churn + a two-origin scan for movement-
correlated words; screenshots as evidence.  The verdicts are
feasibility assessments, NOT runtime games (no adapters built here).

Evidence: data/homebrew/r66_side_probe/{psxmc,zenmai}_probe.json
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import BaseEnv  # noqa: E402

EVID = os.path.join(_REPO, "data", "homebrew", "r66_side_probe")
PSXMC_CUE = ("/home/z/my-project/emu/games_homebrew/patched/"
             "PSXMC_lic.cue")
ZENMAI_CUE = ("/home/z/my-project/emu/games_homebrew/patched/"
              "zenmai_lic.cue")

PSXMC_SHA = None   # filled from the local file at probe time
RAM_LIMIT = 0x200000


def churn_probe(env, label):
    p = env.p
    m = p.mem
    def snap():
        return np.frombuffer(bytes(m.snapshot()[:RAM_LIMIT]),
                             dtype=np.uint8)
    def frame():
        f = p.core.frame_rgb()
        return None if f is None else np.asarray(f, dtype=np.int16)
    out = {}
    p.core.run(30, set())
    s0, f0 = snap(), frame()
    p.core.run(60, set())
    s1, f1 = snap(), frame()
    out["idle_ram_churn"] = int(np.count_nonzero(s0 != s1))
    out["idle_px_churn"] = (None if f0 is None or f1 is None else
                            round(float(np.abs(f0 - f1).mean()), 2))
    s0, f0 = snap(), frame()
    p.core.run(60, {"RIGHT"})
    s2, f2 = snap(), frame()
    out["right_ram_churn"] = int(np.count_nonzero(s0 != s2))
    out["right_px_churn"] = (None if f0 is None or f2 is None else
                             round(float(np.abs(f0 - f2).mean()), 2))
    # the movement-correlated two-origin scan (u32 little-endian,
    # the common position encoding) — candidates whose u32 delta is
    # signed and flips sign LEFT vs RIGHT
    cands = None
    s0, f0 = snap(), frame()
    p.core.run(40, {"RIGHT"})
    sr = snap()
    p.core.run(10, set())
    s0b = snap()
    p.core.run(40, {"LEFT"})
    sl = snap()
    dr = sr.view("<i4") - s0b.view("<i4")
    dl = sl.view("<i4") - s0b.view("<i4")
    m2 = (np.abs(dr) > 100) & (np.abs(dl) > 100) & \
         (np.sign(dr) != np.sign(dl))
    idx = np.flatnonzero(m2)
    out["movement_corr_u32"] = [hex(int(i) * 4) for i in idx[:12]]
    out["n_movement_corr"] = int(idx.size)
    return out


def png(env, path):
    try:
        from PIL import Image
        f = env.p.core.frame_rgb()
        if f is not None:
            Image.fromarray(f).save(path)
            return path
    except Exception as e:                                  # noqa: BLE001
        return f"png failed: {repr(e)[:80]}"
    return None


def probe(cue, name, meta):
    out = {"game": name, "cue": cue, "meta": meta,
           "ts": time.strftime("%FT%TZ", time.gmtime())}
    if not os.path.exists(cue):
        out["verdict"] = "BLOCKED (image missing)"
        return out
    t0 = time.time()
    env = BaseEnv("/home/z/my-project/emu/ws_r66_side_" + name, cue)
    env.p.core.run(600, set())      # settle: BIOS shell -> game
    out["boot_settle_s"] = round(time.time() - t0, 1)
    out["frames_run"] = int(env.p.core.frames_run)
    out["probe"] = churn_probe(env, name)
    shots = os.path.join(EVID, "shots")
    os.makedirs(shots, exist_ok=True)
    out["shot_idle"] = png(env, os.path.join(shots, f"{name}_idle.png"))
    env.p.core.run(60, {"RIGHT"})
    out["shot_right"] = png(env, os.path.join(shots,
                                              f"{name}_right.png"))
    px, ram = out["probe"]["right_px_churn"], \
        out["probe"]["right_ram_churn"]
    ipx, iram = out["probe"]["idle_px_churn"], \
        out["probe"]["idle_ram_churn"]
    causal = (px is not None and ipx is not None and px > ipx * 2
              and px > 1.0) or (ram > iram * 3 and ram > 4000)
    out["input_causal"] = bool(causal)
    out["verdict"] = {
        True: "FEASIBLE (booted + input-causal on the R66 stack; "
              "the state model is the next step)",
        False: "INCONCLUSIVE (booted; input causality not shown by "
               "the generic probe — game-specific anchors needed)",
    }[bool(causal)]
    env.close()
    return out


def main():
    os.makedirs(EVID, exist_ok=True)
    # ---- 1. psx-minecraft (local lic image) -------------------------
    import hashlib
    binp = ("/home/z/my-project/emu/games_homebrew/patched/"
            "PSXMC_lic.bin")
    meta = {"license": "MIT",
            "size_bytes": os.path.getsize(binp) if
            os.path.exists(binp) else None,
            "sha256_lic_bin": hashlib.sha256(
                open(binp, "rb").read()).hexdigest()[:16] + "…"
            if os.path.exists(binp) else None}
    r1 = probe(PSXMC_CUE, "psxmc", meta)
    json.dump(r1, open(os.path.join(EVID, "psxmc_probe.json"), "w"),
              indent=1)
    print(name_res(r1))

    # ---- 2. zenmai --------------------------------------------------
    zbin = ("/home/z/my-project/emu/games_homebrew/patched/"
            "zenmai_lic.bin")
    meta2 = {"license": "MIT (+SIL-OFL font, +zlib MojoZork)",
             "size_bytes": os.path.getsize(zbin) if
             os.path.exists(zbin) else None}
    r2 = probe(ZENMAI_CUE, "zenmai", meta2)
    json.dump(r2, open(os.path.join(EVID, "zenmai_probe.json"), "w"),
              indent=1)
    print(name_res(r2))
    return 0


def name_res(r):
    return (f"{r['game']}: {r.get('verdict')} | "
            f"probe={r.get('probe')}")


if __name__ == "__main__":
    sys.exit(main())
