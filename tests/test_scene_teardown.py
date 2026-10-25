"""Session-7: the alive() scene-teardown gate (S6-F1 fix).

Session-6 proved the c42-43 "death" rows were the mission-clear tally
TEARDOWN (php flips 0 exactly when px -> 0.0), not combat deaths, and
session-7 telemetry (7 JSONL runs) established the golden rule:
px == 0.0  <=>  php == 0 with ZERO counterexamples, while every real
death happens at px != 0.  scene_teardown_snap() encodes that rule and
run_once() consults it BEFORE counting a death.

Vectors below are lifted verbatim from the recorded transition rows
(train_vocab_17d.md, lives5/6/7 JSONLs i=45..47 / i=103..106 and the
c43/c67 teardown rows).
"""
import importlib.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, ".."))
for _p in (_REPO, os.path.join(_REPO, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _load_e2e():
    import e2e_policy_trial as mod
    return mod


try:
    e2e = _load_e2e()
except ModuleNotFoundError:
    # pytest path handling can bypass the inserts above — load the
    # script directly by absolute file path instead.
    _script = os.path.join(_REPO, "scripts", "e2e_policy_trial.py")
    _spec = importlib.util.spec_from_file_location("e2e_policy_trial",
                                                   _script)
    e2e = importlib.util.module_from_spec(_spec)
    sys.modules["e2e_policy_trial"] = e2e
    _spec.loader.exec_module(e2e)


class FakeMem:
    """Minimal MemoryView stand-in: u8/u16/u32 readers over a dict of
    RAM offsets, preloaded with a plausible M2 gameplay reading.
    `overrides` maps raw addresses (ints) to values."""

    def __init__(self, overrides=None):
        self._m = {
            e2e.PLAYER_X: int(404.1 * 65536),      # u32 16.16 world px
            e2e.A_SCORE: 3800,
            e2e.GRENADES: 20,
            e2e.PLAYER_HP: 136,
            e2e.FLAGS_WORD: 0xFF,                  # gameplay
            0x0EB5F4: 11,                          # SECTION_STATE (0xB)
            0x0EB5D0: 9,                           # SECTION_FLAGS
            0x0EB5D4: 0xFFFF,                      # SECTION_PROGRESS
        }
        for a, v in (overrides or {}).items():
            self._m[a] = v

    def u32(self, a):
        return self._m.get(a, 0) & 0xFFFFFFFF

    def u16(self, a):
        return self._m.get(a, 0) & 0xFFFF

    def u8(self, a):
        return self._m.get(a, 0) & 0xFF


# ---- S-A..S-F: every recorded px==0.0 signature must read TEARDOWN ----

def test_sa_tally_teardown():
    # c43/c67 row: px0 php0 gren0 flags255 sec(11,1) score3300
    m = FakeMem({e2e.PLAYER_X: 0, e2e.PLAYER_HP: 0, e2e.GRENADES: 0,
                 0x0EB5F4: 11, 0x0EB5D0: 1, e2e.A_SCORE: 3300})
    assert e2e.scene_teardown(m)


def test_sb_continue_screen():
    # W rows: same scalars as S-A on the CONTINUE? countdown
    m = FakeMem({e2e.PLAYER_X: 0, e2e.PLAYER_HP: 0, e2e.GRENADES: 0,
                 0x0EB5F4: 11, 0x0EB5D0: 1, e2e.A_SCORE: 3300})
    assert e2e.scene_teardown(m)


def test_sc_tally_onset():
    # M i=45: px0 php0 sec(0,0) flags255 score3301
    m = FakeMem({e2e.PLAYER_X: 0, e2e.PLAYER_HP: 0,
                 0x0EB5F4: 0, 0x0EB5D0: 0, e2e.A_SCORE: 3301})
    assert e2e.scene_teardown(m)


def test_sd_loading_flags0():
    # M i=46/47: px0 php0 FLAGS 0 sec(11,1) score3301 gren10
    m = FakeMem({e2e.PLAYER_X: 0, e2e.PLAYER_HP: 0,
                 e2e.FLAGS_WORD: 0, 0x0EB5F4: 11, 0x0EB5D0: 1,
                 e2e.A_SCORE: 3301, e2e.GRENADES: 10})
    assert e2e.scene_teardown(m)


def test_se_msx_logo_loading():
    # M i=103/104: px0 php0 flags0 sec(0,0) score7800 gren10
    m = FakeMem({e2e.PLAYER_X: 0, e2e.PLAYER_HP: 0,
                 e2e.FLAGS_WORD: 0, 0x0EB5F4: 0, 0x0EB5D0: 0,
                 e2e.A_SCORE: 7800, e2e.GRENADES: 10})
    assert e2e.scene_teardown(m)


def test_sf_score_reset():
    # M i=105: px0 php0 flags255 sec(0,0) score0 gren0
    m = FakeMem({e2e.PLAYER_X: 0, e2e.PLAYER_HP: 0,
                 0x0EB5F4: 0, 0x0EB5D0: 0, e2e.A_SCORE: 0})
    assert e2e.scene_teardown(m)


# ---- worlds that must NOT read teardown ----

def test_gameplay_not_teardown():
    # the M2 ride row: px 404.1 php 136
    assert not e2e.scene_teardown(FakeMem())


def test_real_death_shape_not_teardown():
    # a REAL combat death: php -> 0 while the player stands in the
    # world (px != 0) — the death branch MUST keep firing here
    m = FakeMem({e2e.PLAYER_HP: 0})
    assert not e2e.scene_teardown(m)
    assert not e2e.alive(m)


def test_spawn_frame_not_teardown():
    # M2 spawn i=106: px 74.6 php 74 sec(0,0) — a blank walker but a
    # live world (flags 0xFF, px > 0, php > 0)
    m = FakeMem({e2e.PLAYER_X: int(74.6 * 65536), e2e.PLAYER_HP: 74,
                 e2e.A_SCORE: 0, e2e.GRENADES: 10,
                 0x0EB5F4: 0, 0x0EB5D0: 0})
    assert not e2e.scene_teardown(m)
    assert e2e.alive(m)


def test_tally_world_trap_is_alive_but_not_teardown():
    # the honest trap: ~100f after the teardown the tally's own world
    # reads px 992 / php 120 / flags 255 — alive() returns True and the
    # teardown predicate returns False.  Documented here so the
    # stability re-check (world_stable) stays mandatory for callers
    # that must not re-enter on the tally scene.
    m = FakeMem({e2e.PLAYER_X: int(992.0 * 65536), e2e.PLAYER_HP: 120,
                 e2e.GRENADES: 10, 0x0EB5F4: 11, 0x0EB5D0: 1,
                 e2e.A_SCORE: 3301})
    assert not e2e.scene_teardown(m)
    assert e2e.alive(m)


def test_snap_keys_present():
    s = e2e.snap(FakeMem())
    for k in ("px", "score", "gren", "php", "flags", "sec", "prog"):
        assert k in s
