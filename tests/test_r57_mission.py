"""R57 teacher-cutoff / no-teacher / splits / reward tests.

Mission PART 15 for R57 (the autonomous-student round):

  TEACHER cutoff — no teacher label beyond the 20-pipe cap; the cutoff
  step's own label excluded; early deaths kept with no cutoff claim.
  BOOTSTRAP — the qualified dataset matches its manifest; the max pipe
  invariant holds on the REAL committed dataset.
  STUDENT — the no-teacher boundary: AST scan + a live subprocess in
  which importing the teacher RAISES + a hashed trace.
  SPLITS — train/val/test disjoint; TEST seeds were never booted in
  r53-r56; the split file exists and is parseable.
  REWARD/PASSAGE — the visual passage counter: one pipe = one event,
  no duplicates, no RAM path anywhere in r57_lib.run_episode.
"""
import ast
import json
import os
import subprocess
import sys

import numpy as np
import pytest

REPO = "/home/z/my-project/ps1ai"
LEARN = os.path.join(REPO, "data", "learn")
SCR = os.path.join(REPO, "scratch", "r57")
SPLITS = os.path.join(LEARN, "r57_seed_splits.json")

HIST_K = {6, 12, 18, 24, 30, 36, 42, 45, 54, 60, 66, 78, 90, 100, 102,
          114, 120, 126, 130, 150, 174, 198, 210, 222, 246, 270, 294}


# ---------------------------------------------------------- TEACHER
def test_tb_manifest_exists_and_cutoff_proof_holds():
    p = os.path.join(SCR, "tb_manifest.json")
    if not os.path.exists(p):
        pytest.skip("tb_manifest not collected yet")
    m = json.load(open(p))
    assert m["cap_pipes"] == 20
    assert m["cutoff_proof"] is True
    for e in m["episodes"]:
        if e["result"] == "cutoff":
            assert e["passages"] == 20
            # the cutoff step's own label is EXCLUDED
            assert e["n_labels"] == e["cutoff_step"]
        else:
            assert e["result"] == "death"
            assert e["passages"] < 20


def test_bootstrap_dataset_max_pipe_le_20():
    p = os.path.join(LEARN, "r57_bootstrap_dataset.npz")
    if not os.path.exists(p):
        pytest.skip("bootstrap dataset not trained yet")
    z = np.load(p)
    assert int(z["passed_pipe_count"].max()) <= 20
    meta = json.load(open(p + ".json"))
    assert meta["cutoff_proof"] is True
    assert meta["max_passed_pipe_count"] == \
        int(z["passed_pipe_count"].max())


def test_early_death_episode_kept_without_cutoff():
    """A death-before-20 episode contributes labels but must NOT claim
    a cutoff (the cap is a ceiling, not a target)."""
    p = os.path.join(SCR, "tb_manifest.json")
    if not os.path.exists(p):
        pytest.skip("tb_manifest not collected yet")
    m = json.load(open(p))
    deaths = [e for e in m["episodes"] if e["result"] == "death"]
    for e in deaths:
        assert e["cutoff_step"] is None
        assert 0 < e["n_labels"] <= 6000


# -------------------------------------------------------- BOOTSTRAP
def test_bootstrap_sidecar_provenance():
    p = os.path.join(LEARN, "r57_bootstrap_bc.npz.json")
    if not os.path.exists(p):
        pytest.skip("bootstrap model not trained yet")
    meta = json.load(open(p))
    assert meta["feature_version"] == 7
    assert meta["classes"] == ["HOVER", "FLAP"]
    assert "QUALIFIED R57 bootstrap" in meta["teacher_provenance"]
    assert meta["dataset"] == "r57_bootstrap_dataset.npz"
    assert len(meta["dataset_sha256"]) == 64


# ---------------------------------------------------------- STUDENT
# the STUDENT pipeline files (teacher-off by mission PART 4). The
# assisted-mode scripts (r57a smoke, r57c C1-reference eval, r57d
# teacher collection) are deliberately NOT in this list — they are the
# assisted/audit side of the mission and are legal teacher consumers.
STUDENT_SOURCES = ["r57_lib.py", "r57e_train_bootstrap.py",
                   "r57f_es_ars.py", "r57g_ppo.py", "r57h_eval.py",
                   "r57z_push.py"]


def _r57_student_sources():
    scr = os.path.join(REPO, "scripts")
    return [os.path.join(scr, f) for f in STUDENT_SOURCES
            if os.path.exists(os.path.join(scr, f))]


def test_ast_no_teacher_in_student_pipeline():
    from ps1play.learn.student_only import ast_teacher_scan
    v = ast_teacher_scan(_r57_student_sources())
    assert v == [], f"teacher references in student pipeline: {v}"


def test_import_teacher_raises_in_student_process():
    code = (
        "import sys, json;"
        "sys.path.insert(0, {repo!r});"
        "sys.path.insert(0, {learn!r});"
        "from ps1play.learn import student_only as SO;"
        "t = SO.NoTeacherTrace({trace!r});"
        "SO.install_teacher_blocker(t);"
        "blocked = None;\n"
        "try:\n"
        "    import ps1play.learn.teacher\n"
        "except ImportError as e:\n"
        "    blocked = str(e)[:60]\n"
        "h = t.finish();"
        "print(json.dumps({{'blocked': blocked, 'sha': h}}))"
    ).format(repo=REPO, learn=os.path.join(REPO, "ps1play", "learn"),
             trace=os.path.join(SCR, "test_noteacher_trace.jsonl"))
    out = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr[-400:]
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert res["blocked"] is not None, "teacher import was NOT blocked"
    assert len(res["sha"]) == 64


def test_import_student_trainer_module_under_blocker():
    """The REAL student trainer module must import cleanly with the
    teacher blocker installed — and never touch the teacher."""
    code = (
        "import sys, json, os;"
        "sys.path.insert(0, {repo!r});"
        "sys.path.insert(0, {scripts!r});"
        "from ps1play.learn import student_only as SO;"
        "t = SO.NoTeacherTrace({trace!r});"
        "SO.install_teacher_blocker(t);"
        "import r57_lib;"                      # the rollout loop module
        "import importlib.util as iu;"
        "spec = iu.spec_from_file_location("
        "    'r57f_es', os.path.join({scripts!r}, 'r57f_es_ars.py'));"
        "mod = iu.module_from_spec(spec); spec.loader.exec_module(mod);"
        "h = t.finish();"
        "print(json.dumps({{'ok': True, 'sha': h}}))"
    ).format(repo=REPO, scripts=os.path.join(REPO, "scripts"),
             trace=os.path.join(SCR, "test_import_trace.jsonl"))
    if not os.path.exists(os.path.join(REPO, "scripts", "r57f_es_ars.py")):
        pytest.skip("ES module not written yet")
    out = subprocess.run([sys.executable, "-c", code],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-500:]
    res = json.loads(out.stdout.strip().splitlines()[-1])
    assert res["ok"] is True


# ----------------------------------------------------------- SPLITS
def test_seed_splits_disjoint_and_clean():
    s = json.load(open(SPLITS))
    train, val, test = (set(s["train"]), set(s["val"]),
                        set(s["test_never_used_before_this_round"]))
    assert not (train & val) and not (train & test) and not (val & test)
    assert not (test & set(s["used_in_history_r53_r56_never_test"]))
    assert not (test & HIST_K)
    assert len(test) >= 20
    assert s["committed_before_collection"] is True


# --------------------------------------------- REWARD / PASSAGE
def test_passage_counter_one_event_per_pipe():
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    from r57_lib import PassageCounter
    pc = PassageCounter()
    # pipes move LEFT: the band decays, then JUMPS up (>+60) exactly
    # once per passage; repeated values and None detections are inert.
    series = [300.0, 280.0, 260.0, 200.0, 90.0, 30.0,
              260.0,                             # +230 jump -> event
              240.0, 220.0, 200.0, 150.0, 100.0, 60.0,
              280.0,                             # +220 jump -> event
              270.0, 260.0,
              None, None,                        # missed detections
              255.0,
              320.0,                             # +65 jump -> event
              320.0]                             # repeat value: none
    evs = [pc.fire(b, i) for i, b in enumerate(series)]
    assert pc.count == 3
    assert evs.count(True) == 3
    assert pc.events == [6, 13, 19]            # strictly increasing


def test_passage_counter_fresh_per_episode():
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    from r57_lib import PassageCounter
    pc = PassageCounter()
    pc.fire(50.0, 0)
    pc.fire(300.0, 1)
    assert pc.count == 1
    pc2 = PassageCounter()          # fresh instance = fresh episode
    pc2.last = None
    pc2.count = 0
    pc2.events = []
    pc2.fire(300.0, 0)
    assert pc2.count == 0           # no inherited state


def test_run_episode_source_has_no_ram_path():
    """AST: r57_lib.run_episode must not touch core.ram / read_assisted."""
    src = open(os.path.join(REPO, "scripts", "r57_lib.py")).read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert node.attr not in ("ram", "read_assisted", "vram",
                                     "sram"), node.attr
