#!/usr/bin/env python3
"""r38t3_salvage.py — rebuild the aa-trial report from the JSONL
written before the r38t3 report-writer crash (no extra boot: the runs
themselves completed; only the summary write failed)."""
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
SCRATCH = os.path.join(_REPO, "scratch", "r38")
COMMIT_EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                           "truck_evidence", "r38")


def main():
    runs = []
    cur = None
    buf = None
    for line in open(os.path.join(SCRATCH, "aa_trials.jsonl")):
        e = json.loads(line)
        ev = e.get("ev")
        if ev == "start":
            if buf:
                runs.append(buf)
            cur = e["tag"]
            buf = {"tag": cur, "score_events": [], "truck_trace": [],
                   "sec_transitions": [], "terminal": None,
                   "modes": {}, "pol_stats": None, "start": {
                       k: e[k] for k in ("px", "score", "gren", "sec")}}
        elif buf is None:
            continue
        elif ev == "chunk":
            buf.setdefault("timeline", []).append(
                {k: e[k] for k in ("c", "px", "score", "gren", "sec",
                                   "mode") if k in e})
            for x in (e.get("census") or []):
                if x["st"] in (0xAA94, 0xABDC):
                    buf["truck_trace"].append(
                        {"c": e["c"], "chopper_a4": x["a4"],
                         "x": x["x"], "h": x["h"]})
        elif ev == "SCORE_EVENT":
            buf["score_events"].append((e["chunk"], e["from"],
                                        e["to"]))
        elif ev == "sec_transition":
            buf["sec_transitions"].append(
                {"c": e["chunk"], "from": e["from"], "to": e["to"],
                 "px": e.get("px"), "score": e.get("score")})
        elif ev in ("MISSION_BANNER", "MISSION_END_LATCHED",
                    "RESTART_SEEN"):
            buf["terminal"] = {"ev": ev, "chunk": e.get("chunk"),
                               "sec": e.get("sec"), "px": e.get("px")}
        elif ev == "RUN_DONE":
            buf.update({k: e.get(k) for k in
                        ("outcome", "end_chunk", "deaths",
                         "score_final", "truck_a4_min", "wall_s",
                         "pol_stats")})
            buf["pol_stats"] = e.get("pol_stats")
    if buf:
        runs.append(buf)

    base = json.load(open(os.path.join(SCRATCH, "trial_report.json")))
    baseA = [{"tag": r["tag"], "outcome": r["outcome"],
              "end_chunk": r["end_chunk"],
              "score_final": r["score_final"], "deaths": r["deaths"]}
             for r in base["runs"] if r["arm"] == "policy"]
    for r in runs:
        r.pop("timeline", None)
        ch = r.pop("truck_trace", None)
        r["chopper_trace_tail"] = (ch or [])[-6:]
        r["chopper_a4_min"] = min((x["chopper_a4"] for x in ch),
                                  default=None) if ch else None
    rep = {"schema": "ps1play.r38-aa-trial/1",
           "generated": time.strftime("%FT%TZ", time.gmtime()),
           "commit_head": os.popen(
               "git -C %s rev-parse HEAD" % _REPO).read().strip(),
           "checkpoint": "r38_ckpt",
           "policy_change": "aa_kill mode (J1 hop+UP-lob recipe) in "
                            "ps1play/agent/combat.py",
           "salvage_note": "runs completed; summary rebuilt from "
                           "aa_trials.jsonl after a report-writer "
                           "crash (no extra boot)",
           "baseline": baseA,
           "treatment": runs,
           "oracle": "score events + walker 0xC / pre-banner (0,8)->"
                     "(0xC,9) + banner PNG; +0x8E excluded (R38 rule)"}
    with open(os.path.join(SCRATCH, "aa_trial_report.json"), "w") as f:
        json.dump(rep, f, indent=1)
    with open(os.path.join(COMMIT_EVID, "r38_aa_trial_report.json"),
              "w") as f:
        json.dump(rep, f, indent=1)
    print(json.dumps({"runs": [
        {"tag": r["tag"], "outcome": r.get("outcome"),
         "end_chunk": r.get("end_chunk"), "deaths": r.get("deaths"),
         "score_final": r.get("score_final"),
         "chopper_a4_min": r.get("chopper_a4_min"),
         "terminal": r.get("terminal")} for r in runs]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
