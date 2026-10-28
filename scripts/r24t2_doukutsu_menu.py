#!/usr/bin/env python3
"""r24t2_doukutsu_menu.py — Round 24 boot 3: probes on the REAL menu.

Boot 2 finding (disclosed): the bright phase at f~1860 is the INTRO
CUTSCENE (platform scene PNG), not the title menu; the 0x9098 RAM
cluster is cutscene-scene state, RETRACTED as a menu-cursor anchor.
CROSS during the cutscene causally skips it -> the real Cave Story
title menu (New/Load/Options) appears (PNG f2760). So boot 2 delivered
BOOTED_TITLE (PNG-confirmed) + one real state change (cutscene->menu),
but NO menu interactivity evidence.

Boot cap amendment 2 -> 3 (disclosed pre-run): boot 3 goes
  cutscene --CROSS(skip)--> menu --PNG gate--> idle control
  --> DOWN/UP set-algebra AT THE MENU --> DOWN re-confirm
  --> UP back to New --> CROSS on New Game --> watch the next phase
  (name entry / intro text / first room) and, if it looks in-game,
  a cheap LEFT/RIGHT movement probe with its own RAM set-algebra.
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

OUT = os.path.join(REPO, "scratch", "r24", "doukutsu")
SHOTS = os.path.join(OUT, "shots")
CONTENT = "/home/z/my-project/emu/games_homebrew/patched/doukutsu_lic.cue"
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")
PADSIG = b"\x00\x41\xff\xff"

R = {"task": "r24t2 doukutsu REAL-menu probes -> New Game",
     "content": CONTENT,
     "boot_amendment": "cap 2->3 disclosed pre-run: boot-2 menu probes "
                       "hit the intro cutscene (bright phase misread); "
                       "0x9098 cluster retracted as menu anchor",
     "started": time.strftime("%FT%TZ", time.gmtime()),
     "events": [], "shots": []}


def boots_used():
    if os.path.exists(BOOTS):
        return json.load(open(BOOTS)).get("count", 0)
    return 0


def dump():
    json.dump(R, open(os.path.join(OUT, "boot_log.json"), "w"),
              indent=1, default=str)


def log(ev, **kw):
    rec = {"f": core.frames_run, "t": round(time.time() - T0, 1),
           "event": ev, **kw}
    R["events"].append(rec)
    print(f"[r24t2] {json.dumps(rec, default=str)[:230]}", flush=True)
    dump()


def snap(tag):
    arr = core.frame_rgb()
    if arr is not None:
        p = os.path.join(SHOTS, f"{tag}_f{core.frames_run:05d}.png")
        Image.fromarray(arr).save(p)
        R["shots"].append({"tag": tag, "frame": core.frames_run,
                           "png": os.path.relpath(p, OUT)})
    return arr


def mad(a, b):
    if a is None or b is None or a.shape != b.shape:
        return -1.0
    return round(float(np.abs(a.astype(int) - b.astype(int)).mean()), 3)


def ram_arr():
    return np.frombuffer(bytes(core.ram), dtype=np.uint8)


def pad_hits():
    s = bytes(core.ram)
    n, i = 0, 0
    while True:
        i = s.find(PADSIG, i)
        if i < 0:
            break
        n += 1
        i += 1
    return n


def setalg(A0, A1, A2, A3):
    S1 = set(int(i) for i in np.nonzero(A1 != A0)[0])
    S2 = set(int(i) for i in np.nonzero(A2 != A1)[0])
    rev = sorted(i for i in (S1 & S2) if A2[i] == A0[i])
    ret = sorted(i for i in rev if A3[i] != A2[i])
    return rev, ret


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 2, f"boot counter {n0} != 2"
json.dump({"count": 3,
           "amendments": [
               {"from": 1, "to": 2, "reason": "boot-1 settle heuristic bug",
                "disclosed": "pre-run"},
               {"from": 2, "to": 3,
                "reason": "boot-2 menu probes hit the intro cutscene "
                          "(bright phase misread as menu); 0x9098 "
                          "retracted; boot 3 probes the real menu",
                "disclosed": "pre-run of r24t2"}],
           "log": [
               {"boot": 1, "script": "r24t1", "outcome": "FAILED (settle bug)"},
               {"boot": 2, "script": "r24t1 (fixed)",
                "outcome": "BOOTED_TITLE (menu PNG after cutscene skip) "
                           "+ cutscene->menu state change; menu probes "
                           "invalid (cutscene RAM)"},
               {"boot": 3, "script": "r24t2_doukutsu_menu.py",
                "t": time.strftime("%FT%TZ", time.gmtime())}]},
          open(BOOTS, "w"), indent=1)

ws = os.path.join(OUT, "ws")
os.makedirs(os.path.join(ws, "system"), exist_ok=True)
os.makedirs(os.path.join(ws, "saves"), exist_ok=True)
shutil.copyfile(BIOS, os.path.join(ws, "system", "openbios.bin"))
core = LibretroCore(CORE, os.path.join(ws, "system"),
                    os.path.join(ws, "saves"),
                    var_overrides={b"beetle_psx_renderer": b"software",
                                   b"beetle_psx_frame_duping": b"disabled"})
av = core.load_game(CONTENT)
log("boot", core=core.core_name, av=av)

# ---- phase 1: wait through loading + cutscene, then SKIP it -------------
while core.frames_run < 1200:
    core.run_frame()
snap("pre_skip")
core.run(4, {"B"})
core.run(90, set())
menu0 = snap("menu_candidate")
log("skip_cross", mean=None if menu0 is None else round(float(menu0.mean()), 2))

# ---- phase 2: menu gate: title menu means dark bg + white text ----------
# measured menu signature (boot 2 f2760): mean ~34, stable; cutscene is
# bright (mean>20 animated platform scene). Gate: mean in [25, 45] and
# 3 consecutive 60f windows with mad < 1 (menu bg is near-static).
stable = 0
menu_f = None
for k in range(20):
    core.run(60, set())
    a = core.frame_rgb()
    b = core.frame_rgb()
    core.run(60, set())
    c = core.frame_rgb()
    m1, m2 = mad(a, b), mad(b, c)
    g = float(b.mean()) if b is not None else -1
    stable = stable + 1 if (m1 < 1.0 and m2 < 1.0 and 25 < g < 45) else 0
    if stable >= 3:
        menu_f = core.frames_run
        break
menu_pic = snap("menu_confirmed")
log("menu_gate", menu_f=menu_f, mean=round(float(menu_pic.mean()), 2)
    if menu_pic is not None else None)

# ---- phase 3: idle control AT THE MENU ----------------------------------
ctrl = []
for _ in range(5):
    a = core.frame_rgb()
    core.run(30, set())
    ctrl.append(mad(a, core.frame_rgb()))
ctrl_max = max(ctrl)
log("idle_control", ctrl=ctrl, pad_hits=pad_hits())

# ---- phase 4: DOWN/UP set-algebra AT THE MENU ---------------------------
A0 = ram_arr().copy()
pre_down = core.frame_rgb()
core.run(2, {"DOWN"})
core.run(38, set())
A1 = ram_arr().copy()
post_down = snap("menu_down")
vd_down = mad(pre_down, post_down)
core.run(2, {"UP"})
core.run(38, set())
A2 = ram_arr().copy()
post_up = snap("menu_up")
vd_up = mad(post_down, post_up)
core.run(2, {"DOWN"})
core.run(38, set())
A3 = ram_arr().copy()
retouch_pic = snap("menu_down2")
vd_down2 = mad(post_up, retouch_pic)
rev, ret = setalg(A0, A1, A2, A3)
anchor_ok = len(ret) > 0
log("menu_setalg", reverted=len(rev), retouch=len(ret),
    rev_head=[hex(i) for i in rev[:12]], ret_head=[hex(i) for i in ret[:12]],
    vd_down=vd_down, vd_up=vd_up, vd_down2=vd_down2, ctrl_max=ctrl_max)
cursor_ok = anchor_ok and vd_down2 > 0.15
snap("menu_cursor_state")

# ---- phase 5: back to New (UP), then CROSS on New Game ------------------
core.run(2, {"UP"})   # cursor back to the default entry
core.run(30, set())
pre_new = snap("pre_new")
A4 = ram_arr().copy()
core.run(4, {"B"})
core.run(120, set())
A5 = ram_arr().copy()
post_new = snap("post_new")
new_vd = mad(pre_new, post_new)
new_flip = int(np.count_nonzero(A5 != A4))
watch = []
for k in range(10):
    core.run(60, set())
    f = snap(f"new_watch_{k}")
    watch.append({"f": core.frames_run,
                  "mean": None if f is None else round(float(f.mean()), 2)})
final = snap("new_final")
sustain = mad(post_new, final)
log("new_game", new_vd=new_vd, ram_flip=new_flip, watch=watch,
    sustain=sustain, pad_hits_after=pad_hits())

# heuristic in-game check: gameplay screens have persistent non-bg content
# and usually animate (Quote sprite idle). Record, don't over-claim.
looks_ingame = 20 < float(final.mean()) < 60 and sustain > 0.05

# ---- phase 6 (cheap): if in-game, LEFT/RIGHT movement probe -------------
move = None
if looks_ingame:
    M0 = ram_arr().copy()
    pre_l = core.frame_rgb()
    core.run(3, {"LEFT"})
    core.run(57, set())
    M1 = ram_arr().copy()
    post_l = snap("move_left")
    core.run(3, {"RIGHT"})
    core.run(57, set())
    M2 = ram_arr().copy()
    post_r = snap("move_right")
    M3 = ram_arr().copy()
    core.run(3, {"LEFT"})
    core.run(57, set())
    M4 = ram_arr().copy()
    moved = sorted(i for i in range(len(M1)) if M1[i] != M0[i]
                   and M3[i] != M2[i])
    move = {"left_vd": mad(pre_l, post_l), "right_vd": mad(post_l, post_r),
            "candidate_movers": len(moved),
            "head": [hex(i) for i in moved[:12]]}
    log("move_probe", **move)

# ---- verdicts ------------------------------------------------------------
R["verdicts"] = {
    "BOOTED_TITLE": bool(menu_f is not None),
    "INPUT_RESPONSIVE": bool(cursor_ok),
    "STATE_CHANGE_CONFIRMED": bool(cursor_ok and new_vd > 3.0
                                   and new_flip > 1024),
    "MOVE_PROBE_RAN": bool(move is not None),
}
R["verdict"] = ("STATE_CHANGE_CONFIRMED"
                if R["verdicts"]["STATE_CHANGE_CONFIRMED"] else
                "INPUT_RESPONSIVE" if R["verdicts"]["INPUT_RESPONSIVE"]
                else "BOOTED_TITLE" if R["verdicts"]["BOOTED_TITLE"]
                else "FAILED")
R["final"] = {"menu_f": menu_f, "ctrl": ctrl, "reverted": len(rev),
              "retouch": len(ret), "new_vd": new_vd, "new_flip": new_flip,
              "sustain": sustain, "looks_ingame": looks_ingame,
              "move": move}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r24t2] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), flush=True)
