"""Boundary enforcement tests for the R53 learning foundation.

The mission's non-negotiable: the final inference decision path must be
unable to reach privileged state. These tests enforce it technically:

  1. AST scan  — visual_only.py imports ONLY numpy/stdlib and never
     references ram/core/memmap/savestate/host/provider symbols.
  2. Subprocess selfcheck — the brain process reports its loaded
     modules; ps1play (the emulator API chain) must be ABSENT.
  3. Frame-only schema — Brain.act accepts exactly one small RGB frame
     and returns a legal class name; no other input exists.
  4. No future leakage — the raw-mode decision on (t-1, t) equals a
     manual forward over the same stack (no t+1 can be involved).
  5. Fresh-process determinism — the same artifact + same frames give
     identical actions in two independent brain processes.
"""
import ast
import os
import subprocess
import sys

import numpy as np
import pytest

REPO = "/home/z/my-project/ps1ai"
LEARN = os.path.join(REPO, "ps1play", "learn")
VO_PATH = os.path.join(LEARN, "visual_only.py")

ALLOWED_IMPORTS = {"numpy", "json", "os", "sys", "math", "time"}
FORBIDDEN_NAMES = {"ram", "core", "memmap", "savestate", "host",
                   "provider", "teacher", "ps1play", "snapshot",
                   "retro_"}


def test_ast_imports_are_clean():
    tree = ast.parse(open(VO_PATH).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                root = a.name.split(".")[0]
                assert root in ALLOWED_IMPORTS, f"illegal import {a.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            assert root in ALLOWED_IMPORTS, f"illegal from-import {node.module}"
        elif isinstance(node, ast.Name):
            assert node.id not in FORBIDDEN_NAMES, f"forbidden name {node.id}"
        elif isinstance(node, ast.Attribute):
            assert node.attr not in FORBIDDEN_NAMES, \
                f"forbidden attribute {node.attr}"


def test_brain_subprocess_has_no_ps1play():
    r = subprocess.run(
        [sys.executable, os.path.join(LEARN, "brain.py"),
         "--artifact", os.path.join(REPO, "scratch", "r53learn",
                                    "pong_student_feat.npz"),
         "--selfcheck"],
        capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    import json
    info = json.loads(r.stdout.strip().splitlines()[-1])
    assert info["ps1play_loaded"] is False
    assert not any(m.startswith("ps1play") for m in info["modules"])


def _mk_pong_artifact(tmp_path):
    """A tiny valid pong artifact built WITHOUT any game/RAM access."""
    sys.path.insert(0, REPO)
    from ps1play.learn.policy import TinyMLP
    net = TinyMLP(6, 8, 3, seed=3)
    meta = {"game": "pong", "control_mode": "cv+mlp",
            "classes": ["DOWN", "NONE", "UP"],
            "norm": {"mean": [0] * 6, "std": [1] * 6},
            "arch": {"n_in": 6, "hidden": 8, "n_out": 3}}
    return net.save_artifact(os.path.join(tmp_path, "t.npz"), meta)


def test_brain_frame_only_schema_and_determinism(tmp_path):
    info = _mk_pong_artifact(str(tmp_path))
    sys.path.insert(0, LEARN)
    from visual_only import Brain
    b = Brain(info["npz"])
    fr = np.zeros((60, 80, 3), dtype=np.uint8)
    a1 = b.act(fr)
    assert a1 in {"DOWN", "NONE", "UP"}
    # determinism: identical frame -> identical action
    assert b.act(fr) == a1
    # fresh-process determinism via the subprocess brain
    from ps1play.learn.runner import BrainClient
    c1 = BrainClient(info["npz"])
    c2 = BrainClient(info["npz"])
    seq = [np.full((60, 80, 3), v, dtype=np.uint8) for v in (0, 40, 90)]
    r1 = [c1.act(f) for f in seq]
    r2 = [c2.act(f) for f in seq]
    c1.close()
    c2.close()
    assert r1 == r2


def test_no_future_frame_leakage(tmp_path):
    """The raw-mode decision must be a function of [t-1, t] ONLY:
    replaying the same two frames in the same order reproduces the
    manual forward over that stack — a t+1 frame cannot be involved
    because none is ever sent."""
    from ps1play.learn.policy import TinyMLP
    net = TinyMLP(2 * 60 * 80, 8, 2, seed=5)
    meta = {"game": "flappy", "control_mode": "raw+mlp",
            "classes": ["HOVER", "FLAP"],
            "norm": {}, "arch": {"n_in": 2 * 60 * 80, "hidden": 8,
                                 "n_out": 2}}
    info = net.save_artifact(os.path.join(tmp_path, "raw.npz"), meta)
    sys.path.insert(0, LEARN)
    from visual_only import Brain, _as_gray
    b = Brain(info["npz"])
    f1 = np.zeros((60, 80, 3), np.uint8)
    f2 = np.full((60, 80, 3), 200, np.uint8)
    b.act(f1)
    got = b.act(f2)
    x = np.concatenate([_as_gray(f1).ravel(),
                        _as_gray(f2).ravel()]).astype(np.float32) / 255.0
    out = net.predict(x.reshape(1, -1))[0]
    want = ["HOVER", "FLAP"][int(np.argmax(out))]
    assert got == want


def test_brain_needs_no_dataset(tmp_path):
    """The artifact loads and decides in a directory containing NOTHING
    else (no dataset, no manifest)."""
    info = _mk_pong_artifact(str(tmp_path))
    sys.path.insert(0, LEARN)
    from visual_only import Brain
    b = Brain(info["npz"])
    assert b.act(np.zeros((60, 80, 3), np.uint8)) in \
        {"DOWN", "NONE", "UP"}


def test_policy_artifact_size_cap():
    """The deployed artifacts must stay <= 4 MiB (mission §10)."""
    for name in ("pong_student_feat_p3.npz", "flappy_student_feat.npz",
                 "flappy_student_raw.npz"):
        p = os.path.join(REPO, "scratch", "r53learn", name)
        if os.path.exists(p):
            assert os.path.getsize(p) <= 4 * 1024 * 1024, name
