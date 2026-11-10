#!/usr/bin/env python3
"""r70_phase_probe.py — R70 product-track boot 1: THE PHASE LAW probe.

A READ-ONLY product-stack probe (the R64/R67/R68/R69 diagnostic
precedent, disclosed in the round report).  It runs the REAL product
loop (the registered adapter v0.5.0 + the shipped policy v1.8.0) and
answers exactly the R70 questions:

  P3: does the k=0 LEAD throw fire during the drive-in, and does a
      lob landing at freeze+14 (f825 on the r69b timeline) CONNECT?
      -> the R70 falsifiable arm (the grid's backward extrapolation).
  P1: do the grid throws land at freeze+178+164k and CONNECT (the
      r69b f989/f1153 pair, now deterministic)?
  THE KILL: three connects drive a4 300 -> 0 — the truck dies
      ~165f before the scripted scroll death at f1318?

Method: the real adapter + the real policy, per-decision diagnostics;
the FULL entity table dumped every frame from f=650 (the drive-in +
the whole fight); PNGs at the lead throw, each connect, the kill and
the death.  No RAM writes.  Legal inputs only.  No gameplay claim
beyond the probe itself: a perception diagnostic.

Evidence: data/games/SLUS-01212/truck_evidence/r70/
          r70_phase_probe.jsonl
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

from ps1play.runtime.config import RuntimeConfig  # noqa: E402
from ps1play.runtime.registry import (            # noqa: E402
    adapter_for_game, make_env, policy_for_game)
from ps1play.runtime.interfaces import Frame      # noqa: E402
from ps1play.adapters.metal_slug_x.adapter import (  # noqa: E402
    TABLE, STRIDE, SLOTS, CORPSE_ST)

EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r70")

ACTION_BTNS = {
    "IDLE": frozenset(),
    "WALK": frozenset({"RIGHT"}),
    "BACK": frozenset({"LEFT"}),
    "FIRE": frozenset({"Y"}),
    "HOP": frozenset({"RIGHT", "B"}),
    "GRENADE": frozenset({"A"}),
}

TABLE_FROM = 650                  # the every-frame table window
MAX_F = 2400
SHOTS = (790, 795, 800, 811, 820, 825, 830, 900, 985, 990, 1140,
         1150, 1155, 1200, 1300)


def full_table(m):
    rows = []
    for s in range(1, SLOTS):
        base = TABLE + s * STRIDE
        st = int(m.u16(base))
        xw = int(m.u32(base + 0x78))
        if not xw:
            continue
        rows.append({"slot": s, "st": hex(st),
                     "x": round(xw / 65536.0, 1),
                     "h": int(m.u16(base + 0x7E)),
                     "a4": int(m.u16(base + 0xA4)),
                     "sx": int(m.u16(base + 0x8E)),
                     "corpse": st in CORPSE_ST})
    return rows


def shot(env, path):
    try:
        from PIL import Image
        rgb = env.p.core.frame_rgb()
        if rgb is not None:
            Image.fromarray(rgb).save(path)
            return True
    except Exception:                                 # noqa: BLE001
        pass
    return False


def log(*a):
    print("[r70-probe]", *a, file=sys.stderr, flush=True)


def main():
    os.makedirs(EVID, exist_ok=True)
    out_path = os.path.join(EVID, "r70_phase_probe.jsonl")
    jf = open(out_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    log("booting the product stack (the engine's verbatim wiring)...")
    cfg = RuntimeConfig(game="metal_slug_x", episodes=1,
                        max_frames_per_episode=10000,
                        output_dir="")
    env = make_env(cfg)                    # the fresh BaseEnv boot
    ad = adapter_for_game("metal_slug_x", env)
    pol = policy_for_game(cfg)
    ident = pol.identity()
    log("policy:", ident.get("name"), "| adapter:",
        ad.version if hasattr(ad, "version") else "?")

    ad.wait_ready(deadline_s=90.0)
    ad.start_episode(6)

    log("loop start")
    t0 = time.time()
    truck_a4_prev = None
    for f in range(1, MAX_F):
        frame = Frame(seq=f, emulator_frame_count=f, rgb=None,
                      timestamp=float(f), stale=False)
        obs = ad.observe(frame)
        dec = pol.predict(obs)
        x = obs.values
        row = {"f": f, "px": round(float(x[0]), 1),
               "score": int(x[1]), "php": int(x[2]), "gren": int(x[3]),
               "alive": float(x[4]) > 0.5,
               "ents": [[round(float(x[6 + 3 * i]), 1),
                         int(x[7 + 3 * i]), int(x[8 + 3 * i])]
                        for i in range(5)
                        if not (x[7 + 3 * i] == 0
                                and x[6 + 3 * i] == 0)],
               "rule": dec.diagnostics.get("rule"),
               "act": dec.action}
        rule = dec.diagnostics.get("rule") or ""
        if rule in ("truck_lead_throw", "truck_connect_grenade",
                    "truck_phase_hold", "truckin_hold",
                    "truckin_approach", "truck_lead_turn"):
            row["diag"] = {k: v for k, v in dec.diagnostics.items()
                           if k != "rule"}
        if f >= TABLE_FROM:
            tab = full_table(env.p.mem)
            row["table"] = tab
            # the truck armor watch (slot 14 = the r69b truck row;
            # keyed on the state family, not the slot number)
            for e in tab:
                if e["st"] in ("0x9e88", "0x9c14", "0x9e08"):
                    if truck_a4_prev is not None \
                            and e["a4"] != truck_a4_prev:
                        J({"f": f, "ev": "A4_TRANSITION",
                           "from": truck_a4_prev, "to": e["a4"],
                           "st": e["st"], "x": e["x"],
                           "prev_rule": rule})
                        p = os.path.join(
                            EVID, f"r70_connect_f{f}.png")
                        shot(env, p)
                    truck_a4_prev = e["a4"]
        J(row)
        if f in SHOTS:
            p = os.path.join(EVID, f"r70_probe_f{f}.png")
            if shot(env, p):
                J({"f": f, "ev": "SHOT", "path": p})
        btns = ACTION_BTNS.get(dec.action, frozenset())
        env.run(1, set(btns))
        if not ad.alive():
            J({"f": f, "ev": "DEATH",
               "px": round(float(x[0]), 1), "score": int(x[1]),
               "table": full_table(env.p.mem)})
            shot(env, os.path.join(EVID, "r70_probe_death.png"))
            log(f"DEATH at f={f} px={x[0]:.0f} score={int(x[1])}")
            break
        if time.time() - t0 > 500:
            J({"f": f, "ev": "WALL_END"})
            break
    jf.close()
    log("probe ->", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
