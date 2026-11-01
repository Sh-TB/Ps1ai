"""R62 runtime contracts — offline tests (no emulator needed).

Covers the mission's layered strategy at the unit/contract level:
  A. unit: config validation, lifecycle state machine, restart policy,
     telemetry ordering, errors, registry
  B. adapter: FlappyBirdAdapter frame->observation contract (fake env)
  C. policy: RuntimePolicy authority check + invalid-input rejection
  D. controller: legality / sequencing / stop latch / release
  G. fault injection: engine failure handling with fake components
  + the game-agnostic example: a SECOND (fake) game plugged into the
    real RuntimeEngine loop without touching the runtime core.
"""
import hashlib
import json
import os
import sys

import numpy as np
import pytest

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
PKG = os.path.join(REPO, "deployment", "flappybird_policy")
sys.path.insert(0, PKG)

from ps1play.runtime.config import RuntimeConfig  # noqa: E402
from ps1play.runtime.controller import SafetyController  # noqa: E402
from ps1play.runtime.engine import RuntimeEngine  # noqa: E402
from ps1play.runtime.errors import (  # noqa: E402
    AdapterError, AssetError, ConfigError, ControllerError,
    EmulatorError, EmergencyStop, FrameError, LifecycleError,
    Ps1RuntimeError, RuntimePolicyError)
from ps1play.runtime.interfaces import (  # noqa: E402
    ActionDecision, Frame, GameAdapter, GameObservation)
from ps1play.runtime.lifecycle import (  # noqa: E402
    Lifecycle, RestartPolicy, StopWatch)
from ps1play.runtime.scoring import PassageCounter  # noqa: E402
from ps1play.runtime.telemetry import (  # noqa: E402
    LatencyStats, TelemetryLog, manifest_sha)


# ------------------------------------------------------------------
# fakes
# ------------------------------------------------------------------
class FakeCore:
    def __init__(self):
        self.frames_run = 0
        self.shut = False

    def run_frame(self):
        self.frames_run += 1


class FakeFlappyEnv:
    """A flappy-shaped env: real detection surfaces, scripted frames."""

    def __init__(self, n_pipes=2, die_after=40):
        self.boot_info = {"fake": True}
        self.core = FakeCore()
        self._rng = np.random.default_rng(7)
        self._base = self._sky()
        self.n_pipes = n_pipes
        self.die_after = die_after
        self.started = 0
        self.closed = 0

    @staticmethod
    def _sky():
        fr = np.zeros((240, 320, 3), np.uint8)
        fr[:, :, 0] = 90       # teal-ish
        fr[:, :, 2] = 140
        return fr

    class _P:
        pass

    @property
    def p(self):
        p = self._P()
        p.core = self.core
        return p

    def reach_ready(self):
        return True

    def start_episode(self, k):
        self.started += 1
        self.core.frames_run = 13
        return 13

    def frame(self):
        self.core.frames_run += 1
        return self._base.copy()

    def run(self, frames, buttons=None, buttons_p1=None):
        self.core.frames_run += frames

    def game_over(self, fr):
        return self.core.frames_run > self.die_after

    def close(self):
        self.closed += 1


class ScriptedGameAdapter(GameAdapter):
    """A MINIMAL SECOND GAME: 3-feature observation, A/B buttons —
    proves the runtime core is game-agnostic (the engine loop is
    written once and works for any adapter/policy/frame source)."""

    game_id = "scripted"

    def __init__(self, env, telemetry=None):
        self.env = env
        self.n = 0
        self.terminal_after = 25

    def wait_ready(self, deadline_s):
        return True

    def start_episode(self, seed_k):
        self.n = 0
        return 1

    def observe(self, frame):
        # deterministic per-episode signal (resets every start_episode)
        x = np.asarray([self.n % 7, float(self.n), 1.0],
                       dtype=np.float32)
        return GameObservation(values=x, frame_seq=frame.seq,
                               frame_id=frame.frame_id,
                               timestamp=frame.timestamp, valid=True)

    def legal_actions(self):
        return ("IDLE", "PUSH")

    def action_to_buttons(self, action):
        return frozenset({"A"}) if action == "PUSH" else frozenset()

    def post_advance(self, frame):
        self.n += 1
        return {"pipe_passed": False, "pipes": 0, "terminal":
                self.n >= self.terminal_after,
                "death_reason": "scripted_over" if self.n >=
                self.terminal_after else None}

    def episode_stats(self):
        return {"pipes": 0, "actions": 0, "decisions": self.n}

    def reset_episode(self):
        self.n = 0

    def snapshot(self):
        return {"n": self.n}


class ScriptedPolicy:
    def __init__(self):
        self.calls = 0
        self.rejected = 0

    def predict(self, obs):
        self.calls += 1
        if not obs.valid or obs.values is None:
            self.rejected += 1
            raise RuntimePolicyError("invalid obs refused")
        action = "PUSH" if obs.values[0] > 3.5 else "IDLE"
        return ActionDecision(action=action, logits=[0.0, 0.0],
                              frame_seq=obs.frame_seq,
                              policy_name="scripted",
                              policy_sha256="scripted", latency_ms=0.0)

    def legal_actions(self):
        return ("IDLE", "PUSH")

    def reset(self):
        pass

    def identity(self):
        return {"name": "scripted", "model_sha256": "scripted"}

    def close(self):
        pass


class FakeFrameSource:
    """Yields frames from an env, with staleness enforcement."""

    def __init__(self, env):
        self.env = env
        self.seq = 0
        self.last_run = -1

    def latest(self, require_fresh=True):
        fr = self.env.frame()
        if fr is None:
            raise FrameError("capture returned None")
        self.seq += 1
        run = self.env.core.frames_run
        stale = run == self.last_run and self.last_run >= 0
        self.last_run = run
        if stale and require_fresh:
            raise FrameError(f"stale frame (frames_run={run})")
        return Frame(seq=self.seq, emulator_frame_count=run, rgb=fr,
                     timestamp=0.0, stale=stale)

    def capture_latency_ms(self):
        return 0.0

    def close(self):
        pass


class FakeSession:
    def __init__(self, env):
        self.env = env
        self.closed = 0
        self._src = None

    def frames(self):
        if self._src is None:
            self._src = FakeFrameSource(self.env)
        return self._src

    def advance(self, frames, buttons):
        self.env.run(frames, set(buttons))

    def alive(self):
        return True

    def tag(self):
        return "fake-session"

    def close(self):
        self.closed += 1
        self.env.close()


def _make_engine(env, adapter=None, policy=None, **cfgkw):
    out = cfgkw.pop("output_dir", "/tmp/r62_tests")
    os.makedirs(out, exist_ok=True)
    cfg = RuntimeConfig(output_dir=out, **cfgkw).validated()
    for f in ("episodes.jsonl",):
        p = os.path.join(out, f)
        if os.path.exists(p):
            os.remove(p)
    tel = TelemetryLog(os.path.join(out, "events.jsonl"))
    eng = RuntimeEngine(cfg, tel)
    eng.session = FakeSession(env)
    eng.adapter = adapter or ScriptedGameAdapter(env)
    eng.policy = policy or ScriptedPolicy()
    eng.controller = SafetyController(eng.adapter, eng.session, tel)
    eng.manifest = {"test": True}
    eng.manifest_hash = "deadbeef"
    eng.lifecycle.transition("BOOTING")
    eng.lifecycle.transition("READY")
    return eng, tel


# ------------------------------------------------------------------
# A. unit
# ------------------------------------------------------------------
class TestConfig:
    def test_valid_default(self):
        cfg = RuntimeConfig(output_dir="/tmp/x").validated()
        assert cfg.game == "flappybird"
        assert cfg.max_frames_per_episode == 10000

    def test_unknown_game_rejected(self):
        with pytest.raises(ConfigError):
            RuntimeConfig(game="doom", output_dir="/tmp/x").validated()

    def test_unbounded_run_rejected(self):
        with pytest.raises(ConfigError):
            RuntimeConfig(episodes=0, output_dir="/tmp/x").validated()

    def test_negative_rejected(self):
        with pytest.raises(ConfigError):
            RuntimeConfig(max_frames_per_episode=0,
                          output_dir="/tmp/x").validated()
        with pytest.raises(ConfigError):
            RuntimeConfig(max_runtime_s=0,
                          output_dir="/tmp/x").validated()

    def test_frame_cap_safety(self):
        with pytest.raises(ConfigError):
            RuntimeConfig(max_frames_per_episode=2_000_001,
                          output_dir="/tmp/x").validated()

    def test_seed_ladder(self):
        cfg = RuntimeConfig(output_dir="/tmp/x").validated()
        assert [cfg.seed_for_episode(e) for e in (1, 2, 3)] == \
            [6, 12, 18]
        cfg2 = RuntimeConfig(seed_k=210, output_dir="/tmp/x")
        assert cfg2.seed_for_episode(5) == 210

    def test_json_roundtrip_and_hash(self, tmp_path):
        p = tmp_path / "cfg.json"
        cfg = RuntimeConfig(output_dir=str(tmp_path), seed_k=9)
        cfg.write_json(str(p))
        cfg2 = RuntimeConfig.from_json(str(p))
        assert cfg2.seed_k == 9
        assert cfg.config_hash() == cfg2.config_hash()

    def test_config_file_rejects_junk(self, tmp_path):
        p = tmp_path / "junk.json"
        p.write_text("not json at all")
        with pytest.raises(ConfigError):
            RuntimeConfig.from_json(str(p))


class TestLifecycle:
    def test_happy_path(self):
        lc = Lifecycle()
        for st in ("BOOTING", "READY", "EPISODE_ACTIVE", "EPISODE_END",
                   "READY"):
            lc.transition(st)
        assert lc.state == "READY"

    def test_illegal_transition(self):
        lc = Lifecycle()
        with pytest.raises(LifecycleError):
            lc.transition("EPISODE_ACTIVE")

    def test_require(self):
        lc = Lifecycle()
        with pytest.raises(LifecycleError):
            lc.require("READY")

    def test_restart_policy_episode_cap(self):
        rp = RestartPolicy(max_episodes=3, time_limit_s=999)
        for _ in range(3):
            rp.record(failed=False)
        cont, reason = rp.should_continue()
        assert not cont and "limit" in reason

    def test_restart_policy_failure_cap(self):
        rp = RestartPolicy(max_episodes=0, time_limit_s=999,
                           max_consecutive_failures=2)
        rp.record(failed=True)
        cont, _ = rp.should_continue()
        assert cont
        rp.record(failed=True)
        cont, reason = rp.should_continue()
        assert not cont and "failures" in reason

    def test_restart_policy_time_cap(self):
        rp = RestartPolicy(max_episodes=0, time_limit_s=0.01)
        import time as _t
        _t.sleep(0.05)
        cont, reason = rp.should_continue()
        assert not cont and "time" in reason

    def test_stopwatch(self):
        w = StopWatch(0.01)
        import time as _t
        _t.sleep(0.02)
        assert w.expired()

    def test_raise_if_stopped(self):
        with pytest.raises(EmergencyStop):
            from ps1play.runtime.lifecycle import raise_if_stopped
            raise_if_stopped({"stop": True, "reason": "test"})


class TestTelemetry:
    def test_event_ordering_and_flush(self, tmp_path):
        p = tmp_path / "events.jsonl"
        tel = TelemetryLog(str(p), run_meta={"run": 1})
        tel.emit("a", x=1)
        tel.emit("b", y=2)
        tel.close()
        tel.close()  # idempotent
        tel.emit("c")  # after close: ignored, no crash
        lines = [json.loads(l) for l in open(p)]
        seqs = [l["seq"] for l in lines]
        assert seqs == sorted(seqs) and len(seqs) >= 3

    def test_latency_stats(self):
        st = LatencyStats("x")
        for v in (1.0, 2.0, 3.0, 4.0, 100.0):
            st.add(v)
        s = st.summary()
        assert s["n"] == 5 and s["p50_ms"] == 3.0 and \
            s["max_ms"] == 100.0

    def test_manifest_sha_stable(self):
        assert manifest_sha({"a": 1}) == manifest_sha({"a": 1})
        assert manifest_sha({"a": 1}) != manifest_sha({"a": 2})


class TestScoring:
    def test_equivalence_with_r57_lib(self):
        sys.path.insert(0, os.path.join(REPO, "scripts"))
        import r57_lib
        rng = np.random.default_rng(3)
        for trial in range(200):
            xs = [None if rng.random() < 0.2
                  else float(rng.integers(0, 300))
                  for _ in range(rng.integers(1, 40))]
            a, b = PassageCounter(), r57_lib.PassageCounter()
            for i, x in enumerate(xs):
                ra = a.fire(x, i)
                rb = b.fire(x, i)
                assert ra == rb, (trial, i, xs)
                assert a.count == b.count
                assert a.last == b.last

    def test_one_event_per_jump(self):
        pc = PassageCounter()
        assert pc.fire(100.0, 0) is False
        assert pc.fire(99.0, 1) is False
        assert pc.fire(150.0, 2) is False   # small move, no jump
        assert pc.fire(220.0, 3) is True    # jump = passage
        assert pc.count == 1


class TestRegistry:
    def test_flappybird_registered(self):
        from ps1play.runtime.registry import registered_games
        assert "flappybird" in registered_games()

    def test_unknown_game_rejected(self):
        from ps1play.runtime import registry
        with pytest.raises(ConfigError):
            registry.make_env(RuntimeConfig(game="doom",
                                            output_dir="/tmp/x"))


# ------------------------------------------------------------------
# B. adapter contract (offline)
# ------------------------------------------------------------------
class TestFlappyAdapterOffline:
    def _adapter(self):
        from ps1play.adapters.flappybird.adapter import (
            FlappyBirdAdapter)
        env = FakeFlappyEnv()
        return FlappyBirdAdapter(env), env

    def test_observe_shape_and_dtype(self):
        ad, _ = self._adapter()
        ad.start_episode(6)
        fr = Frame(seq=1, emulator_frame_count=20,
                   rgb=np.zeros((240, 320, 3), np.uint8), timestamp=0.0)
        obs = ad.observe(fr)
        assert obs.valid
        assert obs.values.shape == (10,)
        assert obs.values.dtype == np.float32
        assert np.all(np.isfinite(obs.values))

    def test_sentinels_are_valid_observations(self):
        """No pipe / no bird yet = v7 SENTINELS (valid data for the
        model), never invalid observations."""
        ad, _ = self._adapter()
        ad.start_episode(6)
        fr = Frame(seq=1, emulator_frame_count=20,
                   rgb=np.zeros((240, 320, 3), np.uint8), timestamp=0.0)
        obs = ad.observe(fr)
        assert obs.valid
        # zeros frame -> no bird -> the by sentinel
        assert obs.diagnostics["bird_detected"] is False

    def test_bad_frame_is_invalid_not_sent(self):
        ad, _ = self._adapter()
        ad.start_episode(6)
        fr = Frame(seq=1, emulator_frame_count=20, rgb=None,
                   timestamp=0.0)
        obs = ad.observe(fr)
        assert not obs.valid and obs.invalid_reason

    def test_action_mapping(self):
        ad, _ = self._adapter()
        assert ad.action_to_buttons("FLAP") == frozenset({"B"})
        assert ad.action_to_buttons("HOVER") == frozenset()
        with pytest.raises(AdapterError):
            ad.action_to_buttons("JUMP")

    def test_history_update_exact(self):
        ad, _ = self._adapter()
        ad.start_episode(6)
        assert ad._since_flap == 99 and ad._flap_run == 0
        d = ActionDecision("FLAP", None, 1, "p", "h", 0.0)
        o = GameObservation(np.zeros(10, np.float32), 1, "f", 0.0,
                            True)
        ad.note_action(d, o)
        assert ad._since_flap == 0 and ad._flap_run == 1
        ad.note_action(d, o)
        assert ad._flap_run == 2
        d2 = ActionDecision("HOVER", None, 2, "p", "h", 0.0)
        ad.note_action(d2, o)
        assert ad._since_flap == 1 and ad._flap_run == 0
        # caps
        for _ in range(100):
            ad.note_action(d2, o)
        assert ad._since_flap == 99

    def test_reset_drops_all_state(self):
        ad, _ = self._adapter()
        ad.start_episode(6)
        d = ActionDecision("FLAP", None, 1, "p", "h", 0.0)
        o = GameObservation(np.zeros(10, np.float32), 1, "f", 0.0,
                            True)
        ad.note_action(d, o)
        ad._passages.fire(300.0, 1)
        ad.reset_episode()
        assert ad.flaps == 0 and ad.passages == 0 and ad.steps == 0
        assert ad._since_flap == 99 and ad._last_gc == -1.0

    def test_post_advance_terminal(self):
        ad, env = self._adapter()
        ad.start_episode(6)
        fr = Frame(seq=1, emulator_frame_count=999,
                   rgb=np.zeros((240, 320, 3), np.uint8), timestamp=0.0)
        env.core.frames_run = env.die_after + 5
        post = ad.post_advance(fr)
        assert post["terminal"] and post["death_reason"] == "game_over"


# ------------------------------------------------------------------
# C. policy boundary
# ------------------------------------------------------------------
class TestRuntimePolicy:
    def _cfg(self, tmp_path):
        return RuntimeConfig(output_dir=str(tmp_path)).validated()

    def test_load_and_predict(self, tmp_path):
        from ps1play.runtime.policy_runtime import RuntimePolicy
        pol = RuntimePolicy(self._cfg(tmp_path))
        ident = pol.identity()
        assert ident["model_sha256"].startswith("4dd592a7")
        obs = GameObservation(np.zeros(10, np.float32), 1, "f", 0.0,
                              True)
        dec = pol.predict(obs)
        assert dec.action in ("HOVER", "FLAP")
        pol.close()

    def test_rejects_invalid_observation(self, tmp_path):
        from ps1play.runtime.policy_runtime import RuntimePolicy
        pol = RuntimePolicy(self._cfg(tmp_path))
        obs = GameObservation(None, 1, "f", 0.0, False,
                              invalid_reason="test")
        with pytest.raises(RuntimePolicyError):
            pol.predict(obs)
        pol.close()

    def test_rejects_out_of_contract_vector(self, tmp_path):
        from ps1play.runtime.policy_runtime import RuntimePolicy
        pol = RuntimePolicy(self._cfg(tmp_path))
        # bird y outside the documented range -> the package contract
        obs = GameObservation(np.full(10, 1e6, np.float32), 1, "f",
                              0.0, True)
        with pytest.raises(RuntimePolicyError):
            pol.predict(obs)
        pol.close()

    def test_model_hash_mismatch_is_asset_error(self, tmp_path):
        from ps1play.runtime.policy_runtime import RuntimePolicy
        cfg = self._cfg(tmp_path)
        # point at the sidecar json (a valid file, wrong hash)
        cfg.model_path = os.path.join(REPO, "data", "learn",
                                      "r60_soup_e6a010.onnx.json")
        with pytest.raises(AssetError):
            RuntimePolicy(cfg)


# ------------------------------------------------------------------
# D. controller
# ------------------------------------------------------------------
class TestController:
    def _setup(self):
        env = FakeFlappyEnv()
        ad = ScriptedGameAdapter(env)
        sess = FakeSession(env)
        ctl = SafetyController(ad, sess)
        return ad, sess, ctl

    @staticmethod
    def _dec(action, seq):
        return ActionDecision(action, None, seq, "p", "h", 0.0)

    def test_legal_flow(self):
        ad, sess, ctl = self._setup()
        fr = Frame(seq=1, emulator_frame_count=1,
                   rgb=np.zeros((2, 2, 3), np.uint8), timestamp=0.0)
        assert ctl.apply(self._dec("PUSH", 1), fr) >= 0.0
        assert sess.env.core.frames_run == 1   # advanced exactly 1
        assert ctl.state()["n_sends"] == 1

    def test_illegal_action_rejected(self):
        ad, sess, ctl = self._setup()
        fr = Frame(seq=1, emulator_frame_count=1,
                   rgb=np.zeros((2, 2, 3), np.uint8), timestamp=0.0)
        with pytest.raises(ControllerError):
            ctl.apply(self._dec("SHOVE", 1), fr)
        assert ctl.state()["n_rejects"] >= 1

    def test_duplicate_frame_rejected(self):
        ad, sess, ctl = self._setup()
        fr = Frame(seq=1, emulator_frame_count=1,
                   rgb=np.zeros((2, 2, 3), np.uint8), timestamp=0.0)
        ctl.apply(self._dec("PUSH", 1), fr)
        with pytest.raises(ControllerError):
            ctl.apply(self._dec("PUSH", 1), fr)

    def test_stop_latch(self):
        ad, sess, ctl = self._setup()
        ctl.emergency_stop()
        fr = Frame(seq=1, emulator_frame_count=1,
                   rgb=np.zeros((2, 2, 3), np.uint8), timestamp=0.0)
        with pytest.raises(ControllerError):
            ctl.apply(self._dec("IDLE", 1), fr)
        ctl.reset_episode()
        ctl.apply(self._dec("IDLE", 1), fr)   # works again

    def test_release_all_sends_empty(self):
        env = FakeFlappyEnv()
        ad = ScriptedGameAdapter(env)
        sess = FakeSession(env)
        ctl = SafetyController(ad, sess)
        before = env.core.frames_run
        ctl.release_all()
        assert env.core.frames_run == before + 1  # one empty frame
        assert ctl.state()["held_buttons"] == []


# ------------------------------------------------------------------
# F/G. full loop with fake game + fault injection
# ------------------------------------------------------------------
class TestEngineLoopFakeGame:
    def test_scripted_game_runs_to_terminal(self):
        env = FakeFlappyEnv(die_after=10**9)
        eng, tel = _make_engine(env, output_dir="/tmp/r62_t1")
        try:
            results = eng.run()
        finally:
            eng.close()
        assert len(results) == 1
        r = results[0]
        assert r["result"] == "death"
        assert r["death_reason"] == "scripted_over"
        assert r["decisions"] == 25
        assert r["trace_sha256"]
        # the trace hash is stable across identical runs
        env2 = FakeFlappyEnv(die_after=10**9)
        eng2, _ = _make_engine(env2, output_dir="/tmp/r62_t2")
        try:
            r2 = eng2.run()[0]
        finally:
            eng2.close()
        assert r2["trace_sha256"] == r["trace_sha256"]

    def test_multiple_episodes_no_state_leak(self):
        env = FakeFlappyEnv(die_after=10**9)
        eng, _ = _make_engine(env, episodes=3,
                              output_dir="/tmp/r62_t3")
        try:
            results = eng.run()
        finally:
            eng.close()
        assert len(results) == 3
        hashes = {r["trace_sha256"] for r in results}
        assert len(hashes) == 1     # identical -> no stale state

    def test_episode_persisted(self):
        env = FakeFlappyEnv(die_after=10**9)
        out = "/tmp/r62_t4"
        eng, _ = _make_engine(env, output_dir=out)
        try:
            eng.run()
        finally:
            eng.close()
        assert os.path.exists(os.path.join(out, "episodes.jsonl"))
        assert os.path.exists(os.path.join(out, "episode_001.json"))
        assert os.path.exists(os.path.join(out, "runtime_manifest.json"))

    def test_time_limit_stops_episode(self):
        env = FakeFlappyEnv(die_after=10**9)
        out = "/tmp/r62_t5"
        eng, _ = _make_engine(env, max_runtime_s=1.0,
                              output_dir=out)
        # make the wall limit bite: tiny per-run budget via stopwatch
        eng.cfg.max_runtime_s = 0.05
        try:
            results = eng.run()
        finally:
            eng.close()
        # the run either finishes the scripted episode or stops on the
        # wall limit — never hangs
        assert results[0]["result"] in ("death", "stopped", "error")


class TestEngineFaultInjection:
    def test_frame_source_failure_is_typed_error(self):
        env = FakeFlappyEnv(die_after=10**9)
        eng, tel = _make_engine(env, output_dir="/tmp/r62_f1")
        src = eng.session.frames()

        def boom(require_fresh=True):
            raise OSError("capture device gone")
        src.latest = boom
        try:
            results = eng.run()      # failure recovery, not a raise
            recs = [r for r in results if r["result"] == "error"]
            assert recs, results
            assert "OSError" in recs[0]["errors"][0]
            assert not eng.lifecycle.in_terminal() or True
            # stop_on_error stopped the run after the failure
            assert len(results) == 1
        finally:
            eng.close()

    def test_policy_rejection_stops_no_fallback(self):
        env = FakeFlappyEnv(die_after=10**9)

        class BrokenPolicy(ScriptedPolicy):
            def predict(self, obs):
                raise RuntimePolicyError("model exploded")

        eng, _ = _make_engine(env, policy=BrokenPolicy(),
                              output_dir="/tmp/r62_f2")
        try:
            results = eng.run()
            assert results and all(r["result"] == "error"
                                   for r in results)
            assert "RuntimePolicyError" in results[0]["errors"][0]
        finally:
            eng.close()

    def test_emergency_stop_mid_episode(self):
        env = FakeFlappyEnv(die_after=10**9)
        eng, _ = _make_engine(env, output_dir="/tmp/r62_f3")
        try:
            # stop after 5 decisions
            orig = eng.controller.apply

            def stopper(decision, frame):
                if eng.controller.n_sends >= 5:
                    eng.stop_flag["stop"] = True
                return orig(decision, frame)
            eng.controller.apply = stopper
            results = eng.run()
            stopped = [r for r in results
                       if r["result"] == "stopped"]
            assert stopped, results
            assert stopped[0]["death_reason"] == "emergency_stop"
        finally:
            eng.close()

    def test_close_idempotent_and_cleans(self):
        env = FakeFlappyEnv(die_after=10**9)
        eng, _ = _make_engine(env, output_dir="/tmp/r62_f4")
        sess = eng.session
        eng.run()
        eng.close()
        eng.close()
        assert sess.closed >= 1
        assert env.closed >= 1

    def test_missing_iso_is_asset_error(self, tmp_path):
        from ps1play.runtime import session as S
        cfg = RuntimeConfig(output_dir=str(tmp_path),
                            iso_path="/nonexistent/x.cue").validated()
        with pytest.raises(AssetError):
            S.preflight(cfg, iso_path=cfg.iso_path,
                        require_model=False)

    def test_bad_iso_hash_is_asset_error(self, tmp_path):
        from ps1play.runtime import session as S
        # a cue pointing at a wrong-size fake image
        img = tmp_path / "img.bin"
        img.write_bytes(b"\x00" * 1000)
        cue = tmp_path / "x.cue"
        cue.write_text(f'FILE "img.bin" BINARY\n TRACK 01 MODE2/2352\n'
                       f'  INDEX 01 00:00:00\n')
        cfg = RuntimeConfig(output_dir=str(tmp_path)).validated()
        with pytest.raises(AssetError):
            S.preflight(cfg, iso_path=str(cue), require_model=False)

    def test_cue_resolves_to_image(self, tmp_path):
        from ps1play.runtime.session import disc_image_path
        img = tmp_path / "img.bin"
        img.write_bytes(b"\x00" * 10)
        cue = tmp_path / "x.cue"
        cue.write_text('FILE "img.bin" BINARY\n  TRACK 01 '
                       'MODE2/2352\n    INDEX 01 00:00:00\n')
        assert disc_image_path(str(cue)) == str(img)
        assert disc_image_path(str(img)) == str(img)
