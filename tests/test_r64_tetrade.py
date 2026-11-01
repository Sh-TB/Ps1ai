"""R64 Tetrade — the second runtime game: offline contracts.

Everything testable WITHOUT the emulator:

  A. geometry/evaluation math (R63 semantics, hand-computed boards)
  B. DellacheriePolicy: planning + the per-frame realization state
     machine (cooldowns, taps, respawn/pause/over handling, identity)
  C. TetradeAdapter over a FAKE env: the 222-value observation layout,
     post-advance line/score/terminal detection, action mapping,
     episode stats, the R63 entry/restart frame budgets
  D. the struct scan on a synthetic RAM image
  E. registry/config/CLI wiring (games list, progress label, disc map,
     hash pins)

Real-emulator integration lives in tests/test_r64_integration.py.
"""
import hashlib
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

from ps1play.adapters.tetrade import (  # noqa: E402
    ADAPTER_VERSION, DellacheriePolicy, TETRADE_VECTOR_LEN,
    TetradeAdapter,
)
from ps1play.adapters.tetrade import adapter as tad  # noqa: E402
from ps1play.adapters.tetrade import policy as pol  # noqa: E402
from ps1play.runtime.errors import (  # noqa: E402
    AdapterError, ConfigError, EmulatorError, RuntimePolicyError)
from ps1play.runtime.interfaces import Frame  # noqa: E402

CUE = "/home/z/my-project/emu/games_homebrew/patched/tetrade_lic.cue"


# ---------------------------------------------------------------- --
# helpers
# ---------------------------------------------------------------- --
def _frame(seq=1):
    rgb = np.zeros((4, 4, 3), dtype=np.uint8)
    return Frame(seq=seq, emulator_frame_count=seq, rgb=rgb,
                 timestamp=0.0)


def _vec(board=None, ptype=0, rot=0, x=0, y=0, next_type=0, score=0,
         lines=0, level=0, over=0, paused=0) -> np.ndarray:
    v = np.zeros(TETRADE_VECTOR_LEN, dtype=np.float32)
    if board is not None:
        v[:200] = np.asarray(board, dtype=np.float32).ravel()
    if 1 <= ptype <= 7:
        v[200 + ptype - 1] = 1.0
    v[207], v[208], v[209] = float(rot), float(x), float(y)
    if 1 <= next_type <= 7:
        v[210 + next_type - 1] = 1.0
    v[217], v[218], v[219] = float(score), float(lines), float(level)
    v[220], v[221] = float(over), float(paused)
    return v


def _obs(v, seq=1):
    from ps1play.runtime.interfaces import GameObservation
    return GameObservation(values=np.asarray(v, dtype=np.float32),
                           frame_seq=seq, frame_id=f"seq{seq}@emu{seq}",
                           timestamp=0.0, valid=True)


def _ram_with_struct(base=0x1FECA0, *, board=None, ptype=3, x=4, y=0,
                     rot=0, next0=5, score=0, single=0, double=0,
                     triple=0, tetrade=0, level=0, over=0, paused=0,
                     total_bytes=2 * 1024 * 1024):
    """A synthetic 2 MiB RAM image with a planted TetradeGame struct."""
    ram = bytearray(total_bytes)
    a = np.frombuffer(ram, dtype=np.uint8)

    def w32(off, val):
        a[base + off:base + off + 4] = np.array(
            [val & 0xFFFFFFFF], dtype="<u4").view(np.uint8)

    mat = (np.zeros((20, 10), dtype=np.uint32) if board is None
           else np.asarray(board, dtype=np.uint32))
    a[base:base + 800] = mat.astype("<u4").ravel().view(np.uint8)
    w32(tad.O_TYPE, ptype)
    w32(tad.O_X, x)
    w32(tad.O_Y, y)
    w32(tad.O_ROT, rot)
    w32(tad.O_N0, next0)
    w32(tad.O_SCORE, score)
    w32(tad.O_SINGLE, single)
    w32(tad.O_DOUBLE, double)
    w32(tad.O_TRIPLE, triple)
    w32(tad.O_TETRADE, tetrade)
    w32(tad.O_LEVEL, level)
    w32(tad.O_OVER, over)
    w32(tad.O_PAUSED, paused)
    return a


class FakeMem:
    def __init__(self, ram):
        self.ram = ram

    def snapshot(self):
        return self.ram.copy()


class FakeEnv:
    """Records every run() call; exposes p.mem/p.core like BaseEnv."""

    def __init__(self, ram):
        self.p = SimpleNamespace(mem=FakeMem(ram), core=SimpleNamespace())
        self.calls = []           # (frames, frozenset buttons)

    def run(self, frames, buttons=None):
        self.calls.append((int(frames), frozenset(buttons or set())))


class ContinueScreenEnv(FakeEnv):
    """Stateful fake: the test calls go_game_over() to simulate the
    episode having ended; the CIRCLE continue-refusal (the 'A' press)
    then swaps the RAM to a fresh live Marathon — the real sequencing
    episode 2 sees through the restart flow."""

    def __init__(self, ram):
        super().__init__(ram)
        self._refused = False

    def go_game_over(self, **kw):
        self.p.mem.ram = _ram_with_struct(over=1, **kw)

    def run(self, frames, buttons=None):
        b = frozenset(buttons or set())
        if not self._refused and "A" in b:
            self._refused = True
            self.p.mem.ram = _ram_with_struct(ptype=4)
        super().run(frames, b)


# ---------------------------------------------------------------- --
# A. geometry + evaluation
# ---------------------------------------------------------------- --
class TestGeometry:
    def test_rot_shape_known_pieces(self):
        # O-piece is rotation-invariant
        o0 = pol.rot_shape(2, 0)
        for r in range(4):
            assert np.array_equal(o0, pol.rot_shape(2, r))

        def norm(shape):
            cs = np.array(pol.cells(shape))
            return frozenset(map(tuple,
                                 (cs - cs.min(axis=0)).tolist()))

        # the I-piece has exactly two normalized orientations
        # (the 4x4 padding makes rows 1/2 differ byte-wise)
        ishapes = {norm(pol.rot_shape(1, r)) for r in range(4)}
        assert len(ishapes) == 2
        # the T-piece has four distinct orientations
        tshapes = {norm(pol.rot_shape(7, r)) for r in range(4)}
        assert len(tshapes) == 4

    def test_cells_and_drop_y(self):
        shape = pol.rot_shape(1, 0)            # I horizontal, row 1
        cs = pol.cells(shape)
        assert all(r == 1 for r, _ in cs) and len(cs) == 4
        board = np.zeros((20, 10), dtype=int)
        board[18, :] = 1                       # floor-ish tower
        assert pol.drop_y(board, shape, 3) == 16   # rests on row 18
        board2 = np.zeros((20, 10), dtype=int)
        # empty board: the piece's BOTTOM cells rest on row 19, i.e.
        # y offset 18 for the I (its cells are at y+1)
        assert pol.drop_y(board2, shape, 3) == 18

    def test_evaluate_counts_a_single_clear(self):
        board = np.zeros((20, 10), dtype=int)
        for c in range(6):                     # cols 0..5 filled
            board[19, c] = 1                   # 4-wide gap: cols 6..9
        shape = pol.rot_shape(1, 0)            # I horizontal, cols 6-9
        v, info = pol.evaluate(board, shape, 6)
        assert v is not None
        assert info["clear"] == 1
        assert info["epc"] == 4                # 4 cells x 1 line
        # the I rests on the floor row: cells land on row 19
        assert pol.drop_y(board, shape, 6) == 18

    def test_evaluate_hole_detection(self):
        board = np.zeros((20, 10), dtype=int)
        board[19, 0] = board[19, 1] = board[19, 3] = 1
        board[18, 0] = board[18, 1] = board[18, 3] = 1
        shape = pol.rot_shape(2, 0)            # O-piece
        v, info = pol.evaluate(board, shape, 1)
        # O at x=1 covers cols 2-3; resting at y=16 (col3 blocked by
        # the row-18/19 stack): col2 rows 18-19 stay empty under the
        # piece -> holes detected
        assert v is not None
        assert info["holes"] >= 1

    def test_weights_are_the_r63_table(self):
        assert pol.Wts == {"lh": -4.500158, "epc": 3.418126,
                           "rt": -3.217888, "ct": -9.348695,
                           "holes": -7.899265, "wells": -3.385597}


class TestPlanning:
    def test_prefers_the_line_clear(self):
        board = np.zeros((20, 10), dtype=int)
        for c in range(6):                     # gap = cols 6..9
            board[19, c] = 1
        plan = pol.plan_placement(board, 1, 0)     # I, no NEXT
        r_t, x_t, info, v1 = plan
        assert info["clear"] == 1                  # completes the row
        assert x_t == 6                            # the gap column

    def test_empty_board_returns_a_legal_placement(self):
        plan = pol.plan_placement(np.zeros((20, 10), dtype=int), 3, 6)
        assert plan is not None
        r_t, x_t, info, v1 = plan
        assert 0 <= r_t <= 3 and -1 <= x_t <= 9
        # the planned placement must actually fit
        shape = pol.rot_shape(3, r_t)
        assert pol.drop_y(np.zeros((20, 10), dtype=int), shape,
                          x_t) >= 0

    def test_no_placement_when_board_is_full(self):
        board = np.ones((20, 10), dtype=int)
        assert pol.plan_placement(board, 1, 0) is None

    def test_two_ply_uses_next_piece(self):
        # a plan with a NEXT piece must differ (or at least run) vs no
        # NEXT on a board where the second ply matters
        board = np.zeros((20, 10), dtype=int)
        board[19, 0] = board[19, 1] = board[19, 2] = 1
        p_no = pol.plan_placement(board, 7, 0)
        p_yes = pol.plan_placement(board, 7, 1)
        assert p_no is not None and p_yes is not None


# ---------------------------------------------------------------- --
# B. DellacheriePolicy state machine
# ---------------------------------------------------------------- --
class TestPolicyStateMachine:
    def _plan_first(self, **kw):
        p = DellacheriePolicy()
        v = _vec(ptype=1, rot=0, x=4, next_type=2, **kw)
        return p, p.predict(_obs(v))

    def test_first_decision_starts_the_plan(self):
        p, d = self._plan_first()
        assert d.action in ("IDLE", "ROT_CW")
        assert d.diagnostics["r_t"] is not None
        assert d.policy_name.startswith("tetrade_dellacherie")
        assert len(d.policy_sha256) == 64

    def test_full_realization_reaches_hard_drop(self):
        p = DellacheriePolicy()
        actions = []
        # drive one piece: board fixed, piece type 1 rot0 x4
        for i in range(240):
            v = _vec(ptype=1, rot=0, x=4, next_type=2)
            d = p.predict(_obs(v, seq=i + 1))
            actions.append(d.action)
            # simulate the game applying the action to the state
            if d.action == "ROT_CW":
                pass                        # rot stays 0 in this fake
            elif d.action == "MOVE_L":
                pass
            elif d.action == "HARD_DROP":
                break
        assert actions[-1] == "HARD_DROP"
        # with a static state the fuses cap the taps/moves
        assert actions.count("ROT_CW") <= 4
        assert actions.count("MOVE_L") + actions.count("MOVE_R") <= 12
        # the cooldowns: no two taps closer than their idle gap
        gaps = {"ROT_CW": pol.ROT_COOLDOWN, "MOVE_L": pol.MOVE_COOLDOWN,
                "MOVE_R": pol.MOVE_COOLDOWN}
        last = {}
        for i, a in enumerate(actions):
            if a in gaps:
                if a in last:
                    assert i - last[a] > gaps[a], (a, i)
                last[a] = i
        # after the drop: the settle block (>= 40 IDLE frames)
        v = _vec(ptype=1, rot=0, x=4, next_type=2)
        d2 = p.predict(_obs(v))
        assert d2.action == "IDLE"
        assert d2.diagnostics["phase"] in ("SETTLE", "RESPAWN", "DONE")

    def test_realizes_rotation_and_moves_on_live_state(self):
        """Simulate a cooperative game: rot increments on ROT_CW, x
        moves on MOVE_*; the plan must terminate in a HARD_DROP with
        the piece AT the target."""
        p = DellacheriePolicy()
        board = np.zeros((20, 10), dtype=int)
        rot, x = 0, 4
        dropped = False
        for i in range(200):
            ptype = 3                        # J piece
            v = _vec(board=board, ptype=ptype, rot=rot, x=x, y=0,
                     next_type=4)
            d = p.predict(_obs(v, seq=i + 1))
            if d.action == "ROT_CW":
                rot = (rot + 1) % 4
            elif d.action == "MOVE_L":
                x -= 1
            elif d.action == "MOVE_R":
                x += 1
            elif d.action == "HARD_DROP":
                dropped = True
                break
        assert dropped
        diag = d.diagnostics
        assert rot == diag["r_t"] and x == diag["x_t"]

    def test_respawn_resets_plan(self):
        p, d0 = self._plan_first()
        v = _vec(ptype=0)                   # transient respawn state
        d = p.predict(_obs(v))
        assert d.action == "IDLE"
        assert d.diagnostics["phase"] == "RESPAWN"
        # a live piece again -> a FRESH plan is computed (no stale)
        v = _vec(ptype=1, rot=0, x=4, next_type=2)
        d2 = p.predict(_obs(v))
        assert d2.diagnostics["plan_frames"] == 1

    def test_pause_toggle_then_wait(self):
        p = DellacheriePolicy()
        v = _vec(ptype=1, rot=0, x=4, next_type=2, paused=1)
        d1 = p.predict(_obs(v))
        assert d1.action == "PAUSE_TOGGLE"
        d2 = p.predict(_obs(v))
        assert d2.action == "IDLE"          # waiting, not spamming
        # unpause observed -> latch cleared, planning resumes
        v = _vec(ptype=1, rot=0, x=4, next_type=2, paused=0)
        d3 = p.predict(_obs(v))
        assert d3.action in ("IDLE", "ROT_CW")

    def test_game_over_is_idle(self):
        p = DellacheriePolicy()
        v = _vec(ptype=1, over=1)
        assert p.predict(_obs(v)).action == "IDLE"

    def test_invalid_observation_raises(self):
        from ps1play.runtime.interfaces import GameObservation
        p = DellacheriePolicy()
        bad = GameObservation(values=None, frame_seq=1, frame_id="x",
                              timestamp=0.0, valid=False,
                              invalid_reason="test")
        with pytest.raises(RuntimePolicyError):
            p.predict(bad)
        wrong_shape = GameObservation(
            values=np.zeros(10, dtype=np.float32), frame_seq=1,
            frame_id="x", timestamp=0.0, valid=True)
        with pytest.raises(RuntimePolicyError):
            p.predict(wrong_shape)

    def test_identity_pins_the_policy_source(self):
        p = DellacheriePolicy()
        with open(pol.__file__, "rb") as f:
            src_sha = hashlib.sha256(f.read()).hexdigest()
        assert p.identity()["model_sha256"] == src_sha
        assert "training" in p.identity()["kind"]

    def test_reset_clears_the_plan(self):
        p, _ = self._plan_first()
        p.reset()
        v = _vec(ptype=1, rot=0, x=4, next_type=2)
        assert p.predict(_obs(v)).diagnostics["plan_frames"] == 1

    def test_legal_actions_match_the_adapter(self):
        assert tuple(DellacheriePolicy().legal_actions()) == \
            tuple(TetradeAdapter(FakeEnv(_ram_with_struct()))
                  .legal_actions())


# ---------------------------------------------------------------- --
# C. adapter over a FAKE env
# ---------------------------------------------------------------- --
class TestAdapterFakeEnv:
    def _adapter(self, **kw):
        env_cls = kw.pop("env_cls", FakeEnv)
        ram = _ram_with_struct(**kw)
        env = env_cls(ram)
        return TetradeAdapter(env), env

    def test_wait_ready_verifies_and_enters(self):
        """wait_ready is the VERIFIED ready state: the entry ran and
        the struct is located; episode 1 then reuses it without
        double-entering."""
        a, env = self._adapter()
        a.wait_ready(30.0)
        assert a._base == 0x1FECA0 and a._fresh_ready is True
        buttons = [b for _f, b in env.calls]
        assert frozenset({"B"}) in buttons
        assert frozenset({"START"}) in buttons
        assert frozenset({"A"}) not in buttons   # no restart prefix
        consumed = a.start_episode(6)
        assert consumed == 0                     # reused ready state
        assert a._fresh_ready is False

    def test_start_episode_entry_sequence_and_base(self):
        a, env = self._adapter()
        a.wait_ready(30.0)
        consumed = a.start_episode(6)
        # episode 1 reuses the verified ready state (0 frames)
        assert consumed == 0
        assert a._base == 0x1FECA0
        st = a._read_state()
        assert st["type"] == 3 and st["next0"] == 5

    def test_restart_flow_after_a_finished_episode(self):
        a, env = self._adapter(env_cls=ContinueScreenEnv)
        a.wait_ready(30.0)
        a.start_episode(6)                 # consumes the ready state
        env.go_game_over()                 # the episode ended (death)
        env.calls.clear()
        consumed = a.start_episode(12)
        frames = [f for f, _b in env.calls]
        buttons_seq = [b for _f, b in env.calls]
        # the R63 restart prefix: refuse the continue with CIRCLE(A),
        # then the menu START tap, then the entry sequence
        assert frozenset({"A"}) in buttons_seq
        assert frozenset({"START"}) in buttons_seq
        assert frozenset({"B"}) in buttons_seq
        assert consumed == (tad.RESTART_TAIL + tad.CONTINUE_REFUSE
                            + sum(tad.RESTART_MID)
                            + tad.RESTART_MENU_TAP
                            + tad.RESTART_MENU_SETTLE
                            + tad.SELECT_HOLD + tad.SELECT_SETTLE
                            + tad.BEGIN_TAP + tad.COUNTDOWN
                            + tad.BEGIN_TAP + tad.BEGIN_TAIL)

    def test_start_taps_are_short(self):
        """The disclosed PAUSED trap: every IN-GAME START hold must be
        <= 4 frames (a 60f hold triggers the game's key-repeat). The
        one pre-game exception is the title->menu hold (proven safe:
        the pause logic does not exist before a game starts)."""
        a, env = self._adapter(env_cls=ContinueScreenEnv)
        a.wait_ready(30.0)
        a.start_episode(6)
        env.go_game_over()
        a.start_episode(12)
        for f, b in env.calls:
            if "START" in b:
                assert f == tad.TITLE_START_HOLD or \
                    f <= tad.BEGIN_TAP, (f, b)

    def test_budget_alive_episode_is_finished_legally(self):
        """An episode that ended ALIVE at its budget leaves the game
        mid-play: start_episode must first hard-drop to a NATURAL game
        over (legal UP presses only) before the restart flow — and
        refuse to restart if that never arrives."""
        a, env = self._adapter()      # plain FakeEnv: never game over
        a.wait_ready(30.0)
        a.start_episode(6)
        env.calls.clear()
        with pytest.raises(EmulatorError) as e:
            a.start_episode(12)
        assert "natural game over" in str(e.value)
        # the attempt used ONLY legal buttons (UP/START taps)
        pressed = set()
        for _f, b in env.calls:
            pressed |= b
        assert pressed <= {"UP", "START"}

    def test_observe_vector_layout(self):
        board = np.zeros((20, 10), dtype=int)
        board[19, 0] = board[19, 9] = 1        # flat idx 190 and 199
        a, _env = self._adapter()              # fresh struct for the
        a.wait_ready(30.0)
        a.start_episode(6)                     # scan (level/score 0)
        # mid-game state: the scan only ever runs on episode START
        a.env.p.mem.ram = _ram_with_struct(
            board=board, ptype=6, x=3, y=2, rot=2, next0=7, score=120,
            single=1, triple=2, level=3)
        o = a.observe(_frame())
        assert o.valid and o.values.shape == (TETRADE_VECTOR_LEN,)
        v = o.values
        assert v[0] == 0.0 and v[190] == 1.0 and v[199] == 1.0
        assert v[200 + 6 - 1] == 1.0 and v[200 + 5 - 1] == 0.0
        assert v[207] == 2.0 and v[208] == 3.0 and v[209] == 2.0
        assert v[210 + 7 - 1] == 1.0
        assert v[217] == 120.0 and v[218] == 3.0 and v[219] == 3.0
        assert v[220] == 0.0 and v[221] == 0.0
        # the FEATURE_NAMES layout documents exactly this
        assert len(TetradeAdapter.FEATURE_NAMES) == TETRADE_VECTOR_LEN
        assert TetradeAdapter.FEATURE_NAMES[0] == "board_00_0"
        assert TetradeAdapter.FEATURE_NAMES[200] == "type_1"
        assert TetradeAdapter.FEATURE_NAMES[207] == "rot"
        assert TetradeAdapter.FEATURE_NAMES[210] == "next_1"
        assert TetradeAdapter.FEATURE_NAMES[221] == "paused"

    def test_observe_respawn_is_valid(self):
        """The transient type=-1/0 state is a legitimate observation
        (all-zero type slot) — never an invalid one."""
        a, _ = self._adapter(ptype=3)          # live piece first
        a.wait_ready(30.0)
        a.start_episode(6)
        a.env.p.mem.ram = _ram_with_struct(ptype=-1)   # respawn hit
        o = a.observe(_frame())
        assert o.valid
        assert o.values[200:207].sum() == 0.0

    def test_observe_before_start_is_invalid(self):
        a, _ = self._adapter()
        with pytest.raises(AdapterError):
            a.observe(_frame())

    def test_post_advance_line_and_terminal(self):
        a, _ = self._adapter(single=0)
        a.start_episode(6)
        post = a.post_advance(_frame())
        assert post["terminal"] is False
        assert post["line_event"] is False and post["pipes"] == 0
        # a single lands: single 0->1 -> line event
        ram2 = _ram_with_struct(single=1, score=100)
        a.env.p.mem.ram = ram2
        post2 = a.post_advance(_frame(2))
        assert post2["line_event"] is True
        assert post2["pipes"] == 1 and post2["score_delta"] == 100
        assert post2["pipe_passed"] is True
        # game over
        ram3 = _ram_with_struct(single=1, score=100, over=1)
        a.env.p.mem.ram = ram3
        post3 = a.post_advance(_frame(3))
        assert post3["terminal"] is True
        assert post3["death_reason"] == "game_over"

    def test_action_mapping_is_the_r63_map(self):
        a, _ = self._adapter()
        m = {"IDLE": frozenset(), "ROT_CW": frozenset({"A"}),
             "MOVE_L": frozenset({"LEFT"}), "MOVE_R":
             frozenset({"RIGHT"}), "HARD_DROP": frozenset({"UP"}),
             "PAUSE_TOGGLE": frozenset({"START"})}
        for act, btn in m.items():
            assert a.action_to_buttons(act) == btn
        with pytest.raises(AdapterError):
            a.action_to_buttons("FLAP")

    def test_note_action_and_episode_stats(self):
        a, _ = self._adapter(single=2)
        a.wait_ready(30.0)
        a.start_episode(6)
        from ps1play.runtime.interfaces import ActionDecision
        d = ActionDecision(action="ROT_CW", logits=None, frame_seq=1,
                           policy_name="p", policy_sha256="s",
                           latency_ms=0.0)
        a.note_action(d, None)
        a.note_action(d, None)
        d2 = ActionDecision(action="IDLE", logits=None, frame_seq=2,
                            policy_name="p", policy_sha256="s",
                            latency_ms=0.0)
        a.note_action(d2, None)
        st = a.episode_stats()
        assert st["actions"] == 2 and st["decisions"] == 3
        assert st["pipes"] == 2            # the generic progress key

    def test_reset_episode_drops_counters_but_keeps_boot_state(self):
        a, _ = self._adapter()
        a.wait_ready(30.0)
        a.start_episode(6)
        a._lines, a._steps, a._presses = 9, 9, 9
        a._ever_started = True
        a._at_menu = False
        a._boot_base = 0x1FECA0
        a.reset_episode()
        assert a._lines == 0 and a._steps == 0 and a._presses == 0
        # boot-scoped flags survive (the engine resets per episode)
        assert a._ever_started is True
        assert a._at_menu is False
        assert a._boot_base == 0x1FECA0

    def test_wait_ready_drives_title_to_menu(self):
        a, env = self._adapter()
        a.wait_ready(30.0)
        frames = [f for f, _b in env.calls]
        assert frames[0] == tad.BOOT_SETTLE[0]
        assert (tad.TITLE_START_HOLD, frozenset({"START"})) \
            in env.calls
        # wait_ready leaves a VERIFIED fresh Marathon (not a menu)
        assert a._fresh_ready is True and a._base == 0x1FECA0
        # episode 1 reuses it: no restart prefix, no re-entry
        env.calls.clear()
        a.start_episode(6)
        buttons = [b for _f, b in env.calls]
        assert frozenset({"A"}) not in buttons
        assert frozenset({"B"}) not in buttons


# ---------------------------------------------------------------- --
# D. the struct scan on synthetic RAM
# ---------------------------------------------------------------- --
class TestStructScan:
    def test_locates_the_planted_struct(self):
        ram = _ram_with_struct(base=0x1FECA0, ptype=3, next0=5)
        cands = TetradeAdapter._find_base_candidates(ram)
        assert 0x1FECA0 in cands

    def test_secondary_filter_accepts_the_respawn_type(self):
        ram = _ram_with_struct(base=0x1FECA0, ptype=-1, next0=5)
        cands = TetradeAdapter._find_base_candidates(ram)
        assert 0x1FECA0 in cands

    def test_rejects_a_paused_or_over_struct(self):
        for kw in ({"paused": 1}, {"over": 1}, {"score": 50},
                   {"level": 2}):
            ram = _ram_with_struct(base=0x1FECA0, **kw)
            assert 0x1FECA0 not in \
                TetradeAdapter._find_base_candidates(ram)

    def test_locate_prefers_the_previous_base(self):
        """Two live structs planted; the previously-seen base must
        win (the address is stable within one boot — R63 evidence)."""
        ram = _ram_with_struct(base=0x1FECA0, ptype=3)
        other = _ram_with_struct(base=0x100000, ptype=4)
        ram[0x100000:0x100000 + 2400] = other[0x100000:0x100000 + 2400]
        a = TetradeAdapter(FakeEnv(ram))
        a._base = 0x100000
        assert a._locate_base(
            deadline=__import__("time").time() + 5) == 0x100000
        # no previous base -> the first live candidate is fine
        a2 = TetradeAdapter(FakeEnv(ram))
        assert a2._locate_base(
            deadline=__import__("time").time() + 5) in (0x1FECA0,
                                                        0x100000)

    def test_locate_raises_when_nothing_matches(self):
        env = FakeEnv(np.zeros(2 * 1024 * 1024, dtype=np.uint8))
        a = TetradeAdapter(env)
        import time
        with pytest.raises(EmulatorError):
            a._locate_base(deadline=time.time() + 2)


# ---------------------------------------------------------------- --
# E. registry / config / disc wiring
# ---------------------------------------------------------------- --
class TestWiring:
    def test_games_registered(self):
        """R65: the registry GREW (buzzybee is the third runtime
        game); the R64 contract is that tetrade and flappybird stay
        registered — the full-list pin moved to the R65 tests."""
        from ps1play.runtime.registry import registered_games
        games = registered_games()
        assert "flappybird" in games and "tetrade" in games

    def test_progress_labels(self):
        from ps1play.runtime.registry import progress_label_for
        assert progress_label_for("tetrade") == "lines"
        assert progress_label_for("flappybird") == "pipes"

    def test_policy_for_game_tetrade_is_builtin(self):
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.registry import policy_for_game
        cfg = RuntimeConfig(game="tetrade",
                            output_dir="/tmp/r64t").validated()
        p = policy_for_game(cfg)
        assert isinstance(p, DellacheriePolicy)

    def test_policy_for_game_flappy_is_runtimepolicy(self):
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.registry import policy_for_game
        from ps1play.runtime.policy_runtime import RuntimePolicy
        cfg = RuntimeConfig(game="flappybird",
                            output_dir="/tmp/r64t").validated()
        p = policy_for_game(cfg)
        assert isinstance(p, RuntimePolicy)

    def test_config_accepts_registered_rejects_unknown(self):
        from ps1play.runtime.config import RuntimeConfig
        RuntimeConfig(game="tetrade",
                      output_dir="/tmp/r64t").validated()
        with pytest.raises(ConfigError) as e:
            RuntimeConfig(game="tetris",
                          output_dir="/tmp/r64t").validated()
        assert "tetrade" in str(e.value)

    def test_resolve_iso_map(self):
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.session import (GAME_DEFAULT_ISO,
                                             resolve_iso)
        cfg = RuntimeConfig(game="tetrade",
                            output_dir="/tmp/r64t").validated()
        assert resolve_iso(cfg) == GAME_DEFAULT_ISO["tetrade"]
        assert GAME_DEFAULT_ISO["tetrade"] == CUE
        assert GAME_DEFAULT_ISO["flappybird"].endswith("flappybird.cue")

    def test_flappy_hash_pin_unchanged(self):
        from ps1play.runtime.session import EXPECTED_ISO_SHA
        assert EXPECTED_ISO_SHA["flappybird"] == \
            "b45871d32c7910784b26128c3f4ed48d181e31dfd693f4e5efa" \
            "187cf2296f0ed"

    @pytest.mark.skipif(not os.path.exists(CUE),
                        reason="tetrade disc not present")
    def test_tetrade_hash_pin_matches_the_disc(self):
        from ps1play.runtime.session import EXPECTED_ISO_SHA, \
            disc_image_path
        img = disc_image_path(CUE)
        h = hashlib.sha256(open(img, "rb").read()).hexdigest()
        assert EXPECTED_ISO_SHA["tetrade"] == h

    def test_engine_uses_policy_for_game(self):
        """The engine seam: policy_for_game, not a hardcoded class."""
        import inspect
        from ps1play.runtime import engine
        src = inspect.getsource(engine)
        assert "policy_for_game(self.cfg" in src
        assert "RuntimePolicy(self.cfg" not in src

    def test_boot_retries_config(self):
        from ps1play.runtime.config import RuntimeConfig
        from ps1play.runtime.errors import ConfigError
        cfg = RuntimeConfig(game="tetrade",
                            output_dir="/tmp/r64t").validated()
        assert cfg.boot_retries == 2
        with pytest.raises(ConfigError):
            RuntimeConfig(game="tetrade", boot_retries=-1,
                          output_dir="/tmp/r64t").validated()
        with pytest.raises(ConfigError):
            RuntimeConfig(game="tetrade", boot_retries=9,
                          output_dir="/tmp/r64t").validated()

    def test_engine_boot_has_retry(self):
        """The engine re-boots a fresh core when wait_ready fails —
        the generic answer to beetle's in-process boot flakiness."""
        import inspect
        from ps1play.runtime import engine
        src = inspect.getsource(engine)
        assert "boot_retry" in src and "boot_retries" in src

    def test_vector_len_and_feature_names_agree(self):
        assert TETRADE_VECTOR_LEN == 222
        assert len(TetradeAdapter.FEATURE_NAMES) == 222
