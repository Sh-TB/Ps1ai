"""ps1play.runtime.config — runtime configuration (R62).

A single validated dataclass shared by the engine, the CLI and the
release gate. Everything the autonomous run needs is explicit here;
there are no hidden globals. `config_hash()` pins the effective
configuration into the runtime manifest and every episode record.

Validation is fail-early (the repo's ConfigError convention): an
invalid config never reaches the emulator.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .errors import ConfigError

REPO = "/home/z/my-project/ps1ai"

DEFAULTS = {
    "model_path": os.path.join(
        REPO, "deployment", "flappybird_policy", "models",
        "r60_soup_e6a010.onnx"),
    "manifest_path": os.path.join(
        REPO, "data", "learn", "FINAL_MODEL_MANIFEST.json"),
    "authority_manifest_path": os.path.join(
        REPO, "data", "learn", "FINAL_MODEL_MANIFEST.json"),
    "max_frames_per_episode": 10000,     # the R59/R61 budget
    "max_runtime_s": 300,
    "log_every_frames": 0,               # 0 = episode-boundary only
    "screenshot_interval": 0,            # frames; 0 = endpoints only
    "status_every_frames": 600,
    "boot_timeout_s": 120.0,
    "ready_timeout_s": 60.0,
    "boot_retries": 2,
    "max_consecutive_failures": 2,
}

RUNTIME_VERSION = "1.0.0"


@dataclass
class RuntimeConfig:
    """The complete configuration of one autonomous run."""

    game: str = "flappybird"
    episodes: int = 1                    # 0 = unlimited (explicit opt-in)
    seed_k: Optional[int] = None         # None = default episode ladder
    headless: bool = True
    record: bool = False                 # screenshots + GIF video
    screenshot: bool = False             # episode-end screenshots only
    video: bool = False                  # GIF assembly (needs record)
    max_frames_per_episode: int = int(DEFAULTS["max_frames_per_episode"])
    max_runtime_s: float = float(DEFAULTS["max_runtime_s"])
    output_dir: str = ""
    config_path: Optional[str] = None
    model_path: str = DEFAULTS["model_path"]
    manifest_path: str = DEFAULTS["manifest_path"]
    authority_manifest_path: str = DEFAULTS["authority_manifest_path"]
    workspace: str = ""                  # empty = game default
    iso_path: str = ""                   # empty = game default (cue)
    verify_hashes: bool = True
    verbose: bool = False
    stop_on_error: bool = True           # never retry into a broken env
    restart_policy: str = "fixed"        # fixed | time | frames
    seed_ladder_start: int = 6
    seed_ladder_step: int = 6
    boot_timeout_s: float = float(DEFAULTS["boot_timeout_s"])
    ready_timeout_s: float = float(DEFAULTS["ready_timeout_s"])
    boot_retries: int = int(DEFAULTS["boot_retries"])
    log_every_frames: int = int(DEFAULTS["log_every_frames"])
    screenshot_interval: int = int(DEFAULTS["screenshot_interval"])
    status_every_frames: int = int(DEFAULTS["status_every_frames"])
    max_consecutive_failures: int = int(DEFAULTS["max_consecutive_failures"])
    profile: str = "default"
    extra: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------ --
    def validated(self) -> "RuntimeConfig":
        """Fail-early validation. Returns self. The game must be
        REGISTERED (the registry is the single source of truth — R64:
        flappybird + tetrade)."""
        from .registry import registered_games  # noqa: PLC0415
        known = registered_games()
        if self.game not in known:
            raise ConfigError(
                f"unknown game {self.game!r}: registered games are "
                f"{known} (see ps1play/runtime/registry.py)")
        if self.episodes < 0:
            raise ConfigError("episodes must be >= 0 (0 = unlimited)")
        if self.episodes == 0 and self.restart_policy == "fixed":
            raise ConfigError(
                "episodes=0 (unlimited) requires an explicit time or "
                "frame limit (restart_policy=time|frames) — the "
                "default command must never start an unbounded run")
        if self.max_frames_per_episode < 1:
            raise ConfigError("max_frames_per_episode must be >= 1")
        if self.max_frames_per_episode > 1_000_000:
            raise ConfigError(
                "max_frames_per_episode cap is 1,000,000 (safety)")
        if self.max_runtime_s <= 0:
            raise ConfigError("max_runtime_s must be > 0")
        if self.max_runtime_s > 24 * 3600:
            raise ConfigError("max_runtime_s cap is 24h (safety)")
        if self.seed_k is not None and (self.seed_k < 0 or
                                        self.seed_k > 10**9):
            raise ConfigError("seed_k out of range [0, 1e9]")
        if self.restart_policy not in ("fixed", "time", "frames"):
            raise ConfigError("restart_policy must be fixed|time|frames")
        if self.boot_retries < 0 or self.boot_retries > 5:
            raise ConfigError("boot_retries must be in [0, 5]")
        if self.screenshot_interval < 0 or self.status_every_frames < 0:
            raise ConfigError("intervals must be >= 0")
        if not self.output_dir:
            raise ConfigError("output_dir must be resolved before use")
        return self

    def seed_for_episode(self, episode: int) -> int:
        """The deterministic seed ladder (R61 convention: the press
        timing k creates the pipe sequence). episode is 1-based."""
        if self.seed_k is not None:
            return int(self.seed_k)
        return (self.seed_ladder_start
                + (episode - 1) * self.seed_ladder_step)

    def config_hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True,
                          default=str).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {f.name: getattr(self, f.name)
                for f in dataclasses.fields(self)}

    @classmethod
    def from_json(cls, path: str) -> "RuntimeConfig":
        try:
            with open(path) as f:
                raw = json.load(f)
        except OSError as e:
            raise ConfigError(f"config file unreadable: {path}: {e}")
        except json.JSONDecodeError as e:
            raise ConfigError(f"config file is not valid JSON: "
                              f"{path}: {e}")
        if not isinstance(raw, dict):
            raise ConfigError(f"config root must be an object: {path}")
        known = {f.name for f in dataclasses.fields(cls)}
        cfg = cls(config_path=path)
        for k, v in raw.items():
            if k == "extra":
                cfg.extra.update(v)
            elif k in known:
                setattr(cfg, k, v)
            else:
                cfg.extra[k] = v
        return cfg.validated()

    def write_json(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=1, default=str)
