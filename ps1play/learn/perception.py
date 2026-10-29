"""perception.py — pure-frame visual feature extractors (assisted modes).

These functions are DERIVED VISUAL INPUTS (role: visual_input) — computed
from rendered frames only, so they are legal for any policy. The same
geometry is REIMPLEMENTED inside ps1play/learn/visual_only.py (the
boundary module) for the deployed brain; tests assert the two
implementations agree numerically (one geometry, two readers, no hidden
pathway). This module is the assisted-side reference implementation and
carries the game-specific knowledge gathered in Stage A.
"""
import numpy as np

# pong geometry (source-verified + r12-calibrated bands)
PONG_W, PONG_H = 320, 240
PONG_BALL_SIZE = 16
PONG_PADDLE_H = 60
PONG_STEP = 2                 # control step (frames per decision)
PONG_BALL_BAND = (32, 222, 24, 296)   # rows r0:r1, cols c0:c1 (r12)
PONG_PAD_L_COLS = (6, 24)
PONG_PAD_R_COLS = (296, 314)

# flappy geometry (r15-measured + source)
FLAP_W, FLAP_H = 320, 240


def to_gray(fr, shape=(60, 80)):
    """Downsample RGB frame -> uint8 gray (h, w). Pure frame function."""
    g = fr.mean(axis=2)
    h, w = shape
    hs = np.linspace(0, g.shape[0], h + 1).astype(int)
    ws = np.linspace(0, g.shape[1], w + 1).astype(int)
    out = np.empty((h, w), dtype=np.float32)
    for i in range(h):
        for j in range(w):
            out[i, j] = g[hs[i]:hs[i + 1], ws[j]:ws[j + 1]].mean()
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------- pong
def pong_ball_centroid(fr):
    """Ball centroid via the r12-calibrated band + adaptive threshold
    (excludes score digits and paddles). (cx, cy, n) or (None, None, 0)."""
    g = fr.mean(axis=2)
    r0, r1, c0, c1 = PONG_BALL_BAND
    reg = g[r0:r1, c0:c1]
    mx = float(reg.max())
    if mx < 150:
        return None, None, 0
    thr = max(150.0, mx - 60.0)
    mask = reg >= thr
    n = int(mask.sum())
    if n < 15 or n > 320:
        return None, None, n
    ys, xs = np.nonzero(mask)
    return (float(xs.mean()) + c0, float(ys.mean()) + r0, n)


def pong_paddle_rows(fr):
    """White paddle rows in the r12-calibrated column bands."""
    g = fr.mean(axis=2)
    out = []
    for c0, c1 in (PONG_PAD_L_COLS, PONG_PAD_R_COLS):
        band = g[:, c0:c1]
        ys = np.nonzero((band > 200).any(axis=1))[0]
        out.append(float(np.median(ys)) if len(ys) >= 20 else None)
    return out[0], out[1]


# ---------------------------------------------------------------- flappy
def flappy_bird_y(fr):
    """Bird screen y via yellow centroid (r15 sensor, verbatim bands)."""
    r, g, b = (fr[:, :, i].astype(int) for i in range(3))
    yellow = (r > 180) & (g > 170) & (b < 110)
    yellow[:20, :] = False
    yellow[186:, :] = False          # ground strip starts ~y=190
    yellow[:, :130] = False
    yellow[:, 196:] = False
    ys, xs = np.nonzero(yellow)
    if len(ys) < 6 or len(ys) > 900:
        return None, len(ys)
    return float(ys.mean()), len(ys)


def flappy_green_mask(fr):
    """PIPE green family incl. the shaded right side (r15, verbatim)."""
    r, g, b = (fr[:, :, i].astype(int) for i in range(3))
    return (g > 100) & (r < 150) & (g > b + 20)


def flappy_gap_geometry(green, bird_x=160.0):
    """Nearest pipe (right of bird) gap: returns (gap_top_y, gap_bot_y,
    gap_center, pipe_left_col) or Nones. The gap = the vertical run of
    non-green inside the pipe column band."""
    cols = np.nonzero(green.any(axis=0))[0]
    right = cols[cols > bird_x + 12]
    if len(right) == 0:
        return None, None, None, None
    # contiguous column run = nearest pipe
    c0 = right[0]
    c1 = c0
    for c in right:
        if c - c1 <= 2:
            c1 = c
        else:
            break
    band = green[:, c0:c1 + 1]
    rows = np.nonzero(~band.any(axis=1))[0]
    rows = rows[(rows > 24) & (rows < 184)]     # play area
    if len(rows) < 20:
        return None, None, None, None
    # largest contiguous gap run
    splits = np.split(rows, np.nonzero(np.diff(rows) > 2)[0] + 1)
    gap = max(splits, key=len)
    top, bot = float(gap[0]), float(gap[-1])
    return top, bot, (top + bot) / 2.0, float(c0)


def flappy_gap_target_r15(green, by):
    """VERBATIM port of r15_flappy_play.gap_target (the calibrated
    sensor): the pipe currently at/over the bird. Scan bands from x=120
    (dilated column sums over rows above the grass line), pick the
    first band whose right edge > 130, return its gap center + band
    center. Returns (gap_center_y, band_center_x) or (None, None)."""
    colsum = green[:188, :].sum(axis=0)
    cs = np.maximum(np.maximum(colsum[:-2], colsum[1:-1]), colsum[2:])
    colsum = np.concatenate([[colsum[0]], cs, [colsum[-1]]])
    bands, start = [], None
    for x in range(120, 320):
        if colsum[x] > 40:
            if start is None:
                start = x
        else:
            if start is not None and x - start >= 8:
                bands.append((start, x))
            start = None
    if start is not None and 320 - start >= 8:
        bands.append((start, 320))
    if not bands:
        return None, None
    bx0, bx1 = next((b for b in bands if b[1] > 130), bands[0])
    band = green[:188, bx0:bx1]
    rows = np.nonzero(~band.any(axis=1))[0]
    rows = rows[(rows > 20) & (rows < 188)]
    if len(rows) == 0:
        return None, None
    gaps, s, prev = [], rows[0], rows[0]
    for y in rows[1:]:
        if y == prev + 1:
            prev = y
        else:
            gaps.append((s, prev))
            s = prev = y
    gaps.append((s, prev))
    gaps = [g for g in gaps if g[1] - g[0] > 30]
    if not gaps:
        return None, None
    g0, g1 = gaps[0]
    return (g0 + g1) / 2.0, (bx0 + bx1) / 2.0


# ---------------------------------------------------------------- stacks
def stack2(prev_gray, cur_gray):
    """Causal 2-frame stack: [t-1, t]. NEVER includes t+1 (tests assert
    the builder only ever sees frames up to t)."""
    return np.concatenate([prev_gray.ravel(), cur_gray.ravel()])
