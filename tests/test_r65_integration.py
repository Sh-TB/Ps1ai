"""R65 BuzzyBee integration — REAL emulator tests.

The repo convention (R61/R62/R64): real-emulator tests run when the
assets are present and skip honestly otherwise.  One shared boot per
module, through the REAL RuntimeEngine (the product path).

  A. the engine boots BuzzyBee, wait_ready VERIFIES the ready state
     (gs=1 PLAYING), and a short episode plays with the built-in
     bot_policy8 — the score advances (the +1/frame law).
  B. the episode record contract: the generic progress counter carries
     the score; the policy identity is the hand-written heuristic.
"""
import os
import sys

import pytest

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

CUE = ("/home/z/my-project/emu/games_homebrew/patched/"
       "buzzybee_ntsc_lic.cue")

pytestmark = pytest.mark.skipif(not os.path.exists(CUE),
                                reason="buzzybee disc not present "
                                       "on this machine")


@pytest.fixture(scope="module")
def run_result():
    from ps1play.runtime.config import RuntimeConfig
    from ps1play.runtime.engine import RuntimeEngine
    from ps1play.runtime.telemetry import TelemetryLog
    out = "/tmp/r65_integration/module"
    os.makedirs(out, exist_ok=True)
    cfg = RuntimeConfig(
        game="buzzybee", episodes=1, seed_k=6,
        max_frames_per_episode=600, max_runtime_s=120.0,
        output_dir=out)
    cfg.validated()
    tel = TelemetryLog(os.path.join(out, "events.jsonl"),
                       run_meta={"cmd": "test"}, echo=False)
    engine = RuntimeEngine(cfg, tel)
    try:
        assets = engine.preflight()
        engine.boot(assets)
        results = engine.run()
        yield results
    finally:
        engine.close()
        tel.close()


class TestRealEngine:
    def test_episode_plays_and_scores(self, run_result):
        assert len(run_result) == 1
        r = run_result[0]
        assert r["result"] in ("alive", "death")
        assert r["frames"] >= 300
        # the score law: +1 per play frame (>= half the budget)
        assert r["pipes"] >= 0.5 * r["frames"]

    def test_record_contract(self, run_result):
        r = run_result[0]
        assert r["game"] == "buzzybee"
        assert len(r["policy_sha256"]) == 64
        assert "hand-written" in r["policy_name"]
        assert r["trace_sha256"]
