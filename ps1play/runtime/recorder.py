"""ps1play.runtime.recorder — screenshots + video + live event frames
(R62).

Off by default (headless-safe); enabled with --record/--screenshot.

  * screenshots: PNG via PIL at episode endpoints always (when any
    recording is on) and every `screenshot_interval` decision frames
    when > 0. Written incrementally — nothing large is held in RAM.
  * video: a GIF assembled from frames sampled every `video_stride`
    frames (PIL, streaming append into a frame list capped by a temp
    dir; the GIF is written once at episode end). Video must never
    slow the control loop: sampling is ~1 capture re-use (the frame is
    already in memory), encoding happens at finish().
  * every screenshot is timestamped and referenced from the episode
    record (Stage B evidence list).
"""
from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional


class Recorder:
    def __init__(self, cfg, session, episode_no: int, seed_k: int,
                 telemetry):
        self.cfg = cfg
        self.session = session
        self.episode = episode_no
        self.seed_k = seed_k
        self.tel = telemetry
        self.shots: List[str] = []
        self._video_frames: List[Any] = []
        self._shots_dir = os.path.join(cfg.output_dir, "shots")
        os.makedirs(self._shots_dir, exist_ok=True)
        self._video_stride = max(1, int(cfg.extra.get(
            "video_stride", 12)))
        self._video_cap = max(2, int(cfg.extra.get("video_cap", 900)))

    # ------------------------------------------------------------ --
    def _shot(self, rgb, tag: str) -> str:
        from PIL import Image  # noqa: PLC0415
        path = os.path.join(
            self._shots_dir,
            f"ep{self.episode:03d}_k{self.seed_k}_{tag}.png")
        try:
            Image.fromarray(rgb).save(path)
            self.shots.append(path)
            self.tel.emit("screenshot", path=path, tag=tag)
            return path
        except OSError as e:
            self.tel.emit("screenshot_error", error=str(e), tag=tag)
            return ""

    def maybe(self, step: int, frame, nf, obs, decision, post) -> None:
        """Called once per decision frame when recording is on. Never
        raises into the control loop."""
        try:
            interval = self.cfg.screenshot_interval
            if interval and step % interval == 0:
                self._shot(frame.rgb, f"f{step:05d}")
            if self.cfg.video and step % self._video_stride == 0 \
                    and len(self._video_frames) < self._video_cap:
                from PIL import Image  # noqa: PLC0415
                self._video_frames.append(
                    Image.fromarray(frame.rgb).convert("P", palette=1))
            if post.get("pipe_passed"):
                self._shot(nf.rgb, f"pipe{post.get('passage_step')}")
            if step == 0:
                self._shot(frame.rgb, "start")
        except Exception as e:              # noqa: BLE001
            self.tel.emit("recorder_error", error=str(e))

    def finish(self, adapter, steps: int, result: str,
               _unused: List[str]) -> Optional[str]:
        """Episode-end screenshot + optional GIF; returns video path."""
        try:
            fr = self.session.env.frame()
            if fr is not None:
                self._shot(fr, f"end_{result}")
        except Exception:
            pass
        if not (self.cfg.video and len(self._video_frames) >= 2):
            self._video_frames = []
            return None
        path = os.path.join(self.cfg.output_dir,
                            f"video_ep{self.episode:03d}"
                            f"_k{self.seed_k}.gif")
        try:
            first, rest = self._video_frames[0], self._video_frames[1:]
            first.save(path, save_all=True, append_images=rest,
                       duration=1000 // 10, loop=0, optimize=True)
            self.tel.emit("video", path=path,
                          frames=len(self._video_frames))
            return path
        except OSError as e:
            self.tel.emit("video_error", error=str(e))
            return None
        finally:
            self._video_frames = []
