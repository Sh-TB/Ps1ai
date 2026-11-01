"""R62 runtime integration — REAL emulator tests.

Follows the repo's R61 convention: real-emulator tests run when the
assets are present (they are on every dev machine used by this
project) and skip honestly otherwise. One shared boot per module keeps
the suite cost bounded (~2.5 min).

  E. emulator integration: boot, ordered capture, staleness, input,
     reset, shutdown
  F. full loop: the engine drives the REAL game through the REAL
     frozen policy and BYTE-MATCHES the R61 family record (k=45:
     40 pipes @ 4753 frames) — twice in one session to prove no
     state leaks across episodes.
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
if PKG not in sys.path:
    sys.path.insert(0, PKG)

ISO = "/home/z/my-project/emu/games_homebrew/flappybird.cue"

pytestmark = pytest.mark.skipif(not os.path.exists(ISO),
                                reason="emulator assets not present "
                                       "on this machine")


def _family_ref(k=45):
    with open(os.path.join(REPO, "data", "learn",
                           "r61_family_rows.jsonl")) as f:
        for line in f:
            r = json.loads(line)
            if int(r["k"]) == k:
                return r
    raise AssertionError("no k=45 family record")


@pytest.fixture(scope="module")
def session():
    from ps1play.runtime.config import RuntimeConfig
    from ps1play.runtime.session import EnvSession
    cfg = RuntimeConfig(
        output_dir="/tmp/r62_integration",
        max_frames_per_episode=10000).validated()
    os.makedirs(cfg.output_dir, exist_ok=True)
    sess = EnvSession.boot_new(cfg, deadline_s=180)
    yield sess
    sess.close()


class TestEmulatorIntegration:
    def test_boot_and_tag(self, session):
        assert session.alive()
        assert "mednafen_psx" in session.tag()

    def test_ordered_capture_and_staleness(self, session):
        session.advance(3, frozenset())
        src = session.frames()
        f1 = src.latest(require_fresh=False)
        f2 = src.latest(require_fresh=False)
        assert f2.seq == f1.seq + 1
        assert f2.stale            # nothing rendered between reads
        assert f2.emulator_frame_count == f1.emulator_frame_count
        session.advance(1, frozenset())
        f3 = src.latest(require_fresh=True)
        assert f3.emulator_frame_count == f1.emulator_frame_count + 1
        assert not f3.stale
        assert f3.rgb.ndim == 3 and f3.rgb.dtype == np.uint8

    def test_input_advances_and_frame_follows(self, session):
        src = session.frames()
        session.advance(60, frozenset())    # past the black boot frames
        f = src.latest(require_fresh=True)   # must be NEW
        assert f.emulator_frame_count > 0
        # by now the BIOS/video output is a real rendered image
        assert f.rgb.std() > 0.0


class TestFullLoopByteMatch:
    def test_two_consecutive_episodes_match_r61_record(self,
                                                       session):
        """The decisive full-loop proof: the engine + adapter + frozen
        policy reproduce the R61 k=45 record BYTE-EXACTLY, twice, in
        one session (no stale perception/controller/emulator state)."""
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.engine import RuntimeEngine
        from ps1play.runtime.telemetry import TelemetryLog
        ref = _family_ref(45)
        out = "/tmp/r62_integration/loop"
        os.makedirs(out, exist_ok=True)
        for f in ("episodes.jsonl", "events.jsonl"):
            p = os.path.join(out, f)
            if os.path.exists(p):
                os.remove(p)
        cfg = RuntimeConfig(output_dir=out, episodes=2, seed_k=45,
                            max_frames_per_episode=10000,
                            max_runtime_s=600).validated()
        tel = TelemetryLog(os.path.join(out, "events.jsonl"))
        eng = RuntimeEngine(cfg, tel)
        eng.session = session        # reuse the module boot
        try:
            from ps1play.runtime.registry import adapter_for_game
            eng.adapter = adapter_for_game("flappybird", session.env,
                                           telemetry=tel)
            from ps1play.runtime.policy_runtime import RuntimePolicy
            eng.policy = RuntimePolicy(cfg, telemetry=tel)
            from ps1play.runtime.controller import SafetyController
            eng.controller = SafetyController(eng.adapter, session,
                                              telemetry=tel)
            eng.manifest = {"test": "integration"}
            eng.manifest_hash = "integration"
            from ps1play.runtime.lifecycle import Lifecycle
            eng.lifecycle.transition("BOOTING")
            eng.lifecycle.transition("READY")
            results = eng.run()
        finally:
            tel.close()
        assert len(results) == 2
        for r in results:
            assert r["result"] == ref["result"]
            assert r["pipes"] == ref["pipes"]
            assert r["frames"] == ref["frames"]
            assert r["flaps"] == ref["flaps"]
            assert r["trace_sha256"] == ref["trace_sha256"], \
                "byte-mismatch vs the R61 k=45 record"
        # identical to each other (deterministic restart)
        assert results[0]["trace_sha256"] == \
            results[1]["trace_sha256"]
