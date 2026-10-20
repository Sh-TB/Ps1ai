#!/usr/bin/env python3
"""issue5_probe3.py — mapping ground truth + player axis + GS sweep.

V1  region-wide verbatim diff: ram[base:base+len(ENEMY)] vs file bytes,
    list every mismatch run (settles the 0xC0 anomaly definitively).
V2  all-hits scan (limit 10) for the code-head pattern + explicit check
    of the verbatim-expected slot.
V3  MISSION.BIN residency: 5 patterns across the file.
V4  player axis discovery via verify_player_axis (RIGHT), causal LEFT
    cross-check on top candidates, struct context around the winner.
V5  GS lives/hp triple-cluster sweep around published addresses.
"""
import json
import os
import sys
import time

import numpy as np

_REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "scripts"))

from ps1play import labconfig                                # noqa: E402
from mission import ensure_mission                           # noqa: E402
from issue4_real_start import boot_to_demo, owns_pad         # noqa: E402

EV = "/home/z/my-project/work/msx_recomp/evidence/issue5_probe"
ENEMY = os.path.join(_REPO, "ps1play", "re", "ENEMY.BIN")
MISSION = os.path.join(_REPO, "ps1play", "re", "MISSION.BIN")

LOG = []


def log(ev, **kw):
    rec = {"t": time.strftime("%FT%TZ", time.gmtime()), "event": ev, **kw}
    LOG.append(rec)
    print(f"[probe3] {json.dumps(rec, default=str)[:500]}", flush=True)


def save():
    os.makedirs(EV, exist_ok=True)
    with open(os.path.join(EV, "probe3.jsonl"), "w") as f:
        for r in LOG:
            f.write(json.dumps(r, default=str) + "\n")


def pattern_hits(ram, pat, limit=10):
    pat = np.frombuffer(pat, np.uint8) if isinstance(pat, bytes) else pat
    hits = []
    cand = np.flatnonzero(ram[:len(ram) - len(pat)] == pat[0])
    for k in cand.tolist():
        if np.array_equal(ram[k:k + len(pat)], pat):
            hits.append(int(k))
            if len(hits) >= limit:
                break
    return hits


def mismatch_runs(a, b, min_run=8):
    """Ranges where byte arrays differ (min run length)."""
    if len(a) > len(b):
        a, b = b, a
    neq = np.flatnonzero(np.frombuffer(a, np.uint8)
                         != np.frombuffer(b[:len(a)], np.uint8))
    runs = []
    for k in neq.tolist():
        if runs and k - runs[-1][1] <= 4:
            runs[-1][1] = k
        else:
            runs.append([k, k])
    return [[s, e] for s, e in runs if e - s + 1 >= min_run]


def main():
    p = boot_to_demo()
    owned = False
    for _ in range(6):
        p.core.run(12, {"START"})
        p.core.run(150, set())
        if owns_pad(p, frames=30)["owns"]:
            owned = True
            break
    if not owned:
        sys.exit("ownership failed")
    g = ensure_mission(p, log=lambda *a: None, want_hp_cands=False)
    log("mission_gate", in_mission=bool(g.get("in_mission")))
    if not g.get("in_mission"):
        sys.exit("not in mission")
    mem = p.mem
    ram = mem.ram
    enemy = open(ENEMY, "rb").read()

    # ---- V1: region-wide verbatim diff at the anchor base ---------
    base = 0x9C0E8
    live = bytes(ram[base:base + len(enemy)])
    runs = mismatch_runs(live, enemy, min_run=8)
    log("V1_region_diff", base=f"0x{base:X}",
        file_len=len(enemy), n_mismatch_runs=len(runs),
        runs=[[f"0x{s:X}", f"0x{e:X}"] for s, e in runs[:20]])

    # ---- V2: code-head pattern, all hits + expected slot ----------
    pat = enemy[0xD180:0xD1A0]
    log("V2_codehead_all_hits",
        hits=[f"0x{h:X}" for h in pattern_hits(ram, pat, 10)])
    exp = base + 0xD180
    log("V2_verbatim_slot_match",
        at=f"0x{exp:X}",
        match=bool(ram[exp:exp + 32].tobytes() == pat))

    # ---- V3: MISSION.BIN residency --------------------------------
    mission = open(MISSION, "rb").read()
    for off in (0x0, 0x1000, 0x2000, 0x3000, 0x4000):
        h = pattern_hits(ram, mission[off:off + 24], 3)
        log("V3_mission_pattern", off=f"0x{off:X}",
            hits=[f"0x{x:X}" for x in h])

    # ---- V4: player axis discovery (needs a savestate to restore) -
    log("V4_axis_right_start")
    try:
        p.save_state("verify_base")
        cands = p.verify_player_axis(buttons="RIGHT", topk=10,
                                     frames=60)
        log("V4_axis_right",
            cands=[{"addr": f"0x{c['addr']:X}",
                    "dtype": c.get("dtype"),
                    "quality": round(c.get("quality", 0), 3)}
                   for c in (cands or [])[:10]])
        # causal LEFT/RIGHT cross-check on the best candidate
        def rd(addr, dtype):
            m = p.mem
            return {"u8": m.u8, "u16": m.u16, "u32": m.u32}.get(
                (dtype or "u16").lower(), m.u16)(addr)

        if cands:
            best = cands[0]
            a = best["addr"]
            v0 = rd(a, best.get("dtype"))
            p.core.run(60, {"LEFT"})
            vl = rd(a, best.get("dtype"))
            p.core.run(60, {"RIGHT"})
            vr = rd(a, best.get("dtype"))
            log("V4_axis_causal", addr=f"0x{a:X}", v0=v0,
                after_left=vl, after_right=vr,
                causal=bool(vl < v0 < vr))
    except Exception as e:                      # noqa: BLE001
        log("V4_axis_error", err=repr(e)[:300])
    save()

    # ---- V5: GS lives/hp sweep around published addresses ---------
    sweep = []
    for d in range(-0x4000, 0x4000, 0x10):
        a = 0x475A8 + d
        l = mem.u16(a)
        if 1 <= l <= 9:
            h = mem.u16(0x32764 + d)
            if 0 <= h <= 200:
                sweep.append({"phys": f"0x{a:X}", "lives?": l,
                              "hp?": h})
    log("V5_gs_sweep", n=len(sweep), top=sweep[:20])
    save()
    print("probe3 done")


if __name__ == "__main__":
    main()
