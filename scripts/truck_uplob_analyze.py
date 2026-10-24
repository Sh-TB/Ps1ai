#!/usr/bin/env python3
"""Analyze uplob1 trace: truck presence, score events, slot diffs across
throws, and the death timeline."""
import json

TRACE = "/home/z/my-project/work/msx_recomp/evidence/issue5_truck/uplob1/trace.jsonl"
events = [json.loads(l) for l in open(TRACE) if l.strip()]
print(f"{len(events)} events")
by = {}
for e in events:
    by.setdefault(e["ev"], []).append(e)

print("\n== key events ==")
for k in ("ckpt_loaded", "truck_first_sight", "engage_state_saved",
          "arm_start", "point_blank", "arm_end", "died_during_advance"):
    for e in by.get(k, [])[:6]:
        print(k, json.dumps(e)[:260])

print("\n== score trajectory (arm-tagged) ==")
last_score = 0
for e in events:
    if "score" in e and e.get("score") != last_score:
        d = e["score"] - last_score
        last_score = e["score"]
        truck = e.get("truck")
        print(f"{e['ev']:12s} arm={e.get('arm','-')} score={e['score']} "
              f"(+{d}) truck={json.dumps(truck)[:80] if truck else None} "
              f"px={e.get('px')} php={e.get('php')} gren={e.get('gren')}")

print("\n== slot dumps: truck-slot diffs across arms ==")
dumps = [e for e in events if e["ev"] == "slots"]
print(f"{len(dumps)} dumps")

def slotmap(d):
    return {s["slot"]: s for s in d["slots"]}

# find the truck slot from point_blank dumps
for d in dumps:
    if "point_blank" in d.get("note", ""):
        sm = slotmap(d)
        cands = [s for s in sm.values()
                 if 200 <= s.get("hp_screenx", 0) <= 300
                 and s.get("h") == 64]
        print(d["note"], "-> candidates:",
              [(s["slot"], s["x_px"], s["hp_screenx"], s["h"]) for s in cands])

# diff consecutive dumps per slot for the three arms
def diff(d1, d2):
    m1, m2 = slotmap(d1), slotmap(d2)
    out = []
    for s in sorted(set(m1) | set(m2)):
        a, b = m1.get(s), m2.get(s)
        if a and b:
            ch = {k: (a[k], b[k]) for k in a if k != "slot"
                  and a.get(k) != b.get(k)}
            if ch:
                out.append((s, ch))
        elif a or b:
            out.append((s, "presence_change",
                        bool(a), bool(b)))
    return out

pairs = []
prev = None
for d in dumps:
    if prev is not None:
        pairs.append((prev, d))
    prev = d
print("\n== dump-pair diffs (slot: changed fields) ==")
for d1, d2 in pairs:
    dd = diff(d1, d2)
    if dd:
        print(f"\n-- {d1['note']}  ==>  {d2['note']}")
        for s, ch in dd[:8]:
            print("   slot", s, json.dumps(ch)[:300])
