#!/usr/bin/env python3
"""r26t1_zenmai_launch.py — Round 26: zenmai launch diagnostics.

State: INPUT_DEAD_AT_MENU (r22 demotion: r21's opening@f910 was the
LANGUAGE MENU, START never launched, TX-only-wait-RXRDY class source-
proven). The r21 padtest SIO handshake shim (zenmai_lic_r21b disc,
disclosed game-side patch) is rebuilt byte-exact this round (patch
chain re-applied with assertions; psexe sha-verified 7f4be544...e4e2).

Boot cap: hard cap 1 (fresh counter). Program — diagnostic ladder for
the launch blocker, every step PNG'd + RAM-diffed:
  1. settle to the language menu (r22 recon: mean ~31 @f630..f910)
  2. menu cursor causality: DOWN pulse (ENGLISH is below 日本語),
     RAM diff + visual; UP fallback if DOWN is inert
  3. launch attempts, each followed by a 300f watch + BSS scan for the
     z3 story signature / "West of House" (>0xBA800, image ends 0xBA800):
     a. START hold 4f          b. START hold 90f
     c. CROSS hold 4f          d. CROSS hold 90f
     e. back to 日本語 (UP), START hold 4f
        hypothesis: the ENGLISH switch breaks the launch path
  4. if launched: PNG the opening, honest partial verdict (typing/world
     response is the NEXT train — T9 chords need their own careful run).
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

OUT = os.path.join(REPO, "scratch", "r26", "zenmai")
SHOTS = os.path.join(OUT, "shots")
CONTENT = ("/home/z/my-project/emu/games_homebrew/patched/"
           "zenmai_lic_r21b.cue")
CORE = "/home/z/my-project/ps1-test/cores/mednafen_psx_libretro.so"
BIOS = "/home/z/my-project/ps1-test/emu/system/openbios.bin"
BOOTS = os.path.join(OUT, "boots_used.json")

IMAGE_END = 0xBA800
Z3_SIG = bytes.fromhex("00774b5450d5389903e602b02c12")
OPENING = b"West of House"
OPENING2 = b"ZORK I"

R = {"task": "r26t1 zenmai launch diagnostics (r21b SIO shim disc)",
     "boot_cap": 1,
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
    print(f"[r26t1] {json.dumps(rec, default=str)[:230]}", flush=True)
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


def bss_story():
    """story signatures in BSS (above the loaded image)."""
    s = bytes(core.ram)
    return {"z3_sig": s.find(Z3_SIG, IMAGE_END),
            "west_of_house": s.find(OPENING, IMAGE_END),
            "zork_banner": s.find(OPENING2, IMAGE_END)}


T0 = time.time()
for d in (OUT, SHOTS):
    os.makedirs(d, exist_ok=True)
n0 = boots_used()
assert n0 == 0, f"boot counter {n0} != 0 (hard cap 1 for r26t1)"
json.dump({"count": 1,
           "log": [{"boot": 1, "script": "r26t1_zenmai_launch.py",
                    "disc": "zenmai_lic_r21b (r21 padtest SIO shim, "
                            "disclosed game-side patch; rebuilt r26)",
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

# ---- phase 1: settle to the language menu --------------------------------
menu_f = None
while core.frames_run < 2400:
    core.run_frame()
    if core.frames_run % 60:
        continue
    fr = core.frame_rgb()
    if fr is None:
        continue
    g = float(fr.mean())
    if core.frames_run % 240 == 0:
        snap("settle")
    if 25 < g < 40:
        menu_f = core.frames_run
        break
menu = snap("menu")
log("menu", menu_f=menu_f,
    mean=round(float(menu.mean()), 2) if menu is not None else None)

# ---- phase 2: menu cursor causality --------------------------------------
ctrl = []
for _ in range(4):
    a = core.frame_rgb()
    core.run(30, set())
    ctrl.append(mad(a, core.frame_rgb()))
ctrl_max = max(ctrl)
A0 = ram_arr = np.frombuffer(bytes(core.ram), dtype=np.uint8).copy()
pre = core.frame_rgb()
core.run(2, {"DOWN"})
core.run(38, set())
A1 = np.frombuffer(bytes(core.ram), dtype=np.uint8).copy()
post = snap("after_down")
vd_down = mad(pre, post)
down_changed = int(np.count_nonzero(A1 != A0))
log("down_probe", vd_down=vd_down, ram_changed=down_changed,
    ctrl_max=ctrl_max)
if vd_down <= 2 * max(ctrl_max, 0.05):
    pre = core.frame_rgb()
    core.run(2, {"UP"})
    core.run(38, set())
    post = snap("after_up")
    vd_up = mad(pre, post)
    log("up_probe", vd_up=vd_up)
    cursor_ok = vd_up > 2 * max(ctrl_max, 0.05)
else:
    vd_up = -1
    cursor_ok = True
snap("menu_cursor_state")

# ---- phase 3: launch attempts ---------------------------------------------
def try_launch(btn, hold, tag):
    pre = core.frame_rgb()
    core.run(hold, {btn})
    core.run(300, set())
    post = snap(tag)
    story = bss_story()
    vd = mad(pre, post)
    launched = (story["z3_sig"] >= 0 or story["west_of_house"] >= 0
                or story["zork_banner"] >= 0)
    rec = {"btn": btn, "hold": hold, "vd": vd, "story": story,
           "launched": launched,
           "mean": round(float(post.mean()), 2) if post is not None
           else None}
    log("launch_try", tag=tag, **rec)
    return rec


tries = {}
tries["start_4"] = try_launch("START", 4, "try_start4")
if not tries["start_4"]["launched"]:
    tries["start_90"] = try_launch("START", 90, "try_start90")
if not any(t["launched"] for t in tries.values()):
    tries["cross_4"] = try_launch("B", 4, "try_cross4")
if not any(t["launched"] for t in tries.values()):
    tries["cross_90"] = try_launch("B", 90, "try_cross90")
if not any(t["launched"] for t in tries.values()):
    # back to 日本語 default, START again
    core.run(2, {"UP"})
    core.run(40, set())
    tries["jp_start4"] = try_launch("START", 4, "try_jp_start4")
launched = any(t["launched"] for t in tries.values())
snap("final_state")

# ---- verdicts -------------------------------------------------------------
R["verdicts"] = {
    "MENU_REACHED": menu_f is not None,
    "MENU_CURSOR_CAUSAL": bool(cursor_ok),
    "LAUNCHED": bool(launched),
}
R["verdict"] = ("LAUNCHED" if launched else
                "MENU_CURSOR_CAUSAL" if cursor_ok else
                "MENU_REACHED" if menu_f is not None else "FAILED")
R["final"] = {"menu_f": menu_f, "ctrl": ctrl, "vd_down": vd_down,
              "vd_up": vd_up, "tries": {k: {kk: vv for kk, vv in
                                            v.items()}
                                        for k, v in tries.items()}}
R["frames_total"] = core.frames_run
R["finished"] = time.strftime("%FT%TZ", time.gmtime())
dump()
print("[r26t1] DONE frames=", core.frames_run,
      "wall=", round(time.time() - T0, 1), "verdict=", R["verdict"],
      json.dumps(R["verdicts"]), flush=True)
