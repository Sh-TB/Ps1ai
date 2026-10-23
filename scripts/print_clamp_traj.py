#!/usr/bin/env python3
"""print_clamp_traj.py — readable trajectory table from a clampdiff
trace.jsonl (window words + extra words merged)."""
import json
import sys

D = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/z/my-project/work/msx_recomp/evidence/clamp_globals/clampdiff2"

rows = []
for line in open(f"{D}/trace.jsonl"):
    r = json.loads(line)
    r["w"].update(r.get("x", {}))
    rows.append(r)

print("frame | player | scroll | EB594 | EB59C | EB5A0 | D4970px "
      "| D4974px | D4A22 | D4938 | D494E | D4958 | EB5D0")
step = max(1, len(rows) // 26)
for i in range(0, len(rows), step):
    r = rows[i]
    g = r["w"].get
    px70 = int(g("D4970")) / 65536.0
    px74 = int(g("D4974")) / 65536.0
    print(f"{r['f']} | {r['px']:7.1f} | "
          f"{int(g('EB598')) / 65536:8.2f} | "
          f"{int(g('EB594')) / 65536:6.2f} | "
          f"{int(g('EB59C')) / 65536:6.2f} | "
          f"{int(g('EB5A0')) / 65536:8.3f} | "
          f"{px70:7.2f} | {px74:7.2f} | "
          f"{int(g('D4A22'))} | {int(g('D4938')):5d} | "
          f"{int(g('D494E')):#x} | {int(g('D4958')):#x} | "
          f"{int(g('EB5D0')):#x}")
