#!/usr/bin/env python3
"""emit_overlay_summary.py — produce the COMMITTED summary registry
data/games/SLUS-01212/overlay_index.json from the workspace full index.

Metadata only: identities, mappings, counts, function table (addresses/
sizes/confidence), strings. Edges/grefs stay in the workspace index
(queryable via gkb_query --overlay-refs / --overlay-function-at when the
workspace is present; the committed copy answers mapping + functions).
"""
import json
import os

WS = "/home/z/my-project/work/msx_recomp/index/overlay_index.json"
OUT = ("/home/z/my-project/ps1ai/data/games/SLUS-01212/"
       "overlay_index.json")

full = json.load(open(WS))
summary = {
    "schema": "ps1play-overlay-index/1",
    "config_version": full["config_version"],
    "generated_utc": full["generated_utc"],
    "exe_text": full["exe_text"],
    "note": ("mapping evidence + module-tagged function table; full "
             "edges/grefs live in the external workspace index "
             "(re_index.sqlite + overlay_index.json); metadata only — "
             "no game bytes"),
    "modules": {},
}
for name, m in full["modules"].items():
    if m.get("status") != "INDEXED":
        summary["modules"][name] = {"status": m.get("status")}
        continue
    summary["modules"][name] = {
        "status": "INDEXED",
        "file": m["file"],
        "code_region_file_off": m["code_region_file_off"],
        "code_off_source": m["code_off_source"],
        "code_bytes": m["code_bytes"],
        "mapping": m["mapping"],
        "counts": m["counts"],
        "functions": [{"va": f["va"], "size": f["size"],
                       "name": f["name"], "confidence": f["confidence"]}
                      for f in m["functions"]],
        "strings": m["strings"],
    }
os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    json.dump(summary, f, indent=1)
print(f"wrote {OUT} ({os.path.getsize(OUT)} bytes)")
for name, m in summary["modules"].items():
    print(name, m.get("status"), m.get("counts", ""))
