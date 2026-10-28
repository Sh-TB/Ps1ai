#!/usr/bin/env python3
"""r24t1_doukutsu_boot.py — Round 24 Cave Story (doukutsupsx v0.7) boot.

State since r13: BOOTED_TITLE (title menu New/Load/Options @ ~f1740,
2 pad buffers). Nothing above that rung has ever been claimed.

BOOT DISCLOSURE (cap amendment 1 -> 2): boot 1 was consumed by a settle-
heuristic bug (bright-shell frame at f60 tripped `mean > 20` long before
the real menu; probes hit the intro, not the menu; verdict FAILED was
recorded honestly in boot_log.json). Boot 2 re-runs the same program
with a two-stage settle gate (dark LOADING phase seen first, then
sustained bright title) plus a START fallback probe. Disclosed pre-run.

Honest ladder targets:
  - INPUT_RESPONSIVE: menu cursor moves causally (RAM set-algebra anchor:
    address changes on DOWN, reverts on UP, retouches on DOWN again;
    visual pulses vs idle control as supporting evidence).
  - STATE_CHANGE_CONFIRMED: CROSS (ps1play "B") on the default entry
    (New Game) -> sustained new screen phase, PNG-documented.

Image: patched/doukutsu_lic.bin — rebuilt this round (r24t0),
byte-identical to the r13 image (sha256 bf15559e...7554; the release
already carries the standard US license block, overwrite is a no-op).
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

R = {"task": "r24t1 doukutsupsx title->newgame (boot 2 after settle bug)",
     "content": CONTENT,
     "image_note": "rebuilt r24t0, sha256 bf15559e...7554 byte-identical "
                   "to r13 (license no-op)",
     "boot_amendment": "cap 1->2 disclosed: boot 1 consumed by settle "
                       "heuristic bug (bright shell @f60 misread as title; "
                       "probes hit intro), verdict FAILED logged",
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
    print(f"[r24t1] {json.dumps(rec, default=str)[:230]}", flush=True)
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


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 1, f"boot counter {n0} != 1 (boot 1 = settle-bug run)"
json.dump({"count": 2,
           "amendments": [{"from": 1, "to": 2, "reason":
                           "boot-1 settle heuristic bug (bright shell "
                           "misread as title); disclosed pre-run"}],
           "log": [{"boot": 1, "script": "r24t1_doukutsu_boot.py",
                    "outcome": "FAILED (settle bug, probes hit intro)",
                    "t": "2026-10-28"},
                   {"boot": 2, "script": "r24t1_doukutsu_boot.py (fixed)",
                    "image": "doukutsu_lic.bin (license no-op)",
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
log("boot", core=core.core_name, ver=core.core_ver, av=av)

# ---- phase 1: two-stage settle: dark LOADING first, then bright title ----
seen_loading = None
bright_streak = 0
title_f = None
while core.frames_run < 5400:
    core.run_frame()
    if core.frames_run % 60:
        continue
    fr = core.frame_rgb()
    if fr is None:
        continue
    g = float(fr.mean())
    if core.frames_run % 300 == 0:
        snap("settle")
    if g < 15.0:
        if seen_loading is None:
            seen_loading = core.frames_run
            log("loading_phase", f=core.frames_run, mean=round(g, 2))
        bright_streak = 0
        continue
    if seen_loading is not None and g > 20.0:
        bright_streak += 1
        if bright_streak >= 3:
            title_f = core.frames_run
            break
log("settle", title_f=title_f, loading_f=seen_loading)
fr_title = snap("title")

# ---- phase 2: pad buffers + idle control AT THE MENU --------------------
pad_n = pad_hits()
ctrl = []
for _ in range(5):
    a = core.frame_rgb()
    core.run(30, set())
    ctrl.append(mad(a, core.frame_rgb()))
log("idle_control", pad_hits=pad_n, ctrl=ctrl)
ctrl_max = max(ctrl)

# ---- phase 3: DOWN/UP set-algebra on RAM + visual causality -------------
A0 = ram_arr().copy()
before_down = core.frame_rgb()
core.run(2, {"DOWN"})
core.run(38, set())
after_down = core.frame_rgb()
A1 = ram_arr().copy()
snap("after_down")

core.run(2, {"UP"})
core.run(38, set())
after_up = core.frame_rgb()
A2 = ram_arr().copy()
snap("after_up")

S1 = set(int(i) for i in np.nonzero(A1 != A0)[0])
S2 = set(int(i) for i in np.nonzero(A2 != A1)[0])
reverted = sorted(i for i in (S1 & S2) if A2[i] == A0[i])
log("set_algebra", down_changed=len(S1), up_changed=len(S2),
    reverted=len(reverted), reverted_head=[hex(i) for i in reverted[:12]])

# confirmation pulse: DOWN again must re-touch the reverted candidates
core.run(2, {"DOWN"})
core.run(38, set())
A3 = ram_arr().copy()
retouch = sorted(i for i in reverted if A3[i] != A2[i])
after_down2 = core.frame_rgb()
vd_down2 = mad(after_up, after_down2)
vd_down = mad(before_down, after_down)
anchor_ok = len(retouch) > 0
menu_ok = anchor_ok  # RAM anchor is the primary evidence on an animated menu
log("menu_probes", vd_down=vd_down, vd_down2=vd_down2,
    ctrl_max=ctrl_max, retouch=len(retouch),
    retouch_head=[hex(i) for i in retouch[:12]],
    anchor_ok=anchor_ok)
snap("menu_after_probes")

# ---- phase 4: CROSS (B) on the default entry -> New Game ----------------
pre = snap("pre_cross")
A4 = ram_arr().copy()
core.run(4, {"B"})
core.run(86, set())
post = snap("post_cross")
cross_vd = mad(pre, post)
A5 = ram_arr().copy()
ram_flip = int(np.count_nonzero(A5 != A4))
watch = []
for k in range(9):
    core.run(60, set())
    f = snap(f"watch_{k}")
    watch.append({"f": core.frames_run,
                  "mean": None if f is None else round(float(f.mean()), 2)})
post2 = snap("post_watch")
sustain = mad(post, post2)
log("cross_newgame", cross_vd=cross_vd, ram_flip=ram_flip,
    watch=watch, sustain_mad=sustain)

pre_mean = float(pre.mean()) if pre is not None else -1
post_mean = float(post2.mean()) if post2 is not None else -1
state_ok = (cross_vd > 5.0 and ram_flip > 64
            and (sustain > 0.2 or abs(post_mean - pre_mean) > 3))
fallback = ""
if not state_ok:
    # START fallback probe (same boot, disclosed)
    pre_s = core.frame_rgb()
    core.run(4, {"START"})
    core.run(86, set())
    post_s = snap("post_start")
    start_vd = mad(pre_s, post_s)
    A6 = ram_arr().copy()
    start_flip = int(np.count_nonzero(A6 != A5))
    state_ok = (start_vd > 5.0 and start_flip > 64
                and abs(float(post_s.mean()) - float(pre_s.mean())) > 3)
    fallback = f"START vd={start_vd} flip={start_flip}"
    log("start_fallback", start_vd=start_vd, start_flip=start_flip,
        state_ok=state_ok)
snap("final_state")

# ---- verdicts -----------------------------------------------------------
R["verdicts"] = {
    "BOOTED_TITLE": bool(title_f is not None and pad_n >= 1),
    "INPUT_RESPONSIVE": bool(title_f is not None and menu_ok),
    "STATE_CHANGE_CONFIRMED": bool(menu_ok and state_ok),
}
R["verdict"] = ("STATE_CHANGE_CONFIRMED"
                if R["verdicts"]["STATE_CHANGE_CONFIRMED"] else
                "INPUT_RESPONSIVE" if R["verdicts"]["INPUT_RESPONSIVE"]
                else "BOOTED_TITLE" if R["verdicts"]["BOOTED_TITLE"]
                else "FAILED")
R["final"] = {"title_f": title_f, "loading_f": seen_loading,
              "pad_hits": pad_n, "ctrl": ctrl,
              "reverted": [hex(i) for i in reverted[:24]],
              "retouch": [hex(i) for i in retouch[:24]],
              "cross_vd": cross_vd, "ram_flip": ram_flip,
              "sustain_mad": sustain, "pre_mean": round(pre_mean, 2),
              "post_mean": round(post_mean, 2), "fallback": fallback}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r24t1] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), flush=True)
