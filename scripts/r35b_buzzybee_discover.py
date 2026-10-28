#!/usr/bin/env python3
"""r35b_buzzybee_discover.py — R35-B boot 1: BuzzyBee entity-map discovery
+ verification + idle-death baseline + savestate checkpoint.

Source ground truth (github.com/NDR008/BuzzyBee @ master, main.c +
BuzzyBee.map, cloned r30t0-style; verified against this exact build's
map): structs and BSS addresses —

  typedef struct AnimatedObject {   // size 0x24
      int frame_n;     // +0x00
      int index;       // +0x04
      int total_frames;// +0x08
      int y_pos;       // +0x0C   (fixed point: pixel = v / 1024)
      int x_pos;       // +0x10
      int x_vel;       // +0x14
      int y_vel;       // +0x18
      int anim_rate;   // +0x1C
      Image *img_list; // +0x20
  } AnimatedObject;

  COMMON (BuzzyBee.map): mainPlayerL 0x8005e9ac, BeeL 0x8005eb2c,
  enemies 0x8005eb7c, flowers 0x8005eba0 (3 x 0x24), Buzzy 0x8005ec0c,
  mainPlayer 0x8005edc0, rocksL 0x8005ee34, Bee 0x8005ef24,
  mainHealth 0x8005ef48, jam 0x8005f0b8, hills 0x8005f354,
  enemiesL 0x8005f408, mainTimer 0x8005f548 {min,sec,vsync,factor,
  totalsec}, rocks 0x8005f55c (3 x 0x24), flowersL 0x8005f5c8,
  pressStart 0x8005fc00, ground 0x8005fc24.
  .sbss: time3 0x80058808, gameState 0x80058830, bestScore 0x80058838,
  score 0x8005883c, hitF 0x80058840, hitE 0x80058844.

  Physics (main.c): factor=1024, GRAVITY=256/f, MAXSPEED=1024,
  MAXFLAP=6144, flap: y_vel -= 3072 on input_trig & PAD_CROSS rising
  edge; KNOWN BUG: y_vel < -6144 -> y_vel = +6144 (slam down) — avoid
  by never tapping when y_vel > -3000 pre-tap.
  Player clamp: y_pos in [CEILING=18*1024, GROUND+30*1024=172*1024];
  player x fixed 15 px (x1=15, x2=37); bee sprite 22x18 px.
  Enemy (1 wasp, 56x48 px): x_vel = -1536; wrap x_pos < -20*1024 ->
  x_pos = (SCREEN_WIDTH+50)*1024 = 370*1024, y_pos = 5; y bounces off
  2*1024 and GROUND=(240-80-18)*1024=142*1024 with y_vel =
  +/- (1+rand()%3)*1024.
  Rocks (3, 42x40): x_vel = -1024 each; wrap when x+80*1024 <= 0 ->
  respawn x=(420+rand()%50)*1024, y=(160-rand()%120)*1024.
  Flowers (3, 16x29): x = rock.x + 21*1024, y = rock.y - 29*1024;
  pickup (checkHit pad=1) -> +1000 health, flower.x = -50*1024.
  checkHit(enemy, pad=5): AABB with player [15,37]x[y,y+18]:
    contact iff wx1<=32 && wx1>=-36 && by >= wy-13 && by <= wy+43.
  Death: health<0 -> clamp 0, bestScore=max(best,score), gs=5.

Phases (event-driven, ceilings as honesty bounds):
  A boot -> settle -> title gs 0 -> START -> gs 1 -> checkpoint
    savestate once gameMode is ticking (score>=3)
  D dynamics probe (260f): gravity, tap impulse (-3072), double-tap
  F flower-seek rehearsal from checkpoint (<=700f): steer into flower
  W wasp-dodge rehearsal from checkpoint (<=900f): full dodge policy
  I idle baseline from checkpoint (<=2300f): pure idle to death; class
    every health delta with entity coords; gs5; auto-return watch.

Boot ledger: fresh r35b ledger, boot 1 of max 3 (pre-run disclosed).
Savestate checkpoint file enables boot 2 policy retries without boots.
"""
import json
import os
import shutil
import sys
import time

import numpy as np
from PIL import Image

REPO = "/home/z/my-project/ps1ai"
sys.path.insert(0, REPO)
from ps1play.core.host import LibretroCore  # noqa: E402

BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BUZZ = "/home/z/my-project/emu/games_homebrew/patched/buzzybee_ntsc_lic.cue"

# ---- OUT dir: real repo scratch, else PolarFS mirror (disk-full fallback)
MIRROR_NOTE = None
OUT = os.path.join(REPO, "scratch", "r35b")
try:
    os.makedirs(os.path.join(OUT, "shots"), exist_ok=True)
    _probe = os.path.join(OUT, ".probe")
    with open(_probe, "w") as f:
        f.write("ok")
    os.remove(_probe)
except OSError as e:
    OUT = "/tmp/my-project/ps1ai/scratch/r35b"
    MIRROR_NOTE = (f"real scratch/r35b unwritable ({e.__class__.__name__}) "
                   f"— evidence written to PolarFS mirror {OUT}; sync-back "
                   f"attempted at end")
    os.makedirs(os.path.join(OUT, "shots"), exist_ok=True)
SHOTS = os.path.join(OUT, "shots")
BOOTS = os.path.join(OUT, "boots_used.json")
REAL_BOOTS = os.path.join(REPO, "scratch", "r35b", "boots_used.json")

FACTOR = 1024
GS, BEST, SCORE, HITF, HITE = (0x80058830, 0x80058838, 0x8005883C,
                               0x80058840, 0x80058844)
PLAYER, ENEMY, FLOWERS, ROCKS = 0x8005EDC0, 0x8005EB7C, 0x8005EBA0, 0x8005F55C
HEALTH, TIMER = 0x8005EF48, 0x8005F548
TVSYNC, TTOT = TIMER + 8, TIMER + 0x10

R = {"task": "r35b boot1: BuzzyBee entity discovery + baseline",
     "out_dir": OUT, "mirror_note": MIRROR_NOTE,
     "cap_policy": "fresh r35b ledger, max 3 boots; boot 1 = discovery",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": [], "checks": {}}
T0 = time.time()


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log_r35b_b1.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r35b.b1] {json.dumps(rec, default=str)[:250]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def i32(va):
    off = va - 0x80000000
    return int.from_bytes(bytes(core.ram[off:off + 4]), "little", signed=True)


def u32(va):
    off = va - 0x80000000
    return int.from_bytes(bytes(core.ram[off:off + 4]), "little")


def px(v):
    """C integer division by 1024 (truncation toward zero)."""
    return -((-v) // FACTOR) if v < 0 else v // FACTOR


def obj(base):
    return {"fn": i32(base), "idx": i32(base + 4), "tf": i32(base + 8),
            "y": i32(base + 12), "x": i32(base + 16),
            "xv": i32(base + 20), "yv": i32(base + 24),
            "rate": i32(base + 28), "il": u32(base + 32)}


def state():
    return {"gs": i32(GS), "best": i32(BEST), "score": i32(SCORE),
            "hp": i32(HEALTH), "hitE": i32(HITE), "hitF": i32(HITF),
            "p": obj(PLAYER), "e": obj(ENEMY),
            "f0": obj(FLOWERS), "f1": obj(FLOWERS + 0x24),
            "f2": obj(FLOWERS + 0x48),
            "r0": obj(ROCKS), "r1": obj(ROCKS + 0x24),
            "r2": obj(ROCKS + 0x48), "tv": i32(TVSYNC), "tt": i32(TTOT)}


def jl_writer(name):
    fh = open(os.path.join(OUT, name), "w")

    def w(rec):
        fh.write(json.dumps(rec, default=str) + "\n")
        return fh
    return w, fh


def flap_tap(hold=3):
    core.set_buttons("B")
    for _ in range(hold):
        core.run_frame()
    core.set_buttons(set())


def run_logged(n, w, phase):
    for _ in range(n):
        core.run(1, set())
        w({"ph": phase, "f": core.frames_run, **state()})


# ---- boot ledger (pre-run, BEFORE load_game) --------------------------
led_path = BOOTS if os.path.exists(BOOTS) else (
    REAL_BOOTS if os.path.exists(REAL_BOOTS) else BOOTS)
if os.path.exists(led_path):
    led = json.load(open(led_path))
    assert led["count"] == 0, f"r35b ledger expected 0, got {led['count']}"
else:
    led = {"count": 0, "cap": 3, "amendments": [], "log": [],
           "note": "R35-B fresh ledger; real-repo scratch dir unwritable "
                   "(disk-full), mirrored per mirror_note"}
led["count"] = 1
led["log"].append({"boot": 1, "script": "r35b_buzzybee_discover.py",
                   "out_dir": OUT, "mirror_note": MIRROR_NOTE,
                   "t": time.strftime("%FT%TZ", time.gmtime())})
json.dump(led, open(led_path, "w"), indent=1)
R["ledger_path"] = led_path

ws = os.path.join(OUT, "ws_b1")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(BUZZ)
log("boot", core=core.core_name, av=av, ram_mb=round(len(core.ram) / 1e6, 1))

# ---- A: settle -> title -> START -> checkpoint ------------------------
for _ in range(900):
    core.run(1, set())
st = state()
log("A_title", gs=st["gs"], score=st["score"], best=st["best"])
snap("A_title")
assert st["gs"] == 0, "expected title gs 0"

core.set_buttons("START")
for _ in range(40):
    core.run_frame()
core.set_buttons(set())
gs1 = None
for _ in range(200):
    core.run(1, set())
    if i32(GS) == 1:
        gs1 = core.frames_run
        break
st = state()
log("A_run1_started", gs1_frame=gs1, gs=st["gs"], hp=st["hp"])
snap("A_run1_start")
assert st["gs"] == 1, "expected gs 1 after START"

sc = -1
for _ in range(300):
    core.run(1, set())
    sc = i32(SCORE)
    if sc >= 3:
        break
st = state()
log("A_gamemode_ticking", score=sc, hp=st["hp"], tt=st["tt"])
CKPT = core.serialize()
open(os.path.join(OUT, "state_r35b_gs1.bin"), "wb").write(CKPT)
log("A_checkpoint_saved", bytes=len(CKPT), score=sc, hp=st["hp"],
    f_abs=core.frames_run)
snap("A_checkpoint")

# ---- D: dynamics probe (gravity + taps) --------------------------------
core.unserialize(CKPT)
wD, fhD = jl_writer("frames_b1_dyn.jsonl")
prev = state()
run_logged(60, wD, "D")            # pure gravity fall
core.set_buttons("B")               # tap 1: 3f hold
for _ in range(3):
    core.run(1, set())
    wD({"ph": "D", "f": core.frames_run, **state()})
core.set_buttons(set())
run_logged(45, wD, "D")
core.set_buttons("B")               # rapid double-tap probe (2f gap)
for _ in range(3):
    core.run(1, set())
    wD({"ph": "D", "f": core.frames_run, **state()})
core.set_buttons(set())
run_logged(10, wD, "D")
core.set_buttons("B")
for _ in range(3):
    core.run(1, set())
    wD({"ph": "D", "f": core.frames_run, **state()})
core.set_buttons(set())
run_logged(120, wD, "D")
fhD.close()
snap("D_after_taps")
d0, d1 = None, None
log("D_done")

# ---- F: flower-seek rehearsal ------------------------------------------
core.unserialize(CKPT)
wF, fhF = jl_writer("frames_b1_flower.jsonl")
pickups, last_edge = [], None
for i in range(700):
    core.run(1, set())
    s = state()
    wF({"ph": "F", "f": core.frames_run, **s})
    hp_prev = s["hp"]
    by, pvy = px(s["p"]["y"]), s["p"]["yv"]
    # nearest flower ahead
    tgt, chosen = None, None
    for key in ("f0", "f1", "f2"):
        fx, fy = px(s[key]["x"]), px(s[key]["y"])
        if 37 < fx <= 130:
            cand = fy + 14 - 9
            if tgt is None or fx < tgt[0]:
                tgt, chosen = (fx, cand), key
    if tgt is None:
        target = 95
    else:
        target = max(20, min(170, tgt[1]))
    flap = bool(by > target + 4 and pvy > -3000)
    if flap:
        flap_tap(3)
        core.run(1, set())
        s2 = state()
        wF({"ph": "F", "f": core.frames_run, **s2})
        s = s2
    dh = s["hp"] - hp_prev
    if dh <= -1000 or dh >= 900:
        rec = {"f": core.frames_run, "dh": dh, "by": by,
               "fx": {k: px(s[k]["x"]) for k in ("f0", "f1", "f2")},
               "fy": {k: px(s[k]["y"]) for k in ("f0", "f1", "f2")},
               "target": target, "chosen": chosen}
        pickups.append(rec)
        last_edge = core.frames_run
        snap("F_flower_edge")
        log("F_health_edge", **rec)
    if i32(GS) != 1:
        break
fhF.close()
log("F_done", pickups=pickups, gs=i32(GS))

# ---- W: wasp-dodge rehearsal (full policy dress rehearsal) -------------
def bot_policy(s, sticky):
    """Returns (flap, target, mode). Dodge > flower > hover."""
    by, pvy = px(s["p"]["y"]), s["p"]["yv"]
    wx1, wy = px(s["e"]["x"]), px(s["e"]["y"])
    dx = wx1 - 37  # px from bee right edge
    if -80 <= dx <= 100:
        above_lim = wy - 14          # safe above: by <= wy-14
        below_lim = wy + 44          # safe below: by >= wy+44
        room_a, room_b = above_lim - 18, 172 - below_lim
        if sticky.get("side") is None:
            sticky["side"] = "above" if room_a >= room_b else "below"
        if sticky["side"] == "above":
            target = max(20, above_lim - 10)
            if room_a < 4:
                target = min(170, below_lim + 6)
        else:
            target = min(170, below_lim + 8)
            if room_b < 4:
                target = max(20, above_lim - 6)
        return by > target + 4 and pvy > -3000, target, "dodge"
    sticky["side"] = None
    tgt = None
    for key in ("f0", "f1", "f2"):
        fx, fy = px(s[key]["x"]), px(s[key]["y"])
        if 37 < fx <= 110:
            cand = fy + 14 - 9
            if tgt is None or fx < tgt[0]:
                tgt = (fx, cand)
    target = tgt[1] if tgt else 95
    target = max(20, min(170, target))
    return by > target + 4 and pvy > -3000, target, \
        ("flower" if tgt else "hover")


core.unserialize(CKPT)
wW, fhW = jl_writer("frames_b1_dodge.jsonl")
sticky, hits, dodges, passes = {}, [], 0, []
in_pass, hit_in_pass, pass_start = False, False, None
for i in range(900):
    core.run(1, set())
    s = state()
    wW({"ph": "W", "f": core.frames_run, **s})
    wx1, wx2 = px(s["e"]["x"]), px(s["e"]["x"]) + 56
    if not in_pass and wx1 <= 100 and wx2 > 15:
        in_pass, hit_in_pass, pass_start = True, False, core.frames_run
    if in_pass:
        if wx2 < 15:
            in_pass = False
            passes.append({"start_f": pass_start, "end_f": core.frames_run,
                           "hit": hit_in_pass})
            if not hit_in_pass:
                dodges += 1
    hp_prev = s["hp"]
    flap, target, mode = bot_policy(s, sticky)
    if flap:
        flap_tap(3)
        core.run(1, set())
        s = state()
        wW({"ph": "W", "f": core.frames_run, **s})
    dh = s["hp"] - hp_prev
    if dh <= -1000:
        hit_in_pass = True
        hits.append({"f": core.frames_run, "dh": dh,
                     "by": px(s["p"]["y"]), "wy": px(s["e"]["y"]),
                     "wx": px(s["e"]["x"]), "side": sticky.get("side")})
        snap("W_wasp_hit")
        log("W_wasp_hit", **hits[-1])
    if dh >= 900:
        snap("W_flower_edge")
        log("W_flower_edge", f=core.frames_run, dh=dh,
            by=px(s["p"]["y"]), fx={k: px(s[k]["x"]) for k in ("f0", "f1", "f2")})
    if i32(GS) != 1:
        break
fhW.close()
log("W_done", hits=len(hits), dodges=dodges, passes=len(passes),
    gs=i32(GS), hp=i32(HEALTH), score=i32(SCORE))

# ---- I: idle baseline from checkpoint ----------------------------------
core.unserialize(CKPT)
wI, fhI = jl_writer("frames_b1_idle.jsonl")
edges, death_f, prev_hp = [], None, i32(HEALTH)
for i in range(2300):
    core.run(1, set())
    s = state()
    wI({"ph": "I", "f": core.frames_run, **s})
    dh = s["hp"] - prev_hp
    prev_hp = s["hp"]
    if dh <= -1000 or dh >= 900:
        rec = {"f": core.frames_run, "dh": dh, "by": px(s["p"]["y"]),
               "bvy": s["p"]["yv"], "wy": px(s["e"]["y"]),
               "wx": px(s["e"]["x"]), "wvy": s["e"]["yv"],
               "fx": {k: px(s[k]["x"]) for k in ("f0", "f1", "f2")},
               "fy": {k: px(s[k]["y"]) for k in ("f0", "f1", "f2")}}
        edges.append(rec)
        snap("I_edge")
        log("I_health_edge", **rec)
    if i32(GS) == 5:
        death_f = core.frames_run
        break
fhI.close()
st = state()
S1 = st["best"]
log("I_death", death_f=death_f, gs=st["gs"], score=st["score"], best=S1,
    hp=st["hp"], edges=len(edges))
snap("I_death_screen")

ret_f = None
for _ in range(600):
    core.run(1, set())
    if i32(GS) == 0:
        ret_f = core.frames_run
        break
st = state()
log("I_auto_return", ret_f=ret_f, gs=st["gs"], score=st["score"],
    best=st["best"])
snap("I_returned_title")

# ---- checks ------------------------------------------------------------
core.unserialize(CKPT)
run_logged(5, lambda r: None, "chk")
s = state()
C = R["checks"]
C["player_x_const_15360"] = bool(s["p"]["x"] == 15 * FACTOR)
C["player_xv_zero"] = bool(s["p"]["xv"] == 0)
C["enemy_xv_minus1536"] = bool(s["e"]["xv"] == -1536)
C["rock0_xv_minus1024"] = bool(s["r0"]["xv"] == -1024)
C["flower_follows_rock"] = bool(
    s["f0"]["x"] - s["r0"]["x"] == 21 * FACTOR and
    s["f0"]["y"] - s["r0"]["y"] == -29 * FACTOR)
C["health_init_5999"] = bool(s["hp"] in (5996, 5997, 5998, 5999))
C["anim_ils_mainPlayerL"] = bool(s["p"]["il"] == 0x8005E9AC)
C["anim_ils_enemiesL"] = bool(s["e"]["il"] == 0x8005F408)
log("checks", **C)

verdict = {
    "entity_map_verified": bool(all(
        C[k] for k in ("player_x_const_15360", "enemy_xv_minus1536",
                       "rock0_xv_minus1024", "flower_follows_rock"))),
    "idle_baseline": {"death_frame": death_f, "score": st["score"],
                      "best": S1, "edges": edges},
    "flower_rehearsal_pickups": len(pickups),
    "dodge_rehearsal": {"hits": len(hits), "dodges": dodges,
                        "passes": len(passes)},
}
R["verdict"] = verdict
log("verdict", **{k: v for k, v in verdict.items() if k != "idle_baseline"})
dump()

# ---- sync evidence back to the real repo if space allows ---------------
real_out = os.path.join(REPO, "scratch", "r35b")
if os.path.abspath(real_out) != os.path.abspath(OUT):
    try:
        os.makedirs(real_out, exist_ok=True)
        for root, _dirs, files in os.walk(OUT):
            rel = os.path.relpath(root, OUT)
            dst = os.path.join(real_out, rel) if rel != "." else real_out
            os.makedirs(dst, exist_ok=True)
            for fn in files:
                try:
                    shutil.copyfile(os.path.join(root, fn),
                                    os.path.join(dst, fn))
                except OSError:
                    pass
        with open(os.path.join(real_out, "MIRROR_NOTE.txt"), "w") as f:
            f.write(MIRROR_NOTE or "")
        log("sync_back", dst=real_out)
    except OSError as e:
        log("sync_back_failed", err=str(e)[:120])

print("[r35b.b1] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), flush=True)
