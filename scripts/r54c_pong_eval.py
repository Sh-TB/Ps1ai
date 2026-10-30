#!/usr/bin/env python3
"""r54c_pong_eval.py — P4 Stage D: the SAME-PROTOCOL head-to-head.

Agents (identical anchors, opponents, seeds, step budgets):
  P1_teacher_v1   — the r53 visual tracking baseline (small-frame
                    features, in-process)
  P4_teacher_v2   — the RAM-truth predictive teacher (ASSISTED, the
                    label-source ceiling; never claimed visual)
  P4_student_feat — the learned visual-only brain (SUBPROCESS, frames
                    in / action out, artifact pong_student_feat_p4.npz)
  P4_student_raw  — the raw-pixel brain (SUBPROCESS)

Environments: game AI (pad2 disconnected) x2; train_fam (aim 14 /
delay 10) seeds 100-102; HELD-OUT family (aim 22 / delay 16) seeds
200-202 — never seen in collection. Student episodes double as the
DAgger round: every student state is relabeled by teacher v2 (RAM
truth, assisted side) into ds_pong_dagger_p4.
Incremental JSON saves after EVERY agent (timeout resilience).
"""
import json
import os
import sys
import time

import numpy as np

REPO = "/home/z/my-project/ps1ai"
for _p in (REPO, os.path.join(REPO, "scripts")):
    sys.path.insert(0, _p)

from ps1play.learn.games import PongEnv                     # noqa: E402
from ps1play.learn.perception import to_gray                # noqa: E402
from ps1play.learn.teacher import (PongTeacherV2,           # noqa: E402
                                   ScenarioOpponent,
                                   PongTeacherAgent)
from ps1play.learn.runner import BrainClient                # noqa: E402
from ps1play.learn.dataset import EpisodeRecord             # noqa: E402
from hellopong_r12_lib import make_jrn                      # noqa: E402

OUT = os.path.join(REPO, "scratch", "r54")
DS_DAG = os.path.join(OUT, "ds_pong_dagger_p4")
BALL_X, BALL_Y = 0x1FFEA0, 0x1FFEA4
PAD_L, SCORE_L = 0x1FFEB0, 0x1FFEB4
PAD_R, SCORE_R = 0x1FFEB8, 0x1FFEBC

FIELDS = [
    {"name": "frame_small_gray", "role": "visual_input",
     "source": "frame_rgb -> to_gray 60x80"},
    {"name": "ball_x", "role": "teacher_label", "source": "ram:0x1FFEA0"},
    {"name": "ball_y", "role": "teacher_label", "source": "ram:0x1FFEA4"},
    {"name": "pad_l", "role": "teacher_label", "source": "ram:0x1FFEB0"},
    {"name": "pad_r", "role": "teacher_label", "source": "ram:0x1FFEB8"},
    {"name": "score_l", "role": "evaluation_only",
     "source": "ram:0x1FFEB4"},
    {"name": "score_r", "role": "evaluation_only",
     "source": "ram:0x1FFEBC"},
]

TRAIN_FAM = {"aim_err": 14.0, "delay": 10, "deadband": 8.0}
HELDOUT_FAM = {"aim_err": 22.0, "delay": 16, "deadband": 8.0}


def i32(ram, a):
    return int(np.frombuffer(ram[a:a + 4].tobytes(), "<i4")[0])


def episode(env, agent, opponent, max_steps, port1_device,
            dag=None, dag_teacher=None):
    env.p.core.set_port_device(0, port=1)
    env.load_anchor("pong_anchor")
    env.p.core.set_port_device(port1_device, port=1)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    if dag_teacher is not None:
        dag_teacher.reset_history()
    contacts = returns = 0
    in_contact = False
    steps = 0
    t0 = time.time()
    disagree = teacher_n = 0
    for _ in range(max_steps):
        small = env.frame_small()
        ram = env.p.core.ram.copy()
        if getattr(agent, "wants_ram_truth", False):
            agent.set_ram(i32(ram, BALL_X), i32(ram, BALL_Y),
                          i32(ram, PAD_L))
        action = agent.act(small)
        buttons = {"UP": {"UP"}, "DOWN": {"DOWN"},
                   "NONE": set()}.get(action, set())
        opp_buttons = set()
        if opponent is not None:
            opponent.observe(i32(ram, BALL_Y), i32(ram, PAD_R))
            opp_buttons = opponent.buttons()
        if dag is not None and dag_teacher is not None:
            dag_teacher.observe_ram(i32(ram, BALL_X), i32(ram, BALL_Y))
            t_act = dag_teacher.act(i32(ram, PAD_L))
            teacher_n += 1
            disagree += (t_act != action)
            dag.add_frame(to_gray(env.frame()))
            dag.add_step(action, teacher_action=t_act, labels={
                "ball_x": i32(ram, BALL_X), "ball_y": i32(ram, BALL_Y),
                "pad_l": i32(ram, PAD_L), "pad_r": i32(ram, PAD_R),
                "score_l": i32(ram, SCORE_L), "score_r": i32(ram, SCORE_R)})
        env.run(2, buttons, opp_buttons)
        steps += 1
        _, ram = env.frame(), env.p.core.ram.copy()
        bx = i32(ram, BALL_X)
        if bx < 30:
            in_contact = True
        elif in_contact and bx > 45:
            contacts += 1
            returns += 1
            in_contact = False
        elif bx > 100:
            in_contact = False
        sl, sr = i32(ram, SCORE_L), i32(ram, SCORE_R)
        if sl >= 5 or sr >= 5:
            break
    result = ("win" if sl >= 5 else "loss" if sr >= 5 else "rally")
    return {"result": result, "steps": steps, "score_l": int(sl),
            "score_r": int(sr), "contacts": contacts, "returns": returns,
            "wall_s": round(time.time() - t0, 1),
            "disagree_rate": round(disagree / teacher_n, 3)
            if teacher_n else None}


def run_agent(env, name, agent, jr, dag_sink=None):
    rows = []
    for ep in range(2):
        dag = None
        if dag_sink is not None:
            dag = EpisodeRecord(
                game="pong", mode="evaluate_visual_only",
                episode_id=f"{dag_sink['prefix']}_gameai_{ep}",
                scenario="game_ai", field_table=FIELDS,
                frame_shape=(60, 80),
                note="student state, PongTeacherV2 relabel (RAM)")
        r = episode(env, agent, None, 2600, 0,
                    dag=dag if dag_sink else None,
                    dag_teacher=dag_sink["teacher"] if dag_sink else None)
        r["env"] = "game_ai"
        rows.append(r)
        jr({"ev": "ep", "agent": name, **r})
        if dag is not None and len(dag.actions):
            dag.freeze(DS_DAG)
            dag_sink["ids"].append(dag.episode_id)
    for fam, params, base in (("train_fam", TRAIN_FAM, 100),
                              ("heldout_fam", HELDOUT_FAM, 200)):
        for s in range(3):
            opp = ScenarioOpponent(params, seed=base + s)
            dag = None
            if dag_sink is not None:
                dag = EpisodeRecord(
                    game="pong", mode="evaluate_visual_only",
                    episode_id=f"{dag_sink['prefix']}_{fam}_{base + s}",
                    scenario=fam, field_table=FIELDS,
                    frame_shape=(60, 80),
                    note="student state, PongTeacherV2 relabel (RAM)")
            r = episode(env, agent, opp, 2400, 1,
                        dag=dag if dag_sink else None,
                        dag_teacher=dag_sink["teacher"] if dag_sink
                        else None)
            r["env"] = fam
            r["opp_seed"] = base + s
            rows.append(r)
            jr({"ev": "ep", "agent": name, **r})
            if dag is not None and len(dag.actions):
                meta_path = dag.freeze(DS_DAG)
                dag_sink["ids"].append(dag.episode_id)
    return rows


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="p4r1")
    ap.add_argument("--feat-art", default=os.path.join(
        OUT, "pong_student_feat_p4.npz"))
    ap.add_argument("--raw-art", default=os.path.join(
        OUT, "pong_student_raw_p4.npz"))
    ap.add_argument("--dagger-prefix", default="p4dag_r1")
    ap.add_argument("--agents", default="v1,v2,feat,raw",
                    help="comma subset of v1,v2,feat,raw")
    ap.add_argument("--dagger", default="1", choices=["0", "1"])
    a = ap.parse_args()

    os.makedirs(OUT, exist_ok=True)
    jr = make_jrn(OUT, f"[pongP4E:{a.tag}]")
    env = PongEnv()
    env.settle()
    report_path = os.path.join(OUT, f"pong_eval_{a.tag}.json")
    results = {}

    # DAgger sink shared by the student agents
    dag_sink = {"teacher": PongTeacherV2(), "ids": [],
                "prefix": a.dagger_prefix} if a.dagger == "1" else None

    want = set(a.agents.split(","))
    plan = [
        ("P1_teacher_v1", "inproc_v1", None),
        ("P4_teacher_v2", "inproc_v2", None),
        ("P4_student_feat", "brain", a.feat_art),
        ("P4_student_raw", "brain", a.raw_art),
    ]
    plan = [p for p in plan
            if p[0].split("_")[-1] in want
            or (p[0] == "P1_teacher_v1" and "v1" in want)
            or (p[0] == "P4_teacher_v2" and "v2" in want)]
    for name, kind, path in plan:
        if kind == "brain":
            agent = BrainClient(path)
            sink = dag_sink
        elif kind == "inproc_v1":
            agent = PongTeacherAgent()
            sink = None
        else:
            agent = V2TeacherAgentAdapter()
            sink = None
        results[name] = run_agent(env, name, agent, jr, dag_sink=sink)
        if kind == "brain":
            agent.close()
        with open(report_path, "w") as f:
            json.dump({"tag": a.tag, "results": results,
                       "dagger_ids": dag_sink["ids"] if dag_sink
                       else []}, f, indent=2)
        print(f"== {name} saved", flush=True)

    env.close()
    # compact table
    for name, rows in results.items():
        scored = sum(r["score_l"] for r in rows if r["env"] != "game_ai")
        conceded = sum(r["score_r"] for r in rows if r["env"] != "game_ai")
        gr = [r["returns"] for r in rows if r["env"] == "game_ai"]
        print(f"{name:16s} scored={scored} conceded={conceded} "
              f"gameAI_returns={gr}")


class V2TeacherAgentAdapter:
    """Adapter running PongTeacherV2 through the SAME episode() loop.
    RAM truth is pushed in per step (wants_ram_truth contract) — the
    assisted ceiling, disclosed; never claimed as a visual policy."""

    name = "pong_teacher_v2_predictive_edge"
    wants_ram_truth = True

    def __init__(self):
        self.t = PongTeacherV2()

    def reset_history(self):
        self.t.reset_history()

    def set_ram(self, ball_x, ball_y, pad_l):
        self.t.observe_ram(ball_x, ball_y)
        self._pad_l = pad_l

    def act(self, small):
        return self.t.act(getattr(self, "_pad_l", None))


if __name__ == "__main__":
    main()
