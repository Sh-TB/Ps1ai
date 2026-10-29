"""runner.py — episode loops wiring modes, envs, teachers, students.

THE BOUNDARY IN THE LOOPS:
  * assisted modes: the agent may read anything; every recorded value
    carries its role (observations.py).
  * visual-only modes: the agent object is a Brain (in-process, frame
    input only) or a BrainClient (SUBPROCESS pipe — the P4 default).
    The runner reads assisted labels ONLY for the episode record /
    evaluation (role evaluation_only) and passes NOTHING of them to the
    agent object. The brain's decision input is exactly one frame.
"""
import json
import os
import subprocess
import sys
import time

import numpy as np

from ps1play.learn import modes as M
from ps1play.learn.games import PongEnv  # noqa: F401 (re-export)
from ps1play.learn.perception import to_gray  # noqa: F401

LEARN_DIR = os.path.dirname(os.path.abspath(__file__))


class BrainClient:
    """Subprocess brain (P4): frames in, actions out. The child process
    imports only numpy + visual_only.py (asserted by tests + selfcheck)
    — inside it there is no emulator, no RAM, nothing to leak."""

    def __init__(self, artifact_path):
        # Run brain.py by FILE PATH (not -m): importing it as a package
        # module would load the ps1play package __init__ (which pulls
        # the emulator API chain) into the brain process. The file-path
        # child imports ONLY numpy + visual_only.py (selfcheck-asserted).
        self.proc = subprocess.Popen(
            [sys.executable, os.path.join(LEARN_DIR, "brain.py"),
             "--artifact", artifact_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        ready = self.proc.stdout.read(1)
        assert ready == b"B", ready

    @staticmethod
    def _write(buf, b):
        buf.write(b)
        buf.flush()

    def reset_history(self):
        self._write(self.proc.stdin, b"R")
        assert self.proc.stdout.read(1) == b"K"

    def act(self, rgb_small):
        raw = np.ascontiguousarray(rgb_small, dtype=np.uint8).tobytes()
        self._write(self.proc.stdin, b"F")
        self._write(self.proc.stdin,
                    np.asarray(len(raw), dtype="<u4").tobytes())
        self._write(self.proc.stdin, raw)
        hdr = self.proc.stdout.read(5)
        assert hdr[:1] == b"A", hdr
        n = int(np.frombuffer(hdr[1:], dtype="<u4")[0])
        return self.proc.stdout.read(n).decode()

    def close(self):
        try:
            self._write(self.proc.stdin, b"Q")
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


# ---------------------------------------------------------------- pong
def run_pong_episode(env, agent, mode, scenario, ram_anchors,
                     teacher=None, max_steps=6000, collector=None,
                     opponent_params=None, opponent_seed=0):
    """One pong episode from the 0-0 anchor.

    agent: object with .act(step_frame) -> UP/DOWN/NONE (teacher or
    brain). teacher: PongTeacher for DAgger relabeling (assisted only).
    Returns the episode outcome dict; the collector (if given) received
    every step.
    """
    from ps1play.learn.teacher import ScenarioOpponent
    env.load_anchor("pong_anchor")
    opp = ScenarioOpponent(opponent_params or {}, opponent_seed)
    step = 0
    prev_small = None
    score = [0, 0]
    outcome = {"result": "timeout", "player_score": 0, "opponent_score": 0}
    t0 = time.time()
    contact_windows = 0
    agent_buttons = set()
    last_agent = "NONE"
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    while step < max_steps:
        small = env.frame_small()
        # 1) THE AGENT DECIDES — visual-only agents get ONLY this frame.
        action = agent.act(small)
        agent_buttons = {"UP": {"UP"}, "DOWN": {"DOWN"},
                         "NONE": set()}.get(action, set())
        # 2) the scenario opponent (privileged, disclosed, pad2) — it is
        #    an environment component and ALWAYS acts
        labels = env.read_assisted(ram_anchors)
        opp.observe(labels.get("ball_y", 120.0), labels.get("paddle_r", 90.0))
        opp_buttons = opp.buttons()
        # 3) teacher relabel for the record (DAgger; assisted only)
        t_action = ""
        if teacher is not None:
            (cx, cy), prow = teacher.observe(env.frame())
            t_action = teacher.act((cx, cy), prow)
        # 4) advance the world
        env.run(2, agent_buttons, opp_buttons)
        step += 1
        # 5) record (labels are evaluation/teacher-side, never re-sent)
        labels = env.read_assisted(ram_anchors)
        if collector is not None:
            collector.add_frame(_small_gray(small))
            collector.add_step(
                action, teacher_action=t_action,
                labels={k: labels[k] for k in labels})
        contact_windows += _pong_contact(labels)
        score = [labels.get("score_l", score[0]),
                 labels.get("score_r", score[1])]
        last_agent = action
        if score[0] >= 5 or score[1] >= 5:
            outcome = {"result": "win" if score[0] >= 5 else "loss",
                       "player_score": score[0],
                       "opponent_score": score[1],
                       "contact_windows": contact_windows,
                       "agent_last": last_agent}
            break
    else:
        outcome = {"result": "timeout", "player_score": score[0],
                   "opponent_score": score[1],
                   "contact_windows": contact_windows}
    outcome.update({"steps": step, "mode": mode, "scenario": scenario,
                    "wall_s": round(time.time() - t0, 2),
                    "opponent": opponent_params or {}})
    if collector is not None:
        collector.set_outcome(**outcome)
    return outcome


def _pong_contact(labels):
    """Contact proxy: the ball within the left paddle column band."""
    bx = labels.get("ball_x")
    if bx is None:
        return 0
    return 1 if bx <= 24 else 0


# -------------------------------------------------------------- flappy
def run_flappy_episode(env, agent, mode, scenario_k, ram_anchors,
                       teacher=None, max_steps=9000, collector=None):
    """One flappy episode: restore ready anchor -> k idle -> X press
    (seeds RNG) -> control steps of 2 frames. FLAP edge semantics
    enforced by the runner (a FLAP step is followed by a release step)."""
    from ps1play.learn.perception import flappy_bird_y
    env.start_episode(scenario_k)
    step = 0
    prev_by = None
    last_was_flap = False
    flaps = 0
    pipes0 = None
    outcome = {"result": "timeout", "pipes": 0}
    t0 = time.time()
    if hasattr(agent, "reset_history"):
        agent.reset_history()
    while step < max_steps:
        small = env.frame_small()
        action = agent.act(small)
        # 1-frame decision cadence (r15 verbatim). The teacher carries
        # its own 2f-pulse + 3f-cooldown state machine, so B is held
        # exactly for the FLAP frames it emits; edge semantics = hold.
        if action == "FLAP":
            buttons = {"B"}
            flaps += 1
        else:
            buttons = set()
        last_was_flap = action == "FLAP"
        t_action = ""
        if teacher is not None:
            fr = env.frame()
            by, vy, gc = teacher.observe(fr, prev_by)
            t_action = teacher.act(by, vy or 0.0, gc)
            prev_by = by
        env.run(1, buttons)
        step += 1
        labels = env.read_assisted(ram_anchors)
        if pipes0 is None:
            pipes0 = labels.get("score", 0)
        if collector is not None:
            collector.add_frame(_small_gray(small))
            collector.add_step(
                action, teacher_action=t_action,
                labels={k: labels[k] for k in labels})
        if labels.get("dead", 0) or _flappy_dead(small):
            outcome = {"result": "death", "pipes": labels.get("score", 0),
                       "steps": step, "flaps": flaps}
            break
    else:
        labels = env.read_assisted(ram_anchors)
        outcome = {"result": "timeout", "pipes": labels.get("score", 0),
                   "steps": step, "flaps": flaps}
    outcome.update({"mode": mode, "scenario_k": scenario_k,
                    "wall_s": round(time.time() - t0, 2)})
    if collector is not None:
        collector.set_outcome(**outcome)
    return outcome


def _flappy_dead(small_rgb):
    """GAME OVER panel detection on the SMALL frame (band scaled /4):
    the beige-panel color test mirrored from FlappyEnv.game_over."""
    band = small_rgb[15:38, 22:58].astype(int)
    r, g, b = band[:, :, 0], band[:, :, 1], band[:, :, 2]
    beige = (r > 185) & (g > 175) & (b < 200) & (r > b + 20)
    return float(beige.mean()) > 0.35


def _small_gray(small_rgb):
    return small_rgb.mean(axis=2).astype(np.uint8)


def brain_selfcheck_ok(artifact_path):
    """Fresh-process audit: the brain process must NOT have ps1play
    loaded and must answer a synthetic frame."""
    c = BrainClient(artifact_path)
    try:
        a = c.act(np.zeros((60, 80, 3), dtype=np.uint8))
        return True, a
    finally:
        c.close()
