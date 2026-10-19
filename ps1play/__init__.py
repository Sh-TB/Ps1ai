"""ps1play — an agentic, plugin-based PS1 gaming base for AI agents.

Design goals:
- Runs PS1 games headless (no GPU/X11) via libretro cores (Beetle PSX / SwanStation).
- Agent observes the game through *RAM bytes* (token-minimal), NOT pixels.
- Plays like a human: only button inputs are injected. No memory writes, no cheats.
- Universal core + per-game plugins (boot script, state inference, policy, features).
- Learns per-game "profiles" (memory candidates, boot script) after 1-2 runs and
  reuses them forever, so agents never repeat thousands of discovery steps.
- Save states + progress journal => "continue from where you left off".
"""
__version__ = "0.1.0"

from .api import PS1Play  # noqa: F401
