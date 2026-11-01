"""R64 Tetrade integration — REAL emulator tests.

Follows the repo convention (R61/R62): real-emulator tests run when
the assets are present and skip honestly otherwise. One shared BOOT
per module — through the REAL RuntimeEngine (the product path), so
every test benefits from the engine's boot-retry (beetle's in-process
boot may stick at the OpenBIOS cube; the engine re-boots a fresh
core — observed and recorded 2026-11-01).

  E. engine boot: the registry-built Tetrade env boots, wait_ready
     VERIFIES the ready state (fresh Marathon, struct at the
     twice-observed 0x1FECA0), RAM reads return a live game.
  F. engine loop: the REAL RuntimeEngine plays tetrade through the
     built-in Dellacherie policy — two short episodes in ONE launch
     prove the restart flow (CONTINUE refused -> fresh Marathon) and
     the per-episode record contract.
"""
import os
import sys

import pytest

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"

pytestmark = pytest.mark.skipif(not os.path.exists(CUE),
                                reason="tetrade disc not present "
                                       "on this machine")


@pytest.fixture(scope="module")
def engine():
    from ps1play.runtime.config import RuntimeConfig
    from ps1play.runtime.engine import RuntimeEngine
    from ps1play.runtime.telemetry import TelemetryLog
    out = "/tmp/r64_integration/module"
    os.makedirs(out, exist_ok=True)
    cfg = RuntimeConfig(
        game="tetrade", output_dir=out,
        max_frames_per_episode=10000).validated()
    tel = TelemetryLog(os.path.join(out, "events.jsonl"), echo=False)
    eng = RuntimeEngine(cfg, tel)
    try:
        eng.boot(eng.preflight())
        yield eng
    finally:
        tel.close()
        eng.close()


class TestEmulatorIntegration:
    def test_boot_tag_and_registry_env(self, engine):
        assert engine.session.alive()
        assert "beetle" in engine.session.tag()
        from ps1play.adapters.tetrade import TetradeAdapter
        assert isinstance(engine.adapter, TetradeAdapter)
        # the policy came from the registry's built-in factory
        assert engine.policy.identity()["name"].startswith(
            "tetrade_dellacherie")

    def test_verified_ready_state(self, engine):
        """wait_ready VERIFIED: fresh Marathon running, struct located
        at the base observed by two independent prior boots (the
        round-10 prior, Oct-26, and R63, Nov-1)."""
        a = engine.adapter
        assert a._base == 0x1FECA0, \
            f"struct base {hex(a._base)} != the 0x1FECA0 prior"
        st = a._read_state()
        assert st["level"] == 0 and st["score"] == 0
        assert not st["over"] and not st["paused"]
        # a live piece or the transient respawn state — the board is
        # fresh (empty or the first piece's cells)
        assert int((st["board"] > 0).sum()) <= 4
        # observation is valid and shaped
        from ps1play.runtime.interfaces import Frame
        import numpy as np
        fr = Frame(seq=1, emulator_frame_count=1,
                   rgb=np.zeros((4, 4, 3), dtype=np.uint8),
                   timestamp=0.0)
        o = a.observe(fr)
        assert o.valid and o.values.shape == (222,)
        assert a.episode_stats()["pipes"] == 0
        # episode 1 reuses the verified ready state
        assert a.start_episode(6) == 0
        a.reset_episode()

    def test_short_engine_episode(self, engine):
        """One REAL short episode through the FULL engine (policy ->
        controller -> adapter), result record contract held."""
        import time as _t
        cfg = engine.cfg
        out = "/tmp/r64_integration/ep1"
        os.makedirs(out, exist_ok=True)
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.telemetry import TelemetryLog
        from ps1play.runtime.engine import RuntimeEngine
        cfg2 = RuntimeConfig(
            game="tetrade", output_dir=out, episodes=1,
            max_frames_per_episode=450, max_runtime_s=90.0,
            seed_k=6).validated()
        tel = TelemetryLog(os.path.join(out, "events.jsonl"),
                           echo=False)
        eng = RuntimeEngine(cfg2, tel)
        try:
            eng.boot(eng.preflight())
            assert eng.policy.identity()["name"].startswith(
                "tetrade_dellacherie")
            t0 = _t.time()
            results = eng.run()
            assert _t.time() - t0 < 80
        finally:
            tel.close()
        assert len(results) == 1
        r = results[0]
        assert r["game"] == "tetrade"
        assert r["result"] in ("death", "alive", "stopped")
        assert r["decisions"] > 0 and r["actions"] > 0
        assert len(r["trace_sha256"]) == 64
        assert r["policy_name"].startswith("tetrade_dellacherie")
        assert r["manifest_sha256"]
        # the record's flaps/actions columns carry REAL button presses
        # for any game (tetrade: rotate/move/drop presses — no FLAP
        # action exists in its vocabulary)
        assert r["flaps"] == r["actions"]
        assert r["actions"] > 0


class TestEngineRestartFlow:
    def test_two_episodes_one_launch(self):
        """Episode 2 must go through the R63 restart flow and start
        FRESH — the #8 re-delivery property, now through the product
        path (with the engine's boot-retry protecting the launch)."""
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.engine import RuntimeEngine
        from ps1play.runtime.telemetry import TelemetryLog
        out = "/tmp/r64_integration/ep2"
        os.makedirs(out, exist_ok=True)
        cfg = RuntimeConfig(
            game="tetrade", output_dir=out, episodes=2,
            max_frames_per_episode=380, max_runtime_s=150.0,
            seed_k=6).validated()
        tel = TelemetryLog(os.path.join(out, "events.jsonl"),
                           echo=False)
        eng = RuntimeEngine(cfg, tel)
        try:
            eng.boot(eng.preflight())
            results = eng.run()
        finally:
            eng.close()
            tel.close()
        assert len(results) == 2
        ep1, ep2 = results
        assert ep1["episode"] == 1 and ep2["episode"] == 2
        for r in results:
            assert r["result"] in ("death", "alive", "stopped")
            assert r["trace_sha256"]
        # the restart reached a FRESH Marathon: episode 2 actually
        # played (decisions happened) after the continue refusal
        assert ep2["decisions"] > 0
