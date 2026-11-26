#!/usr/bin/env python3
"""r73_analysis.py — R73 offline lever: THE STREAM-CALIBRATED THROW
SCHEDULE (the R72 next_experiment, half 1; zero boots).

Mines every committed product-boot JSONL (r69b volley, r70 phase
probe, r71 chip probe boots 2-3, r72 hybrid boot 1) and emits THE
CALIBRATION TABLE: for every grenade throw — the stream, the grid
window k (the land vs freeze + 178 + 164k), the signed land offset,
the outcome (CONNECT / CHIP / MISS), and the grenade counter at the
throw.  Answers exactly the two R73 schedule questions:

  Q1 (the ownership law): do the on-grid outcomes split by STREAM
      (idle-hold owns k=2, the volley owns k=0/k=1) or by the signed
      SIDE (the -2f side 0/2 vs the -1f/+0f side 4/4)?
  Q2 (the grenade budget): what did each boot SPEND on the closed
      windows and what was left at the later windows (k=3, land
      freeze + 670) — would a skip-closed-windows schedule have had
      ammunition there?

Boot segmentation: the older probes concatenated boots in one JSONL
(the frame counter resets); every segment gets its own freeze anchor
(the first 0x9E88 sighting in its per-frame table, or a FREEZE event).

Output: stdout tables + data/games/SLUS-01212/truck_evidence/r73/
r73_calibration.json (committed evidence).
"""
from __future__ import annotations

import json
import os
import sys

_REPO = "/home/z/my-project/ps1ai"
EVID = os.path.join(_REPO, "data", "games", "SLUS-01212",
                    "truck_evidence")
OUT = os.path.join(EVID, "r73", "r73_calibration.json")

PERIOD = 164.0
BASE = 178.0
FLIGHT = 30.0

# stream per SOURCE FILE (the committed round evidence; the r71 file
# names are the probe script's outputs: chip_probe.jsonl = BOOT 3 =
# the falsification arm TRUCK_CHIP_FIRE=False = the idle-hold stream;
# chip_probe_boot2.jsonl = BOOT 2 = the chip-fire armed stream)
SOURCES = [
    ("r69b", "volley_gre40", os.path.join(EVID, "r69",
                                          "r69b_connect_probe.jsonl")),
    ("r70", "v1.8.x_walk_hold", os.path.join(EVID, "r70",
                                             "r70_phase_probe.jsonl")),
    ("r71b3", "idle_hold", os.path.join(EVID, "r71",
                                        "r71_chip_probe.jsonl")),
    ("r71b2", "chipfire", os.path.join(EVID, "r71",
                                       "r71_chip_probe_boot2.jsonl")),
    ("r72b1", "idle_hold_hybrid", os.path.join(
        EVID, "r72", "r72_hybrid_probe_boot1.jsonl")),
]

THROW_RULES = ("truck_lead_throw", "truck_width_probe",
               "truck_connect_grenade")

# The old-vintage probes (r69b) predate the live A4_TRANSITION
# telemetry; their connect frames are the COMMITTED R69 round
# analysis (reports + the issue-#9 report): the two confirmed
# volley connects f989/f1153 from freeze 811.  Applied only when a
# source logs zero A4 events; provenance disclosed per throw.
KNOWN_CONNECTS = {"r69b": [989, 1153]}


def score_transitions(seg):
    """PAY(+100) events from the score deltas (old-vintage fallback;
    the +100 class cannot distinguish CONNECT from CHIP — the cls is
    honestly 'PAY' unless the frame is a known connect)."""
    out, prev = [], None
    for r in seg:
        f, s = r.get("f"), r.get("score")
        if f is None or s is None:
            continue
        if prev is not None and s - prev[1] == 100:
            out.append({"f": f, "from": None, "to": None,
                        "cls": "PAY"})
        prev = (f, s)
    return out


def load(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:                       # noqa: PERF203
                pass
    return rows


def segment(rows):
    """Split one JSONL into boot segments (the frame counter resets)."""
    segs, cur, prev_f = [], [], None
    for r in rows:
        f = r.get("f")
        if f is None:
            if cur:
                cur.append(r)
            continue
        if prev_f is not None and f < prev_f - 2:
            segs.append(cur)
            cur = []
        cur.append(r)
        prev_f = f
    if cur:
        segs.append(cur)
    return segs


def freeze_of(seg):
    for r in seg:
        if r.get("ev") == "FREEZE":
            return r["f"]
    # derive: the first per-frame row whose table holds a live 0x9e88
    for r in seg:
        for e in r.get("table") or []:
            if e.get("st") == "0x9e88":
                return r["f"]
    return None


def a4_transitions(seg):
    out = []
    for r in seg:
        if r.get("ev") == "A4_TRANSITION":
            d = int(r["to"]) - int(r["from"])
            cls = r.get("cls") or ("CONNECT" if d == -100 else
                                   "CHIP" if d == -10 else "OTHER")
            out.append({"f": r["f"], "from": int(r["from"]),
                        "to": int(r["to"]), "cls": cls})
    return out


def throws_of(seg, freeze):
    out = []
    for r in seg:
        f = r.get("f")
        if f is None:
            continue
        rule = r.get("rule") or (r.get("diag") or {}).get("rule") or ""
        act = r.get("act") or ""
        if r.get("ev") == "GRID_THROW":
            out.append({"f": f, "rule": "truck_connect_grenade",
                        "gren_pre": None,
                        "gren_used": r.get("grenades_used")})
            continue
        d = r.get("diag") or {}
        if rule in THROW_RULES and (act == "GRENADE" or d):
            if act != "GRENADE" and not d.get("grenades_used"):
                continue                    # the turn frame, not the throw
            out.append({"f": f, "rule": rule,
                        "gren_pre": r.get("gren"),
                        "gren_used": d.get("grenades_used")})
    for t in out:
        t["land"] = t["f"] + FLIGHT
        t["outcome"] = "MISS"
        t["k"] = None
        t["side"] = None
    return out


def annotate(seg, throws, a4, freeze):
    for t in throws:
        for a in a4:
            if a["cls"] in ("CONNECT", "CHIP") and \
                    t["land"] <= a["f"] <= t["land"] + 8:
                t["outcome"] = a["cls"]
                t["a4_f"] = a["f"]
                break
        if freeze:
            rel = (t["land"] - freeze - BASE) / PERIOD
            t["k"] = int(round(rel))
            t["side"] = round(t["land"] - freeze - BASE
                              - PERIOD * t["k"], 1)


def gren_at(seg, f):
    best = None
    for r in seg:
        rf = r.get("f")
        if rf is None or "gren" not in r:
            continue
        if rf <= f:
            best = r["gren"]
        elif best is not None:
            break
    return best


def main():
    out = {}
    hdr = (f"{'src':6} {'stream':16} {'k':>3} {'side':>6} "
           f"{'outcome':8} {'throw_f':>8} {'gren_pre':>8} "
           f"{'rule':22}")
    print(hdr)
    print("-" * len(hdr))
    for name, stream, path in SOURCES:
        if not os.path.exists(path):
            print(f"{name:6} MISSING {path}")
            continue
        rows = load(path)
        segs = segment(rows)
        boots = []
        for seg in segs:
            freeze = freeze_of(seg)
            if freeze is None:
                continue
            a4 = a4_transitions(seg)
            if not a4:
                a4 = score_transitions(seg)
                for a in a4:
                    if a["f"] in KNOWN_CONNECTS.get(name, []):
                        a["cls"] = "CONNECT"
            throws = throws_of(seg, freeze)
            annotate(seg, throws, a4, freeze)
            deaths = [r for r in seg if r.get("ev") == "DEATH"]
            boot = {"freeze_f": freeze, "throws": throws,
                    "a4": a4,
                    "death": deaths[0] if deaths else None,
                    "n_rows": len(seg)}
            boots.append(boot)
        out[name] = {"stream": stream,
                     "file": os.path.relpath(path, EVID),
                     "boots": boots}
        for boot in boots:
            fz = boot["freeze_f"]
            for t in boot["throws"]:
                side_s = (f"{t['side']:+.0f}f"
                          if t.get("side") is not None else "?")
                print(f"{name:6} {stream:16} {str(t['k']):>3} "
                      f"{side_s:>6} {t['outcome']:8} {t['f']:>8} "
                      f"{str(t.get('gren_pre')):>8} {t['rule']:22}")
            d = boot["death"]
            if d:
                print(f"{name:6} DEATH f={d.get('f')} "
                      f"score={d.get('score')} px={d.get('px')}")
            else:
                print(f"{name:6} (no DEATH event; "
                      f"{boot['n_rows']} rows, freeze {fz})")
    # Q2: the grenade budget on r72b1 (the latest idle-hold boot)
    r72 = out.get("r72b1")
    if r72:
        boot = r72["boots"][0]
        fz = boot["freeze_f"]
        print(f"\nQ2 r72b1: freeze={fz}")
        for k in range(0, 5):
            grid = fz + BASE + PERIOD * k
            throw_f = int(grid - FLIGHT)
            print(f"  k={k} land=f{int(grid)} throw_f={throw_f} "
                  f"gren_at={gren_at(boot['n_rows'] and
                                    _seg_of(r72), throw_f)}")
    print("\nSUMMARY (stream, k, side-bucket) -> connect rate:")
    agg = {}
    for name, m in out.items():
        for boot in m["boots"]:
            for t in boot["throws"]:
                if t.get("k") is None or t.get("side") is None:
                    continue
                bucket = (m["stream"], t["k"],
                          "early(<=-2)" if t["side"] <= -2 else
                          "near(-1..0)" if t["side"] <= 0 else
                          "late(>=1)")
                agg.setdefault(bucket, []).append(t["outcome"])
    for bucket in sorted(agg, key=str):
        o = agg[bucket]
        print(f"  {bucket}: {o.count('CONNECT')}/{len(o)} connect {o}")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1, default=str)
    print("->", os.path.relpath(OUT, _REPO))
    return 0


_SEG_CACHE = {}


def _seg_of(m):
    if m["file"] not in _SEG_CACHE:
        path = os.path.join(EVID, m["file"])
        segs = segment(load(path))
        _SEG_CACHE[m["file"]] = segs[0]
    return _SEG_CACHE[m["file"]]


if __name__ == "__main__":
    sys.exit(main())
