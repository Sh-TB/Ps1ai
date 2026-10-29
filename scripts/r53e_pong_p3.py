#!/usr/bin/env python3
"""r53e_pong_p3.py — the P3 round: DAgger collection (short) + class-
weighted retrain + compact re-evaluation. Incremental saves after every
agent so partial evidence survives a timeout."""
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
from ps1play.learn.teacher import (PongTeacher, PongTeacherAgent,  # noqa
                                   ScenarioOpponent)
from ps1play.learn.runner import BrainClient                # noqa: E402
from ps1play.learn.dataset import EpisodeRecord             # noqa: E402
from ps1play.learn.policy import TinyMLP                    # noqa: E402
from ps1play.learn import visual_only as VO                 # noqa: E402
from hellopong_r12_lib import make_jrn                      # noqa: E402

OUT = os.path.join(REPO, "scratch", "r53learn")
DS = os.path.join(OUT, "ds_pong")
DS_DAG = os.path.join(OUT, "ds_pong_dagger")
CLASSES = ["DOWN", "NONE", "UP"]
BALL_X, BALL_Y = 0x1FFEA0, 0x1FFEA4
PAD_L, SCORE_L = 0x1FFEB0, 0x1FFEB4
PAD_R, SCORE_R = 0x1FFEB8, 0x1FFEBC


def i32(ram, a):
    return int(np.frombuffer(ram[a:a + 4].tobytes(), "<i4")[0])


def episode(env, agent, opponent, max_steps, teacher=None,
            dag=None, port1_device=1):
    env.p.core.set_port_device(0, port=1)
    env.load_anchor("pong_anchor")
    env.p.core.set_port_device(port1_device, port=1)
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    contacts = returns = 0
    in_contact = False
    steps = 0
    t0 = time.time()
    disagree = teacher_n = 0
    for _ in range(max_steps):
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
        if teacher is not None and dag is not None:
            fr = env.frame()
            (cx, cy), prow = teacher.observe(fr)
            t_act = teacher.act((cx, cy), prow)
            teacher_n += 1
            disagree += (t_act != action)
            dag.add_frame(to_gray(fr))
            dag.add_step(action, teacher_action=t_act,
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
    return {"result": "win" if sl >= 5 else "loss" if sr >= 5
            else "rally", "steps": steps, "score_l": sl, "score_r": sr,
            "contacts": contacts, "returns": returns,
            "wall_s": round(time.time() - t0, 2),
            "disagree_rate": round(disagree / teacher_n, 3)
            if teacher_n else None}


def dag_relabel_episode(env, agent, params, ep_id, steps=700):
    opp = ScenarioOpponent(params, seed=200 + ep_id)
    dag = EpisodeRecord(
        game="pong", mode="evaluate_visual_only",
        episode_id=f"p3dag_{ep_id}", scenario="p3_dagger",
        field_table=[{"name": k, "role": "teacher_label",
                      "source": "ram"} for k in
                     ("ball_x", "ball_y", "pad_l", "pad_r")] +
        [{"name": "frame_small_gray", "role": "visual_input",
          "source": "frame_rgb"}],
        frame_shape=(60, 80), note="P3 DAgger: student states, "
        "teacher relabels")
    r = episode(env, agent, opp, steps, teacher=PongTeacher(deadband=10.0),
                dag=dag)
    dag.set_outcome(**r)
    meta_path = dag.freeze(DS_DAG)
    with open(meta_path) as f:
        meta = json.load(f)
    return r, meta["n_steps"]


def train_model(which, hidden, epochs, lr):
    """Retrain on ds_pong + all p3dag_* records with class weights."""
    Xf, Xr, Y, W = [], [], [], []
    # teacher set
    import glob
    recs = [("ds_pong", eid) for eid in
            [f"t{i:03d}" for i in range(8)]]
    for root_name, eid in recs:
        root = os.path.join(OUT, root_name)
        try:
            meta, npz = EpisodeRecord.load(root, eid)
        except FileNotFoundError:
            continue
        frames = npz["frames"]
        acts = [str(a) for a in npz["actions"]]
        labels = json.loads(str(npz["labels_json"]))
        for i in range(meta["n_steps"]):
            cur = frames[i]
            prev = frames[i - 1] if i > 0 else np.zeros_like(cur)
            Xf.append(VO.features_pong(cur, prev))
            Xr.append(np.concatenate([prev.ravel(), cur.ravel()])
                      .astype(np.float32) / 255.0)
            Y.append(CLASSES.index(acts[i]))
            W.append(2.0 if i32_like(labels[i]["ball_x"]) else 1.0)
    # dagger set (student states, teacher relabels as targets)
    for path in sorted(glob.glob(os.path.join(DS_DAG, "p3dag_*.json"))):
        eid = os.path.basename(path)[4:-5]
        meta, npz = EpisodeRecord.load(DS_DAG, eid)
        frames = npz["frames"]
        acts = [str(a) for a in npz["teacher_actions"]]
        labels = json.loads(str(npz["labels_json"]))
        for i in range(meta["n_steps"]):
            if not acts[i]:
                continue
            cur = frames[i]
            prev = frames[i - 1] if i > 0 else np.zeros_like(cur)
            Xf.append(VO.features_pong(cur, prev))
            Xr.append(np.concatenate([prev.ravel(), cur.ravel()])
                      .astype(np.float32) / 255.0)
            Y.append(CLASSES.index(acts[i]))
            W.append(3.0 if i32_like(labels[i]["ball_x"]) else 1.5)
    Xf, Xr, Y, W = (np.asarray(Xf, np.float32), np.asarray(Xr, np.float32),
                    np.asarray(Y), np.asarray(W, np.float32))
    counts = np.bincount(Y, minlength=3)
    cw = (counts.sum() / (3.0 * np.maximum(counts, 1))) ** 0.5
    cw = np.clip(cw, 0.5, 6.0).astype(np.float32)
    X, n_in = ((Xf, Xf.shape[1]) if which == "feat"
               else (Xr, Xr.shape[1]))
    mu, sd = X.mean(0), X.std(0) + 1e-6
    net = TinyMLP(n_in, hidden, 3, seed=7)
    net.fit((X - mu) / sd, np.eye(3, dtype=np.float32)[Y], epochs=epochs,
            batch=128, lr=lr, classification=True, seed=7,
            class_weights=cw, sample_weights=W)
    acc = float((net.predict((X - mu) / sd).argmax(1) == Y).mean())
    art = os.path.join(OUT, f"pong_student_{which}_p3.npz")
    info = net.save_artifact(art, meta={
        "game": "pong",
        "control_mode": "cv+mlp" if which == "feat" else "raw+mlp",
        "classes": CLASSES,
        "norm": {"mean": mu.tolist(), "std": sd.tolist()},
        "dataset": {"roots": [DS, DS_DAG], "n_steps": int(len(Y)),
                    "class_weights": cw.tolist(),
                    "note": "P3: teacher data + DAgger relabels"},
        "trained_at": time.time(),
        "train_acc_weighted_round": round(acc, 4)})
    return info, acc


def i32_like(bx):
    try:
        return float(bx) < 170
    except (TypeError, ValueError):
        return False


def main():
    jr = make_jrn(OUT, "[pongP3]")
    env = PongEnv()
    out = {}

    # 1) short DAgger with the CURRENT P2 feat student
    c = BrainClient(os.path.join(OUT, "pong_student_feat.npz"))
    dag_steps = 0
    for ep in range(2):
        r, n = dag_relabel_episode(
            env, c, {"aim_err": 14.0, "delay": 10, "deadband": 8.0},
            ep, steps=700)
        dag_steps += n
        jr({"ev": "p3_dag", "ep": ep, **r})
    c.close()
    out["dag_steps"] = dag_steps

    # 2) retrain P3 models
    for which, hidden, epochs, lr in (("feat", 24, 50, 3e-3),
                                      ("raw", 48, 14, 1e-3)):
        info, acc = train_model(which, hidden, epochs, lr)
        out[f"p3_{which}"] = {"artifact": info, "train_acc": acc}
        jr({"ev": "p3_trained", "which": which, "acc": acc,
            "bytes": info["npz_bytes"]})

    # 3) compact re-eval: teacher vs P3 students
    teacher_agent = PongTeacherAgent()
    plan = [
        ("P1_teacher", "inproc", None),
        ("P3_student_feat", "brain", os.path.join(
            OUT, "pong_student_feat_p3.npz")),
        ("P3_student_raw", "brain", os.path.join(
            OUT, "pong_student_raw_p3.npz")),
    ]
    results = {}
    for name, kind, path in plan:
        agent = BrainClient(path) if kind == "brain" else teacher_agent
        rows = []
        for ep in range(2):
            r = episode(env, agent, None, 1200, port1_device=0)
            r["env"] = "game_ai"
            rows.append(r)
            jr({"ev": "p3_ep", "agent": name, **r})
        for fam, params in (("train_fam", {"aim_err": 14.0, "delay": 10,
                                           "deadband": 8.0}),
                            ("heldout_fam", {"aim_err": 22.0, "delay": 16,
                                             "deadband": 8.0})):
            r = episode(env, agent, ScenarioOpponent(params, seed=300),
                        1400, port1_device=1)
            r["env"] = fam
            rows.append(r)
            jr({"ev": "p3_ep", "agent": name, **r})
        if kind == "brain":
            agent.close()
        results[name] = rows
        with open(os.path.join(OUT, "pong_eval_p3.json"), "w") as f:
            json.dump({"round": out, "results": results}, f, indent=2)
    env.close()
    print(json.dumps({"round": out, "results": results}, indent=2))


if __name__ == "__main__":
    main()
