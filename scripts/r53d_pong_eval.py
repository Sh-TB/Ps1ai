#!/usr/bin/env python3
"""r53d_pong_eval.py — Stage D/E: closed-loop visual-only evaluation.

Agents on the SAME protocol (fresh anchors, first-to-5 or step budget):
  P1 teacher   — PongTeacher (visual, in-process) [baseline]
  P2 student-f — Brain(pong_student_feat.npz) via SUBPROCESS pipe
  P2 student-r — Brain(pong_student_raw.npz)  via SUBPROCESS pipe

Environments (both disclosed):
  A) game AI (pad2 disconnected) — the AI is unbeatable by design
     (speed parity with the vel_y cap) -> honest metric = rally
     survival (steps survived, points conceded). Wins impossible.
  B) scenario opponent (port-1 scripted, aim_err 14 / delay 10 = the
     TRAIN family; aim_err 22 / delay 16 = HELD-OUT family) —
     beatable -> wins/losses meaningful.

Also collects the DAgger round: student-controlled steps relabeled by
the teacher (visual) -> scratch/r53learn/ds_pong_dagger/.
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
from ps1play.learn.perception import pong_ball_centroid     # noqa: E402
from ps1play.learn.teacher import PongTeacher, ScenarioOpponent  # noqa
from ps1play.learn.runner import BrainClient                # noqa: E402
from ps1play.learn.dataset import EpisodeRecord             # noqa: E402
from ps1play.learn.perception import to_gray                # noqa: E402
from hellopong_r12_lib import make_jrn                      # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")
DS_DAG = os.path.join(OUT, "ds_pong_dagger")
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
    {"name": "score_l", "role": "evaluation_only", "source": "ram:0x1FFEB4"},
    {"name": "score_r", "role": "evaluation_only", "source": "ram:0x1FFEBC"},
]


def i32(ram, a):
    return int(np.frombuffer(ram[a:a + 4].tobytes(), "<i4")[0])


def episode(env, agent, mode, opponent, max_steps=1800, teacher=None,
            dag_collector=None, port1_device=0):
    """One episode; agent = PongTeacher | BrainClient | in-proc Brain.
    opponent: None (game AI) | ScenarioOpponent instance.
    ORDER MATTERS: the anchor was saved with port1=NONE — the core's
    port-1 device must MATCH that config during unserialize (beetle
    refuses a device-class change across restore); the desired device
    is applied AFTER the restore."""
    env.p.core.set_port_device(0, port=1)
    env.load_anchor("pong_anchor")
    env.p.core.set_port_device(port1_device, port=1)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    contacts = 0
    returns = 0
    conceded = 0
    scored = 0
    prev_bx = None
    in_contact = False
    steps = 0
    t0 = time.time()
    disagree = 0
    teacher_n = 0
    for step in range(max_steps):
        small = env.frame_small()
        action = agent.act(small)
        buttons = {"UP": {"UP"}, "DOWN": {"DOWN"},
                   "NONE": set()}.get(action, set())
        _, ram = env.frame(), env.p.core.ram.copy()
        if opponent is not None:
            opponent.observe(i32(ram, BALL_Y), i32(ram, PAD_R))
            opp_buttons = opponent.buttons()
        else:
            opp_buttons = set()
        # teacher relabel (DAgger) — visual, recorded, never re-sent
        t_act = ""
        if teacher is not None and dag_collector is not None:
            fr = env.frame()
            (cx, cy), prow = teacher.observe(fr)
            t_act = teacher.act((cx, cy), prow)
            teacher_n += 1
            if t_act != action:
                disagree += 1
            dag_collector.add_frame(to_gray(fr))
            dag_collector.add_step(action, teacher_action=t_act,
                                   labels={"ball_x": i32(ram, BALL_X),
                                           "ball_y": i32(ram, BALL_Y),
                                           "pad_l": i32(ram, PAD_L),
                                           "pad_r": i32(ram, PAD_R),
                                           "score_l": i32(ram, SCORE_L),
                                           "score_r": i32(ram, SCORE_R)})
        env.run(2, buttons, opp_buttons)
        steps += 1
        _, ram = env.frame(), env.p.core.ram.copy()
        bx = i32(ram, BALL_X)
        if prev_bx is not None:
            if bx < 30:
                in_contact = True
            elif in_contact and bx > 45:
                contacts += 1
                returns += 1
                in_contact = False
            elif bx > 100:
                in_contact = False
        prev_bx = bx
        sl, sr = i32(ram, SCORE_L), i32(ram, SCORE_R)
        if (sl, sr) != (scored, conceded):
            scored, conceded = sl, sr
        if sl >= 5 or sr >= 5:
            break
    result = ("win" if sl >= 5 else "loss" if sr >= 5 else "rally")
    return {"result": result, "steps": steps, "score_l": sl,
            "score_r": sr, "contacts": contacts, "returns": returns,
            "wall_s": round(time.time() - t0, 2),
            "disagree_rate": round(disagree / teacher_n, 3)
            if teacher_n else None}


def main():
    jr = make_jrn(OUT, "[pongE]")
    env = PongEnv()
    from ps1play.learn.teacher import PongTeacherAgent
    teacher_agent = PongTeacherAgent()

    agents = {
        "P1_teacher": ("inproc", teacher_agent),
        "P2_student_feat": ("brain", os.path.join(
            OUT, "pong_student_feat.npz")),
        "P2_student_raw": ("brain", os.path.join(
            OUT, "pong_student_raw.npz")),
    }
    results = {}
    dag = None
    dag_open = False
    for name, (kind, agent_or_path) in agents.items():
        if kind == "brain":
            agent = BrainClient(agent_or_path)
        else:
            agent = agent_or_path
        rows = []
        for ep in range(2):
            r = episode(env, agent, "evaluate_visual_only", None,
                        max_steps=1500, port1_device=0)  # game AI
            r["env"] = "game_ai"
            rows.append(r)
            jr({"ev": "ep", "agent": name, **r})
        for fam, params in (("train_fam", {"aim_err": 14.0, "delay": 10,
                                           "deadband": 8.0}),
                            ("heldout_fam", {"aim_err": 22.0, "delay": 16,
                                             "deadband": 8.0})):
            for ep in range(2):
                opp = ScenarioOpponent(params, seed=100 + ep)
                dag = (EpisodeRecord(
                    game="pong", mode="evaluate_visual_only",
                    episode_id=f"dag_{name}_{fam}_{ep}",
                    scenario=fam, field_table=FIELDS,
                    frame_shape=(60, 80),
                    note="student-controlled, teacher relabels")
                    if (kind == "brain" and not dag_open) else dag)
                r = episode(env, agent, "evaluate_visual_only", opp,
                            max_steps=1800, port1_device=1,
                            teacher=(PongTeacher(deadband=10.0)
                                     if kind == "brain" else None),
                            dag_collector=dag if kind == "brain" else None)
                r["env"] = fam
                rows.append(r)
                jr({"ev": "ep", "agent": name, **r})
        if kind == "brain":
            dag_open = True
            agent.close()
        results[name] = rows

    # freeze the DAgger record
    if dag is not None and len(dag.actions):
        dag.set_outcome(note="pooled student steps for the P3 round")
        meta_path = dag.freeze(DS_DAG)
        with open(meta_path) as f:
            meta = json.load(f)
        jr({"ev": "dagger_frozen", "steps": meta["n_steps"],
            "path": meta_path})

    with open(os.path.join(OUT, "pong_eval_p2.json"), "w") as f:
        json.dump(results, f, indent=2)
    env.close()
    # compact summary
    for name, rows in results.items():
        for r in rows:
            print(f"{name:18s} {r['env']:12s} {r['result']:6s} "
                  f"l={r['score_l']} r={r['score_r']} "
                  f"contacts={r['contacts']} returns={r['returns']} "
                  f"steps={r['steps']}")


if __name__ == "__main__":
    main()
