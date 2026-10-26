"""Offline tests for the Tetrade play plugin stack (Issue #8; round 10).

Pure-logic verification, NO emulator: evaluator golden cases, rotation
semantics, plan->segment translation, plugin contract v1 negotiation,
the full state machine (boot/play/wrap/over/refuse/restart), the
2-ply engine wiring with the live NEXT piece, and the chunk-granular
score/level causality bookkeeping (exact by the one-action-per-chunk
drop discipline).
"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import pytest                                       # noqa: E402
from ps1play.agent import tetris_ai as ta           # noqa: E402
from ps1play.plugins.base import PLUGIN_CLASSES     # noqa: E402
from ps1play.plugins.contract import (CONTRACT_VERSION,   # noqa: E402
                                      UnsupportedCapabilityError)
from ps1play.plugins import tetrade_play as tp      # noqa: E402
from ps1play.plugins.tetrade_play import (TetradePlayPlugin,   # noqa: E402
                                          choose_2ply, _fit)

BASE = 0x1FECA0                     # live-verified struct anchor (Issue #8)

# profile field layout (mirrors ps1play/profiles/tetrade_lic.json)
FIELDS = {"matrix": BASE, "tet_type": BASE + 800, "tet_shape": BASE + 804,
          "tet_x": BASE + 868, "tet_y": BASE + 872, "tet_held": BASE + 876,
          "tet_rot": BASE + 880, "next_count": BASE + 892,
          "next0_type": BASE + 896, "hold_type": BASE + 2184,
          "score": BASE + 2276, "single": BASE + 2280,
          "double": BASE + 2284, "triple": BASE + 2288,
          "tetra": BASE + 2292, "move_cd": BASE + 2296,
          "set_time": BASE + 2300, "level": BASE + 2304,
          "ghost_y": BASE + 2308, "game_over": BASE + 2312,
          "paused": BASE + 2316}


class FakeMem:
    """Minimal read-only MemoryView stand-in (u32 little-endian)."""

    def __init__(self):
        self.buf = bytearray(2 * 1024 * 1024)

    def u32(self, addr):
        return int.from_bytes(self.buf[addr:addr + 4], "little")

    def poke32(self, addr, val):
        self.buf[addr:addr + 4] = (val & 0xFFFFFFFF).to_bytes(4, "little")


def empty_grid():
    return [[0] * ta.WIDTH for _ in range(ta.HEIGHT)]


def from_rows(rows):
    return [list(map(int, r)) for r in rows]


def make_plugin(**prof_extra):
    prof = {"discovered": {"fields": dict(FIELDS)}}
    prof.update(prof_extra)
    return TetradePlayPlugin(prof)


def live_feat(**kw):
    """A plausible live-gameplay feat dict (all bookkeeping keys)."""
    f = {"changed_bytes": 5000, "board": empty_grid(), "board_occupied": 0,
         "shape": [[0, 0, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
         "type": 7, "x": 4, "y": 5, "rot": 0, "score": 0,
         "single": 0, "double": 0, "triple": 0, "tetra": 0,
         "level": 0, "ghost_y": 15, "game_over": 0, "paused": 0,
         "next0_type": 1, "next0_shape": [[0, 0, 0, 0], [1, 1, 1, 1],
                                          [0, 0, 0, 0], [0, 0, 0, 0]]}
    f["lines_total"] = 0
    f.update(kw)
    return f


def run_chunk(plug, feat, chunk=30, t=0, fc=None):
    ctx = {"chunk": chunk, "feat": feat}
    if fc is not None:
        ctx["fc"] = fc
    else:
        ctx["t"] = t
    return plug.policy(ctx)


# ---------------- rotation semantics (mirrors main.c) ----------------

def test_rotate_cw_preserves_cells_and_identity():
    t = [[0, 0, 1, 0],
         [1, 1, 1, 0],
         [0, 0, 0, 0],
         [0, 0, 0, 0]]
    r1 = ta.rotate_cw(t, 3)
    assert sum(map(sum, r1)) == 4
    assert sum(map(sum, t)) == 4
    r4 = t
    for _ in range(4):
        r4 = ta.rotate_cw(r4, 3)
    assert r4 == t
    assert r1 != t


def test_shape_after_matches_n_single_rotations():
    s = [[0, 0, 0, 0],
         [1, 1, 1, 1],
         [0, 0, 0, 0],
         [0, 0, 0, 0]]
    assert ta.shape_after(s, 4, 2) != s
    assert ta.shape_after(s, 4, 4) == s


# ---------------- evaluator + choose golden cases --------------------

def test_choose_completes_a_gapped_row():
    g = from_rows(["0000000000"] * 19 + ["1111111011"])
    i_shape = [[0, 0, 0, 0],
               [1, 1, 1, 1],
               [0, 0, 0, 0],
               [0, 0, 0, 0]]
    best = ta.choose(g, i_shape, 4)
    assert best is not None and best["lines"] == 1


def test_choose_avoids_creating_holes():
    g = from_rows(["0000000000"] * 17 +
                  ["1000000001",
                   "1000000001",
                   "1100000011"])
    o_shape = [[1, 1, 0, 0],
               [1, 1, 0, 0],
               [0, 0, 0, 0],
               [0, 0, 0, 0]]
    best = ta.choose(g, o_shape, 4)
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
    cells = [(0, 0), (0, 1), (1, 0), (1, 1)]
    assert ta.drop_row(g, cells, 4) == ta.HEIGHT - 2
    g[ta.HEIGHT - 1][4] = g[ta.HEIGHT - 1][5] = 1
    assert ta.drop_row(g, cells, 4) == ta.HEIGHT - 3


def test_choose_determinism():
    g = from_rows(["1000000000"] * 3 + ["0000000000"] * 17)
    s = [[0, 0, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    a = ta.choose(g, s, 3)
    b = ta.choose(g, s, 3)
    assert a == b


# ---------------- 2-ply engine (r9 port) ------------------------------

def test_choose_2ply_takes_the_tetris_in_a_ready_well():
    grid = empty_grid()
    for r in range(16, 20):                   # flat stack, 1-wide gap col 9
        for c in range(9):
            grid[r][c] = 1
    i_shape = [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]]
    t = choose_2ply(grid, i_shape, 4, 4, nxt=None)
    assert t is not None and t["lines"] == 4


def test_choose_2ply_uses_next_piece_when_given():
    grid = empty_grid()
    s = [[0, 0, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]]
    nxt = (1, [[0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0]])
    t = choose_2ply(grid, s, 3, 4, nxt=nxt)
    assert t is not None and {"rot", "x", "lines"} <= set(t)


# ---------------- plan -> segment translation -------------------------

def test_plan_segments_per_cell_and_release():
    segs = ta.plan_segments(cur_x=2, target_x=5, drop_now=False)
    rights = [s for s in segs if "RIGHT" in s["btns"]]
    releases = [s for s in segs if s["btns"] == set()]
    assert len(rights) == 3
    assert all(s["frames"] == 2 for s in rights)
    assert len(releases) >= 3
    segs2 = ta.plan_segments(cur_x=5, target_x=5, drop_now=True)
    drops = [s for s in segs2 if "UP" in s["btns"]]
    assert len(drops) == 1 and drops[0]["frames"] == 1


def test_plan_segments_no_drop_when_misaligned():
    segs = ta.plan_segments(cur_x=5, target_x=2, drop_now=True)
    assert not any("UP" in s["btns"] for s in segs)
    assert any("LEFT" in s["btns"] for s in segs)


def test_fit_sums_exactly_to_chunk():
    segs = _fit([{"btns": {"A"}, "frames": 7},
                 {"btns": set(), "frames": 100}], 30)
    assert sum(s["frames"] for s in segs) == 30
    assert _fit([], 12) == [{"btns": set(), "frames": 12}]


# ---------------- plugin contract v1 ----------------------------------

def test_tetrade_play_registered_and_compliant():
    ids = [c.ID for c in PLUGIN_CLASSES]
    assert "tetrade_play" in ids
    p = make_plugin()
    caps = p.capabilities()
    assert caps.game_id == "tetrade_play"
    assert caps.boot_exe_names == ("tetrade.exe",)
    assert caps.contract_version == CONTRACT_VERSION == 1
    assert p.PLUGIN_CONTRACT == CONTRACT_VERSION
    for op in ("boot_script", "features", "policy", "infer_state",
               "detectors"):
        assert caps.supports(op), op
        assert p.require(op) is True


def test_tetrade_play_rejects_undeclared_ops():
    p = make_plugin()
    for op in ("route", "encounter", "re_index", "checkpoints"):
        with pytest.raises(UnsupportedCapabilityError):
            p.require(op)


def test_boot_script_releases_every_press():
    """Every pressed segment must be followed by an explicit release —
    core.run() holds the last set otherwise (documented bug)."""
    p = make_plugin()
    steps = p.boot_script()
    assert p._nav_seen is True                  # nav provenance recorded
    prev_press = False
    for st in steps:
        if st.get("op") == "tap":
            if st["btns"]:
                assert not prev_press, "press without release"
                prev_press = True
            else:
                prev_press = False
    assert not prev_press


# ---------------- features / detectors (fake mem) ----------------------

def test_features_reads_struct_and_next_piece():
    mem = FakeMem()
    mem.poke32(FIELDS["matrix"] + (19 * 10 + 9) * 4, 3)   # one block
    mem.poke32(FIELDS["tet_type"], 7)
    mem.poke32(FIELDS["tet_x"], 4)
    mem.poke32(FIELDS["tet_y"], 5)
    mem.poke32(FIELDS["score"], 1234)
    mem.poke32(FIELDS["single"], 1)
    mem.poke32(FIELDS["next0_type"], 1)
    for i in range(16):
        mem.poke32(FIELDS["next0_type"] + 4 + i * 4, 1 if i in (4, 5, 6, 7)
                   else 0)
    p = make_plugin()
    feat = p.features(mem, {"changed_bytes": 42})
    assert feat["changed_bytes"] == 42
    assert feat["board"][19][9] == 3
    assert feat["board_occupied"] == 1
    assert feat["type"] == 7 and feat["x"] == 4 and feat["y"] == 5
    assert feat["score"] == 1234 and feat["lines_total"] == 1
    assert feat["next0_type"] == 1
    assert sum(map(sum, feat["next0_shape"])) == 4     # the I row


def test_features_degrades_without_fields():
    p = TetradePlayPlugin({})
    feat = p.features(FakeMem(), {"changed_bytes": 7})
    assert feat == {"changed_bytes": 7}
    assert p.infer_state({}, feat) == "unknown"


def test_detectors_op_reports_state_and_freshness():
    mem = FakeMem()
    p = make_plugin()
    d = p.detectors(mem)
    assert d["fields_present"] and d["quiescent_fresh"]
    assert d["fresh_cycle"] and not d["live_piece"]
    assert d["state"] == "title"
    mem.poke32(FIELDS["tet_type"], 3)
    mem.poke32(FIELDS["tet_x"], 4)
    mem.poke32(FIELDS["tet_y"], 5)
    d2 = p.detectors(mem)
    assert d2["live_piece"] and d2["state"] == "marathon"


# ---------------- infer_state covers the full loop ---------------------

def test_infer_state_covers_title_menu_marathon_gameover():
    p = make_plugin()
    quiet = live_feat(type=0, x=None, y=None, next0_type=None,
                      next0_shape=None)
    assert p.infer_state({}, quiet) == "title"
    p.boot_script()                       # nav provenance -> menu
    assert p.infer_state({}, quiet) == "menu"
    assert p.infer_state({}, live_feat()) == "marathon"
    assert p.infer_state({}, live_feat(game_over=1)) == "gameover"
    assert p.infer_state({}, live_feat(paused=1)) == "paused"
    assert p.infer_state({}, live_feat(type=255, x=255)) == "unknown"


# ---------------- policy: fresh-cycle discovery + wiring ----------------

def test_policy_discovers_fresh_cycle_and_plans_in_agentloop_dialect():
    p = make_plugin()
    segs = run_chunk(p, live_feat(), chunk=30, t=1234)   # boot discovery
    assert p.mode == "play"
    assert sum(s["frames"] for s in segs) == 30
    evs = [e["ev"] for e in p.events]
    assert "fresh_cycle_verified" in evs and "marathon_entered" in evs
    plan = [e for e in p.events if e["ev"] == "plan"]
    assert plan and plan[-1]["fc"] == 1234      # AgentLoop ctx["t"] used


def test_policy_wires_the_2ply_engine_with_the_live_next_piece():
    p = make_plugin()
    run_chunk(p, live_feat(), chunk=30, t=0)
    st = p.engine_stats
    assert st["choose_calls"] >= 1 and st["used_2ply"] >= 1
    assert st["next_ok_calls"] == st["used_2ply"]
    # no NEXT read -> honest 1-ply fallback (used_2ply must not grow)
    n = st["used_2ply"]
    run_chunk(p, live_feat(next0_type=None, next0_shape=None), chunk=30)
    assert p.engine_stats["used_2ply"] == n


def test_policy_hard_drop_records_exact_cells_and_never_double_drops(
        monkeypatch):
    monkeypatch.setattr(
        tp, "choose_2ply",
        lambda *a, **k: {"rot": 0, "x": 4, "lines": 0})
    p = make_plugin()
    # discovery + aligned drop in ONE call: UP is the FIRST segment and
    # the live ghost_y - y distance is recorded exactly
    segs = run_chunk(p, live_feat(x=4, y=5, ghost_y=15), chunk=30, t=0)
    assert segs[0]["btns"] == {"UP"} and segs[0]["frames"] == 1
    plan = [e for e in p.events if e["ev"] == "plan"][-1]
    assert plan["act"] == "hard_drop" and plan["drop_cells"] == 10
    assert p._drop_pending == 10
    # the same piece is never dropped twice
    segs2 = run_chunk(p, live_feat(x=4, y=12, ghost_y=15), chunk=30, t=30)
    assert not any("UP" in s["btns"] for s in segs2)
    # ...and the pending cells are consumed by the next bookkeep pass
    assert p._drop_pending == 0


def test_policy_scores_exact_via_counter_kinds_and_drop_cells():
    p = make_plugin()
    p.mode = "play"
    p._fresh_seen = True
    prev = live_feat(type=1, x=4, y=12, ghost_y=15, score=10,
                     level=0, single=0, double=0, triple=0, tetra=0)
    prev["lines_total"] = 16
    p._feat_prev = prev
    p._drop_pending = 3
    # single clear at the natural 0->1 flip: level applied AFTER the flip
    cur = live_feat(type=-1, x=None, y=None, score=10 + 200 + 2 * 3,
                    level=1, single=1, next0_type=None, next0_shape=None)
    cur["lines_total"] = 17
    run_chunk(p, cur, chunk=30, t=60)
    e = [e for e in p.events if e["ev"] == "line_clear"][-1]
    assert e["kinds"] == {"d1": 1, "d2": 0, "d3": 0, "d4": 0}
    assert e["expected_pts"] == 200 and e["clear_pts"] == 200
    assert e["match"] is True
    f = [e for e in p.events if e["ev"] == "level_flip"][-1]
    assert (f["frm"], f["to"]) == (0, 1) and f["threshold_ok"] is True
    assert f["threshold"] == 8


def test_policy_scores_level0_clears_as_zero():
    p = make_plugin()
    p.mode = "play"
    p._fresh_seen = True
    prev = live_feat(type=1, score=50, level=0)
    prev["lines_total"] = 3
    p._feat_prev = prev
    p._drop_pending = 2
    cur = live_feat(type=-1, x=None, y=None, score=54, level=0, single=1)
    cur["lines_total"] = 4
    run_chunk(p, cur, chunk=30, t=30)
    e = [e for e in p.events if e["ev"] == "line_clear"][-1]
    assert e["expected_pts"] == 0 and e["clear_pts"] == 0
    assert e["match"] is True          # singles at level 0 add 0 points


def test_policy_records_honest_mismatch():
    p = make_plugin()
    p.mode = "play"
    p._fresh_seen = True
    prev = live_feat(type=1, score=100, level=1, single=0)
    prev["lines_total"] = 20
    p._feat_prev = prev
    p._drop_pending = 0
    cur = live_feat(type=-1, x=None, y=None, score=999, level=1, single=1)
    cur["lines_total"] = 21
    run_chunk(p, cur, chunk=30, t=30)
    e = [e for e in p.events if e["ev"] == "line_clear"][-1]
    assert e["match"] is False
    assert e["expected_pts"] == 200


# ---------------- game over -> refuse -> restart ------------------------

def _drive_to_over(p):
    p.mode = "over"
    p._over_fc = 0
    p._refused = False


def test_policy_refuses_continue_once_then_restarts():
    p = make_plugin()
    _drive_to_over(p)
    over = live_feat(game_over=1, type=-1, x=None, y=None)
    for _ in range(2):                       # destruction anim window
        segs = run_chunk(p, over, chunk=60, t=0)
        assert sum(s["frames"] for s in segs) == 60
        assert not any("A" in s["btns"] for s in segs)
    segs = run_chunk(p, over, chunk=60, t=120)     # 180f >= OVER_ANIM
    assert any("A" in s["btns"] for s in segs)     # the CIRCLE refusal
    assert [e for e in p.events if e["ev"] == "refuse_continue"]
    assert p.mode == "restart"
    # over persists: restart mode must NEVER tap (START would continue)
    segs = run_chunk(p, over, chunk=30, t=180)
    assert all(s["btns"] == set() for s in segs)
    # menu (over cleared, dead board, no live piece) -> START nav tap
    menu = live_feat(game_over=0, type=-1, x=None, y=None, score=5000,
                     single=7, level=4)
    for _ in range(8):                             # settle + stage taps
        run_chunk(p, menu, chunk=30, t=240)
    navs = [e for e in p.events if e["ev"] == "restart_nav"]
    assert navs and navs[0]["btn"] == "START"
    # fresh Marathon with a live piece -> restart VERIFIED, cycle 2
    fresh = live_feat(score=0, level=0, single=0, type=3, x=4, y=0)
    segs = run_chunk(p, fresh, chunk=30, t=600)
    rc = [e for e in p.events if e["ev"] == "restart_complete"]
    assert rc and rc[0]["cycle"] == 2
    assert p.cycle == 2 and p.mode == "play" and not p._fresh_seen
    assert sum(s["frames"] for s in segs) == 30


def test_maybe_finish_closes_the_loop_after_fresh_clear():
    p = make_plugin()
    p.cycles = 1
    p.mode = "restart"
    fresh = live_feat(type=3, x=4, y=0)
    run_chunk(p, fresh, chunk=30, t=0)
    assert p.cycle == 2 and p.mode == "play"
    assert p.maybe_finish(fc=30) is False          # no fresh clear yet
    p._post_restart_clears = 1
    assert p.maybe_finish(fc=60) is True
    assert p.mode == "done"
    assert [e for e in p.events if e["ev"] == "loop_complete"]


def test_game_over_transition_from_play_is_natural_and_flagged():
    p = make_plugin()
    p.mode = "play"
    p._fresh_seen = True
    p._feat_prev = live_feat()
    over = live_feat(game_over=1, type=-1, x=None, y=None, score=4321,
                     single=3, level=5)
    over["lines_total"] = 33
    run_chunk(p, over, chunk=30, t=99)
    e = [e for e in p.events if e["ev"] == "game_over"][-1]
    assert e["score"] == 4321 and e["level"] == 5
    assert p.mode == "over"


def test_never_writes_memory():
    """The plugin stack is read-only by construction (MemoryView has no
    write methods); guard the contract honestly."""
    from ps1play.core.memory import MemoryView
    for name in dir(MemoryView):
        if name.startswith("w") or "write" in name or "poke" in name:
            pytest.fail(f"MemoryView grew a writer: {name}")
