"""tests/test_learn_features_v2.py — the P4 feature/brain upgrade.

Covers:
  * _small_rgb fast path == loop reference (dataset consistency)
  * v1 feature functions unchanged (shapes; the r53 datasets stay valid)
  * pong v2 predictive feature (extrapolation + wall fold + fallbacks)
  * flappy v2 gap-edge features consistent with the v1 gap center
  * Brain(artifact, feature_version=2) == manual feature+forward, and
    its OWN-history plumbing (prev action / since flap) + determinism
Causality: every feature consumes [t-1, t] only — asserted by
construction here (no future argument exists in the signatures).
"""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

from ps1play.learn.games import _small_rgb, _small_rgb_ref  # noqa: E402
from ps1play.learn import visual_only as VO                 # noqa: E402
from ps1play.learn.policy import TinyMLP                    # noqa: E402


def _synth_pong_frame(ball_xy=None, pad_l=120, pad_r=90):
    fr = np.zeros((240, 320, 3), dtype=np.uint8)
    fr[...] = (20, 20, 20)                      # dark field
    if ball_xy is not None:
        x, y = int(ball_xy[0]), int(ball_xy[1])
        fr[y:y + 8, x:x + 8] = (255, 255, 255)  # ball blob
    fr[pad_l - 20:pad_l + 20, 8:16] = (255, 255, 255)
    fr[pad_r - 20:pad_r + 20, 300:308] = (255, 255, 255)
    return fr


def test_smallrgb_fast_equals_ref():
    rng = np.random.default_rng(3)
    for _ in range(10):
        fr = rng.integers(0, 256, (240, 320, 3), dtype=np.uint8)
        assert np.array_equal(_small_rgb(fr), _small_rgb_ref(fr))
    # structured frame too (flat regions, hard rounding cases)
    fr = np.zeros((240, 320, 3), dtype=np.uint8)
    fr[::2, ::2] = 255
    assert np.array_equal(_small_rgb(fr), _small_rgb_ref(fr))


def test_v1_feature_shapes_unchanged():
    fr = _synth_pong_frame((160, 120))
    small = _small_rgb(fr)
    f1 = VO.features_pong(small, None)
    assert f1.shape == (6,)
    ff = VO.features_flappy(np.zeros((60, 80, 3), np.uint8), None)
    assert ff.shape == (4,)


def test_pong_v2_predictive_intercept():
    # ball at (200, 60) moving LEFT 2 px/step and DOWN 1 px/step:
    # reaches x=24 after (200-24)/2 = 88 steps -> pred y = 60 + 88 = 148
    cur = _small_rgb(_synth_pong_frame((200, 60)))
    prev = _small_rgb(_synth_pong_frame((204, 58)))
    f = VO.features_pong_v2(cur, prev)
    assert f.shape == (9,)
    assert abs(f[0] - 200.0) <= 6.0               # cx near 200 (scaled)
    steps = (24.0 - f[0]) / f[2]
    expect = VO._fold_playfield(f[1] + f[3] * steps)
    assert abs(f[6] - expect) < 1e-3              # pred_y == manual fold
    # ball moving RIGHT -> pred_y falls back to the CURRENT cy
    cur2 = _small_rgb(_synth_pong_frame((100, 80)))
    prev2 = _small_rgb(_synth_pong_frame((96, 82)))
    f2 = VO.features_pong_v2(cur2, prev2)
    assert abs(f2[6] - f2[1]) < 1e-3
    # no ball visible -> 120 fallback
    f3 = VO.features_pong_v2(_small_rgb(_synth_pong_frame(None)), None)
    assert abs(f3[6] - 120.0) < 1e-3


def test_pong_v2_policy_history_dims():
    cur = _small_rgb(_synth_pong_frame((160, 120)))
    fu = VO.features_pong_v2(cur, None, prev_action="UP")
    fd = VO.features_pong_v2(cur, None, prev_action="DOWN")
    fn = VO.features_pong_v2(cur, None, prev_action=None)
    assert fu[7] == 1.0 and fu[8] == 0.0
    assert fd[7] == 0.0 and fd[8] == 1.0
    assert fn[7] == 0.0 and fn[8] == 0.0
    # the v1 prefix is identical regardless of history
    assert np.array_equal(fu[:6], fn[:6])


def test_wall_fold():
    assert VO._fold_playfield(250.0) == pytest.approx(230.0)
    assert VO._fold_playfield(-10.0) == pytest.approx(10.0)
    assert VO._fold_playfield(120.0) == pytest.approx(120.0)
    assert VO._fold_playfield(500.0) == pytest.approx(20.0)


def _synth_flappy_frame(bird_y=120, gap_rows=(60, 100), gap_x=200):
    fr = np.zeros((240, 320, 3), dtype=np.uint8)
    fr[...] = (80, 160, 200)                    # teal sky
    # pipes: green columns with a gap
    if gap_rows is not None:
        g0, g1 = gap_rows
        for x0 in (gap_x, gap_x + 60):
            fr[20:g0, x0:x0 + 24] = (60, 180, 60)
            fr[g1:200, x0:x0 + 24] = (60, 180, 60)
    # bird: yellow 20x14 blob at x=130
    fr[bird_y - 7:bird_y + 7, 130:150] = (230, 210, 60)
    return fr


def test_flappy_v2_gap_edges_consistent_with_v1():
    cur = _small_rgb(_synth_flappy_frame(bird_y=120, gap_rows=(60, 100)))
    f1 = VO.features_flappy(cur, None)
    f2 = VO.features_flappy_v2(cur, None)
    assert f2.shape == (8,)
    # v1 prefix identical
    assert np.array_equal(f2[:4], f1)
    if f2[2] > 0:                                # a gap was found
        center = (f2[4] + f2[5]) / 2.0
        assert abs(center - f2[2]) < 2.0         # edges bracket the center
        assert f2[5] > f2[4] >= 0                # top above bottom


def test_flappy_v2_history_dims():
    cur = _small_rgb(_synth_flappy_frame())
    a = VO.features_flappy_v2(cur, None, prev_action="FLAP", since_flap=0)
    b = VO.features_flappy_v2(cur, None, prev_action=None, since_flap=7)
    c = VO.features_flappy_v2(cur, None, prev_action=None,
                              since_flap=99)
    assert a[6] == 1.0 and a[7] == 0.0
    assert b[6] == 0.0 and b[7] == 7.0
    assert c[7] == 10.0                          # capped at 10
    assert np.array_equal(a[:6], b[:6])


def test_brain_v2_matches_manual_forward(tmp_path):
    rng = np.random.default_rng(5)
    net = TinyMLP(9, 8, 3, seed=5)
    net.W1 = rng.standard_normal(net.W1.shape).astype(np.float32)
    net.W2 = rng.standard_normal(net.W2.shape).astype(np.float32)
    art = str(tmp_path / "t.npz")
    info = net.save_artifact(art, meta={
        "game": "pong", "control_mode": "cv+mlp", "feature_version": 2,
        "classes": ["DOWN", "NONE", "UP"],
        "norm": {"mean": np.zeros(9).tolist(),
                 "std": np.ones(9).tolist()}})
    assert info["npz_bytes"] <= 4 * 1024 * 1024
    with open(art + ".json") as f:
        assert json.load(f)["feature_version"] == 2

    brain = VO.Brain(art)
    prev = _small_rgb(_synth_pong_frame((204, 58)))
    cur = _small_rgb(_synth_pong_frame((200, 60)))
    a1 = brain.act(prev)
    a2 = brain.act(cur)
    # manual: same two frames through the SAME feature+forward path
    x1 = VO.features_pong_v2(prev, None, prev_action=None)
    x2 = VO.features_pong_v2(cur, prev, prev_action=a1)
    o1, _ = net.forward(x1.reshape(1, -1))
    o2, _ = net.forward(x2.reshape(1, -1))
    assert a1 == ["DOWN", "NONE", "UP"][int(np.argmax(o1[0]))]
    assert a2 == ["DOWN", "NONE", "UP"][int(np.argmax(o2[0]))]
    # determinism: a fresh brain replays the same actions
    brain2 = VO.Brain(art)
    assert brain2.act(prev) == a1
    assert brain2.act(cur) == a2
    # reset_history restores the cold start
    brain2.reset_history()
    assert brain2.act(prev) == a1
