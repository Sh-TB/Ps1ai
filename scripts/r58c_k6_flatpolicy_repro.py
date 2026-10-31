#!/usr/bin/env python3
"""r58c_k6_flatpolicy_repro.py — measure the champion on k6 through the
EXACT r57 ARS measurement path (FlatPolicy + rollout), FIRST rollout of
a fresh process (restore #1 — the cleanest restore class).

Resolves the k6 discrepancy: r57 recorded 87 @10000 (ARS iter-0 eval);
today's BrainClient eval measured 63 death@7345. The path-replay (r58b)
proved the two decision paths act identically on identical frames, so
any difference must come from the EPISODE state, not the policy call.
"""
import json
import os
import sys

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv                  # noqa: E402
from ps1play.learn import student_only as SO               # noqa: E402
from r57f_es_ars import FlatPolicy, rollout                # noqa: E402

ART = os.path.join(REPO, "data", "learn", "r57_es2_dir2p.npz")
SCR = os.path.join(REPO, "scratch", "r57")


def main():
    trace = SO.NoTeacherTrace(os.path.join(
        SCR, "noteacher_trace_r58c_k6repro.jsonl"))
    SO.install_teacher_blocker(trace)
    trace.event("K6_REPRO_START", model="r57_es2_dir2p.npz")

    env = FlappyEnv()
    env.reach_ready()
    pol = FlatPolicy(ART)
    # restore #1 in this process: k6
    r, steps, wall = rollout(env, pol, 6, 10000)
    row = {"path": "FlatPolicy.rollout (r57f exact)", "k": 6,
           "pipes": r, "steps": steps, "wall_s": wall}
    # and a second restore in the same process for the restore-count axis
    r2, steps2, wall2 = rollout(env, pol, 6, 10000)
    row["second_restore"] = {"pipes": r2, "steps": steps2}
    env.close()
    trace.event("K6_REPRO_DONE", **{k: v for k, v in row.items()
                                    if k != "path"})
    trace.event("SECOND_RESTORE", pipes=r2, steps=steps2)
    print("TRACE_SHA:", trace.finish())
    with open(os.path.join(SCR, "r58c_k6_repro.json"), "w") as f:
        json.dump(row, f, indent=2)
    print(json.dumps(row, indent=1))


if __name__ == "__main__":
    main()
