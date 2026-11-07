#!/usr/bin/env python3
"""r67_product_loop_probe.py — the R67 instrumented product-loop probe.

The REAL product loop (the registered adapter + the shipped policy)
with per-decision diagnostics: every frame's (px, score, gren, php,
mortals, rule, action).  Read-only, legal inputs, no claims — the
diagnostic track answering WHY the v1.2.0 product run died at 888f
with score 0 and full grenades.

Evidence: data/games/SLUS-01212/truck_evidence/r67/
          r67_product_loop_probe.jsonl
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

EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r67")

ACTION_BTNS = {
    "IDLE": frozenset(),
    "WALK": frozenset({"RIGHT"}),
    "FIRE": frozenset({"Y"}),
    "HOP": frozenset({"RIGHT", "B"}),
    "GRENADE": frozenset({"A"}),
}


def log(*a):
    print("[r67-loop]", *a, file=sys.stderr, flush=True)


def main():
    out_path = os.path.join(EVID, "r67_product_loop_probe.jsonl")
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

    # the engine's verbatim ready flow: settle -> nav -> START taps
    # -> ownership -> the mission gate
    ad.wait_ready(deadline_s=60.0)
    ad.start_episode(6)

    log("loop start")
    t0 = time.time()
    for f in range(1, 1900):
        frame = Frame(seq=f, emulator_frame_count=f, rgb=None,
                      timestamp=float(f), stale=False)
        obs = ad.observe(frame)
        dec = pol.predict(obs)
        x = obs.values
        J({"f": f, "px": round(float(x[0]), 1),
           "score": int(x[1]), "php": int(x[2]), "gren": int(x[3]),
           "alive": float(x[4]) > 0.5,
           "ents": [[round(float(x[6 + 3 * i]), 1),
                     int(x[7 + 3 * i]), int(x[8 + 3 * i])]
                    for i in range(5)
                    if not (x[7 + 3 * i] == 0 and x[6 + 3 * i] == 0)],
           "rule": dec.diagnostics.get("rule"),
           "act": dec.action})
        if f % 10 == 0:
            J({"f": f, "ev": "TABLE", "px": round(float(x[0]), 1),
               "rows": full_table(env.p.mem)})
        btns = ACTION_BTNS.get(dec.action, frozenset())
        env.run(1, set(btns))
        if f in (30, 240, 480, 900):
            try:
                from PIL import Image
                rgb = env.p.core.frame_rgb()
                if rgb is not None:
                    Image.fromarray(rgb).save(
                        f"/tmp/r67_loop_f{f}.png")
                    J({"f": f, "ev": "SHOT", "path":
                       f"/tmp/r67_loop_f{f}.png"})
            except Exception as e:                      # noqa: BLE001
                J({"f": f, "ev": "SHOT_FAIL", "err": repr(e)[:80]})
        if not ad.alive():
            J({"f": f, "ev": "DEATH",
               "px": round(float(x[0]), 1), "score": int(x[1])})
            log(f"DEATH at f={f} px={x[0]:.0f} score={int(x[1])}")
            break
        if time.time() - t0 > 200:
            J({"f": f, "ev": "WALL_END"})
            break
    jf.close()
    log("probe ->", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
