"""PS1Play — the one-class API every agent (LLM or script) needs.

Minimal-token session flow:
    p = PS1Play(game).boot()
    p.run_steps(p.plugin.boot_script())     # get to gameplay
    p.discover("RIGHT")                     # 1st-run pattern extraction
    p.play(6000)                            # policy plays, checkpoints roll
    p.save_state("stage1"); p.load_state("stage1")   # resume anywhere
All methods return small JSON-able dicts (LLM-friendly).
"""
import json
import os
import sys
import time

import numpy as np

from .core.host import LibretroCore
from .core.memory import MemoryView
from .core.statemgr import StateManager, Journal
from .agent.observer import Observer
from .agent.discovery import DiscoverySession
from .agent.loop import AgentLoop
from .plugins.base import parse_serial, detect_plugin
from . import labconfig
from .labconfig import ConfigError                      # noqa: F401 (re-export)

# v0.12: machine-specific absolute defaults were removed. Defaults now
# resolve through the shared configuration contract (env var > gitignored
# machine config). They may legitimately be None — PS1Play then fails
# early with a concise, actionable error instead of a ctypes traceback.
DEFAULT_CORE = labconfig.resolve_path("core")
DEFAULT_WORKSPACE = labconfig.resolve_path("workspace")
DEFAULT_PROFILES = os.path.join(os.path.dirname(__file__), "profiles")


def _corner_blue(arr):
    h, w = arr.shape[:2]
    regs = (arr[:45, :45], arr[:45, -45:], arr[-45:, :45], arr[-45:, -45:])
    tot = 0.0
    for r in regs:
        tot += float(((r[:, :, 2] > 120) & (r[:, :, 2] > r[:, :, 0] + 40) &
                      (r[:, :, 2] > r[:, :, 1] + 30)).mean())
    return tot / 4.0


class PS1Play:
    def __init__(self, game, core=None, workspace=None,
                 profile_dir=DEFAULT_PROFILES, profile_name=None,
                 states_dir=None, journal_path=None, verbose=False,
                 var_overrides=None):
        # v0.12: explicit fail-early configuration contract. A None or
        # missing core/workspace is an immediate, actionable error —
        # never a silent fallback to a different environment.
        core = core if core is not None else DEFAULT_CORE
        workspace = workspace if workspace is not None else \
            DEFAULT_WORKSPACE
        if not core:
            raise ConfigError(
                "no libretro core configured — pass core=..., set "
                "M1_CORE, or create .autolab_config.json (see "
                "ps1play/labconfig.py)")
        if not os.path.exists(core):
            raise ConfigError(f"libretro core not found: {core}")
        if not workspace:
            raise ConfigError(
                "no workspace configured — pass workspace=..., set "
                "M1_WORKSPACE, or create .autolab_config.json")
        self.game = game
        self.core_path = core
        self.workspace = workspace
        self.verbose = verbose
        # Forwarded to LibretroCore (core options such as
        # beetle_psx_override_bios); None keeps the defaults.
        self.var_overrides = var_overrides
        self.system_dir = os.path.join(workspace, "system")
        self.save_dir = os.path.join(workspace, "saves")
        self.states_dir = states_dir or os.path.join(workspace, "states")
        os.makedirs(self.save_dir, exist_ok=True)
        self.profile_path = os.path.join(
            profile_dir, (profile_name or
                          os.path.splitext(os.path.basename(game))[0]) + ".json")
        self.journal_path = journal_path or os.path.join(
            self.states_dir, "journal.jsonl")
        self.core = None
        self.plugin = None
        self.profile = {}
        self.t = 0

    # ---------------- lifecycle ----------------
    def boot(self):
        for d in (self.system_dir, self.save_dir, self.states_dir):
            os.makedirs(d, exist_ok=True)
        self.core = LibretroCore(self.core_path, self.system_dir,
                                 self.save_dir, verbose=self.verbose,
                                 var_overrides=self.var_overrides)
        self.core.load_game(self.game)
        self.mem = MemoryView(self.core.ram)
        self.observer = Observer(self.mem)
        self.observer.mark()
        self._fc_last = 0
        self.states = StateManager(self.states_dir)
        self.disc = DiscoverySession(self.core, self.mem)
        serial = parse_serial(self.game)
        cls = detect_plugin(serial)
        self.profile = self._load_profile()
        self.profile.setdefault("serial", serial)
        self.profile.setdefault("plugin", cls.ID)
        self.plugin = cls(self.profile)
        return {"core": f"{self.core.core_name} {self.core.core_ver}",
                "serial": serial, "plugin": self.plugin.ID,
                "ram_bytes": len(self.mem),
                "profile_reused": self.profile.get("discovered") is not None}

    # ---------------- profile (learned knowledge) ----------------
    def _load_profile(self):
        if os.path.exists(self.profile_path):
            with open(self.profile_path) as f:
                return json.load(f)
        return {}

    def save_profile(self):
        os.makedirs(os.path.dirname(self.profile_path), exist_ok=True)
        self.profile["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(self.profile_path, "w") as f:
            json.dump(self.profile, f, indent=1)
        return {"profile": self.profile_path}

    def _remember(self, role, cand):
        if not cand:
            return None
        disc = self.profile.setdefault("discovered", {})
        prev = disc.get(role)
        if prev and prev.get("score", 0) >= cand.get("score", 0):
            return None
        disc[role] = {k: cand[k] for k in ("addr", "dtype", "score", "dir")}
        return disc[role]

    # ---------------- movement ----------------
    def _advance(self):
        delta = self.core.frames_run - self._fc_last
        self._fc_last = self.core.frames_run
        self.t += delta
        return delta

    # ---------------- universal: get into playable state ----------------
    def _changed_count(self, frames, buttons):
        """How many RAM bytes changed across a window (activity metric)."""
        s0 = self.mem.snapshot()
        self.core.run(frames, buttons)
        s1 = self.mem.snapshot()
        return int(np.count_nonzero(s0 != s1))

    def _confirm_gameplay(self, addr, dt, windows=3, per=100, min_gain=30):
        """Anti-menu confirmation: a REAL player keeps advancing while
        RIGHT is held. Menu cursors saturate after one step, so three
        consecutive strictly-increasing windows prove actual gameplay."""
        read = self.mem.u32 if dt == "u32" else self.mem.u16
        vals = []
        for _ in range(windows):
            self.core.run(per, {"RIGHT"})
            vals.append(read(addr))
        self._advance()
        mono = all(b > a for a, b in zip(vals, vals[1:]))
        return mono and (vals[-1] - vals[0]) >= min_gain, vals

    def enter_gameplay(self, max_taps=14, window=30, thresh=8):
        """Generic 'human-like' boot: play the plugin's coarse boot script,
        then tap START and PROBE RAM: are we actually controlling something?

        Probe = correlate('RIGHT'): 2 consecutive passing probes mean a
        movement counter responds to input (real gameplay, not a menu —
        menu cursors move once and fail the repeat probe).
        Game-agnostic: works for any game where moving moves something.
        """
        boot = self.run_steps(self.plugin.boot_script())
        taps = 0
        ok_streak = 0
        best = None
        probe = []
        debug = os.environ.get("PS1PLAY_DEBUG")
        for _ in range(max_taps):
            probe = self.disc.correlate("RIGHT", window=window, reps=2)
            top = probe[0] if probe else None
            if debug:
                print(f"[enter_dbg] tap={taps} t={self.t} "
                      f"n_cands={len(probe)} top={top}")
            if top and top["score"] >= thresh and top["dir"] == "+":
                ok_streak += 1
                if best is None or top["score"] > best["score"]:
                    best = top
                if ok_streak >= 2:
                    ok, _vals = self._confirm_gameplay(best["addr"],
                                                       best["dtype"])
                    if ok:
                        self._remember("player_x", best)
                        self.profile.setdefault("history", []).append(
                            {"op": "enter_gameplay", "taps": taps,
                             "addr": best["addr"], "dtype": best["dtype"],
                             "score": best["score"]})
                        self._advance()
                        return {"in_game": True, "taps": taps, "probe": best,
                                "boot_frames": boot["t"]}
                    ok_streak = 0
            else:
                ok_streak = 0
            self.core.run(15, {"START"})
            # keep moving between taps (a standing player gets killed and
            # the game Game-Over's back to title — exactly like a human
            # who refuses to stand still). Run right + hop.
            self.core.run(225, {"RIGHT"})
            self.core.run(15, {"RIGHT", "X"})
            self.core.run(45, {"RIGHT"})
            taps += 1
        self._advance()
        png = None
        try:
            from PIL import Image
            rgb = self.core.frame_rgb()
            if rgb is not None:
                png = "/tmp/enter_gameplay_fail.png"
                Image.fromarray(rgb).save(png)
        except Exception:
            pass
        return {"in_game": False, "taps": taps, "png": png,
                "best": (probe[:3] if probe else [])}

    def enter_gameplay2(self, max_rounds=8):
        """Menu-proof navigation (learned from MSX behavior):
        - START during the attract demo boots 1P directly
        - B confirms menu selections (OK?/YES ignores START)
        - UP puts the dialog cursor on YES
        - direction HOLDS in menus move cursors -> never hold during nav
        Round = punch A (title/menu/demo) -> probe -> punch B (dialog
        confirm + skip intros) -> probe. Probe = correlate(RIGHT) plus a
        sustained-movement confirm, so attract demos CANNOT fool it (the
        demo ignores our input; a real player accelerates)."""
        boot = self.run_steps(self.plugin.boot_script())
        probe = []
        dbg = os.environ.get("PS1PLAY_NAV_DEBUG")
        if dbg:
            os.makedirs("/tmp/navdbg", exist_ok=True)
            _seq = [0]

            def _snap(tag):
                _seq[0] += 1
                try:
                    from PIL import Image
                    rgb = self.core.frame_rgb()
                    if rgb is not None:
                        Image.fromarray(rgb).resize((320, 240)).save(
                            f"/tmp/navdbg/{_seq[0]:03d}_{tag}.png")
                except Exception:
                    pass
        else:
            def _snap(tag):
                pass

        def try_enter(tag):
            """Activity-ratio detector (game-generic): real gameplay is
            INPUT-RESPONSIVE — holding RIGHT scrolls the whole world
            (huge byte churn) while idle windows churn far less. Attract
            demos churn at the same rate either way (ratio ~1), menus
            barely churn at all, pause = zero. Two consecutive passes."""
            results = []
            for k in range(2):
                i1 = self._changed_count(40, set())
                r = self._changed_count(80, {"RIGHT"})
                i2 = self._changed_count(40, set())   # aftermath (ignored)
                if dbg:
                    print(f"[nav] try{tag} act{k}: idle1={i1} run={r} "
                          f"idle2={i2}", file=sys.stderr)
                    _snap(f"try{tag}_act{k}")
                results.append((i1, r, i2))
                # Compare only against the PRE-run idle: after running,
                # the world keeps churning (bullets/enemies in flight),
                # so idle2 is polluted. A demo churns at ~equal rate in
                # both windows (ratio ~1); real play ratio is 2.5-5x.
                ok = (r > 1.5 * max(i1, 1)) and r > 3000
                if not ok:
                    return None
            self._advance()
            self.profile.setdefault("history", []).append(
                {"op": "enter_gameplay2", "round": tag,
                 "detector": "activity_ratio",
                 "probe": results[0]})
            return {"in_game": True, "round": tag, "detector": "activity",
                    "boot_frames": boot["t"]}

        for rnd in range(1, max_rounds + 1):
            # punch A: start game from title/demo / select in menus
            for k in range(3):
                self.core.run(15, {"START"})
                self.core.run(45, set())
                _snap(f"r{rnd}a{k}_start")
                self.core.run(15, {"B"})
                self.core.run(45, set())
                _snap(f"r{rnd}a{k}_b")
            self._advance()
            r = try_enter(rnd * 10)
            if r:
                return r
            # punch B: dialog confirm + skip intros.
            # Learned: circle(A) CONFIRMS the OK?/YES dialog (cross=B
            # cancels it), UP puts the cursor on YES, B re-opens the
            # dialog if we are sitting on the menu list instead.
            for k in range(4):
                self.core.run(10, {"UP"})
                self.core.run(30, set())
                self.core.run(15, {"A"})
                self.core.run(45, set())
                _snap(f"r{rnd}b{k}_a")
                self.core.run(15, {"B"})
                self.core.run(45, set())
                self.core.run(15, {"A"})
                self.core.run(45, set())
                _snap(f"r{rnd}b{k}_a2")
            self.core.run(60, set())         # ensure unpaused before probe
            self._advance()
            r = try_enter(rnd * 10 + 1)
            if r:
                return r
        png = None
        try:
            from PIL import Image
            rgb = self.core.frame_rgb()
            if rgb is not None:
                png = "/tmp/enter_gameplay2_fail.png"
                Image.fromarray(rgb).save(png)
        except Exception:
            pass
        return {"in_game": False, "rounds": max_rounds, "png": png,
                "best": (probe[:3] if probe else [])}

    def trajectory_test(self, frames=300):
        """THE definitive anti-scripted-content test, zero tokens.

        Restore the SAME savestate and play three different input
        scripts. A scripted attract demo overrides the pad -> all three
        futures are byte-identical. A real mission diverges: running
        right + firing changes position/kills/camera -> different RAM.
        Returns (diverged, detail)."""
        from .core.memory import digest
        self.save_state("_traj")
        self.core.run(frames, {"RIGHT", "Y"})
        d1 = digest(self.mem.snapshot())
        self.load_state("_traj")
        self.core.run(frames, {"LEFT"})
        d2 = digest(self.mem.snapshot())
        self.load_state("_traj")
        self.core.run(frames, set())
        d3 = digest(self.mem.snapshot())
        self._advance()
        diverged = len({d1, d2, d3}) > 1
        return diverged, {"d_run": d1, "d_left": d2, "d_idle": d3,
                          "frames": frames}

    def control_proof(self, reps=3):
        """DEFINITIVE 'we control the game' test.

        Method 1 (trajectory divergence): same savestate, 3 input
        scripts -> scripted demos stay byte-identical, real play
        diverges. Game-agnostic, no addresses needed.
        Method 2 (GameShark knowledge): the published rapid-fire joker
        D00D4948 8000 implies a pad mirror at 0x0D4948 (bit15=SQUARE)
        — verified empirically when it responds; best-effort only
        (this revision updates it mainly during missions).
        Method 3 (fallback): discover an input-echo word live and test
        the same rhythm on the libretro bit mask."""
        ok, traj = self.trajectory_test()
        if ok:
            return True, {"method": "trajectory", **traj}
        spec = (self.profile.get("gsmap") or {}).get("pad_mirror")
        if spec and spec.get("addr"):
            A = spec["addr"]
            ok = 0
            last = None
            for _ in range(reps):
                self.core.run(20, {"Y"})
                v1 = self.mem.u16(A)
                self.core.run(20, set())
                v2 = self.mem.u16(A)
                self._advance()
                last = [v1, v2]
                if ((v1 >> 15) & 1) and not ((v2 >> 15) & 1):
                    ok += 1
            if ok >= reps:
                self.profile.setdefault("discovered", {}).setdefault(
                    "controller_echo", {"addr": A, "dtype": "u16",
                                        "mask": "0x8000 (PSX SQUARE bit)",
                                        "hits": reps})
                return True, {"addr": A, "ok": ok, "reps": reps,
                              "method": "gs_pad_mirror", "last": last}
        cands = []
        seen = set()
        prev = (self.profile.get("discovered") or {}).get("controller_echo")
        if prev and prev.get("addr"):
            cands.append(prev["addr"])
            seen.add(prev["addr"])
        for _scan in range(2):
            echo = self.disc.input_echo("RIGHT+Y", window=40, reps=2)
            for e in echo:
                if (e.get("hits", 0) >= 2 and e.get("addr", 0) < 0x1FC000
                        and e["addr"] not in seen):
                    cands.append(e["addr"])
                    seen.add(e["addr"])
        last = None
        for A in cands[:3]:
            ok = 0
            for _ in range(reps):
                self.core.run(30, {"RIGHT", "Y"})
                v1 = self.mem.u16(A)
                self.core.run(30, set())
                v2 = self.mem.u16(A)
                self._advance()
                last = [v1, v2]
                if (v1 & 0x80) and not (v2 & 0x80):
                    ok += 1
            if ok >= reps:
                self.profile.setdefault("discovered", {}).setdefault(
                    "controller_echo", {"addr": A, "dtype": "u16",
                                        "mask": "0x82", "hits": reps})
                return True, {"addr": A, "ok": ok, "reps": reps,
                              "last": last}
        return False, {"addr": (cands[0] if cands else None), "ok": 0,
                       "reps": reps, "last": last}

    def enter_gameplay3(self, max_steps=240):
        """Fully ADAPTIVE boot navigation (boot timing varies +-1000f with
        CD seeks, so fixed timelines are gambling). Every ~60f: classify
        the screen against labeled 64x48 references and act:
          loading -> wait | title/demo -> START | menu -> B (select)
          dialog  -> rotate confirm candidates [circle, START, UP+circle]
        The dialog/menu tie is broken by the OK?-box brightness. After
        dialog -> loading the mission is 'confirmed'; once RAM churns
        hard, control is PROVEN with a 3-rep input-word toggle test
        (attract demos cannot mirror our hold/release rhythm 3/3)."""
        from .agent.nav import ThumbNav, load_refs, to_thumb
        from PIL import Image as _PILImage
        refs_dir = os.path.join(DEFAULT_PROFILES, "nav_refs",
                                (self.plugin.ID if self.plugin else "generic"))
        nav = ThumbNav(load_refs(refs_dir))
        dbg = os.environ.get("PS1PLAY_NAV_DEBUG")
        # ---- THE SELF-CORRECTING BOOT LOOP --------------------------
        # Proven mechanics (Task-2/3 + this session's bisection):
        #  * START taps every 300f during boot open menu/dialog; the
        #    dialog's default cursor is YES, so a START tap confirms it
        #  * after YES the coin-up attract shows "PRESS 1P OR 2P START"
        #    -> two STARTs (coin, then 1P launch) start the mission
        #  * a REAL mission has NO white PRESS-START text in the bottom
        #    band (demo scenes always do) + RAM churn > 15000
        import numpy as _np

        def _frame_stats():
            rgb = self.core.frame_rgb()
            if rgb is None:
                return None
            a = _np.asarray(_PILImage.fromarray(rgb).convert("RGB"),
                            dtype=_np.int32)
            g = _np.asarray(_PILImage.fromarray(rgb).convert("L"),
                            dtype=_np.float32)
            band = a[222:240, 60:260]
            white = float(((band[:, :, 0] > 190) &
                           (band[:, :, 1] > 190) &
                           (band[:, :, 2] > 190)).mean())
            dark = float((a.max(axis=2) < 60).mean())
            return {"white": white, "dark": dark, "rgb": rgb,
                    "thumb": to_thumb(rgb)}

        def _looks_dialog(rgb):
            st, d = nav.classify(to_thumb(rgb))
            return st == "dialog" and d <= 15

        for attempt in range(3):
            self.core.reset()
            self.core.run(1000, set())
            self._advance()
            # THE PROVEN TASK-2 TIMELINE (reproduced 3x today): START
            # taps 1000..5200 drive title -> menu -> selects; the extra
            # 5150 tap confirms the OK?/YES box; holding RIGHT from
            # ~5650 rides soldier-select (auto-pick) -> radio -> briefing
            # -> MISSION 1 live by ~9000 (HUD proven at frame_08999).
            for _t in range(1000, 5300, 300):
                self.core.run(15, {"START"})
                self.core.run(285, set())
                self._advance()
            self.core.run(15, {"START"})       # the 5150 OK?/YES confirm
            self.core.run(435, set())
            self._nav_menu_seen = True         # menu phase handled; no
            self.core.run(3350, {"RIGHT"})     # START punches from here
            self._advance()
            if dbg:
                os.makedirs("/tmp/nav5dbg", exist_ok=True)
                _seq = [0]

                def _snap(tag):
                    _seq[0] += 1
                    try:
                        from PIL import Image as _I2
                        rgb = self.core.frame_rgb()
                        if rgb is not None:
                            _I2.fromarray(rgb).resize((320, 240)).save(
                                f"/tmp/nav5dbg/{_seq[0]:04d}_{tag}.png")
                    except Exception:
                        pass
            else:
                def _snap(tag):
                    pass
            # watch and self-correct for ~11000f.
            # LESSONS (this session's bisection):
            #  * the PRESS-START text blinks ~30f on / 30f off -> sparse
            #    sampling aliased with the OFF phase and mistook attract
            #    demos for missions -> sample the band every ~30f and
            #    judge by the rolling MAX over 240f
            #  * the published GameShark pad-mirror word (0x0D4948) is
            #    NOT updated on menus in this revision -> the mirror proof
            #    is best-effort; the PRIMARY gate is behavioral: the world
            #    must be INPUT-RESPONSIVE (churn while holding RIGHT+Y
            #    far exceeds idle churn; scripted demos churn at ~1:1)
            #  * menus (colorful, no white text, unresponsive) are busted
            #    with B (select) + circle (confirm YES) like a human
            from collections import deque
            recent = deque(maxlen=6)     # last-6 responsiveness votes
            menu_stall = 0
            white_hist = []
            quiet_until = self.t + 6500  # mission-start window: no punches
            t_watch_end = self.t + 16000
            while self.t < t_watch_end:
                fs = _frame_stats()
                if fs is None:
                    self.core.run_frame()
                    continue
                st, d = nav.classify(fs["thumb"])
                white_hist.append(fs["white"])
                if len(white_hist) > 8:
                    white_hist.pop(0)
                rolling_white = max(white_hist)
                if dbg:
                    print(f"[nav5] a{attempt} t={self.t} white={fs['white']:.3f} "
                          f"roll={rolling_white:.3f} dark={fs['dark']:.2f} "
                          f"{st} d={d:.1f}", file=sys.stderr)
                if _looks_dialog(fs["rgb"]):
                    self._nav_menu_seen = True
                    _snap("dialogB")
                    # PROVEN (flow_probe8/9): the OK?/YES box confirms on
                    # B (cross). A/START/UP do nothing on this dialog.
                    self.core.run(15, {"B"})
                    self.core.run(150, set())
                    self._advance()
                    continue
                if st == "menu" and d <= 15:
                    # the mission-select menu (d=0.0 = pixel-perfect):
                    # cross selects the highlighted ARCADE MISSION
                    self._nav_menu_seen = True
                    _snap("menuB")
                    self.core.run(15, {"B"})
                    self.core.run(75, set())
                    self._advance()
                    continue
                if 0.004 < rolling_white <= 0.35:
                    # blinking white text (title PRESS-START / coin-up):
                    # insert coin, launch 1P
                    white_hist.clear()
                    menu_stall = 0
                    _snap("coinx2")
                    self.core.run(15, {"START"})
                    self.core.run(45, set())
                    self.core.run(15, {"START"})
                    self.core.run(200, set())
                    self._advance()
                    continue
                if fs["dark"] > 0.93:
                    self.core.run(30, set())       # NOW LOADING/black: wait
                    self._advance()
                    continue
                # ANY visible screen — play like an impatient human:
                # rotate START (coin/start) / B (select) / A (confirm)
                # across iterations so every screen in the attract cycle
                # eventually gets the punch it needs, PLAY the plugin
                # policy in between, and vote on input-responsiveness.
                # Scripted attract content ignores the pad (ratio ~1);
                # a real mission churns far harder while we act.
                ai = self._changed_count(60, set())
                self._advance()
                if any(recent) or self.t < quiet_until:
                    # inside the mission (probably) or still settling:
                    # NO menu punches — START would open the PAUSE menu
                    pass
                else:
                    self._nav_punch = getattr(self, "_nav_punch", 0) + 1
                    seen = getattr(self, "_nav_menu_seen", False)
                    if not seen:
                        k = self._nav_punch % 4
                        if k == 1 or k == 3:
                            _snap("punchSTART")
                            self.core.run(15, {"START"})  # coin / 1P
                        elif k == 0:
                            _snap("punchB")
                            self.core.run(15, {"B"})      # menu select
                        else:
                            _snap("punchA")
                            self.core.run(15, {"A"})      # confirm / skip
                    else:
                        # menus already navigated: NEVER punch START here
                        # (it PAUSES the mission and the pause menu leads
                        # to QUIT!). B/A are safe in-mission: jump/grenade.
                        k = self._nav_punch % 2
                        if k == 0:
                            _snap("punchB")
                            self.core.run(15, {"B"})
                        else:
                            _snap("punchA")
                            self.core.run(15, {"A"})
                self.core.run(75, set())
                s0 = self.mem.snapshot()
                obs = self.observer.observe(self.t)
                feat = self.plugin.features(self.mem, obs)
                ctx = {"t": self.t, "chunk": 60, "stall": 0,
                       "feat": feat, "obs": obs}
                done = 0
                for s_ in (self.plugin.policy(ctx) or
                           [{"frames": 60, "btns": {"RIGHT", "Y"}}]):
                    kk = min(s_["frames"], 60 - done)
                    if kk > 0:
                        self.core.run(kk, s_["btns"])
                        done += kk
                if done < 60:
                    self.core.run(60 - done)
                ar = int(np.count_nonzero(s0 != self.mem.snapshot()))
                self._advance()
                # vote ONLY on a VISIBLE game screen measured AFTER the
                # play window: mission night scenes run dark~0.5-0.7, the
                # NOW LOADING screens ~0.85+ -> bound at 0.80.
                fs2 = _frame_stats()
                d2 = fs2["dark"] if fs2 else 1.0
                responsive = (8000 < ar < 200000 and 0.08 < d2 < 0.80
                              and ar > 1.25 * max(ai, 1))
                _snap("vote1" if responsive else "vote0")
                recent.append(responsive)
                it_n = getattr(self, "_nav_it", 0) + 1
                self._nav_it = it_n
                if (sum(recent) >= 4 or
                        (getattr(self, "_nav_menu_seen", False)
                         and it_n % 6 == 0)):
                    proven, proof = self.control_proof()
                    if dbg:
                        print(f"[nav5] control_proof: {proof}",
                              file=sys.stderr)
                    if proven:                     # hard gate: only accept
                        self.profile.setdefault(   # divergent futures
                            "history", []).append(
                            {"op": "enter_gameplay3",
                             "attempt": attempt,
                             "detector": "boot-taps+overlay+trajectory",
                             "proof": proof})
                        return {"in_game": True,
                                "attempt": attempt,
                                "detector": "boot-taps+overlay",
                                "proof": proof}
                    recent.clear()                 # demand fresh evidence
        png = "/tmp/enter_gameplay3_fail.png"
        try:
            rgb = self.core.frame_rgb()
            if rgb is not None:
                _PILImage.fromarray(rgb).save(png)
        except Exception:
            pass
        return {"in_game": False, "detector": "boot-taps+overlay",
                "png": png}

    def run_steps(self, steps):
        t0 = time.time()
        for st in steps:
            op = st.get("op")
            if op == "wait":
                self.core.run(st["frames"])
            elif op == "tap":
                f = st.get("frames", 15)
                self.core.run(f, st["btns"])
                ev = st.get("every")
                if ev:                      # `every` = full period
                    self.core.run(max(0, ev - f))
            elif op == "hold":
                self.core.run(st["frames"], st["btns"])
        self._advance()
        return {"steps": len(steps), "wall_s": round(time.time() - t0, 1),
                "t": self.t}

    def wait(self, frames, buttons=None):
        self.core.run(frames, buttons)
        self._advance()
        return self.observe()

    # ---------------- observation ----------------
    def observe(self):
        row = self.observer.observe(self.t)
        feat = self.plugin.features(self.mem, row)
        row["feat"] = feat
        row["state"] = self.plugin.infer_state(row, feat)
        return row

    # ---------------- discovery (1st-run learning) ----------------
    def discover(self, buttons="RIGHT", window=45, reps=2, echo=True):
        """Play A/B windows; find & VERIFY candidates, remember in profile.

        Verification = bidirectional probe: a true position/scroll counter
        grows with RIGHT and shrinks with LEFT at the SAME address.
        """
        out = {}
        cands = self.disc.correlate(buttons, window=window, reps=reps)
        out["correlate_" + buttons] = cands[:6]
        winner = None
        opp = {"RIGHT": "LEFT", "LEFT": "RIGHT"}.get(buttons)
        used = window * reps * 2
        if opp:
            cands_o = self.disc.correlate(opp, window=window, reps=reps)
            out["correlate_" + opp] = cands_o[:6]
            used += window * reps * 2
            index = {(c["addr"], c["dtype"]): c for c in cands}
            for c in cands_o:
                m = index.get((c["addr"], c["dtype"]))
                if m and m["dir"] != c["dir"]:
                    s = min(m["score"], c["score"])
                    if winner is None or s > winner[0]:
                        winner = (s, m)
        role = ("player_x" if buttons in ("RIGHT", "LEFT")
                else "player_y" if buttons in ("UP", "DOWN") else "misc")
        if winner:
            s, m = winner
            cand = {"addr": m["addr"], "dtype": m["dtype"], "score": s,
                    "dir": m["dir"], "verified": "bidirectional"}
        elif cands:
            cand = {"addr": cands[0]["addr"], "dtype": cands[0]["dtype"],
                    "score": cands[0]["score"], "dir": cands[0]["dir"],
                    "verified": False}
        else:
            cand = None
        if cand:
            self._remember(role, cand)
        if echo:
            e = self.disc.input_echo(buttons, reps=1)
            out["input_echo"] = e
            used += window * 2
            if e:
                self.profile.setdefault(
                    "discovered", {}).setdefault("controller_echo", e[0])
        self.profile.setdefault("history", []).append(
            {"op": "discover", "buttons": buttons, "frames_used": used,
             "role": role, "addr": cand["addr"] if cand else None})
        # ---- series verification (savestate restore => noise-free) ----
        if cand and role == "player_x":
            try:
                self.save_state("verify_base")
                ver = self.verify_player_axis(buttons)
                out["verified_series"] = ver[:3]
                if ver:
                    v = ver[0]
                    better = (not self.profile["discovered"].get(role) or
                              v["quality"] > self.profile["discovered"]
                              [role].get("quality", 0))
                    if better:
                        self._remember(role, {
                            "addr": v["addr"], "dtype": v["dtype"],
                            "score": int(v["quality"]),
                            "dir": "+" if v["m_act"] > 0 else "-",
                            "verified": "series",
                            "quality": v["quality"],
                            "mono_frac": v["mono_frac"],
                            "m_act": v["m_act"], "m_idle": v["m_idle"]})
                        out["winner"] = v["addr"]
            except Exception as e:
                out["verify_error"] = str(e)
        return out

    def verify_player_axis(self, buttons="RIGHT", topk=12, frames=60):
        """Restore the same savestate per candidate and sample value series:
        a real position counter moves steadily when held, flat when idle."""
        cands = self.disc.correlate(buttons, window=45, reps=2)[:topk]
        results = []
        for c in cands:
            r = self.disc.verify_series(self.states, "verify_base",
                                        c["addr"], c["dtype"],
                                        buttons, frames=frames)
            if r and r["quality"] > 0:
                results.append(r)
        results.sort(key=lambda r: -r["quality"])
        return results

    def discover_progress(self, frames=180, buttons=None):
        mono = self.disc.monotonic(frames=frames, buttons=buttons)
        self.profile.setdefault("history", []).append(
            {"op": "monotonic", "frames_used": frames})
        u32s = [m for m in mono if m["dtype"] == "u32"]
        if u32s:
            self._remember("score", {"addr": u32s[0]["addr"],
                                     "dtype": u32s[0]["dtype"],
                                     "score": u32s[0]["gain"],
                                     "dir": "+"})
        return {"monotonic": mono}

    def diff_now(self, frames=45, buttons=None):
        return self.disc.diff(frames, buttons)

    # ---------------- gameplay ----------------
    def play(self, frames, chunk=60, checkpoint_every=1800):
        jr = Journal(self.journal_path)
        try:
            loop = AgentLoop(self.core, self.mem, self.plugin,
                             self.observer, self.states, jr)
            res = loop.run(frames, chunk=chunk,
                           checkpoint_every=checkpoint_every,
                           t_start=self.t)
            self.t = res["t_end"]
            return res
        finally:
            jr.close()

    # ---------------- continue-anywhere ----------------
    def save_state(self, name):
        return self.states.save(self.core, name,
                                meta={"t": self.t})

    def load_state(self, name):
        res = self.states.load(self.core, name)
        self.t += 0  # frame_count resets are core-internal; t is session bookkeeping
        self.observer.mark()
        return res

    def resume(self):
        name = self.states.latest()
        if not name:
            return {"resumed": False}
        self.states.load(self.core, name)
        self.observer.mark()
        return {"resumed": True, "state": name}

    # ---------------- reporting (token-minimal) ----------------
    def report(self):
        return {
            "game": os.path.basename(self.game),
            "serial": self.profile.get("serial"),
            "plugin": self.plugin.ID if self.plugin else None,
            "frames_played": self.t,
            "states": [s["name"] for s in self.states.list()],
            "discovered": self.profile.get("discovered"),
            "profile_file": self.profile_path,
            "journal": self.journal_path,
        }
