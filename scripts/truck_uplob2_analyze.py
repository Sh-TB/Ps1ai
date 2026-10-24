#!/usr/bin/env python3
"""Analyze uplob2 raw dumps: diff slot 10 and slot 0 records across
throw boundaries; find any hp-like decrement."""
import json

TRACE = "/home/z/my-project/work/msx_recomp/evidence/issue5_truck/uplob2/trace.jsonl"
events = [json.loads(l) for l in open(TRACE) if l.strip()]
raws = [e for e in events if e["ev"] == "raw"]
print(f"{len(events)} events, {len(raws)} raw dumps")
for e in raws:
    print("  ", e["note"], "presence:", e.get("presence"))

NAMES = {0: "state", 11: "f16", 19: "f26", 20: "f28", 21: "f2A",
         22: "f2C", 51: "f66", 60: "x_lo", 61: "x_hi", 63: "h",
         71: "sx", 73: "sy", 98: "fC4", 117: "fEA", 118: "fEB",
         122: "fF4"}

def diff(r1, r2, slot):
    a = r1["slots"].get(str(slot))
    b = r2["slots"].get(str(slot))
    if a is None or b is None:
        return None
    out = []
    for i in range(len(a)):
        if a[i] != b[i]:
            out.append((i, NAMES.get(i, f"w{i}"), a[i], b[i]))
    return out

pairs = list(zip(raws, raws[1:]))
for r1, r2 in pairs:
    for slot in (0, 10):
        d = diff(r1, r2, slot)
        if d:
            print(f"\n{r1['note']} => {r2['note']}  slot {slot}:")
            for i, nm, va, vb in d:
                print(f"   w{i:3d} {nm:5s} {va:6d} -> {vb:6d}  "
                      f"(hex {va & 0xffff:04x}->{vb & 0xffff:04x})")
