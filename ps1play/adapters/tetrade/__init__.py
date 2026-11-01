"""ps1play.adapters.tetrade — the Tetrade GameAdapter (R64).

The second runtime game, built exactly per the
`docs/r62_architecture.md` "adding a second game" recipe on top of the
R63 re-delivery evidence (Issue #8, commit c708c03):

  * perception: RAM reads over the `TetradeGame` struct (located by
    signature each episode start) — the R63-proven anchor map:
    matrix[20][10]@+0 (values = piece type), tetrimino
    {type@+800, shape@+804, x@+868, y@+872, rot@+880},
    nextTetriminos[14].type@+896+92k, score@+2276,
    single/double/triple/tetrade @+2280..2292, level@+2304,
    isGameOver@+2312, isGamePaused@+2316.
  * ZERO memory writes, ZERO core edits, real pad input only.
  * policy: the built-in hand-written Dellacherie 2-ply heuristic
    (policy.py) — R63 semantics ported verbatim behind the runtime
    Policy contract. NO model, NO training (training stays CLOSED).
  * entry/restart flows: the R63 probe1-proven sequences, including
    the disclosed traps (START taps <= 4f — a 60f hold triggers the
    game's key-repeat and lands PAUSED; CIRCLE refuses the continue;
    UP = hard drop; A/CIRCLE rotates CW).

The adapter owns ALL per-episode state (struct base, counters, last
observation) and drops it in reset_episode().
"""
from .adapter import TetradeAdapter, TETRADE_VECTOR_LEN, ADAPTER_VERSION
from .policy import DellacheriePolicy

__all__ = ["TetradeAdapter", "DellacheriePolicy",
           "TETRADE_VECTOR_LEN", "ADAPTER_VERSION"]
