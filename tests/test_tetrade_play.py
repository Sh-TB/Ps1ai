"""Offline tests for the Tetrade play plugin stack (Issue #8, T9).

Pure-logic verification: evaluator golden cases, rotation semantics,
plan->segment translation, plugin contract compliance. No emulator.
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from ps1play.agent import tetris_ai as ta          # noqa: E402
from ps1play.plugins.base import PLUGIN_CLASSES     # noqa: E402
from ps1play.plugins.tetrade_play import TetradePlayPlugin  # noqa: E402


def empty_grid():
    return [[0] * ta.WIDTH for _ in range(ta.HEIGHT)]


def from_rows(rows):
    return [list(map(int, r)) for r in rows]


# ---------------- rotation semantics (mirrors main.c) ----------------

def test_rotate_cw_preserves_cells_and_identity():
    # T piece spawn shape (type>2 -> tetSize 3)
    t = [[0, 0, 1, 0],
         [1, 1, 1, 0],
         [0, 0, 0, 0],
         [0, 0, 0, 0]]
    r1 = ta.rotate_cw(t, 3)
    assert sum(map(sum, r1)) == 4            # cell count preserved
    assert sum(map(sum, t)) == 4
    r4 = t
    for _ in range(4):
        r4 = ta.rotate_cw(r4, 3)
    assert r4 == t                           # 4-step identity
    assert r1 != t                           # actually rotates


def test_shape_after_matches_n_single_rotations():
    s = [[0, 0, 0, 0],
         [1, 1, 1, 1],
         [0, 0, 0, 0],
         [0, 0, 0, 0]]      # I piece (tetSize 4)
    assert ta.shape_after(s, 4, 2) != s
    assert ta.shape_after(s, 4, 4) == s


# ---------------- evaluator + choose golden cases --------------------

def test_choose_completes_a_gapped_row():
    g = from_rows(["0000000000"] * 19 + ["1111111011"])   # gap at col 7
    i_shape = [[0, 0, 0, 0],
               [1, 1, 1, 1],
               [0, 0, 0, 0],
               [0, 0, 0, 0]]
    best = ta.choose(g, i_shape, 4)
    assert best is not None and best["lines"] == 1


def test_choose_avoids_creating_holes():
    # floor-anchored stack (blocks never float in real play)
    g = from_rows(["0000000000"] * 17 +
                  ["1000000001",
                   "1000000001",
                   "1100000011"])
    o_shape = [[1, 1, 0, 0],
               [1, 1, 0, 0],
               [0, 0, 0, 0],
               [0, 0, 0, 0]]
    best = ta.choose(g, o_shape, 4)
    # placing must not bury a hole: simulate and check
    cells = ta.minos_of(ta.shape_after(o_shape, 4, best["rot"]))
    y0 = ta.drop_row(g, cells, best["x"])
    g2 = [row[:] for row in g]
    for r, c in cells:
        g2[y0 + r][best["x"] + c] = 1
    _, holes = ta._heights_holes(g2)
    assert holes == 0


def test_choose_returns_none_when_board_full():
    g = from_rows(["1111111111"] * 20)
    assert ta.choose(g, [[1, 1, 0, 0], [1, 1, 0, 0],
                         [0, 0, 0, 0], [0, 0, 0, 0]], 4) is None


def test_drop_row_stacks_on_floor_and_piles():
    g = empty_grid()
    cells = [(0, 0), (0, 1), (1, 0), (1, 1)]     # O at frame offset
    assert ta.drop_row(g, cells, 4) == ta.HEIGHT - 2
    g[ta.HEIGHT - 1][4] = g[ta.HEIGHT - 1][5] = 1
    assert ta.drop_row(g, cells, 4) == ta.HEIGHT - 3


def test_choose_determinism():
    g = from_rows(["1000000000"] * 3 + ["0000000000"] * 17)
    s = [[0, 0, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    a = ta.choose(g, s, 3)
    b = ta.choose(g, s, 3)
    assert a == b


# ---------------- plan -> segment translation -------------------------

def test_plan_segments_per_cell_and_release():
    segs = ta.plan_segments(cur_x=2, target_x=5, drop_now=False)
    rights = [s for s in segs if "RIGHT" in s["btns"]]
    releases = [s for s in segs if s["btns"] == set()]
    assert len(rights) == 3                      # one per cell
    assert all(s["frames"] == 2 for s in rights)
    assert len(releases) >= 3                    # explicit releases present
    # aligned piece -> drop segment present
    segs2 = ta.plan_segments(cur_x=5, target_x=5, drop_now=True)
    drops = [s for s in segs2 if "UP" in s["btns"]]
    assert len(drops) == 1 and drops[0]["frames"] == 1


def test_plan_segments_no_drop_when_misaligned():
    segs = ta.plan_segments(cur_x=5, target_x=2, drop_now=True)
    assert not any("UP" in s["btns"] for s in segs)
    assert any("LEFT" in s["btns"] for s in segs)


# ---------------- plugin contract compliance --------------------------

def test_tetrade_play_registered_and_compliant():
    ids = [c.ID for c in PLUGIN_CLASSES]
    assert "tetrade_play" in ids
    p = TetradePlayPlugin({})
    caps = p.capabilities()
    assert caps.game_id == "tetrade_play"
    assert caps.boot_exe_names == ("tetrade.exe",)
    assert caps.contract_version == 1
    for op in ("boot_script", "features", "policy", "infer_state",
               "detectors"):
        assert caps.supports(op), op
        p.require(op)


def test_boot_script_releases_every_press():
    """Every pressed segment must be followed by an explicit release —
    core.run() holds the last set otherwise (documented bug)."""
    p = TetradePlayPlugin({})
    steps = p.boot_script()
    prev_press = False
    for st in steps:
        if st.get("op") == "tap":
            if st["btns"]:
                assert not prev_press, "press without release"
                prev_press = True
            else:
                prev_press = False
    assert not prev_press


def test_policy_gates_garbage_reads():
    """Mid-lock transient reads (x=-1/255, type=255) must idle, not plan."""
    p = TetradePlayPlugin({"discovered": {"fields": {
        k: 0x1000 + i * 4 for i, k in enumerate(
            ["matrix", "tet_type", "tet_shape", "tet_x", "tet_y",
             "tet_rot", "score", "single", "double", "triple", "tetra",
             "level", "game_over"])}}})
    mem = None  # features() needs mem — gate is in policy; use feat dict
    feat = {"type": 255, "x": 255, "y": 4, "game_over": 0,
            "board": empty_grid(), "shape": [[0] * 4 for _ in range(4)],
            "lines_total": 0}
    segs = p.policy({"chunk": 60, "fc": 0, "feat": feat})
    assert segs == [{"btns": set(), "frames": 60}]


def test_policy_refuses_continue_once_then_done():
    p = TetradePlayPlugin({})
    over = {"game_over": 1, "type": 255, "x": 3, "y": 0, "lines_total": 5}
    # anim window: idle
    for _ in range(2):
        segs = p.policy({"chunk": 60, "fc": 0, "feat": over})
        assert sum(s["frames"] for s in segs) == 60
    # after OVER_ANIM frames accumulated: the CIRCLE refusal
    segs = p.policy({"chunk": 60, "fc": 0, "feat": over})
    assert any("A" in s["btns"] for s in segs)
    # game reset (over cleared): loop done
    segs = p.policy({"chunk": 60, "fc": 0, "feat": {"game_over": 0}})
    assert p.mode == "done"
    assert segs == [{"btns": set(), "frames": 60}]
