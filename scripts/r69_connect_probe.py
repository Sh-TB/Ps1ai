#!/usr/bin/env python3
"""r69_connect_probe.py — the R69 connect-window diagnostic probe.

A READ-ONLY product-stack probe (the product-path diagnostic track,
the R64/R67/R68 diag precedent, disclosed in the round report).  It
answers exactly the R69 questions:

  WITH the connect-window policy (v1.7.0 C1): how many lobs fire
  INSIDE the window [125, 140], does the truck's armor a4 drop
  (the CONNECTS), where does the window close, and what kills the
  episode — the R69 product verdict on the capsule hypothesis
  (the band window ~280f => up to 7 throws => the kill inside the
  window at the measured rate).

Method: the REAL product loop (the registered adapter + the shipped
policy 1.7.0) with per-decision diagnostics; the FULL entity table
dumped EVERY frame from f=800 (the truck-fight window); PNGs at the
fight + the death.  No RAM writes.  Legal inputs only.  No gameplay
claim beyond the probe itself: a perception diagnostic.

Evidence: data/games/SLUS-01212/truck_evidence/r69/
          r69b_connect_probe.jsonl
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
                    "truck_evidence", "r69")

ACTION_BTNS = {
    "IDLE": frozenset(),
    "WALK": frozenset({"RIGHT"}),
    "BACK": frozenset({"LEFT"}),
    "FIRE": frozenset({"Y"}),
    "HOP": frozenset({"RIGHT", "B"}),
    "GRENADE": frozenset({"A"}),
}

TABLE_FROM = 700                  # the every-frame table window
MAX_F = 2200
SHOTS = (1000, 1100, 1150, 1200, 1250, 1300, 1350, 1400)


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


def log(*a):
    print("[r69-probe]", *a, file=sys.stderr, flush=True)


def main():
    os.makedirs(EVID, exist_ok=True)
    out_path = os.path.join(EVID, "r69b_connect_probe.jsonl")
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
    log("policy:", pol.identity().get("name"))

    ad.wait_ready(deadline_s=60.0)
    ad.start_episode(6)

    log("loop start")
    t0 = time.time()
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
        if f >= TABLE_FROM:
            row["table"] = full_table(env.p.mem)
        J(row)
        btns = ACTION_BTNS.get(dec.action, frozenset())
        env.run(1, set(btns))
        if f in SHOTS:
            try:
                from PIL import Image
                rgb = env.p.core.frame_rgb()
                if rgb is not None:
                    p = os.path.join(EVID, f"r69_probe_f{f}.png")
                    Image.fromarray(rgb).save(p)
                    J({"f": f, "ev": "SHOT", "path": p})
            except Exception as e:                      # noqa: BLE001
                J({"f": f, "ev": "SHOT_FAIL", "err": repr(e)[:80]})
        if not ad.alive():
            J({"f": f, "ev": "DEATH",
               "px": round(float(x[0]), 1), "score": int(x[1]),
               "table": full_table(env.p.mem)})
            try:
                from PIL import Image
                rgb = env.p.core.frame_rgb()
                if rgb is not None:
                    p = os.path.join(EVID, "r69_probe_death.png")
                    Image.fromarray(rgb).save(p)
            except Exception:                            # noqa: BLE001
                pass
            log(f"DEATH at f={f} px={x[0]:.0f} score={int(x[1])}")
            break
        if time.time() - t0 > 420:
            J({"f": f, "ev": "WALL_END"})
            break
    jf.close()
    log("probe ->", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
