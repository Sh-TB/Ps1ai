#!/usr/bin/env python3
"""r54g_flappy_eval.py — P4 Stage D (flappy): the SAME-PROTOCOL
head-to-head + DAgger collection.

Tiers (disclosed):
  P1_teacher_full — the r15 play law on FULL-RES vision (the r53
                    baseline tier; 69 pipes @ k=6 in r53)
  P1s_teacher_sf  — the SAME law through the SMALL-FRAME feature
                    pathway (the same-sensory-tier baseline the
                    visual student must beat)
  P4_student_feat — the learned visual-only brain (SUBPROCESS; frames
                    in / action out; feature_version 2)

Seeds: k=6/30/60 (train family), k=90/210 (HELD-OUT, never collected).
Pipe count = the vision band-acquisition proxy (r53 convention).
Deaths = the beige-panel test. Student episodes on TRAIN seeds also
collect DAgger relabels (full-res teacher) into ds_flappy_dagger_p4.
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import FlappyEnv, _small_rgb      # noqa: E402
from ps1play.learn.teacher import FlappyTeacher            # noqa: E402
from ps1play.learn.runner import BrainClient               # noqa: E402
from ps1play.learn.dataset import EpisodeRecord            # noqa: E402
from ps1play.learn.perception import (flappy_bird_y,       # noqa: E402
                                      flappy_gap_target_r15,
                                      flappy_green_mask)
from hellopong_r12_lib import make_jrn                     # noqa: E402

OUT = os.path.join(REPO, "scratch", "r54")
DS_DAG = os.path.join(OUT, "ds_flappy_dagger_p4")

FIELDS = [
    {"name": "frame_small_rgb", "role": "visual_input",
     "source": "frame_rgb -> area downsample 60x80x3"},
    {"name": "bird_y", "role": "visual_input",
     "source": "yellow centroid"},
    {"name": "vy", "role": "visual_input", "source": "bird_y diff"},
    {"name": "gap_center", "role": "visual_input",
     "source": "flappy_gap_target_r15"},
    {"name": "pipes", "role": "evaluation_only",
     "source": "vision band-crossing count"},
]


def run_life(env, agent, k, max_steps, tag, jr, dag=None, dag_t=None):
    env.start_episode(k)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    if dag_t is not None:
        dag_t.reset_history()
    pipes = 0
    flaps = 0
    last_band_x = None
    prev_by = None
    t0 = time.time()
    step = 0
    for step in range(max_steps):
        fr = env.frame()
        small = _small_rgb(fr)
        if hasattr(agent, "act_full"):
            action = agent.act_full(fr)   # native-sensor baseline tier
        else:
            action = agent.act(small)     # frame-only tier
        buttons = {"B"} if action == "FLAP" else set()
        if action == "FLAP":
            flaps += 1
        # vision bookkeeping (evaluation-side; never sent to the agent)
        by, _n = flappy_bird_y(fr)
        green = flappy_green_mask(fr)
        _gc, bx = flappy_gap_target_r15(green, by)
        if bx is not None:
            if last_band_x is not None and bx > last_band_x + 60:
                pipes += 1
            last_band_x = bx
        if dag is not None and dag_t is not None:
            tby, tvy, tgc = dag_t.observe(fr, prev_by)
            t_act = dag_t.act(tby, tvy if tvy is not None else 0.0, tgc)
            dag.add_frame(small)
            dag.add_step(action, teacher_action=t_act, labels={
                "bird_y": -1.0 if tby is None else float(tby),
                "vy": -99.0 if tvy is None else float(tvy),
                "gap_center": -1.0 if tgc is None else float(tgc),
                "pipes": pipes})
        prev_by = by
        env.run(1, buttons)
        if env.game_over(env.frame()):
            break
    res = {"tag": tag, "k": k, "result": "death" if step < max_steps - 1
           else "budget", "pipes": pipes, "steps": step + 1,
           "flaps": flaps, "wall_s": round(time.time() - t0, 1)}
    jr({"ev": "eval", **res})
    return res


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="p4r1")
    ap.add_argument("--art", default=os.path.join(
        OUT, "flappy_student_feat_p4.npz"))
    ap.add_argument("--agents", default="full,sf,student")
    ap.add_argument("--dagger-prefix", default="p4fdag_r1")
    ap.add_argument("--dagger", default="1", choices=["0", "1"])
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    jr = make_jrn(OUT, f"[flapP4E:{a.tag}]")
    env = FlappyEnv()
    env.reach_ready()
    report_path = os.path.join(OUT, f"flappy_eval_{a.tag}.json")
    results = {}
    dag_sink = {"ids": [], "prefix": a.dagger_prefix} if a.dagger == "1" \
        else None

    seeds = [(6, 6000), (30, 4500), (60, 4500),
             (90, 4000), (210, 4000)]
    want = set(a.agents.split(","))

    if "full" in want:
        teacher = FlappyTeacherAgentFull()
        rows = []
        for k, budget in seeds:
            r = run_life(env, teacher, k, budget,
                         f"teacher_full_k{k}", jr)
            rows.append(r)
        results["P1_teacher_full"] = rows
        with open(report_path, "w") as f:
            json.dump({"tag": a.tag, "results": results,
                       "dagger_ids": dag_sink["ids"] if dag_sink
                       else []}, f, indent=2)
        print("== P1_teacher_full saved", flush=True)

    if "obs" in want:
        rows = []
        for k, budget in seeds:
            r = run_life(env, FlappyTeacherAgentObserver(), k, budget,
                         f"teacher_obs_k{k}", jr)
            rows.append(r)
        results["P1t_teacher_observer"] = rows
        with open(report_path, "w") as f:
            json.dump({"tag": a.tag, "results": results,
                       "dagger_ids": dag_sink["ids"] if dag_sink
                       else []}, f, indent=2)
        print("== P1t_teacher_observer saved", flush=True)

    if "sf" in want:
        from ps1play.learn.teacher import FlappyTeacherAgent
        rows = []
        for k, budget in seeds:
            r = run_life(env, FlappyTeacherAgent(), k, budget,
                         f"teacher_sf_k{k}", jr)
            rows.append(r)
        results["P1s_teacher_smallframe"] = rows
        with open(report_path, "w") as f:
            json.dump({"tag": a.tag, "results": results,
                       "dagger_ids": dag_sink["ids"] if dag_sink
                       else []}, f, indent=2)
        print("== P1s_teacher_smallframe saved", flush=True)

    if "student" in want:
        client = BrainClient(a.art)
        rows = []
        for k, budget in seeds:
            dag = None
            if dag_sink is not None and k in (6, 30, 60):
                dag = EpisodeRecord(
                    game="flappy", mode="evaluate_visual_only",
                    episode_id=f"{a.dagger_prefix}_k{k:03d}",
                    scenario=f"seed_k{k}", field_table=FIELDS,
                    frame_shape=(60, 80, 3),
                    note="student state, full-res FlappyTeacher relabel")
            r = run_life(env, client, k, budget,
                         f"student_feat_k{k}", jr,
                         dag=dag, dag_t=FlappyTeacher() if dag else None)
            r["agent"] = "P4_student_feat"
            rows.append(r)
            if dag is not None and len(dag.actions):
                dag.freeze(DS_DAG)
                dag_sink["ids"].append(dag.episode_id)
        client.close()
        results["P4_student_feat"] = rows
        with open(report_path, "w") as f:
            json.dump({"tag": a.tag, "results": results,
                       "dagger_ids": dag_sink["ids"] if dag_sink
                       else []}, f, indent=2)
        print("== P4_student_feat saved", flush=True)

    env.close()
    for name, rows in results.items():
        for r in rows:
            print(f"{name:22s} k={r['k']:3d} {r['result']:6s} "
                  f"pipes={r['pipes']:3d} steps={r['steps']:5d} "
                  f"flaps={r['flaps']}")


class FlappyTeacherAgentFull:
    """The r15 law with native full-res sensors (the r53 baseline)."""

    name = "flappy_teacher_full"

    def __init__(self):
        self.t = FlappyTeacher()
        self._prev = None

    def reset_history(self):
        self.t.reset_history()
        self._prev = None

    def act(self, small):    # ignores the small frame; uses act_full path
        raise NotImplementedError

    def act_full(self, fr):
        by, vy, gc = self.t.observe(fr, self._prev)
        self._prev = by
        return self.t.act(by, vy if vy is not None else 0.0, gc)


class FlappyTeacherAgentObserver:
    """The r15 law driven by the v5 OBSERVER bird state (the same
    perception the v5 student consumes — its true same-sensor
    ceiling). Frames in; observer integrates source-verified physics
    between gated measurements."""

    name = "flappy_teacher_sf_obs"

    def __init__(self, use_v2=True):
        from ps1play.learn import visual_only as VO
        self.t = FlappyTeacher()
        self.obs = (VO.FlappyObserverV2() if use_v2
                    else VO.FlappyObserver())
        self._prev_action = None
        self._vo = VO

    def reset_history(self):
        self.t.reset_history()
        self.obs.reset()
        self._prev_action = None

    def act(self, small):
        by, vy = self.obs.step(small, self._prev_action)
        _gc, _dx, _g0, _g1, _rb = self._vo._flappy_gap_raw(small)
        a = self.t.act(by if by is not None else None, vy,
                       _gc if _gc >= 0 else None)
        self._prev_action = a
        return a


if __name__ == "__main__":
    main()
