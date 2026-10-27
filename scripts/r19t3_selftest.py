#!/usr/bin/env python3
"""r19t3_selftest.py — offline (no-emulator) validation of the r19 T3
Tetrade bot planner before it is allowed near the emulator.

What is tested:
  1. bfs_reach / drop_from / canonical_rot on small boards.
  2. plan_2ply / plan_1ply_reachable sanity + wall-clock cost.
  3. cols_within (the decision-accuracy metric).
  4. A pure-Python Tetrade simulator (main.c semantics as documented:
     20x10, gravity 30 f/cell, no-kick CW rotation, hard drop, +2/cell
     hard-drop score) driven by the SAME planner the bot uses with
     ideal per-cell execution -> clears/game over the planning stack
     achieves on random piece sequences (2-ply ON vs OFF).

Run: python3 scripts/r19t3_selftest.py
Exit 0 = all gates pass.
"""
import json
import random
import sys
import time

sys.path.insert(0, "/home/z/my-project/ps1ai")

from scripts.r19t3_tetrade_bot import (           # noqa: E402
    bfs_reach, drop_from, canonical_rot, plan_2ply,
    plan_1ply_reachable, shape_cols, cols_within, collides, HEIGHT, WIDTH)
from ps1play.agent import tetris_ai as ai         # noqa: E402

# standard tetrominoes in the game's bounding boxes (4x4 for I/O, 3x3 rest)
SHAPES = {
    1: [[1, 1, 1, 1], [0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
    2: [[1, 1, 0, 0], [1, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],
    3: [[1, 1, 1, 0], [0, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],   # T
    4: [[0, 1, 1, 0], [1, 1, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]],   # S
    5: [[1, 1, 0, 0], [0, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],   # Z
    6: [[1, 0, 0, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],   # J
    7: [[0, 0, 1, 0], [1, 1, 1, 0], [0, 0, 0, 0], [0, 0, 0, 0]],   # L
}
IDS = sorted(SHAPES)


def shape4(t):
    return [row[:] for row in SHAPES[t]]


def sim_lock(grid, cells, x, y):
    """Merge + clear.  Returns (new_grid, lines)."""
    g2 = [row[:] for row in grid]
    for r, c in cells:
        g2[y + r][x + c] = 1
    n = ai._clear_lines(g2)
    return g2, n


def spawn_ok(grid, t):
    shape = shape4(t)
    cells = ai.minos_of(shape)
    x0 = (WIDTH - (max(c for _, c in cells) + 1)) // 2
    return not collides(grid, cells, x0, 0)


def simulate(seed, lookahead, max_pieces=400):
    """Ideal-execution sim: planner picks, piece is placed exactly."""
    rng = random.Random(seed)
    grid = [[0] * WIDTH for _ in range(HEIGHT)]
    queue = [rng.choice(IDS) for _ in range(2)]
    clears = pieces = score = 0
    while pieces < max_pieces:
        t = queue.pop(0)
        queue.append(rng.choice(IDS))
        if not spawn_ok(grid, t):
            break                                  # natural top-out
        shape = shape4(t)
        size = 4 if t <= 2 else 3
        cells0 = ai.minos_of(shape)
        x0 = (WIDTH - (max(c for _, c in cells0) + 1)) // 2
        nsh, nsize = (shape4(queue[0]), 4 if queue[0] <= 2 else 3) \
            if lookahead else (None, 0)
        tgt = plan_2ply(grid, shape, size, x0, 0, nsh, nsize)
        if tgt is None:
            break
        grid, n = sim_lock(grid, tgt["cells"], tgt["x"], tgt["y_land"])
        clears += n
        score += 2 * sum(HEIGHT - r for r, _ in tgt["cells"])
        pieces += 1
    return {"pieces": pieces, "clears": clears, "score": score}


def main():
    fails = []
    t0 = time.time()

    # ---- 1. helpers ----
    g = [[0] * WIDTH for _ in range(HEIGHT)]
    g[19] = [1] * WIDTH
    g[18] = [0, 0, 1, 1, 1, 1, 1, 1, 1, 1]
    shape = shape4(1)                            # I horizontal
    cells = ai.minos_of(shape)
    assert drop_from(g, cells, 0, 0) == 17, drop_from(g, cells, 0, 0)
    reach = bfs_reach(g, shape, 4, 3, 0)
    assert (0, 0) in reach and (1, 0) in reach, sorted(reach)[:5]
    # a column closed to the top (x=3 filled up to row 4 via walls) is
    # a deeper check; keep to basics here.
    assert canonical_rot(shape4(2), 4, 4) == 0   # O: full cycle identity
    assert canonical_rot(shape4(2), 4, 2) == 2   # O spins in the 4x4 box
    assert canonical_rot(shape4(1), 4, 1) == 1   # I: 4 distinct shapes
    assert canonical_rot(shape4(1), 4, 2) == 2

    # ---- 2. planner cost + sanity ----
    rng = random.Random(7)
    grid = [[0] * WIDTH for _ in range(HEIGHT)]
    for r in range(14, 20):                      # some garbage
        for c in range(WIDTH):
            if rng.random() < 0.4:
                grid[r][c] = 1
    t = time.time()
    tgt = plan_2ply(grid, shape4(3), 3, 3, 0, shape4(4), 3)
    dt = time.time() - t
    assert tgt is not None and 0 <= tgt["x"] < WIDTH, tgt
    print(f"plan_2ply cost: {dt*1000:.0f} ms "
          f"(target < 1500) -> {'OK' if dt < 1.5 else 'FAIL'}")
    if dt >= 1.5:
        fails.append("plan_2ply too slow")
    tgt1 = plan_1ply_reachable(grid, shape4(3), 3, 3, 0)
    assert tgt1 is not None
    t = time.time()
    for _ in range(20):
        plan_1ply_reachable(grid, shape4(3), 3, 3, 0)
    print(f"plan_1ply cost: {(time.time()-t)/20*1000:.1f} ms")

    # ---- 3. accuracy metric ----
    assert cols_within([3, 4], [3, 4]) and cols_within([3, 5], [4, 5])
    assert not cols_within([3, 4], [6, 7])
    assert not cols_within([], [1])

    # ---- 4. full-game simulations ----
    for lookahead in (False, True):
        res = [simulate(seed, lookahead) for seed in range(6)]
        clears = [r["clears"] for r in res]
        pieces = [r["pieces"] for r in res]
        mean_c = sum(clears) / len(clears)
        print(f"simulate lookahead={lookahead}: clears/game "
              f"{clears} mean {mean_c:.1f}; pieces {pieces}")
        if lookahead and mean_c < 15:
            fails.append(f"2-ply plays too weak: mean clears "
                         f"{mean_c:.1f} < 15")
        if not lookahead and mean_c < 8:
            fails.append(f"1-ply plays too weak: mean clears "
                         f"{mean_c:.1f} < 8")

    print(f"selftest done in {time.time()-t0:.1f}s; "
          f"{'FAIL: ' + '; '.join(fails) if fails else 'ALL GATES PASS'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
