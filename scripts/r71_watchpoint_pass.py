#!/usr/bin/env python3
"""r71_watchpoint_pass.py — R71 experiment track: the restore-only
WATCHPOINT PASS on the score word 0x800EE318 (the capsule R71 lever,
SOURCE-FIRST).

The R69 verdict: "the payment writer NARROWED (the overlay damage
tail + the credit tables; the exact store is a RUNTIME fact for the
watchpoint hunt)".  The R71 capsule lever: "one restore-only
watchpoint pass on 0x800EE318 to log the payment-writer PC (the R69
xref: the overlay damage tail + the credit tables
0x8009C134/0x8009C48C/0x8009C91C); needs the frontier rebuild (the
disclosed contingency)".

THE HONEST TOOL LIMIT (disclosed): the beetle/libretro core exposes
RAM, frames and save states — NOT the CPU PC.  A literal PC log is
NOT obtainable on this stack.  The pass therefore delivers the
RUNTIME WATCHPOINT that IS obtainable, verbatim code path:

  * stage 1 — the tainted frontier rebuild (the R47/R66/R68 recipe
    VERBATIM via r66t1.do_stage1; the byte-exact precedent: the
    frontier_px 1254.8 7-for-7);
  * stage 2 — the verbatim R66 stage-2 pass B (r66t1.do_stage2
    only='b' — the R68 +500 tap replay path) with the WATCHPOINT
    TELEMETRY patched at the DISCLOSED R52 seam
    (R50T.frame_walk): per-frame score word reads (0x800EE318,
    the harness `watch` granularity) + at EVERY score change the
    full-RAM PAYMENT CLUSTER (diff_regions: which byte regions
    co-change with the payment) — the co-changing cluster is the
    runtime evidence that discriminates the R69 writer candidates
    (the overlay damage tail vs the HUD/credit cluster) by their
    MEMORY FOOTPRINT, the honest substitute for the PC.

  * the PC question answered honestly: the store site stays
    NARROWED (the R69 static verdict); the runtime pass pins the
    payment timeline + the clusters; a literal PC needs a
    CPU-instrumented core (PCSX-Redux's debugger — the R64 tools
    matrix oracle) — recorded as the follow-up, not claimed here.

No RAM writes anywhere.  Legal inputs only (pad buttons).  Ledger
cap 2 (stage 1 + stage 2), DISCLOSED PRE-RUN, written before boot.

Evidence: data/games/SLUS-01212/truck_evidence/r71/r71wp_*.jsonl
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
import r39t1_baseline as t1                        # noqa: E402
import r47t1_singletap_taps as R47T                # noqa: E402
from ps1play.core.memory import diff_regions       # noqa: E402

EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r71")
SCRATCH = os.path.join(_REPO, "scratch", "r71_exp")
r66t1.EVID = EVID
r66t1.SCRATCH = SCRATCH
r66t1.PNGDIR = os.path.join(SCRATCH, "pngs")
r66t1.LEDGER = os.path.join(SCRATCH, "boots_used.json")
R47T.PNGDIR = r66t1.PNGDIR

LEDGER = r66t1.LEDGER

WP_TAG = sys.argv[1] if len(sys.argv) > 1 else "r71wp"
STAGE = sys.argv[2] if len(sys.argv) > 2 else "1"


def log(*a):
    print("[r71wp]", *a, file=sys.stderr, flush=True)


def write_ledger():
    os.makedirs(SCRATCH, exist_ok=True)
    if not os.path.exists(LEDGER):
        with open(LEDGER, "w") as f:
            json.dump({"cap": 2, "count": 0, "log": [], "note":
                       "R71 watchpoint ledger cap 2 DISCLOSED PRE-RUN: "
                       "boot 1 = the tainted frontier rebuild (the "
                       "R47/R66/R68 recipe VERBATIM, the byte-exact "
                       "7-for-7 precedent); boot 2 = the verbatim "
                       "R66 stage-2 pass B (the +500 tap replay) "
                       "with the WATCHPOINT telemetry (the per-frame "
                       "score word 0x800EE318 + the payment-cluster "
                       "diff at every score change) patched at the "
                       "DISCLOSED R52 seam.  The literal PC is NOT "
                       "readable on beetle/libretro (the tool limit, "
                       "disclosed); the co-changing cluster is the "
                       "runtime writer evidence.  Lineage TAINTED "
                       "(never a clean claim).  m2_gate unchanged.",
                       "hypothesis":
                       "the payment cluster (the byte regions "
                       "co-changing with the 0x800EE318 payment) "
                       "discriminates the R69 writer candidates by "
                       "memory footprint: the overlay damage tail "
                       "writes the entity record + the accumulator "
                       "row; the HUD/credit cluster reads them — "
                       "the cluster at the pay frame is the "
                       "runtime fact"},
                      f, indent=1)


def amend_ledger(reason):
    write_ledger()
    with open(LEDGER) as f:
        led = json.load(f)
    if int(led.get("count", 0)) + 1 > int(led.get("cap", 0)):
        raise SystemExit("BOOT CAP EXCEEDED (r71wp ledger)")
    led["count"] = int(led.get("count", 0)) + 1
    led["log"].append({"n": led["count"],
                       "ts": time.strftime("%FT%TZ", time.gmtime()),
                       "script": "r71_watchpoint_pass.py",
                       "reason": reason})
    with open(LEDGER, "w") as f:
        json.dump(led, f, indent=1)
    log(f"boot ledger: count={led['count']}/{led['cap']} ({reason})")
    return led["count"]


# ------------------------------------------------------------------
# the WATCHPOINT frame walk (the disclosed R52 seam): the VERBATIM
# r66t1 rows + the per-frame score watch + the payment-cluster diff.
# ------------------------------------------------------------------
def frame_walk_hunt_wp(p, m, J, tap, phase, n_frames, btns):
    rows = []
    prev_ram = m.snapshot()
    prev_sc = int(m.u32(t1.A_SCORE))
    for k in range(n_frames):
        p.core.run(1, btns)
        cur_ram = m.snapshot()
        sc = int(m.u32(t1.A_SCORE))
        px = t1.px_of(m)
        ents = r66t1.mini_census(m, px)
        words = {}
        for e in ents:
            slot = e["slot"]
            if not slot or e["x"] == 0.0:
                continue
            base = r66t1.combat.TABLE + slot * r66t1.combat.STRIDE
            words[str(slot)] = [int(m.u16(base + off))
                                for off in r66t1._WORD_CACHE]
        if sc != prev_sc:
            # THE WATCHPOINT EVENT: the score word changed this
            # frame — the payment cluster = the co-changing RAM
            # regions (the writer's footprint).  R71WP_TOP (default
            # 24): the boot-3 amendment arm captures the FULL
            # cluster (top=200) — the boot-2 pass's top-24 cap cut
            # the 4-byte score-word region itself (ranked below the
            # 24 biggest co-changes by size; disclosed in the
            # report)
            top = int(os.environ.get("R71WP_TOP", "24"))
            diff = diff_regions(prev_ram, cur_ram, top=top)
            J({"ev": "PAYMENT_CLUSTER", "tap": tap, "phase": phase,
               "f_rel": k + 1, "from": prev_sc, "to": sc,
               "delta": sc - prev_sc,
               "score_addr": hex(t1.A_SCORE),
               "diff_top": top,
               "bytes_changed": diff["bytes_changed"],
               "regions": [[a, b, n] for a, b, n in
                           diff["regions"]]})
            log(f"PAYMENT {prev_sc}->{sc} (delta {sc - prev_sc}) "
                f"tap={tap} {phase} f_rel={k + 1} "
                f"clusters={len(diff['regions'])}")
        prev_ram = cur_ram
        prev_sc = sc
        rows.append({"f_rel": k + 1, "sc": sc, "px": round(px, 1),
                     "ents": ents,
                     "direct": r66t1.direct_table(m),
                     "words": words,
                     "net": [hex(o) for o in r66t1._WORD_CACHE]
                     if k == 0 else None})
    J({"ev": "FRAME_WALK", "tap": tap, "phase": phase,
       "n": n_frames, "rows": rows})
    return rows


def _diff_regions_capped(prev, cur):
    return diff_regions(prev, cur, top=24)


def main():
    write_ledger()
    T0 = time.time()
    r66t1.T0 = T0
    # the watchpoint patch (the disclosed seam; the verbatim rows)
    r66t1.frame_walk_hunt = frame_walk_hunt_wp
    r66t1.R50T.frame_walk = frame_walk_hunt_wp

    J = r66t1.J if hasattr(r66t1, "J") else None

    # the J sink: r66t1.do_stage1/do_stage2 take J as an argument
    def Jsink(ev):
        ev["wp_stage"] = STAGE
        path = os.path.join(EVID, f"{WP_TAG}_stage{STAGE}.jsonl")
        os.makedirs(EVID, exist_ok=True)
        with open(path, "a") as f:
            f.write(json.dumps(ev, default=str) + "\n")

    if STAGE == "1":
        n = amend_ledger("BOOT stage-1 (the tainted frontier "
                         "REBUILD; the disclosed capsule contingency: "
                         "the r66_frontier_a/b states are LOST again; "
                         "the R47/R66/R68 recipe verbatim, the "
                         "byte-exact 7-for-7 precedent; lineage "
                         "TAINTED — never a clean claim)")
        log("stage 1: the frontier rebuild (r66t1.do_stage1 "
            "verbatim)...")
        rc = r66t1.do_stage1(Jsink, f"{WP_TAG}_s1", f"{WP_TAG}_s1")
        log("stage 1 done rc=", rc)
        return rc
    if STAGE == "2":
        n = amend_ledger("BOOT stage-2 (the verbatim R66 pass B "
                         "restore-only tap replay with the "
                         "WATCHPOINT telemetry on 0x800EE318)")
        log("stage 2: the +500 tap replay + the watchpoint "
            "(r66t1.do_stage2 only='b' verbatim)...")
        rc = r66t1.do_stage2(Jsink, f"{WP_TAG}_s2", f"{WP_TAG}_s2",
                             only="b")
        log("stage 2 done rc=", rc)
        return rc
    raise SystemExit("usage: r71_watchpoint_pass.py <tag> [1|2]")


if __name__ == "__main__":
    sys.exit(main())
