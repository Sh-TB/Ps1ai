"""visual_only.py — THE DECISION BOUNDARY (mission §2, non-negotiable).

This module is the ONLY thing the deployed policy needs. Constraints,
enforced by tests/test_learning_boundary.py (not by documentation):

  1. IMPORTS: numpy + stdlib ONLY. No ps1play import of any kind.
  2. INPUTS: `Brain.act(rgb_small)` accepts ONE downsampled RGB frame
     (uint8 HxWx3, 60x80). The brain keeps its OWN single-frame history
     for velocity/temporal features. No host, no ram, no provider, no
     callback, no cache, no log pathway exists in this module.
  3. NO game bytes, no ROM knowledge, no teacher labels, no future
     frames (the history is strictly [t-1, t]).
  4. The forward pass re-derives TinyMLP.forward from the artifact
     weights; tests assert numerical equality between this reader and
     the training-side implementation on random inputs.

control_mode (from the artifact meta, disclosed):
  "cv+mlp"  — hand-written frame-derived CV features (image-derived,
              legal) feed the learned controller. What was learned =
              the control law; disclosed per the mission's hybrid rule.
  "raw+mlp" — the learned network consumes the stacked RGB pixels
              directly (perception AND control learned end-to-end).

Both variants NEVER see anything but rendered frames.
"""
import json
import os

import numpy as np

# ------------------------------------------------------------------
# NOTE FOR AUDITORS: this module must stay free of ps1play imports.
# tests/test_learning_boundary.py AST-scans this file and fails if any
# import besides numpy/stdlib appears, or if names like `ram`, `core`,
# `memmap`, `savestate`, `teacher` are referenced.
# ------------------------------------------------------------------

OUT_H, OUT_W = 60, 80
SX, SY = 320.0 / OUT_W, 240.0 / OUT_H


def _as_gray(cur):
    """Small frame -> 2-D gray (accepts HxWx3 RGB or HxW gray)."""
    a = np.asarray(cur)
    return a if a.ndim == 2 else a.mean(axis=2)


def features_pong(cur, prev):
    """PUBLIC pong features on gray (the Brain + the trainer share
    THIS function — one geometry, no drift)."""
    gray = _as_gray(cur)
    pgray = _as_gray(prev) if prev is not None else None
    reg = gray[8:56, 6:74]
    mx = float(reg.max()) if reg.size else 0.0
    if mx < 150:
        cx = cy = -1.0
    else:
        thr = max(150.0, mx - 60.0)
        mask = reg >= thr
        ys, xs = np.nonzero(mask)
        n = len(ys)
        if 1 <= n <= 25:            # ~90px/16 area scale
            cx, cy = (xs.mean() + 6) * SX, (ys.mean() + 8) * SY
        else:
            cx = cy = -1.0
    vx = vy = 0.0
    if pgray is not None and cx >= 0:
        preg = pgray[8:56, 6:74]
        pmx = float(preg.max()) if preg.size else 0.0
        if pmx >= 150:
            pmask = preg >= max(150.0, pmx - 60.0)
            pys, pxs = np.nonzero(pmask)
            if 1 <= len(pys) <= 25:
                vx = cx - (pxs.mean() + 6) * SX
                vy = cy - (pys.mean() + 8) * SY
    out = [cx, cy, vx, vy]
    for c0, c1 in ((2, 6), (74, 78)):     # paddle bands /4
        band = gray[:, c0:c1]
        yy = np.nonzero((band > 200).any(axis=1))[0]
        out.append(float(np.median(yy)) * SY if len(yy) >= 5 else 120.0)
    return np.asarray(out, dtype=np.float32)


def _features_pong(cur, prev):
    """Legal visual features from the CURRENT (+PREVIOUS) small RGB.
    Mirrors perception.pong_* on the 60x80 grid (bands scaled /4;
    adaptive in-band threshold like the calibrated reference)."""
    return features_pong(cur, prev)


def features_flappy(cur, prev):
    """Legal visual features: bird y/vy + the r15 gap-target logic on
    the 60x80 small RGB (the /4-scaled mirror of
    perception.flappy_gap_target_r15 — tests assert both readers agree
    on synthetic frames)."""
    r = cur[:, :, 0].astype(int)
    g = cur[:, :, 1].astype(int)
    b = cur[:, :, 2].astype(int)
    # BLEND-ROBUST bird test: area-averaging mixes the 20px bird with
    # the teal sky (the pure r>180/g>170/b<110 test measured EMPTY on
    # the small frame — the eval run's 0-flap deaths). The blended
    # bird keeps r,g above b; the sky has b highest.
    yellow = (r > b + 25) & (g > b + 5) & (r > 120)
    yellow[:5, :] = False
    yellow[46:, :] = False
    yellow[:, :32] = False
    yellow[:, 50:] = False
    ys, _xs = np.nonzero(yellow)
    by = ys.mean() * SY if len(ys) >= 2 else -1.0
    vy = 0.0
    if prev is not None and by >= 0:
        pr = prev[:, :, 0].astype(int)
        pg = prev[:, :, 1].astype(int)
        pb = prev[:, :, 2].astype(int)
        pyel = (pr > pb + 25) & (pg > pb + 5) & (pr > 120)
        pyel[:5, :] = False
        pyel[46:, :] = False
        pyel[:, :32] = False
        pyel[:, 50:] = False
        pys, _p = np.nonzero(pyel)
        if len(pys) >= 2:
            vy = by - pys.mean() * SY
    # blend-robust pipe test on the small frame: pipes keep g the max
    # channel with b LOW; the sky's b is HIGH (the full-res thresholds
    # measured sky false-positives here)
    green = (g > 110) & (g > r + 10) & (b < 175) & (r < g)
    colsum = green[:47, :].sum(axis=0)          # rows above grass /4
    cs = np.maximum(np.maximum(colsum[:-2], colsum[1:-1]), colsum[2:])
    colsum = np.concatenate([[colsum[0]], cs, [colsum[-1]]])
    bands, start = [], None
    for x in range(30, 80):                     # x=120..320 /4
        if colsum[x] > 10:                      # >40/4
            if start is None:
                start = x
        else:
            if start is not None and x - start >= 2:   # >=8/4
                bands.append((start, x))
            start = None
    if start is not None and 80 - start >= 2:
        bands.append((start, 80))
    gc = dx = -1.0
    if bands:
        bx0, bx1 = next((bd for bd in bands if bd[1] > 32), bands[0])
        band = green[:47, bx0:bx1]
        rows = np.nonzero(~band.any(axis=1))[0]
        rows = rows[(rows > 5) & (rows < 47)]
        if len(rows):
            gaps, s, pr = [], rows[0], rows[0]
            for y in rows[1:]:
                if y == pr + 1:
                    pr = y
                else:
                    gaps.append((s, pr))
                    s = pr = y
            gaps.append((s, pr))
            gaps = [gp for gp in gaps if gp[1] - gp[0] > 7]   # >30/4
            if gaps:
                g0, g1 = gaps[0]
                gc = (g0 + g1) / 2.0 * SY
                dx = (bx0 + bx1) / 2.0 * SX - 160.0
    return np.asarray([by, vy, gc, dx], dtype=np.float32)


def _features_flappy(cur, prev):
    return features_flappy(cur, prev)


def _stack_raw(cur, prev):
    """Causal 2-frame RGB stack: [t-1, t] pixels only."""
    if prev is None:
        prev = np.zeros_like(cur)
    return np.concatenate(
        [prev.ravel(), cur.ravel()]).astype(np.float32) / 255.0


class Brain:
    """The deployed visual-only policy.

    act(rgb_small 60x80x3) -> action str. Owns its own frame history.
    Loads ONLY the artifact npz (+ its .json meta). No other capability
    exists on this class — auditors can read it in one screen.
    """

    def __init__(self, artifact_path):
        z = np.load(artifact_path)
        meta = {}
        js = artifact_path + ".json"
        if os.path.exists(js):
            with open(js) as f:
                meta = json.load(f)
        self.game = meta.get("game", "pong")
        self.control_mode = meta.get("control_mode", "cv+mlp")
        self.classes = list(meta.get("classes", ["DOWN", "NONE", "UP"]))
        self.norm = meta.get("norm", {})
        self.W1 = z["W1"].astype(np.float32)
        self.b1 = z["b1"].astype(np.float32)
        self.W2 = z["W2"].astype(np.float32)
        self.b2 = z["b2"].astype(np.float32)
        mean = self.norm.get("mean")
        std = self.norm.get("std")
        self.mean = (np.asarray(mean, dtype=np.float32)
                     if mean is not None else None)
        self.std = (np.asarray(std, dtype=np.float32)
                    if std is not None else None)
        self._prev = None
        self._steps = 0

    # -- forward identical to TinyMLP.forward (tests assert equality) --
    def _forward(self, x):
        h = np.maximum(x @ self.W1 + self.b1, 0.0)
        return h @ self.W2 + self.b2

    def reset_history(self):
        self._prev = None
        self._steps = 0

    def act(self, rgb_small):
        """THE decision entry point: one small frame in, one action
        out. No other input exists."""
        cur = np.asarray(rgb_small)
        if self.control_mode == "raw+mlp":
            pclean = (np.zeros_like(cur) if self._prev is None
                      else self._prev)
            x = np.concatenate(
                [_as_gray(pclean).ravel(),
                 _as_gray(cur).ravel()]).astype(np.float32) / 255.0
        else:
            x = (features_pong(cur, self._prev) if self.game == "pong"
                 else features_flappy(cur, self._prev))
        if self.mean is not None:
            x = (x - self.mean) / (self.std + 1e-6)
        out = self._forward(x.reshape(1, -1))[0]
        self._prev = cur.copy()
        self._steps += 1
        return self.classes[int(np.argmax(out))]
