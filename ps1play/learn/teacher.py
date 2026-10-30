"""teacher.py — the teachers and the scenario opponent.

DISCLOSURE (mission §3): the teachers are HAND-WRITTEN policies built on
the r11/r12 (pong) and r15 (flappy) controllers. They are baselines and
label sources — NEVER reported as the learned policy. Their information
sources are disclosed per teacher. The PongTeacher and FlappyTeacher
consume frame-derived features (legal visual inputs) so that their
labels transfer to a visual student 1:1; the ScenarioOpponent (pong
port-1) MAY read RAM truth — it is an environment component, not part
of the learned system, and its parameters are the scenario variables.
"""
from collections import deque

import numpy as np

from ps1play.learn.perception import (flappy_bird_y, flappy_gap_geometry,
                                      flappy_green_mask, pong_ball_centroid,
                                      pong_paddle_rows)


class PongTeacher:
    """r11/r12 left-paddle tracking policy (visual).

    info sources: frame-derived ball centroid + left paddle row
    (visual_input). Deadband + speed-aware hold. Actions: UP/DOWN/NONE
    held for STEP=2 frames by the runner.
    """
    name = "pong_teacher_v1"
    info_sources = ["frame_rgb -> ball centroid", "frame_rgb -> paddle row"]

    def __init__(self, deadband=10.0):
        self.deadband = deadband

    def act(self, ball_xy, paddle_row):
        if ball_xy[0] is None or paddle_row is None:
            return "NONE"
        _, by = ball_xy
        if by < paddle_row - self.deadband:
            return "UP"
        if by > paddle_row + self.deadband:
            return "DOWN"
        return "NONE"

    def observe(self, fr):
        cx, cy, _ = pong_ball_centroid(fr)
        lp, _rp = pong_paddle_rows(fr)
        return (cx, cy), lp


class FlappyTeacher:
    """THE r15 PLAY-LOOP law verbatim (r15_flappy_play.py lines
    355-382 — NOT the line-168 sensor-window servo I mis-ported
    first). Differences that matter, all measured in r15:
      * flap threshold ty+14 (the 36px coast then peaks at ty-22 so the
        20px bird box stays inside the 70px gap) + the emergency
        clauses by > ty+26 and by > 162;
      * every flap is a 2-frame B pulse + a 3-frame cooldown (edge
        semantics: hold = ONE flap);
      * stale-gap memory: the last gap target survives a 40-frame
        sliver phase where the band finder returns None;
      * a lost bird (None) = no flap.
    act() carries the pulse/cooldown state machine internally and
    returns FLAP for the pulse frames; the runner forwards B 1:1."""
    name = "flappy_teacher_v2_r15play"
    info_sources = ["frame_rgb -> bird y", "frame_rgb -> gap target",
                    "internal pulse/cooldown state"]

    def __init__(self, below_px=None, hover_y=120.0):
        self.hover_y = hover_y
        self.last_gap = None
        self.last_gap_age = 999
        self.press_remaining = 0
        self.cool_remaining = 0

    def reset_history(self):
        self.last_gap = None
        self.last_gap_age = 999
        self.press_remaining = 0
        self.cool_remaining = 0

    def act(self, bird_y, vy_screen, gap_center):
        if self.press_remaining > 0:
            self.press_remaining -= 1
            if self.press_remaining == 0:
                self.cool_remaining = 3
            return "FLAP"
        if self.cool_remaining > 0:
            self.cool_remaining -= 1
            return "HOVER"
        if gap_center is not None and gap_center > 0:
            self.last_gap = gap_center
            self.last_gap_age = 0
        else:
            self.last_gap_age += 1
        eff = (gap_center if gap_center is not None and gap_center > 0
               else (self.last_gap if self.last_gap_age <= 40 else None))
        if bird_y is None or bird_y < 0:
            return "HOVER"
        ty = eff if eff is not None else self.hover_y
        falling = vy_screen is None or vy_screen >= -0.5
        if ((falling and bird_y > ty + 14) or bird_y > ty + 26
                or bird_y > 162):
            self.press_remaining = 1
            return "FLAP"
        return "HOVER"

    def observe(self, fr, prev_bird_y):
        from ps1play.learn.perception import (
            flappy_gap_target_r15, flappy_green_mask)
        by, _n = flappy_bird_y(fr)
        vy = (by - prev_bird_y) if (by is not None
                                    and prev_bird_y is not None) else None
        green = flappy_green_mask(fr)
        gc, _bx = flappy_gap_target_r15(green, by)
        return by, vy, gc


class FlappyTeacherAgent:
    """Agent-interface adapter: .act(small_rgb) like the Brain, using
    the SAME small-frame visual feature pathway as the cv student
    (fair same-sensory-level comparison). Carries its own
    FlappyTeacher pulse state."""

    name = "flappy_teacher_agent_v2"

    def __init__(self, teacher=None):
        self.t = teacher or FlappyTeacher()
        from ps1play.learn import visual_only as VO
        self._vo = VO

    def reset_history(self):
        self.t.reset_history()
        self._prev_full = None

    def act(self, small):
        f = self._vo.features_flappy(small, self._prev
                                     if hasattr(self, "_prev") else None)
        self._prev = small
        by = f[0] if f[0] >= 0 else None
        gc = f[2] if f[2] >= 0 else None
        return self.t.act(by, f[1], gc)

    def act_full(self, fr):
        """Native-sensor path (full-res vision) — the P1 baseline must
        run on the SAME sensors that collected the data; the students
        stay on the small-frame pathway (same-sensory comparison is
        WITHIN each sensory tier, disclosed in the issue)."""
        by, vy, gc = self.t.observe(fr, self._prev_full)
        self._prev_full = by
        return self.t.act(by, vy if vy is not None else 0.0, gc)


class PongTeacherAgent:
    """Agent-interface adapter for PongTeacher: .act(small_frame) like
    the Brain (visual inputs only — the features are frame-derived).
    Used in evaluation to run the teacher on the SAME protocol."""

    name = "pong_teacher_agent_v1"

    def __init__(self, teacher=None):
        from ps1play.learn.teacher import PongTeacher
        self.t = teacher or PongTeacher(deadband=10.0)
        from ps1play.learn import visual_only as VO
        self._vo = VO

    def reset_history(self):
        pass

    def act(self, small):
        f = self._vo.features_pong(small, None)
        return self.t.act((f[0], f[1]) if f[0] >= 0 else (None, None),
                          f[4] if f[4] > 0 else None)


class PongTeacherV2:
    """PREDICTIVE + EDGE-AIM left-paddle teacher (P4 label source).

    Why a second teacher: the v1 teacher (above) tracks the ball's
    CURRENT y with a deadband — the classic servo lag; the P3 student
    cloned it exactly and could only ever TIE it. To give the student
    labels that EXCEED the P1 baseline, this teacher aims at the ball's
    PREDICTED crossing y (truth velocity -> contact plane x=24, wall
    reflection) with a deterministic edge offset, so its returns leave
    at sharper angles and beatable opponents miss more.

    Information sources (DISCLOSED, assisted modes only — this module
    never ships to the deployed brain):
      * ram ball_x/ball_y truth (0x1FFEA0/0x1FFEA4), read per step
      * the teacher's OWN velocity EWMA state over those readings
      * ram pad_l truth (0x1FFEB0)
      * pong geometry constants (contact plane, paddle half-height 30)
    The edge offset is a DETERMINISTIC function of the predicted
    crossing y (observable in the image), so the mapping the student
    must learn stays single-valued.
    """

    name = "pong_teacher_v2_predictive_edge"
    info_sources = ["ram ball_x/y truth", "own velocity EWMA",
                    "ram pad_l truth", "pong geometry constants"]

    def __init__(self, deadband=3.0, aim_offset=12.0, contact_plane=24.0,
                 vel_alpha=0.8, max_horizon=600.0, close_range=60.0):
        self.deadband = deadband
        self.aim_offset = aim_offset
        self.contact_plane = contact_plane
        self.vel_alpha = vel_alpha
        self.max_horizon = max_horizon
        self.close_range = close_range
        self.prev = None            # (ball_x, ball_y) truth
        self.vx = 0.0
        self.vy = 0.0
        self.last_pred = None       # diagnostics
        self.last_target = None     # diagnostics

    def reset_history(self):
        self.prev = None
        self.vx = self.vy = 0.0
        self.last_pred = None
        self.last_target = None

    def observe_ram(self, ball_x, ball_y):
        """Update the velocity state from TRUTH readings (privileged,
        assisted-only; the deployed student never sees this)."""
        if self.prev is not None:
            vx = float(ball_x) - self.prev[0]
            vy = float(ball_y) - self.prev[1]
            if abs(vx) < 40 and abs(vy) < 40:      # serve-reset guard
                a = self.vel_alpha
                self.vx = (1 - a) * self.vx + a * vx
                self.vy = (1 - a) * self.vy + a * vy
        self.prev = (float(ball_x), float(ball_y))

    def _predict(self):
        from ps1play.learn.visual_only import _fold_playfield
        bx, by = self.prev
        if self.vx < -0.01:
            steps = (self.contact_plane - bx) / self.vx
            if 0.0 <= steps <= self.max_horizon:
                return _fold_playfield(by + self.vy * steps)
        return None

    def act(self, pad_l):
        """pad_l = RAM truth of the left paddle row. UP/DOWN/NONE.

        Law (r54a-measured): at CLOSE range the crossing is imminent —
        track the current y (the P1-proven servo). Far range: aim at the
        PREDICTED crossing with a MODERATE deterministic edge offset
        (the r53b ±26 hold-to-contact experiment MISSED the ball: the
        paddle must stay within ~30 half-height of the crossing path;
        ±12 with deadband 3 keeps contact offset in [9,15] = a solid
        angled hit)."""
        if pad_l is None or self.prev is None:
            return "NONE"
        bx, by = self.prev
        pred = self._predict()
        self.last_pred = pred
        if bx < self.close_range:
            target = float(by)
        elif pred is not None:
            off = self.aim_offset if pred < 120.0 else -self.aim_offset
            target = pred + off
        elif 0.0 <= bx <= 320.0:
            target = float(by)
        else:
            target = 120.0
        self.last_target = target
        if target < pad_l - self.deadband:
            return "UP"
        if target > pad_l + self.deadband:
            return "DOWN"
        return "NONE"


class ScenarioOpponent:
    """Pong port-1 scripted opponent (ENVIRONMENT, not the learned
    system). Tracks the ball with a reaction delay and gaussian aim
    error; its parameters are scenario variables -> held-out opponent
    parameters = genuinely different ball trajectories for the student.

    info sources (disclosed): RAM ball-y truth + RAM right-paddle row.
    """
    name = "scenario_opponent_v1"
    info_sources = ["ram ball-y truth (delayed)", "ram right paddle row",
                    "gaussian aim error"]

    def __init__(self, params, seed=0):
        self.params = dict(params)
        self.rng = np.random.default_rng(seed)
        self.delay = int(params.get("delay_frames", 6))
        self.hist = deque(maxlen=max(1, self.delay))
        self.paddle_row = 90.0            # source: y start = 240/2-30

    def observe(self, ball_truth_y, paddle_truth_row):
        self.hist.append(ball_truth_y)
        self.paddle_row = float(paddle_truth_row)

    def buttons(self):
        if len(self.hist) < self.delay:
            return set()
        obs = self.hist[-1] + float(
            self.rng.normal(0.0, self.params.get("aim_err", 6.0)))
        dead = self.params.get("deadband", 8.0)
        if obs < self.paddle_row - dead:
            return {"UP"}
        if obs > self.paddle_row + dead:
            return {"DOWN"}
        return set()
