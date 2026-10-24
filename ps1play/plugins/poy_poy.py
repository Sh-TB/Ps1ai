"""PoyPoyPlugin — Poy Poy (USA, SLUS-00486) plugin, contract v1.

Session-4 evidence: boot + input causality (START diff 181.4). This
session (menu probes poypoy_menuprobes/menu2/menu3): the path
title -> START -> MODE SELECT (EXHIBITION/POYPOY CUP/OPTIONS) is
data-frozen; cursor navigation (DOWN/UP) verified live by diff; the
MATCH-ENTRY confirm button is NOT yet identified: X/O/START/SQ/TR
produce no forward transition from MODE SELECT, X/O/START bounce to
the title after a long idle (an attract idle-timeout is suspected,
>=120f safe idle, ~200f+ risky). Honest scope: this plugin drives the
verified path to MODE SELECT and wiggles the cursor; match entry is
BLOCKED-by-discovery, not claimed.
"""
from .base import GamePlugin


class PoyPoyPlugin(GamePlugin):
    ID = "poy_poy"
    SERIALS = ("SLUS-00486",)
    OPTIONAL_OPS = ()

    def boot_script(self):
        cached = self.profile.get("boot_script")
        if cached:
            return cached
        steps = [{"op": "wait", "frames": 420}]
        steps += [{"op": "tap", "btns": "START", "frames": 90},
                  {"op": "tap", "btns": "", "frames": 90},
                  {"op": "tap", "btns": "START", "frames": 60},
                  {"op": "wait", "frames": 240}]
        return steps

    def features(self, mem, obs):
        return {"changed_bytes": obs.get("changed_bytes")}

    def policy(self, ctx):
        """Cursor wiggle on MODE SELECT (verified navigation), no
        unverified confirm claims."""
        c = ctx["chunk"]
        n = ctx.get("progress") or 0.0
        btn = {"DOWN"} if int(n * 10) % 2 == 0 else {"UP"}
        return [{"btns": btn, "frames": 10},
                {"btns": set(), "frames": max(0, c - 10)}]
