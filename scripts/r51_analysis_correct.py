#!/usr/bin/env python3
"""r51_analysis_correct.py — R51 offline CORRECTED analysis (no boot).

The authoritative readout for the wound-accumulator hunt.  Built on
the R49/R50 v2 global-frame per-slot matcher (ALL slots' transitions
re-based onto one frame line — the R49 v1 blindness lesson), plus:
  1. THE WOUND-WORD HUNT: for every payment, the paying tap's union-
     net (0x60..0xE0 even) word deltas of ALL live slots — the
     non-zero-delta words are the accumulator candidates; the
     candidates INTERSECTED across the two +1000 connects; the
     bounded-net subset (0x88..0xA8) cross-joined against the R50
     +500/+1000 events (R50 read only the bounded net — the join
     works there and only there);
  2. THE PIERCE VERDICT: the PIERCE taps (transparent 0xab94 target)
     — did the transparent target react, did the BEHIND mortal pay;
  3. THE INVULNERABILITY CENSUS: every 0xab94/0xae7c dwell recorded;
  4. THE CONTROLS: zero-input AND movement-only windows pay 0.
"""
from __future__ import annotations

import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence")
CONNECT_ST = 0x42BC
REG_ST = 0x515C
CORPSE_ST = 0x4BE4
AE7C_ST = 0xAE7C
INVUL_ST = 0xAB94
LAG_LO, LAG_HI = -2, 6
BOUNDED = {f"0x{o:02X}".replace("0x0", "0x").lower()
           for o in range(0x88, 0xAA, 2)}
BOUNDED = {f"0x{o:x}" for o in range(0x88, 0xAA, 2)}


def load(path):
    taps = []
    with open(path) as f:
        for line in f:
            ev = json.loads(line)
            if ev.get("ev") == "TAP":
                taps.append(ev)
    return taps


def build_pass(taps, fr):
    seq, tap_meta = [], []
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
            hist.setdefault(d["slot"], []).append((gf, d["st"], d["x"]))

    def transitions(slot, st_to):
        out = []
        h = hist.get(slot, [])
        for i in range(1, len(h)):
            if h[i][1] == st_to and h[i - 1][1] != st_to:
                out.append({"gf": h[i][0], "x": h[i][2],
                            "from": h[i - 1][1]})
        return out

    return seq, tap_meta, hist, transitions


def payments(seq, hist, transitions, fr):
    pays = []
    for i in range(1, len(seq)):
        a, b = seq[i - 1], seq[i]
        d = b["sc"] - a["sc"]
        if d == 0:
            continue
        ev = {"pass": fr[-1], "gf": i, "d": d, "sc": b["sc"],
              "tap": b["tap"], "intent": b["intent"]}
        if "CONTROL" in b["intent"]:
            ev["class"] = "CONTROL_PAID"
            pays.append(ev)
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
        holders_inv = [s for s, h in hist.items()
                       if any(g == i and st in (INVUL_ST, AE7C_ST)
                              for g, st, _x in h)]
        ev["regs"] = regs
        ev["holders_0x42bc"] = holders42
        ev["holders_invul"] = holders_inv
        if regs and d == 100:
            ev["class"] = "KILL_REG"
        elif holders42 and not regs:
            ev["class"] = "CONNECT_0x42bc"
        elif holders_inv and not regs:
            ev["class"] = "INVUL_CONTEXT"
        else:
            ev["class"] = "UNATTRIBUTED"
        pays.append(ev)
    return pays


def main():
    path = os.path.join(EVID, "r51", "r51_boot3.jsonl")
    r50_path = os.path.join(EVID, "r50", "r50_boot2.jsonl")
    taps = load(path)
    report = {"schema": "ps1play.r51-analysis/1", "input": path,
              "generated": time.strftime("%FT%TZ", time.gmtime()),
              "payments": [], "pierce_events": [], "invul_census": [],
              "wound_candidates": {}, "r50_join": {}, "ledger": {}}
    tap_by_num = {}
    for t in taps:
        tap_by_num[(t["frontier"], t["tap"])] = t
    for fr in ("r47_frontier_a", "r47_frontier_b"):
        seq, tap_meta, hist, transitions = build_pass(taps, fr)
        pays = payments(seq, hist, transitions, fr)
        report["payments"] += pays
        report["ledger"][fr] = {
            "score_start": seq[0]["sc"], "score_end": seq[-1]["sc"],
            "delta": seq[-1]["sc"] - seq[0]["sc"]}
        # ---- the pierce events ------------------------------------
        for t, base in tap_meta:
            if t.get("intent") != "PIERCE":
                continue
            trans = t.get("target_st_transitions", [])
            report["pierce_events"].append({
                "pass": fr[-1], "tap": t["tap"],
                "transparent_slot": t["target"]["slot"],
                "dscore": t["score_delta"],
                "transparent_reacted": any(
                    x["to"] == CONNECT_ST for x in trans),
                "transparent_registered": any(
                    x["to"] == REG_ST for x in trans),
                "corpses_in_window": t["corpses"],
                "regs_lag_window": [
                    p for p in pays
                    if p["tap"] == t["tap"] and p.get("regs")]})
        # ---- the invul census (dwell from the direct tables) -------
        for s, h in sorted(hist.items()):
            frames_inv = [g for g, st, _x in h
                          if st in (INVUL_ST, AE7C_ST)]
            if frames_inv:
                report["invul_census"].append({
                    "pass": fr[-1], "slot": s,
                    "n_invul_frames": len(frames_inv),
                    "st_seen": sorted({hex(st)
                                       for _g, st, _x in h
                                       if st in (INVUL_ST, AE7C_ST)}),
                    "registrations": transitions(s, REG_ST),
                    "corpses": transitions(s, CORPSE_ST)})
    # ---- THE WOUND-WORD HUNT ---------------------------------------
    cand = None
    plus1000_events = []
    for p in report["payments"]:
        if p["class"] not in ("CONNECT_0x42bc", "UNATTRIBUTED",
                              "INVUL_CONTEXT"):
            continue
        t = tap_by_num.get((("r47_frontier_" + p["pass"]), p["tap"]))
        if t is None or p["d"] <= 0:
            continue
        wd = t.get("word_deltas", {})
        nz = {}
        for slot, words in wd.items():
            for off, dv in words.items():
                if dv:
                    nz.setdefault(slot, {})[off] = dv
        if p["d"] == 1000:
            plus1000_events.append({"pass": p["pass"], "tap": p["tap"],
                                    "class": p["class"],
                                    "nonzero_deltas": nz})
            keys = {(s, o) for s, w in nz.items() for o in w}
            cand = keys if cand is None else (cand & keys)
    report["wound_candidates"] = {
        "plus1000_events": plus1000_events,
        "intersected_candidates": [
            {"slot": s, "off": o} for s, o in sorted(cand or set())],
    }
    # ---- the R50 cross-round join (bounded net only) ----------------
    if os.path.exists(r50_path) and cand:
        r50_taps = load(r50_path)
        r50_bounded = []
        for t in r50_taps:
            d = t.get("score_delta", 0)
            if d not in (500, 1000) or t.get("intent") != "CONNECT":
                continue
            wd = t.get("word_deltas", {})
            nz = {(s, o): dv for s, words in wd.items()
                  for o, dv in words.items()
                  if dv and o.lower() in BOUNDED}
            r50_bounded.append({"pass": t["frontier"][-1],
                                "tap": t["tap"], "d": d,
                                "nonzero_bounded": {
                                    f"{s}:{o}": dv
                                    for (s, o), dv in nz.items()}})
        cand_b = {f"{s}:{o}" for s, o in cand
                  if o.lower() in BOUNDED}
        disc = []
        for e in r50_bounded:
            hit = sorted(cand_b & set(e["nonzero_bounded"]))
            disc.append({"pass": e["pass"], "tap": e["tap"],
                         "d": e["d"], "candidate_words_present": hit})
        report["r50_join"] = {
            "r50_connect_events_bounded": r50_bounded,
            "r51_candidates_in_bounded": sorted(cand_b),
            "per_event_presence": disc,
            "note": "R50 read ONLY the bounded net; the new-net "
                    "candidates cannot join across rounds - a "
                    "dedicated +500 connect with the union net is "
                    "the R52 lever"}
    # ---- verdict -----------------------------------------------------
    pays = report["payments"]
    ctrl_paid = [p for p in pays if p["class"] == "CONTROL_PAID"]
    conn1000 = [p for p in pays if p["d"] == 1000
                and "CONTROL" not in p["intent"]]
    pierce = report["pierce_events"]
    verdict = {
        "controls_all_zero": len(ctrl_paid) == 0,
        "n_connect_1000_this_round": len(conn1000),
        "pierce_replicated": (
            len([e for e in pierce if e["dscore"] == 100
                 and not e["transparent_reacted"]]) >= 2),
        "pierce_events": pierce,
        "invul_census_n": len(report["invul_census"]),
        "wound_candidates_intersected": [
            f"{s}:{o}" for s, o in sorted(cand or set())],
        "ledger": report["ledger"],
    }
    report["verdict"] = verdict
    op = os.path.join(EVID, "r51", "r51_wound_table.json")
    with open(op, "w") as f:
        json.dump(report, f, indent=1, default=str)
    print("=== R51 CORRECTED VERDICT (offline, authoritative) ===")
    print("ledger:", report["ledger"])
    print("controls paid:", len(ctrl_paid))
    print("+1000 events:", [(p["pass"], p["tap"], p["intent"],
                             p["class"]) for p in conn1000])
    for e in plus1000_events:
        print(f"  +1000 pass {e['pass']} tap {e['tap']} "
              f"nonzero slots/words:",
              {s: list(w) for s, w in e["nonzero_deltas"].items()})
    print("intersected wound candidates:",
          verdict["wound_candidates_intersected"])
    print("PIERCE:", [(e["pass"], e["tap"], e["dscore"],
                       e["transparent_reacted"]) for e in pierce],
          "| replicated:", verdict["pierce_replicated"])
    print("invul census entries:", verdict["invul_census_n"])
    print("r50 join:", json.dumps(report.get("r50_join", {})
                                  .get("per_event_presence", []),
                                  default=str)[:400])
    print("written:", op)
    return 0


if __name__ == "__main__":
    sys.exit(main())
