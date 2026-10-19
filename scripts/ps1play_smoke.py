#!/usr/bin/env python3
"""Smoke test: boot Metal Slug X headless with the new ps1play package."""
import sys
sys.path.insert(0, "/home/z/my-project")
from ps1play.api import PS1Play  # noqa: E402

p = PS1Play("/home/z/my-project/ps1-test/emu/games/Metal Slug X (USA).cue")
info = p.boot()
print("boot:", info)
p.core.run(120)
print("obs:", p.observe())
print("ram stats:", p.mem.stats())
print("serialize_size:", len(p.core.serialize()))
p.core.shutdown()
print("SMOKE OK")
