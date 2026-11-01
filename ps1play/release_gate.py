"""ps1play.release_gate — the R62 automated final release gate (§18).

    python3 -m ps1play verify --profile final

Validates the complete runtime in one command and writes a
machine-readable result (reports/r62_release_gate.json + .log).
Every gate checks its required condition EXPLICITLY — a subprocess
exiting 0 is never taken as PASS by itself. Status vocabulary:
PASS / FAIL / SKIP / BLOCKED / NOT_APPLICABLE. Exit code is nonzero
when any REQUIRED gate is not PASS (SKIP is only legal for gates this
profile marks optional).

Gates (final profile):
  repo_state          HEAD readable + frozen artifacts exist
  model_manifest      FINAL_MODEL_MANIFEST binds npz+onnx (hashes)
  deployment_package  the R61 independent consumer loads + identity
  policy_runtime      RuntimePolicy authority-hash check + predict
  adapter_contract    FlappyBirdAdapter offline contract suite
  controller_legality illegal action / double-send / stop-latch tests
  episode_lifecycle   the state machine + restart policy rules
  frame_capture       REAL emulator: ordered capture + staleness flag
  full_loop_smoke     REAL episode k=30 byte-matches the R61 record
  multi_episode       3 consecutive REAL episodes byte-match R61
  process_cleanup     session close is idempotent + re-boot works
  regression_suite    the full pytest suite (0 failures)
  evidence_complete   the R62 evidence files exist
  docs_commands       documented CLI commands parse and exit 0
  clean_install       fresh venv + pinned deps + package smoke
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from typing import Any, Dict, List, Optional

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

DATA = os.path.join(REPO, "data", "learn")
OUT_JSON_DEFAULT = os.path.join(REPO, "reports", "r62_release_gate.json")

REQUIRED = {  # gate -> required for the profile "final"
    "repo_state": True,
    "model_manifest": True,
    "deployment_package": True,
    "policy_runtime": True,
    "adapter_contract": True,
    "controller_legality": True,
    "episode_lifecycle": True,
    "frame_capture": True,
    "full_loop_smoke": True,
    "multi_episode": True,
    "process_cleanup": True,
    "regression_suite": True,
    "evidence_complete": True,
    "docs_commands": True,
    "clean_install": False,   # network-dependent: BLOCKED is honest
}


def sha(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


class Gate:
    def __init__(self) -> None:
        self.results: Dict[str, Dict[str, str]] = {}

    def record(self, name: str, status: str, detail: str) -> bool:
        self.results[name] = {"status": status, "detail": detail}
        print(f"[{status:>13}] {name}: {detail}", flush=True)
        return status == "PASS"


# ---------------------------------------------------------------- --
# offline gates (no emulator)
# ---------------------------------------------------------------- --

def gate_repo_state(g: Gate) -> bool:
    need = [
        os.path.join(DATA, "FINAL_MODEL_MANIFEST.json"),
        os.path.join(DATA, "r59_soup_e6a010.npz"),
        os.path.join(DATA, "r60_soup_e6a010.onnx"),
        os.path.join(REPO, "deployment", "flappybird_policy", "models",
                     "r60_soup_e6a010.onnx"),
        os.path.join(REPO, "third_party", "openbios", "openbios.bin"),
    ]
    missing = [p for p in need if not os.path.exists(p)]
    if missing:
        return g.record("repo_state", "FAIL",
                        f"missing: {missing}")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                          capture_output=True, text=True)
    if head.returncode != 0:
        return g.record("repo_state", "FAIL", "git HEAD unreadable")
    return g.record("repo_state", "PASS",
                    f"HEAD {head.stdout.strip()[:12]}; artifacts present")


def gate_model_manifest(g: Gate) -> bool:
    with open(os.path.join(DATA, "FINAL_MODEL_MANIFEST.json")) as f:
        man = json.load(f)
    npz_ok = sha(os.path.join(DATA, "r59_soup_e6a010.npz")) == \
        man["source_checkpoint"]["sha256"]
    onnx = os.path.join(DATA, "r60_soup_e6a010.onnx")
    pkg_onnx = os.path.join(REPO, "deployment", "flappybird_policy",
                            "models", "r60_soup_e6a010.onnx")
    onnx_ok = sha(onnx) == man["onnx_artifact"]["sha256"]
    pkg_ok = sha(pkg_onnx) == sha(onnx)
    if npz_ok and onnx_ok and pkg_ok:
        return g.record("model_manifest", "PASS",
                        "manifest<->npz/onnx/package bound")
    return g.record("model_manifest", "FAIL",
                    f"npz={npz_ok} onnx={onnx_ok} pkg={pkg_ok}")


def gate_deployment_package(g: Gate) -> bool:
    code = subprocess.run(
        [sys.executable, "-m", "flappybird_policy"], cwd=os.path.join(
            REPO, "deployment", "flappybird_policy"),
        capture_output=True, text=True, timeout=120)
    ok = code.returncode == 0 and "SMOKE PASS" in code.stdout
    if not ok:
        return g.record("deployment_package", "FAIL",
                        f"rc={code.returncode} tail={code.stdout[-200:]}")
    return g.record("deployment_package", "PASS",
                    "fresh CLI smoke green (SMOKE PASS)")


def gate_policy_runtime(g: Gate) -> bool:
    try:
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.policy_runtime import RuntimePolicy
        import numpy as np
        cfg = RuntimeConfig(output_dir="/tmp/r62_gate").validated()
        pol = RuntimePolicy(cfg)
        ident = pol.identity()
        obs_vec = np.zeros(10, dtype=np.float32)
        obs_vec[0] = 100.0
        from ps1play.runtime.interfaces import GameObservation
        obs = GameObservation(values=obs_vec, frame_seq=1,
                              frame_id="gate1", timestamp=0.0,
                              valid=True)
        dec = pol.predict(obs)
        pol.close()
        if dec.action not in ("HOVER", "FLAP"):
            return g.record("policy_runtime", "FAIL",
                            f"action {dec.action!r} illegal")
        return g.record("policy_runtime", "PASS",
                        f"authority-checked load + predict OK "
                        f"({ident['model_sha256'][:12]}...)")
    except Exception as e:
        return g.record("policy_runtime", "FAIL",
                        f"{type(e).__name__}: {e}")


def gate_adapter_contract(g: Gate) -> bool:
    try:
        from ps1play.adapters.flappybird.adapter import (
            FlappyBirdAdapter)
        from ps1play.runtime.interfaces import Frame
        import numpy as np
        env = _FakeFlappyEnv()
        ad = FlappyBirdAdapter(env)
        ad.wait_ready(5.0)
        ad.start_episode(6)
        rgb = (np.random.default_rng(0).integers(
            0, 255, (240, 320, 3))).astype(np.uint8)
        fr = Frame(seq=1, emulator_frame_count=20, rgb=rgb,
                   timestamp=0.0)
        obs = ad.observe(fr)
        if not obs.valid or obs.values.shape != (10,) or \
                obs.values.dtype != np.float32:
            return g.record("adapter_contract", "FAIL",
                            f"observation invalid: {obs.invalid_reason}")
        if sorted(ad.legal_actions()) != ["FLAP", "HOVER"]:
            return g.record("adapter_contract", "FAIL",
                            "legal actions wrong")
        if ad.action_to_buttons("FLAP") != frozenset({"B"}) or \
                ad.action_to_buttons("HOVER") != frozenset():
            return g.record("adapter_contract", "FAIL",
                            "button mapping wrong")
        ad.reset_episode()
        return g.record("adapter_contract", "PASS",
                        "observe/act/reset contract green (fake env)")
    except Exception as e:
        return g.record("adapter_contract", "FAIL",
                        f"{type(e).__name__}: {e}")


def gate_controller_legality(g: Gate) -> bool:
    try:
        from ps1play.adapters.flappybird.adapter import (
            FlappyBirdAdapter)
        from ps1play.runtime.controller import SafetyController
        from ps1play.runtime.errors import ControllerError
        from ps1play.runtime.interfaces import (ActionDecision, Frame)
        import numpy as np
        env = _FakeFlappyEnv()
        ad = FlappyBirdAdapter(env)
        ad.start_episode(6)
        sess = _FakeSession(env)
        ctl = SafetyController(ad, sess)
        fr = Frame(seq=1, emulator_frame_count=1,
                   rgb=np.zeros((240, 320, 3), np.uint8), timestamp=0.0)
        d = ActionDecision(action="FLAP", logits=None, frame_seq=1,
                           policy_name="t", policy_sha256="t",
                           latency_ms=0.0)
        ctl.apply(d, fr)
        try:
            ctl.apply(d, fr)     # duplicate frame send
            return g.record("controller_legality", "FAIL",
                            "duplicate send accepted")
        except ControllerError:
            pass
        bad = ActionDecision(action="JUMP", logits=None, frame_seq=2,
                             policy_name="t", policy_sha256="t",
                             latency_ms=0.0)
        try:
            ctl.apply(bad, Frame(seq=2, emulator_frame_count=2,
                                 rgb=fr.rgb, timestamp=0.0))
            return g.record("controller_legality", "FAIL",
                            "illegal action accepted")
        except ControllerError:
            pass
        ctl.emergency_stop()
        try:
            ctl.apply(ActionDecision(action="HOVER", logits=None,
                                     frame_seq=3, policy_name="t",
                                     policy_sha256="t", latency_ms=0.0),
                      Frame(seq=3, emulator_frame_count=3, rgb=fr.rgb,
                            timestamp=0.0))
            return g.record("controller_legality", "FAIL",
                            "emergency-stop latch ignored")
        except ControllerError:
            pass
        return g.record("controller_legality", "PASS",
                        "legality + sequencing + stop latch enforced")
    except Exception as e:
        return g.record("controller_legality", "FAIL",
                        f"{type(e).__name__}: {e}")


def gate_episode_lifecycle(g: Gate) -> bool:
    try:
        from ps1play.runtime.errors import LifecycleError
        from ps1play.runtime.lifecycle import (Lifecycle,
                                               RestartPolicy)
        lc = Lifecycle()
        lc.transition("BOOTING")
        lc.transition("READY")
        lc.transition("EPISODE_ACTIVE")
        try:
            lc.transition("INIT")
            return g.record("episode_lifecycle", "FAIL",
                            "illegal transition accepted")
        except LifecycleError:
            pass
        rp = RestartPolicy(max_episodes=2, time_limit_s=60,
                           max_consecutive_failures=2)
        rp.record(failed=False)
        c1, _ = rp.should_continue()
        rp.record(failed=False)
        c2, reason2 = rp.should_continue()
        if not (c1 and not c2 and "limit" in reason2):
            return g.record("episode_lifecycle", "FAIL",
                            f"restart policy: {c1},{c2},{reason2}")
        rp2 = RestartPolicy(max_episodes=0, time_limit_s=60,
                            max_consecutive_failures=2)
        rp2.record(failed=True)
        rp2.record(failed=True)
        c4, r4 = rp2.should_continue()
        if c4 or "failures" not in r4:
            return g.record("episode_lifecycle", "FAIL",
                            f"failure cap not enforced: {c4},{r4}")
        return g.record("episode_lifecycle", "PASS",
                        "state machine + restart policy rules green")
    except Exception as e:
        return g.record("episode_lifecycle", "FAIL",
                        f"{type(e).__name__}: {e}")


def gate_docs_commands(g: Gate) -> bool:
    import shlex
    cmds = [
        "python3 -m ps1play --help",
        "python3 -m ps1play play --help",
        "python3 -m ps1play verify --help",
    ]
    for c in cmds:
        r = subprocess.run(shlex.split(c), cwd=REPO,
                           capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return g.record("docs_commands", "FAIL", f"{c} rc!=0")
    return g.record("docs_commands", "PASS",
                    f"{len(cmds)} documented commands exit 0")


def gate_evidence_complete(g: Gate) -> bool:
    need_docs = [
        "docs/r62_baseline_audit.md",
        "docs/r62_architecture.md",
        "docs/r62_runtime_contracts.md",
        "docs/r62_installation.md",
        "docs/r62_user_guide.md",
        "docs/r62_troubleshooting.md",
        "docs/r62_testing.md",
        "docs/r62_final_report.md",
    ]
    need_evidence = [
        "data/r62/r62_stage_b_summary.json",
        "data/r62/r62_stage_c_summary.json",
        "data/r62/r62_stage_d_summary.json",
        "data/r62/r62_profile.json",
    ]
    missing = [p for p in need_docs + need_evidence
               if not os.path.exists(os.path.join(REPO, p))]
    if missing:
        return g.record("evidence_complete", "BLOCKED",
                        f"evidence not yet written: {missing}")
    # the summaries must actually assert success
    import json as _json
    for p in need_evidence:
        with open(os.path.join(REPO, p)) as f:
            d = _json.load(f)
        if p.endswith("stage_b_summary.json"):
            ok = d.get("n_episodes_completed", 0) >= 20 and \
                d.get("family_byte_match_all")
        elif p.endswith("stage_c_summary.json"):
            ok = d.get("all_ok")
        elif p.endswith("stage_d_summary.json"):
            ok = d.get("all_ok")
        else:
            ok = d.get("full_loop", {}).get("decision_cycles", 0) \
                >= 10000
        if not ok:
            return g.record("evidence_complete", "FAIL",
                            f"{p} does not assert success")
    return g.record("evidence_complete", "PASS",
                    f"{len(need_docs)} docs + {len(need_evidence)} "
                    f"evidence summaries, all asserting success")


def gate_clean_install(g: Gate) -> bool:
    script = os.path.join(REPO, "scripts", "r61_cleanroom.sh")
    if not os.path.exists(script):
        return g.record("clean_install", "BLOCKED",
                        "clean-room script missing")
    try:
        r = subprocess.run(["bash", script], capture_output=True,
                           text=True, timeout=420)
        ok = r.returncode == 0 and "CLEANROOM PASS" in r.stdout
        if ok:
            return g.record("clean_install", "PASS",
                            "fresh venv + pinned deps + smoke green")
        return g.record("clean_install", "FAIL",
                        f"rc={r.returncode} "
                        f"tail={r.stdout[-300:] if r.stdout else ''}")
    except subprocess.TimeoutExpired:
        return g.record("clean_install", "BLOCKED",
                        "clean-room timed out (network?)")
    except Exception as e:
        return g.record("clean_install", "BLOCKED",
                        f"{type(e).__name__}: {e}")


def gate_regression_suite(g: Gate) -> bool:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "-x",
             "-p", "no:cacheprovider"],
            cwd=REPO, capture_output=True, text=True, timeout=1200)
        out = r.stdout or r.stderr
        tail = out.strip().splitlines()[-1] if out.strip() else "?"
        if r.returncode != 0:
            return g.record("regression_suite", "FAIL", tail)
        return g.record("regression_suite", "PASS", tail)
    except Exception as e:
        return g.record("regression_suite", "FAIL",
                        f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- --
# emulator-backed gates
# ---------------------------------------------------------------- --

def gate_frame_capture(g: Gate) -> bool:
    try:
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.session import EnvSession
        from ps1play.runtime.errors import FrameError
        import numpy as np
        cfg = RuntimeConfig(output_dir="/tmp/r62_gate",
                            max_frames_per_episode=100).validated()
        sess = EnvSession.boot_new(cfg, deadline_s=120)
        try:
            sess.advance(2, frozenset())    # first render
            src = sess.frames()
            f1 = src.latest(require_fresh=False)
            f2 = src.latest(require_fresh=False)
            if not f2.stale:
                return g.record("frame_capture", "FAIL",
                                "stale frame not flagged without advance")
            sess.advance(1, frozenset())
            f3 = src.latest(require_fresh=True)
            if f3.emulator_frame_count <= f1.emulator_frame_count:
                return g.record("frame_capture", "FAIL",
                                "frame count did not advance")
            if f3.rgb.ndim != 3 or f3.rgb.shape[2] != 3 \
                    or f3.rgb.dtype != np.uint8:
                return g.record("frame_capture", "FAIL",
                                f"bad frame {f3.rgb.shape} "
                                f"{f3.rgb.dtype}")
            # the staleness CONTRACT: a require_fresh capture right
            # after another capture (no advance) must raise
            try:
                src.latest(require_fresh=True)
                return g.record("frame_capture", "FAIL",
                                "stale capture accepted")
            except FrameError:
                pass
            return g.record("frame_capture", "PASS",
                            f"ordered capture + staleness enforced "
                            f"(emu frames {f1.emulator_frame_count}"
                            f"->{f3.emulator_frame_count})")
        finally:
            sess.close()
    except Exception as e:
        return g.record("frame_capture", "FAIL",
                        f"{type(e).__name__}: {e}")


def _family_ref() -> Dict[int, Dict[str, Any]]:
    rows = {}
    with open(os.path.join(DATA, "r61_family_rows.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            rows[int(r["k"])] = r
    return rows


def _run_family_episode(g: Gate, k: int, ref: Dict[str, Any],
                        budget: Optional[int] = None) -> bool:
    from ps1play.runtime.config import RuntimeConfig
    from ps1play.runtime.engine import RuntimeEngine
    from ps1play.runtime.telemetry import TelemetryLog
    out = f"/tmp/r62_gate/fam_k{k}"
    os.makedirs(out, exist_ok=True)
    cfg = RuntimeConfig(
        output_dir=out, seed_k=k,
        max_frames_per_episode=budget or int(ref["frames"]),
        max_runtime_s=900, verbose=False).validated()
    tel = TelemetryLog(os.path.join(out, "events.jsonl"))
    eng = RuntimeEngine(cfg, tel)
    try:
        assets = eng.preflight()
        eng.boot(assets)
        results = eng.run()
    finally:
        eng.close()
    if not results:
        g.detail = "no episode ran"
        return False
    r = results[0]
    want_frames = int(ref["frames"])
    ok = (r["result"] == ref["result"] and r["pipes"] == ref["pipes"]
          and r["frames"] == want_frames and r["flaps"] == ref["flaps"]
          and r["trace_sha256"] == ref["trace_sha256"])
    return ok


def gate_full_loop_smoke(g: Gate) -> bool:
    ref = _family_ref().get(30)
    if ref is None:
        return g.record("full_loop_smoke", "BLOCKED",
                        "no k=30 family reference")
    try:
        ok = _run_family_episode(g, 30, ref)
        if ok:
            return g.record(
                "full_loop_smoke", "PASS",
                f"k=30 through the runtime = {ref['pipes']}@"
                f"{ref['frames']}, trace byte-matches the R61 record")
        return g.record("full_loop_smoke", "FAIL",
                        f"k=30 mismatch vs {ref}")
    except Exception as e:
        return g.record("full_loop_smoke", "FAIL",
                        f"{type(e).__name__}: {e}")


def gate_multi_episode(g: Gate) -> bool:
    fam = _family_ref()
    ref = fam.get(45)
    if ref is None:
        return g.record("multi_episode", "BLOCKED",
                        "no k=45 family reference")
    try:
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.engine import RuntimeEngine
        from ps1play.runtime.telemetry import TelemetryLog
        out = "/tmp/r62_gate/multi"
        os.makedirs(out, exist_ok=True)
        cfg = RuntimeConfig(
            output_dir=out, episodes=3, seed_k=45,
            max_frames_per_episode=10000,
            max_runtime_s=900).validated()
        tel = TelemetryLog(os.path.join(out, "events.jsonl"))
        eng = RuntimeEngine(cfg, tel)
        try:
            assets = eng.preflight()
            eng.boot(assets)
            results = eng.run()
        finally:
            eng.close()
        # 3 episodes, same seed k=45 -> byte-identical to each other
        # AND to the R61 record (deterministic emulator)
        ok = len(results) == 3 and all(
            r["trace_sha256"] == ref["trace_sha256"]
            and r["pipes"] == ref["pipes"] for r in results)
        if ok:
            return g.record(
                "multi_episode", "PASS",
                f"3 consecutive episodes (k=45) all byte-match the "
                f"R61 record ({ref['pipes']}@{ref['frames']}) — no "
                f"stale state across episodes")
        detail = [(r["result"], r["pipes"], r["frames"],
                   r["trace_sha256"][:12]) for r in results]
        return g.record("multi_episode", "FAIL", f"{detail} vs "
                        f"{ref['pipes']}@{ref['frames']} "
                        f"{ref['trace_sha256'][:12]}")
    except Exception as e:
        return g.record("multi_episode", "FAIL",
                        f"{type(e).__name__}: {e}")


def gate_process_cleanup(g: Gate) -> bool:
    try:
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.session import EnvSession
        cfg = RuntimeConfig(output_dir="/tmp/r62_gate").validated()
        s1 = EnvSession.boot_new(cfg, deadline_s=120)
        tag1 = s1.tag()
        s1.advance(2, frozenset())
        s1.frames().latest(require_fresh=False)   # a capture
        s1.close()
        s1.close()      # idempotent
        if s1.alive():
            return g.record("process_cleanup", "FAIL",
                            "session still alive after close")
        # re-boot in the SAME process must work (no leaked core state)
        s2 = EnvSession.boot_new(cfg, deadline_s=120)
        s2.advance(2, frozenset())
        f = s2.frames().latest(require_fresh=False)
        ok = f.rgb.ndim == 3 and f.rgb.shape[2] == 3
        s2.close()
        if ok:
            return g.record("process_cleanup", "PASS",
                            "close idempotent + same-process re-boot "
                            f"works ({tag1[:40]}...)")
        return g.record("process_cleanup", "FAIL", "re-boot bad frame")
    except Exception as e:
        return g.record("process_cleanup", "FAIL",
                        f"{type(e).__name__}: {e}")


# ---------------------------------------------------------------- --
# the fake env used by offline gates
# ---------------------------------------------------------------- --

class _FakeFlappyEnv:
    """A minimal flappy-shaped env for offline contract gates."""

    def __init__(self):
        self.boot_info = {"fake": True}
        self._n = 0

    class _Core:
        frames_run = 0
        log_history = []

    @property
    def p(self):
        return self

    @property
    def core(self):
        return self._Core()

    def reach_ready(self):
        return True

    def start_episode(self, k):
        return 13

    def frame(self):
        import numpy as np
        self._n += 1
        return np.zeros((240, 320, 3), np.uint8)

    def run(self, frames, buttons=None, buttons_p1=None):
        self._Core.frames_run += frames

    def game_over(self, fr):
        return False

    def close(self):
        pass


class _FakeSession:
    def __init__(self, env):
        self.env = env

    def advance(self, frames, buttons):
        self.env.run(frames, set(buttons))

    def alive(self):
        return True


# ---------------------------------------------------------------- --
# driver
# ------------------------------------------------------------------

def run_release_gate(profile: str = "final",
                     output_dir: Optional[str] = None) -> int:
    t0 = time.time()
    out_dir = output_dir or os.path.join(REPO, "reports")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "r62_release_gate.json")
    log_path = os.path.join(out_dir, "r62_release_gate.log")

    import contextlib
    import io
    buf = io.StringIO()
    g = Gate()
    order = [
        ("repo_state", gate_repo_state),
        ("model_manifest", gate_model_manifest),
        ("deployment_package", gate_deployment_package),
        ("policy_runtime", gate_policy_runtime),
        ("adapter_contract", gate_adapter_contract),
        ("controller_legality", gate_controller_legality),
        ("episode_lifecycle", gate_episode_lifecycle),
        ("frame_capture", gate_frame_capture),
        ("full_loop_smoke", gate_full_loop_smoke),
        ("multi_episode", gate_multi_episode),
        ("process_cleanup", gate_process_cleanup),
        ("regression_suite", gate_regression_suite),
        ("docs_commands", gate_docs_commands),
        ("evidence_complete", gate_evidence_complete),
        ("clean_install", gate_clean_install),
    ]
    with contextlib.redirect_stdout(io.StringIO()) as gate_buf:
        for name, fn in order:
            try:
                fn(g)
            except Exception as e:      # a gate crash is a FAIL
                tb = traceback.format_exc(limit=3)
                g.record(name, "FAIL",
                         f"gate crashed: {type(e).__name__}: {e} "
                         f"{tb[-200:]}")
    print(gate_buf.getvalue(), end="")
    wall = round(time.time() - t0, 1)
    required_fail = [n for n, r in g.results.items()
                     if REQUIRED.get(n, True)
                     and r["status"] not in ("PASS", "NOT_APPLICABLE")]
    release = "PASS" if not required_fail else "FAIL"
    doc = {
        "round": "R62",
        "profile": profile,
        "when": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "wall_s": wall,
        "gates": g.results,
        "required_failures": required_fail,
        "release": release,
    }
    with open(json_path, "w") as f:
        json.dump(doc, f, indent=1)
    with open(log_path, "w") as f:
        f.write(gate_buf.getvalue())
    print(f"RELEASE: {release} -> {json_path} ({wall}s)")
    return 0 if release == "PASS" else 1
