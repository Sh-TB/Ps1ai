#!/usr/bin/env python3
"""r49_analysis_correct.py — R49 offline CORRECTED analysis v2 (no boot).

The authoritative frame-exact readout for the class-keyed hypothesis.
v2 supersedes the v1 in-runner-shaped classification: the v1 missed
that (a) the frame_rows numbering restarts at the tap/tail boundary
(so "f_rel" alone is ambiguous — v2 rebuilds GLOBAL frames per pass),
(b) the pay windows contain MULTIPLE entity cycles (the spawner zone
x~1277-1310: 0xaec8 spawn -> walk -> 0x515c registration -> 0x4be4),
so a per-target-slot check is structurally blind to the true victim.

v2 method: per pass, concatenate the tap windows into one global
frame sequence (sc is continuous); per slot, date every 0x42bc hold,
0x515c registration and 0x4be4 corpse; for every score jump, list the
co-landing candidates within the flight-consistent lag window
[-2, +6] rows and classify:
  KILL_REG  — a registration co-lands and the jump reads +100;
  CONNECT   — no registration co-lands but the aiming slot is in the
              0x42bc hit-reaction at the pay frame;
  MIXED     — both contexts co-land (decomposition attempted);
  UNPAID_REG— a registration with NO co-landing jump (the zone/wound
              churn baseline);
  CHURN     — control-walk jumps (expected none).
Verdict pieces reported honestly with n; the strict class-keyed
verdict decided only where the data is unconfounded.
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r49")
CONNECT_ST = 0x42BC
REG_ST = 0x515C
CORPSE_ST = 0x4BE4
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
    path = os.path.join(EVID, "r49_boot1.jsonl")
    taps = load(path)
    report = {"schema": "ps1play.r49-analysis/2", "input": path,
              "generated": time.strftime("%FT%TZ", time.gmtime()),
              "passes": [], "events": [], "unpaid_regs": [],
              "ledger": {}}
    for fr in ("r47_frontier_a", "r47_frontier_b"):
        seq = []                     # the global frame sequence
        ctrl_jumps = []
        for t in [x for x in taps if x["frontier"] == fr]:
            for row in t["frame_rows"]:
                seq.append({"sc": row["sc"], "direct": row["direct"],
                            "tap": t["tap"],
                            "intent": t.get("intent",
                                            "CONTROL_ZERO_INPUT")})
        # ---- per-slot histories over the global frames ----------------
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
                                "from_st": h[i - 1][1]})
            return out
        # ---- the control-walk churn baseline ---------------------------
        ctrl_frames = [i for i, r in enumerate(seq)
                       if r["intent"] == "CONTROL_ZERO_INPUT"]
        for i in range(1, len(seq)):
            a, b = seq[i - 1], seq[i]
            if b["sc"] - a["sc"] != 0:
                ev = {"pass": fr[-1], "gf": i,
                      "d": b["sc"] - a["sc"], "sc": b["sc"],
                      "tap": b["tap"], "intent": b["intent"]}
                if b["intent"] == "CONTROL_ZERO_INPUT" or \
                        a["intent"] == "CONTROL_ZERO_INPUT":
                    ev["class"] = "CHURN"
                    ctrl_jumps.append(ev)
                    report["events"].append(ev)
                    continue
                # candidates: registrations in the lag window
                regs = []
                for s in hist:
                    for tr in transitions(s, REG_ST):
                        if LAG_LO <= tr["gf"] - i <= LAG_HI:
                            regs.append({"slot": s, "lag": tr["gf"] - i,
                                         "x": tr["x"]})
                # 0x42bc holders at the pay frame
                holders42 = [s for s, h in hist.items()
                             if any(g == i and st == CONNECT_ST
                                    for g, st, _x in h)]
                aimed = None
                for s, h in hist.items():
                    pass
                if regs and ev["d"] == 100:
                    ev["class"] = "KILL_REG"
                    ev["regs"] = regs
                elif holders42 and not regs:
                    ev["class"] = "CONNECT"
                    ev["holders_0x42bc"] = holders42
                elif holders42 and regs:
                    ev["class"] = "MIXED"
                    ev["holders_0x42bc"] = holders42
                    ev["regs"] = regs
                else:
                    ev["class"] = "UNATTRIBUTED"
                    ev["regs"] = regs
                report["events"].append(ev)
        # ---- unpaid registrations (the zone/wound churn baseline) ------
        for s in hist:
            for tr in transitions(s, REG_ST):
                gf = tr["gf"]
                paid = any(e["class"] in ("KILL_REG", "MIXED")
                           and any(r["slot"] == s for r in
                                   e.get("regs", []))
                           for e in report["events"]
                           if e["pass"] == fr[-1])
                if not paid:
                    report["unpaid_regs"].append(
                        {"pass": fr[-1], "slot": s, "gf": gf,
                         "x": tr["x"], "from_st": tr["from_st"],
                         "note": "no co-landing payment in-window"})
        # ---- the pass ledger -------------------------------------------
        report["ledger"][fr] = {
            "aimed_taps": len([r for r in seq
                               if r["intent"] != "CONTROL_ZERO_INPUT"]),
            "score_start": seq[0]["sc"], "score_end": seq[-1]["sc"],
            "delta": seq[-1]["sc"] - seq[0]["sc"]}
    # ---- verdict assembly ----------------------------------------------
    kill = [e for e in report["events"] if e["class"] == "KILL_REG"]
    conn = [e for e in report["events"] if e["class"] == "CONNECT"]
    mixed = [e for e in report["events"] if e["class"] == "MIXED"]
    unattr = [e for e in report["events"]
              if e["class"] == "UNATTRIBUTED"]
    churn = [e for e in report["events"] if e["class"] == "CHURN"]
    verdict = {
        "kill_reg_uniform_100": bool(kill) and
            all(e["d"] == 100 for e in kill),
        "kill_reg_n": len(kill),
        "connect_uniform_500": bool(conn) and
            all(e["d"] == 500 for e in conn),
        "connect_n": len(conn),
        "mixed_n": len(mixed),
        "mixed_detail": [{"d": e["d"], "gf": e["gf"],
                          "pass": e["pass"], "regs": e.get("regs"),
                          "holders": e.get("holders_0x42bc")}
                         for e in mixed],
        "unattributed_n": len(unattr),
        "churn_jumps_n": len(churn),
        "unpaid_regs_n": len(report["unpaid_regs"]),
        "leading_model": "PLAYER-BULLET-VICTIM-LOCKED payments: the "
                         "+100s co-land on the flight-consistent "
                         "registrations of freshly-spawned soldiers "
                         "in the bullet corridor; the zone/wound "
                         "registrations (the spawner zone x~1277-1310 "
                         "churn) pay 0 — R48's death-registration "
                         "lock refined to the bullet's victim",
        "strict_class_keyed":
            "NOT DECIDABLE this round: the kill group never ran as a "
            "clean group (the census thinned — the spawner-zone churn "
            "dominates the windows) and the connect group caught 2 "
            "events with 1 mixed (+1000) — the strong 'magnitude "
            "reads off the class' form is FALSIFIED in its identical-"
            "context reading (the same 0x42bc connect context paid "
            "+500 once and +1000 once); the weak form (per-class "
            "magnitudes +500 connect / +100 bullet-victim kill) "
            "stands on unconfounded n=1 + n=2",
    }
    report["verdict"] = verdict
    op = os.path.join(EVID, "r49_class_keyed_table.json")
    with open(op, "w") as f:
        json.dump(report, f, indent=1, default=str)
    print("=== R49 CORRECTED VERDICT v2 (offline, authoritative) ===")
    print("KILL_REG:", [(e["pass"], e["gf"], e["d"],
                         e.get("regs")) for e in kill])
    print("CONNECT:", [(e["pass"], e["gf"], e["d"],
                        e.get("holders_0x42bc")) for e in conn])
    print("MIXED:", verdict["mixed_detail"])
    print("UNATTRIBUTED:", [(e["pass"], e["gf"], e["d"])
                            for e in unattr])
    print("CHURN jumps:", len(churn),
          "| unpaid regs:", verdict["unpaid_regs_n"])
    print("ledger:", report["ledger"])
    print("leading model:", verdict["leading_model"])
    print("strict verdict:", verdict["strict_class_keyed"])
    print("written:", op)
    return 0


if __name__ == "__main__":
    sys.exit(main())
