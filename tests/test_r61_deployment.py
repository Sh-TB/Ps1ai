"""R61 deployment-package tests — the independent consumer, its input
contract, its failure handling, and its isolation from the training
implementation.

Layout:
  - test_r61_package_isolation   the package imports NOTHING training-
                                 related (AST scan + fresh-subprocess
                                 import with ps1play unreachable)
  - test_r61_schema_*            the enforced input contract (shape,
                                 dtype, finiteness, ranges, sentinels)
  - test_r61_lifecycle_*         init / reset / close / context manager
  - test_r61_manifest_*          hash binding, corrupt model, missing
                                 files, wrong manifests, no-ort fallback
  - test_r61_determinism_*       repeat + instance + batch/single agree
  - test_r61_loop_faults_*       closed-loop runner fault injection
  - test_r61_emulator_smoke      REAL emulator: a short closed-loop
                                 episode through the package (skipped
                                 when the emulator assets are absent)
"""
import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pytest

REPO = "/home/z/my-project/ps1ai"
PKG = os.path.join(REPO, "deployment", "flappybird_policy")
MODELS = os.path.join(PKG, "models")

for _p in (REPO, os.path.join(REPO, "scripts"), PKG):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flappybird_policy import (  # noqa: E402
    FlappyBirdPolicy,
    InputValidationError,
    ManifestError,
    ModelLoadError,
    PolicyError,
    load_policy,
)
from flappybird_policy.schema import (  # noqa: E402
    FEATURE_NAMES,
    N_FEATURES,
    VALID_RANGES,
)


def _vec(**over):
    """A legal in-range observation with per-feature overrides."""
    v = [97.9, -2.0, 98.5, 32.7, 66.5, 130.5, 0.0, 12.0, 98.8, 8.0]
    v = [float(x) for x in v]
    for k, val in over.items():
        v[FEATURE_NAMES.index(k)] = float(val)
    return np.asarray(v, dtype=np.float32)


@pytest.fixture(scope="module")
def policy():
    p = load_policy()
    yield p
    p.close()


# ------------------------------------------------------------------
# isolation from the training implementation
# ------------------------------------------------------------------
FORBIDDEN_IMPORT_TOKENS = (
    "ps1play", "teacher", "r57", "r58", "r59", "r60", "r61",
    "games", "visual_only", "brain", "student_only", "replay",
)


def test_r61_package_isolation_ast():
    """No package module may import the training implementation, any
    teacher concept, or anything outside {stdlib, numpy, onnxruntime}."""
    core = os.path.join(PKG, "flappybird_policy")
    files = [os.path.join(core, f) for f in os.listdir(core)
             if f.endswith(".py")]
    assert files, "package modules missing"
    for path in files:
        tree = ast.parse(open(path).read())
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            for m in mods:
                for tok in FORBIDDEN_IMPORT_TOKENS:
                    assert tok not in m.lower(), (path, m, tok)


def test_r61_package_isolation_fresh_subprocess():
    """In a subprocess where ps1play is UNREACHABLE and sys.path holds
    only the package + stdlib, load_policy must work and produce a
    legal action."""
    code = (
        "import sys, json, numpy as np\n"
        f"sys.path.insert(0, {PKG!r})\n"
        "sys.path = [p for p in sys.path if 'ps1ai' not in p or "
        "'deployment' in p]\n"
        "import flappybird_policy as fb\n"
        "assert 'ps1play' not in sys.modules, 'training leaked'\n"
        "p = fb.load_policy()\n"
        "v = np.zeros(10, dtype=np.float32)\n"
        "v[0] = 97.9\n"
        "a = p.predict(v)\n"
        "assert a in ('HOVER', 'FLAP'), a\n"
        "assert 'ps1play' not in sys.modules, 'training leaked late'\n"
        "print(json.dumps({'action': a, 'sha': p.model_sha256[:16]}))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, timeout=180, cwd=tempfile.gettempdir())
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["sha"] == "4dd592a7118a5c4de7b44166b42b8d09"[:16]


# ------------------------------------------------------------------
# the enforced input contract
# ------------------------------------------------------------------
def test_r61_schema_wrong_feature_count(policy):
    with pytest.raises(InputValidationError, match="shape"):
        policy.predict(np.zeros(9, dtype=np.float32))
    with pytest.raises(InputValidationError, match="shape"):
        policy.predict(np.zeros(11, dtype=np.float32))
    with pytest.raises(InputValidationError):
        policy.predict_batch(np.zeros((3, 9), dtype=np.float32))


def test_r61_schema_nan_inf(policy):
    for bad in (np.nan, np.inf, -np.inf):
        v = _vec()
        v[0] = bad
        with pytest.raises(InputValidationError, match="non-finite"):
            policy.predict(v)
        b = np.repeat(_vec().reshape(1, -1), 2, axis=0)
        b[1, 5] = bad
        with pytest.raises(InputValidationError, match="non-finite"):
            policy.predict_batch(b)


def test_r61_schema_wrong_dtype(policy):
    with pytest.raises(InputValidationError, match="dtype"):
        policy.predict(_vec().astype(np.float64))
    with pytest.raises(InputValidationError, match="dtype"):
        policy.predict(_vec().astype(np.int64))
    with pytest.raises(InputValidationError, match="numpy.ndarray"):
        policy.predict([97.9, 0, 98.5, 32.7, 66.5, 130.5, 0, 12,
                        98.8, 8])


def test_r61_schema_wrong_shape(policy):
    with pytest.raises(InputValidationError, match="shape"):
        policy.predict(_vec().reshape(2, 5))
    with pytest.raises(InputValidationError, match="shape"):
        policy.predict_batch(_vec())  # single passed where batch due


def test_r61_schema_out_of_range_every_feature(policy):
    for j, name in enumerate(FEATURE_NAMES):
        lo, hi = VALID_RANGES[j]
        for bad in (lo - 1.0, hi + 1.0):
            if bad < -160 and name != "dx":
                continue  # skip only where the sentinel floor is -1
            v = _vec()
            v[j] = np.float32(bad)
            with pytest.raises(InputValidationError,
                               match=name):
                policy.predict(v)


def test_r61_schema_boundary_values_legal(policy):
    """Every documented range ENDPOINT is a legal observation and
    produces a deterministic legal action."""
    for j, name in enumerate(FEATURE_NAMES):
        lo, hi = VALID_RANGES[j]
        for edge in (lo, hi):
            v = _vec()
            v[j] = np.float32(edge)
            a1 = policy.predict(v)
            a2 = policy.predict(v)
            assert a1 in ("HOVER", "FLAP")
            assert a1 == a2


def test_r61_schema_sentinel_vectors_legal(policy):
    """The all-missing state and the init-counter state are legal
    (they are trained-for perception states, never rejected)."""
    miss = np.full(10, -1.0, dtype=np.float32)
    miss[1] = 0.0            # vy has no -1 sentinel
    miss[6:8] = (0.0, 99.0)  # flap_run, since_flap
    miss[9] = 40.0           # since_gap
    assert policy.predict(miss) in ("HOVER", "FLAP")


# ------------------------------------------------------------------
# lifecycle
# ------------------------------------------------------------------
def test_r61_lifecycle_close_and_reuse():
    p = load_policy()
    assert p.predict(_vec()) in ("HOVER", "FLAP")
    p.close()
    p.close()  # idempotent
    with pytest.raises(PolicyError, match="closed"):
        p.predict(_vec())
    with pytest.raises(PolicyError, match="closed"):
        p.reset()
    p2 = load_policy()  # a fresh instance works after another's close
    assert p2.predict(_vec()) in ("HOVER", "FLAP")
    p2.close()


def test_r61_lifecycle_repeated_init(policy):
    for _ in range(5):
        q = load_policy()
        assert q.model_sha256 == policy.model_sha256
        q.close()


def test_r61_lifecycle_reset_between_episodes(policy):
    """reset() is a clean lifecycle boundary: statistics clear, the
    decision function is unchanged, determinism holds."""
    a0 = policy.predict(_vec())
    policy.predict(_vec(by=30.0))
    n = policy.n_calls
    policy.reset()
    assert policy.n_calls == 0 and n >= 2
    assert policy.predict(_vec()) == a0


def test_r61_lifecycle_context_manager():
    with load_policy() as p:
        assert p.predict(_vec()) in ("HOVER", "FLAP")
    assert p.closed


# ------------------------------------------------------------------
# manifest / artifact binding
# ------------------------------------------------------------------
def test_r61_manifest_hash_mismatch_rejected(tmp_path):
    model = os.path.join(MODELS, "r60_soup_e6a010.onnx")
    bad = tmp_path / "mutated.onnx"
    blob = bytearray(open(model, "rb").read())
    blob[-1] ^= 0xFF  # flip one bit
    bad.write_bytes(bytes(blob))
    with pytest.raises(ManifestError, match="HASH MISMATCH"):
        load_policy(model_path=str(bad))


def test_r61_manifest_corrupt_model_rejected(tmp_path):
    model = os.path.join(MODELS, "r60_soup_e6a010.onnx")
    good = open(model, "rb").read()
    trunc = tmp_path / "trunc.onnx"
    trunc.write_bytes(good[: len(good) // 2])
    # a truncated file still hashes to *something*; craft a manifest
    # binding the truncated hash so the failure is at session init
    import hashlib
    h = hashlib.sha256(bytes(trunc.read_bytes())).hexdigest()
    man = json.load(open(os.path.join(MODELS,
                                      "FINAL_MODEL_MANIFEST.json")))
    man["onnx_artifact"]["sha256"] = h
    man_path = tmp_path / "m.json"
    man_path.write_text(json.dumps(man))
    with pytest.raises(ModelLoadError, match="session init failed"):
        load_policy(model_path=str(trunc), manifest_path=str(man_path))


def test_r61_manifest_missing_files():
    with pytest.raises(ModelLoadError, match="not found"):
        load_policy(model_path="/nonexistent/x.onnx")
    with pytest.raises(ManifestError, match="not found"):
        load_policy(manifest_path="/nonexistent/m.json")


def test_r61_manifest_garbage_rejected(tmp_path):
    man = tmp_path / "m.json"
    man.write_text("{not json")
    with pytest.raises(ManifestError, match="unreadable"):
        load_policy(manifest_path=str(man))


def test_r61_manifest_wrong_class_order_rejected(tmp_path):
    man = json.load(open(os.path.join(MODELS,
                                      "FINAL_MODEL_MANIFEST.json")))
    man["output_schema"]["logits"]["order"] = ["FLAP", "HOVER"]
    p_ = tmp_path / "m.json"
    p_.write_text(json.dumps(man))
    with pytest.raises(ManifestError, match="class order"):
        load_policy(manifest_path=str(p_))


def test_r61_manifest_identity(policy):
    ident = policy.identity()
    import hashlib
    want = hashlib.sha256(
        open(os.path.join(MODELS, "r60_soup_e6a010.onnx"),
             "rb").read()).hexdigest()
    assert ident["model_sha256"] == want
    assert ident["source_checkpoint"] == "data/learn/r59_soup_e6a010.npz"


def test_r61_no_ort_clear_error(tmp_path):
    """With onnxruntime unimportable, load_policy fails with the
    actionable message (never a bare traceback)."""
    fake = tmp_path / "sitefake"
    fake.mkdir()
    (fake / "onnxruntime.py").write_text(
        "raise ImportError('simulated missing onnxruntime')\n")
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(fake)!r})\n"
        f"sys.path.insert(0, {PKG!r})\n"
        "from flappybird_policy import load_policy, ModelLoadError\n"
        "try:\n"
        "    load_policy()\n"
        "    print('BAD: loaded without ort')\n"
        "except ModelLoadError as e:\n"
        "    assert 'onnxruntime is not installed' in str(e), e\n"
        "    print('OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    assert "OK" in r.stdout


# ------------------------------------------------------------------
# determinism
# ------------------------------------------------------------------
def test_r61_determinism_repeat_and_batch(policy):
    rng = np.random.default_rng(61)
    xs = np.stack(
        [_vec(by=float(rng.uniform(20, 200)),
              vy=float(rng.uniform(-8, 5)),
              gc=float(rng.uniform(40, 180)),
              dx=float(rng.uniform(-30, 150)),
              since_flap=float(rng.integers(0, 40))) for _ in range(64)]
    ).astype(np.float32)
    singles = [policy.predict(x) for x in xs]
    batch = policy.predict_batch(xs)
    assert singles == batch
    assert singles == [policy.predict(x) for x in xs]  # repeatable


# ------------------------------------------------------------------
# closed-loop runner fault injection (the emulator runner, duck-typed)
# ------------------------------------------------------------------
def test_r61_loop_faults():
    from r61e_deploy_loop import LoopError, run_episode

    class FakeEnv:
        def __init__(self, mode):
            self.mode = mode
            self.closed = False

        def start_episode(self, k):
            if self.mode == "start_fail":
                raise RuntimeError("anchor restore failed")
            return k + 13

        def frame(self):
            if self.mode == "frame_fail":
                raise RuntimeError("core died")
            return np.zeros((240, 320, 3), dtype=np.uint8)

        def run(self, n, buttons):
            return n

        def game_over(self, fr):
            return self.mode == "instant_over"

        def close(self):
            self.closed = True

    class FakePolicy:
        classes = ("HOVER", "FLAP")

        def predict(self, obs):
            return "HOVER"

        def close(self):
            pass

    # normal episode on a fake env runs and returns a record
    env = FakeEnv("ok")
    rec = run_episode(env, FakePolicy(), k=6, budget=50)
    assert rec["frames"] == 50 and rec["result"] == "alive"
    assert rec["actions"] == 0  # all HOVER on a black frame
    # the runner must NOT swallow env failures
    with pytest.raises(LoopError, match="anchor restore failed"):
        run_episode(FakeEnv("start_fail"), FakePolicy(), 6, 10)
    with pytest.raises(LoopError, match="core died"):
        run_episode(FakeEnv("frame_fail"), FakePolicy(), 6, 10)
    # an instant game-over episode terminates early, honestly
    rec = run_episode(FakeEnv("instant_over"), FakePolicy(), 6, 100)
    assert rec["result"] == "death" and rec["frames"] < 100


def test_r61_loop_resets_numpy_policies_between_episodes():
    """REGRESSION (R61 validation incident): a numpy-path policy that
    owns its perception (FlatPolicy-style .act + .reset_obs) must be
    reset at EVERY episode start — a stale observer from the previous
    life is not the deployed behavior."""
    from r61e_deploy_loop import run_episode

    class FakeEnv:
        def frame(self):
            return np.zeros((240, 320, 3), dtype=np.uint8)

        def start_episode(self, k):
            return k

        def run(self, n, buttons):
            return n

        def game_over(self, fr):
            return False

        def close(self):
            pass

    class StatefulPolicy:
        """FlatPolicy-shaped: has .act and .reset_obs, no .predict."""
        artifact = None

        def __init__(self):
            self.resets = 0
            self.acts = 0

        def reset_obs(self):
            self.resets += 1

        def act(self, small):
            self.acts += 1
            return "HOVER"

    pol = StatefulPolicy()
    env = FakeEnv()
    run_episode(env, pol, k=6, budget=10)
    assert pol.resets == 1 and pol.acts == 10
    run_episode(env, pol, k=14, budget=10)
    assert pol.resets == 2, "perception state carried across episodes"


# ------------------------------------------------------------------
# real-emulator smoke through the package (minutes, not seconds)
# ------------------------------------------------------------------
def test_r61_emulator_smoke():
    iso = "/home/z/my-project/emu/games_homebrew/flappybird.cue"
    if not os.path.exists(iso):
        pytest.skip("emulator assets not present on this machine")
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    from ps1play.learn.games import FlappyEnv, _small_rgb  # noqa: E402
    from ps1play.learn import visual_only as VO            # noqa: E402
    from r61e_deploy_loop import (                         # noqa: E402
        advance_history, build_vector)

    pol = load_policy()
    env = FlappyEnv()
    try:
        env.reach_ready()
        env.start_episode(6)
        observer, tracker = VO.BirdObserverV7(), VO.GapTrackerV7()
        since_flap, flap_run, last_gc, since_gap = 99, 0, -1.0, 40
        prev_action = None
        flaps = 0
        for t in range(300):
            small = _small_rgb(env.frame())
            x, pend = build_vector(
                small, observer, tracker, since_flap, flap_run,
                last_gc, since_gap, prev_action)
            action = pol.predict(x)
            since_flap, flap_run, last_gc, since_gap = advance_history(
                action, since_flap, flap_run, last_gc, since_gap, pend)
            prev_action = action
            if action == "FLAP":
                flaps += 1
            env.run(1, {"B"} if action == "FLAP" else set())
        assert flaps > 0, "the policy never flapped in 300 frames"
    finally:
        env.close()
        pol.close()
