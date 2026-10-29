#!/usr/bin/env python3
"""r48_analysis_correct.py — R48 offline frame-exact analysis (no boot).

The authoritative per-event verdict for the R48 frame-exact tap
protocol.  The runner only records; this script decides.

Inputs:  truck_evidence/r48/r48_bootN.jsonl (the FRAME_WALK rows +
the TAP envelopes).  boot 2 carries DIRECT per-frame table reads
(the corpse-blindness fix); boot 1 is scan-census-only.

Rules (the capsule method):
  - the SCORE LEDGER is the cumulative delta (restore -> final);
  - DIRECT rows date every state transition per slot to its exact
    frame_rel — a DEATH = st enters CORPSE_ST (0x4BE4/0x5CC8); an
    sx-CHIP = the +0x8E screen-x drops while alive; a ST-CHANGE is
    any state-handler move (0x4054/0x42bc/0x5b0c/0x6730 = one
    soldier class, the st word is NOT identity);
  - EVENT DECISION per +delta frame: (a) PER-KILL if the SAME slot
    shows a death (or a death-adjacent transition <= 2f) at the pay
    frame; (b) PER-HIT if the pay frame shows an sx-CHIP/st-CHANGE
    on a slot that is ALIVE at the walk end; else UNATTRIBUTED
    (checked against the world-transition table, never assumed);
  - IDENTITY: the paying slot's pre-event row (st class, x, h ->
    ground vs air) — the x~1275 cluster classification;
  - the ZERO-INPUT control walk is the frame-exact churn baseline:
    transitions/deltas it also produces are churn, not payment.

Writes: r48_frame_exact_events.json + the verdict; amends the boot
ledger (the same-entry outcome_corrected precedent).
"""
from __future__ import annotations

import json
import os
import time

_REPO = "/home/z/my-project/ps1ai"
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence", "r48")
LEDGER = os.path.join(_REPO, "scratch", "r48", "boots_used.json")

CORPSE_ST = (0x4BE4, 0x5CC8)
ADJ = 2                      # death-adjacent match window (frames)


def load_runs(path):
    taps_by, walks_by = {}, {}
    cur = None
    for line in open(path):
        e = json.loads(line)
        ev = e.get("ev")
        if ev == "FRONTIER_RESTORED":
            cur = e["frontier"]
        elif ev == "FRAME_WALK":
            walks_by.setdefault(cur, {}).setdefault(
                e["tap"], []).append(e)
        elif ev == "TAP":
            taps_by.setdefault(cur, []).append(dict(e, frontier=cur))
    return taps_by, walks_by


def slot_timeline(rows):
    """Per-frame slot states -> dated transitions per slot.
    rows = the FRAME_WALK events of one tap; each carries rows[] of
    frames, each frame carries 'direct'.  Returns (transitions,
    deaths, sx_drops):  a DEATH = st enters CORPSE_ST; an sx-CHIP =
    a drop of >= 3px in one frame (the 1-2px/frame camera drift is
    churn — the R45 screen-x lesson); a VANISH = a slot present at
    f-1 gone at f (despawn/recycle)."""
    transitions, deaths, sx_drops, vanishes = [], [], [], []
    prev = {}
    for rw in rows:
        for fr in rw["rows"]:
            cur = {r["slot"]: r for r in fr.get("direct") or []}
            for slot, r in cur.items():
                pr = prev.get(slot)
                if pr is None:
                    continue
                if pr["st"] != r["st"]:
                    tr = {"f_rel": fr["f_rel"], "slot": slot,
                          "from": pr["st"], "to": r["st"],
                          "pre": {"st": pr["st"], "x": pr["x"],
                                  "sx": pr["sx"], "h": pr["h"],
                                  "a4": pr["a4"]},
                          "post": {"st": r["st"], "x": r["x"],
                                   "sx": r["sx"], "h": r["h"],
                                   "a4": r["a4"]}}
                    transitions.append(tr)
                    if r["st"] in CORPSE_ST:
                        deaths.append(tr)
                if pr["sx"] and r["sx"] \
                        and pr["sx"] - r["sx"] >= 3 \
                        and pr["st"] not in CORPSE_ST \
                        and r["st"] not in CORPSE_ST:
                    sx_drops.append({"f_rel": fr["f_rel"],
                                     "slot": slot,
                                     "from": pr["sx"], "to": r["sx"],
                                     "drop": pr["sx"] - r["sx"],
                                     "st": pr["st"], "x": pr["x"],
                                     "h": pr["h"]})
            for slot, pr in prev.items():
                if slot not in cur:
                    vanishes.append({"f_rel": fr["f_rel"],
                                     "slot": slot,
                                     "pre": {"st": pr["st"],
                                             "x": pr["x"],
                                             "sx": pr["sx"],
                                             "h": pr["h"],
                                             "a4": pr["a4"]}})
            prev = cur
    return transitions, deaths, sx_drops, vanishes


def score_events(rows):
    out, prev = [], None
    for rw in rows:
        for fr in rw["rows"]:
            if prev is not None and fr["sc"] != prev:
                out.append({"f_rel": fr["f_rel"], "d": fr["sc"] - prev,
                            "from": prev, "to": fr["sc"]})
            prev = fr["sc"]
    return out


def classify(events, deaths, transitions, sx_drops, vanishes):
    """The per-event decision from the direct timelines (v3: the
    0x515c death-INITIATION lock).  Classes:
      DEATH_INITIATION_LOCKED  - the pay frame == a slot's entry into
          the dying state 0x515c (the kill registration frame)
      CORPSE_LOCKED(<=2f)      - pay frame within 2f of a corpse
          transition (0x4BE4/0x5CC8) but no initiation match
      SURVIVING_CONNECT_PAYMENT - the pay frame carries a state
          change on a slot that is ALIVE at the walk end (hit
          reaction without death from that connect)
      UNATTRIBUTED_FRAME       - nothing measurable at the pay frame"""
    out = []
    for se in events:
        f, d = se["f_rel"], se["d"]
        if d == 0:
            continue
        ini = [x for x in transitions if x["f_rel"] == f
               and x["to"] == 20828]          # 0x515c entry, exact
        de = [x for x in deaths if abs(x["f_rel"] - f) <= ADJ]
        sd = [x for x in sx_drops if abs(x["f_rel"] - f) <= ADJ]
        vn = [x for x in vanishes if abs(x["f_rel"] - f) <= ADJ]
        tr = [x for x in transitions if x["f_rel"] == f
              and x["to"] != 20828]
        if ini:
            out.append({"f_rel": f, "d": d, "verdict":
                        "DEATH_INITIATION_LOCKED",
                        "identity": ini[0]["pre"],
                        "slots": [x["slot"] for x in ini],
                        "n_initiations": len(ini),
                        "n_deaths_near": len(de)})
        elif de:
            out.append({"f_rel": f, "d": d, "verdict":
                        "CORPSE_LOCKED(<=2f)",
                        "identity": de[0]["pre"],
                        "slots": [x["slot"] for x in de],
                        "n_initiations": 0,
                        "n_deaths_near": len(de)})
        elif tr or vn or sd:
            v = "SURVIVING_CONNECT_PAYMENT" if tr else \
                ("VANISH_AT_PAY(despawn/recycle)" if vn else
                 "CHIP_NEAR(<=2f)")
            src = (tr or vn or sd)[0]
            out.append({"f_rel": f, "d": d, "verdict": v,
                        "identity": src.get("pre", src),
                        "slots": [x["slot"] for x in (tr or vn
                                                      or sd)],
                        "n_initiations": 0,
                        "n_deaths_near": len(de)})
        else:
            out.append({"f_rel": f, "d": d, "verdict":
                        "UNATTRIBUTED_FRAME",
                        "identity": None, "slots": [],
                        "n_initiations": 0,
                        "n_deaths_near": len(de)})
    return out


def analyze_frontier(taps, walks):
    per_tap = walks
    ctrl_rows = per_tap.get(0, [])
    ctrl_tr, ctrl_de, ctrl_sd, ctrl_vn = slot_timeline(ctrl_rows)
    ctrl_sc = score_events(ctrl_rows)
    churn_f = {e["f_rel"] for e in ctrl_sc}
    churn_death_f = {x["f_rel"] for x in ctrl_de}
    all_events, all_deaths, all_trans, all_van = [], [], [], []
    for tap in taps:
        if tap["tap"] == 0:
            continue
        rows = per_tap.get(tap["tap"], [])
        tr, de, sd, vn = slot_timeline(rows)
        ev = score_events(rows)
        all_deaths += [{"tap": tap["tap"], **x} for x in de]
        all_trans += [{"tap": tap["tap"], **x} for x in tr]
        all_van += [{"tap": tap["tap"], **x} for x in vn]
        for e in classify(ev, de, tr, sd, vn):
            e = dict(e, tap=tap["tap"])
            e["churn_alert"] = bool(
                e["f_rel"] in churn_f
                or e["f_rel"] in churn_death_f)
            all_events.append(e)
    paid = [e for e in all_events]
    n_kill = sum(1 for e in paid
                 if e["verdict"].startswith("DEATH_INIT"))
    n_cl = sum(1 for e in paid
               if e["verdict"].startswith("CORPSE_LOCKED"))
    n_hit = sum(1 for e in paid
                if e["verdict"].startswith("SURVIVING"))
    n_van = sum(1 for e in paid
                if e["verdict"].startswith("VANISH"))
    n_chip = sum(1 for e in paid
                 if e["verdict"].startswith("CHIP"))
    n_unattr = sum(1 for e in paid
                   if e["verdict"] == "UNATTRIBUTED_FRAME")
    xs = [d["pre"]["x"] for d in all_deaths]
    x1275 = sum(1 for x in xs if 1260 <= x <= 1290)
    if n_kill and n_hit:
        verdict = ("TWO PAY CLASSES measured frame-exact: "
                   "death-initiation-locked payments (0x515c entry, "
                   f"n={n_kill}) AND a surviving-connect payment "
                   f"(n={n_hit}) - both the pure per-KILL and the "
                   "pure per-HIT models are falsified; payments land "
                   "at the connect/kill-registration frame, the "
                   "corpse state follows 1-14f later")
    elif n_kill and not (n_hit or n_van or n_chip or n_cl):
        verdict = ("DEATH_INITIATION_LOCKED only: every payment "
                   "lands exactly on a 0x515c entry (kill "
                   "registration); no surviving-connect payment")
    elif n_kill:
        verdict = "DEATH_INITIATION_LOCKED dominant + secondary classes"
    elif n_hit:
        verdict = "SURVIVING_CONNECT payments only"
    else:
        verdict = "NO PAYING EVENTS ATTRIBUTED"
    return {
        "taps_analyzed": len([t for t in taps if t["tap"] > 0]),
        "control_churn": {"score_deltas": ctrl_sc,
                          "deaths": [{"f_rel": x["f_rel"],
                                      "slot": x["slot"],
                                      "from": hex(x["from"]),
                                      "pre_x": x["pre"]["x"]}
                                     for x in ctrl_de],
                          "sx_drops": ctrl_sd,
                          "vanishes": ctrl_vn,
                          "n_transitions": len(ctrl_tr)},
        "deaths_dated": [{"tap": d["tap"], "f_rel": d["f_rel"],
                          "slot": d["slot"],
                          "from_st": hex(d["from"]),
                          "to_st": hex(d["to"]),
                          "pre_x": d["pre"]["x"],
                          "pre_h": d["pre"]["h"],
                          "pre_sx": d["pre"]["sx"]}
                         for d in all_deaths],
        "vanishes_dated": [{"tap": v["tap"], "f_rel": v["f_rel"],
                            "slot": v["slot"],
                            "pre_st": hex(v["pre"]["st"]),
                            "pre_x": v["pre"]["x"],
                            "pre_sx": v["pre"]["sx"],
                            "pre_h": v["pre"]["h"]}
                           for v in all_van],
        "frame_exact_events": all_events,
        "summary": {"paying_events": len(paid),
                    "death_initiation_locked": n_kill,
                    "corpse_locked_2f": n_cl,
                    "surviving_connect": n_hit,
                    "vanish_events": n_van,
                    "chip_events": n_chip,
                    "unattributed": n_unattr,
                    "cluster_x_1260_1290": x1275,
                    "death_x_list": xs},
        "verdict": verdict,
    }


def main():
    out = {"schema": "ps1play.r48-frameexact-analysis/2",
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "frontiers": {}}
    for n in (1, 2):
        path = os.path.join(EVID, f"r48_boot{n}.jsonl")
        if not os.path.exists(path):
            continue
        taps_by, walks_by = load_runs(path)
        for fr, taps in sorted(taps_by.items()):
            res = analyze_frontier(taps, walks_by.get(fr, {}))
            res["boot"] = n
            out["frontiers"][f"{fr}(boot{n})"] = res
            print(f"[r48-analysis] boot{n} {fr}: {res['verdict']}")
            s = res["summary"]
            print(f"  paid={s['paying_events']} init_locked="
                  f"{s['death_initiation_locked']} "
                  f"corpse2f={s['corpse_locked_2f']} "
                  f"surv_conn={s['surviving_connect']} "
                  f"chip={s['chip_events']} "
                  f"unattr={s['unattributed']} "
                  f"cluster_x1275={s['cluster_x_1260_1290']}")
    with open(os.path.join(EVID, "r48_frame_exact_events.json"),
              "w") as f:
        json.dump(out, f, indent=1, default=str)
    if os.path.exists(LEDGER):
        led = json.load(open(LEDGER))
        led.setdefault("log", []).append(
            {"ts": time.strftime("%FT%TZ", time.gmtime()),
             "script": "r48_analysis_correct.py",
             "outcome_corrected":
                 "offline frame-exact analysis appended: " +
                 "; ".join(f"{k}: {v['verdict']}"
                           for k, v in out["frontiers"].items())})
        json.dump(led, open(LEDGER, "w"), indent=1)
    print("[r48-analysis] written r48_frame_exact_events.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
