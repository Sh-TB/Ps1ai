#!/usr/bin/env python3
"""r71_capsule_compact.py — the R71 final-mile fix: bring the shipped
msx capsule back under the 64 KiB shipped-validation bound
(test_shipped_capsules_validate_and_size: size < 64*1024) WITHOUT
losing a single fact (the r66 precedent).

The compaction entries live in scripts/r71_compact_entries.json
(keyed by the exact first-10-chars prefix of each event's what text).
The compact discipline: the facts stay; the prose shrinks; the
statuses NEVER change (the honest-registry law).  The full narratives
already live in reports/, the worklog, the round reports on the
issues and git history.
"""
import json
import sys

sys.path.insert(0, ".")
from ps1play.knowledge.capsule import Capsule  # noqa: E402

P = "data/knowledge/msx/capsule.json"
ENTRIES = json.load(open("scripts/r71_compact_entries.json"))


def main():
    with open(P) as f:
        raw = json.load(f)
    evs = raw["events"]
    changed = 0
    before = len(open(P, "rb").read())
    for e in evs:
        w = e.get("what", "")
        key = w[:10]
        if key in ENTRIES and ENTRIES[key] != w:
            e["what"] = ENTRIES[key]
            changed += 1
    with open(P, "w") as f:
        json.dump(raw, f, indent=1, ensure_ascii=False)
    size = len(open(P, "rb").read())
    print(f"compacted {changed} events: {before} -> {size} B "
          f"(bound 65536)")
    cap = Capsule(raw)
    cap.validate()
    print("capsule validate: OK, size =", cap.size_bytes())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
