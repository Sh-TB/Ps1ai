#!/usr/bin/env python3
"""r67_truckzone_probe.py — the R67 truck-campaign diagnostic probe.

A READ-ONLY product-stack probe (no experiment-ledger boot: this is
the product-path diagnostic track, the R64 diag precedent, disclosed
in the round report).  It answers exactly one question:

  WHICH entities present (state-code 6, h==64) to the policy between
  the spawn and the truck zone — the T1 truck identity the R67 ep2
  hold got stuck on (px ~493) — and what killed the R67 ep1 at 378f
  (score 0, pre-truck).

Method: boot the real product stack, walk RIGHT from the spawn with
the shipped policy cadence, and every 30 frames dump the FULL entity
table (slots 1..39: st / x / h / a4 / sx) — the same read-only reads
the adapter does.  No RAM writes.  Legal inputs only.  No gameplay
claim: this is a perception diagnostic.

Evidence: data/games/SLUS-01212/truck_evidence/r67/r67_truckzone_probe.jsonl
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

import ps1play.agent.combat as combat             # noqa: E402
from r39t1_baseline import px_of, snap, alive     # noqa: E402
from issue4_controller import boot                # noqa: E402
from ps1play.adapters.metal_slug_x.adapter import (  # noqa: E402
    TABLE, STRIDE, SLOTS, CORPSE_ST, state_code)

EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r67")


def log(*a):
    print("[r67-probe]", *a, file=sys.stderr, flush=True)


def full_table(m):
    rows = []
    for s in range(1, SLOTS):
        base = TABLE + s * STRIDE
        st = int(m.u16(base))
        xw = int(m.u32(base + 0x78))
        if not xw:
            continue
        x = xw / 65536.0
        h = int(m.u16(base + 0x7E))
        a4 = int(m.u16(base + 0xA4))
        sx = int(m.u16(base + 0x8E))
        rows.append({"slot": s, "st": st, "st_hex": hex(st),
                     "x": round(x, 1), "h": h, "a4": a4, "sx": sx,
                     "corpse": st in CORPSE_ST,
                     "code": state_code(st)})
    return rows


def main():
    out_path = os.path.join(EVID, "r67_truckzone_probe.jsonl")
    jf = open(out_path, "w")

    def J(ev):
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    log("booting the product stack (read-only probe)...")
    p, fwmode = boot()
    m = p.mem
    J({"ev": "BOOTED", "fw": fwmode, "world": snap(m)})
    t0 = time.time()
    px_prev = px_of(m)
    for k in range(120):                    # 120 * 30f = 3600 frames
        p.core.run(30, {"RIGHT"})
        px = px_of(m)
        rows = full_table(m)
        interesting = [r for r in rows
                       if not r["corpse"] and r["sx"] > 0
                       and abs(r["x"] - px) <= 260.0]
        J({"ev": "SCAN", "k": k, "f": (k + 1) * 30, "px": round(px, 1),
           "score": int(m.u32(0x0EE318)),
           "near": interesting})
        sc6h64 = [r for r in interesting
                  if r["code"] == 6 and r["h"] >= 64]
        if sc6h64:
            log(f"k={k} px={px:.0f} SC6-h64: "
                + ", ".join(f"slot{r['slot']} {r['st_hex']} x={r['x']} "
                            f"h={r['h']} a4={r['a4']}"
                            for r in sc6h64))
        if not alive(m):
            J({"ev": "DEATH", "k": k, "px": round(px, 1)})
            log(f"DEATH at k={k} px={px:.0f}")
            s = snap(m)
            J({"ev": "DEATH_WORLD", **s})
            break
        if time.time() - t0 > 240:
            J({"ev": "WALL_END", "k": k, "px": round(px, 1)})
            break
    jf.close()
    log("probe ->", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
