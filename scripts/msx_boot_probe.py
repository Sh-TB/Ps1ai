#!/usr/bin/env python3
"""msx_boot_probe.py — round 7 (task 17-a) boot diagnostic.

m2t8 (anchor regen, post workspace-reset) recorded a FALSE gate pass:
boot() returned px 258.6 php 144 sec (6,1) (NOT the documented fresh
M1 spawn), the "M1 ride" hit a score-3300 tally at c43, and post_banner
right_probe "moved 135px" on an animating non-gameplay world — the
m2t1 trap signature.  Hypothesis: the gate (owns_pad churn>800 /
responsive()) false-passes on the INPUT-DEAD attract demo, which
self-animates and self-advances (session-8 discriminator).

This probe boots ONCE and classifies the gate-passed world with the
RAM-level discriminator (visual churn cannot distinguish demo vs real):
  quiet 90f  -> px drift (demo SELF-ADVANCES: drift != 0)
  RIGHT 90f  -> px delta on top of drift (real gameplay: > +8)
Verdicts: REAL_GAMEPLAY | ATTRACT_DEMO | INCONCLUSIVE.
One boot per process; evidence: scratch/issue6_round7_msx/.
"""
import argparse
import json
import os
import sys
import time

_REPO = "/home/z/my-project/ps1ai"
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _REPO)

from issue4_controller import boot                  # noqa: E402
from e2e_policy_trial import snap, px_of, sha_file, DISC  # noqa: E402
from msx_ramhunt_util import png, jlog              # noqa: E402

EVID = "/home/z/my-project/ps1ai/scratch/issue6_round7_msx"


def log(*a):
    print("[bp]", *a, file=sys.stderr, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=1)
    args = ap.parse_args()
    os.makedirs(EVID, exist_ok=True)
    tag = f"bp{args.run}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(EVID, f"{tag}.jsonl"), "w")

    def J(ev):
        jlog(jf, ev)

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    s0 = snap(m)
    J({"ev": "boot", "run": args.run, "firmware": fw, **s0})
    png(p, "gate_world", tag)
    log(f"boot gate world: px={s0['px']} php={s0['php']} "
        f"sec={s0['sec']} score={s0['score']} flags={s0['flags']}")

    px0 = px_of(m)
    p.core.run(90, set())
    drift = round(px_of(m) - px0, 1)
    s1 = snap(m)
    J({"ev": "QUIET", "px0": px0, "drift": drift, **s1})
    png(p, "quiet90", tag)

    p.core.run(90, {"RIGHT"})
    moved = round(px_of(m) - px0 - drift, 1)
    s2 = snap(m)
    J({"ev": "RIGHT", "moved_net": moved, **s2})
    png(p, "right90", tag)

    if abs(drift) < 2.0 and moved > 8.0:
        verdict = "REAL_GAMEPLAY"
    elif abs(drift) >= 2.0 or moved <= 8.0:
        verdict = "ATTRACT_DEMO"
    else:
        verdict = "INCONCLUSIVE"
    J({"ev": "VERDICT", "verdict": verdict, "drift": drift,
       "moved_net": moved})
    out = {"run": args.run, "firmware": fw, "gate_world": s0,
           "drift": drift, "moved_net": moved, "verdict": verdict,
           "wall_s": round(time.time() - t0, 1),
           "game_sha256": sha_file(DISC)}
    with open(os.path.join(EVID, f"report_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    jf.close()
    log(f"VERDICT {verdict} drift={drift} moved={moved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
