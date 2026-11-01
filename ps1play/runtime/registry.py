"""ps1play.runtime.registry — game registration (R62, R64).

The game-agnostic boundary: the runtime core knows games only through
this registry. A second game adds ONE entry (an env factory + an
adapter class + an optional per-game policy factory + a progress
label) and inherits the entire engine, CLI, telemetry, lifecycle, and
release gate — no runtime-core game knowledge.

R64 (Tetrade) added the two generic extension points the recipe
needed:

  * `policy_factory` — a game may ship a BUILT-IN policy (a
    hand-written heuristic behind the Policy contract) instead of the
    frozen-model RuntimePolicy; when the entry carries no factory the
    engine falls back to RuntimePolicy exactly as R62 did.
  * `progress_label` — the human name of the generic per-episode
    progress counter (flappy: "pipes", tetrade: "lines"); the CLI
    summary prints it, the episode record keeps the generic key.

`make_env(config)` builds the game env object; `adapter_for_game()`
instantiates the GameAdapter; `policy_for_game()` instantiates the
Policy. See docs/r62_architecture.md ("adding a second game") —
Tetrade (ps1play/adapters/tetrade) is the worked example.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional, Type

from .errors import ConfigError

# game_id -> {"env_factory": fn(config) -> env object,
#             "adapter": GameAdapter subclass,
#             "policy_factory": fn(config, telemetry) -> Policy|None,
#             "progress_label": str}
_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_game(game_id: str, *, env_factory: Callable,
                  adapter: Type, policy_factory: Optional[Callable] = None,
                  progress_label: str = "pipes") -> None:
    _REGISTRY[game_id] = {"env_factory": env_factory,
                          "adapter": adapter,
                          "policy_factory": policy_factory,
                          "progress_label": progress_label}


def registered_games() -> list:
    return sorted(_REGISTRY)


def make_env(config):
    if config.game not in _REGISTRY:
        raise ConfigError(
            f"game {config.game!r} is not registered; known: "
            f"{registered_games()}")
    return _REGISTRY[config.game]["env_factory"](config)


def adapter_for_game(game_id: str, env: Any, telemetry=None):
    if game_id not in _REGISTRY:
        raise ConfigError(
            f"game {game_id!r} is not registered; known: "
            f"{registered_games()}")
    return _REGISTRY[game_id]["adapter"](env, telemetry=telemetry)


def policy_for_game(config, telemetry=None):
    """The per-game Policy: a registered built-in policy factory when
    the game ships one, the frozen-model RuntimePolicy otherwise."""
    ent = _REGISTRY.get(config.game)
    if ent is None:
        raise ConfigError(
            f"game {config.game!r} is not registered; known: "
            f"{registered_games()}")
    if ent["policy_factory"] is not None:
        return ent["policy_factory"](config, telemetry=telemetry)
    from .policy_runtime import RuntimePolicy  # noqa: PLC0415
    return RuntimePolicy(config, telemetry=telemetry)


def progress_label_for(game_id: str) -> str:
    if game_id not in _REGISTRY:
        raise ConfigError(
            f"game {game_id!r} is not registered; known: "
            f"{registered_games()}")
    return str(_REGISTRY[game_id]["progress_label"])


def component_versions() -> Dict[str, str]:
    """Adapter versions for the runtime manifest (best-effort)."""
    out: Dict[str, str] = {}
    for gid, ent in _REGISTRY.items():
        out[f"adapter_{gid}"] = str(getattr(ent["adapter"],
                                            "version", "?"))
    return out


# ------------------------------------------------------------ --
# the built-in registration
# ------------------------------------------------------------ --

def _default_env_factory(config):
    """The real flappy factory: honors config.workspace / config.iso_path
    by constructing FlappyEnv with an explicit cue when overridden."""
    from ps1play.learn.games import FlappyEnv  # noqa: PLC0415
    import ps1play.learn.games as games_mod  # noqa: PLC0415
    ws = config.workspace or os.path.join(
        "/home/z/my-project/emu/games_homebrew", "ws_r62_runtime")
    if config.iso_path:
        # an explicit cue: build via BaseEnv with that disc
        env = FlappyEnv.__new__(FlappyEnv)
        games_mod.BaseEnv.__init__(env, ws, config.iso_path)
        return env
    return FlappyEnv(workspace=ws)


def _tetrade_env_factory(config):
    """Tetrade: BaseEnv over the license-patched disc (the exact R63
    boot: openbios firmware, headless beetle core)."""
    from ps1play.learn.games import BaseEnv  # noqa: PLC0415
    from .session import GAME_DEFAULT_ISO  # noqa: PLC0415
    ws = config.workspace or os.path.join(
        "/home/z/my-project/emu/games_homebrew", "ws_r64_tetrade")
    cue = config.iso_path or GAME_DEFAULT_ISO["tetrade"]
    return BaseEnv(ws, cue)


def _register_defaults() -> None:
    from ps1play.adapters.flappybird.adapter import (
        FlappyBirdAdapter,  # noqa: PLC0415
    )
    register_game("flappybird", env_factory=_default_env_factory,
                  adapter=FlappyBirdAdapter,
                  progress_label="pipes")

    def _tetrade_policy_factory(config, telemetry=None):
        from ps1play.adapters.tetrade import (  # noqa: PLC0415
            DellacheriePolicy,
        )
        return DellacheriePolicy(config, telemetry=telemetry)

    from ps1play.adapters.tetrade.adapter import (  # noqa: PLC0415
        TetradeAdapter,
    )
    register_game("tetrade", env_factory=_tetrade_env_factory,
                  adapter=TetradeAdapter,
                  policy_factory=_tetrade_policy_factory,
                  progress_label="lines")


_register_defaults()
