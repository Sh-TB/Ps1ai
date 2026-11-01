"""ps1play.runtime.registry — game registration (R62).

The game-agnostic boundary: the runtime core knows games only through
this registry. A second game adds ONE entry (an env factory + an
adapter class) and inherits the entire engine, CLI, telemetry,
lifecycle, and release gate — no runtime-core edits.

`make_env(config)` builds the game env object (the proven
ps1play.learn.games wrappers for flappybird); `adapter_for_game()`
instantiates the GameAdapter over that env. See
docs/r62_architecture.md ("adding a second game") and the example
adapter test (tests/test_r62_runtime.py::TestSecondGameExample) that
plugs a fake game into the real engine.
"""
from __future__ import annotations

import os
from typing import Any, Callable, Dict, Type

from .errors import ConfigError

# game_id -> {"env_factory": fn(config) -> env object,
#             "adapter": GameAdapter subclass}
_REGISTRY: Dict[str, Dict[str, Any]] = {}


def register_game(game_id: str, *, env_factory: Callable,
                  adapter: Type) -> None:
    _REGISTRY[game_id] = {"env_factory": env_factory,
                          "adapter": adapter}


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


def _register_defaults() -> None:
    from ps1play.adapters.flappybird.adapter import (
        FlappyBirdAdapter,  # noqa: PLC0415
    )
    register_game("flappybird", env_factory=_default_env_factory,
                  adapter=FlappyBirdAdapter)


_register_defaults()
