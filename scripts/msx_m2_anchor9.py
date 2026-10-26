#!/usr/bin/env python3
"""msx_m2_anchor9.py — Issue #5 session 11 / Issue #6 round 8 (task 8-a):
m2_train anchor regeneration attempt #9 + the m1_end gate capture.

The round-8 recorded lever ("the surgical M1-end vs M2-side loading
diff — requires the m2_train anchor") needs TWO savestates from ONE
proven fresh-boot chain:

  1. "m1_end"  — the post-banner CONTINUE? countdown gate
                 (px 0.0, sec (11,1), flags 255, score>0) captured at
                 FIRST sighting, BEFORE any START tap.
  2. "m2_train" — the first stable M2 gameplay (score==0, 0<px<100,
                 php>0) — the anchor the workspace reset wiped.

This wrapper REUSES the proven m2_train_advance machinery verbatim
(run_once -> post_banner -> train_phase, the session-6 path) and adds
exactly ONE thing: the J() event logger watches every observation for
the countdown signature and saves "m1_end" the moment it first appears.
No input, timing, or phase logic is changed — the m2t1 lesson (input
inside the fragile window re-arms the end machinery) is respected.

One boot per process.  Evidence: scratch/issue6_round8_msx/ (this
wrapper's own JSONL + report); m2_train_advance's own artifacts still
land in evidence issue5_m2_train/ and are copied to scratch after.
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

import m2_train_advance as mt                       # noqa: E402
from issue4_controller import boot                  # noqa: E402
from e2e_policy_trial import snap, sha_file, DISC   # noqa: E402

SCRATCH = "/home/z/my-project/ps1ai/scratch/issue6_round8_msx"
COUNTDOWN = (11, 1)          # sec (state, flags) of the CONTINUE? gate


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=int, default=9)
    ap.add_argument("--chunks", type=int, default=2600,
                    help="fresh-boot M1 chunk budget (m2t7 banner c=107)")
    ap.add_argument("--t_chunks", type=int, default=mt.T_CHUNKS_DEFAULT)
    args = ap.parse_args()
    os.makedirs(SCRATCH, exist_ok=True)
    tag = f"m2t{args.run}_{time.strftime('%H%M%S')}"
    jf = open(os.path.join(SCRATCH, f"{tag}.jsonl"), "w")
    st = {"m1_end_saved": False, "m1_end_snap": None}

    def J(ev):
        # ---- the ONLY addition: capture m1_end at the gate ----
        if (not st["m1_end_saved"] and ev.get("px") == 0.0
                and ev.get("flags") == 255
                and int(ev.get("score") or 0) > 0
                and tuple(ev.get("sec") or ()) == COUNTDOWN):
            try:
                p.save_state("m1_end")
                st["m1_end_saved"] = True
                st["m1_end_snap"] = {k: ev.get(k) for k in
                                     ("px", "score", "php", "gren",
                                      "flags", "sec")}
                jf.write(json.dumps(
                    {"ev": "M1_END_SAVED", "state": "m1_end",
                     "at_event": ev.get("ev"), **st["m1_end_snap"]},
                    default=str) + "\n")
                jf.flush()
                mt.png(p, "m1_end_gate", tag)
                mt.log("M1_END saved at countdown signature "
                       f"(event {ev.get('ev')})")
            except Exception as e:                          # noqa: BLE001
                jf.write(json.dumps({"ev": "M1_END_SAVE_FAIL",
                                     "err": repr(e)[:120]}) + "\n")
                jf.flush()
        jf.write(json.dumps(ev, default=str) + "\n")
        jf.flush()

    t0 = time.time()
    p, fw = boot()
    m = p.mem
    J({"ev": "boot", "run": args.run, "firmware": fw, **snap(m)})
    mt.log(f"=== anchor9 run {args.run}: booted ({fw}) ===")
    # ---- the PROVEN fresh-boot path, verbatim ----
    rec = mt.run_once(p, m, J, tag, args.chunks, control=False)
    J({"ev": "e2e_result", **{k: rec[k] for k in
                              ("outcome", "end_chunk", "deaths")}})
    mt.log("M1 fresh boot:", rec["outcome"], "c=", rec["end_chunk"],
           "deaths=", rec["deaths"])
    post = trec = None
    if rec["outcome"] == "MISSION_BANNER":
        post = mt.post_banner(p, m, J, tag, rec["deaths"])
        J({"ev": "post_banner", "result": post})
        mt.log("post-banner:", post)
        if post == "gameplay_seen":
            trec = mt.train_phase(p, m, J, tag, t_chunks=args.t_chunks)
    else:
        mt.log("M1 fresh boot did not reach the banner — aborting before T")
    out = {"m1": {k: rec[k] for k in
                  ("outcome", "end_chunk", "deaths", "was_deep",
                   "final", "wall_s")},
           "post_banner": post,
           "train": ({k: trec[k] for k in
                      ("outcome", "end_i", "spawns_seen", "anchor_saved",
                       "max_px", "final", "wall_s")} if trec else None),
           "m1_end_saved": st["m1_end_saved"],
           "m1_end_snap": st["m1_end_snap"],
           "run": args.run, "firmware": fw,
           "wall_total_s": round(time.time() - t0, 1),
           "frames": p.core.frames_run,
           "game_sha256": sha_file(DISC)}
    with open(os.path.join(SCRATCH, f"report_{tag}.json"), "w") as f:
        json.dump(out, f, indent=1, default=str)
    J({"ev": "RUN_DONE", **out})
    jf.close()
    mt.log(f"RUN m2t{args.run}: m1={rec['outcome']} post={post} "
           f"train={trec['outcome'] if trec else None} "
           f"anchor={trec['anchor_saved'] if trec else False} "
           f"m1_end={st['m1_end_saved']} wall={out['wall_total_s']}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
