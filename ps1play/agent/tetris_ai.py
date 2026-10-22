"""Pure Tetris placement engine for the Tetrade play plugin.

Source-verified semantics (MIT Logan-Campbell/Tetrade, main.c):
  - matrix int[20][10], values 0..8 (0 = empty, 1..7 = tetromino type,
    8 = versus garbage; never present in Marathon)
  - piece shape is a 4x4 int grid; rotation spins the top-left
    tetSize x tetSize region, tetSize = 4 for types 1..2 (I, O), else 3
  - gravity at level 0 = 30 frames/cell; horizontal hold moves one cell
    per frame; A (PAD_CIRCLE) rotates CW once per frame held; UP (PAD_UP)
    hard-drops instantly (score += 2 cells); DOWN soft-drops (+1/cell)
  - scoring: single 200 x level, double 500 x level, triple 700,
    Tetrade 1000; level up every LEVEL_GOAL(8) x (level+1) total lines

This module is PURE (no emulator imports) so the evaluator is
offline-testable (Issue #8, T4). The plugin closes the loop around it
with live RAM reads: every plan step is verified against the real
tetrimino/shape/x fields before the next one is issued.
"""

HEIGHT, WIDTH = 20, 10

# weights for the placement evaluator (classic Dellacherie-style)
W_LINES = [0, 500, 1200, 2700, 5400]     # by rows cleared in one placement
W_HOLES = -450
W_BUMP = -28
W_AGG = -4
W_MAXH = -18


def minos_of(shape):
    """[(r, c)] of filled cells in a 4x4 shape grid."""
    return [(r, c) for r in range(4) for c in range(4) if shape[r][c]]


def rotate_cw(shape, tet_size):
    """Clockwise rotation of the tetSize x tetSize region of a 4x4 grid
    (mirrors rotate_clockwise(tetSize, tetSize, 4, 4, shape) in main.c)."""
    out = [[0] * 4 for _ in range(4)]
    for r in range(tet_size):
        for c in range(tet_size):
            out[c][tet_size - 1 - r] = shape[r][c]
    return out


def shape_after(shape, tet_size, n_rot):
    s = [row[:] for row in shape]
    for _ in range(n_rot % 4):
        s = rotate_cw(s, tet_size)
    return s


def drop_row(grid, cells, x0):
    """Landing top-row for `cells` placed at column offset x0, or None."""
    if any(c + x0 < 0 or c + x0 >= WIDTH for _, c in cells):
        return None
    y = 0
    while True:
        for r, c in cells:
            rr, cc = y + r, x0 + c
            if rr >= HEIGHT:
                return None if y == 0 else y - 1
            if grid[rr][cc]:
                return None if y == 0 else y - 1
        if y + max(r for r, _ in cells) >= HEIGHT - 1:
            return y
        y += 1


def _heights_holes(grid):
    heights = [0] * WIDTH
    holes = 0
    for c in range(WIDTH):
        seen = False
        for r in range(HEIGHT):
            if grid[r][c]:
                if not seen:
                    heights[c] = HEIGHT - r
                    seen = True
            elif seen:
                holes += 1
    return heights, holes


def evaluate(grid):
    """Heuristic score of a board AFTER a placement (lower holes/heights
    better, more cleared lines better)."""
    heights, holes = _heights_holes(grid)
    bump = sum(abs(heights[i] - heights[i + 1]) for i in range(WIDTH - 1))
    agg = sum(heights)
    mx = max(heights) if heights else 0
    return {"heights": heights, "holes": holes, "bump": bump,
            "agg": agg, "max_h": mx,
            "score": W_HOLES * holes + W_BUMP * bump + W_AGG * agg
            + W_MAXH * mx}


def _clear_lines(grid):
    rows = [r for r in range(HEIGHT) if all(grid[r])]
    for r in rows:
        del grid[r]
        grid.insert(0, [0] * WIDTH)
    return len(rows)


def choose(grid, shape, tet_size, rot_limit=4):
    """Best (rot_taps, x0, metrics) for the piece on `grid`.

    rot_limit caps the rotation search (1 = current orientation only) —
    the plugin's fallback when SRS wall-kicks keep failing near walls.
    Returns None when no placement fits (board too full — the caller
    should let gravity end the game honestly).
    """
    best = None
    for n_rot in range(rot_limit):
        sh = shape_after(shape, tet_size, n_rot)
        cells = minos_of(sh)
        if not cells:
            continue
        c_min = min(c for _, c in cells)
        c_max = max(c for _, c in cells)
        for x0 in range(-c_min, WIDTH - c_max):
            y0 = drop_row(grid, cells, x0)
            if y0 is None:
                continue
            g2 = [row[:] for row in grid]
            for r, c in cells:
                g2[y0 + r][x0 + c] = 1
            n_lines = _clear_lines(g2)
            ev = evaluate(g2)
            sc = W_LINES[n_lines] + ev["score"]
            cand = (sc, n_rot, x0, n_lines,
                    {"score": sc, "lines": n_lines,
                     "holes": ev["holes"], "bump": ev["bump"],
                     "agg": ev["agg"], "max_h": ev["max_h"]})
            if best is None or cand[0] > best[0]:
                best = cand
    if best is None:
        return None
    _, n_rot, x0, n_lines, info = best
    return {"rot": n_rot, "x": x0, "lines": n_lines, "eval": info}


def plan_segments(cur_x, target_x, drop_now):
    """Action segments for the translation+drop phase of one piece.

    Measured hold semantics (calibration, honest uncertainty): a short
    hold moves ~1 cell but the exact frame boundary varies, so the plan
    issues PER-CELL taps ([hold 2f, release 2f] each) and the plugin
    verifies the result next chunk and corrects — closed loop, never a
    blind open-chain.

    Returns a list of {"btns": set-of-names, "frames": n} segments; an
    empty set = explicit release (core.run() holds the last set
    otherwise — the documented run()-hold bug).
    """
    segs = []
    dx = target_x - cur_x
    n = abs(dx)
    btn = "RIGHT" if dx > 0 else "LEFT"
    for _ in range(n):
        segs.append({"btns": {btn}, "frames": 2})
        segs.append({"btns": set(), "frames": 2})
    if drop_now and dx == 0:
        segs.append({"btns": {"UP"}, "frames": 1})
        segs.append({"btns": set(), "frames": 3})
    return segs
