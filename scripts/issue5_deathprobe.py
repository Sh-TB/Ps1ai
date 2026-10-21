#!/usr/bin/env python3
"""issue5_deathprobe.py — WHAT kills at the village (~2100f) even with
the invulnerability-blink frozen positive?

Protocol (smallest decisive experiment):
  1. boot, freeze the verified blink timer u8@<live> (0xEF13F family).
  2. save t0, walk right (RoutePolicy, no grenades) with PNG every
     100 frames and a 4-slot snapshot ring (100f spacing).
  3. on the first flags!=0xFF: save the death PNG + final snapshot;
     diff the last alive snapshot vs the death snapshot and report
     changed regions (pit => position-ish words, scripted => state
     bytes, damage => health-ish words).
Output: evidence/issue5_deathprobe_<tag>/{pngs,death_report.json}
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

import numpy as np
from PIL import Image                                     # noqa: E402

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play import labconfig                             # noqa: E402
from ps1play.telemetry import TelemetryAdapter, JsonlTrace  # noqa: E402
from ps1play.agent.cheatprof import (                      # noqa: E402
    CheatSession, CHEAT_ASSISTED, derive_freeze_code)
from ps1play.agent.route import RoutePolicy, StallDetector   # noqa: E402
from issue4_controller import boot                           # noqa: E402
from issue5_recon import _blink_candidates                   # noqa: E402


def _log(*a):
    print("[deathprobe]", *a, file=sys.stderr, flush=True)


def png(p, evid, name):
    rgb = p.core.frame_rgb()
    if rgb is not None:
        Image.fromarray(rgb).save(os.path.join(evid, name))


def diff_regions(a, b, top=24, gap=6):
    ch = np.flatnonzero(a[:0x1FC000] != b[:0x1FC000])
    out = []
    if ch.size:
        gaps = np.flatnonzero(np.diff(ch) > gap)
        starts = np.concatenate(([0], gaps + 1))
        ends = np.concatenate((gaps, [ch.size - 1]))
        for s, e in zip(starts, ends):
            aa, bb = int(ch[s]), int(ch[e])
            out.append({"addr": hex(aa), "len": bb - aa + 1,
                        "before": [int(x) for x in
                                   a[aa:aa + 8]], "after":
                        [int(x) for x in b[aa:aa + 8]]})
        out.sort(key=lambda r: -r["len"])
    return out[:top]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="d1")
    ap.add_argument("--max-frames", type=int, default=4000)
    ap.add_argument("--grenade-period", type=int, default=0,
                    help="0 = no grenades (d1 baseline); else throw "
                         "cadence in frames (A/B variable)")
    ap.add_argument("--jump", action="store_true",
                    help="enable the periodic hop (A/B variable)")
    ap.add_argument("--evidence-dir",
                    default=labconfig.resolve_path("evidence_dir"))
    args = ap.parse_args()
    outdir = os.path.join(args.evidence_dir,
                          f"issue5_deathprobe_{args.tag}")
    os.makedirs(outdir, exist_ok=True)
    trace = JsonlTrace(os.path.join(outdir, "trace.jsonl"))

    p, fwmode = boot()
    session = CheatSession(p, CHEAT_ASSISTED, opt_in=True)
    tel = TelemetryAdapter(p)

    cands = _blink_candidates(p)
    _log("blink cands:", [(hex(c["addr"]), c["width"]) for c in cands])
    if not cands:
        sys.exit("!! blink not found")
    cd = sorted(cands, key=lambda c: (c["width"], c["addr"]))[0]
    dtype = "u8" if cd["width"] == 1 else "u16"
    code, val = derive_freeze_code(p, cd["addr"],
                                   value=max(int(cd["series"][0]), 32),
                                   dtype=dtype)
    session.enable("invuln_blink", [code])
    _log("blink frozen:", code.raw)
    p.save_state("t0")

    policy = RoutePolicy(allow_grenades=args.grenade_period > 0,
                         jump_enabled=args.jump)
    if args.grenade_period > 0:
        policy.GRENADE_PERIOD = args.grenade_period
    det = StallDetector()
    ring = collections.deque(maxlen=4)      # (frame, snapshot)
    death = None
    f = 0
    t0 = time.time()
    while f < args.max_frames:
        for s in policy.decide(100, det):
            session.run_frames(s["frames"], set(s["btns"] or set()))
            f += s["frames"]
        cur = tel.snapshot(buttons=[], frame=p.core.frames_run)
        ring.append((cur["frame"], p.mem.snapshot()))
        png(p, outdir, f"w{cur['frame']:06d}.png")
        trace.write({"type": "w", "frame": cur["frame"],
                     "flags": cur["flags_word"], "score": cur["score"]})
        if cur["flags_word"] != 0xFF:
            death = cur
            png(p, outdir, "DEATH.png")
            break
    if death is None:
        _log("survived the whole window (no death) — variant holds!")
        report = {"survived": True, "frames": f,
                  "blink": code.raw,
                  "grenade_period": args.grenade_period,
                  "wall_s": round(time.time() - t0, 1)}
    else:
        fr_last, snap_last = ring[-2] if len(ring) >= 2 else ring[-1]
        fr_d, snap_d = ring[-1]
        regions = diff_regions(snap_last, snap_d)
        report = {"survived": False, "death_frame": death["frame"],
                  "last_alive_frame": fr_last, "blink": code.raw,
                  "blink_addr": hex(int(cd["addr"])),
                  "grenade_period": args.grenade_period,
                  "diff_regions": regions,
                  "wall_s": round(time.time() - t0, 1)}
        _log("death at frame", death["frame"],
             "diff regions:", [(r["addr"], r["len"]) for r in regions[:8]])
    with open(os.path.join(outdir, "death_report.json"), "w") as fjson:
        json.dump(report, fjson, indent=1, default=str)
    _log("report:", os.path.join(outdir, "death_report.json"))
    trace.close()
    session.disable_all()
    del p
    return 0


if __name__ == "__main__":
    sys.exit(main())
