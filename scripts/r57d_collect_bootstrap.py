#!/usr/bin/env python3
"""r57d_collect_bootstrap.py — R57 P1: the capped teacher demonstrations.

Mission PART 2 verbatim discipline:
  * 10 teacher episodes on the TRAIN seed family (k6 x3, k60 x3, k30 x2,
    k12, k45 — interleaved), ONE boot, all from the pre-seed anchor;
  * the teacher = flappy_law_on_v7 (the r15 law on BirdObserverV7 +
    GapTrackerV7 — the SAME same-sensor pathway as the v7 student);
  * recording STOPS at the step whose execution completes the 20th
    VISUALLY CONFIRMED passage; the label at that cutoff step is
    EXCLUDED (the conservative rule: no teacher action from the cutoff
    frame onward — test-enforced);
  * early teacher deaths are kept (the cap is a ceiling, not a target);
  * RAM score read ONCE per episode, after the cutoff, ASSISTED MODE
    ONLY, role = audit (cross-checks the visual counter; never a label).

Outputs: scratch/r57/tb_life_eNN.npz + tb_manifest.json (episode table,
boot id, cutoff proof, dataset sha256).
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv, _small_rgb      # noqa: E402
from ps1play.learn.perception import flappy_bird_y         # noqa: E402
from r57_lib import PassageCounter, jsave, sha256_file     # noqa: E402
from r55g_m1 import LawOnV7Agent                           # noqa: E402

OUT = os.path.join(REPO, "scratch", "r57")
os.makedirs(OUT, exist_ok=True)

PLAN = [("e01", 6), ("e02", 60), ("e03", 6), ("e04", 60), ("e05", 30),
        ("e06", 6), ("e07", 60), ("e08", 30), ("e09", 12), ("e10", 45)]
CAP = 20
BUDGET = 6000
RAM_ANCHORS = {"score": (0x1FF50E, "u16"), "dead": (0x1FF496, "u8")}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="",
                    help="comma list of PLAN indices to run (e.g. 1,2,3); "
                         "default all; existing episode records are kept")
    a = ap.parse_args()
    idxs = ([int(x) for x in a.only.split(",")] if a.only
            else list(range(len(PLAN))))
    env = FlappyEnv()
    env.reach_ready()
    boot_id = f"boot_{time.strftime('%H%M%S')}"
    agent = LawOnV7Agent()
    episodes = []
    for i in idxs:
        eid, k = PLAN[i]
        env.start_episode(k)
        agent.reset_history()
        pc = PassageCounter()
        frames, acts, obs_ys, gcs, beaks, sts, bxs = [], [], [], [], [], [], []
        cutoff_step = None
        step = 0
        result = "budget"
        for step in range(BUDGET):
            fr = env.frame()
            small = _small_rgb(fr)
            action = agent.act(small)
            frames.append(small)
            acts.append(action)
            obs_ys.append(float(agent.obs.y)
                          if agent.obs.y is not None else -1.0)
            gcs.append(float(agent.gtr.gc)
                       if agent.gtr.gc is not None else -1.0)
            sts.append(int(agent.obs.since_trust))
            by, _n = flappy_bird_y(fr)
            beaks.append(float(by) if by is not None else -1.0)
            from ps1play.learn.perception import (
                flappy_green_mask as _fgm,
                flappy_gap_target_r15 as _fgr)
            _gc, bx = _fgr(_fgm(fr), by if by is not None else -1)
            bxs.append(float(bx) if bx is not None else -1.0)
            env.run(1, {"B"} if action == "FLAP" else set())
            fr2 = env.frame()
            by2, _n2 = flappy_bird_y(fr2)
            _gc2, bx2 = _fgr(_fgm(fr2), by2 if by2 is not None else -1)
            if pc.fire(bx2, step):
                if pc.count >= CAP:
                    cutoff_step = step      # the step that COMPLETED #20
                    result = "cutoff"
                    break
            if env.game_over(env.frame()):
                result = "death"
                break
        n_rec = (cutoff_step if cutoff_step is not None
                 else step + 1)            # labels: steps [0, n_rec)
        audit = env.read_assisted(RAM_ANCHORS)
        rec = {
            "episode_id": f"r57_tb_{eid}", "k": int(k),
            "result": result,
            "passages": pc.count, "cutoff_step": cutoff_step,
            "n_labels": int(n_rec), "steps_total": step + 1,
            "ram_score_at_end": audit.get("score", -1),
            "dead_flag_at_end": audit.get("dead", -1),
            "source_type": "teacher",
            "source_checkpoint": "flappy_law_on_v7 (r55g_m1)",
            "action_contract": "FLAP=1-frame B emit inside the teacher's "
                               "2f-pulse/3f-cooldown SM; HOVER=release",
            "feature_version": 7,
        }
        npz = os.path.join(OUT, f"tb_life_{eid}.npz")
        np.savez_compressed(
            npz,
            frames=np.asarray(frames[:n_rec], dtype=np.uint8),
            actions=np.asarray(acts[:n_rec]),
            obs_y=np.asarray(obs_ys[:n_rec], dtype=np.float32),
            gc=np.asarray(gcs[:n_rec], dtype=np.float32),
            beak_y=np.asarray(beaks[:n_rec], dtype=np.float32),
            since_trust=np.asarray(sts[:n_rec], dtype=np.int32),
            band_x=np.asarray(bxs[:n_rec], dtype=np.float32))
        rec["npz"] = os.path.basename(npz)
        rec["npz_sha256"] = sha256_file(npz)
        rec["boot_id"] = boot_id
        episodes.append(rec)
        print(json.dumps(rec), flush=True)
    env.close()
    mpath = os.path.join(OUT, "tb_manifest.json")
    prev = []
    if os.path.exists(mpath):
        with open(mpath) as f:
            prev = json.load(f).get("episodes", [])
    have = {e["episode_id"] for e in prev}
    merged = prev + [e for e in episodes
                     if e["episode_id"] not in have]
    merged.sort(key=lambda e: e["episode_id"])
    manifest = {
        "round": "R57 P1", "cap_pipes": CAP, "rule": (
            "recording stops at the step completing the 20th visually "
            "confirmed passage; the cutoff step's own label is excluded "
            "(no teacher action from the cutoff frame onward)"),
        "teacher": "flappy_law_on_v7",
        "teacher_params": {"flap_below": 14.0, "emergency_below": 26.0},
        "plan": PLAN, "boot_ids": sorted(
            {e.get("boot_id", "?") for e in merged}),
        "episodes": merged,
        "total_labels": sum(e["n_labels"] for e in merged),
        "cutoff_proof": all(
            (e["result"] == "cutoff" and e["passages"] == CAP
             and e["n_labels"] == e["cutoff_step"])
            or (e["result"] == "death" and e["passages"] < CAP)
            for e in merged),
    }
    jsave(mpath, manifest)
    print("episodes so far:", len(merged),
          "| cutoff_proof:", manifest["cutoff_proof"],
          "| total labels:", manifest["total_labels"], flush=True)


if __name__ == "__main__":
    main()
