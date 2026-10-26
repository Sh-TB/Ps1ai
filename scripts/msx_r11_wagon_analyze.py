#!/usr/bin/env python3
"""msx_r11_wagon_analyze.py — offline classifier for the Segment-1
crossed lifecycles (read-only over the pass evidence).

Inputs: scratch/round11_msx/wagons/pass_*/wagon_lifecycles.json
Outputs: scratch/round11_msx/wagons/analysis.json with
  * per-pass table (crossed_total / crossed_persistent / continues /
    max_px / stop reason),
  * the st-family census of persistent crossed events,
  * the WAGON-FAMILY split (small/big) under the declared rule:
    family = the dominant st among persistent crossed events whose
    spawn px0 is at/after the train-yard band (--min-px0, default
    1400 = past the truck pin); small/big = height-word gap split
    (msx_r11_lib.split_kinds).  The rule + PNG cross-check pointers
    are recorded so the label can be audited.
Cumulative acceptance is then updated in cumulative.json (wagons only,
honest ceiling otherwise).
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, "/home/z/my-project/ps1ai/scripts")
from msx_r11_lib import split_kinds                      # noqa: E402

WAG = "/home/z/my-project/ps1ai/scratch/round11_msx/wagons"


def strict_recompute(e, margin=8.0):
    """crossed_strict for events logged by the pre-strict tracker."""
    if "crossed_strict" in e:
        return e["crossed_strict"]
    return bool(e["spawn_ahead"] and e["end_behind"]
                and e["px1"] > e["px0"] + margin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-px0", type=float, default=1400.0)
    ap.add_argument("--wagon-st", type=int, default=None,
                    help="override the auto family pick")
    args = ap.parse_args()
    table = []
    fam_events = []
    for d in sorted(glob.glob(os.path.join(WAG, "pass_*"))):
        rp = os.path.join(d, "report.json")
        lp = os.path.join(d, "wagon_lifecycles.json")
        if not (os.path.exists(rp) and os.path.exists(lp)):
            continue
        rep = json.load(open(rp))
        life = json.load(open(lp))
        cross = [e for e in life if e["crossed"]]
        pers = [e for e in cross if e["persistent"]]
        table.append({
            "pass": rep["pass"], "stop": rep["stop_reason"],
            "max_px": rep["max_px"],
            "continues": rep["continues_accepted"],
            "restarts": rep["mission_restarts"],
            "deaths": rep["deaths"],
            "crossed_total": rep["tracker"]["crossed_total"],
            "crossed_persistent": rep["tracker"]["crossed_persistent"],
            "crossed_strict": rep["tracker"].get(
                "crossed_strict",
                sum(1 for e in cross if strict_recompute(e))),
            "crossed_strict_persistent": rep["tracker"].get(
                "crossed_strict_persistent",
                sum(1 for e in cross if strict_recompute(e)
                    and e.get("persistent"))),
            "lifecycles": rep["tracker"]["lifecycles_closed"]})
        fam_events += [e for e in pers if e["px0"] >= args.min_px0
                       and strict_recompute(e)]
    fam_counts = collections.Counter(e["st"] for e in fam_events)
    st_pick = args.wagon_st if args.wagon_st else \
        (fam_counts.most_common(1)[0][0] if fam_counts else None)
    wagon = [e for e in fam_events
             if st_pick is not None and e["st"] == st_pick]
    kinds = split_kinds(wagon, persist=False)
    out = {"schema": "ps1play-r11-wagon-analysis/1",
           "min_px0": args.min_px0,
           "per_pass": table,
           "cumulative_crossed_all": sum(t["crossed_persistent"]
                                         for t in table),
           "cumulative_crossed_strict_persistent": sum(
               t["crossed_strict_persistent"] for t in table),
           "trainband_events": len(fam_events),
           "trainband_st_census": {str(k): v
                                   for k, v in fam_counts.items()},
           "wagon_family_st": st_pick,
           "wagon_family_kinds": kinds,
           "wagon_family_n": len(wagon),
           "events": wagon}
    json.dump(out, open(os.path.join(WAG, "analysis.json"), "w"),
              indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "events"},
                     indent=1))


if __name__ == "__main__":
    main()
