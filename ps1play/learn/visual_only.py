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
import math
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


def _fold_playfield(y):
    """Reflect a raw y into the playfield [0, 240] (pong walls)."""
    m = 480.0
    p = y % m
    if p < 0:
        p += m
    return m - p if p > 240.0 else p


def features_pong_v2(cur, prev, prev_action=None):
    """v2 pong features = v1 prefix + PREDICTIVE + policy-history dims.

    NEW in v2 (all image-derived, causal [t-1, t], disclosed):
      [6] pred_y_at_pad — the ball's y EXTRAPOLATED to the left-paddle
          contact plane (x=24 full-res) with wall reflection; falls back
          to the current ball y (moving right / lost ball -> 120).
          This is the feature that lets the learned controller play
          PREDICTIVE interception instead of the teacher's instantaneous
          tracking (the mechanism by which the student can exceed the
          P1 teacher).
      [7] prev_action == UP   (own policy history, mission-legal)
      [8] prev_action == DOWN
    """
    base = features_pong(cur, prev)
    cx, cy, vx, vy, pad_l, pad_r = (float(v) for v in base)
    if cx >= 0 and vx < -0.01:
        steps = (24.0 - cx) / vx
        pred_y = _fold_playfield(cy + vy * steps) \
            if 0.0 <= steps <= 600.0 else cy
    elif cx >= 0:
        pred_y = cy
    else:
        pred_y = 120.0
    a = prev_action or ""
    return np.asarray(
        [cx, cy, vx, vy, pad_l, pad_r, pred_y,
         1.0 if a == "UP" else 0.0, 1.0 if a == "DOWN" else 0.0],
        dtype=np.float32)


def _flappy_gap_raw(cur):
    """Shared v1/v2 gap finder. Returns (gc, dx, g0, g1) where gc/dx are
    the v1 gap-center / band-center features and g0/g1 the RAW gap top
    and bottom small-rows (v2 gap-edge features; -1 when no gap)."""
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
    gc = dx = g0 = g1 = -1.0
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
    return gc, dx, g0 * SY, g1 * SY, by


def features_flappy(cur, prev):
    """Legal visual features: bird y/vy + the r15 gap-target logic on
    the 60x80 small RGB (the /4-scaled mirror of
    perception.flappy_gap_target_r15 — tests assert both readers agree
    on synthetic frames)."""
    gc, dx, _g0, _g1, by = _flappy_gap_raw(cur)
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
    return np.asarray([by, vy, gc, dx], dtype=np.float32)


def _features_flappy(cur, prev):
    return features_flappy(cur, prev)


def features_flappy_v2(cur, prev, prev_action=None, since_flap=None):
    """v2 flappy features = v1 prefix + gap EDGES + policy history.

    NEW in v2 (all image-derived, causal [t-1, t], disclosed):
      [4] gap_top_y   — the top edge of the current gap (full-res px)
      [5] gap_bot_y   — the bottom edge of the current gap
      [6] prev_FLAP   — the policy's own previous action (mission-legal
          history: "frame + policy history")
      [7] since_flap  — control steps since the last emitted FLAP
          (capped 10; lets the LEARNED policy implement the flap-edge
          pulse/cooldown discipline itself instead of relying on a
          hand-written state machine)
    """
    gc, dx, g0, g1, by = _flappy_gap_raw(cur)
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
    return np.asarray(
        [by, vy, gc, dx, g0, g1,
         1.0 if prev_action == "FLAP" else 0.0,
         float(min(int(since_flap or 0), 10))],
        dtype=np.float32)


def features_flappy_v3(cur, prev, prev_action=None, since_flap=None,
                       last_gc=None, since_gap=None):
    """v3 flappy features = v2 + the policy-owned STALE-GAP memory.

    The r15 law keeps the last gap target alive for <= 40 frames when
    the band finder returns None (the sliver phase between pipes). A
    student that cannot SEE that memory cannot reproduce the law (the
    r54sf1 round measured the ambiguity as ~8% decision error).
    v3 exposes the memory as BRAIN-OWNED history (mission-legal):
      [8] last_gc   — the last non-negative gap center y (fallback -1)
      [9] since_gap — control steps since a gap was visible (capped 40)
    """
    base = features_flappy_v2(cur, prev, prev_action=prev_action,
                              since_flap=since_flap)
    lg = float(last_gc) if last_gc is not None else -1.0
    sg = float(min(int(since_gap or 0), 40))
    return np.concatenate([base, np.asarray([lg, sg], dtype=np.float32)])


def features_flappy_v4(cur, prev, prev_action=None, since_flap=None,
                       last_gc=None, since_gap=None, flap_run=0):
    """v4 flappy features = v2 prefix + FULL policy-owned history.

    The r15 law's button discipline is: a 2-frame FLAP pulse then a
    3-frame cooldown. v3's (prev_FLAP, since_flap) pair is AMBIGUOUS
    inside the pulse (both pulse frames reset since_flap to 0) — the
    r54sf3 round measured the residual as ~3.7% decision error.
    v4 replaces the prev_FLAP dim with flap_run = the number of
    consecutive FLAPs the POLICY itself just emitted (0 = none; the
    pulse frames are run=1 and run=2), making every phase separable:
      run=1 & since=0 -> pulse frame 2 (keep FLAP)
      run>=2          -> pulse done -> cooldown HOVER x3 (since 1..3)
      run=0 & since>=4-> the threshold law
    All dims are image-derived or BRAIN-OWNED history (mission-legal).
    """
    base = features_flappy_v2(cur, prev)
    lg = float(last_gc) if last_gc is not None else -1.0
    sg = float(min(int(since_gap or 0), 40))
    sf = float(min(int(since_flap or 0), 99))
    fr = float(min(int(flap_run or 0), 9))
    return np.asarray(
        [base[0], base[1], base[2], base[3], base[4], base[5],
         fr, sf, lg, sg], dtype=np.float32)


def _flappy_bird_meas(cur):
    """Raw bird measurement + the pipe-green mask on the small frame.

    The caller (FlappyObserver) gates the measurement: trust it only
    when NO pipe green sits near the EXPECTED bird row (a global
    column test is wrong — a pipe far above/below the bird does not
    corrupt its 4x4 blocks). The r54 trace measured the ungated
    centroid FROZEN at ~95-105 while the true bird fell 77->139 (the
    student's first-pipe death). Physics constants are source-verified
    (r15): gravity 0.125 px/f^2, flap impulse 8 px/f.
    """
    r = cur[:, :, 0].astype(int)
    g = cur[:, :, 1].astype(int)
    b = cur[:, :, 2].astype(int)
    yellow = (r > b + 25) & (g > b + 5) & (r > 120)
    yellow[:5, :] = False
    yellow[46:, :] = False
    yellow[:, :32] = False
    yellow[:, 50:] = False
    ys, _xs = np.nonzero(yellow)
    m_by = ys.mean() * SY if len(ys) >= 2 else -1.0
    green = (g > 110) & (g > r + 10) & (b < 175) & (r < g)
    return m_by, green


class FlappyObserver:
    """Policy-owned bird-state observer (the v5 perception).

    Integrates the SOURCE-VERIFIED bird dynamics between trusted
    measurements and corrects ONLY on trusted ones:
      vy[t]   = -8.0                 if the policy's own previous
                                     action was FLAP (the impulse
                                     resets velocity exactly)
               vy[t-1] + 0.125       otherwise (gravity)
      y[t]    = y[t-1] + vy[t]
      y[t]    <- measurement         when the measurement is trusted
    All inputs are the policy's OWN action history + rendered frames —
    mission-legal (frame + policy history). Disclosed in the artifact
    meta and the issue's information-source table.
    """

    # DATA-FITTED dynamics (r54k fit on 45k recorded frames):
    # the 2-frame flap pulse applies vy=-8 on its SECOND frame; the
    # rise decelerates at +1.0 px/f^2; the fall is TERMINAL at +2
    # px/f. (The r15 note's "gravity 0.125 / impulse 8" is the same
    # curve in 1/8-px fixed-point units: 0.125*8=1.0, 2=0.25*8.)
    GRAVITY = 1.0
    TERMINAL = 2.0
    IMPULSE = -8.0

    def __init__(self):
        self.reset()

    def reset(self):
        self.y = None            # last integrated bird y (full-res px)
        self.vy = 0.0
        self.run = 0             # consecutive own-FLAP count
        self.ever_measured = False

    def step(self, cur, own_prev_action):
        """Advance one control step; returns the (by, vy) features."""
        # 1) integrate the motion since the previous decision using
        #    the action this policy emitted then
        self.run = (min(self.run + 1, 9) if own_prev_action == "FLAP"
                    else 0)
        if self.y is not None:
            if self.run == 2:            # the pulse's impulse frame
                self.vy = self.IMPULSE
            else:
                self.vy = min(self.vy + self.GRAVITY, self.TERMINAL)
            self.y = self.y + self.vy
        # 2) gated measurement correction: trust the centroid ONLY when
        #    no pipe green sits near the EXPECTED bird row (cols 32..38
        #    = the bird's body; +/- 8 rows covers the 20px bird box)
        m_by, green = _flappy_bird_meas(cur)
        trusted = False
        if m_by >= 0:
            if self.y is None:
                trusted = True
            else:
                r_est = int(self.y / SY)
                lo, hi = max(0, r_est - 8), min(60, r_est + 9)
                trusted = not bool(green[lo:hi, 32:39].any())
        if trusted:
            if self.y is not None and self.ever_measured:
                # jump sanity at 28px: a 1-frame move beyond it means the
                # centroid latched onto something else (the 45px bound
                # let latches THROUGH and blocked coast re-locks)
                if abs(m_by - self.y) <= 28.0:
                    self.y = m_by
            else:
                self.y = m_by
            self.ever_measured = True
        by_feat = self.y if self.ever_measured else -1.0
        vy_feat = self.vy if self.ever_measured else 0.0
        return by_feat, vy_feat


class FlappyObserverV2:
    """Latch-guarded bird tracker (v6 perception).

    The raw small-frame centroid is TRUSTED BY DEFAULT; a physics
    coast (data-fitted: impulse -8 on the 2nd pulse frame, accel
    +1.0/f^2, terminal fall +2) takes over ONLY while the raw reading
    is FROZEN (|delta| < 0.8 px for >= 5 consecutive steps) — the
    r54-measured pipe-overlap latch (centroid stuck at ~95-105 while
    the bird fell 77->139). When the raw reading moves again, it
    re-locks automatically: no jump-gate deadlock (the v1 observer's
    failure mode).
    """

    GRAVITY = 1.0
    TERMINAL = 2.0
    IMPULSE = -8.0
    FROZEN_STEPS = 5

    def __init__(self):
        self.reset()

    def reset(self):
        self.coast_y = None
        self.coast_vy = 0.0
        self.run = 0
        self.last_raw = None
        self.frozen = 0
        self.latch = False

    def step(self, cur, own_prev_action):
        """Advance one control step; returns the (by, vy) features."""
        # 1) raw measurement (no gate, no jump check)
        m_by, _green = _flappy_bird_meas(cur)
        raw_vy = 0.0
        if m_by >= 0:
            if self.last_raw is not None:
                raw_vy = float(np.clip(m_by - self.last_raw, -9.0, 3.0))
                self.frozen = (self.frozen + 1
                               if abs(m_by - self.last_raw) < 0.8 else 0)
            self.last_raw = m_by
        # 2) physics coast (always integrated; own flap run drives it)
        self.run = (min(self.run + 1, 9) if own_prev_action == "FLAP"
                    else 0)
        if self.coast_y is not None:
            if self.run == 2:
                self.coast_vy = self.IMPULSE
            else:
                self.coast_vy = min(self.coast_vy + self.GRAVITY,
                                    self.TERMINAL)
            self.coast_y += self.coast_vy
        # 3) latch arbitration
        self.latch = self.frozen >= self.FROZEN_STEPS
        if not self.latch and m_by >= 0:
            self.coast_y = m_by          # the coast re-locks on raw
            self.coast_vy = raw_vy
        # 4) outputs
        if self.latch and self.coast_y is not None:
            return self.coast_y, self.coast_vy
        if m_by >= 0:
            return m_by, raw_vy
        if self.coast_y is not None:
            # dropout: the bird is not visible; the coast carries on
            return self.coast_y, self.coast_vy
        return -1.0, 0.0


def _flappy_bird_cues(cur):
    """R55f-CALIBRATED small-frame bird evidence (measured on recorded
    frames, scripts/r55f_cues.py + the r55h trace dissection):
      sky      = (72,184,192)  -> g,b high, r LOW
      body     = (219,219,219) -> r,g,b all high, |r-g| ~ 0
      face     = (201,188,48)  -> r >= g, b ~ 0..75
      outline  = (74,74,74)    -> ALL channels low
      clouds   = (224,240,208) -> g - r ~ 16 (excluded by |r-g|<14)
      digit    = (219,219,219) = the SAME white as the body -> handled
                 by position (the score glyph lives at small rows 9..15)
      pipes    = (130,166,72)..(178,202,104) -> g > r + 8 ALWAYS.

    THE r54 LATCH ROOT CAUSE (r55h, proven by pixel dissection): the
    v1 'yellow' test (r > b+25) fires on EVERY pipe green (the pipe's
    red channel sits 24-60 above its blue) — 40-50 pipe blocks swamp
    the 5-8 bird blocks whenever a pipe shares the bird's column band,
    and their symmetric mass centroid lands at y ~ 95-110: the frozen
    "95-105 latch".
    The r55m PROXIMITY RULE replaces a single face threshold: the bird
    spans TWO orange classes (the bright face r-g >= 13; the dim body
    edges r-g 3..6) while the score glyph's anti-aliased edge sits at
    r-g = 3 — (147,144,94), the tv7m_k90 death — INSEPARABLE from the
    dim bird class by any global threshold. But every real bird
    carries STRONG face pixels: weak orange (r > g+3) is kept only
    within 2 small blocks of strong orange (r > g+8) — the digit edge
    has no strong neighbor and dies, the bird's dim edges ride its
    bright beak.
    Returns (orange, white, dark) masks restricted to the bird's fixed
    column band (small cols 36..47, rows 5..46)."""
    r = cur[:, :, 0].astype(int)
    g = cur[:, :, 1].astype(int)
    b = cur[:, :, 2].astype(int)
    base = (r > 120) & (r > b + 25) & (g < 210)
    strong = (r > g + 8) & base
    weak = (r > g + 3) & base
    near_strong = strong.copy()
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            near_strong |= np.roll(np.roll(strong, dy, axis=0),
                                   dx, axis=1)
    orange = weak & near_strong
    white = ((r > 195) & (g > 195) & (b > 185)
             & (np.abs(r - g) < 14))
    dark = (r < 110) & (g < 110) & (b < 110)
    band = np.zeros(cur.shape[:2], dtype=bool)
    band[5:46, 36:47] = True
    return orange & band, white & band, dark & band


class BirdObserverV7:
    """v7 bird tracker — MULTI-CUE + RIDING-WINDOW physics fusion.

    The r54 failure chain, and what breaks it here:
      * the beak-only sensor (the r15 'yellow' test) reads a ~27px
        orange patch that vanishes behind the score glyph or a pipe
        edge -> the old centroid LATCHED on whatever static junk kept
        passing the test (measured: frozen at ~95-105 while the bird
        fell 77->139).
      * v7 reads the WHOLE bird (face + body + outline, r55f
        calibration) and NEVER searches a fixed window: the evidence
        window RIDES the physics prediction and grows only with the
        blind-streak length. Static junk therefore leaves the window
        as the coasted prediction moves on — the latch cannot hold.
    Dynamics (r55k, MEASURED on 183 corpus impulse events + the law-
    regime fall table — supersedes the r54k 'terminal +2' fit that the
    8-frame rounding plateaus had faked): impulse -8 on the 2nd pulse
    frame; the rise arc decelerates at exactly +1 px/f^2 (integer
    steps); the fall accelerates at +0.125 px/f^2 with the screen dy
    ROUNDED HALF-UP (plateaus 0/+1/+2/+3 of ~4/7/8/8 frames); no fall
    cap.
    Inputs: rendered small frames + the policy's OWN action history —
    mission-legal (frame + policy history), disclosed in the meta.
    """

    GRAVITY = 1.0          # the rise arc only
    FALL_G = 0.125         # the fall acceleration (px/f^2)
    IMPULSE = -8.0
    ROW0, ROW1 = 5, 46          # small-row search band
    DIGIT = (9, 16, 38, 44)     # score glyph box r0:r1, c0:c1
    MASS_MIN = 1.6              # a lone noise block = 0.8

    def __init__(self):
        self.reset()

    def reset(self):
        self.y = None
        self.vy = 0.0
        self.run = 0
        self.ever = False
        self.since_trust = 99

    def _score_map(self, cur):
        """Bird evidence map (orange 1.0 + white 0.8 per small block)
        with the score-glyph box removed unless the face overlaps the
        BOX PROPER (the bird drawn IN FRONT of the digit keeps its
        orange). r55m fix: the padded +-2-row window let a bird flying
        BELOW the glyph (its face at rows 16-17, y 64-70) keep the box
        active, the glyph's white entered the evidence map and the
        centroid LATCHED on the digit while the true bird fell away
        (the tv7m_k90 death: obs frozen at 28-48 vs beak 66->99)."""
        orange, white, dark = _flappy_bird_cues(cur)
        r0, r1, c0, c1 = self.DIGIT
        near = orange[r0:r1, c0:c1]
        if not bool(near.any()):
            white = white.copy()
            white[r0:r1, c0:c1] = False
            orange = orange.copy()
            orange[r0:r1, c0:c1] = False
        return orange, white, dark, (1.0 * orange + 0.8 * white)

    def step(self, cur, own_prev_action):
        """One control step -> (by, vy) in full-res px (by -1 when the
        bird has never been seen).

        BEAK-PRIORITY measurement (r55h trace lesson): the r15 law's
        thresholds are calibrated on the orange-face (beak) reading —
        during steep climbs the sprite tilts nose-up and the BODY
        centroid shifts 5-8px above the face, which alone eats the
        ~7px arc-apex margin. The measurement is therefore the face
        centroid whenever the face is visible, and the body centroid
        +4px (the level-flight face offset) only as a fallback.
        Boundary-bias guard: the window clips the evidence during fast
        motion; the centroid is computed over evidence rows that do
        NOT touch the window edges when possible (the clipped-side
        rows bias the centroid toward the window center)."""
        self.run = (min(self.run + 1, 9) if own_prev_action == "FLAP"
                    else 0)
        if self.y is not None:
            if self.run == 2:
                self.vy = self.IMPULSE
            elif self.vy < 0:
                self.vy = min(self.vy + self.GRAVITY, 0.0)
            else:
                self.vy = self.vy + self.FALL_G
            dy = math.floor(self.vy + 0.5) if self.vy > 0 else self.vy
            self.y = self.y + dy
        orange, white, dark, score = self._score_map(cur)
        meas = None

        def _centroid(mask, lo, hi):
            rows = np.nonzero(mask[lo:hi].any(axis=1))[0]
            if len(rows) == 0:
                return None
            # drop window-edge rows (clipped evidence) when the band
            # has interior rows left
            if len(rows) > 1:
                if rows[0] == 0 and rows[-1] != (hi - lo - 1):
                    rows = rows[1:]
                elif rows[-1] == (hi - lo - 1) and rows[0] != 0:
                    rows = rows[:-1]
            m = mask[lo:hi][rows]
            w = m.sum(axis=1).astype(float)
            return (float((rows * w).sum() / w.sum()) + lo) * SY

        if self.ever:
            # RIDING window: half-height grows with the blind streak
            pr = self.y / SY
            h = 4 + min(self.since_trust, 21) // 3      # 4..11 rows
            lo = max(self.ROW0, int(pr) - h)
            hi = min(self.ROW1, int(pr) + h + 1)
            o_n = float(orange[lo:hi].sum())
            w_n = float(white[lo:hi].sum())
            if o_n >= 1.0 or w_n >= 2.0:
                if o_n >= 1.0:
                    meas = _centroid(orange, lo, hi)
                else:
                    meas = (_centroid(white, lo, hi) or 0.0) + 4.0
        else:
            o_n = float(orange.sum())
            w_n = float(white.sum())
            if o_n >= 1.0 or w_n >= 2.0:
                if o_n >= 1.0:
                    meas = _centroid(orange, self.ROW0, self.ROW1)
                else:
                    meas = (_centroid(white, self.ROW0, self.ROW1)
                            or 0.0) + 4.0
        # desperate re-lock after a long blind stretch: global search
        # with a generous 60px gate (the coast may have drifted)
        if meas is None and self.ever and self.since_trust >= 25:
            if float(score.sum()) >= 2.0:
                ys = np.nonzero(score)[0]
                cand = float(ys.mean()) * SY
                if abs(cand - self.y) <= 60.0:
                    meas = cand
        trusted = meas is not None
        if trusted:
            self.y = meas
            self.ever = True
            self.since_trust = 0
        else:
            self.since_trust = min(self.since_trust + 1, 99)
        return (self.y if self.ever else -1.0,
                self.vy if self.ever else 0.0)


def _flappy_gap_raw2(cur, by_hint=None):
    """R55 gap finder v3 — v2 + CONSTANT-GAP BIRD DECONTAMINATION.

    The r55j-k90 measurement (tv7g_k90 trace, steps 263..331): inside
    ONE static pipe the raw reading ALTERNATED between the true 125
    and a bird-biased 141 — the bird occludes the rim rows behind its
    body, those rows drop below the pipe fraction and EXTEND the free
    run downward by ~32px (+16 on the center); the tracker's 24px
    consistency gate then adopted the bias and the law flew a 16px
    too-low line into the bottom rim. v3 removes the contamination at
    the source: the physical gap height is CONSTANT 70px (source), so
    a free run LONGER than ~82px proves one side is bird-extended, and
    the side NEARER the bird is the dirty one — the center pins on the
    OPPOSITE edge (top+35 / bottom-35). The magic |c-110| prior is
    replaced by the sharper-transition rule (a true rim transition
    reads ~1.0; a bird-softened one reads lower).

    Inherits v2's calibrations (r55f/r55h/r55i, all measured on
    recorded frames): measured pipe greens, band rows 5..41, whole-band
    fraction profile, >= 8-row runs, sharp-edge voting.
    r55j-k90 mask fix (measured on the same frames): the v2 brightness
    gates (g > 135, r < 205) REJECTED the pipe gradient's bright
    (216,232,128) and shaded (80,120,40) ends, so the lower-pipe rows
    flipped free/pipe as the band width wobbled (3/6 vs 3/9 columns
    passing) — the 125<->141 alternation. The measured pipe hue rule
    (every sampled pipe pixel keeps g > r + 8 AND b < g - 40, while
    sky/clouds/buildings all carry b >= g - 40) replaces them:
    (g > r + 8) & (b < g - 40) — the profile reads solid pipe.
    by_hint = the observer's bird y (full-res px) from the SAME step —
    the caller passes it AFTER its observer step (the Brain and the
    law-on-v7 agent both do); None falls back to the frame's own bird
    reading. Returns (gc, dx, g0, g1, by) — same semantics as v1/v2."""
    r = cur[:, :, 0].astype(int)
    g = cur[:, :, 1].astype(int)
    b = cur[:, :, 2].astype(int)
    green = (g > r + 8) & (b < g - 40)
    orange, white, _dark = _flappy_bird_cues(cur)
    by = -1.0
    if by_hint is not None and by_hint >= 0:
        by = float(by_hint)
    elif float(orange.sum()) >= 1.0:
        ys, _xs = np.nonzero(orange)
        by = ys.mean() * SY
    elif float(white.sum()) >= 2.0:
        ys, _xs = np.nonzero(white)
        by = ys.mean() * SY + 4.0
    colsum = green[5:41, :].sum(axis=0)
    cs = np.maximum(np.maximum(colsum[:-2], colsum[1:-1]), colsum[2:])
    colsum = np.concatenate([[colsum[0]], cs, [colsum[-1]]])
    bands, start = [], None
    for x in range(30, 80):
        if colsum[x] > 10:
            if start is None:
                start = x
        else:
            if start is not None and x - start >= 2:
                bands.append((start, x))
            start = None
    if start is not None and 80 - start >= 2:
        bands.append((start, 80))
    # MERGE bands separated by a single dip column: the pipe's own
    # column sum can dip for one column (the rim's dark edge) and the
    # split fragments then dilute the fraction profile so the soft rim
    # rows flip free/pipe — the tv7m_k6/k60 death (a 19px whole-run
    # up-shift adopted as the "next pipe's" gap).
    merged = []
    for bd in bands:
        if merged and bd[0] - merged[-1][1] <= 1:
            merged[-1] = (merged[-1][0], bd[1])
        else:
            merged.append(bd)
    bands = merged
    gc = dx = g0 = g1 = -1.0
    if bands:
        # BAND PICK with the bird-overlap preference: the pipe at/over
        # the bird = the band overlapping the bird's fixed columns
        # (36..47 small); a qualifying band left of the bird that does
        # NOT overlap it must not steal the pick (the r15 semantics:
        # the pipe the bird must fly THROUGH)
        qualifying = [bd for bd in bands if bd[1] > 32]
        bird_bands = [bd for bd in qualifying
                      if bd[0] <= 47 and bd[1] >= 36]
        pick = (bird_bands[0] if bird_bands
                else (qualifying[0] if qualifying else bands[0]))
        bx0, bx1 = pick
        cols = list(range(bx0, bx1))
        if len(cols) >= 3:
            # CORE-WINDOW profile (the r55m source fix): a row is PIPE
            # iff ANY 3 adjacent band columns are mostly green. The
            # plain band mean sits at 5/9 vs 4/9 columns on the pipe's
            # boundary rows — ONE edge column's sub-pixel washout flips
            # 4 rim-adjacent rows and shifts the whole reported gap by
            # 19px (the tv7n_k6/k60/k90 deaths: the law flapped at the
            # shifted target and rose into the top rim). The pipe's
            # solid core reads 1.0 in every window; the junk edges
            # cannot dilute it.
            gband = green[5:46, :]
            frac = np.zeros(41)
            for i in range(41):
                frac[i] = max(gband[i, c:c + 3].mean()
                              for c in range(bx0, bx1 - 2))
            pipe = frac >= 0.5
            free = np.nonzero(~pipe)[0]
            if len(free) >= 8:
                splits = np.split(
                    free, np.nonzero(np.diff(free) > 1)[0] + 1)
                best = None          # (score, gc_cand, g0, g1)
                for rp in splits:
                    if len(rp) < 8:
                        continue
                    rt, rb = int(rp[0]), int(rp[-1])   # rows rel. +5
                    top_frac = frac[rt - 1] if rt > 0 else 0.0
                    bot_frac = frac[rb + 1] if rb < len(frac) - 1 \
                        else 0.0
                    top_ok = top_frac >= 0.6
                    bot_ok = bot_frac >= 0.6
                    g0c = (rt + 5) * SY
                    g1c = (rb + 5) * SY
                    if g1c - g0c > 82.0:
                        # BIRD-EXTENDED RUN: the constant-gap prior
                        # pins the center on the edge AWAY from the
                        # bird (the near side is the occluded rim)
                        bird_row = by / SY if by >= 0 else None
                        if bird_row is None:
                            if top_frac >= bot_frac and top_ok:
                                best = (1.0, g0c + 35.0,
                                        g0c, g0c + 70.0)
                            elif bot_ok:
                                best = (1.0, g1c - 35.0,
                                        g1c - 70.0, g1c)
                        elif (bird_row - 5.0) > (rt + rb) / 2.0:
                            if top_ok:
                                best = (1.0, g0c + 35.0,
                                        g0c, g0c + 70.0)
                        elif bot_ok:
                            best = (1.0, g1c - 35.0, g1c - 70.0, g1c)
                    else:
                        cands = []
                        if top_ok:
                            cands.append((top_frac, g0c + 35.0,
                                          g0c, g1c))
                        if bot_ok:
                            cands.append((bot_frac, g1c - 35.0,
                                          g0c, g1c))
                        if len(cands) == 2:
                            best = (2.0, (cands[0][1]
                                          + cands[1][1]) / 2.0,
                                    g0c, g1c)
                        elif len(cands) == 1:
                            best = (1.0, cands[0][1], g0c, g1c)
                    if best is not None:
                        break
                if best is not None:
                    gc = best[1]
                    g0, g1 = best[2] * 1.0, best[3] * 1.0
                    dx = (bx0 + bx1) / 2.0 * SX - 160.0
    return gc, dx, g0, g1, by


class GapTrackerV7:
    """Temporal filter + pipe-identity tracker for the v7 gap readings.

    r55j lessons baked in (each measured from a death trace):
      * SINGLE-FRAME SPIKES: one garbage gc (a bird-hole-merged run
        voting through one clean-looking edge) triggers one wrong flap
        whose ~36px impulse arc then clips the pipe -> median-of-3 and
        a consistency gate.
      * LOCK-ON-GARBAGE at re-acquire: after the pass's blind streak
        the gate opened to ANY reading, including exit junk -> the
        tracker held junk and REJECTED the true readings (k90 death:
        the law flew the stale height into the bottom pipe).
      * EXIT-PHASE IDENTITY: while a pipe scrolls out, its band's
        bird-free columns still read its TRUE (static) gap — those
        valid readings kept 'since' at 0, so the re-acquire gate never
        opened for the genuinely NEW pipe (k60 death: the law flew the
        OLD gap's height as the new pipe arrived). The pipe identity
        is the BAND's x: pipes scroll left ~1.4px/f, so a band whose
        center JUMPS right by > 12px is a NEW pipe.

    Protocol: step() takes (gc, g0, g1, bx) or None; returns the
    filtered gap center or None (the caller's stale-gap memory then
    carries, exactly like the full-res finder returning None). The
    r15 law itself stays verbatim."""

    JUMP = 12.0          # band-center jump that means "new pipe"
    CONSIST = 24.0       # same-pipe reading tolerance
    DRIFT = 8.0          # adopt-immediately tolerance; a mid-size
                         # shift (the rim-wobble class) needs 2-of-3
    ACQ_N = 3            # acquire = N persistent readings
    ACQ_SPREAD = 10.0
    REJECT_STREAK = 6
    REFRACTORY = 10      # steps of jump-suppression after a reset

    def __init__(self):
        self.reset()

    def reset(self):
        self.gc = None
        self.since = 99
        self.last_bx = None
        self.hist = []
        self.acq = []
        self.reject_streak = 0
        self.reject_hist = []
        self.refractory = 0
        self.mid = []

    def step(self, reading):
        if reading is None or reading[0] is None or reading[0] < 0:
            self.since += 1
            self.refractory = max(0, self.refractory - 1)
            return None
        gc, _g0, _g1, bx = reading
        if (self.refractory == 0 and self.last_bx is not None
                and bx - self.last_bx > self.JUMP):
            self.acq = []                     # a new pipe arrived
            self.hist = []
            self.reject_streak = 0
            self.reject_hist = []
            self.gc = None                    # the law's memory carries
            self.refractory = self.REFRACTORY
        self.last_bx = float(bx)
        self.refractory = max(0, self.refractory - 1)
        self.hist.append(float(gc))
        self.hist = self.hist[-3:]
        med = float(np.median(self.hist))
        if self.gc is None:
            # ACQUIRE: the new pipe's gap is vertically static, so the
            # readings must bunch up before they are trusted
            self.acq.append(med)
            self.acq = self.acq[-self.ACQ_N:]
            if (len(self.acq) >= self.ACQ_N
                    and max(self.acq) - min(self.acq)
                    <= self.ACQ_SPREAD):
                self.gc = float(np.median(self.acq))
                self.since = 0
                self.acq = []
                return self.gc
            self.since += 1
            return None
        if abs(med - self.gc) <= self.CONSIST:
            delta = abs(med - self.gc)
            if delta <= self.DRIFT:
                self.gc = med
                self.since = 0
                self.reject_streak = 0
                self.reject_hist = []
                self.mid = []
                return self.gc
            # MID-SIZE SHIFT (8..24px): the rim-wobble / early-next-pipe
            # class — one bad frame must not retarget the law while the
            # bird is still mid-gap (the tv7m_k6/k60 death); require
            # 2-of-3 persistence
            self.mid.append(med)
            self.mid = self.mid[-2:]
            if (len(self.mid) >= 2
                    and max(self.mid) - min(self.mid) <= 6.0):
                self.gc = med
                self.since = 0
                self.reject_streak = 0
                self.reject_hist = []
                self.mid = []
                return self.gc
            self.since += 1
            return None
        # inconsistent: exit junk or a lock-on-garbage to break
        self.since += 1
        self.mid = []
        self.reject_streak += 1
        self.reject_hist.append(med)
        self.reject_hist = self.reject_hist[-self.REJECT_STREAK:]
        if self.reject_streak >= self.REJECT_STREAK:
            rm = float(np.median(self.reject_hist))
            if max(self.reject_hist) - min(self.reject_hist) <= 8.0:
                # the rejected readings are self-consistent -> the
                # held value was the garbage; adopt theirs
                self.gc = rm
                self.since = 0
                self.reject_streak = 0
                self.reject_hist = []
                return self.gc
        return None


def features_flappy_v5(cur, by_obs, vy_obs, since_flap=None,
                       last_gc=None, since_gap=None, flap_run=0):
    """v5 flappy features: the OBSERVER bird state replaces the raw
    centroid/diff pair; the rest is the v2 gap + v4 history block:
      [0] by_obs  (observer bird y, full-res px)
      [1] vy_obs  (observer bird vy, screen px/f)
      [2] gc      gap center (raw finder)
      [3] dx      band center - 160
      [4] g0      gap top edge
      [5] g1      gap bottom edge
      [6] flap_run    (policy-owned)
      [7] since_flap  (policy-owned)
      [8] last_gc     (policy-owned stale-gap memory)
      [9] since_gap   (policy-owned)
    """
    _gc, _dx, g0, g1, _raw_by = _flappy_gap_raw(cur)
    by = float(by_obs) if by_obs is not None else -1.0
    vy = float(np.clip(float(vy_obs or 0.0), -10.0, 10.0))
    lg = float(last_gc) if last_gc is not None else -1.0
    sg = float(min(int(since_gap or 0), 40))
    sf = float(min(int(since_flap or 0), 99))
    fr = float(min(int(flap_run or 0), 9))
    return np.asarray(
        [by, vy, _gc, _dx, g0, g1, fr, sf, lg, sg], dtype=np.float32)


def features_flappy_v7(cur, by_obs, vy_obs, since_flap=None,
                       last_gc=None, since_gap=None, flap_run=0,
                       gc_obs=None):
    """v7 flappy features — the v5 LAYOUT with the v7 perception:
    the bird state comes from BirdObserverV7 (passed in by the caller,
    the SAME observer the deployed brain runs) and the gap block from
    the r55 gap finder v3 (bird-decontaminated: by_obs feeds the
    constant-gap pinning). gc_obs = the GapTrackerV7-filtered center;
    when provided it REPLACES the instantaneous reading in dim [2]
    (the label source decides on the filtered value — the student must
    see exactly what the law saw, same-sensor discipline)."""
    _gc, _dx, g0, g1, _raw_by = _flappy_gap_raw2(cur, by_hint=by_obs)
    if gc_obs is not None:
        _gc = float(gc_obs)
    by = float(by_obs) if by_obs is not None else -1.0
    vy = float(np.clip(float(vy_obs or 0.0), -10.0, 10.0))
    lg = float(last_gc) if last_gc is not None else -1.0
    sg = float(min(int(since_gap or 0), 40))
    sf = float(min(int(since_flap or 0), 99))
    fr = float(min(int(flap_run or 0), 9))
    return np.asarray(
        [by, vy, _gc, _dx, g0, g1, fr, sf, lg, sg], dtype=np.float32)


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
        self.feature_version = int(meta.get("feature_version", 1))
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
        self._prev_action = None
        self._since_flap = 99
        self._flap_run = 0
        self._last_gc = -1.0
        self._since_gap = 40
        self._observer = None
        self._steps = 0

    # -- forward identical to TinyMLP.forward (tests assert equality) --
    def _forward(self, x):
        h = np.maximum(x @ self.W1 + self.b1, 0.0)
        return h @ self.W2 + self.b2

    def reset_history(self):
        self._prev = None
        self._prev_action = None
        self._since_flap = 99
        self._flap_run = 0
        self._last_gc = -1.0
        self._since_gap = 40
        self._observer = None
        self._gap_tracker = None
        self._gc_obs = None
        self._steps = 0

    def _vector(self, cur):
        """The decision input vector: pixels (raw+mlp) or features.
        v2 adds the policy's OWN history (prev action / since flap) —
        mission-legal: the deployed policy may always know what IT did."""
        if self.control_mode == "raw+mlp":
            pclean = (np.zeros_like(cur) if self._prev is None
                      else self._prev)
            return np.concatenate(
                [_as_gray(pclean).ravel(),
                 _as_gray(cur).ravel()]).astype(np.float32) / 255.0
        if self.feature_version >= 7 and self.game == "flappy":
            if self._observer is None:
                self._observer = BirdObserverV7()
                self._gap_tracker = GapTrackerV7()
            self._by_obs, self._vy_obs = self._observer.step(
                cur, self._prev_action)
            _gcr, _dxr, _g0r, _g1r, _byr = _flappy_gap_raw2(
                cur, by_hint=self._by_obs)
            self._gc_obs = self._gap_tracker.step(
                (_gcr, _g0r, _g1r, _dxr + 160.0))
            return features_flappy_v7(cur, self._by_obs, self._vy_obs,
                                      since_flap=self._since_flap,
                                      last_gc=self._last_gc,
                                      since_gap=self._since_gap,
                                      flap_run=self._flap_run,
                                      gc_obs=self._gc_obs)
        if self.feature_version >= 6 and self.game == "flappy":
            if self._observer is None:
                self._observer = FlappyObserverV2()
            self._by_obs, self._vy_obs = self._observer.step(
                cur, self._prev_action)
            return features_flappy_v5(cur, self._by_obs, self._vy_obs,
                                      since_flap=self._since_flap,
                                      last_gc=self._last_gc,
                                      since_gap=self._since_gap,
                                      flap_run=self._flap_run)
        if self.feature_version >= 5 and self.game == "flappy":
            if self._observer is None:
                self._observer = FlappyObserver()
            self._by_obs, self._vy_obs = self._observer.step(
                cur, self._prev_action)
            return features_flappy_v5(cur, self._by_obs, self._vy_obs,
                                      since_flap=self._since_flap,
                                      last_gc=self._last_gc,
                                      since_gap=self._since_gap,
                                      flap_run=self._flap_run)
        if self.feature_version >= 4 and self.game == "flappy":
            return features_flappy_v4(cur, self._prev,
                                      since_flap=self._since_flap,
                                      last_gc=self._last_gc,
                                      since_gap=self._since_gap,
                                      flap_run=self._flap_run)
        if self.feature_version >= 3 and self.game == "flappy":
            return features_flappy_v3(cur, self._prev,
                                      prev_action=self._prev_action,
                                      since_flap=self._since_flap,
                                      last_gc=self._last_gc,
                                      since_gap=self._since_gap)
        if self.feature_version >= 2:
            if self.game == "pong":
                return features_pong_v2(cur, self._prev,
                                        prev_action=self._prev_action)
            return features_flappy_v2(cur, self._prev,
                                      prev_action=self._prev_action,
                                      since_flap=self._since_flap)
        return (features_pong(cur, self._prev) if self.game == "pong"
                else features_flappy(cur, self._prev))

    def act(self, rgb_small):
        """THE decision entry point: one small frame in, one action
        out. No other input exists."""
        cur = np.asarray(rgb_small)
        x = self._vector(cur)
        if self.mean is not None:
            x = (x - self.mean) / (self.std + 1e-6)
        out = self._forward(x.reshape(1, -1))[0]
        action = self.classes[int(np.argmax(out))]
        self._prev = cur.copy()
        self._prev_action = action
        if action == "FLAP":
            self._since_flap = 0
            self._flap_run = min(self._flap_run + 1, 9)
        else:
            self._since_flap = min(self._since_flap + 1, 99)
            self._flap_run = 0
        if self.feature_version >= 7 and self.game == "flappy":
            if self._gc_obs is not None:
                self._last_gc = self._gc_obs
                self._since_gap = 0
            else:
                self._since_gap = min(self._since_gap + 1, 40)
        elif self.feature_version >= 3 and self.game == "flappy":
            gc = float(features_flappy(cur, None)[2])
            if gc >= 0:
                self._last_gc = gc
                self._since_gap = 0
            else:
                self._since_gap = min(self._since_gap + 1, 40)
        self._steps += 1
        return action
