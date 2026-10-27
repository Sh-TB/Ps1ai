"""PoyPoyPlugin — Poy Poy (USA, SLUS-00486) plugin, contract v1.

Session-4 evidence: boot + input causality (START diff 181.4). Menu
probes menu2/3 (session 4) are VOID: their timings landed inside the
boot cinematic (see docs + scripts/poypoy_calib.py).

TRUE BOOT SEQUENCE (menu20 passive timeline + menu21/22/23, 2026-10-27;
SUPERSEDES the 2026-10-24 calib strip: the splash/static START taps were
pressed at AUTO transitions — all of it plays itself):
  boot -> KONAMI logo (~f1200) -> title "PRESS START!" (~f2400,
  window ends when the ATTRACT DEMO starts by itself ~f3000 — the
  arena scene with "GO!!") -> START-hold 60f AT THE TITLE -> MODE
  SELECT (EXHIBITION / POYPOY CUP / OPTIONS). The state reached by the
  old gate walk (anchor 6210) was the input-disabled showcase/demo —
  X-hold there only skips to title (menu19: X-hold==START-hold
  byte-identical transition).

DISC GROUND TRUTH (strings @ bin offsets):
  7925868 "Use the Directional button. Press the <SJIS 817E = x>
           button to select."  -> X is CONFIRM (on-screen help bar
           verified on the menu itself)
  7926432 "Press the <x> button to stop the wheel." -> team select is
           a ROULETTE WHEEL (animated until X stops it)
  7926396 "Press the <SJIS 81A2 = triangle> button to exit."

ROUND-16 (2026-10-27, menu19-23) — MATCH ENTRY UNBLOCKED, control CAUSAL:
  verified ladder (checkpointed at every rung; B = PSX CROSS, ps1play "B"):
  title(f2350) --START-hold60--> MODE SELECT --B-hold60-->
  PLAYER SET UP (1P human + 3 CPU, OK preselected) --B-hold60-->
  PLAYER ENTRY (HARRY default 1P) --B-hold60--> GLOVE SET UP
  (per-player glove list; ticker "the [x] button to select")
  --B-hold60--> PRACTICE ARENA: "PRESS THE START BUTTON TO EXIT
  PRACTICE" + full control legend (X=THROW, O=SUPLEX, sq=SLAM,
  R1=SPECIAL, X=PICKUP/DUCK, O+dir=JUMP, dir+O=DIVE); LEFT vs RIGHT
  census 54,357 differing bytes with det_none=0 => verdict REAL_MATCH
  (player control causal — the blocker since session 4 is closed).
  NEXT: START exits practice into the real match; then the closed-loop
  player agent (the demo-vs-real discriminator stays RAM causality).
HONEST SCOPE: boot_script drives the verified path to the PRACTICE
arena; a real (non-practice) match win is NOT claimed yet.
Method assets: scripts/poypoy_menu19-23.py (relative-stepping census;
load_state does NOT restore frames_run — step with p.core.run(n) after
rewinds)."""
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
        steps = [{"op": "wait", "frames": 2350},   # ride the auto boot to the title window
                 {"op": "tap", "btns": "START", "frames": 60},   # -> MODE SELECT
                 {"op": "wait", "frames": 480},
                 {"op": "tap", "btns": "B", "frames": 60},       # confirm EXHIBITION
                 {"op": "wait", "frames": 480},
                 {"op": "tap", "btns": "B", "frames": 60},       # PLAYER SET UP: OK
                 {"op": "wait", "frames": 480},
                 {"op": "tap", "btns": "B", "frames": 60},       # PLAYER ENTRY: HARRY
                 {"op": "wait", "frames": 480},
                 {"op": "tap", "btns": "B", "frames": 60},       # GLOVE SET UP: confirm
                 {"op": "wait", "frames": 480}]                  # -> PRACTICE arena
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
