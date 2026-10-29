#!/usr/bin/env python3
"""r50_analysis_correct.py — R50 offline CORRECTED analysis (no boot).

The authoritative readout for the controlled-corridor round.  Built
on the R49 v2 global-frame per-slot matcher, plus:
  1. the corridor verification: for every fired tap, re-derive the
     pre-fire corridor from row-1 direct tables (player_x_at_fire +
     target x) and verify NO live slot stood inside — the fired-tap
     clearance is procedural (pick_target gate) but re-derived here
     for the record;
  2. the CONNECT-magnitude focus: every payment in a CONNECT window
     with its co-landing candidates (lag-0 registrations, 0x42bc
     holders, recovery chains) — the +500-vs-+1000 question;
  3. the 0xae7c census: every 0xae7c-class slot's full cycle dated
     (spawn/hold/registration/corpse) + any co-landing payment —
     the b-tap1 (R49) residual candidate;
  4. the controls: zero-input AND movement-only windows must pay 0
     (the churn baseline, now with movement).
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r50")
CONNECT_ST = 0x42BC
REG_ST = 0x515C
CORPSE_ST = 0x4BE4
AE7C_ST = 0xAE7C
LAG_LO, LAG_HI = -2, 6


def load(path):
    taps = []
    with open(path) as f:
        for line in f:
            ev = json.loads(line)
            if ev.get("ev") == "TAP":
                taps.append(ev)
    return taps


def main():
    path = os.path.join(EVID, "r50_boot2.jsonl")
    taps = load(path)
    report = {"schema": "ps1play.r50-analysis/1", "input": path,
              "generated": time.strftime("%FT%TZ", time.gmtime()),
              "payments": [], "controls": [], "ae7c_cycles": [],
              "corridor_violations": [], "ledger": {}}
    for fr in ("r47_frontier_a", "r47_frontier_b"):
        seq = []
        tap_meta = []
        for t in [x for x in taps if x["frontier"] == fr]:
            base = len(seq)
            for row in t["frame_rows"]:
                seq.append({"sc": row["sc"], "direct": row["direct"],
                            "tap": t["tap"],
                            "intent": t.get("intent", "CONTROL")})
            tap_meta.append((t, base))
        hist = {}
        for gf, r in enumerate(seq):
            for d in r["direct"]:
                hist.setdefault(d["slot"], []).append(
                    (gf, d["st"], d["x"]))

        def transitions(slot, st_to):
            out = []
            h = hist.get(slot, [])
            for i in range(1, len(h)):
                if h[i][1] == st_to and h[i - 1][1] != st_to:
                    out.append({"gf": h[i][0], "x": h[i][2],
                                "from": h[i - 1][1]})
            return out

        # ---- the corridor verification per fired tap ----------------
        for t, base in tap_meta:
            if t.get("intent") not in ("CONNECT", "KILL") \
                    or not t.get("target"):
                continue
            tgt = t["target"]
            px = t.get("player_x_at_fire")
            if px is None:
                continue
            lo, hi = min(px, tgt["x_px"]), max(px, tgt["x_px"])
            for d in seq[base]["direct"]:
                if d["slot"] == tgt["slot"] or d["st"] == CORPSE_ST \
                        or d["x"] <= 0.0:
                    continue
                if lo < d["x"] < hi:
                    report["corridor_violations"].append(
                        {"pass": fr[-1], "tap": t["tap"],
                         "slot": d["slot"], "x": d["x"],
                         "st": d["st"]})
        # ---- payments ------------------------------------------------
        for i in range(1, len(seq)):
            a, b = seq[i - 1], seq[i]
            d = b["sc"] - a["sc"]
            if d == 0:
                continue
            intent = b["intent"]
            ev = {"pass": fr[-1], "gf": i, "d": d, "sc": b["sc"],
                  "tap": b["tap"], "intent": intent}
            if intent == "CONTROL":
                ev["class"] = "CONTROL_PAID"
                report["controls"].append(ev)
                report["payments"].append(ev)
                continue
            regs = []
            for s in hist:
                for tr in transitions(s, REG_ST):
                    if LAG_LO <= tr["gf"] - i <= LAG_HI:
                        regs.append({"slot": s, "lag": tr["gf"] - i,
                                     "x": tr["x"]})
            holders42 = [s for s, h in hist.items()
                         if any(g == i and st == CONNECT_ST
                                for g, st, _x in h)]
            holders_ae7c = [s for s, h in hist.items()
                            if any(g == i and st == AE7C_ST
                                   for g, st, _x in h)]
            ev["regs"] = regs
            ev["holders_0x42bc"] = holders42
            ev["holders_0xae7c"] = holders_ae7c
            if regs and d == 100:
                ev["class"] = "KILL_REG"
            elif holders42 and not regs:
                ev["class"] = "CONNECT_0x42bc"
            elif holders_ae7c and not regs:
                ev["class"] = "CONTEXT_0xae7c"
            else:
                ev["class"] = "UNATTRIBUTED"
            report["payments"].append(ev)
        # ---- the 0xae7c census --------------------------------------
        for s, h in hist.items():
            if not any(st == AE7C_ST for _g, st, _x in h):
                continue
            cyc = {"pass": fr[-1], "slot": s,
                   "ae7c_frames": [g for g, st, _x in h
                                   if st == AE7C_ST],
                   "registrations": transitions(s, REG_ST),
                   "corpses": transitions(s, CORPSE_ST),
                   "x_first": h[0][2], "x_last": h[-1][2]}
            paid = [p for p in report["payments"]
                    if p["pass"] == fr[-1]
                    and any(r["slot"] == s for r in p.get("regs", []))]
            cyc["co_landing_payments"] = paid
            report["ae7c_cycles"].append(cyc)
        report["ledger"][fr] = {
            "score_start": seq[0]["sc"], "score_end": seq[-1]["sc"],
            "delta": seq[-1]["sc"] - seq[0]["sc"]}
    # ---- verdict ------------------------------------------------------
    pays = report["payments"]
    ctrl_paid = [p for p in pays if p["class"] == "CONTROL_PAID"]
    conn500 = [p for p in pays if p["class"] == "CONNECT_0x42bc"
               and p["d"] == 500]
    conn1000 = [p for p in pays if p["class"] == "CONNECT_0x42bc"
                and p["d"] != 500]
    kill = [p for p in pays if p["class"] == "KILL_REG"]
    unattr = [p for p in pays if p["class"] == "UNATTRIBUTED"]
    verdict = {
        "controls_all_zero": len(ctrl_paid) == 0,
        "n_control_windows": len([t for t in taps
                                  if "CONTROL" in (t.get("kind", "")
                                                   + t.get("intent",
                                                           ""))]),
        "connect_0x42bc_500": [dict(p, regs=p.get("regs"))
                               for p in conn500],
        "connect_0x42bc_non500": [dict(p, regs=p.get("regs"))
                                  for p in conn1000],
        "kill_reg_100": [{"pass": p["pass"], "gf": p["gf"],
                          "regs": p["regs"]} for p in kill],
        "unattributed": [{"pass": p["pass"], "gf": p["gf"],
                          "d": p["d"], "regs": p.get("regs"),
                          "42bc": p.get("holders_0x42bc"),
                          "ae7c": p.get("holders_0xae7c")}
                         for p in unattr],
        "corridor_violations": report["corridor_violations"],
        "ae7c_cycles": report["ae7c_cycles"],
    }
    verdict["CONNECT_MAGNITUDE_SETTLED"] = bool(
        len(conn500) >= 3 and not conn1000)
    report["verdict"] = verdict
    op = os.path.join(EVID, "r50_corridor_table.json")
    with open(op, "w") as f:
        json.dump(report, f, indent=1, default=str)
    print("=== R50 CORRECTED VERDICT (offline, authoritative) ===")
    print("controls paid:", len(ctrl_paid),
          "| corridor violations:", len(report["corridor_violations"]))
    print("CONNECT 0x42bc +500:", [(p["pass"], p["gf"], p["d"])
                                   for p in conn500])
    print("CONNECT 0x42bc non-500:", [(p["pass"], p["gf"], p["d"],
                                       p.get("holders_0x42bc"))
                                      for p in conn1000])
    print("KILL_REG +100:", [(p["pass"], p["gf"], p["regs"])
                             for p in kill])
    print("UNATTRIBUTED:", [(p["pass"], p["gf"], p["d"],
                             p.get("holders_0xae7c"))
                            for p in unattr])
    print("0xae7c cycles:",
          [(c["pass"], c["slot"], len(c["ae7c_frames"]),
            len(c["co_landing_payments"])) for c in
           report["ae7c_cycles"]])
    print("ledger:", report["ledger"])
    print("CONNECT_MAGNITUDE_SETTLED:",
          verdict["CONNECT_MAGNITUDE_SETTLED"])
    print("written:", op)
    return 0


if __name__ == "__main__":
    sys.exit(main())
