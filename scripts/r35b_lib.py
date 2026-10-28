#!/usr/bin/env python3
"""r35b_lib.py — R35-B shared helpers for the BuzzyBee RAM-guided bot.

Anchors are KUSEG VAs; every RAM read subtracts 0x80000000 first.

Entity map (source-derived by the dead prior r35b attempt from
github.com/NDR008/BuzzyBee main.c + BuzzyBee.map; live-verified in
r35b boot 1 — see checks in boot_log_r35b_b1.json):

  AnimatedObject, 0x24 bytes (fixed point: px = v/1024, C trunc):
    +0x00 frame_n  +0x04 index  +0x08 total_frames
    +0x0C y_pos    +0x10 x_pos  +0x14 x_vel  +0x18 y_vel
    +0x1C anim_rate +0x20 Image** img_list
  mainPlayer 0x8005EDC0  bee: x fixed 15px, sprite 22x18, x1=15 x2=37
  enemies    0x8005EB7C  1 wasp 56x48, xv=-1536, y bounces 2..142px
  flowers    0x8005EBA0  3 x 0x24, 16x29, x=rock.x+21, y=rock.y-29
  rocks      0x8005F55C  3 x 0x24, 42x40, xv=-1024
  mainHealth 0x8005EF48  init/cap 5999, drain -3/f, enemy -1500,
                         flower +1000, <0 -> clamp 0, gs 5
  gameState  0x80058830  0=title 1=gameplay 5=gameover
  bestScore  0x80058838  score 0x8005883C
  hitF 0x80058840  hitE 0x80058844
  input_pad 0x8005881C  input_trig 0x80058820  input_held 0x80058824

Physics (main.c): y_vel += 256/f (gravity); CROSS rising edge:
  y_vel -= 3072. KNOWN BUG: y_vel < -6144 -> y_vel = +6144 (slam down)
  -> never tap when y_vel <= -3000 pre-tap. Player y clamp
  [18*1024, 172*1024] px [18,172].
  checkHit enemy pad=5: contact iff ex in [-36,32] AND by in [wy-13,wy+43].
"""
import json
import os
import shutil
import sys
import time

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)

BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BUZZ = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_ntsc_lic.cue"

# ---- OUT dir: real repo scratch, else PolarFS mirror (disk-full fallback)
MIRROR_NOTE = None
OUT = os.path.join(REPO, "scratch", "r35b")
try:
    os.makedirs(os.path.join(OUT, "shots"), exist_ok=True)
    _p = os.path.join(OUT, ".probe")
    open(_p, "w").write("ok")
    os.remove(_p)
except OSError as e:
    OUT = "/tmp/my-project/ps1ai/scratch/r35b"
    MIRROR_NOTE = (f"real scratch/r35b unwritable ({e.__class__.__name__}) "
                   f"— evidence written to PolarFS mirror {OUT}; sync-back "
                   f"attempted at end")
    os.makedirs(os.path.join(OUT, "shots"), exist_ok=True)
SHOTS = os.path.join(OUT, "shots")
BOOTS = os.path.join(OUT, "boots_used.json")
CKPT_PATH = os.path.join(OUT, "state_r35b_gs1.bin")

FACTOR = 1024
KUSEG = 0x80000000
GS, BEST, SCORE, HITF, HITE = (0x80058830, 0x80058838, 0x8005883C,
                               0x80058840, 0x80058844)
INPUT_PAD, INPUT_TRIG, INPUT_HELD = 0x8005881C, 0x80058820, 0x80058824
PLAYER, ENEMY, FLOWERS, ROCKS = 0x8005EDC0, 0x8005EB7C, 0x8005EBA0, 0x8005F55C
HEALTH, TIMER = 0x8005EF48, 0x8005F548
TVSYNC, TTOT = TIMER + 8, TIMER + 0x10
# anim img_list anchors (struct-integrity checks)
IL_PLAYER, IL_ENEMY, IL_FLOWER, IL_ROCK = (0x8005E9AC, 0x8005F408,
                                           0x8005F5C8, 0x8005EE34)

BEE_X1, BEE_X2, BEE_H = 15, 37, 18
Y_MIN, Y_MAX = 18, 172          # player y clamp (px)
ENGAGE_X = 137                  # engage dodge when wasp left edge <= this
PASS_END_X = -41                # wasp fully past bee (x+w < 15 with pad)

T0 = time.time()


def px(v):
    """C integer division by 1024 (truncation toward zero)."""
    return -((-v) // FACTOR) if v < 0 else v // FACTOR


# ---------------------------------------------------------------- ledger
def ledger_load():
    for p in (BOOTS, os.path.join(REPO, "scratch", "r35b", "boots_used.json")):
        if os.path.exists(p):
            return json.load(open(p)), p
    raise FileNotFoundError("r35b boots_used.json missing — create pre-run")


def ledger_use(count_to, script, note=None):
    """PRE-RUN boot consumption. Asserts the expected prior count."""
    led, path = ledger_load()
    assert led["count"] == count_to - 1, \
        f"ledger count {led['count']} != expected {count_to - 1}"
    led["count"] = count_to
    ent = {"boot": count_to, "script": script, "out_dir": OUT,
           "mirror_note": MIRROR_NOTE,
           "t": time.strftime("%FT%TZ", time.gmtime())}
    if note:
        ent["note"] = note
    led["log"].append(ent)
    json.dump(led, open(path, "w"), indent=1)
    return led


# ---------------------------------------------------------------- core
class Bee:
    """Thin wrapper over LibretroCore with BuzzyBee RAM readers."""

    def __init__(self, ws="ws_r35b", core_path=CORE):
        import numpy as np  # noqa: F401  (host needs it)
        from ps1play.core.host import LibretroCore
        wsroot = os.path.join(OUT, ws)
        os.makedirs(os.path.join(wsroot, "system"), exist_ok=True)
        os.makedirs(os.path.join(wsroot, "saves"), exist_ok=True)
        dst = os.path.join(wsroot, "system", "openbios.bin")
        if not os.path.exists(dst):
            shutil.copyfile(BIOS, dst)
        self.core = LibretroCore(core_path, os.path.join(wsroot, "system"),
                                 os.path.join(wsroot, "saves"),
                                 var_overrides={
                                     b"beetle_psx_renderer": b"software",
                                     b"beetle_psx_frame_duping": b"disabled"})

    # --- passthrough
    def load_game(self, path=BUZZ):
        return self.core.load_game(path)

    def run(self, n, buttons=set()):
        self.core.run(n, buttons)

    def run_frame(self):
        self.core.run_frame()

    def set_buttons(self, spec):
        self.core.set_buttons(spec)

    @property
    def frames_run(self):
        return self.core.frames_run

    @property
    def ram(self):
        return self.core.ram

    def frame_rgb(self):
        return self.core.frame_rgb()

    def serialize(self):
        return self.core.serialize()

    def unserialize(self, blob):
        self.core.unserialize(blob)

    # --- RAM readers (KUSEG subtraction lives HERE)
    def _off(self, va):
        return va - KUSEG

    def i32(self, va):
        o = self._off(va)
        return int.from_bytes(bytes(self.ram[o:o + 4]), "little", signed=True)

    def u32(self, va):
        o = self._off(va)
        return int.from_bytes(bytes(self.ram[o:o + 4]), "little")

    def u16(self, va):
        o = self._off(va)
        return int.from_bytes(bytes(self.ram[o:o + 2]), "little")

    def u8(self, va):
        return int(self.ram[self._off(va)])

    # --- struct readers
    def obj(self, base, full=False):
        o = {"y": self.i32(base + 0x0C), "x": self.i32(base + 0x10),
             "xv": self.i32(base + 0x14), "yv": self.i32(base + 0x18)}
        if full:
            o = {"fn": self.i32(base), "idx": self.i32(base + 4),
                 "tf": self.i32(base + 8), **o,
                 "rate": self.i32(base + 0x1C), "il": self.u32(base + 0x20)}
        return o

    def state(self, full=False):
        s = {"gs": self.i32(GS), "best": self.i32(BEST),
             "score": self.i32(SCORE), "hp": self.i32(HEALTH),
             "hitE": self.i32(HITE), "hitF": self.i32(HITF),
             "p": self.obj(PLAYER, full), "e": self.obj(ENEMY, full),
             "trig": self.u32(INPUT_TRIG), "held": self.u32(INPUT_HELD)}
        for i in range(3):
            s[f"f{i}"] = self.obj(FLOWERS + 0x24 * i, full)
            s[f"r{i}"] = self.obj(ROCKS + 0x24 * i, full)
        return s

    def obs(self):
        """Compact px-space observation for the policy."""
        p = self.obj(PLAYER)
        e = self.obj(ENEMY)
        return {"by": px(p["y"]), "bvy": p["yv"],
                "e": [px(e["x"]), px(e["y"]), px(e["yv"])],
                "fl": [[px(self.i32(FLOWERS + 0x24 * i + 0x10)),
                        px(self.i32(FLOWERS + 0x24 * i + 0x0C))]
                       for i in range(3)]}

    # --- io helpers
    def snap(self, tag, R=None):
        arr = self.frame_rgb()
        if arr is not None:
            from PIL import Image
            p = os.path.join(SHOTS, f"{tag}_f{self.frames_run:05d}.png")
            Image.fromarray(arr).save(p)
            if R is not None:
                R["shots"].append({"tag": tag, "frame": self.frames_run,
                                   "png": os.path.relpath(p, OUT)})
        return arr


def make_logger(out_dir, name, tag):
    R = {"task": tag, "out_dir": OUT, "mirror_note": MIRROR_NOTE,
         "started": time.strftime("%FT%TZ", time.gmtime()),
         "events": [], "shots": []}

    def dump():
        json.dump(R, open(os.path.join(out_dir, name), "w"),
                  indent=1, default=str)

    def log(ev, **kw):
        rec = {"f": 0, "t": round(time.time() - T0, 1), "event": ev, **kw}
        R["events"].append(rec)
        print(f"[{tag}] {json.dumps(rec, default=str)[:240]}", flush=True)
        dump()

    return R, log, dump


def jl_writer(out_dir, name):
    fh = open(os.path.join(out_dir, name), "w")

    def w(rec):
        fh.write(json.dumps(rec, default=str) + "\n")
    return w, fh


def sync_back():
    """Mirror evidence to the real repo if we fell back to /tmp."""
    real_out = os.path.join(REPO, "scratch", "r35b")
    if os.path.abspath(real_out) == os.path.abspath(OUT):
        return None
    try:
        os.makedirs(real_out, exist_ok=True)
        n = 0
        for root, _d, files in os.walk(OUT):
            rel = os.path.relpath(root, OUT)
            dst = os.path.join(real_out, rel) if rel != "." else real_out
            os.makedirs(dst, exist_ok=True)
            for fn in files:
                try:
                    shutil.copyfile(os.path.join(root, fn),
                                    os.path.join(dst, fn))
                    n += 1
                except OSError:
                    pass
        return f"synced {n} files -> {real_out}"
    except OSError as e:
        return f"sync_back_failed: {e}"


# ---------------------------------------------------------------- policy
def bot_policy(s, sticky, engage=ENGAGE_X, margin=14):
    """BuzzyBee policy. Returns (flap, target_by, mode).

    Priority: dodge wasp > seek flower > hover mid-band.
    s: px-space obs from Bee.obs(): by, bvy, e=[ex,ey,evy], fl=[[fx,fy]x3].
    flap rule always respects the slam-down bug: only tap when bvy > -3000
    (post-tap y_vel = bvy-3072 > -6072 > -6144).
    """
    by, bvy = s["by"], s["bvy"]
    ex, ey = s["e"][0], s["e"][1]
    if PASS_END_X < ex <= engage:
        # contact iff by in [ey-13, ey+43] while ex in [-36,32]; hold a
        # side with `margin` px of extra room, committed for the pass.
        above_lim = ey - 13            # need by < above_lim to be safe
        below_lim = ey + 43            # need by > below_lim to be safe
        tgt_a, tgt_b = above_lim - margin, below_lim + margin
        room_a, room_b = tgt_a - Y_MIN, Y_MAX - tgt_b
        if sticky.get("side") is None:
            sticky["side"] = "above" if room_a >= room_b else "below"
        if sticky["side"] == "above":
            target = tgt_a
            if room_a < 6:             # ceiling blocks: flip below
                target, sticky["side"] = tgt_b, "below"
        else:
            target = tgt_b
            if room_b < 6:             # floor blocks: flip above
                target, sticky["side"] = tgt_a, "above"
        target = max(Y_MIN + 2, min(Y_MAX - 2, target))
        return (by > target + 4 and bvy > -3000), target, "dodge"
    sticky["side"] = None
    best = None
    for fx, fy in s["fl"]:
        if BEE_X2 < fx <= 130 and (best is None or fx < best[0]):
            best = (fx, fy)
    if best:
        # flower 16x29 at (fx,fy): bee center on flower center -> by=fy+5
        target = max(Y_MIN + 2, min(Y_MAX - 2, best[1] + 5))
        return (by > target + 4 and bvy > -3000), target, "flower"
    return (by > 99 and bvy > -3000), 95, "hover"


def predict_wasp_y(ey, evy, t):
    """Simulate wasp y (px) for t frames with bounce off [2,142]."""
    y, v = float(ey), evy
    for _ in range(max(0, int(t))):
        y += v
        if y < 2:
            y, v = 2, abs(v)
        elif y > 142:
            y, v = 142, -abs(v)
    return y


def bot_policy2(s, sticky, engage=150, margin=16, flower_hi=160,
                hover_y=95):
    """Boot-2 policy: predictive dodge + wider flower seek.

    Dodge: when wasp engaged, predict its y at contact-x entry
    (t = (ex-32)/1.5 f, bounce sim), pick the side with more room on the
    PREDICTED band, commit for the pass, flip only if infeasible.
    Flower: nearest flower with BEE_X2 < fx <= flower_hi; bee center on
    flower center. Flap rule always bug-guarded (bvy > -3000).
    """
    by, bvy = s["by"], s["bvy"]
    ex, ey, evy = s["e"][0], s["e"][1], s["e"][2]
    if PASS_END_X < ex <= engage:
        t_c = max(0, int((ex - 32) / 1.5))
        ey_c = predict_wasp_y(ey, evy, t_c)
        tgt_a = ey_c - 13 - margin            # safe-above target
        tgt_b = ey_c + 43 + margin            # safe-below target
        room_a, room_b = tgt_a - Y_MIN, Y_MAX - tgt_b
        if sticky.get("side") is None:
            if room_a >= room_b and room_a > 0:
                sticky["side"] = "above"
            elif room_b > 0:
                sticky["side"] = "below"
            else:
                sticky["side"] = "above" if by < ey_c else "below"
        if sticky["side"] == "above":
            target = tgt_a
            if room_a < 4:
                sticky["side"], target = "below", tgt_b
        else:
            target = tgt_b
            if room_b < 4:
                sticky["side"], target = "above", tgt_a
        target = max(Y_MIN + 2, min(Y_MAX - 2, target))
        return (by > target + 4 and bvy > -3000), target, "dodge"
    sticky["side"] = None
    best = None
    for fx, fy in s["fl"]:
        if BEE_X2 < fx <= flower_hi and (best is None or fx < best[0]):
            best = (fx, fy)
    if best:
        target = max(Y_MIN + 2, min(Y_MAX - 2, best[1] + 5))
        return (by > target + 4 and bvy > -3000), target, "flower"
    return (by > hover_y and bvy > -3000), hover_y, "hover"


def rise_px(bvy):
    """Px climbed by a tap launched at velocity bvy (fixed 1024)."""
    u = (3072 - bvy) / 1024.0
    return 2.0 * u * u if u > 0 else 0.0


def bot_policy3(s, sticky, engage=170, margin=14, flower_hi=170,
                hover_y=95):
    """Boot-3 policy: momentum/arc-aware dodge + fixed flower window.

    Boot-2 forensics: all 7 hits were below-side over-flaps chaining the
    bee up into the contact band (tap rise 10-40px). Fixes:
      - side=ABOVE preferred whenever feasible (climb overshoot is safe);
        below only if above infeasible or bee already deep-low.
      - side=below: NO tap unless the whole tap arc stays clear of the
        band bottom (by - rise_px(bvy) > ey+43+8).
      - emergency: bee inside the band now -> nearest exit, no flap if
        below (fall), flap if above.
      - vy sign flip mid-pass -> re-choose side (band reverses).
      - flower window fixed: fx > 0 (boot-2 used fx > 37, which dropped
        the target during final approach -> pickups logged as hover).
    """
    by, bvy = s["by"], s["bvy"]
    ex, ey, evy = s["e"][0], s["e"][1], s["e"][2]
    if PASS_END_X < ex <= engage:
        t_c = max(0, int((ex - 32) / 1.5))
        ey_c = predict_wasp_y(ey, evy, t_c)
        band_top, band_bot = ey - 13, ey + 43          # current band
        tgt_a = ey_c - 13 - margin
        tgt_b = ey_c + 43 + margin
        room_a, room_b = tgt_a - Y_MIN, Y_MAX - tgt_b
        cur = sticky.get("side")
        inside = (band_top + 2) <= by <= (band_bot - 2)
        flipped = sticky.get("vy") is not None and \
            (sticky["vy"] < 0) != (evy < 0)
        sticky["vy"] = evy
        if inside or cur is None or flipped:
            # (re)choose: above if feasible; below if bee already deep
            # low or above infeasible
            if inside:
                cur = "above" if by < ey + 15 else "below"
            elif room_a >= 10 and by <= tgt_b - 6:
                cur = "above"
            elif room_b >= 10 and by >= tgt_b - 4:
                cur = "below"
            elif room_a >= 10:
                cur = "above"
            elif room_b >= 10:
                cur = "below"
            else:
                cur = "above" if by < ey_c else "below"
        sticky["side"] = cur
        if cur == "above":
            target = max(Y_MIN + 2, min(Y_MAX - 2, tgt_a))
            flap = by > target + 4 and bvy > -3000
        else:
            target = max(Y_MIN + 2, min(Y_MAX - 2, tgt_b))
            # corrective tap only if the WHOLE tap arc stays clear
            flap = (by > target + 12 and bvy > -3000 and
                    by - rise_px(bvy) > band_bot + 8)
        return flap, target, "dodge"
    sticky["side"] = None
    sticky["vy"] = None
    best = None
    for i, (fx, fy) in enumerate(s["fl"]):
        if 0 < fx <= flower_hi and (best is None or fx < best[1]):
            best = (i, fx, fy)
    if best:
        target = max(Y_MIN + 2, min(Y_MAX - 2, best[2] + 5))
        return (by > target + 4 and bvy > -3000), target, "flower"
    return (by > hover_y and bvy > -3000), hover_y, "hover"
