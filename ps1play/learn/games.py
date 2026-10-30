"""games.py — environment wrappers for the two learning games.

ONE boot per process; episodes start from RESTORED anchor savestates
(restore is not a boot). The assisted observation readers live here and
are used ONLY in assisted modes / for evaluation labels — the deployed
brain receives frames only (see visual_only.py + brain.py).

Scenario-opponent (pong): hello_pong has NO AI (source-verified) and the
static right paddle makes single-paddle play degenerate (the serve is
ALWAYS rightward — the left paddle would never touch the ball). The
foundation therefore drives pad2 (port 1) with a scripted opponent whose
parameters (reaction delay, aim error, seed) are SCENARIO variables:
train on one parameter family, evaluate on held-out families -> the
student faces genuinely different ball trajectories (the return
vel_y = f(hit offset), source line 190). The student never sends pad2
inputs. This is an environment component, disclosed everywhere.
"""
import os
import shutil
import time

import numpy as np

from ps1play import labconfig
from ps1play.api import PS1Play

REPO = "/home/z/my-project/ps1ai"
EMU = "/home/z/my-project/emu/games_homebrew"
OPENBIOS_SRC = os.path.join(REPO, "third_party", "openbios", "openbios.bin")
SCRATCH_LEARN = os.path.join(REPO, "scratch", "r53learn")

# pong geometry constants (source-verified)
PONG_BALL_SPEED = 2
PONG_PADDLE_SPEED = 4
PONG_WIN = 5

# flappy constants (r15-measured / source)
FLAP_PIPE_SPEED = 1.40625      # px/frame leftward
FLAP_GRAVITY = 0.125           # px/f^2 (screen)
FLAP_FLAP_IMPULSE = 8.0        # px/f up per flap


def _small_rgb(fr, out=(60, 80, 3)):
    """Area-average RGB downsample 320x240 -> (60,80,3) uint8.
    THE frame format sent to the brain (and stored in datasets)."""
    oh, ow = out[0], out[1]
    # fast path: the default 320x240 -> 60x80 grid splits EXACTLY into
    # 4x4 blocks (linspace boundaries are exact multiples); the reshape
    # mean is the same 16-pixel average — tests/_smallrgb check equality
    # against the loop reference on random frames.
    if (fr.shape[0] == 240 and fr.shape[1] == 320
            and (oh, ow) == (60, 80)):
        return np.clip(
            fr.reshape(60, 4, 80, 4, 3).mean(axis=(1, 3)),
            0, 255).astype(np.uint8)
    hs = np.linspace(0, fr.shape[0], oh + 1).astype(int)
    ws = np.linspace(0, fr.shape[1], ow + 1).astype(int)
    outv = np.empty((oh, ow, 3), dtype=np.float32)
    for i in range(oh):
        for j in range(ow):
            outv[i, j] = fr[hs[i]:hs[i + 1], ws[j]:ws[j + 1]] \
                .reshape(-1, 3).mean(axis=0)
    return np.clip(outv, 0, 255).astype(np.uint8)


def _small_rgb_ref(fr, out=(60, 80, 3)):
    """The ORIGINAL loop reference (kept for the equality test)."""
    oh, ow = out[0], out[1]
    hs = np.linspace(0, fr.shape[0], oh + 1).astype(int)
    ws = np.linspace(0, fr.shape[1], ow + 1).astype(int)
    outv = np.empty((oh, ow, 3), dtype=np.float32)
    for i in range(oh):
        for j in range(ow):
            outv[i, j] = fr[hs[i]:hs[i + 1], ws[j]:ws[j + 1]] \
                .reshape(-1, 3).mean(axis=0)
    return np.clip(outv, 0, 255).astype(np.uint8)


class BaseEnv:
    game = "?"

    def __init__(self, workspace, cue, fw_mode="openbios"):
        self.workspace = workspace
        os.makedirs(os.path.join(workspace, "system"), exist_ok=True)
        shutil.copyfile(OPENBIOS_SRC,
                        os.path.join(workspace, "system", "openbios.bin"))
        fw = labconfig.resolve_firmware(fw_mode, workspace=workspace)
        self.p = PS1Play(cue, workspace=workspace,
                         var_overrides=fw["override_vars"])
        boot_info = self.p.boot()
        fw_ev = labconfig.firmware_log_evidence(
            getattr(self.p.core, "log_history", []))
        ok, detail = labconfig.check_firmware_trust(fw, fw_ev)
        if not ok:
            raise SystemExit(f"firmware trust failed: {detail}")
        self.boot_info = boot_info
        self.fw_mode = fw["mode"]
        self._anchors = {}

    # ---- shared surface ----
    def frame(self):
        return self.p.core.frame_rgb()

    def frame_small(self):
        return _small_rgb(self.frame())

    def run(self, frames, buttons=None, buttons_p1=None):
        self.p.core.run(frames, buttons, buttons_p1)

    def save_anchor(self, name):
        blob = self.p.core.serialize()
        path = os.path.join(SCRATCH_LEARN, f"{name}.bin")
        os.makedirs(SCRATCH_LEARN, exist_ok=True)
        with open(path, "wb") as f:
            f.write(blob)
        self._anchors[name] = path
        return path

    def load_anchor(self, name):
        path = (self._anchors.get(name)
                or os.path.join(SCRATCH_LEARN, f"{name}.bin"))
        with open(path, "rb") as f:
            self.p.core.unserialize(f.read())
        self.run(1, set())          # force a render before frame reads
        return path

    def close(self):
        try:
            self.p.core.shutdown()
        except Exception:
            pass


# ---------------------------------------------------------------- pong
class PongEnv(BaseEnv):
    """hello_pong. Anchor `pong_anchor` = fresh game, first rally,
    scores 0-0 (verified in Stage A against the score words)."""

    game = "pong"
    LIC_CUE = os.path.join(EMU, "patched", "hello_pong_lic.cue")

    def __init__(self, workspace=os.path.join(EMU, "ws_learn_pong")):
        super().__init__(workspace, self.LIC_CUE)

    @staticmethod
    def playing(fr):
        """Dark field + two white paddle columns + no big bright text."""
        g = fr.mean(axis=2)
        if g.mean() > 60:
            return False
        white = g > 150
        lcol = white[:, :26].any(axis=1).sum()
        rcol = white[:, 296:].any(axis=1).sum()
        return lcol > 20 and rcol > 20

    def settle(self, max_frames=3000):
        """Boot -> PLAYING (auto-start). Saves `pong_anchor`."""
        self.run(300, set())
        for f in range(0, max_frames, 30):
            fr = self.frame()
            if self.playing(fr):
                self.run(30, set())
                self.save_anchor("pong_anchor")
                return f + 30
            self.run(30, set())
        raise RuntimeError("pong never reached PLAYING")

    # ---- assisted readers (assisted modes / evaluation labels ONLY) ----
    def read_assisted(self, ram_anchors):
        """ram_anchors: dict with ball_x/y/paddle_left/score addresses
        (Stage A). Returns teacher-side labels with provenance."""
        ram = self.p.core.ram
        out = {}
        for name, (addr, fmt) in ram_anchors.items():
            if fmt == "i32":
                v = int(np.frombuffer(ram[addr:addr + 4].tobytes(),
                                      dtype="<i4")[0])
            elif fmt == "u16":
                v = int(np.frombuffer(ram[addr:addr + 2].tobytes(),
                                      dtype="<u2")[0])
            else:
                v = int(ram[addr])
            out[name] = v
        return out

    @staticmethod
    def scenario_opponent_step(est_ball_y, paddle_row, params):
        """Port-1 opponent decision (used by the runner): track the ball
        with delay + aim error. Pure function of disclosed inputs."""
        target = est_ball_y + float(params.get("aim_bias", 0.0))
        dead = params.get("deadband", 8.0)
        if target < paddle_row - dead:
            return {"UP"}
        if target > paddle_row + dead:
            return {"DOWN"}
        return set()


# -------------------------------------------------------------- flappy
class FlappyEnv(BaseEnv):
    """FlappyBirdPSX. Anchor `flappy_ready` = the GET READY screen
    BEFORE the seed press. Scenario = idle_frames k before the X press:
    the press seeds the RNG (r15) -> different pipe sequences."""

    game = "flappy"
    CUE = os.path.join(EMU, "flappybird.cue")

    def __init__(self, workspace=os.path.join(EMU, "ws_learn_flappy")):
        super().__init__(workspace, self.CUE)

    @staticmethod
    def game_over(fr):
        """The GAME OVER panel = a large BEIGE rectangle (r>185, g>175,
        b<200, r>b+20) in the band rows 60..150 / cols 90..230. The
        GET READY screen's teal sky (b high) and white clouds (b>200)
        never match — measured after a brightness-only detector
        false-positived on the ready screen."""
        band = fr[60:150, 90:230]
        r = band[:, :, 0].astype(int)
        g = band[:, :, 1].astype(int)
        b = band[:, :, 2].astype(int)
        beige = (r > 185) & (g > 175) & (b < 200) & (r > b + 20)
        return float(beige.mean()) > 0.35

    def reach_ready(self, max_frames=2400):
        """Boot -> the GET READY screen; save `flappy_ready` BEFORE any
        button press (the press seeds the RNG -> the anchor must be
        pre-seed so each episode's press timing k creates a fresh pipe
        sequence)."""
        self.run(900, set())
        self.save_anchor("flappy_ready")
        return True

    def start_episode(self, scenario_k=0):
        """Restore ready anchor -> k idle frames -> the r15 start
        sequence VERBATIM (B 3f -> 4f idle -> B 2f = the first real
        flap pulse -> 4f idle). Returns frames consumed."""
        self.load_anchor("flappy_ready")
        k = int(scenario_k)
        if k:
            self.run(k, set())
        self.run(3, {"B"})
        self.run(4, set())
        self.run(2, {"B"})
        self.run(4, set())
        return k + 13

    def read_assisted(self, ram_anchors):
        ram = self.p.core.ram
        out = {}
        for name, (addr, fmt) in ram_anchors.items():
            if fmt == "i32":
                v = int(np.frombuffer(ram[addr:addr + 4].tobytes(),
                                      dtype="<i4")[0])
            elif fmt == "u16":
                v = int(np.frombuffer(ram[addr:addr + 2].tobytes(),
                                      dtype="<u2")[0])
            else:
                v = int(ram[addr])
            out[name] = v
        return out
