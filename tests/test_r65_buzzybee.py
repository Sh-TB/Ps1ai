"""R65 BuzzyBee tests — offline contract tests (no emulator) + the
registry wiring.  Real-emulator integration lives in
test_r65_integration.py (skips honestly without the disc).

Everything here is GAME-SPECIFIC to BuzzyBee and imports nothing from
any other game's plugin (the isolation rule).
"""
import hashlib
import os
import sys

import numpy as np
import pytest

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

from ps1play.adapters.buzzybee import adapter as ba          # noqa: E402
from ps1play.adapters.buzzybee import policy as bp           # noqa: E402
from ps1play.adapters.buzzybee.adapter import BuzzyBeeAdapter  # noqa: E402
from ps1play.adapters.buzzybee.policy import BuzzyPolicy     # noqa: E402
from ps1play.runtime.errors import EmulatorError             # noqa: E402
from ps1play.runtime.interfaces import (ActionDecision, Frame,  # noqa: E402
                                        GameObservation)

RAM_BYTES = 2 * 1024 * 1024


def _ram_with(**fields):
    """A 2MB RAM image with the given anchor values set."""
    ram = np.zeros(RAM_BYTES, dtype=np.uint8)
    a4 = ram.view("<i4")

    def put(va, val):
        a4[(va - 0x80000000) // 4] = val

    put(ba.GS, fields.get("gs", 1))
    put(ba.BEST, fields.get("best", 123))
    put(ba.SCORE, fields.get("score", 0))
    put(ba.HEALTH, fields.get("hp", 5999))
    put(ba.PLAYER + 0x0C, fields.get("by", 100 * 1024))
    put(ba.PLAYER + 0x10, fields.get("bx", 26 * 1024))
    put(ba.PLAYER + 0x14, fields.get("bxv", 0))
    put(ba.PLAYER + 0x18, fields.get("bvy", 0))
    put(ba.ENEMY + 0x0C, fields.get("ey", 60 * 1024))
    put(ba.ENEMY + 0x10, fields.get("ex", 200 * 1024))
    put(ba.ENEMY + 0x14, fields.get("exv", 0))
    put(ba.ENEMY + 0x18, fields.get("evy", 1536))
    for i in range(3):
        base = ba.FLOWERS + ba.FLOWER_STRIDE * i
        fx, fy = fields.get(f"f{i}", (-50 * 1024, 50 * 1024))
        put(base + 0x0C, fy)
        put(base + 0x10, fx)
    return ram


class FakeEnv:
    """Minimal env object: RAM + run() call recording."""

    def __init__(self, ram=None):
        self.ram = _ram_with() if ram is None else ram
        self.p = self
        self.mem = self
        self.calls = []          # (frames, buttons)
        self.gs = 1

    def snapshot(self):
        return bytes(self.ram)

    def run(self, frames, buttons=frozenset()):
        self.calls.append((int(frames), frozenset(buttons)))
        # the R65-measured state machine: gs=5 (game over) auto-returns
        # to the title on idle frames; the title takes START -> PLAYING
        a4 = self.ram.view("<i4")
        gi = (ba.GS - 0x80000000) // 4
        gs = int(a4[gi])
        if gs == ba.GS_OVER and "START" not in buttons:
            a4[gi] = ba.GS_TITLE
        elif gs == ba.GS_TITLE and "START" in buttons:
            a4[gi] = ba.GS_PLAYING
        return frames

    # -- state-change helpers --
    def set(self, **fields):
        self.ram = _ram_with(**fields)


def _frame(seq=1):
    import time
    return Frame(seq=seq, emulator_frame_count=seq,
                 rgb=np.zeros((4, 4, 3), dtype=np.uint8),
                 timestamp=time.time())


def _dec(action, seq=1):
    return ActionDecision(action=action, logits=None, frame_seq=seq,
                          policy_name="p", policy_sha256="s",
                          latency_ms=0.0)


# ---------------------------------------------------------------- --
# A. adapter
# ---------------------------------------------------------------- --
class TestAdapter:
    def test_observation_layout(self):
        env = FakeEnv(_ram_with(score=42, gs=1, by=90 * 1024,
                                ex=150 * 1024, ey=50 * 1024,
                                evy=2048 * 1024 // 1024 * 1024))
        a = BuzzyBeeAdapter(env)
        obs = a.observe(_frame())
        assert obs.valid and obs.values.shape == (15,)
        v = obs.values
        assert v[0] == pytest.approx(90.0)          # by in px
        assert v[2] == pytest.approx(150.0)         # ex
        assert v[3] == pytest.approx(50.0)          # ey
        assert v[11] == pytest.approx(42.0)         # score
        assert v[12] == pytest.approx(1.0)          # gs
        assert v[13] == pytest.approx(5999.0)       # hp
        assert v[14] == pytest.approx(123.0)        # best
        # inactive flowers carry x<=0 verbatim
        assert v[5] <= 0 and v[7] <= 0 and v[9] <= 0

    def test_px_is_c_truncation(self):
        assert ba.px(-1536) == -1          # toward zero, not floor
        assert ba.px(1536) == 1
        assert ba.px(-1023) == 0

    def test_wait_ready_starts_from_title(self):
        env = FakeEnv(_ram_with(gs=0))
        a = BuzzyBeeAdapter(env)
        assert a.wait_ready(30.0) is True
        assert any("START" in b for _f, b in env.calls)

    def test_wait_ready_times_out(self):
        env = FakeEnv(_ram_with(gs=99))    # never becomes PLAYING
        a = BuzzyBeeAdapter(env)
        with pytest.raises(EmulatorError):
            a.wait_ready(0.15)

    def test_start_episode_reuses_playing_state(self):
        env = FakeEnv(_ram_with(gs=1))
        a = BuzzyBeeAdapter(env)
        assert a.start_episode(6) == 0
        assert not any("START" in b for _f, b in env.calls)

    def test_start_episode_recovers_from_game_over(self):
        """gs=5 -> (auto) title -> START -> PLAYING, all legal menu
        input through the adapter's recovery."""
        env = FakeEnv(_ram_with(gs=5))
        a = BuzzyBeeAdapter(env)
        assert a.start_episode(12) == 0
        assert any("START" in b for _f, b in env.calls)

    def test_legal_actions_and_buttons(self):
        a = BuzzyBeeAdapter(FakeEnv())
        assert set(a.legal_actions()) == {"HOVER", "FLAP"}
        assert a.action_to_buttons("HOVER") == frozenset()
        assert a.action_to_buttons("FLAP") == frozenset({"B"})
        with pytest.raises(Exception):
            a.action_to_buttons("LEFT")

    def test_flap_press_pipeline_is_two_frames_plus_idle(self):
        """The proven r45-B press: B,B, idle — one impulse per press."""
        a = BuzzyBeeAdapter(FakeEnv())
        seq = [a.action_to_buttons("FLAP"),
               a.action_to_buttons("HOVER"),
               a.action_to_buttons("HOVER"),
               a.action_to_buttons("HOVER")]
        assert seq[0] == frozenset({"B"})
        assert seq[1] == frozenset({"B"})   # the 2nd frame
        assert seq[2] == frozenset()        # the forced idle frame
        assert seq[3] == frozenset()        # normal hover
        # a fresh FLAP after the pipeline works again
        assert a.action_to_buttons("FLAP") == frozenset({"B"})

    def test_post_advance_terminal_on_game_over(self):
        a = BuzzyBeeAdapter(FakeEnv(_ram_with(gs=1, score=10)))
        a.start_episode(6)
        post = a.post_advance(_frame())
        assert post["terminal"] is False and post["pipes"] == 10
        env2 = FakeEnv(_ram_with(gs=5, score=1000))
        a2 = BuzzyBeeAdapter(env2)     # no start_episode: gs=5 as-is
        post2 = a2.post_advance(_frame())
        assert post2["terminal"] is True
        assert post2["death_reason"] == "game_over"

    def test_episode_stats_carry_score(self):
        a = BuzzyBeeAdapter(FakeEnv(_ram_with(score=77)))
        a.observe(_frame())
        stats = a.episode_stats()
        assert stats["pipes"] == 77


# ---------------------------------------------------------------- --
# B. policy (the R48-B invariants, ported)
# ---------------------------------------------------------------- --
class TestPolicyPlanner:
    def test_predict_shape_contract(self):
        p = BuzzyPolicy()
        v = np.zeros(15, dtype=np.float32)
        v[12] = 1.0
        obs = GameObservation(values=v, frame_seq=1, frame_id="f1",
                              timestamp=0.0, valid=True)
        d = p.predict(obs)
        assert d.action in ("HOVER", "FLAP")

    def test_predict_refuses_invalid(self):
        p = BuzzyPolicy()
        obs = GameObservation(values=None, frame_seq=1, frame_id="f1",
                              timestamp=0.0, valid=False,
                              invalid_reason="x")
        with pytest.raises(Exception):
            p.predict(obs)
        obs2 = GameObservation(values=np.zeros(10, dtype=np.float32),
                               frame_seq=1, frame_id="f1",
                               timestamp=0.0, valid=True)
        with pytest.raises(Exception):
            p.predict(obs2)

    def test_not_playing_is_idle(self):
        p = BuzzyPolicy()
        v = np.zeros(15, dtype=np.float32)
        v[12] = 5.0
        obs = GameObservation(values=v, frame_seq=1, frame_id="f1",
                              timestamp=0.0, valid=True)
        d = p.predict(obs)
        assert d.action == "HOVER"
        assert d.diagnostics["mode"] == "not_playing"

    def test_bail_targets_the_safe_extreme(self):
        """A wasp sweeping the whole column during the window -> no
        candidate is guaranteed -> the bail path (planned=False)."""
        sticky = {}
        flap, tgt, side, planned, gm, sh = bp.plan_exit8(
            95.0, 0, 2.0, 3.2, 30.0, [], sticky)
        assert planned is False               # the bail path
        assert bp.Y_MIN <= tgt <= bp.Y_MAX

    def test_committed_hold_survives_frames(self):
        """The COMMITTED pre-danger hold: the same (side, target) is
        reused across frames while it stays guaranteed."""
        sticky = {}
        ey, evy, ex = 40.0, 0.0, 120.0
        r1 = bp.plan_exit8(95.0, 0, ey, evy, ex, [], sticky)
        by2 = r1[1] + 1.0
        r2 = bp.plan_exit8(by2, 0, ey, evy, ex - 1.5, [], sticky)
        if sticky.get("hold8") is not None or r1[3]:
            assert r2[2] == r1[2]

    def test_no_wasp_flower_seek(self):
        p = BuzzyPolicy()
        p.reset()
        v = np.zeros(15, dtype=np.float32)
        v[12] = 1.0
        v[0] = 100.0            # by
        v[2] = -60.0            # wasp far past
        v[5], v[6] = 80.0, 60.0   # flower 0 ahead
        obs = GameObservation(values=v, frame_seq=1, frame_id="f1",
                              timestamp=0.0, valid=True)
        d = p.predict(obs)
        assert d.diagnostics["mode"] == "flower"
        assert d.diagnostics["target"] == pytest.approx(65.0)

    def test_reset_clears_sticky_state(self):
        p = BuzzyPolicy()
        p.reset()
        v = np.zeros(15, dtype=np.float32)
        v[12] = 1.0
        v[2] = 100.0
        obs = GameObservation(values=v, frame_seq=1, frame_id="f1",
                              timestamp=0.0, valid=True)
        p.predict(obs)
        assert p._sticky                      # state was built
        p.reset()
        assert p._sticky == {}

    def test_identity_pins_the_policy_source(self):
        p = BuzzyPolicy()
        src = os.path.join(REPO, "ps1play/adapters/buzzybee/policy.py")
        with open(src, "rb") as f:
            src_sha = hashlib.sha256(f.read()).hexdigest()
        assert p.identity()["model_sha256"] == src_sha
        assert "training" in p.identity()["kind"]


# ---------------------------------------------------------------- --
# C. registry wiring
# ---------------------------------------------------------------- --
class TestRegistry:
    def test_buzzybee_is_registered(self):
        from ps1play.runtime.registry import (registered_games,
                                              progress_label_for)
        assert "buzzybee" in registered_games()
        assert progress_label_for("buzzybee") == "score"

    def test_adapter_policy_factories(self):
        from ps1play.runtime import registry as R
        ent = R._REGISTRY["buzzybee"]
        assert ent["adapter"] is BuzzyBeeAdapter
        pol = ent["policy_factory"](None)
        assert isinstance(pol, BuzzyPolicy)

    def test_disc_pin_present(self):
        from ps1play.runtime.session import (GAME_DEFAULT_ISO,
                                             EXPECTED_ISO_SHA)
        assert "buzzybee" in GAME_DEFAULT_ISO
        assert "buzzybee" in EXPECTED_ISO_SHA
        assert len(EXPECTED_ISO_SHA["buzzybee"]) == 64
