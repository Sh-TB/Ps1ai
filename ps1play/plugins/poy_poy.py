"""PoyPoyPlugin — Poy Poy (USA, SLUS-00486) plugin, contract v1.

Session-4 evidence: boot + input causality (START diff 181.4). Menu
probes menu2/3 (session 4) are VOID: their timings landed inside the
boot cinematic (see docs + scripts/poypoy_calib.py).

TRUE BOOT SEQUENCE (calib strip, 2026-10-24):
  boot -> early title (~420) -> START(90) -> BLACK -> Konami
  cinematic -> "WAIT A MOMENT" -> "NOW LOADING" -> (c) splash
  "PRESS START!" (~1830) -> START -> static -> START -> MODE SELECT
  (interactive instance; the menu seen ~1770 after ONE START is the
  ATTRACT SHOWCASE rendering — input disabled there).

DISC GROUND TRUTH (strings @ bin offsets):
  7925868 "Use the Directional button. Press the <SJIS 817E = x>
           button to select."  -> X is CONFIRM (on-screen help bar
           verified on the menu itself)
  7926432 "Press the <x> button to stop the wheel." -> team select is
           a ROULETTE WHEEL (animated until X stops it)
  7926396 "Press the <SJIS 81A2 = triangle> button to exit."

SESSION-5 PROBES (menu4-menu18, scripts committed, evidence local):
  - X taps (20f) on the menu NEVER register; X-HOLD (60f) on the
    interactive menu produces a 131,364-byte RAM state transition
    (menu -> field scene) — the confirm DID fire (menu17).
  - the post-X-hold sequence (+700..+3000f) ignores direction input
    (left==right within 3 bytes; determinism baseline 0 — the core is
    FULLY deterministic, none-arm replays are byte-exact) — no player
    control observed yet; demo-segment vs pre-control phase
    UNRESOLVED.
  - attract demo plays CPU-vs-CPU exhibition matches WITH READY!
    countdowns and HUD — visually identical to real matches; the
    only valid discriminator is RAM input-causality, not screenshots.
HONEST SCOPE: boot_script drives the verified path to the interactive
MODE SELECT; match entry BLOCKED-by-discovery (control handoff).
Method assets: scripts/poypoy_menu16-18.py (RAM-census causality
probe; menu_anchor savestate, local-only)."""
from .base import GamePlugin


class PoyPoyPlugin(GamePlugin):
    ID = "poy_poy"
    SERIALS = ("SLUS-00486",)
    OPTIONAL_OPS = ()

    def boot_script(self):
        """Static approximation of the verified gate path (calib strip
        + menu17): title START -> cinematic/loads -> splash START ->
        static -> START -> interactive MODE SELECT. The preferred
        runner is the polling walker (scripts/poypoy_menu17.py
        try_gate) — static steps can land a frame off the splash."""
        cached = self.profile.get("boot_script")
        if cached:
            return cached
        steps = [{"op": "wait", "frames": 480},
                 {"op": "tap", "btns": "START", "frames": 90},
                 {"op": "wait", "frames": 1300},   # cinematic + loads
                 {"op": "tap", "btns": "START", "frames": 90},
                 {"op": "wait", "frames": 250},
                 {"op": "tap", "btns": "START", "frames": 90},
                 {"op": "wait", "frames": 250}]
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
