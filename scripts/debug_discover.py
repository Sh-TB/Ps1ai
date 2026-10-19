#!/usr/bin/env python3
"""Scientific discovery: restore the SAME savestate, A/B probes become
perfectly comparable. Verify top candidates with value-series sampling."""
import json
import sys
sys.path.insert(0, "/home/z/my-project")
from ps1play.api import PS1Play  # noqa: E402

GAME = "/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue"
p = PS1Play(GAME)
print("boot:", p.boot())
print("enter:", p.enter_gameplay(max_taps=10))
p.save_state("dbg")
mem = p.mem

cr = p.disc.correlate("RIGHT", window=45, reps=2)
p.load_state("dbg")
cl = p.disc.correlate("LEFT", window=45, reps=2)

idx = {(c["addr"], c["dtype"]): c for c in cr}
cross = []
for c in cl:
    m = idx.get((c["addr"], c["dtype"]))
    if m and m["dir"] != c["dir"]:
        cross.append({"addr": m["addr"], "dtype": m["dtype"],
                      "dR": m["deltas"], "dL": c["deltas"],
                      "score": min(m["score"], c["score"])})
cross.sort(key=lambda x: -x["score"])
print("\n== BIDIRECTIONAL CANDIDATES (same-address RIGHT+/LEFT-) ==")
for c in cross[:10]:
    print(c)

print("\n== VALUE SERIES (restore -> hold 60f, sample every 10f) ==")
for c in cross[:6]:
    a, dt = c["addr"], c["dtype"]
    read = mem.u32 if dt == "u32" else mem.u16
    out = {}
    for btn in ("RIGHT", "LEFT"):
        p.load_state("dbg")
        series = [read(a)]
        for k in range(6):
            p.core.run(10, {btn})
            series.append(read(a))
        out[btn] = series
    print(f"addr={a} {dt}: R={out['RIGHT']}  L={out['LEFT']}")
p.core.shutdown()
